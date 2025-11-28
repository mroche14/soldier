# Observability Interface Contracts

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This document defines the contracts for observability components: logging, metrics, and tracing.

---

## Logging

### Setup Interface

```python
def setup_logging(
    level: str = "INFO",
    format: Literal["json", "console"] = "json",
    include_trace_id: bool = True,
    redact_pii: bool = True,
    redact_patterns: list[str] | None = None,
) -> None:
    """Configure structured logging for Soldier.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format ("json" for production, "console" for dev)
        include_trace_id: Whether to include trace_id from OpenTelemetry
        redact_pii: Whether to redact PII patterns
        redact_patterns: Additional regex patterns to redact

    Effects:
        - Configures structlog globally
        - Sets up processors for timestamps, levels, context
        - Configures output renderer based on format
    """


def get_logger(name: str) -> BoundLogger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Bound structlog logger
    """
```

### Context Binding (via contextvars - per spec clarification)

```python
# From structlog.contextvars
def bind_contextvars(**kwargs) -> None:
    """Bind context that will be included in all logs in current async context."""


def clear_contextvars() -> None:
    """Clear all bound context variables."""


def unbind_contextvars(*keys: str) -> None:
    """Unbind specific context variables."""
```

### PII Redaction (Two-Tier - per spec clarification)

```python
# Tier 1: Key-name lookup (O(1) - fast path)
SENSITIVE_KEYS = frozenset({
    "password", "token", "secret", "api_key",
    "user_email", "email", "phone", "ssn", "credit_card"
})

# Tier 2: Regex patterns (slower fallback for string values)
PII_REGEX_PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "PHONE": re.compile(r'\b\+?1?\d{9,15}\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
}

REDACTED_MASK = "[REDACTED]"
```

**Algorithm**:
1. For each key in log event dict:
   - If `key.lower() in SENSITIVE_KEYS`: redact value immediately (fast path)
   - Else if value is string: apply regex patterns (slow path)
2. Skip non-string values for regex (ints, bools, UUIDs)

### Log Schema (JSON Format)

Every log entry must include:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "info",
  "event": "event_name",
  "logger": "soldier.module.name",

  "tenant_id": "uuid",
  "agent_id": "uuid",
  "session_id": "uuid",
  "turn_id": "uuid",
  "trace_id": "hex-string"
}
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_setup_json_format` | Setup with format="json" | Output is valid JSON |
| `test_setup_console_format` | Setup with format="console" | Output is human-readable |
| `test_log_levels` | Log at each level | Only >= configured level emitted |
| `test_context_binding` | Bind context, log | Context appears in output |
| `test_context_clear` | Bind, clear, log | Context not in output |
| `test_pii_redaction_by_key` | Log with key="email" | Value redacted (fast path) |
| `test_pii_redaction_email_pattern` | Log email in string value | Email pattern redacted (regex fallback) |
| `test_pii_redaction_phone_pattern` | Log phone in string value | Phone pattern redacted |
| `test_pii_redaction_ssn_pattern` | Log SSN in string value | SSN pattern redacted |
| `test_pii_redaction_skip_non_string` | Log with key="data", value=123 | Integer not processed by regex |
| `test_trace_id_inclusion` | Log with active trace | trace_id in output |
| `test_logger_name` | Get logger with name | logger field matches |

---

## Metrics

### Metric Definitions

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Service info
SERVICE_INFO = Info("soldier", "Soldier service information")

# Request metrics
REQUEST_COUNT = Counter(
    "soldier_requests_total",
    "Total number of requests",
    ["tenant_id", "agent_id", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "soldier_request_duration_seconds",
    "Request latency in seconds",
    ["tenant_id", "agent_id", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Pipeline metrics
PIPELINE_STEP_LATENCY = Histogram(
    "soldier_pipeline_step_duration_seconds",
    "Pipeline step latency in seconds",
    ["step", "tenant_id"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Provider metrics
LLM_CALL_COUNT = Counter(
    "soldier_llm_calls_total",
    "Total LLM provider calls",
    ["provider", "model", "step", "status"],
)

LLM_TOKENS = Counter(
    "soldier_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "direction"],  # direction: input/output
)

LLM_LATENCY = Histogram(
    "soldier_llm_call_duration_seconds",
    "LLM call latency in seconds",
    ["provider", "model", "step"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Rule matching metrics
RULES_MATCHED = Histogram(
    "soldier_rules_matched",
    "Number of rules matched per turn",
    ["tenant_id", "agent_id"],
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    "soldier_active_sessions",
    "Number of active sessions",
    ["tenant_id", "agent_id"],
)

# Error metrics
ERRORS = Counter(
    "soldier_errors_total",
    "Total errors",
    ["tenant_id", "error_type", "component"],
)
```

