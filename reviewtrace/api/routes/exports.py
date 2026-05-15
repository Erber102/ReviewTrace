"""File download endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
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


def _default_output_dir() -> Path:
    return Path(os.getenv("REVIEWTRACE_OUTPUT_DIR", "outputs"))


def _resolve_output_dir(requested: str | None) -> Path:
    """Return the resolved output directory, validating it stays inside the configured root."""
    root = _default_output_dir().resolve()
    if requested is None:
        return root
    candidate = Path(requested).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="output_dir must be inside the configured output root",
        )
    return candidate


@router.get("/export/manifest")
async def get_export_manifest(
    output_dir: str | None = Query(default=None, description="Output directory to read manifest from (must be inside the output root)"),
) -> dict:
    """Return the run_manifest.json for the given output directory."""
    import json

    path = _resolve_output_dir(output_dir) / "run_manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="run_manifest.json not found in the specified output directory")
    try:
        return json.loads(path.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse run_manifest.json")


@router.get("/export/{kind}")
async def download_export(
    kind: str,
    output_dir: str | None = Query(default=None, description="Override output directory (must be inside the output root)"),
) -> FileResponse:
    if kind not in _EXPORT_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown export type '{kind}'")
    filename, media_type = _EXPORT_FILES[kind]
    path = _resolve_output_dir(output_dir) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found — run the pipeline first",
        )
    return FileResponse(str(path), media_type=media_type, filename=filename)


@router.get("/export")
async def list_exports(
    output_dir: str | None = Query(default=None, description="Override output directory (must be inside the output root)"),
) -> list[dict]:
    """Return availability status of all export files."""
    resolved = _resolve_output_dir(output_dir)
    result = []
    for kind, (filename, media_type) in _EXPORT_FILES.items():
        path = resolved / filename
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
