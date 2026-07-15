"""Manual story entry source.

Validates raw form/upload input into :class:`StoryInput`. Also splits a blob
of acceptance-criteria text into a list.
"""
from __future__ import annotations

from typing import Any

from ..schema import StoryInput


def parse_manual(raw: dict[str, Any]) -> StoryInput:
    """Build a :class:`StoryInput` from a raw manual-entry dict."""
    return StoryInput(
        title=str(raw.get("title", "")).strip(),
        description=str(raw.get("description", "")),
        acceptance_criteria=raw.get("acceptance_criteria", []) or [],
        context=str(raw.get("context", "")),
        source="manual",
    )


__all__ = ["parse_manual"]
