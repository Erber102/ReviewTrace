"""ReviewTrace CLI entry point."""

import json
from pathlib import Path

import typer

app = typer.Typer(help="ReviewTrace — auditable literature review pipeline")

# ---------------------------------------------------------------------------
# Demo defaults
# ---------------------------------------------------------------------------

_DEMO_TOPIC = "Sparse Autoencoders for Mechanistic Interpretability"
_DEMO_SEEDS = Path("examples/sparse_autoencoders/seeds.txt")
_DEMO_CRITERIA = Path("examples/sparse_autoencoders/criteria.json")
_DEMO_OUTPUT_DIR = Path("outputs/sparse_autoencoders_demo")


# ---------------------------------------------------------------------------
# T8.1  Full pipeline
# ---------------------------------------------------------------------------

@app.command()
def run(
    topic: str = typer.Option(..., "--topic", "-t", help="Research topic"),
    seeds: Path = typer.Option(None, "--seeds", "-s", help="Seeds file (one arXiv/DOI per line)"),
    criteria: Path = typer.Option(None, "--criteria", "-c", help="Screening criteria JSON file"),
    db_path: Path | None = typer.Option(None, "--db", help="SQLite database path (default: <output-dir>/reviewtrace.db)"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Max results per query"),
    depth: int = typer.Option(2, "--depth", help="Citation expansion depth"),
    max_per_hop: int = typer.Option(30, "--max-per-hop", help="Max papers per expansion hop"),
    llm_delay: float = typer.Option(0.5, "--llm-delay", help="Seconds between LLM calls"),
    skip_expand: bool = typer.Option(False, "--skip-expand", help="Skip citation graph expansion"),
    demo: bool = typer.Option(False, "--demo", help="Demo mode: max 3 queries, max_results=15, depth=0, no S2"),
    max_queries: int = typer.Option(None, "--max-queries", help="Cap number of search queries"),
    fresh: bool = typer.Option(False, "--fresh/--no-fresh", help="Delete DB and clear output dir before running"),
) -> None:
    """Run the full ReviewTrace pipeline end-to-end.

    Steps: retrieve → load seeds → dedup → [expand → dedup] → screen → extract → taxonomize → export
    """
    if demo:
        if max_results == 50:
            max_results = 15
        if depth == 2:
            depth = 0
        if not skip_expand:
            skip_expand = True
        typer.echo("[demo] Demo mode enabled: max_results=15, depth=0, skip_expand=True, max 3 queries")

    _execute_pipeline(
        topic=topic,
        seeds=seeds,
        criteria=criteria,
        db_path=db_path,
        output_dir=output_dir,
        max_results=max_results,
        depth=depth,
        max_per_hop=max_per_hop,
        llm_delay=llm_delay,
        skip_expand=skip_expand,
        demo=demo,
        max_queries=max_queries,
        fresh=fresh,
    )


# ---------------------------------------------------------------------------
# One-command demo
# ---------------------------------------------------------------------------

@app.command()
def demo(
    output_dir: Path = typer.Option(_DEMO_OUTPUT_DIR, "--output-dir", "-o", help="Output directory"),
    max_results: int = typer.Option(15, "--max-results", "-n", help="Max results per query"),
    max_queries: int = typer.Option(3, "--max-queries", help="Number of search queries"),
    topic: str = typer.Option(_DEMO_TOPIC, "--topic", "-t", help="Research topic"),
    seeds: Path = typer.Option(_DEMO_SEEDS, "--seeds", "-s", help="Seeds file"),
    criteria: Path = typer.Option(_DEMO_CRITERIA, "--criteria", "-c", help="Screening criteria JSON file"),
    db_path: Path | None = typer.Option(None, "--db", help="SQLite database path (default: <output-dir>/reviewtrace.db)"),
    fresh: bool = typer.Option(True, "--fresh/--no-fresh", help="Delete DB and clear output dir before running (default: True)"),
) -> None:
    """Run the sparse autoencoders demo pipeline (fast, no citation expansion).

    Equivalent to:
      reviewtrace run --topic "..." --seeds examples/... --criteria examples/... --demo --fresh
    """
    # Validate that example files exist
    missing = [p for p in (seeds, criteria) if not p.exists()]
    if missing:
        for p in missing:
            typer.echo(f"Error: required file not found: {p}", err=True)
        typer.echo(
            "Tip: run this command from the repository root, or pass --seeds / --criteria explicitly.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo("\nRunning ReviewTrace demo:")
    typer.echo(f"  topic:    {topic}")
    typer.echo(f"  seeds:    {seeds}")
    typer.echo(f"  criteria: {criteria}")
    typer.echo(f"  output:   {output_dir}/")
    typer.echo(f"  fresh:    {fresh}\n")

    _execute_pipeline(
        topic=topic,
        seeds=seeds,
        criteria=criteria,
        db_path=db_path,
        output_dir=output_dir,
        max_results=max_results,
        depth=0,
        max_per_hop=30,
        llm_delay=0.5,
        skip_expand=True,
        demo=True,
        max_queries=max_queries,
        fresh=fresh,
    )


# ---------------------------------------------------------------------------
# Individual phase commands
# ---------------------------------------------------------------------------

@app.command()
def retrieve(
    topic: str = typer.Option(..., "--topic", "-t", help="Search topic"),
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Max results per query"),
) -> None:
    """Keyword search across OpenAlex, Semantic Scholar, and arXiv."""
    import asyncio

    from reviewtrace.db.connection import init_db
    from reviewtrace.retrieval.orchestrator import run_queries
    from reviewtrace.retrieval.planner import plan_queries

    init_db(db_path)
    queries = plan_queries(topic, max_results_per_query=max_results)
    typer.echo(f"[retrieve] {len(queries)} queries across {len(set(q.source for q in queries))} sources")
    papers = asyncio.run(run_queries(queries))
    typer.echo(f"[retrieve] {len(papers)} unique papers written to {db_path}")


@app.command()
def expand(
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    depth: int = typer.Option(2, "--depth", help="Max BFS expansion depth"),
    max_per_hop: int = typer.Option(30, "--max-per-hop", help="Max papers per hop"),
    seed_ids: str = typer.Option(None, "--seeds", "-s", help="Comma-separated internal paper IDs (default: all)"),
) -> None:
    """Expand paper pool via citation graph BFS."""
    import asyncio

    from reviewtrace.db.connection import fetchall, init_db
    from reviewtrace.expansion.controller import expand as run_expand

    init_db(db_path)
    ids = [s.strip() for s in seed_ids.split(",") if s.strip()] if seed_ids else \
          [r["id"] for r in fetchall("SELECT id FROM papers")]
    if not ids:
        typer.echo("[expand] No papers in DB. Run `retrieve` first.")
        raise typer.Exit(1)

    typer.echo(f"[expand] {len(ids)} seed(s), depth={depth}, max_per_hop={max_per_hop}")
    result = asyncio.run(run_expand(ids, max_depth=depth, max_papers_per_hop=max_per_hop))
    typer.echo(f"[expand] +{result.new_papers_count} papers in {result.total_hops} hops")


@app.command()
def screen(
    topic: str = typer.Option(..., "--topic", "-t", help="Review topic"),
    criteria: Path = typer.Option(None, "--criteria", "-c", help="Criteria JSON file"),
    inclusion: str = typer.Option("", "--include", help="Comma-separated inclusion criteria"),
    exclusion: str = typer.Option("", "--exclude", help="Comma-separated exclusion criteria"),
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    policy_file: Path = typer.Option(None, "--policy", help="Source policy JSON file"),
    delay: float = typer.Option(0.5, "--delay", help="Seconds between LLM calls"),
) -> None:
    """Screen papers with LLM include/exclude decisions."""
    from reviewtrace.db.connection import init_db
    from reviewtrace.screening.policy import load_policy
    from reviewtrace.screening.screener import run_screening

    init_db(db_path)
    sc = _load_criteria(criteria, topic)
    if inclusion:
        sc.inclusion += [c.strip() for c in inclusion.split(",") if c.strip()]
    if exclusion:
        sc.exclusion += [c.strip() for c in exclusion.split(",") if c.strip()]

    decisions = run_screening(sc, policy=load_policy(policy_file), delay_seconds=delay)
    inc = sum(1 for d in decisions if d.decision == "include")
    typer.echo(f"[screen] include={inc}  exclude={len(decisions)-inc}  uncertain={len(decisions)-inc-sum(1 for d in decisions if d.decision=='exclude')}")


@app.command()
def dedup(
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
) -> None:
    """Deduplicate paper pool (title fuzzy match, threshold=0.9)."""
    from reviewtrace.audit.dedup import run_dedup
    from reviewtrace.db.connection import init_db

    init_db(db_path)
    r = run_dedup()
    typer.echo(f"[dedup] {r.total_before} → {r.total_after}  fuzzy_merges={r.fuzzy_merges}")


@app.command()
def extract(
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
    delay: float = typer.Option(0.5, "--delay", help="Seconds between LLM calls"),
) -> None:
    """Extract structured evidence from included papers."""
    from reviewtrace.db.connection import init_db
    from reviewtrace.evidence.extractor import run_extraction
    from reviewtrace.evidence.matrix import export_items_json, export_matrix_csv

    init_db(db_path)
    items = run_extraction(delay_seconds=delay)
    typer.echo(f"[extract] {len(items)} items extracted")
    out = Path(output_dir)
    export_matrix_csv(out / "evidence_matrix.csv")
    export_items_json(out / "evidence_items.json")


@app.command()
def taxonomize(
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
) -> None:
    """Build taxonomy: embed → cluster → label → link evidence → export."""
    from reviewtrace.db.connection import init_db
    from reviewtrace.taxonomy.controller import run_taxonomy
    from reviewtrace.taxonomy.exporter import export_taxonomy_md

    init_db(db_path)
    result = run_taxonomy()
    typer.echo(f"[taxonomize] {result.n_nodes} nodes · {result.n_evidence_links} evidence links")
    export_taxonomy_md(Path(output_dir) / "taxonomy.md")


@app.command()
def export(
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
) -> None:
    """Export all outputs: papers.csv, audit, citation graph, evidence, taxonomy."""
    from reviewtrace.audit.export import export_json, export_markdown
    from reviewtrace.db.connection import init_db
    from reviewtrace.evidence.matrix import export_items_json, export_matrix_csv
    from reviewtrace.export.csv_export import export_papers_csv
    from reviewtrace.export.graphml_export import export_graphml
    from reviewtrace.taxonomy.exporter import export_taxonomy_md

    init_db(db_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    export_papers_csv(out / "papers.csv")
    export_json(out / "retrieval_audit.json")
    export_markdown(out / "retrieval_audit.md")
    export_graphml(out / "citation_graph.graphml")
    export_matrix_csv(out / "evidence_matrix.csv")
    export_items_json(out / "evidence_items.json")
    export_taxonomy_md(out / "taxonomy.md")

    typer.echo(f"[export] All outputs written to {out}/")


# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
    skip_build: bool = typer.Option(False, "--skip-build", help="Skip npm build (reuse existing dist/)"),
) -> None:
    """Build the React frontend (if needed) and start the web server."""
    import os
    import subprocess

    import uvicorn

    web_dir = Path(__file__).parent.parent / "web"
    dist_dir = web_dir / "dist"

    if not skip_build:
        if not (web_dir / "node_modules").exists():
            typer.echo("Installing frontend dependencies (npm install)…")
            subprocess.run(["npm", "install"], cwd=web_dir, check=True)
        typer.echo("Building frontend…")
        subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)

    if not dist_dir.exists():
        typer.echo("Error: web/dist not found — run without --skip-build", err=True)
        raise typer.Exit(1)

    import threading
    import time
    import webbrowser

    os.environ.setdefault("REVIEWTRACE_DB_PATH", str(db_path))
    os.environ.setdefault("REVIEWTRACE_OUTPUT_DIR", str(output_dir))

    url = f"http://{host}:{port}"
    typer.echo(f"\nReviewTrace is running at {url}\n")

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("reviewtrace.api.app:app", host=host, port=port)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
    db_path: Path = typer.Option(Path("reviewtrace.db"), "--db", help="SQLite database path"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir", "-o", help="Output directory"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev)"),
) -> None:
    """Start the API server only (no frontend build). Use `web` for the full UI."""
    import os

    import uvicorn

    os.environ.setdefault("REVIEWTRACE_DB_PATH", str(db_path))
    os.environ.setdefault("REVIEWTRACE_OUTPUT_DIR", str(output_dir))
    typer.echo(f"Starting ReviewTrace API at http://{host}:{port}")
    uvicorn.run("reviewtrace.api.app:app", host=host, port=port, reload=reload)


