"""Engine + provider-plumbing tests (LLM fully mocked — no network)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from story_pointer.config import ModelSpec, reset_settings_cache
from story_pointer.engine import (
    StreamEvent,
    _call_provider,
    _rate_limit_hint,
    apply_invariant_gate,
    stream,
    stream_batch,
)
from story_pointer.llm import RateLimitError, build_request, extract_content, parse_json_payload
from story_pointer.schema import StoryInput


# A representative well-formed model response.
GOOD_RESPONSE_JSON = json.dumps({
    "factors": [
        {"id": "requirements_clarity", "level": "Low", "evidence": "clear ACs"},
        {"id": "technical_complexity", "level": "Medium", "evidence": "branching logic"},
        {"id": "backend_effort", "level": "Medium", "evidence": "new endpoint"},
        {"id": "frontend_effort", "level": "Low", "evidence": "existing view"},
        {"id": "data_model_change", "level": "Low", "evidence": "additive column"},
        {"id": "test_effort", "level": "Medium", "evidence": "new suite"},
        {"id": "integration_surface", "level": "Low", "evidence": "one module"},
        {"id": "regulatory_compliance", "level": "Low", "evidence": "none"},
        {"id": "security_review", "level": "Medium", "evidence": "sensitive field"},
        {"id": "observability_ops", "level": "Low", "evidence": "standard logs"},
        {"id": "cross_team_dependency", "level": "Low", "evidence": "none"},
        {"id": "reversibility", "level": "Low", "evidence": "toggle"},
    ],
    "deciding_drivers": [
        {"id": "technical_complexity", "why": "branching dominates"},
        {"id": "backend_effort", "why": "new endpoint is the bulk"},
    ],
    "closest_anchors": [{"points": 3, "why": "read endpoint + small UI"}],
    "points": 3,
    "plain_language_why": "A standard small feature: one read endpoint on an existing domain plus a small UI view.",
    "tldr": "Standard 3 — small feature, low risk.",
    "per_layer_effort": {
        "frontend": "Low", "backend": "Medium", "data": "Low",
        "test": "Medium", "integration": "Low",
    },
    "person_days": {"min": 2, "max": 3},
    "hidden_work": ["error mapping", "logging"],
    "risks": [
        {"description": "scope creep", "severity": "Medium", "mitigation": "flag in refinement"},
    ],
    "assumptions": ["authz already exists"],
    "spike_needed": False,
    "must_split": False,
})


@pytest.fixture(autouse=True)
def _reset_settings():
    reset_settings_cache()
    yield
    reset_settings_cache()


# ===========================================================================
# Request builders — all four providers
# ===========================================================================
def _spec(provider: str, **kw) -> ModelSpec:
    base = dict(provider=provider, model=f"{provider}-model", api_key="key", base_url="https://api.x")
    base.update(kw)
    return ModelSpec(**base)


def test_build_request_openai_shape():
    spec = _spec("openai")
    url, headers, body = build_request(spec, StoryInput(title="t", description="d"))
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer key"
    assert headers["Content-Type"] == "application/json"
    assert body["model"] == "openai-model"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert body["response_format"] == {"type": "json_object"}


def test_build_request_groq_is_openai_compatible():
    spec = _spec("groq")
    url, headers, body = build_request(spec, StoryInput(title="t"))
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer key"
    assert "response_format" in body


def test_build_request_glm_is_openai_compatible():
    spec = _spec("glm")
    url, headers, body = build_request(spec, StoryInput(title="t"))
    assert url.endswith("/chat/completions")
    assert body["model"] == "glm-model"


def test_build_request_claude_uses_anthropic_shape():
    spec = _spec("claude", api_version="2023-06-01")
    url, headers, body = build_request(spec, StoryInput(title="t"))
    assert url.endswith("/v1/messages")
    assert headers["x-api-key"] == "key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert body["system"]  # system is a top-level string for Anthropic
    assert body["messages"][0]["role"] == "user"
    assert "response_format" not in body  # not used by Anthropic


# ===========================================================================
# Response parsing
# ===========================================================================
def test_extract_content_openai():
    payload = {"choices": [{"message": {"content": "hello"}}]}
    assert extract_content("openai", 200, payload) == "hello"


def test_extract_content_claude():
    payload = {"content": [{"type": "text", "text": "hi"}]}
    assert extract_content("claude", 200, payload) == "hi"


def test_extract_content_http_error():
    with pytest.raises(Exception):
        extract_content("openai", 500, {"error": "boom"})


def test_parse_json_payload_strips_fences():
    raw = "```json\n{\"points\": 5}\n```"
    assert parse_json_payload(raw)["points"] == 5


def test_parse_json_payload_extracts_from_prose():
    raw = 'Sure! Here you go:\n{"points": 3}\nHope that helps.'
    assert parse_json_payload(raw)["points"] == 3


# ===========================================================================
# End-to-end stream() with the provider HTTP call mocked
# ===========================================================================
@pytest.mark.asyncio
async def test_stream_happy_path(monkeypatch):
    # Force provider + key to be valid.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()

    async def fake_call(spec, story):
        return GOOD_RESPONSE_JSON

    monkeypatch.setattr("story_pointer.engine._call_provider", fake_call)

    story = StoryInput(title="Add login", description="users need to log in")
    events = []
    async for ev in stream(story):
        events.append(ev)

    types = [e.type for e in events]
    assert "result" in types
    assert "trace_id" in events[0].data
    final = next(e for e in events if e.type == "result")
    result = final.data["result"]
    assert "trace_id" in final.data
    assert result["ok"] is True
    assert result["points"] == 3
    assert result["plain_language_why"]
    assert result["tldr"]
    # status events fired for each stage
    assert "status" in types
    # chunks of raw text delivered
    assert "chunk" in types


@pytest.mark.asyncio
async def test_stream_emits_atomic_final_only(monkeypatch):
    """The result event carries the gated result exactly once."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()

    monkeypatch.setattr(
        "story_pointer.engine._call_provider",
        AsyncMock(return_value=GOOD_RESPONSE_JSON),
    )

    events = []
    async for ev in stream(StoryInput(title="t")):
        events.append(ev)

    assert sum(1 for e in events if e.type == "result") == 1


