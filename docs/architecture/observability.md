# Observability Architecture

This document defines Focal's logging, tracing, and metrics strategy. Focal is designed to integrate seamlessly into the External Platform (kernel_agent) observability stack while providing rich, structured telemetry for debugging, auditing, and performance analysis.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Structured over unstructured** | JSON logs with consistent schema, not plain text |
| **Context propagation** | Every log/span includes `tenant_id`, `agent_id`, `session_id`, `logical_turn_id` |
| **Audit vs. Operational separation** | Domain events in `AuditStore`, runtime debugging in logs |
| **Container-native** | stdout only; no file writes; let orchestrator handle shipping |
| **Vendor-agnostic** | OpenTelemetry for traces, Prometheus for metrics |

---

## Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OBSERVABILITY                                   │
├─────────────────────┬─────────────────────┬─────────────────────────────────┤
│       LOGS          │       TRACES        │           METRICS               │
│                     │                     │                                 │
│  Structured JSON    │  OpenTelemetry      │  Prometheus                     │
│  via structlog      │  spans per          │  counters/histograms            │
│                     │  brain step      │                                 │
│  → stdout           │  → OTLP Collector   │  → /metrics endpoint            │
│  → Promtail/Fluent  │  → Jaeger/Tempo     │  → Prometheus scrape            │
│  → Loki/ELK         │                     │  → Grafana                      │
└─────────────────────┴─────────────────────┴─────────────────────────────────┘
```

---

## 1. Logging

### Library Choice: structlog

Focal uses [structlog](https://www.structlog.org/) for structured logging. This provides:

- **JSON output** for machine parsing in production
- **Console output** with colors for local development
- **Context binding** via contextvars (thread-safe, async-safe)
- **Processors** for timestamp, log level, and custom enrichment

### Log Schema

Every log entry includes these fields:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "info",
  "event": "turn_processed",
  "logger": "ruche.alignment.brain",

  "tenant_id": "tenant_abc123",
  "agent_id": "agent_xyz789",
  "session_id": "sess_456",
  "logical_turn_id": "turn_789",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",

  "latency_ms": 342,
  "rules_matched": 3,
  "scenario": "returns_flow",
  "step": "collect_order_id"
}
```

### Log Levels

| Level | Use Case | Production Visibility |
|-------|----------|----------------------|
| **DEBUG** | Verbose internals, LLM prompts/responses, full payloads | Off (only enable for troubleshooting) |
| **INFO** | Request lifecycle, brain steps, provider calls | On |
| **WARNING** | Fallbacks triggered, retries, degraded operations | On |
| **ERROR** | Failures, exceptions, constraint violations | On |

### Privacy and Security

- **Never log secrets**: API keys, tokens, passwords (use `SecretStr` in Pydantic)
- **Never log raw PII at INFO**: User messages, LLM responses only at DEBUG
- **Redact sensitive fields**: Email, phone, SSN patterns auto-redacted
- **Follow [configuration-secrets.md](./configuration-secrets.md)** guidance

### Configuration

```toml
# config/default.toml
[observability.logging]
level = "INFO"
format = "json"              # "json" for production, "console" for development
include_trace_id = true
redact_pii = true
redact_patterns = [
    "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",  # Email
    "\\b\\d{3}-\\d{2}-\\d{4}\\b",                                # SSN
]
```

```toml
# config/development.toml
[observability.logging]
level = "DEBUG"
format = "console"           # Pretty-printed for local development
```

### Implementation

```python
# ruche/observability/logging.py
import logging
import os
from typing import Literal

import structlog


def setup_logging(
    level: str = "INFO",
    format: Literal["json", "console"] = "json",
    include_trace_id: bool = True,
) -> None:
    """Configure structured logging for Focal.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format ("json" for production, "console" for dev)
        include_trace_id: Whether to include trace_id from OpenTelemetry
    """
    # Shared processors
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Add trace ID from OpenTelemetry context
    if include_trace_id:
        processors.append(_add_trace_id)

    # Format-specific renderer
    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _add_trace_id(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Add OpenTelemetry trace_id to log event."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            ctx = span.get_span_context()
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except ImportError:
        pass
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Bound structlog logger
    """
    return structlog.get_logger(name)
```

