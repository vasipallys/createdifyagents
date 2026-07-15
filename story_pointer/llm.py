"""Provider-agnostic LLM request builders and response parsers.

The four supported providers (groq, openai, glm, claude) split into two wire
shapes:

* **OpenAI-compatible** (groq, openai, glm): ``POST {base_url}/chat/completions``
  with ``Authorization: Bearer <key>`` and a ``messages`` array. Response content
  lives at ``choices[0].message.content``.
* **Anthropic** (claude): ``POST {base_url}/v1/messages`` with
  ``x-api-key`` + ``anthropic-version`` headers and a ``messages`` array whose
  first element's role must be ``user``. Response content lives at
  ``content[0].text``.

This module produces (url, headers, body) tuples the graphon ``http-request``
node can POST directly, and parses raw provider JSON back into our canonical
:class:`~story_pointer.schema.StoryPointResult` draft (before the invariant gate).

NOTE: the heavy "call the model" step is done by graphon (either an
``http-request`` node or a Slim-backed ``llm`` node). This module is the
*adapter* that knows each provider's wire format so the DSL stays generic.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .anchors import build_user_prompt, system_prompt
from .config import ModelSpec
from .schema import (
    AnchorCmp,
    DecidingDriver,
    FactorScore,
    PerLayerEffort,
    PersonDays,
    Risk,
    SplitSubStory,
    StoryInput,
    StoryPointResult,
)

_VALID_POINTS = {1, 2, 3, 5, 8, 13}
_VALID_LEVELS = {"Low", "Medium", "High"}


# ===========================================================================
# Request builders  -> (url, headers, json_body)
# ===========================================================================
def build_request(spec: ModelSpec, story: StoryInput) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Return ``(url, headers, body)`` for the active provider.

    The body's ``messages`` always contains the system prompt + the assembled
    user prompt (rubric + 6 anchors + story). The graphon ``http-request`` node
    will POST this verbatim.
    """
    sys_p = system_prompt()
    user_p = build_user_prompt(
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        context=story.context,
    )
    if spec.provider in ("groq", "openai", "glm"):
        return _openai_request(spec, sys_p, user_p)
    if spec.provider == "claude":
        return _anthropic_request(spec, sys_p, user_p)
    raise ValueError(f"Unsupported provider: {spec.provider}")


def _openai_request(
    spec: ModelSpec, sys_p: str, user_p: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    url = f"{spec.base_url.rstrip('/')}/chat/completions"
    headers: dict[str, str] = {
        "Authorization": f"Bearer {spec.api_key}",
        "Content-Type": "application/json",
    }
    if spec.organization:
        headers["OpenAI-Organization"] = spec.organization
    body: dict[str, Any] = {
        "model": spec.model,
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p},
        ],
        "temperature": spec.temperature,
        "max_tokens": spec.max_tokens,
        "response_format": {"type": "json_object"},
    }
    return url, headers, body


def _anthropic_request(
    spec: ModelSpec, sys_p: str, user_p: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    url = f"{spec.base_url.rstrip('/')}/v1/messages"
    headers: dict[str, str] = {
        "x-api-key": spec.api_key,
        "anthropic-version": spec.api_version or "2023-06-01",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": spec.model,
        "system": sys_p,
        "messages": [{"role": "user", "content": user_p}],
        "temperature": spec.temperature,
        "max_tokens": spec.max_tokens,
    }
    return url, headers, body


# ===========================================================================
# Response parsers  -> raw dict (canonical-ish), then -> StoryPointResult
# ===========================================================================
def extract_content(provider: str, status: int, payload: Any) -> str:
    """Pull the model's text content out of a provider HTTP response."""
    if status >= 400:
        raise ProviderError(
            f"{provider} returned HTTP {status}: "
            f"{json.dumps(payload)[:400] if payload else '<no body>'}"
        )
    if provider in ("groq", "openai", "glm"):
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{provider}: unexpected response shape: {exc}") from exc
    if provider == "claude":
        try:
            block = payload["content"][0]
            return str(block.get("text", ""))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"claude: unexpected response shape: {exc}") from exc
    raise ValueError(f"Unsupported provider: {provider}")


