"""DSL editor API router.

Endpoints for the visual graphon DSL editor:

    GET  /dsl/list                 -> list .yml files in /dsl
    GET  /dsl/file?name=...        -> read a DSL file
    POST /dsl/save                 -> write a DSL file (body: {name, dsl})
    POST /dsl/validate             -> graphon.dsl.inspect() dry-run

Validation uses graphon's own `inspect()` planner so what the editor reports
matches what the engine will actually accept.
"""
from __future__ import annotations

import logging
import hashlib
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .config import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/dsl", tags=["dsl"])

DSL_DIR = Path(__file__).resolve().parent.parent / "dsl"
# Only allow filenames that are safe to read/write inside /dsl.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+\.ya?ml$")


def _resolve(name: str) -> Path:
    if not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid filename: {name!r}")
    path = (DSL_DIR / name).resolve()
    if path.parent != DSL_DIR.resolve():
        raise HTTPException(status_code=400, detail="DSL path escapes the configured directory")
    return path


def _revision(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _authorize_write(x_dsl_api_key: str | None) -> None:
    """Require the configured editor key without ever reflecting it."""
    expected = get_settings().dsl_write_api_key
    if expected and (not x_dsl_api_key or not secrets.compare_digest(expected, x_dsl_api_key)):
        raise HTTPException(status_code=401, detail="Invalid or missing DSL write API key")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SaveRequest(BaseModel):
    name: str
    dsl: str
    revision: str | None = None


class ValidateRequest(BaseModel):
    dsl: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/list")
async def list_files() -> dict[str, Any]:
    files = []
    if DSL_DIR.exists():
        files = sorted({p.name for pattern in ("*.yml", "*.yaml") for p in DSL_DIR.glob(pattern)})
    return {"files": files}


@router.get("/file")
async def get_file(name: str) -> dict[str, Any]:
    p = _resolve(name)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    content = p.read_bytes()
    if len(content) > get_settings().max_dsl_bytes:
        raise HTTPException(status_code=413, detail="DSL file exceeds the configured size limit")
    return {"name": name, "dsl": content.decode("utf-8"), "revision": _revision(content)}


@router.post("/save")
async def save_file(
    req: SaveRequest,
    x_dsl_api_key: str | None = Header(default=None, alias="X-DSL-API-Key"),
) -> dict[str, Any]:
    _authorize_write(x_dsl_api_key)
    p = _resolve(req.name)
    content = req.dsl.encode("utf-8")
    if len(content) > get_settings().max_dsl_bytes:
        raise HTTPException(status_code=413, detail="DSL content exceeds the configured size limit")

    inspection = _inspect_dsl(req.dsl)
    if not inspection.get("loadable"):
        raise HTTPException(status_code=422, detail=inspection.get("error") or "DSL is not loadable")

    DSL_DIR.mkdir(parents=True, exist_ok=True)
    if p.exists():
        current = _revision(p.read_bytes())
        if req.revision is None or not secrets.compare_digest(current, req.revision):
            raise HTTPException(status_code=409, detail="DSL file changed; reopen it before saving")

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=DSL_DIR, prefix=".dsl-", suffix=".tmp", delete=False
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, p)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)

    revision = _revision(content)
    log.info("DSL saved: %s (%s bytes)", req.name, len(content))
    return {"name": req.name, "bytes": len(content), "revision": revision}


@router.post("/validate")
async def validate(req: ValidateRequest) -> dict[str, Any]:
    """Dry-run the DSL through graphon's own planner."""
    if len(req.dsl.encode("utf-8")) > get_settings().max_dsl_bytes:
        raise HTTPException(status_code=413, detail="DSL content exceeds the configured size limit")
    return _inspect_dsl(req.dsl)


def _inspect_dsl(dsl: str) -> dict[str, Any]:
    """Return graphon validation results without writing to disk."""
    try:
        from graphon.dsl import inspect  # type: ignore[import-untyped]
    except Exception as exc:  # noqa: BLE001
        # graphon not installed -> fall back to a YAML sanity check
        return _yaml_fallback(dsl, str(exc))

    try:
        plan = inspect(dsl)
    except Exception as exc:  # noqa: BLE001 - surface graphon errors to the UI
        return {"loadable": False, "error": str(exc), "dependencies": []}

    return {
        "loadable": bool(getattr(plan, "loadable", False)),
        "dependencies": [str(d) for d in getattr(plan, "dependencies", []) or []],
        "error": "",
    }


def _yaml_fallback(dsl: str, reason: str) -> dict[str, Any]:
    """Used only when graphon itself can't be imported."""
    import yaml

    try:
        doc = yaml.safe_load(dsl) or {}
    except yaml.YAMLError as exc:
        return {"loadable": False, "error": f"YAML parse error: {exc}", "dependencies": []}
    ok = (
        isinstance(doc, dict)
        and doc.get("kind") == "graph"
        and isinstance(doc.get("graph"), dict)
        and isinstance(doc["graph"].get("nodes"), list)
    )
    return {
        "loadable": ok,
        "error": "" if ok else "Missing kind: graph / graph.nodes.",
        "dependencies": [],
        "note": f"graphon unavailable ({reason}); YAML-only check.",
    }


__all__ = ["router"]