### Request Context Middleware

```python
# ruche/api/middleware/logging.py
from fastapi import Request
from structlog.contextvars import bind_contextvars, clear_contextvars

from ruche.observability.logging import get_logger

logger = get_logger(__name__)


async def logging_context_middleware(request: Request, call_next):
    """Bind request context to all logs within this request."""
    clear_contextvars()

    # Extract IDs from headers or request body
    bind_contextvars(
        tenant_id=request.headers.get("X-Tenant-ID"),
        agent_id=request.headers.get("X-Agent-ID"),
        session_id=request.headers.get("X-Session-ID"),
        request_id=request.headers.get("X-Request-ID"),
        # Extract trace_id from W3C traceparent header
        trace_id=_extract_trace_id(request.headers.get("traceparent")),
    )

    logger.info("request_started", method=request.method, path=request.url.path)

    response = await call_next(request)

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )

    return response


def _extract_trace_id(traceparent: str | None) -> str | None:
    """Extract trace_id from W3C traceparent header."""
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) >= 2 else None
```

---

## 2. Tracing

### Integration with kernel_agent

Focal reuses the OpenTelemetry setup from `libs/observability` in kernel_agent:

```python
# ruche/observability/tracing.py
import os
from typing import Optional

# Reuse kernel_agent's tracing setup if available
try:
    from libs.observability import setup_tracing as _setup_tracing

    def setup_tracing(
        service_name: str = "focal",
        service_version: str = "0.1.0",
        otlp_endpoint: Optional[str] = None,
    ) -> None:
        """Setup OpenTelemetry tracing for Focal."""
        endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        _setup_tracing(service_name, service_version, endpoint)

except ImportError:
    # Standalone mode - configure OpenTelemetry directly
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    def setup_tracing(
        service_name: str = "focal",
        service_version: str = "0.1.0",
        otlp_endpoint: Optional[str] = None,
    ) -> None:
        """Setup OpenTelemetry tracing for Focal (standalone mode)."""
        resource = Resource.create({
            "service.name": service_name,
            "service.version": service_version,
        })

        provider = TracerProvider(resource=resource)

        endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
        else:
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
```

### Span Structure

Each turn creates a trace with spans for each FOCAL brain step:

```
turn_process (root span)
├── context_extraction
│   └── llm_call (provider: anthropic, model: haiku)
├── retrieval
│   ├── rule_retrieval
│   ├── scenario_retrieval
│   └── memory_retrieval
├── reranking
│   └── rerank_call (provider: cohere)
├── rule_filtering
│   └── llm_call (provider: anthropic, model: haiku)
├── tool_execution
│   └── tool_call (tool: get_order_status)
├── generation
│   └── llm_call (provider: anthropic, model: sonnet)
├── enforcement
└── persist
    ├── session_store
    └── audit_store
```

### Span Attributes

```python
span.set_attribute("tenant_id", tenant_id)
span.set_attribute("agent_id", agent_id)
span.set_attribute("session_id", session_id)
span.set_attribute("logical_turn_id", logical_turn_id)
span.set_attribute("focal.step", "generation")
span.set_attribute("llm.provider", "anthropic")
span.set_attribute("llm.model", "claude-sonnet-4-5-20250514")
span.set_attribute("llm.tokens.input", 1500)
span.set_attribute("llm.tokens.output", 350)
span.set_attribute("rules.matched", 3)
span.set_attribute("scenario.active", "returns_flow")
```

### Configuration

```toml
# config/default.toml
[observability.tracing]
enabled = true
service_name = "focal"
otlp_endpoint = ""           # Empty = use OTEL_EXPORTER_OTLP_ENDPOINT env var
sample_rate = 1.0            # 1.0 = 100% sampling (reduce in production)
propagators = ["tracecontext", "baggage"]  # W3C standard
```

