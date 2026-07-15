"""Regression coverage for the HTTP SSE contract and browser transport."""

from pathlib import Path

from fastapi.testclient import TestClient

import story_pointer.api as api_module
from story_pointer.engine import StreamEvent


def test_estimate_returns_named_sse_events(monkeypatch):
    async def fake_stream(story):
        yield StreamEvent("status", {"message": f"Estimating {story.title}"})
        yield StreamEvent(
            "result",
            {
                "result": {
                    "ok": True,
                    "points": 3,
                    "plain_language_why": "Small and well understood.",
                    "tldr": "A standard three-point story.",
                }
            },
        )

    monkeypatch.setattr(api_module, "stream", fake_stream)

    with TestClient(api_module.app) as client:
        response = client.post(
            "/estimate",
            json={"story": {"title": "Regression test", "source": "manual"}},
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert "event: status" in response.text
    assert "event: result" in response.text
    assert '"points": 3' in response.text


def test_frontend_uses_one_guarded_post_stream():
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    stream_code = html.split("// ---- Estimation via SSE ----", 1)[1].split(
        "// ============================================================================\n"
        "// ResultCard",
        1,
    )[0]

    # EventSource is GET-only and the removed placeholder request was both
    # invalid and unrelated to the actual POST stream.
    assert "new EventSource(" not in html
    assert 'fetch("/estimate"' in stream_code
    assert "new AbortController()" in stream_code
    assert "if (!resp.ok)" in stream_code
    assert "try {" in stream_code
    assert "catch (e)" in stream_code
    assert "finally {" in stream_code
    assert "stream closed before returning a result" in stream_code


def test_config_exposes_safe_observability_status():
    with TestClient(api_module.app) as client:
        response = client.get("/config")
        telemetry = client.get("/health/telemetry")

    assert response.status_code == 200
    observability = response.json()["observability"]
    assert observability["enabled"] is False
    assert "api_key" not in observability
    assert telemetry.status_code == 200
    assert telemetry.json()["phoenix"]["project_name"] == "story-pointer"
