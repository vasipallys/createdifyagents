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
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/dsl", tags=["dsl"])

DSL_DIR = Path(__file__).resolve().parent.parent / "dsl"
# Only allow filenames that are safe to read/write inside /dsl.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+\.ya?ml$")


def _resolve(name: str) -> Path:
    if not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid filename: {name!r}")
    return (DSL_DIR / name).resolve()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SaveRequest(BaseModel):
    name: str
    dsl: str


class ValidateRequest(BaseModel):
    dsl: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/list")
async def list_files() -> dict[str, Any]:
    files = sorted(p.name for p in DSL_DIR.glob("*.yml")) if DSL_DIR.exists() else []
    return {"files": files, "dir": str(DSL_DIR)}


@router.get("/file")
async def get_file(name: str) -> dict[str, Any]:
    p = _resolve(name)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return {"name": name, "dsl": p.read_text(encoding="utf-8")}


@router.post("/save")
async def save_file(req: SaveRequest) -> dict[str, Any]:
    p = _resolve(req.name)
    DSL_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(req.dsl, encoding="utf-8")
    log.info("DSL saved: %s", p)
    return {"name": req.name, "bytes": len(req.dsl), "path": str(p)}


@router.post("/validate")
async def validate(req: ValidateRequest) -> dict[str, Any]:
    """Dry-run the DSL through graphon's own planner."""
    try:
        from graphon.dsl import inspect  # type: ignore[import-untyped]
    except Exception as exc:  # noqa: BLE001
        # graphon not installed -> fall back to a YAML sanity check
        return _yaml_fallback(req.dsl, str(exc))

    try:
        plan = inspect(req.dsl)
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
