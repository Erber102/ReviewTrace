"""Taxonomy data models."""

from dataclasses import dataclass


@dataclass
class TaxonomyNode:
    id: str
    label: str
    description: str
    cluster_id: int
    parent_id: str | None = None
