"""Pydantic models for story inputs and estimation results.

These models are the single source of truth for the wire contract between the
graphon DSL pipeline, the FastAPI layer, and the browser. The CORE PRODUCT
INVARIANT — *a point value is never shown without its explanation* — is
enforced in :mod:`story_pointer.engine` (backend gate) and in the frontend
``ResultCard``. This module makes the invariant *expressible* by marking
``points``/``plain_language_why``/``tldr`` as the load-bearing fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Level = Literal["Low", "Medium", "High"]
Points = Literal[1, 2, 3, 5, 8, 13]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class StoryInput(BaseModel):
    """A story to estimate. All three sources resolve to this shape."""

    title: str = Field(..., min_length=1, description="Story / ticket title.")
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: str = Field("", description="Optional extra context (tech notes, links).")
    source: str = Field("manual", description="manual | jira | spreadsheet")

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _coerce_ac(cls, v: object) -> list[str]:
        # Accept a single string -> split on newlines.
        if isinstance(v, str):
            return [line.strip("- ").strip() for line in v.splitlines() if line.strip()]
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        return []


class StoryBatch(BaseModel):
    """A batch of stories (used by spreadsheet ingestion)."""

    stories: list[StoryInput]


# ---------------------------------------------------------------------------
# Result sub-models
# ---------------------------------------------------------------------------
class FactorScore(BaseModel):
    id: str
    level: Level
    evidence: str = ""


class DecidingDriver(BaseModel):
    id: str
    why: str = ""


class AnchorCmp(BaseModel):
    points: int
    why: str = ""


class PerLayerEffort(BaseModel):
    frontend: Level = "Low"
    backend: Level = "Low"
    data: Level = "Low"
    test: Level = "Low"
    integration: Level = "Low"


class PersonDays(BaseModel):
    min: int = Field(..., ge=0)
    max: int = Field(..., ge=0)


class Risk(BaseModel):
    description: str
    severity: Level = "Medium"
    mitigation: str = ""


class SplitSubStory(BaseModel):
    title: str
    points: int
    why: str = ""


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------
class StoryPointResult(BaseModel):
    """The final estimation payload.

    ``ok`` is False when the invariant gate could not certify the result; in
    that case ``points`` is None and a human-readable ``error`` is set. The
    frontend MUST treat ``ok=False`` as "no estimate available".
    """

    ok: bool = True
    title: str = ""

    # --- The invariant triple. points is Optional so it can be REDACTED. ---
    points: int | None = None
    plain_language_why: str = ""
    tldr: str = ""

    # Evidence
    factors: list[FactorScore] = Field(default_factory=list)
    deciding_drivers: list[DecidingDriver] = Field(default_factory=list)
    closest_anchors: list[AnchorCmp] = Field(default_factory=list)

    # Sizing
    per_layer_effort: PerLayerEffort = Field(default_factory=PerLayerEffort)
    person_days: PersonDays | None = None

    # Discoveries
    hidden_work: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    spike_needed: bool = False
    spike_reason: str = ""

    # Split
    must_split: bool = False
    recommended_split: list[SplitSubStory] = Field(default_factory=list)

    # Meta
    error: str = ""
    model: str = ""
    provider: str = ""

    # ----- invariant helpers -----
    def has_explanation(self) -> bool:
        """True iff both explanation fields are non-empty."""
        return bool(self.plain_language_why.strip() and self.tldr.strip())

    def is_invariant_satisfied(self) -> bool:
        """A point value may be surfaced only when this is True."""
        return (
            self.ok
            and self.points is not None
            and self.points in (1, 2, 3, 5, 8, 13)
            and self.has_explanation()
        )

    def redact_points(self) -> "StoryPointResult":
        """Return a copy with points removed (used when invariant fails)."""
        return self.model_copy(update={"points": None})


__all__ = [
    "AnchorCmp",
    "DecidingDriver",
    "FactorScore",
    "Level",
    "PerLayerEffort",
    "PersonDays",
    "Points",
    "Risk",
    "SplitSubStory",
    "StoryBatch",
    "StoryInput",
    "StoryPointResult",
]
