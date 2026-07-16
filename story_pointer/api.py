"""FastAPI application for Story Pointer.

Endpoints:
    GET  /                          -> single-page frontend
    GET  /health                    -> liveness
    GET  /config                    -> active provider/model + jira instances
    POST /estimate                  -> SSE stream of one estimation
    POST /estimate/batch            -> estimate many stories (NDJSON/SSE)
    GET  /jira/instances            -> list configured Jira instances
    POST /jira/fetch                -> {instance, issue} -> StoryInput
    POST /upload                    -> spreadsheet -> StoryBatch
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .config import get_settings
from .engine import StreamEvent, estimate, stream, stream_batch
from .schema import StoryInput, StoryPointResult
from .sources import jira as jira_source
from .sources import spreadsheet as sheet_source
from .telemetry import configure_telemetry, instrument_fastapi, telemetry_state

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Story Pointer",
    description="Evidence-led story-point estimator for React/Spring delivery teams.",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register one trace provider for inbound FastAPI requests, outbound HTTPX
# calls, and the custom workflow/LLM spans emitted by the engine.
configure_telemetry(settings)
instrument_fastapi(app)


# ---------------------------------------------------------------------------
# Simple request models
# ---------------------------------------------------------------------------
class EstimateRequest(BaseModel):
    story: StoryInput


class BatchEstimateRequest(BaseModel):
    stories: list[StoryInput] = Field(..., min_length=1)


class JiraFetchRequest(BaseModel):
    instance: str
    issue: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sse(event: StreamEvent) -> dict[str, str]:
    """Convert a StreamEvent into an sse-starlette payload dict."""
    return {"event": event.type, "data": json.dumps(event.data)}


# ---------------------------------------------------------------------------
# Routes — meta
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/telemetry")
async def telemetry_health() -> dict[str, Any]:
    """Report Phoenix exporter configuration without exposing credentials."""
    state = telemetry_state()
    return {
        "status": "configured" if state.configured else "disabled_or_unavailable",
        "phoenix": state.public_dict(),
    }


@app.get("/config")
async def get_config() -> dict[str, Any]:
    s = get_settings()
    spec = s.model_spec()
    return {
        "provider": spec.provider,
        "model": spec.model,
        "execution_mode": s.llm_execution_mode,
        "has_api_key": bool(spec.api_key),
        "jira_instances": [i.name for i in s.jira_config()],
        "observability": telemetry_state().public_dict(),
    }


# ---------------------------------------------------------------------------
# Routes — estimation
# ---------------------------------------------------------------------------
@app.post("/estimate")
async def estimate_endpoint(req: EstimateRequest) -> EventSourceResponse:
    """Stream a single estimation. Final result is emitted atomically."""
    async def gen():
        try:
            async for ev in stream(req.story):
                yield _sse(ev)
        except Exception as exc:  # noqa: BLE001
            log.exception("estimate stream failed")
            yield _sse(StreamEvent("error", {"message": str(exc)}))

    return EventSourceResponse(gen())


@app.post("/estimate/sync", response_model=StoryPointResult)
async def estimate_sync_endpoint(req: EstimateRequest) -> StoryPointResult:
    """Non-streaming variant: returns the final gated result directly."""
    try:
        return await estimate(req.story)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Routes — Jira
# ---------------------------------------------------------------------------
@app.get("/jira/instances")
async def jira_instances() -> dict[str, Any]:
    s = get_settings()
    return {"instances": [i.model_dump() for i in s.jira_config()]}


@app.post("/jira/fetch", response_model=StoryInput)
async def jira_fetch(req: JiraFetchRequest) -> StoryInput:
    try:
        return await jira_source.get_story(req.instance, req.issue)
    except jira_source.JiraError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("jira fetch failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Routes — spreadsheet upload
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    try:
        batch = sheet_source.parse(content, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("upload parse failed")
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")
    return {
        "count": len(batch.stories),
        "stories": [s.model_dump() for s in batch.stories],
    }


@app.post("/estimate/batch")
async def estimate_batch(req: BatchEstimateRequest) -> EventSourceResponse:
    """Estimate all supplied stories in one resilient SSE stream."""
    async def gen():
        try:
            async for ev in stream_batch(req.stories):
                yield _sse(ev)
        except Exception as exc:  # noqa: BLE001
            log.exception("batch estimate stream failed")
            yield _sse(StreamEvent("error", {"message": str(exc)}))

    return EventSourceResponse(gen())


# ---------------------------------------------------------------------------
# DSL editor API (graphon DSL CRUD + validation)
# ---------------------------------------------------------------------------
from .dsl_api import router as dsl_router  # noqa: E402

app.include_router(dsl_router)


# ---------------------------------------------------------------------------
# Static frontend + React DSL editor
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Production build of the React DSL editor (editor/dist). Served at /editor.
EDITOR_DIR = Path(__file__).resolve().parent.parent / "editor" / "dist"
if EDITOR_DIR.exists():
    app.mount("/editor", StaticFiles(directory=str(EDITOR_DIR), html=True), name="editor")


@app.get("/", response_model=None)
async def index() -> FileResponse | JSONResponse:
    idx = STATIC_DIR / "index.html"
    if not idx.exists():
        return JSONResponse(
            {"message": "Frontend not built. PUT static/index.html."},
            status_code=404,
        )
    return FileResponse(str(idx), media_type="text/html")


@app.get("/api/config")
async def api_config() -> dict[str, Any]:
    """Lightweight config for the editor (mirrors /config, CORS-friendly)."""
    s = get_settings()
    spec = s.model_spec()
    return {
        "provider": spec.provider,
        "model": spec.model,
        "execution_mode": s.llm_execution_mode,
        "has_api_key": bool(spec.api_key),
        "editor_available": EDITOR_DIR.exists(),
    }


__all__ = ["app"]
