"""Multi-instance Jira source.

Supports Jira Cloud (REST API v3) and Jira Server / Data Center (REST API v2).

* Cloud v3 auth: ``Authorization: Basic <base64(email:api_token)>`` or a Bearer
  PAT. We accept either; the instance config carries ``auth_type``.
* Server/DC v2 auth: HTTP Basic with ``username``/``password`` (API token).

The fetched issue JSON is mapped to :class:`StoryInput`. Acceptance criteria are
pulled from the most plausible field — structured ADF child blocks whose text
starts with "Given"/"When"/"Then"/"Acceptance", or a custom field named
``acceptance``/``acceptance_criteria`` if present.
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx

from ..config import JiraInstance, get_settings
from ..schema import StoryInput

log = logging.getLogger(__name__)

# Regex to detect Gherkin-ish / acceptance lines inside description ADF.
_AC_LINE = re.compile(
    r"^\s*(?:given|when|then|and|but|\*|-|\d+[.)])\s+", re.IGNORECASE
)
_AC_CUSTOM_FIELDS = ("acceptance", "acceptance_criteria", "acceptancecriteria", "criteria")


class JiraError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Auth header construction
# ---------------------------------------------------------------------------
def auth_header(inst: JiraInstance) -> dict[str, str]:
    """Build the ``Authorization`` header for a Jira instance."""
    if inst.auth_type == "pat":
        # Cloud: bearer PAT (preferred) — fall back to Basic(email:token).
        token = inst.token or inst.password
        if inst.email:
            raw = f"{inst.email}:{token}".encode("utf-8")
            b64 = base64.b64encode(raw).decode("ascii")
            return {"Authorization": f"Basic {b64}"}
        return {"Authorization": f"Bearer {token}"}
    # Server/DC basic auth
    raw = f"{inst.username}:{inst.password}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {b64}"}


# ---------------------------------------------------------------------------
# Fetch + map
# ---------------------------------------------------------------------------
async def fetch_issue(inst: JiraInstance, issue_key: str) -> dict[str, Any]:
    """Fetch a single issue document from Jira."""
    url = f"{inst.rest_root}/issue/{issue_key}"
    headers = {
        **auth_header(inst),
        "Accept": "application/json",
    }
    params = {
        "fields": "summary,description,status,assignee,reporter,"
                  "priority,issuetype,labels,components,customfield_*"
    }
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 404:
        raise JiraError(f"Issue {issue_key} not found in '{inst.name}'.")
    if resp.status_code >= 400:
        raise JiraError(f"Jira {inst.name} returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _adf_to_text(node: Any) -> str:
    """Recursively flatten an Atlassian Document Format (ADF) node to text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(_adf_to_text(n) for n in node)
    if isinstance(node, dict):
        if node.get("type") == "doc" and "content" in node:
            return _adf_to_text(node["content"])
        if "text" in node:
            return str(node["text"])
        if "content" in node:
            return _adf_to_text(node["content"])
    return ""


def map_issue_to_story(issue: dict[str, Any]) -> StoryInput:
    """Convert a Jira issue document to :class:`StoryInput`."""
    key = issue.get("key", "")
    fields: dict[str, Any] = issue.get("fields", {}) or {}

    title = str(fields.get("summary", "")).strip()
    if key:
        title = f"[{key}] {title}".strip()

    description_text = _adf_to_text(fields.get("description"))

    # Acceptance criteria: custom field first, then Gherkin-ish lines in desc.
    ac_lines: list[str] = []
    for fname, fval in fields.items():
        if any(c in fname.lower() for c in _AC_CUSTOM_FIELDS):
            txt = _adf_to_text(fval)
            if txt.strip():
                ac_lines.extend(line.strip("- *").strip() for line in txt.splitlines() if line.strip())
            break
    if not ac_lines:
        for line in description_text.splitlines():
            if _AC_LINE.match(line):
                ac_lines.append(line.strip("- *").strip())

    labels = fields.get("labels") or []
    components = [c.get("name", "") for c in (fields.get("components") or [])]
    status = (fields.get("status") or {}).get("name", "")
    extra_bits = [b for b in (f"status={status}", f"labels={','.join(labels)}" if labels else "",
                              f"components={','.join(components)}" if components else "") if b]
    context = "; ".join(extra_bits)

    return StoryInput(
        title=title or key or "Untitled story",
        description=description_text,
        acceptance_criteria=ac_lines,
        context=context,
        source="jira",
    )


# ---------------------------------------------------------------------------
# High-level entrypoint
# ---------------------------------------------------------------------------
async def get_story(instance_name: str, issue_key: str) -> StoryInput:
    """Resolve an instance by name and fetch+map the issue."""
    settings = get_settings()
    inst = settings.jira_instance(instance_name)
    if inst is None:
        available = [i.name for i in settings.jira_config()]
        raise JiraError(
            f"Unknown Jira instance '{instance_name}'. Configured: {available}"
        )
    issue = await fetch_issue(inst, issue_key)
    return map_issue_to_story(issue)


__all__ = ["JiraError", "auth_header", "fetch_issue", "get_story", "map_issue_to_story"]
