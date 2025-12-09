# Research: Core Abstractions Layer

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This document consolidates research findings for implementing the Core Abstractions Layer (Phases 2-5). Since all technical decisions are pre-defined in the architecture documentation, this research focuses on best practices and implementation patterns.

---

## 1. Structured Logging with structlog

### Decision
Use structlog for structured logging with JSON output in production and console output in development.

### Rationale
- **Context binding via contextvars**: Thread-safe and async-safe context propagation without passing logger instances
- **Processor pipeline**: Flexible processing (timestamps, log levels, PII redaction) in a composable manner
- **Output flexibility**: JSON for machines, colored console for humans
- **Integration with stdlib logging**: Can wrap existing loggers for library compatibility

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Python stdlib logging | No native structured output, verbose configuration |
| loguru | Less mature processor pipeline, harder to customize |
| python-json-logger | Requires stdlib logging, less flexible processors |

### Best Practices
1. Use `structlog.contextvars.bind_contextvars()` to set request context once at entry point
2. Use `structlog.get_logger(__name__)` pattern for module-scoped loggers
3. Always log events as keyword arguments: `logger.info("event_name", key=value)`
4. Use processors for cross-cutting concerns (timestamps, trace IDs) rather than per-log logic

---

## 2. Prometheus Metrics with prometheus_client

### Decision
Use prometheus_client for Prometheus-compatible metrics with standard metric types.

### Rationale
- **De facto standard**: Prometheus is the dominant metrics system in cloud-native environments
- **Push vs pull**: Pull model fits container deployments (no centralized push target)
- **Metric types**: Counter, Histogram, Gauge, Info cover all observability needs
- **Label support**: Multi-dimensional metrics with tenant_id, agent_id labels

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| OpenTelemetry metrics | Less mature ecosystem, overkill for current needs |
| StatsD | Push model requires aggregator, less suited for containerized deployment |
| Custom metrics | Reinventing the wheel, no ecosystem integration |