def parse_json_payload(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM text response.

    Tolerates surrounding prose and ```json fences.
    """
    text = raw_text.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # try direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fall back to first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ProviderError(f"Could not find JSON object in model response: {raw_text[:200]}...")


def to_result(provider: str, model: str, raw_text: str, title: str = "") -> StoryPointResult:
    """Convert raw model text into a (pre-gate) :class:`StoryPointResult`."""
    data = parse_json_payload(raw_text)
    return dict_to_result(data, provider=provider, model=model, title=title)


def dict_to_result(
    data: dict[str, Any], *, provider: str = "", model: str = "", title: str = ""
) -> StoryPointResult:
    """Map the parsed JSON dict onto :class:`StoryPointResult`, coercing gently.

    The invariant GATE runs later (engine); here we only normalise shapes and
    clamp obviously-wrong values so a single bad field doesn't crash the
    pipeline.
    """
    factors = [
        FactorScore(
            id=str(f.get("id", "unknown")),
            level=_level(f.get("level")),
            evidence=str(f.get("evidence", "")),
        )
        for f in (data.get("factors") or [])
    ]
    drivers = [
        DecidingDriver(id=str(d.get("id", "unknown")), why=str(d.get("why", "")))
        for d in (data.get("deciding_drivers") or [])
    ]
    anchors = [
        AnchorCmp(points=_points(a.get("points")), why=str(a.get("why", "")))
        for a in (data.get("closest_anchors") or [])
    ]

    ple = data.get("per_layer_effort") or {}
    per_layer = PerLayerEffort(
        frontend=_level(ple.get("frontend")),
        backend=_level(ple.get("backend")),
        data=_level(ple.get("data")),
        test=_level(ple.get("test")),
        integration=_level(ple.get("integration")),
    )

    pd_raw = data.get("person_days") or {}
    person_days: PersonDays | None = None
    if isinstance(pd_raw, dict) and ("min" in pd_raw or "max" in pd_raw):
        pmin = int(pd_raw.get("min", 0) or 0)
        pmax = int(pd_raw.get("max", pmin) or pmin)
        if pmax < pmin:
            pmin, pmax = pmax, pmin
        person_days = PersonDays(min=max(pmin, 0), max=max(pmax, 0))

    risks = [
        Risk(
            description=str(r.get("description", "")),
            severity=_level(r.get("severity")),
            mitigation=str(r.get("mitigation", "")),
        )
        for r in (data.get("risks") or [])[:3]
    ]

    split = [
        SplitSubStory(
            title=str(s.get("title", "")),
            points=_points(s.get("points")),
            why=str(s.get("why", "")),
        )
        for s in (data.get("recommended_split") or [])
    ]

    must_split = bool(data.get("must_split"))
    points = _points(data.get("points"))
    # A 13 always means must_split, regardless of what the model said.
    if points == 13:
        must_split = True

    return StoryPointResult(
        ok=True,
        title=title,
        points=points,
        plain_language_why=str(data.get("plain_language_why", "")),
        tldr=str(data.get("tldr", "")),
        factors=factors,
        deciding_drivers=drivers,
        closest_anchors=anchors,
        per_layer_effort=per_layer,
        person_days=person_days,
        hidden_work=[str(h) for h in (data.get("hidden_work") or [])],
        risks=risks,
        assumptions=[str(a) for a in (data.get("assumptions") or [])],
        spike_needed=bool(data.get("spike_needed")),
        spike_reason=str(data.get("spike_reason", "")),
        must_split=must_split,
        recommended_split=split,
        provider=provider,
        model=model,
    )


# ===========================================================================
# helpers
# ===========================================================================
def _level(v: Any) -> str:
    s = str(v or "Medium").strip().capitalize()
    # tolerant: "high" -> "High", "M" -> "Medium"
    if s.lower().startswith("h"):
        return "High"
    if s.lower().startswith("l"):
        return "Low"
    return "Medium"


def _points(v: Any) -> int | None:
    """Coerce to a valid Fibonacci point value or None."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    # Snap common out-of-scale answers to the nearest valid value.
    fib = [1, 2, 3, 5, 8, 13]
    if n in fib:
        return n
    # 4 -> 3 or 5 (nearest), 6/7 -> 5, 9-12 -> 8 or 13
    nearest = min(fib, key=lambda f: (abs(f - n), f))
    return nearest if abs(nearest - n) <= 1 else None


class ProviderError(RuntimeError):
    """Raised when a provider returns a non-2xx or unparseable response."""


__all__ = [
    "ProviderError",
    "build_request",
    "dict_to_result",
    "extract_content",
    "parse_json_payload",
    "to_result",
]
