"""Screening data models."""

from dataclasses import dataclass


@dataclass
class ScreeningDecision:
    paper_id: str
    decision: str           # include / exclude / uncertain
    reason: str
    confidence: float       # 0.0 – 1.0
    source_type_label: str  # assigned by classifier
    screened_by: str        # llm / human


@dataclass
class ScreeningCriteria:
    topic: str
    inclusion: list[str]
    exclusion: list[str]
