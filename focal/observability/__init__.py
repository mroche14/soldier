"""Observability: structured logging, distributed tracing, metrics.

Provides standardized observability primitives using structlog for logging,
OpenTelemetry for tracing, and Prometheus for metrics.
"""

from focal.observability.logging import PIIRedactor, get_logger, setup_logging
from focal.observability.metrics import (
    ACTIVE_SESSIONS,
    ERRORS,
    LLM_TOKENS,
    MEMORY_ENTITIES,
    MEMORY_EPISODES,
    PIPELINE_STEP_LATENCY,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    RULES_MATCHED,
    setup_metrics,
)
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

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "PIIRedactor",
    # Metrics
    "setup_metrics",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "LLM_TOKENS",
    "RULES_MATCHED",
    "ACTIVE_SESSIONS",
    "ERRORS",
    "PIPELINE_STEP_LATENCY",
    "MEMORY_EPISODES",
    "MEMORY_ENTITIES",
    # Tracing
    "setup_tracing",
    "get_tracer",
    "create_span",
    "extract_context",
    "inject_context",
    "get_current_trace_id",
    "get_current_span_id",
    "record_exception",
    "set_span_attributes",
    "TracingContext",
]
