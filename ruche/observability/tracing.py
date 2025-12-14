"""OpenTelemetry distributed tracing setup.

Provides trace context propagation, span creation, and OTLP export.
Supports W3C Trace Context for cross-service correlation.
"""

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Global tracer instance
_tracer: Tracer | None = None

# W3C Trace Context propagator
_propagator = TraceContextTextMapPropagator()


def setup_tracing(
    service_name: str = "focal",
    otlp_endpoint: str | None = None,
    console_export: bool = False,
    _sample_rate: float = 1.0,  # Reserved for future sampling configuration
) -> Tracer:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Name to identify this service in traces
        otlp_endpoint: OTLP gRPC endpoint (e.g., "localhost:4317")
                       Falls back to OTEL_EXPORTER_OTLP_ENDPOINT env var
        console_export: Also export spans to console (for debugging)
        sample_rate: Fraction of traces to sample (0.0 to 1.0)

    Returns:
        Configured Tracer instance
    """
    global _tracer

    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint configured
    endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Add console exporter if requested
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Set as global provider
    trace.set_tracer_provider(provider)

    # Get tracer
    _tracer = trace.get_tracer(service_name)

    return _tracer


def get_tracer() -> Tracer:
    """Get the configured tracer, or a no-op tracer if not initialized.

    Returns:
        Tracer instance
    """
    global _tracer
    if _tracer is None:
        # Return no-op tracer if not initialized
        return trace.get_tracer("focal")
    return _tracer


def extract_context(headers: dict[str, str]) -> Context:
    """Extract trace context from HTTP headers.

    Supports W3C Trace Context (traceparent/tracestate headers).

    Args:
        headers: HTTP headers dict

    Returns:
        OpenTelemetry Context with extracted trace info
    """
    return _propagator.extract(carrier=headers)


def inject_context(headers: dict[str, str], context: Context | None = None) -> None:
    """Inject trace context into HTTP headers.

    Adds W3C Trace Context headers (traceparent/tracestate).

    Args:
        headers: HTTP headers dict to inject into
        context: Context to inject (current if not specified)
    """
    _propagator.inject(carrier=headers, context=context)


def get_current_trace_id() -> str | None:
    """Get the current trace ID as a hex string.

    Returns:
        Trace ID or None if not in a trace
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_current_span_id() -> str | None:
    """Get the current span ID as a hex string.

    Returns:
        Span ID or None if not in a span
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, "016x")
    return None


@contextmanager
def create_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    context: Context | None = None,
) -> Generator[Span, None, None]:
    """Create a new span as a context manager.

    Args:
        name: Span name
        kind: Span kind (INTERNAL, SERVER, CLIENT, etc.)
        attributes: Initial span attributes
        context: Parent context (current if not specified)

    Yields:
        The created span
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {},
        context=context,
    ) as span:
        yield span


def record_exception(span: Span, exception: Exception, escaped: bool = True) -> None:
    """Record an exception on a span.

    Args:
        span: Span to record on
        exception: The exception that occurred
        escaped: Whether the exception escaped the span scope
    """
    span.record_exception(exception, escaped=escaped)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_span_attributes(span: Span, **attributes: Any) -> None:
    """Set multiple attributes on a span.

    Args:
        span: Span to set attributes on
        **attributes: Key-value pairs to set
    """
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


class TracingContext:
    """Context manager for traced operations with common patterns.

    Provides convenient tracing for turn processing and pipeline steps.
    """

    def __init__(
        self,
        tenant_id: str,
        agent_id: str,
        session_id: str,
    ):
        """Initialize tracing context.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            session_id: Session identifier
        """
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.session_id = session_id

    @contextmanager
    def turn_span(
        self,
        turn_id: str,
        user_message_preview: str | None = None,
    ) -> Generator[Span, None, None]:
        """Create a span for a turn.

        Args:
            turn_id: Turn identifier
            user_message_preview: First N chars of user message

        Yields:
            Turn span
        """
        attributes = {
            "focal.tenant_id": self.tenant_id,
            "focal.agent_id": self.agent_id,
            "focal.session_id": self.session_id,
            "focal.turn_id": turn_id,
        }
        if user_message_preview:
            attributes["focal.message_preview"] = user_message_preview[:50]

        with create_span(
            "focal.turn",
            kind=SpanKind.SERVER,
            attributes=attributes,
        ) as span:
            yield span

    @contextmanager
    def pipeline_step_span(
        self,
        step_name: str,
        turn_id: str,
    ) -> Generator[Span, None, None]:
        """Create a span for a pipeline step.

        Args:
            step_name: Pipeline step name (e.g., "context_extraction")
            turn_id: Turn identifier

        Yields:
            Pipeline step span
        """
        attributes = {
            "focal.tenant_id": self.tenant_id,
            "focal.agent_id": self.agent_id,
            "focal.session_id": self.session_id,
            "focal.turn_id": turn_id,
            "focal.pipeline_step": step_name,
        }

        with create_span(
            f"focal.pipeline.{step_name}",
            kind=SpanKind.INTERNAL,
            attributes=attributes,
        ) as span:
            yield span

    @contextmanager
    def llm_call_span(
        self,
        provider: str,
        model: str,
        purpose: str,
    ) -> Generator[Span, None, None]:
        """Create a span for an LLM API call.

        Args:
            provider: LLM provider name
            model: Model identifier
            purpose: Call purpose (e.g., "context_extraction", "generation")

        Yields:
            LLM call span
        """
        attributes = {
            "focal.tenant_id": self.tenant_id,
            "focal.llm.provider": provider,
            "focal.llm.model": model,
            "focal.llm.purpose": purpose,
        }

        with create_span(
            f"focal.llm.{purpose}",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ) as span:
            yield span
