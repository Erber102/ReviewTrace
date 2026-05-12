"""Evidence data models."""

from dataclasses import dataclass

EVIDENCE_TYPES = (
    "method_proposal",
    "empirical_finding",
    "theoretical_claim",
    "limitation",
    "comparison",
    "dataset_contribution",
)


@dataclass
class EvidenceItem:
    paper_id: str
    evidence_type: str  # one of EVIDENCE_TYPES
    content: str        # self-contained statement, 1-2 sentences
    location: str = "abstract"
