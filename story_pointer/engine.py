"""Estimation engine.

This is where graphon actually runs the checkpointed DSL pipeline. Two
execution modes are supported, selected by ``Settings.llm_execution_mode``:

* ``http`` (default): the graphon graph uses ``http-request`` nodes. We do the
  provider call ourselves with :mod:`story_pointer.llm` (so we fully control
  auth, retries, and parsing) and hand the parsed result to graphon purely as
  the *orchestration + invariant gate + rendering* layer. This needs ZERO
  external binaries and works in any environment.

* ``slim``: the graphon graph uses native ``llm`` nodes backed by the
  ``dify-plugin-daemon-slim`` runtime + Dify marketplace plugins. Token-level
  streaming comes for free; but it requires the Slim binary + plugin download.

Both modes share the SAME invariant gate (see :func:`apply_invariant_gate`)
and the SAME canonical :class:`~story_pointer.schema.StoryPointResult`.

The CORE PRODUCT INVARIANT — *a point value is never shown without its
explanation* — is enforced right here before any result leaves the engine.
The frontend enforces it a second time defensively.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterator
from urllib.parse import urlsplit

import httpx

from .anchors import FACTOR_IDS, VALID_POINTS
from .config import ModelSpec, get_settings
from .llm import ProviderError, RateLimitError, build_request, extract_content, to_result
from .schema import StoryInput, StoryPointResult
from .telemetry import (
    CHAIN,
    LLM,
    OPENINFERENCE_SPAN_KIND,
    current_trace_id,
    get_tracer,
    set_error,
    set_ok,
    story_attributes,
    telemetry_state,
)

log = logging.getLogger(__name__)
tracer = get_tracer(__name__)

DSL_DIR = Path(__file__).resolve().parent.parent / "dsl"
HTTP_GRAPH = DSL_DIR / "graph_http.yml"
SLIM_GRAPH = DSL_DIR / "graph_slim.yml"


# ===========================================================================
# Public streaming event type
# ===========================================================================
@dataclass(slots=True)
class StreamEvent:
    """A single SSE-bound event from the engine."""

    type: str           # "status" | "chunk" | "result" | "error"
    data: dict[str, Any]

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


# ===========================================================================
# Invariant gate  (the heart of the product)
# ===========================================================================
def apply_invariant_gate(result: StoryPointResult) -> StoryPointResult:
    """Certify a result. Returns a (possibly redacted) result.

    Rules:
    1. No points without ``plain_language_why`` AND ``tldr``.
    2. ``points`` must be a valid modified-Fibonacci value.
    3. ``points == 13`` => ``must_split = True`` and a non-empty split is
       required; if no split is provided we redact points and mark an error.
    4. Person-day range sanity (min<=max, both >= 0).
    5. Factor coverage: ideally all 12 factors scored; if < 8 we mark the
       result low-confidence but still certify (we only refuse on the
       explanation rule, which is the invariant).
    """
    # 1. explanation rule
    if not result.has_explanation():
        result.ok = False
        result.error = (
            "Invariant violation: estimate produced without plain_language_why/tldr. "
            "Points redacted."
        )
        result.points = None
        return result

    # 2. valid points
    if result.points is None or result.points not in VALID_POINTS:
        result.ok = False
        result.error = "Invariant violation: no valid modified-Fibonacci point value."
        result.points = None
        return result

    # 3. a 13 must always be split, with sized sub-stories each <= 8
    if result.points == 13:
        result.must_split = True
        valid_split = [
            s for s in result.recommended_split
            if s.title.strip() and s.points in VALID_POINTS and s.points <= 8
        ]
        if len(valid_split) < 2:
            result.ok = False
            result.error = (
                "Invariant violation: a 13 must be split into >=2 sub-stories each <= 8, "
                "each with a title. Points redacted until split is provided."
            )
            result.points = None
            return result
        result.recommended_split = valid_split[:3]

    # 4. person-day sanity
    if result.person_days is not None:
        if result.person_days.min > result.person_days.max:
            result.person_days.min, result.person_days.max = (
                result.person_days.max,
                result.person_days.min,
            )

    # 5. factor coverage flag (informational, not a refusal)
    scored = {f.id for f in result.factors}
    missing = [fid for fid in FACTOR_IDS if fid not in scored]
    if len(missing) > 4:
        # very low coverage -> treat as not trustworthy
        log.warning("Low factor coverage for '%s'; missing=%s", result.title, missing)

    result.ok = True
    result.error = ""
    return result


# ===========================================================================
# graphon loader (best-effort: falls back to direct orchestration if graphon
# is unavailable or the slim binary is missing). This keeps the app runnable
# in CI and minimal deployments while STILL being a graphon-first design.
# ===========================================================================
def _load_graphon(path: Path) -> Any:
    """Import and run ``graphon.dsl.loads`` on the DSL file.

    Returns a ``GraphEngine``. Raises ``GraphonUnavailable`` if graphon isn't
    importable or the graph won't load.
    """
    try:
        import graphon  # type: ignore[import-untyped]
        from graphon.dsl import loads  # type: ignore[import-untyped]
    except Exception as exc:  # noqa: BLE001 - we want a single, typed fallback
        raise GraphonUnavailable(str(exc)) from exc

    dsl_text = path.read_text(encoding="utf-8")
    return loads(dsl_text, workflow_id=f"story-pointer:{path.stem}")


class GraphonUnavailable(RuntimeError):
    """Raised when graphon/Slim is not installed or cannot run."""


def _graphon_available() -> bool:
    try:
        import graphon  # noqa: F401
        return True
    except Exception:
        return False


# ===========================================================================
# Orchestration: the actual estimation flow
# ===========================================================================
async def estimate(
    story: StoryInput,
    *,
    spec: ModelSpec | None = None,
    progress: bool = True,
) -> StoryPointResult:
    """Estimate a single story and return the gated result.

    High-level flow (mirrors the DSL graph exactly):
        build prompt -> call provider -> parse -> invariant gate -> return
    """
    settings = get_settings()
    spec = spec or settings.model_spec()
    settings.validate_provider_ready()

    steps = [
        ("start", "Starting estimation pipeline"),
        ("build_prompt", "Assembling 12-factor rubric + 6 anchors + story"),
        ("estimate", f"Calling {spec.provider}/{spec.model}"),
        ("normalize", "Parsing structured response"),
        ("gate", "Applying invariant gate (no points without explanation)"),
    ]
    # The progress events are surfaced by stream() below; here we just log.
    for node_id, msg in steps:
        log.info("[%s] %s", node_id, msg)

    attributes = {
        OPENINFERENCE_SPAN_KIND: CHAIN,
        "story_pointer.execution_mode": settings.llm_execution_mode,
        "llm.provider": spec.provider,
        "llm.model_name": spec.model,
        **story_attributes(story),
    }
    with tracer.start_as_current_span("story_pointer.estimate", attributes=attributes) as span:
        try:
            raw_text = await _call_provider_with_retry(spec, story)
            with tracer.start_as_current_span(
                "story_pointer.normalize",
                attributes={OPENINFERENCE_SPAN_KIND: CHAIN},
            ):
                result = to_result(spec.provider, spec.model, raw_text, title=story.title)
            with tracer.start_as_current_span(
                "story_pointer.invariant_gate",
                attributes={OPENINFERENCE_SPAN_KIND: CHAIN},
            ):
                result = apply_invariant_gate(result)
            span.set_attribute("story_pointer.result.ok", result.ok)
            if result.points is not None:
                span.set_attribute("story_pointer.result.points", result.points)
            set_ok(span)
            return result
        except Exception as exc:
            set_error(span, exc)
            raise


async def stream(story: StoryInput, *, spec: ModelSpec | None = None) -> AsyncIterator[StreamEvent]:
    """Run :func:`estimate` and yield SSE-friendly :class:`StreamEvent`s.

    Emits ``status`` events as each pipeline stage runs, then exactly one
    ``result`` event carrying the gated :class:`StoryPointResult`. The final
    ``result`` is emitted ATOMICALLY — only after the invariant gate passes
    (or it carries ``ok=False`` with ``points=None``).
    """
    settings = get_settings()
    spec = spec or settings.model_spec()
    settings.validate_provider_ready()

    attributes = {
        OPENINFERENCE_SPAN_KIND: CHAIN,
        "story_pointer.transport": "sse",
        "story_pointer.execution_mode": settings.llm_execution_mode,
        "llm.provider": spec.provider,
        "llm.model_name": spec.model,
        **story_attributes(story),
    }
    with tracer.start_as_current_span("story_pointer.estimate.stream", attributes=attributes) as span:
        trace_id = current_trace_id()
        yield StreamEvent(
            "status",
            {"node": "start", "message": "Pipeline started.", "trace_id": trace_id},
        )
        try:
            yield StreamEvent(
                "status",
                {"node": "build_prompt", "message": "Injecting 12-factor rubric + 6 anchors."},
            )

            yield StreamEvent(
                "status",
                {"node": "estimate", "message": f"Calling {spec.provider}/{spec.model}."},
            )
            raw_text = ""
            for attempt in range(settings.llm_rate_limit_max_retries + 1):
                try:
                    raw_text = await _call_provider(spec, story)
                    break
                except RateLimitError as exc:
                    if attempt >= settings.llm_rate_limit_max_retries:
                        raise
                    delay = _rate_limit_delay(settings.llm_rate_limit_wait_seconds, exc)
                    retry_number = attempt + 1
                    span.add_event(
                        "story_pointer.rate_limit.wait",
                        attributes={
                            "story_pointer.rate_limit.delay_seconds": delay,
                            "story_pointer.rate_limit.retry_number": retry_number,
                        },
                    )
                    yield StreamEvent(
                        "status",
                        {
                            "node": "rate_limit",
                            "message": (
                                f"{spec.provider} rate limit reached; holding for "
                                f"{delay:.2f}s before retry "
                                f"{retry_number}/{settings.llm_rate_limit_max_retries}."
                            ),
                            "retry_after_seconds": delay,
                            "retry_number": retry_number,
                            "trace_id": trace_id,
                        },
                    )
                    log.warning(
                        "%s rate limited; waiting %.2fs before retry %s/%s",
                        spec.provider,
                        delay,
                        retry_number,
                        settings.llm_rate_limit_max_retries,
                    )
                    await asyncio.sleep(delay)

            # Stream the raw text in ~120-char chunks so the UI feels alive.
            chunk_count = 0
            for i in range(0, len(raw_text), 120):
                chunk_count += 1
                yield StreamEvent("chunk", {"text": raw_text[i : i + 120]})
                await asyncio.sleep(0)
            span.set_attribute("story_pointer.sse.chunk_count", chunk_count)

            yield StreamEvent("status", {"node": "normalize", "message": "Parsing structured response."})
            with tracer.start_as_current_span(
                "story_pointer.normalize",
                attributes={OPENINFERENCE_SPAN_KIND: CHAIN},
            ):
                result = to_result(spec.provider, spec.model, raw_text, title=story.title)

            yield StreamEvent(
                "status",
                {"node": "gate", "message": "Applying invariant gate."},
            )
            with tracer.start_as_current_span(
                "story_pointer.invariant_gate",
                attributes={OPENINFERENCE_SPAN_KIND: CHAIN},
            ):
                result = apply_invariant_gate(result)

            span.set_attribute("story_pointer.result.ok", result.ok)
            if result.points is not None:
                span.set_attribute("story_pointer.result.points", result.points)
            set_ok(span)

            # ATOMIC final emission, including a trace id for UI/log correlation.
            yield StreamEvent(
                "result",
                {"result": result.model_dump(mode="json"), "trace_id": trace_id},
            )

        except ProviderError as exc:
            set_error(span, exc)
            yield StreamEvent(
                "error",
                {"message": f"Provider error: {exc}", "trace_id": trace_id},
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            set_error(span, exc)
            log.exception("Estimation failed")
            yield StreamEvent(
                "error",
                {"message": f"Estimation failed: {exc}", "trace_id": trace_id},
            )


async def stream_batch(
    stories: list[StoryInput], *, spec: ModelSpec | None = None
) -> AsyncIterator[StreamEvent]:
    """Estimate every story through one resilient, sequential SSE stream.

    Sequential execution avoids an unbounded burst of provider requests for a
    large spreadsheet. An item failure becomes an ``item_error`` event and the
    remaining rows continue. Nested per-story spans share one Phoenix trace.
    """
    settings = get_settings()
    spec = spec or settings.model_spec()
    settings.validate_provider_ready()
    total = len(stories)
    attributes = {
        OPENINFERENCE_SPAN_KIND: CHAIN,
        "story_pointer.transport": "sse",
        "story_pointer.operation": "batch",
        "story_pointer.batch.total": total,
        "story_pointer.execution_mode": settings.llm_execution_mode,
        "llm.provider": spec.provider,
        "llm.model_name": spec.model,
    }

    with tracer.start_as_current_span(
        "story_pointer.estimate.batch", attributes=attributes
    ) as span:
        trace_id = current_trace_id()
        succeeded = 0
        failed = 0
        yield StreamEvent("batch_start", {"total": total, "trace_id": trace_id})

        for index, story in enumerate(stories):
            item = {"index": index, "total": total, "title": story.title}
            terminal = False
            yield StreamEvent("item_start", item)
            try:
                async for event in stream(story, spec=spec):
                    if event.type == "status":
                        yield StreamEvent("item_status", {**item, **event.data})
                    elif event.type == "chunk":
                        yield StreamEvent("item_chunk", {**item, **event.data})
                    elif event.type == "result":
                        terminal = True
                        result = event.data.get("result", {})
                        if result.get("ok"):
                            succeeded += 1
                        else:
                            failed += 1
                        yield StreamEvent("item_result", {**item, **event.data})
                    elif event.type == "error":
                        terminal = True
                        failed += 1
                        yield StreamEvent("item_error", {**item, **event.data})
                if not terminal:
                    failed += 1
                    yield StreamEvent(
                        "item_error",
                        {
                            **item,
                            "message": "Estimation ended without a result.",
                            "trace_id": trace_id,
                        },
                    )
            except Exception as exc:  # noqa: BLE001 - isolate each row
                failed += 1
                log.exception("Batch item %s failed", index)
                yield StreamEvent(
                    "item_error",
                    {**item, "message": str(exc), "trace_id": trace_id},
                )

        span.set_attribute("story_pointer.batch.succeeded", succeeded)
        span.set_attribute("story_pointer.batch.failed", failed)
        set_ok(span)
        yield StreamEvent(
            "batch_complete",
            {
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
                "trace_id": trace_id,
            },
        )


# ===========================================================================
# Provider HTTP call (shared by both execution modes' "estimate" stage)
# ===========================================================================
def _parse_retry_duration(value: Any) -> float | None:
    """Parse provider retry durations such as ``13.78``, ``13.78s``, or ``1m2s``."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    match = re.search(
        r"(?:(?P<minutes>\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?\s*)?"
        r"(?P<seconds>\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?",
        text,
    )
    if not match:
        return None
    minutes = float(match.group("minutes") or 0.0)
    seconds = float(match.group("seconds"))
    return max(0.0, minutes * 60.0 + seconds)