### Metrics Setup

```python
def setup_metrics() -> None:
    """Initialize Prometheus metrics.

    Effects:
        - Registers all metric collectors
        - Sets up service info
    """


def get_metrics_app() -> ASGIApplication:
    """Get ASGI app for /metrics endpoint.

    Returns:
        ASGI application serving Prometheus metrics
    """
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_counter_increment` | Increment counter | Value increases |
| `test_histogram_observe` | Observe histogram | Value recorded |
| `test_gauge_set` | Set gauge | Value updated |
| `test_label_cardinality` | Use labels | Metrics distinguished |
| `test_metrics_endpoint` | Scrape /metrics | Prometheus format output |
| `test_all_metrics_present` | Scrape /metrics | All defined metrics exist |

---

## Tracing

### Setup Interface

```python
def setup_tracing(
    service_name: str = "soldier",
    service_version: str = "0.1.0",
    otlp_endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> None:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Service name for spans
        service_version: Service version
        otlp_endpoint: OTLP collector endpoint (None = console exporter)
        sample_rate: Sampling rate (0.0-1.0)

    Effects:
        - Sets up TracerProvider
        - Configures exporter (OTLP or console)
        - Sets resource attributes
    """


def get_tracer(name: str) -> Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        OpenTelemetry Tracer
    """
```

### Span Creation Helpers

```python
@contextmanager
def span(
    name: str,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Iterator[Span]:
    """Create a span as context manager.

    Args:
        name: Span name
        attributes: Span attributes

    Yields:
        Active span
    """


def current_span() -> Span:
    """Get the current active span."""


def add_span_attributes(**kwargs) -> None:
    """Add attributes to the current span."""
```

### Standard Attributes

```python
# Required on all spans
ATTR_TENANT_ID = "tenant.id"
ATTR_AGENT_ID = "agent.id"
ATTR_SESSION_ID = "session.id"
ATTR_TURN_ID = "turn.id"

# Pipeline spans
ATTR_PIPELINE_STEP = "pipeline.step"

# LLM spans
ATTR_LLM_PROVIDER = "llm.provider"
ATTR_LLM_MODEL = "llm.model"
ATTR_LLM_TOKENS_INPUT = "llm.tokens.input"
ATTR_LLM_TOKENS_OUTPUT = "llm.tokens.output"

# Rule spans
ATTR_RULES_MATCHED = "rules.matched"
ATTR_SCENARIO_ACTIVE = "scenario.active"
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_setup_console_exporter` | Setup without endpoint | Spans to console |
| `test_setup_otlp_exporter` | Setup with endpoint | Spans to OTLP |
| `test_span_creation` | Create span | Span active in context |
| `test_span_attributes` | Set attributes | Attributes on span |
| `test_span_hierarchy` | Create nested spans | Parent-child relationship |
| `test_span_timing` | Complete span | Duration recorded |
| `test_trace_propagation` | Create with traceparent | Trace ID preserved |

---

## Middleware

### Request Context Middleware

```python
async def observability_middleware(request: Request, call_next) -> Response:
    """Bind observability context for request lifecycle.

    Effects:
        - Clears previous context
        - Binds tenant_id, agent_id, session_id from headers/body
        - Creates root span for request
        - Logs request start/end
        - Records request metrics

    Headers used:
        - X-Tenant-ID
        - X-Agent-ID
        - X-Session-ID
        - X-Request-ID
        - traceparent (W3C)
    """
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_context_extraction` | Request with headers | Context bound to logs |
| `test_trace_propagation` | Request with traceparent | Trace continued |
| `test_request_logging` | Any request | Start and end logged |
| `test_request_metrics` | Any request | Metrics recorded |
| `test_error_handling` | Request raises error | Error logged, span status error |