---

## 3. Metrics

### Prometheus Integration

Focal exposes a `/metrics` endpoint compatible with Prometheus scraping:

```python
# ruche/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info

# Service info
SERVICE_INFO = Info("focal", "Focal service information")

# Request metrics
REQUEST_COUNT = Counter(
    "focal_requests_total",
    "Total number of requests",
    ["tenant_id", "agent_id", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "focal_request_duration_seconds",
    "Request latency in seconds",
    ["tenant_id", "agent_id", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# FOCAL brain metrics
PIPELINE_STEP_LATENCY = Histogram(
    "focal_pipeline_step_duration_seconds",
    "FOCAL brain step latency in seconds",
    ["step", "tenant_id"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Provider metrics
LLM_CALL_COUNT = Counter(
    "focal_llm_calls_total",
    "Total LLM provider calls",
    ["provider", "model", "step", "status"],
)

LLM_TOKENS = Counter(
    "focal_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "direction"],  # direction: input/output
)

LLM_LATENCY = Histogram(
    "focal_llm_call_duration_seconds",
    "LLM call latency in seconds",
    ["provider", "model", "step"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

PROVIDER_FALLBACK = Counter(
    "focal_provider_fallbacks_total",
    "Provider fallback events",
    ["step", "from_provider", "to_provider", "reason"],
)

# Rule matching metrics
RULES_MATCHED = Histogram(
    "focal_rules_matched",
    "Number of rules matched per turn",
    ["tenant_id", "agent_id"],
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

RULE_FIRES = Counter(
    "focal_rule_fires_total",
    "Total rule fires",
    ["tenant_id", "agent_id", "rule_id", "scope"],
)

# Scenario metrics
SCENARIO_TRANSITIONS = Counter(
    "focal_scenario_transitions_total",
    "Scenario state transitions",
    ["tenant_id", "agent_id", "scenario_id", "from_step", "to_step"],
)

# Memory metrics
MEMORY_RETRIEVAL_LATENCY = Histogram(
    "focal_memory_retrieval_duration_seconds",
    "Memory retrieval latency",
    ["tenant_id", "retrieval_type"],  # retrieval_type: vector, bm25, graph
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5],
)

MEMORY_RESULTS = Histogram(
    "focal_memory_results",
    "Number of memory results retrieved",
    ["tenant_id", "retrieval_type"],
    buckets=[0, 1, 5, 10, 20, 50],
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    "focal_active_sessions",
    "Number of active sessions",
    ["tenant_id", "agent_id"],
)

# Error metrics
ERRORS = Counter(
    "focal_errors_total",
    "Total errors",
    ["tenant_id", "error_type", "component"],
)
```

### Configuration

```toml
# config/default.toml
[observability.metrics]
enabled = true
path = "/metrics"
include_default_metrics = true   # Python process metrics
```

### Prometheus Scrape Config

Add to kernel_agent's `infra/observability/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'focal'
    static_configs:
      - targets: ['focal:8000']
        labels:
          service: 'focal'
          component: 'cognitive-layer'
```

---

## 4. Audit Store vs. Logs

### Separation of Concerns

| Data Type | Storage | Retention | Purpose |
|-----------|---------|-----------|---------|
| **Turn records** | AuditStore (PostgreSQL) | Years | Compliance, replay, analytics |
| **Rule fires** | AuditStore | Years | Behavior analysis, debugging |
| **Scenario transitions** | AuditStore | Years | Flow analysis |
| **Provider errors** | Logs (stdout) | Days/weeks | Operational debugging |
| **Latency details** | Traces (Jaeger/Tempo) | Days | Performance analysis |
| **Request counts** | Metrics (Prometheus) | Months | Capacity planning |

### What Goes Where

```python
# AuditStore - durable, queryable domain events
await audit_store.log_turn(
    logical_turn_id=logical_turn_id,
    tenant_id=tenant_id,
    agent_id=agent_id,
    session_id=session_id,
    user_message=message,
    agent_response=response,
    rules_matched=[rule.id for rule in matched_rules],
    scenario_id=scenario.id if scenario else None,
    step_id=step.id if step else None,
    latency_ms=latency,
    tokens_used=tokens,
)