### Best Practices
1. Use descriptive metric names with `focal_` prefix
2. Keep label cardinality bounded (don't use unbounded values like user_id)
3. Use Histograms for latency, Counters for events, Gauges for current state
4. Define buckets appropriate to expected latency distributions

---

## 3. OpenTelemetry Tracing

### Decision
Use OpenTelemetry SDK with OTLP exporter for distributed tracing.

### Rationale
- **Vendor neutral**: Works with Jaeger, Tempo, Honeycomb, Datadog
- **W3C trace context**: Standard propagation headers for distributed systems
- **Auto-instrumentation**: Library support for common frameworks
- **Unified API**: Same API for traces, eventually metrics and logs

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Jaeger client directly | Vendor lock-in, deprecated in favor of OpenTelemetry |
| Custom tracing | No standard propagation, no ecosystem tooling |

### Best Practices
1. Create spans at logical operation boundaries (pipeline steps, external calls)
2. Set semantic attributes per OpenTelemetry conventions (service.name, etc.)
3. Use BatchSpanProcessor for production (reduces overhead)
4. Propagate trace context via W3C traceparent header

---

## 4. Pydantic v2 Domain Models

### Decision
Use Pydantic v2 for all domain models with strict validation.

### Rationale
- **Performance**: Pydantic v2 is significantly faster than v1 (Rust core)
- **Validation**: Rich validation with clear error messages
- **Serialization**: JSON serialization with model_dump/model_validate
- **Type safety**: Full typing support with IDE integration

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| dataclasses | No built-in validation, manual serialization |
| attrs | Less ecosystem integration, less JSON support |
| TypedDict | No runtime validation |

### Best Practices
1. Use `Field()` for constraints: `Field(ge=0, le=100)` for ranges
2. Use `field_validator` for complex validation logic
3. Use `model_config` for JSON serialization settings
4. Use `Optional[T] = None` for optional fields with None default
5. Use `datetime` fields with `default_factory=datetime.utcnow`

---

## 5. Abstract Base Classes for Interfaces

### Decision
Use Python ABC (Abstract Base Class) for store and provider interfaces.

### Rationale
- **Enforcement**: `@abstractmethod` enforces implementation in subclasses
- **Type checking**: ABCs work with mypy/pyright for type checking
- **Documentation**: Interface defines contract explicitly in code
- **Testing**: Easy to create mock implementations from interface

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Protocol classes | Less explicit enforcement, more for structural typing |
| Plain classes | No enforcement of interface implementation |
| Duck typing | No compile-time interface validation |

### Best Practices
1. Keep interfaces minimal - only methods that all implementations must have
2. Use `@abstractmethod` on all interface methods
3. Use type hints on all parameters and return values
4. Document each method with docstring describing contract

---

## 6. In-Memory Store Implementations

### Decision
Implement all stores with dict-based in-memory storage for testing/development.

### Rationale
- **Zero dependencies**: No external services needed for tests
- **Fast**: Memory access is orders of magnitude faster than I/O
- **Deterministic**: No network latency or connection issues
- **Contract tests**: Same tests run against in-memory and production implementations

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| SQLite | Requires disk I/O, more complex setup |
| Fake/stub classes | Less realistic behavior for integration tests |
| Mocking libraries | Per-test setup overhead, less readable |

### Best Practices
1. Store data in plain dicts keyed by ID
2. Implement vector search with cosine similarity and linear scan
3. Implement text search with simple substring matching
4. Use deepcopy when returning stored objects to prevent mutation

---

## 7. Mock Provider Implementations

### Decision
Implement mock providers with configurable responses for testing.

### Rationale
- **Deterministic tests**: Same input always produces same output
- **No API costs**: Tests don't consume API quotas
- **Fast execution**: No network latency
- **Edge case testing**: Can simulate errors, timeouts, edge cases

### Best Practices
1. Accept default response in constructor for simple cases
2. Support response sequences for multi-call scenarios
3. Track call history for assertion in tests
4. Simulate realistic token usage for LLM mocks

---

## 8. Async Patterns

### Decision
All store and provider methods are async, using asyncio patterns.

### Rationale
- **Non-blocking I/O**: Production implementations will do network I/O
- **Consistency**: Same interface for mock and production implementations
- **Scalability**: Async enables handling many concurrent requests

### Best Practices
1. Use `async def` for all interface methods
2. Use `await` even in mock implementations (for interface consistency)
3. Use `asyncio.gather()` for parallel operations
4. Use `pytest-asyncio` with `@pytest.mark.asyncio` decorator

---

## 9. Testing Strategy

### Decision
Unit tests for individual components, contract tests for store implementations.

### Rationale
- **Unit tests**: Fast feedback, test edge cases, ~80% of test effort
- **Contract tests**: Ensure all implementations behave identically
- **Integration tests**: Verify components work together

### Best Practices
1. One test file per module, mirroring source structure
2. Use pytest fixtures for common setup (stores, providers, sample data)
3. Use factory patterns for test data generation
4. Contract tests inherit from base test class with all assertions

---

## 10. PII Redaction (Clarified)

### Decision
Two-tier PII redaction: (1) key-name lookup via frozenset, (2) regex patterns on string values.

### Rationale (from spec clarifications)
- **O(1) key lookup** catches 95% of cases (email, password, token, ssn fields)
- **Regex fallback** catches accidental PII in freeform text fields
- **Minimal performance impact** - regex only runs on string values after key check fails

### Implementation
```python
# 1. Keys that are ALWAYS sensitive (Fastest - O(1))
SENSITIVE_KEYS = frozenset({
    "password", "token", "secret", "api_key",
    "user_email", "email", "phone", "ssn", "credit_card"
})

# 2. Regex for accidental PII in string values (Slower fallback)
PII_REGEX_PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "PHONE": re.compile(r'\b\+?1?\d{9,15}\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
}

REDACTED_MASK = "[REDACTED]"
```

### Best Practices
1. Check key name first (fast path), then regex on string values (slow path)
2. Skip regex on non-string values (ints, bools) to save CPU
3. Use `[REDACTED]` as mask for consistency
4. Document which fields contain PII in model definitions

---

## 11. Vector Similarity Metric (Clarified)

### Decision
Use **cosine similarity** for all in-memory vector search operations.

### Rationale (from spec clarifications)
- Most common metric for text embeddings
- Production vector databases (pgvector, Pinecone) typically default to cosine
- Text embedding models are optimized for cosine similarity
- Range -1 to 1 makes score interpretation straightforward

### Implementation
```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

---

## 12. Mock Provider Failure Injection (Clarified)

### Decision
All mock providers support `fail_after_n` and `error_rate` configuration for testing.

### Rationale (from spec clarifications)
- Enables testing error handling paths without real provider failures
- `fail_after_n`: Deterministic - succeeds N times then fails
- `error_rate`: Probabilistic - fails with given probability

### Implementation
```python
class MockLLMProvider(LLMProvider):
    def __init__(
        self,
        default_response: str = "Mock response",
        fail_after_n: int | None = None,
        error_rate: float = 0.0,
    ):
        self._call_count = 0
        self._fail_after_n = fail_after_n
        self._error_rate = error_rate

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self._call_count += 1

        # Deterministic failure
        if self._fail_after_n and self._call_count > self._fail_after_n:
            raise ProviderError("Mock failure after N calls")

        # Probabilistic failure
        if random.random() < self._error_rate:
            raise ProviderError("Mock random failure")

        return LLMResponse(text=self._default_response, ...)
```

---

## 13. Context Propagation (Clarified)

### Decision
Use Python's `contextvars` module for async-safe context propagation.

### Rationale (from spec clarifications)
- Built into Python 3.7+ (no external dependency)
- Works correctly with asyncio (copies context to new tasks)
- Native integration with structlog via `merge_contextvars` processor

### Implementation
```python
from contextvars import ContextVar
from structlog.contextvars import bind_contextvars, clear_contextvars

# Define context variables
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
agent_id_var: ContextVar[str | None] = ContextVar("agent_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
turn_id_var: ContextVar[str | None] = ContextVar("turn_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Bind context at request entry
def bind_request_context(
    tenant_id: str,
    agent_id: str,
    session_id: str | None = None,
    turn_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    bind_contextvars(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        turn_id=turn_id,
        trace_id=trace_id,
    )
```

---

## Summary

All technical decisions for this phase are well-defined by the architecture documentation and spec clarifications:

| Decision | Source |
|----------|--------|
| Two-tier PII redaction | Spec clarification |
| Cosine similarity | Spec clarification |
| contextvars propagation | Spec clarification |
| Mock failure injection | Spec clarification |
| structlog for logging | Architecture docs |
| prometheus_client for metrics | Architecture docs |
| OpenTelemetry for tracing | Architecture docs |
| Pydantic v2 for models | Architecture docs |
| ABC for interfaces | Architecture docs |
| Async all methods | Architecture docs |

No open questions - proceeding to Phase 1 design artifacts.