@pytest.mark.asyncio
async def test_stream_provider_error_emits_error_event(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()

    from story_pointer.llm import ProviderError

    async def boom(spec, story):
        raise ProviderError("HTTP 503")

    monkeypatch.setattr("story_pointer.engine._call_provider", boom)

    events = []
    async for ev in stream(StoryInput(title="t")):
        events.append(ev)

    assert any(e.type == "error" for e in events)
    assert not any(e.type == "result" for e in events)


def test_rate_limit_hint_parses_groq_retry_message_and_headers():
    payload = {
        "error": {
            "message": (
                "Rate limit reached on tokens per minute. "
                "Please try again in 13.78s."
            )
        }
    }
    assert _rate_limit_hint({}, payload) == 13.78
    assert _rate_limit_hint({"retry-after": "20"}, payload) == 20.0


@pytest.mark.asyncio
async def test_provider_http_429_becomes_retryable_error(monkeypatch):
    payload = {
        "error": {
            "message": "Rate limit reached. Please try again in 13.78s.",
            "code": "rate_limit_exceeded",
        }
    }

    class FakeResponse:
        status_code = 429
        headers = {"retry-after": "10"}
        text = json.dumps(payload)

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("story_pointer.engine.httpx.AsyncClient", FakeClient)
    with pytest.raises(RateLimitError) as caught:
        await _call_provider(_spec("groq"), StoryInput(title="Rate limited"))

    assert caught.value.retry_after == 13.78
    assert "groq returned HTTP 429" in str(caught.value)


@pytest.mark.asyncio
async def test_stream_holds_and_retries_after_rate_limit(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_RATE_LIMIT_WAIT_SECONDS", "0")
    monkeypatch.setenv("LLM_RATE_LIMIT_MAX_RETRIES", "2")
    reset_settings_cache()
    calls = 0

    async def limited_once(spec, story):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("HTTP 429", retry_after=0.01)
        return GOOD_RESPONSE_JSON

    monkeypatch.setattr("story_pointer.engine._call_provider", limited_once)
    monkeypatch.setattr("story_pointer.engine.asyncio.sleep", AsyncMock())
    events = [event async for event in stream(StoryInput(title="Retry me"))]

    wait = next(e for e in events if e.type == "status" and e.data["node"] == "rate_limit")
    assert wait.data["retry_after_seconds"] == 0.01
    assert wait.data["retry_number"] == 1
    assert calls == 2
    assert any(e.type == "result" for e in events)


@pytest.mark.asyncio
async def test_stream_invariant_violation_redacts_points(monkeypatch):
    """If the model omits the explanation, the gate redacts points and the
    result event still fires with ok=False, points=None."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()

    bad = json.dumps({"points": 5, "plain_language_why": "", "tldr": ""})

    async def fake_call(spec, story):
        return bad

    monkeypatch.setattr("story_pointer.engine._call_provider", fake_call)

    events = []
    async for ev in stream(StoryInput(title="t")):
        events.append(ev)

    final = next(e for e in events if e.type == "result")
    result = final.data["result"]
    assert result["ok"] is False
    assert result["points"] is None
    assert result["error"]


@pytest.mark.asyncio
async def test_stream_batch_estimates_every_story(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()
    monkeypatch.setattr(
        "story_pointer.engine._call_provider",
        AsyncMock(return_value=GOOD_RESPONSE_JSON),
    )

    stories = [StoryInput(title="First"), StoryInput(title="Second")]
    events = [event async for event in stream_batch(stories)]

    assert events[0].type == "batch_start"
    assert [e.data["index"] for e in events if e.type == "item_start"] == [0, 1]
    results = [e for e in events if e.type == "item_result"]
    assert [e.data["title"] for e in results] == ["First", "Second"]
    assert all(e.data["result"]["points"] == 3 for e in results)
    assert events[-1].type == "batch_complete"
    assert events[-1].data == {
        "total": 2,
        "succeeded": 2,
        "failed": 0,
        "trace_id": events[-1].data["trace_id"],
    }


@pytest.mark.asyncio
async def test_stream_batch_continues_after_item_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_settings_cache()
    from story_pointer.llm import ProviderError

    async def fake_call(spec, story):
        if story.title == "Broken":
            raise ProviderError("HTTP 503")
        return GOOD_RESPONSE_JSON

    monkeypatch.setattr("story_pointer.engine._call_provider", fake_call)
    events = [
        event
        async for event in stream_batch(
            [StoryInput(title="Broken"), StoryInput(title="Still runs")]
        )
    ]

    assert [e.data["index"] for e in events if e.type == "item_error"] == [0]
    assert [e.data["index"] for e in events if e.type == "item_result"] == [1]
    assert events[-1].data["succeeded"] == 1
    assert events[-1].data["failed"] == 1


def test_stream_event_to_sse_format():
    ev = StreamEvent("status", {"node": "x", "message": "y"})
    sse = ev.to_sse()
    assert sse.startswith("event: status\n")
    assert "data:" in sse
    assert sse.endswith("\n\n")
