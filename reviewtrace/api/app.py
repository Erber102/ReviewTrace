"""ReviewTrace FastAPI application."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from reviewtrace.api.routes import audit, exports, papers, pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    from reviewtrace.db.connection import init_db

    db_path = os.getenv("REVIEWTRACE_DB_PATH", "reviewtrace.db")
    init_db(db_path)
    yield


app = FastAPI(title="ReviewTrace API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(exports.router, prefix="/api")

# Serve built React app in production
_WEB_DIST = Path(__file__).parent.parent.parent / "web" / "dist"
if _WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="static")