# Logs - operational debugging (ephemeral)
logger.info(
    "turn_completed",
    logical_turn_id=logical_turn_id,
    latency_ms=latency,
    rules_matched=len(matched_rules),
    fallback_triggered=fallback_used,
)
```

---

## 5. Integration with kernel_agent

### Docker Compose Environment

```yaml
# In kernel_agent's docker-compose.yml
focal:
  build:
    context: ../focal
    dockerfile: Dockerfile
  environment:
    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    OTEL_SERVICE_NAME: focal
    LOG_LEVEL: INFO

    # ... other env vars
  networks:
    - external
```

### Correlation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Message-Router │────▶│     Focal     │────▶│    ToolHub      │
│                 │     │                 │     │                 │
│  traceparent:   │     │  traceparent:   │     │  traceparent:   │
│  00-abc123-...  │     │  00-abc123-...  │     │  00-abc123-...  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OpenTelemetry Collector                      │
│                         (otel-collector)                         │
└─────────────────────────────────────────────────────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Jaeger/Tempo   │     │   Prometheus    │     │   Loki (future) │
│    (traces)     │     │    (metrics)    │     │     (logs)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 6. Configuration Reference

### Full Observability Configuration

Observability settings are split between root-level settings (for compatibility with existing config) and a dedicated `[observability]` section for detailed options.

```toml
# config/default.toml

# Root-level logging (existing config pattern)
app_name = "focal"
debug = false
log_level = "INFO"                # DEBUG, INFO, WARNING, ERROR

# Detailed observability settings
[observability]
# Logging format and enrichment
log_format = "json"               # "json" for production, "console" for dev
log_include_trace_id = true       # Add trace_id from OpenTelemetry
log_redact_pii = true             # Auto-redact email, phone, SSN patterns
log_redact_patterns = []          # Additional regex patterns to redact

# Tracing (OpenTelemetry)
tracing_enabled = true
tracing_service_name = "focal"
tracing_otlp_endpoint = ""        # Uses OTEL_EXPORTER_OTLP_ENDPOINT if empty
tracing_sample_rate = 1.0         # 0.0-1.0, reduce in high-traffic production
tracing_propagators = ["tracecontext", "baggage"]

# Metrics (Prometheus)
metrics_enabled = true
metrics_path = "/metrics"
metrics_include_default = true    # Python process metrics (memory, GC, etc.)
```

```toml
# config/development.toml
debug = true
log_level = "DEBUG"

[observability]
log_format = "console"            # Pretty-printed for local development
tracing_sample_rate = 1.0         # 100% sampling in dev
```

```toml
# config/production.toml
debug = false
log_level = "INFO"

[observability]
log_format = "json"
tracing_sample_rate = 0.1         # 10% sampling in production
```

### Environment Overrides

```bash
# Root-level logging (existing pattern)
export RUCHE_LOG_LEVEL=DEBUG
export RUCHE_DEBUG=true

# Observability section
export RUCHE_OBSERVABILITY__LOG_FORMAT=console
export RUCHE_OBSERVABILITY__TRACING_ENABLED=true

# Standard OpenTelemetry environment variables (used by kernel_agent)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_SERVICE_NAME=focal
export LOG_LEVEL=INFO
```

---

## Related Documentation

- [Configuration Overview](./configuration-overview.md) - Configuration system
- [Configuration Secrets](./configuration-secrets.md) - Secrets management
- [API Layer](./api-layer.md) - Request handling and middleware
- [FOCAL Brain](../focal_brain/spec/brain.md) - FOCAL brain steps to instrument
- [ADR-001: Storage](../design/decisions/001-storage-choice.md) - AuditStore interface
