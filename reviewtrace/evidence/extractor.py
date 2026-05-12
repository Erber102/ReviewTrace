"""Abstract-level evidence extractor.

Sends paper title + abstract to the LLM and returns a list of structured
EvidenceItems. Full-text extraction (T5.2) is deferred to a later phase.
"""

import time
import uuid

from reviewtrace.db import connection as db
from reviewtrace.evidence.models import EVIDENCE_TYPES, EvidenceItem
from reviewtrace.llm import complete
from reviewtrace.llm_json import parse_llm_json

_EXTRACT_PROMPT = """\
You are extracting structured evidence from a research paper abstract for a \
systematic literature review.

Paper:
  Title:    {title}
  Venue:    {venue}
  Year:     {year}
  Abstract: {abstract}

Extract ALL distinct evidence items present in this abstract.
Each item must have:
  - evidence_type: exactly one of {types}
  - content: a specific, self-contained statement (1-2 sentences, quoted or \
paraphrased from the abstract)

Evidence type definitions:
  method_proposal      — a new method, model, algorithm, or framework proposed
  empirical_finding    — an empirical result, benchmark score, or experimental finding
  theoretical_claim    — a theoretical insight, proof, or formal argument
  limitation           — a stated limitation, failure case, or scope boundary
  comparison           — a comparison with existing methods or baselines
  dataset_contribution — a new dataset, benchmark, or evaluation suite introduced

Return only a valid JSON array. Do not use Markdown. Do not wrap the JSON in code fences. Do not include text before or after the array.
Example: [{{"evidence_type": "method_proposal", "content": "We propose sparse autoencoders to decompose residual stream activations into interpretable features."}}]

If the abstract yields no extractable evidence, return [].
"""


def extract_paper(paper: dict) -> list[EvidenceItem]:
    """Extract evidence from a single paper dict (from DB)."""
    abstract = (paper.get("abstract") or "").strip()
    if not abstract:
        return []

    prompt = _EXTRACT_PROMPT.format(
        title=paper.get("title") or "",
        venue=paper.get("venue") or "unknown",
        year=paper.get("year") or "unknown",
        abstract=abstract[:2000],
        types=str(list(EVIDENCE_TYPES)),
    )

    try:
        raw = complete(prompt, max_tokens=1024)
        items_raw: list[dict] = parse_llm_json(raw)
    except Exception:
        print(f"[extractor] LLM output parse failed for {paper['id']}; skipped evidence extraction.")
        return []

    if not isinstance(items_raw, list):
        print(f"[extractor] LLM output parse failed for {paper['id']}; skipped evidence extraction.")
        return []

    items: list[EvidenceItem] = []
    for item in items_raw:
        etype = item.get("evidence_type", "").strip()
        content = item.get("content", "").strip()
        if etype not in EVIDENCE_TYPES or not content:
            continue
        items.append(EvidenceItem(
            paper_id=paper["id"],
            evidence_type=etype,
            content=content,
            location="abstract",
        ))
    return items


def run_extraction(
    papers: list[dict] | None = None,
    delay_seconds: float = 0.5,
) -> list[EvidenceItem]:
    """Extract evidence for all included and uncertain papers not yet processed.

    If papers is None, queries the DB automatically.
    """
    if papers is None:
        papers = _get_extractable_papers_without_evidence()

    if not papers:
        print("[extractor] No papers to process.")
        return []

    print(f"[extractor] Extracting evidence from {len(papers)} papers…")
    all_items: list[EvidenceItem] = []

    for i, paper in enumerate(papers, 1):
        items = extract_paper(paper)
        for item in items:
            _save_item(item)
        all_items.extend(items)

        if i % 10 == 0:
            print(f"[extractor] {i}/{len(papers)} done ({len(all_items)} items so far)")

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    print(f"[extractor] Done — {len(all_items)} evidence items extracted.")
    return all_items


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_extractable_papers_without_evidence() -> list[dict]:
    """Return included and uncertain papers that have no evidence items yet."""
    return db.fetchall(
        """
        SELECT p.*
        FROM papers p
        JOIN screening_decisions sd ON p.id = sd.paper_id
        WHERE sd.decision IN ('include', 'uncertain')
          AND p.abstract IS NOT NULL
          AND p.abstract != ''
          AND p.id NOT IN (SELECT DISTINCT paper_id FROM evidence_items)
        ORDER BY sd.decision ASC, p.year DESC
        """
    )


def _save_item(item: EvidenceItem) -> None:
    db.execute(
        """
        INSERT INTO evidence_items (id, paper_id, evidence_type, content, location)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), item.paper_id, item.evidence_type, item.content, item.location),
    )
