"""OpenTelemetry setup for end-to-end monitoring in Arize Phoenix.

Phoenix is deliberately configured in the application (rather than through
``opentelemetry-instrument``) so the same trace provider is shared by FastAPI,
HTTPX, the estimation workflow, and the manual OpenInference LLM spans.

Prompt/story/model content is not recorded by default. Operators can opt in
with ``PHOENIX_CAPTURE_CONTENT=true`` in a trusted environment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.trace import TracerProvider

    from .config import Settings

log = logging.getLogger(__name__)

OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
CHAIN = "CHAIN"
LLM = "LLM"


@dataclass(frozen=True, slots=True)
class TelemetryState:
    enabled: bool
    configured: bool
    project_name: str
    collector_endpoint: str
    ui_url: str
    capture_content: bool
    error: str = ""

    def public_dict(self) -> dict[str, Any]:
        """Return status safe for the browser; credentials are never exposed."""
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "project_name": self.project_name,
            "collector_endpoint": self.collector_endpoint,
            "ui_url": self.ui_url,
            "capture_content": self.capture_content,
            "error": self.error,
        }


_provider: TracerProvider | None = None
_state = TelemetryState(False, False, "", "", "", False)
_httpx_instrumented = False
_fastapi_apps: set[int] = set()


def configure_telemetry(settings: Settings) -> TelemetryState:
    """Register Phoenix as the global OTLP trace destination once per process."""
    global _provider, _state, _httpx_instrumented

    if _state.configured or _provider is not None:
        return _state

    if not settings.phoenix_enabled:
        _state = TelemetryState(
            enabled=False,
            configured=False,
            project_name=settings.phoenix_project_name,
            collector_endpoint=settings.phoenix_collector_endpoint,
            ui_url=settings.phoenix_ui_url,
            capture_content=settings.phoenix_capture_content,
        )
        log.info("Phoenix tracing is disabled")
        return _state

    try:
        # Keep these imports lazy: test and CLI paths that explicitly disable
        # telemetry should not pay Phoenix's server import/startup cost.
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from phoenix.otel import register

        _provider = register(
            endpoint=settings.phoenix_collector_endpoint,
            project_name=settings.phoenix_project_name,
            api_key=settings.phoenix_api_key or None,
            protocol="http/protobuf",
            batch=settings.phoenix_batch,
            auto_instrument=False,
            verbose=False,
        )
        if not _httpx_instrumented:
            HTTPXClientInstrumentor().instrument(tracer_provider=_provider)
            _httpx_instrumented = True

        _state = TelemetryState(
            enabled=True,
            configured=True,
            project_name=settings.phoenix_project_name,
            collector_endpoint=settings.phoenix_collector_endpoint,
            ui_url=settings.phoenix_ui_url,
            capture_content=settings.phoenix_capture_content,
        )
        log.info(
            "Phoenix tracing configured: project=%s collector=%s",
            settings.phoenix_project_name,
            settings.phoenix_collector_endpoint,
        )
    except Exception as exc:  # noqa: BLE001 - observability must not break the app
        log.exception("Phoenix tracing setup failed; application will continue")
        _state = TelemetryState(
            enabled=True,
            configured=False,
            project_name=settings.phoenix_project_name,
            collector_endpoint=settings.phoenix_collector_endpoint,
            ui_url=settings.phoenix_ui_url,
            capture_content=settings.phoenix_capture_content,
            error=str(exc),
        )
    return _state


def instrument_fastapi(app: FastAPI) -> None:
    """Add server spans to one FastAPI application, if Phoenix is configured."""
    if _provider is None or id(app) in _fastapi_apps:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_provider,
        excluded_urls="/health",
        # SSE emits many ASGI send/receive operations. Keeping each as a span
        # overwhelms the useful request/workflow/LLM hierarchy in Phoenix.
        exclude_spans=["receive", "send"],
    )
    _fastapi_apps.add(id(app))


def telemetry_state() -> TelemetryState:
    return _state


def get_tracer(name: str):
    """Return an OTel tracer backed by Phoenix when enabled, otherwise a no-op."""
    return trace.get_tracer(name, "0.1.0")


def current_trace_id() -> str:
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else ""


def set_error(span: Span, exc: BaseException | str) -> None:
    """Mark a span as failed without putting secrets or payloads in attributes."""
    message = str(exc)
    span.set_status(Status(StatusCode.ERROR, message[:500]))
    if isinstance(exc, BaseException):
        span.record_exception(exc)


def set_ok(span: Span) -> None:
    span.set_status(Status(StatusCode.OK))


def story_attributes(story: Any) -> dict[str, Any]:
    """Non-content story metadata safe to export by default."""
    return {
        "story_pointer.story.source": str(story.source),
        "story_pointer.story.title_length": len(story.title),
        "story_pointer.story.description_length": len(story.description),
        "story_pointer.story.acceptance_criteria_count": len(story.acceptance_criteria),
        "story_pointer.story.has_context": bool(story.context),
    }


__all__ = [
    "CHAIN",
    "LLM",
    "OPENINFERENCE_SPAN_KIND",
    "TelemetryState",
    "configure_telemetry",
    "current_trace_id",
    "get_tracer",
    "instrument_fastapi",
    "set_error",
    "set_ok",
    "story_attributes",
    "telemetry_state",
]
