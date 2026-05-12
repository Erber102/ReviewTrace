"""LLM-based screening engine.

For each paper, sends title + abstract + criteria to the LLM and records
include / exclude / uncertain with a reason and confidence score.

Human override: export decisions to CSV, edit, re-import.
"""

import csv
import time
import uuid
from pathlib import Path

from reviewtrace.audit.dedup import get_canonical_papers
from reviewtrace.db import connection as db
from reviewtrace.llm import complete
from reviewtrace.llm_json import parse_llm_json
from reviewtrace.screening.classifier import classify_source
from reviewtrace.screening.models import ScreeningCriteria, ScreeningDecision
from reviewtrace.screening.policy import SourcePolicy, load_policy

_SCREENING_PROMPT = """\
You are screening papers for a systematic literature review.

Topic: {topic}

Inclusion criteria:
{inclusion}

Exclusion criteria:
{exclusion}

Paper to screen:
  Title:    {title}
  Venue:    {venue}
  Year:     {year}
  Abstract: {abstract}

Carefully evaluate the paper against the criteria above.
Return only one valid JSON object with these fields:
  "decision":   "include" | "exclude" | "uncertain"
  "reason":     one or two sentences explaining your decision
  "confidence": a float between 0.0 (very unsure) and 1.0 (very sure)

Do not use Markdown. Do not wrap the JSON in code fences. Do not include text before or after the JSON.
Example: {{"decision": "include", "reason": "The paper proposes sparse autoencoders for circuit analysis.", "confidence": 0.92}}
"""


def run_screening(
    criteria: ScreeningCriteria,
    policy: SourcePolicy | None = None,
    delay_seconds: float = 0.5,
) -> list[ScreeningDecision]:
    """Screen all canonical papers not yet screened. Returns new decisions."""
    if policy is None:
        policy = load_policy()

    already_screened = {
        r["paper_id"]
        for r in db.fetchall("SELECT paper_id FROM screening_decisions")
    }
    papers = [p for p in get_canonical_papers() if p["id"] not in already_screened]

    if not papers:
        print("[screener] No unscreened papers found.")
        return []

    print(f"[screener] Screening {len(papers)} papers…")
    decisions: list[ScreeningDecision] = []

    for i, paper in enumerate(papers, 1):
        source_type = classify_source(paper)

        # Policy gate: skip LLM call for blocked sources
        if policy.is_blocked(source_type):
            decision = ScreeningDecision(
                paper_id=paper["id"],
                decision="exclude",
                reason=f"Source type '{source_type}' is blocked by policy.",
                confidence=1.0,
                source_type_label=source_type,
                screened_by="policy",
            )
        else:
            decision = _llm_screen(paper, criteria, source_type)

        _save_decision(decision)
        decisions.append(decision)

        if i % 10 == 0:
            print(f"[screener] {i}/{len(papers)} done")

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    print(f"[screener] Done — {len(decisions)} decisions recorded.")
    return decisions


def export_csv(output_path: Path) -> None:
    """Export all screening decisions to CSV for human review."""
    rows = db.fetchall(
        """
        SELECT
            sd.paper_id, p.title, p.doi, p.year, p.venue,
            sd.decision, sd.reason, sd.confidence,
            sd.source_type_label, sd.screened_by
        FROM screening_decisions sd
        JOIN papers p ON sd.paper_id = p.id
        ORDER BY sd.decision, p.title
        """
    )
    if not rows:
        print("[screener] No screening decisions to export.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[screener] Exported {len(rows)} decisions to {output_path}")


def import_csv_overrides(csv_path: Path) -> int:
    """Re-import human-corrected CSV. Only 'decision' column is used for updates."""
    updated = 0
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            paper_id = row.get("paper_id", "").strip()
            decision = row.get("decision", "").strip()
            if not paper_id or decision not in ("include", "exclude", "uncertain"):
                continue
            db.execute(
                """
                UPDATE screening_decisions
                SET decision = ?, screened_by = 'human'
                WHERE paper_id = ?
                """,
                (decision, paper_id),
            )
            updated += 1
    print(f"[screener] Applied {updated} human overrides.")
    return updated


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _llm_screen(
    paper: dict, criteria: ScreeningCriteria, source_type: str
) -> ScreeningDecision:
    inclusion_text = "\n".join(f"  - {c}" for c in criteria.inclusion)
    exclusion_text = "\n".join(f"  - {c}" for c in criteria.exclusion)

    prompt = _SCREENING_PROMPT.format(
        topic=criteria.topic,
        inclusion=inclusion_text or "  - (none specified)",
        exclusion=exclusion_text or "  - (none specified)",
        title=paper.get("title") or "",
        venue=paper.get("venue") or "unknown",
        year=paper.get("year") or "unknown",
        abstract=(paper.get("abstract") or "")[:1500],  # truncate long abstracts
    )

    try:
        raw = complete(prompt, max_tokens=256)
        parsed = parse_llm_json(raw)
        decision = parsed.get("decision", "uncertain")
        if decision not in ("include", "exclude", "uncertain"):
            decision = "uncertain"
        return ScreeningDecision(
            paper_id=paper["id"],
            decision=decision,
            reason=str(parsed.get("reason", "")),
            confidence=float(parsed.get("confidence", 0.5)),
            source_type_label=source_type,
            screened_by="llm",
        )
    except Exception:
        print(f"[screener] LLM output parse failed for {paper['id']}; marked as uncertain.")
        return ScreeningDecision(
            paper_id=paper["id"],
            decision="uncertain",
            reason="LLM output could not be parsed.",
            confidence=0.0,
            source_type_label=source_type,
            screened_by="llm",
        )


def _save_decision(d: ScreeningDecision) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO screening_decisions
            (id, paper_id, decision, reason, confidence, source_type_label, screened_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            d.paper_id,
            d.decision,
            d.reason,
            d.confidence,
            d.source_type_label,
            d.screened_by,
        ),
    )
    # Keep source_type on the paper record too
    db.execute(
        "UPDATE papers SET source_type = ? WHERE id = ?",
        (d.source_type_label, d.paper_id),
    )