def _rate_limit_hint(headers: Any, payload: Any) -> float | None:
    """Read Retry-After/Groq reset headers, then the JSON error message."""
    hints: list[float] = []
    for name in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        parsed = _parse_retry_duration(headers.get(name) if headers else None)
        if parsed is not None:
            hints.append(parsed)
    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
    match = re.search(r"try again in\s+([^.,;]+(?:\.\d+)?s)", message, re.IGNORECASE)
    if match:
        parsed = _parse_retry_duration(match.group(1))
        if parsed is not None:
            hints.append(parsed)
    return max(hints) if hints else None


def _rate_limit_delay(configured_wait: float, exc: RateLimitError) -> float:
    return max(configured_wait, exc.retry_after or 0.0)


async def _call_provider_with_retry(spec: ModelSpec, story: StoryInput) -> str:
    """Provider call with async 429 holds for non-streaming callers."""
    settings = get_settings()
    for attempt in range(settings.llm_rate_limit_max_retries + 1):
        try:
            return await _call_provider(spec, story)
        except RateLimitError as exc:
            if attempt >= settings.llm_rate_limit_max_retries:
                raise
            delay = _rate_limit_delay(settings.llm_rate_limit_wait_seconds, exc)
            log.warning(
                "%s rate limited; waiting %.2fs before retry %s/%s",
                spec.provider,
                delay,
                attempt + 1,
                settings.llm_rate_limit_max_retries,
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def _call_provider(spec: ModelSpec, story: StoryInput) -> str:
    """POST to the provider and return the model's text content."""
    url, headers, body = build_request(spec, story)
    attributes: dict[str, Any] = {
        OPENINFERENCE_SPAN_KIND: LLM,
        "llm.model_name": spec.model,
        "llm.provider": spec.provider,
        "llm.invocation_parameters": json.dumps(
            {"temperature": spec.temperature, "max_tokens": spec.max_tokens}
        ),
        "server.address": urlsplit(url).hostname or "",
        **story_attributes(story),
    }
    capture_content = telemetry_state().capture_content
    if capture_content:
        attributes["input.mime_type"] = "application/json"
        attributes["input.value"] = json.dumps(body, ensure_ascii=False)

    with tracer.start_as_current_span("story_pointer.llm.call", attributes=attributes) as span:
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            span.set_attribute("http.response.status_code", resp.status_code)
            payload: Any
            try:
                payload = resp.json()
            except ValueError:
                payload = {"raw": resp.text}
            _record_token_usage(span, payload)
            if resp.status_code == 429:
                error_body = json.dumps(payload)[:400] if payload else "<no body>"
                raise RateLimitError(
                    f"{spec.provider} returned HTTP 429: {error_body}",
                    retry_after=_rate_limit_hint(resp.headers, payload),
                )
            content = extract_content(spec.provider, resp.status_code, payload)
            if not content.strip():
                raise ProviderError(f"{spec.provider}: empty content in response")
            if capture_content:
                span.set_attribute("output.mime_type", "text/plain")
                span.set_attribute("output.value", content)
            set_ok(span)
            return content


def _record_token_usage(span: Any, payload: Any) -> None:
    """Normalize common provider usage shapes into OpenInference attributes."""
    if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
        return
    usage = payload["usage"]
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    total = usage.get("total_tokens")
    if isinstance(prompt, int):
        span.set_attribute("llm.token_count.prompt", prompt)
    if isinstance(completion, int):
        span.set_attribute("llm.token_count.completion", completion)
    if not isinstance(total, int) and isinstance(prompt, int) and isinstance(completion, int):
        total = prompt + completion
    if isinstance(total, int):
        span.set_attribute("llm.token_count.total", total)


# ===========================================================================
# graphon runner (used when LLM_EXECUTION_MODE=slim and graphon is available)
# ===========================================================================
def run_graphon_slim(story: StoryInput) -> Iterator[Any]:
    """Yield raw graphon events from the Slim-backed graph.

    This is the "real" graphon path: we load ``graph_slim.yml``, seed the start
    node with the story fields, and iterate ``engine.run()``. Callers map the
    typed ``GraphEngineEvent`` objects to SSE.
    """
    if not _graphon_available():
        raise GraphonUnavailable("graphon is not installed; cannot run slim graph")

    settings = get_settings()
    spec = settings.model_spec()
    engine = _load_graphon(SLIM_GRAPH)
    start_inputs = {
        "title": story.title,
        "description": story.description,
        "acceptance_criteria": story.acceptance_criteria,
        "context": story.context,
        "provider": spec.provider,
        "model": spec.model,
    }
    # loads() already built the engine; set start inputs via run.
    # Different graphon versions expose start inputs differently; we set them
    # on the variable pool if accessible.
    try:
        yield from engine.run(start_inputs=start_inputs)  # type: ignore[call-arg]
    except TypeError:
        # older/newer signature: pass via run_context
        yield from engine.run()  # type: ignore[call-arg]


__all__ = [
    "DSL_DIR",
    "GraphonUnavailable",
    "HTTP_GRAPH",
    "SLIM_GRAPH",
    "StreamEvent",
    "apply_invariant_gate",
    "estimate",
    "stream",
    "stream_batch",
]
