"""Pipeline execution route with SSE progress streaming."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from threading import Thread

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from reviewtrace.api.schemas import JobStarted, JobStatus, RunRequest

router = APIRouter()

# ── In-memory job registry ────────────────────────────────────────────────────

_job_queues: dict[str, asyncio.Queue] = {}
_job_status: dict[str, str] = {}   # running | done | error
_event_counts: dict[str, int] = {}
_main_loop: asyncio.AbstractEventLoop | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/run", response_model=JobStarted)
async def start_run(req: RunRequest) -> JobStarted:
    """Start the full pipeline in a background thread and return a job_id."""
    global _main_loop
    _main_loop = asyncio.get_event_loop()

    job_id = uuid.uuid4().hex[:8]
    _job_queues[job_id] = asyncio.Queue()
    _job_status[job_id] = "running"
    _event_counts[job_id] = 0

    thread = Thread(target=_run_pipeline, args=(job_id, req), daemon=True)
    thread.start()

    return JobStarted(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    return JobStatus(
        job_id=job_id,
        status=_job_status.get(job_id, "unknown"),
        event_count=_event_counts.get(job_id, 0),
    )


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    """SSE endpoint — streams job progress events until done or error."""
    if job_id not in _job_queues:
        return StreamingResponse(
            _one_shot_error("Job not found"),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        _event_generator(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── SSE helpers ───────────────────────────────────────────────────────────────


async def _event_generator(job_id: str):
    queue = _job_queues[job_id]
    while True:
        event = await queue.get()
        _event_counts[job_id] = _event_counts.get(job_id, 0) + 1
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") in ("done", "error"):
            _job_status[job_id] = event["type"]
            break


async def _one_shot_error(msg: str):
    yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"


def _send(job_id: str, event: dict) -> None:
    """Thread-safe: enqueue an event onto the asyncio queue."""
    if _main_loop and job_id in _job_queues:
        asyncio.run_coroutine_threadsafe(_job_queues[job_id].put(event), _main_loop)


def _emit(job_id: str, step: str, message: str) -> None:
    _send(job_id, {"type": "progress", "step": step, "message": message})


# ── Blocking pipeline runner (runs in a worker thread) ───────────────────────


def _run_pipeline(job_id: str, req: RunRequest) -> None:  # noqa: C901
    import asyncio as _asyncio
    import traceback

    try:
        from reviewtrace.audit.dedup import run_dedup
        from reviewtrace.audit.export import export_json, export_markdown
        from reviewtrace.db.connection import fetchall, init_db
        from reviewtrace.evidence.extractor import run_extraction
        from reviewtrace.evidence.matrix import export_items_json, export_matrix_csv
        from reviewtrace.expansion.controller import expand as run_expand
        from reviewtrace.export.csv_export import export_papers_csv
        from reviewtrace.export.graphml_export import export_graphml
        from reviewtrace.retrieval.orchestrator import run_queries
        from reviewtrace.retrieval.planner import plan_queries
        from reviewtrace.retrieval.seed_loader import load_seeds
        from reviewtrace.screening.models import ScreeningCriteria
        from reviewtrace.screening.policy import load_policy
        from reviewtrace.screening.screener import run_screening
        from reviewtrace.taxonomy.controller import run_taxonomy
        from reviewtrace.taxonomy.exporter import export_taxonomy_md

        db_path = os.getenv("REVIEWTRACE_DB_PATH", "reviewtrace.db")
        output_dir = Path(os.getenv("REVIEWTRACE_OUTPUT_DIR", "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)
        init_db(db_path)

        # 1. Keyword retrieval
        _emit(job_id, "retrieval", "Planning search queries…")
        queries = plan_queries(req.topic, max_results_per_query=req.max_results)
        n_sources = len({q.source for q in queries})
        _emit(job_id, "retrieval", f"Running {len(queries)} queries across {n_sources} sources…")
        papers = _asyncio.run(run_queries(queries))
        _emit(job_id, "retrieval", f"✓ {len(papers)} papers retrieved")

        # 2. Seed papers
        seed_ids: list[str] = []
        if req.seeds.strip():
            _emit(job_id, "seeds", "Loading seed papers…")
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(req.seeds)
                tmp = f.name
            seed_ids = load_seeds(Path(tmp))
            Path(tmp).unlink(missing_ok=True)
            _emit(job_id, "seeds", f"✓ {len(seed_ids)} seed papers loaded")
        else:
            _emit(job_id, "seeds", "No seeds provided — skipping")

        # 3. Dedup
        _emit(job_id, "dedup", "Deduplicating paper pool…")
        r = run_dedup()
        _emit(job_id, "dedup", f"✓ {r.total_before} → {r.total_after} papers ({r.fuzzy_merges} fuzzy merges)")

        # 4. Citation expansion
        if not req.skip_expand:
            _emit(job_id, "expand", "Building citation graph (BFS)…")
            expand_seeds = seed_ids or [p["id"] for p in fetchall("SELECT id FROM papers")]
            exp = _asyncio.run(
                run_expand(expand_seeds, max_depth=req.depth, max_papers_per_hop=req.max_per_hop)
            )
            _emit(job_id, "expand", f"✓ +{exp.new_papers_count} papers in {exp.total_hops} hops")
            r2 = run_dedup()
            _emit(job_id, "dedup", f"✓ Post-expansion: {r2.total_after} canonical papers")
        else:
            _emit(job_id, "expand", "Citation expansion skipped")

        # 5. Screening
        _emit(job_id, "screening", "Screening papers with LLM…")
        criteria = ScreeningCriteria(
            topic=req.criteria_topic or req.topic,
            inclusion=req.inclusion,
            exclusion=req.exclusion,
        )
        decisions = run_screening(criteria, policy=load_policy(), delay_seconds=req.llm_delay)
        inc = sum(1 for d in decisions if d.decision == "include")
        _emit(job_id, "screening", f"✓ include={inc}  exclude={len(decisions) - inc}")

        # 6. Evidence extraction
        _emit(job_id, "evidence", "Extracting evidence from included papers…")
        items = run_extraction(delay_seconds=req.llm_delay)
        _emit(job_id, "evidence", f"✓ {len(items)} evidence items extracted")

        # 7. Taxonomy
        _emit(job_id, "taxonomy", "Building taxonomy (embed → cluster → label)…")
        tax = run_taxonomy()
        _emit(job_id, "taxonomy", f"✓ {tax.n_nodes} nodes · {tax.n_evidence_links} evidence links")

        # Export
        _emit(job_id, "export", "Writing output files…")
        export_papers_csv(output_dir / "papers.csv")
        export_json(output_dir / "retrieval_audit.json")
        export_markdown(output_dir / "retrieval_audit.md")
        export_graphml(output_dir / "citation_graph.graphml")
        export_matrix_csv(output_dir / "evidence_matrix.csv")
        export_items_json(output_dir / "evidence_items.json")
        export_taxonomy_md(output_dir / "taxonomy.md")
        _emit(job_id, "export", f"✓ Outputs written to {output_dir}/")

        _send(job_id, {"type": "done", "message": "Pipeline complete!"})

    except Exception as e:
        _send(
            job_id,
            {"type": "error", "message": str(e), "traceback": traceback.format_exc()},
        )
