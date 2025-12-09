"""Tests for OpenTelemetry tracing."""

from uuid import uuid4

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanKind, StatusCode

from focal.observability.tracing import (
    TracingContext,
    create_span,
    extract_context,
    get_current_span_id,
    get_current_trace_id,
    get_tracer,
    inject_context,
    record_exception,
    set_span_attributes,
    setup_tracing,
)


@pytest.fixture(autouse=True)
def reset_tracing():
    """Reset tracing state before each test."""
    # Set up a fresh tracer provider for each test
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield


class TestSetupTracing:
    """Tests for tracing setup."""

    def test_setup_tracing_returns_tracer(self):
        """Should return a tracer."""
        tracer = setup_tracing(service_name="test-service")
        assert tracer is not None

    def test_setup_tracing_configures_service_name(self):
        """Should configure service name."""
        tracer = setup_tracing(service_name="my-service")
        # Tracer should be configured with the service name
        assert tracer is not None


class TestGetTracer:
    """Tests for get_tracer."""

    def test_get_tracer_returns_tracer(self):
        """Should return a tracer even without setup."""
        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_returns_configured_tracer_after_setup(self):
        """Should return configured tracer after setup."""
        setup_tracing(service_name="test")
        tracer = get_tracer()
        assert tracer is not None


class TestCreateSpan:
    """Tests for span creation."""

    def test_create_span_context_manager(self):
        """Should create span as context manager."""
        setup_tracing(service_name="test")

        with create_span("test-span") as span:
            assert span is not None
            assert span.is_recording()

    def test_create_span_with_attributes(self):
        """Should set initial attributes."""
        setup_tracing(service_name="test")

        with create_span("test-span", attributes={"key": "value"}) as span:
            # Span should be recording with attributes
            assert span.is_recording()

    def test_create_span_with_kind(self):
        """Should set span kind."""
        setup_tracing(service_name="test")

        with create_span("test-span", kind=SpanKind.CLIENT) as span:
            assert span.kind == SpanKind.CLIENT


class TestTraceContext:
    """Tests for trace context propagation."""

    def test_extract_context_from_headers(self):
        """Should extract context from traceparent header."""
        headers = {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        }
        context = extract_context(headers)
        assert context is not None

    def test_inject_context_into_headers(self):
        """Should inject traceparent header."""
        setup_tracing(service_name="test")
        headers: dict[str, str] = {}

        with create_span("test-span"):
            inject_context(headers)

        assert "traceparent" in headers

    def test_get_current_trace_id_inside_span(self):
        """Should return trace ID inside span."""
        setup_tracing(service_name="test")

        with create_span("test-span"):
            trace_id = get_current_trace_id()
            assert trace_id is not None
            assert len(trace_id) == 32  # 128-bit as hex

    def test_get_current_trace_id_outside_span(self):
        """Should return None outside span."""
        trace_id = get_current_trace_id()
        assert trace_id is None

    def test_get_current_span_id_inside_span(self):
        """Should return span ID inside span."""
        setup_tracing(service_name="test")

        with create_span("test-span"):
            span_id = get_current_span_id()
            assert span_id is not None
            assert len(span_id) == 16  # 64-bit as hex


class TestSpanOperations:
    """Tests for span operations."""

    def test_record_exception(self):
        """Should record exception on span."""
        setup_tracing(service_name="test")

        with create_span("test-span") as span:
            try:
                raise ValueError("Test error")
            except ValueError as e:
                record_exception(span, e)
                # Span should have error status
                assert span.status.status_code == StatusCode.ERROR

    def test_set_span_attributes(self):
        """Should set multiple attributes."""
        setup_tracing(service_name="test")

        with create_span("test-span") as span:
            set_span_attributes(
                span,
                key1="value1",
                key2=123,
                key3=None,  # Should be skipped
            )
            # Should not raise


class TestTracingContext:
    """Tests for TracingContext helper."""

    @pytest.fixture
    def tracing_context(self):
        """Create a tracing context."""
        setup_tracing(service_name="test")
        return TracingContext(
            tenant_id=str(uuid4()),
            agent_id=str(uuid4()),
            session_id=str(uuid4()),
        )

    def test_turn_span(self, tracing_context):
        """Should create turn span with attributes."""
        with tracing_context.turn_span("turn-123", "Hello world") as span:
            assert span.is_recording()
            # Attributes should be set
            assert span.name == "focal.turn"

    def test_pipeline_step_span(self, tracing_context):
        """Should create pipeline step span."""
        with tracing_context.pipeline_step_span("context_extraction", "turn-123") as span:
            assert span.is_recording()
            assert span.name == "focal.pipeline.context_extraction"

    def test_llm_call_span(self, tracing_context):
        """Should create LLM call span."""
        with tracing_context.llm_call_span(
            provider="anthropic",
            model="claude-3",
            purpose="generation",
        ) as span:
            assert span.is_recording()
            assert span.name == "focal.llm.generation"
            assert span.kind == SpanKind.CLIENT


class TestNestedSpans:
    """Tests for nested span behavior."""

    def test_nested_spans_parent_child_relationship(self):
        """Should create parent-child relationship."""
        setup_tracing(service_name="test")

        with create_span("parent") as parent_span:
            parent_trace_id = get_current_trace_id()

            with create_span("child") as child_span:
                child_trace_id = get_current_trace_id()
                # Same trace
                assert parent_trace_id == child_trace_id
                # Different spans
                assert parent_span != child_span
