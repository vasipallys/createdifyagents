"""Spreadsheet source — CSV/XLS/XLSX ingestion with fuzzy column mapping.

Given a file (bytes + filename) we:

1. Read it with pandas (engine chosen by extension).
2. Fuzzy-map columns to our canonical fields (title, description,
   acceptance_criteria, context) using token-overlap scoring against a set of
   aliases. This tolerates spreadsheets named "Story", "User Story", "AC",
   "Acceptance", "Notes", etc.
3. Yield one :class:`StoryInput` per row, skipping empty rows.

No embeddings / vector store — pure string heuristics, which is the right tool
for ≤ a few hundred rows of tabular backlog data.
"""
from __future__ import annotations

import io
import re
from typing import Iterable

import pandas as pd

from ..schema import StoryBatch, StoryInput

# Canonical field -> aliases (lowercased). The matcher scores a column header
# by how many alias tokens it shares with the candidate.
_FIELD_ALIASES: dict[str, list[str]] = {
    "title": [
        "title", "story", "user story", "user_story", "summary", "name",
        "subject", "ticket", "item", "epic story", "jira title",
    ],
    "description": [
        "description", "desc", "details", "narrative", "body", "as a",
        "as an", "story description",
    ],
    "acceptance_criteria": [
        "acceptance criteria", "acceptance", "acceptance_criteria", "ac",
        "acceptance criteria given", "dod", "definition of done", "criteria",
        "given when then",
    ],
    "context": [
        "context", "notes", "comments", "remarks", "tech notes", "tags",
        "labels", "links",
    ],
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _score(header: str, aliases: Iterable[str]) -> int:
    """Token-overlap score between a header and a field's aliases."""
    h = _tokens(header)
    if not h:
        return 0
    best = 0
    for alias in aliases:
        a = _tokens(alias)
        if not a:
            continue
        overlap = len(h & a)
        # exact alias match wins big
        if header.strip().lower() == alias:
            return 100
        # proportional overlap, but require at least one shared token
        score = int((overlap / max(len(h), 1)) * 50) + overlap
        best = max(best, score)
    return best


def map_columns(columns: list[str]) -> dict[str, str | None]:
    """Return ``{canonical_field: chosen_column_or_None}`` for a header list."""
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    # Resolve fields in priority order: title, then AC, description, context.
    for field in ("title", "acceptance_criteria", "description", "context"):
        aliases = _FIELD_ALIASES[field]
        best_col: str | None = None
        best_score = 0
        for col in columns:
            if col in used:
                continue
            s = _score(col, aliases)
            if s > best_score:
                best_score = s
                best_col = col
        # Require a minimum confidence to avoid grabbing unrelated columns.
        if best_col and best_score >= 2:
            mapping[field] = best_col
            used.add(best_col)
        else:
            mapping[field] = None
    return mapping


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def read_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    """Read spreadsheet bytes into a DataFrame based on the file extension."""
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content), dtype=str).fillna("")
    if name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content), engine="xlrd", dtype=str).fillna("")
    if name.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype=str).fillna("")
    # Fallback: try CSV.
    return pd.read_csv(io.BytesIO(content), dtype=str).fillna("")


def parse(content: bytes, filename: str) -> StoryBatch:
    """Parse a spreadsheet into a :class:`StoryBatch`."""
    df = read_dataframe(content, filename)
    columns = [str(c) for c in df.columns]
    mapping = map_columns(columns)
    if mapping.get("title") is None:
        raise ValueError(
            "Could not find a title/story column. Found columns: "
            + ", ".join(columns)
        )

    stories: list[StoryInput] = []
    for _, row in df.iterrows():
        title = str(row[mapping["title"]]).strip() if mapping["title"] else ""
        if not title or title.lower() in {"nan", "none"}:
            continue
        desc = str(row[mapping["description"]]).strip() if mapping["description"] else ""
        ac_raw = str(row[mapping["acceptance_criteria"]]).strip() if mapping["acceptance_criteria"] else ""
        ctx = str(row[mapping["context"]]).strip() if mapping["context"] else ""
        ac = _split_ac(ac_raw)
        stories.append(StoryInput(
            title=title, description=desc, acceptance_criteria=ac,
            context=ctx, source="spreadsheet",
        ))
    return StoryBatch(stories=stories)


def _split_ac(text: str) -> list[str]:
    """Split a blob into acceptance-criteria items."""
    if not text.strip():
        return []
    # Split on newlines first; fall back to numbered/bulleted markers.
    parts = re.split(r"[\r\n]+|(?:\d+[.)]\s+)|(?<=[;|])\s*", text)
    return [p.strip("- *;").strip() for p in parts if p.strip("- *;").strip()]


__all__ = ["map_columns", "parse", "read_dataframe"]
