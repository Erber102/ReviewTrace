"""File download endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

_EXPORT_FILES = {
    "papers": ("papers.csv", "text/csv"),
    "audit": ("retrieval_audit.json", "application/json"),
    "audit-md": ("retrieval_audit.md", "text/markdown"),
    "graphml": ("citation_graph.graphml", "application/xml"),
    "evidence-matrix": ("evidence_matrix.csv", "text/csv"),
    "evidence-items": ("evidence_items.json", "application/json"),
    "taxonomy": ("taxonomy.md", "text/markdown"),
}


def _output_dir() -> Path:
    return Path(os.getenv("REVIEWTRACE_OUTPUT_DIR", "outputs"))


@router.get("/export/{kind}")
async def download_export(kind: str) -> FileResponse:
    if kind not in _EXPORT_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown export type '{kind}'")
    filename, media_type = _EXPORT_FILES[kind]
    path = _output_dir() / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found — run the pipeline first",
        )
    return FileResponse(str(path), media_type=media_type, filename=filename)


@router.get("/export")
async def list_exports() -> list[dict]:
    """Return availability status of all export files."""
    output_dir = _output_dir()
    result = []
    for kind, (filename, media_type) in _EXPORT_FILES.items():
        path = output_dir / filename
        result.append(
            {
                "kind": kind,
                "filename": filename,
                "media_type": media_type,
                "available": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
            }
        )
    return result
