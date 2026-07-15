"""OpenTelemetry/Phoenix regression tests without a live collector."""
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from story_pointer.engine import _record_token_usage
from story_pointer.schema import StoryInput
from story_pointer.telemetry import TelemetryState, current_trace_id, story_attributes


class RecordingSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


def test_story_attributes_are_metadata_only():
    story = StoryInput(
        title="Confidential customer story",
        description="Contains regulated details",
        acceptance_criteria=["secret one", "secret two"],
        context="private context",
        source="jira",
    )

    attributes = story_attributes(story)

    assert attributes["story_pointer.story.source"] == "jira"
    assert attributes["story_pointer.story.acceptance_criteria_count"] == 2
    assert attributes["story_pointer.story.has_context"] is True
    rendered = repr(attributes)
    assert story.title not in rendered
    assert story.description not in rendered
    assert story.context not in rendered
    assert not any("api_key" in key or "authorization" in key for key in attributes)


def test_provider_usage_is_mapped_to_openinference_token_attributes():
    span = RecordingSpan()
    _record_token_usage(
        span,
        {"usage": {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125}},
    )

    assert span.attributes == {
        "llm.token_count.prompt": 100,
        "llm.token_count.completion": 25,
        "llm.token_count.total": 125,
    }


def test_anthropic_usage_total_is_derived():
    span = RecordingSpan()
    _record_token_usage(span, {"usage": {"input_tokens": 40, "output_tokens": 10}})
    assert span.attributes["llm.token_count.total"] == 50


def test_current_trace_id_is_w3c_width():
    context = SpanContext(
        trace_id=1,
        span_id=2,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    with trace.use_span(NonRecordingSpan(context)):
        assert current_trace_id() == "00000000000000000000000000000001"


def test_public_status_never_contains_an_api_key():
    state = TelemetryState(
        enabled=True,
        configured=True,
        project_name="story-pointer",
        collector_endpoint="http://localhost:6006/v1/traces",
        ui_url="http://localhost:6006",
        capture_content=False,
    )
    public = state.public_dict()
    assert public["project_name"] == "story-pointer"
    assert "api_key" not in public
    assert "headers" not in public