# ---------------------------------------------------------------------------
# Shared pipeline implementation
# ---------------------------------------------------------------------------

def _execute_pipeline(  # noqa: C901
    *,
    topic: str,
    seeds: Path | None,
    criteria: Path | None,
    db_path: Path | None,
    output_dir: Path,
    max_results: int,
    depth: int,
    max_per_hop: int,
    llm_delay: float,
    skip_expand: bool,
    demo: bool,
    max_queries: int | None,
    fresh: bool = False,
) -> None:
    """Shared pipeline body used by both `run` and `demo`."""
    import asyncio
    import shutil
    import uuid

    from reviewtrace.audit.dedup import run_dedup
    from reviewtrace.audit.export import export_json, export_markdown
    from reviewtrace.db.connection import fetchall, init_db
    from reviewtrace.evidence.extractor import run_extraction
    from reviewtrace.evidence.matrix import export_items_json, export_matrix_csv
    from reviewtrace.expansion.controller import expand as run_expand
    from reviewtrace.export.csv_export import export_papers_csv
    from reviewtrace.export.graphml_export import export_graphml
    from reviewtrace.manifest import write_manifest
    from reviewtrace.retrieval.orchestrator import run_queries
    from reviewtrace.retrieval.planner import plan_queries
    from reviewtrace.retrieval.seed_loader import load_seeds
    from reviewtrace.screening.policy import load_policy
    from reviewtrace.screening.screener import run_screening
    from reviewtrace.taxonomy.controller import run_taxonomy
    from reviewtrace.taxonomy.exporter import export_taxonomy_md

    run_id = uuid.uuid4().hex[:12]

    # Resolve db_path: default to <output_dir>/reviewtrace.db so each run is self-contained
    if db_path is None:
        db_path = Path(output_dir) / "reviewtrace.db"

    if fresh:
        if db_path.exists():
            db_path.unlink()
            typer.echo(f"[fresh] Removed existing database: {db_path}")
        out_to_clear = Path(output_dir)
        if out_to_clear.exists():
            shutil.rmtree(out_to_clear)
            typer.echo(f"[fresh] Cleared output directory: {out_to_clear}/")

    init_db(db_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    _manifest_kwargs = dict(
        topic=topic, demo=demo, fresh=fresh, db_path=db_path, run_id=run_id
    )

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  ReviewTrace  |  {topic}")
    typer.echo(f"{'='*60}\n")

    try:
        # 1. Keyword retrieval
        typer.echo("[1/7] Keyword retrieval…")
        queries = plan_queries(topic, max_results_per_query=max_results, demo=demo, max_queries=max_queries)
        papers = asyncio.run(run_queries(queries))
        typer.echo(f"      {len(papers)} papers retrieved")

        # 2. Seed papers
        seed_ids: list[str] = []
        if seeds:
            typer.echo("[2/7] Loading seed papers…")
            seed_ids = load_seeds(seeds, progress_cb=lambda msg: typer.echo(f"      {msg}"))
        else:
            typer.echo("[2/7] No seeds file — skipping seed load")

        # 3. Dedup
        typer.echo("[3/7] Deduplication…")
        r = run_dedup()
        typer.echo(f"      {r.total_before} → {r.total_after} papers ({r.fuzzy_merges} fuzzy merges)")

        # 4. Citation graph expansion
        if not skip_expand:
            typer.echo("[4/7] Citation graph expansion (BFS)…")
            expand_seeds = seed_ids or [row["id"] for row in fetchall("SELECT id FROM papers")]
            exp = asyncio.run(run_expand(expand_seeds, max_depth=depth, max_papers_per_hop=max_per_hop))
            typer.echo(f"      +{exp.new_papers_count} papers in {exp.total_hops} hops")
            r2 = run_dedup()
            typer.echo(f"      Dedup after expansion: {r2.total_after} canonical papers")
        else:
            typer.echo("[4/7] Citation graph expansion skipped (--skip-expand)")

        # 5. Screening
        typer.echo("[5/7] Screening…")
        sc = _load_criteria(criteria, topic)
        policy = load_policy()
        decisions = run_screening(sc, policy=policy, delay_seconds=llm_delay)
        inc = sum(1 for d in decisions if d.decision == "include")
        typer.echo(f"      include={inc}  exclude={len(decisions)-inc}")

        # 6. Evidence extraction
        typer.echo("[6/7] Evidence extraction…")
        items = run_extraction(delay_seconds=llm_delay)
        typer.echo(f"      {len(items)} evidence items extracted")

        # 7. Taxonomy
        typer.echo("[7/7] Building taxonomy…")
        tax = run_taxonomy()
        typer.echo(f"      {tax.n_nodes} nodes · {tax.n_evidence_links} evidence links")

        # Export everything
        typer.echo("\nExporting outputs…")
        export_papers_csv(out / "papers.csv")
        export_json(out / "retrieval_audit.json")
        export_markdown(out / "retrieval_audit.md")
        export_graphml(out / "citation_graph.graphml")
        export_matrix_csv(out / "evidence_matrix.csv")
        export_items_json(out / "evidence_items.json")
        export_taxonomy_md(out / "taxonomy.md")
        write_manifest(out, status="completed", **_manifest_kwargs)

        typer.echo(f"\nDone. Outputs written to {out}/")
        typer.echo("  papers.csv · retrieval_audit.json · retrieval_audit.md")
        typer.echo("  citation_graph.graphml · evidence_matrix.csv")
        typer.echo("  evidence_items.json · taxonomy.md · run_manifest.json")

    except Exception as exc:
        write_manifest(out, status="error", error=str(exc), **_manifest_kwargs)
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_criteria(criteria_path: Path | None, topic: str):
    from reviewtrace.screening.models import ScreeningCriteria

    if criteria_path and criteria_path.exists():
        data = json.loads(criteria_path.read_text())
        return ScreeningCriteria(
            topic=data.get("topic", topic),
            inclusion=data.get("inclusion", []),
            exclusion=data.get("exclusion", []),
        )
    return ScreeningCriteria(topic=topic, inclusion=[], exclusion=[])


if __name__ == "__main__":
    app()
