# Error Handling Specification

> **Status**: PROPOSED
> **Date**: 2025-12-15
> **Scope**: Standardized error model across all Ruche platform layers
> **Dependencies**: API Layer (`api-layer.md`), ACF Specification (`acf/architecture/ACF_SPEC.md`)

---

## Executive Summary

This specification defines a **unified error handling model** for the Ruche platform. It covers:

1. **Error taxonomy**: Categorization by domain and severity
2. **Error propagation**: How errors flow through layers
3. **Client-facing errors**: What external callers see
4. **Recovery strategies**: Retry, fallback, escalation patterns
5. **Observability**: Logging, metrics, and alerting standards

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Structured error codes** | Machine-readable, stable across versions |
| **Layered error handling** | Each layer handles what it can, propagates what it can't |
| **Error context preservation** | Stack traces and context preserved internally, sanitized externally |
| **Graceful degradation** | Prefer partial success over total failure |
| **Idempotent recovery** | Retries must be safe |

---

## 1. Error Model

### 1.1 RucheError Base Class

```python
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    DEBUG = "debug"      # Development/debugging only
    INFO = "info"        # Expected conditions (rate limits, validation)
    WARNING = "warning"  # Recoverable issues (retry succeeded)
    ERROR = "error"      # Failed operation, needs attention
    CRITICAL = "critical"  # System-level failure, immediate action


class ErrorCategory(str, Enum):
    """Top-level error categories."""
    VALIDATION = "validation"      # Input validation failures
    AUTHENTICATION = "auth"        # Auth/authz failures
    RESOURCE = "resource"          # Resource not found, conflict
    RATE_LIMIT = "rate_limit"      # Rate/quota exceeded
    PROVIDER = "provider"          # External provider failures
    INTERNAL = "internal"          # Internal system errors
    TIMEOUT = "timeout"            # Operation timeouts
    POLICY = "policy"              # Policy/rule violations
    CHANNEL = "channel"            # Channel delivery failures


class RucheError(Exception):
    """
    Base error class for all Ruche exceptions.

    All errors carry structured metadata for logging and client responses.
    """

    def __init__(
        self,
        code: str,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.error_id = uuid4()
        self.timestamp = datetime.utcnow()

    def to_dict(self, include_internal: bool = False) -> dict:
        """Convert to dictionary for logging or response."""
        result = {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "error_id": str(self.error_id),
        }
        if self.details:
            result["details"] = self.details
        if self.retryable:
            result["retryable"] = True
        if self.retry_after_seconds:
            result["retry_after_seconds"] = self.retry_after_seconds

        if include_internal:
            result["severity"] = self.severity.value
            result["timestamp"] = self.timestamp.isoformat()
            if self.cause:
                result["cause"] = str(self.cause)

        return result
```

### 1.2 Error Response Model (API)

```python
class ErrorResponse(BaseModel):
    """
    Standard error response format for all API endpoints.

    This is what external clients receive.
    """

    error: dict = Field(
        ...,
        description="Error details",
        json_schema_extra={
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": {"field": "message", "reason": "required"},
                "error_id": "err_abc123",
            }
        },
    )


class ErrorDetail(BaseModel):
    """Structured error detail."""
    code: str
    message: str
    category: str | None = None
    details: dict[str, Any] | None = None
    error_id: str | None = None
    retryable: bool = False
    retry_after_seconds: int | None = None
```

---

## 2. Error Code Taxonomy

### 2.1 Validation Errors (4xx)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `VALIDATION_ERROR` | 400 | Generic validation failure | No |
| `INVALID_JSON` | 400 | Malformed JSON body | No |
| `MISSING_FIELD` | 400 | Required field missing | No |
| `INVALID_FIELD` | 400 | Field value invalid | No |
| `INVALID_UUID` | 400 | Invalid UUID format | No |
| `INVALID_CONTENT_TYPE` | 400 | Unsupported content type | No |
| `PAYLOAD_TOO_LARGE` | 413 | Request body exceeds limit | No |

### 2.2 Authentication Errors (401/403)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `AUTHENTICATION_REQUIRED` | 401 | No credentials provided | No |
| `INVALID_TOKEN` | 401 | Token invalid or expired | No |
| `TOKEN_EXPIRED` | 401 | Token has expired | Yes (refresh) |
| `INSUFFICIENT_PERMISSIONS` | 403 | Valid auth but not authorized | No |
| `TENANT_MISMATCH` | 403 | Token tenant doesn't match request | No |
| `AGENT_ACCESS_DENIED` | 403 | No access to specified agent | No |

### 2.3 Resource Errors (404/409)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `TENANT_NOT_FOUND` | 404 | Tenant doesn't exist | No |
| `AGENT_NOT_FOUND` | 404 | Agent doesn't exist | No |
| `SESSION_NOT_FOUND` | 404 | Session doesn't exist | No |
| `RULE_NOT_FOUND` | 404 | Rule doesn't exist | No |
| `SCENARIO_NOT_FOUND` | 404 | Scenario doesn't exist | No |
| `INTERLOCUTOR_NOT_FOUND` | 404 | Interlocutor doesn't exist | No |
| `RESOURCE_CONFLICT` | 409 | Resource already exists | No |
| `VERSION_CONFLICT` | 409 | Concurrent modification | Yes (refetch) |
| `RESOURCE_DELETED` | 410 | Resource was deleted | No |

### 2.4 Rate Limit Errors (429)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `RATE_LIMIT_EXCEEDED` | 429 | Request rate exceeded | Yes |
| `QUOTA_EXCEEDED` | 429 | Usage quota exceeded | No (contact sales) |
| `CONCURRENT_LIMIT` | 429 | Too many concurrent requests | Yes |

### 2.5 Provider Errors (502/503)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `LLM_ERROR` | 502 | LLM provider failure | Yes |
| `LLM_TIMEOUT` | 504 | LLM request timeout | Yes |
| `LLM_RATE_LIMIT` | 503 | LLM provider rate limited | Yes |
| `LLM_CONTENT_FILTER` | 422 | LLM content filter triggered | No |
| `EMBEDDING_ERROR` | 502 | Embedding provider failure | Yes |
| `RERANK_ERROR` | 502 | Rerank provider failure | Yes |
| `TOOL_PROVIDER_ERROR` | 502 | External tool API failure | Depends |

### 2.6 Internal Errors (500)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `INTERNAL_ERROR` | 500 | Unexpected internal error | No |
| `DATABASE_ERROR` | 500 | Database operation failed | Yes |
| `CACHE_ERROR` | 500 | Cache operation failed | Yes |
| `SERIALIZATION_ERROR` | 500 | Data serialization failed | No |
| `CONFIGURATION_ERROR` | 500 | Invalid configuration | No |

### 2.7 Timeout Errors (504)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `REQUEST_TIMEOUT` | 504 | Overall request timeout | Yes |
| `BRAIN_TIMEOUT` | 504 | Brain processing timeout | Yes |
| `TOOL_TIMEOUT` | 504 | Tool execution timeout | Depends |
| `MUTEX_TIMEOUT` | 503 | Session lock timeout | Yes |

### 2.8 Policy Errors (422)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `RULE_VIOLATION` | 422 | Response violated rule | No |
| `SAFETY_VIOLATION` | 422 | Safety policy triggered | No |
| `CONSTRAINT_VIOLATION` | 422 | Hard constraint violated | No |
| `TOOL_POLICY_DENIED` | 422 | Tool blocked by policy | No |
| `ESCALATION_REQUIRED` | 422 | Human escalation needed | No |

### 2.9 Channel Errors (502/503)

| Code | HTTP | Description | Retryable |
|------|------|-------------|-----------|
| `CHANNEL_UNAVAILABLE` | 503 | Channel temporarily unavailable | Yes |
| `CHANNEL_DELIVERY_FAILED` | 502 | Message delivery failed | Depends |
| `CHANNEL_RATE_LIMIT` | 429 | Channel rate limit exceeded | Yes |
| `INVALID_RECIPIENT` | 400 | Invalid recipient identifier | No |
| `CHANNEL_AUTH_FAILED` | 502 | Channel authentication failed | No |

---

## 3. Domain-Specific Error Classes

### 3.1 API Layer Errors

```python
class ValidationError(RucheError):
    """Input validation failed."""
    def __init__(self, field: str, reason: str, value: Any = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=f"Validation failed for field '{field}': {reason}",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.INFO,
            details={"field": field, "reason": reason, "value": str(value) if value else None},
        )


class AuthenticationError(RucheError):
    """Authentication failed."""
    def __init__(self, reason: str):
        super().__init__(
            code="AUTHENTICATION_REQUIRED",
            message=f"Authentication failed: {reason}",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.WARNING,
        )


class ResourceNotFoundError(RucheError):
    """Requested resource not found."""
    def __init__(self, resource_type: str, resource_id: str | UUID):
        super().__init__(
            code=f"{resource_type.upper()}_NOT_FOUND",
            message=f"{resource_type} not found: {resource_id}",
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.INFO,
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
        )


class RateLimitError(RucheError):
    """Rate limit exceeded."""
    def __init__(self, limit: int, window_seconds: int, retry_after: int):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit of {limit} requests per {window_seconds}s exceeded",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.INFO,
            retryable=True,
            retry_after_seconds=retry_after,
            details={"limit": limit, "window_seconds": window_seconds},
        )
```

### 3.2 Brain/Pipeline Errors

```python
class BrainError(RucheError):
    """Error during brain processing."""
    def __init__(self, phase: str, message: str, cause: Exception | None = None):
        super().__init__(
            code="BRAIN_ERROR",
            message=f"Brain error in {phase}: {message}",
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.ERROR,
            cause=cause,
            details={"phase": phase},
        )


class BrainTimeoutError(RucheError):
    """Brain processing timeout."""
    def __init__(self, phase: str, timeout_ms: int):
        super().__init__(
            code="BRAIN_TIMEOUT",
            message=f"Brain timeout in {phase} after {timeout_ms}ms",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.WARNING,
            retryable=True,
            details={"phase": phase, "timeout_ms": timeout_ms},
        )


class RuleViolationError(RucheError):
    """Response violated a rule."""
    def __init__(self, rule_id: str, rule_name: str, reason: str):
        super().__init__(
            code="RULE_VIOLATION",
            message=f"Response violated rule '{rule_name}': {reason}",
            category=ErrorCategory.POLICY,
            severity=ErrorSeverity.WARNING,
            details={"rule_id": rule_id, "rule_name": rule_name, "reason": reason},
        )
```

### 3.3 Provider Errors

```python
class ProviderError(RucheError):
    """External provider failure."""
    def __init__(
        self,
        provider: str,
        operation: str,
        message: str,
        cause: Exception | None = None,
        retryable: bool = True,
    ):
        super().__init__(
            code=f"{provider.upper()}_ERROR",
            message=f"{provider} {operation} failed: {message}",
            category=ErrorCategory.PROVIDER,
            severity=ErrorSeverity.ERROR,
            cause=cause,
            retryable=retryable,
            details={"provider": provider, "operation": operation},
        )


class LLMError(ProviderError):
    """LLM provider error."""
    def __init__(self, model: str, message: str, cause: Exception | None = None):
        super().__init__(
            provider="llm",
            operation="generate",
            message=f"[{model}] {message}",
            cause=cause,
            retryable=True,
        )
        self.details["model"] = model


class LLMContentFilterError(RucheError):
    """LLM content filter triggered."""
    def __init__(self, model: str, filter_type: str):
        super().__init__(
            code="LLM_CONTENT_FILTER",
            message=f"Content filter triggered: {filter_type}",
            category=ErrorCategory.POLICY,
            severity=ErrorSeverity.WARNING,
            retryable=False,
            details={"model": model, "filter_type": filter_type},
        )
```

### 3.4 Tool Errors

```python
class ToolError(RucheError):
    """Tool execution error."""
    def __init__(
        self,
        tool_name: str,
        message: str,
        cause: Exception | None = None,
        retryable: bool = False,
    ):
        super().__init__(
            code="TOOL_ERROR",
            message=f"Tool '{tool_name}' failed: {message}",
            category=ErrorCategory.PROVIDER,
            severity=ErrorSeverity.ERROR,
            cause=cause,
            retryable=retryable,
            details={"tool_name": tool_name},
        )


class ToolTimeoutError(RucheError):
    """Tool execution timeout."""
    def __init__(self, tool_name: str, timeout_ms: int):
        super().__init__(
            code="TOOL_TIMEOUT",
            message=f"Tool '{tool_name}' timed out after {timeout_ms}ms",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.WARNING,
            retryable=True,  # Idempotent tools can retry
            details={"tool_name": tool_name, "timeout_ms": timeout_ms},
        )


class ToolPolicyDeniedError(RucheError):
    """Tool blocked by policy."""
    def __init__(self, tool_name: str, policy: str, reason: str):
        super().__init__(
            code="TOOL_POLICY_DENIED",
            message=f"Tool '{tool_name}' blocked by policy '{policy}': {reason}",
            category=ErrorCategory.POLICY,
            severity=ErrorSeverity.INFO,
            details={"tool_name": tool_name, "policy": policy, "reason": reason},
        )
```

### 3.5 ACF Errors

```python
class MutexAcquisitionError(RucheError):
    """Failed to acquire session mutex."""
    def __init__(self, session_key: str, timeout_ms: int):
        super().__init__(
            code="MUTEX_TIMEOUT",
            message=f"Failed to acquire lock for session after {timeout_ms}ms",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.WARNING,
            retryable=True,
            details={"session_key": session_key, "timeout_ms": timeout_ms},
        )


class SupersedeError(RucheError):
    """Turn was superseded by new message."""
    def __init__(self, turn_id: UUID, reason: str):
        super().__init__(
            code="TURN_SUPERSEDED",
            message=f"Turn was superseded: {reason}",
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.INFO,
            details={"turn_id": str(turn_id), "reason": reason},
        )
```

---

## 4. Error Propagation

### 4.1 Layer Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          API Layer                                       │
│                                                                          │
│  - Validate request format                                              │
│  - Catch and transform all errors to HTTP responses                     │
│  - Add error_id, sanitize internal details                              │
│  - Set appropriate HTTP status codes                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          ACF Layer                                       │
│                                                                          │
│  - Handle mutex/concurrency errors                                      │
│  - Implement retry logic for transient failures                         │
│  - Propagate or transform brain/tool errors                             │
│  - Record errors in audit log                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Brain Layer                                     │
│                                                                          │
│  - Handle phase-specific errors                                         │
│  - Implement fallback strategies (alternate models, simplified output)   │
│  - Wrap provider errors with context                                    │
│  - Emit error events for observability                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Provider/Store Layer                               │
│                                                                          │
│  - Catch external API errors                                            │
│  - Add retry for transient failures                                     │
│  - Wrap exceptions in typed errors                                      │
│  - Track metrics (latency, error rates)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Error Handling Patterns

#### Pattern 1: Transform and Propagate

```python
async def process_turn(self, request: ChatRequest) -> ChatResponse:
    try:
        result = await self._brain.think(context)
        return self._build_response(result)

    except BrainTimeoutError as e:
        # Transform to API error with context
        raise HTTPException(
            status_code=504,
            detail=e.to_dict(),
        )

    except RuleViolationError as e:
        # Policy errors are 422
        raise HTTPException(
            status_code=422,
            detail=e.to_dict(),
        )
```

#### Pattern 2: Retry with Fallback

```python
async def generate_response(self, prompt: str) -> str:
    """Generate with retry and fallback chain."""

    for model in self._model_chain:
        for attempt in range(self._max_retries):
            try:
                return await self._llm.generate(model, prompt)

            except LLMError as e:
                if not e.retryable:
                    raise

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue

                # Try next model in chain
                logger.warning(
                    "llm_retry_exhausted",
                    model=model,
                    attempts=attempt + 1,
                )
                break

    # All models failed
    raise LLMError(
        model="all",
        message="All models in fallback chain failed",
    )
```

#### Pattern 3: Graceful Degradation

```python
async def retrieve_context(self, query: str) -> Context:
    """Retrieve with graceful degradation."""

    context = Context()

    # Memory retrieval - optional
    try:
        context.memories = await self._memory_store.search(query)
    except ProviderError as e:
        logger.warning("memory_retrieval_failed", error=str(e))
        context.memories = []  # Continue without memories

    # Rule retrieval - required
    try:
        context.rules = await self._config_store.get_rules(query)
    except Exception as e:
        # This is critical - propagate
        raise BrainError("retrieval", "Rule retrieval failed", cause=e)

    return context
```

---

## 5. API Error Responses

### 5.1 Standard Response Format

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit of 60 requests per 60s exceeded",
    "error_id": "err_abc123def456",
    "details": {
      "limit": 60,
      "window_seconds": 60
    },
    "retryable": true,
    "retry_after_seconds": 30
  }
}
```

### 5.2 HTTP Status Code Mapping

| Status | When to Use | Example Codes |
|--------|-------------|---------------|
| **400** | Client sent invalid request | `VALIDATION_ERROR`, `INVALID_JSON` |
| **401** | No/invalid authentication | `AUTHENTICATION_REQUIRED`, `INVALID_TOKEN` |
| **403** | Authenticated but not authorized | `INSUFFICIENT_PERMISSIONS`, `TENANT_MISMATCH` |
| **404** | Resource doesn't exist | `*_NOT_FOUND` |
| **409** | Resource conflict | `RESOURCE_CONFLICT`, `VERSION_CONFLICT` |
| **413** | Payload too large | `PAYLOAD_TOO_LARGE` |
| **422** | Valid request but can't process | `RULE_VIOLATION`, `LLM_CONTENT_FILTER` |
| **429** | Rate/quota limit | `RATE_LIMIT_EXCEEDED`, `QUOTA_EXCEEDED` |
| **500** | Internal server error | `INTERNAL_ERROR`, `DATABASE_ERROR` |
| **502** | Upstream provider error | `LLM_ERROR`, `TOOL_PROVIDER_ERROR` |
| **503** | Service temporarily unavailable | `MUTEX_TIMEOUT`, `CHANNEL_UNAVAILABLE` |
| **504** | Timeout | `REQUEST_TIMEOUT`, `BRAIN_TIMEOUT` |

### 5.3 Error Response Headers

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
X-Ruche-Error-Id: err_abc123def456
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1734264060
Retry-After: 30

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    ...
  }
}
```

---

## 6. Recovery Strategies

### 6.1 FabricErrorPolicy (ACF Configuration)

```python
class ErrorAction(str, Enum):
    """Action to take on error."""
    RETRY = "retry"         # Retry the operation
    FAIL = "fail"           # Fail and return error
    ESCALATE = "escalate"   # Escalate to human/webhook
    FALLBACK = "fallback"   # Use fallback strategy
    IGNORE = "ignore"       # Ignore and continue


class EscalationTarget(str, Enum):
    """Where to escalate errors."""
    TENANT_WEBHOOK = "tenant_webhook"
    INTERNAL_ALERT = "internal_alert"
    USER_ERROR_MESSAGE = "user_error"
    SILENT_LOG = "silent_log"


class FabricErrorPolicy(BaseModel):
    """
    Error handling policy for ACF.

    Configured per tenant/agent in ConfigStore.
    """

    # Action by error type
    on_brain_error: ErrorAction = ErrorAction.FAIL
    on_tool_error: ErrorAction = ErrorAction.ESCALATE
    on_tool_timeout: ErrorAction = ErrorAction.RETRY
    on_provider_error: ErrorAction = ErrorAction.RETRY
    on_mutex_timeout: ErrorAction = ErrorAction.FAIL

    # Retry settings
    max_retries: int = 3
    retry_backoff_base_ms: int = 1000
    retry_backoff_multiplier: float = 2.0
    retry_backoff_max_ms: int = 30000

    # Escalation settings
    escalation_target: EscalationTarget = EscalationTarget.SILENT_LOG
    escalation_webhook_url: str | None = None

    # Timeout settings
    brain_timeout_ms: int = 30000
    tool_timeout_ms: int = 15000
    total_timeout_ms: int = 60000
```

### 6.2 Configuration Example

```toml
[error_handling]
# Default policy
default_action = "fail"

# Brain errors
[error_handling.brain]
on_timeout = "retry"
on_error = "fail"
max_retries = 2

# Tool errors
[error_handling.tool]
on_timeout = "retry"
on_error = "escalate"
max_retries = 3
escalation_target = "tenant_webhook"

# Provider errors
[error_handling.provider]
on_llm_error = "fallback"
on_llm_timeout = "retry"
fallback_chain = ["claude-sonnet", "gpt-4o", "claude-haiku"]
max_retries = 3

# Timeouts
[error_handling.timeouts]
brain_ms = 30000
tool_ms = 15000
total_ms = 60000
```

---

## 7. Observability

### 7.1 Error Metrics

```python
# Error counts by code and category
ruche_errors_total = Counter(
    "ruche_errors_total",
    "Total errors by code and category",
    ["code", "category", "tenant_id"],
)

# Error rates by layer
ruche_error_rate = Histogram(
    "ruche_error_rate",
    "Error rate by layer",
    ["layer"],  # api, acf, brain, provider
)

# Retry metrics
ruche_retries_total = Counter(
    "ruche_retries_total",
    "Retry attempts",
    ["operation", "success"],
)

# Escalation metrics
ruche_escalations_total = Counter(
    "ruche_escalations_total",
    "Error escalations",
    ["target", "error_code"],
)
```

### 7.2 Structured Logging

```python
# Error occurred
logger.error(
    "error_occurred",
    error_id=str(error.error_id),
    error_code=error.code,
    category=error.category.value,
    severity=error.severity.value,
    message=error.message,
    details=error.details,
    retryable=error.retryable,
    tenant_id=str(context.tenant_id),
    agent_id=str(context.agent_id),
    session_key=context.session_key,
    trace_id=context.trace_id,
    exc_info=error.cause,
)

# Retry attempt
logger.warning(
    "retry_attempt",
    operation=operation,
    attempt=attempt,
    max_attempts=max_attempts,
    error_code=error.code,
    retry_delay_ms=delay_ms,
)

# Recovery succeeded
logger.info(
    "error_recovered",
    operation=operation,
    recovery_strategy=strategy,
    attempts=attempts,
)
```

### 7.3 Alerting Rules

```yaml
# Critical error rate spike
- alert: RucheCriticalErrorRate
  expr: rate(ruche_errors_total{severity="critical"}[5m]) > 0.1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Critical error rate spike"

# Provider error rate
- alert: RucheProviderErrorRate
  expr: rate(ruche_errors_total{category="provider"}[5m]) > 0.5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Provider error rate elevated"

# Escalation volume
- alert: RucheEscalationVolume
  expr: rate(ruche_escalations_total[1h]) > 10
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "High escalation volume"
```

---

## 8. Client SDK Error Handling

### 8.1 Python SDK Example

```python
from ruche import RucheClient, RucheError, RateLimitError, ResourceNotFoundError

client = RucheClient(api_key="...")

try:
    response = await client.chat(
        agent_id="...",
        message="Hello",
    )
except RateLimitError as e:
    # Retry after specified time
    await asyncio.sleep(e.retry_after_seconds)
    response = await client.chat(...)

except ResourceNotFoundError as e:
    # Handle missing resource
    print(f"Resource not found: {e.details}")

except RucheError as e:
    # Generic error handling
    if e.retryable:
        # Implement retry logic
        pass
    else:
        # Log and fail
        logger.error(f"Ruche error: {e.code} - {e.message}")
        raise
```

### 8.2 JavaScript SDK Example

```typescript
import { RucheClient, RucheError, isRetryable } from '@ruche/sdk';

const client = new RucheClient({ apiKey: '...' });

try {
  const response = await client.chat({
    agentId: '...',
    message: 'Hello',
  });
} catch (error) {
  if (error instanceof RucheError) {
    if (isRetryable(error)) {
      // Implement retry with exponential backoff
      await retryWithBackoff(() => client.chat(...), {
        maxRetries: 3,
        baseDelayMs: error.retryAfterSeconds * 1000 || 1000,
      });
    } else {
      console.error(`Error: ${error.code} - ${error.message}`);
      throw error;
    }
  }
  throw error;
}
```

---

## 9. Error Code Registry

All error codes must be registered in a central registry for documentation and SDK generation:

```python
ERROR_REGISTRY = {
    "VALIDATION_ERROR": {
        "http_status": 400,
        "category": "validation",
        "retryable": False,
        "description": "Request validation failed",
        "resolution": "Check request format against API documentation",
    },
    "RATE_LIMIT_EXCEEDED": {
        "http_status": 429,
        "category": "rate_limit",
        "retryable": True,
        "description": "Request rate limit exceeded",
        "resolution": "Wait for Retry-After seconds before retrying",
    },
    "LLM_ERROR": {
        "http_status": 502,
        "category": "provider",
        "retryable": True,
        "description": "LLM provider returned an error",
        "resolution": "Retry with exponential backoff; check provider status",
    },
    # ... all other codes
}
```

---

## 10. Future Considerations

### 10.1 Error Budgets

Track error budgets per tenant for SLA compliance:

```python
class ErrorBudget:
    """Track error budget consumption."""

    def __init__(self, slo_target: float = 0.999):
        self.slo_target = slo_target
        self.error_budget = 1 - slo_target  # 0.1% error budget

    def check_budget(self, tenant_id: UUID) -> bool:
        """Check if tenant has remaining error budget."""
        current_error_rate = self._get_error_rate(tenant_id)
        return current_error_rate < self.error_budget
```

### 10.2 Error Analytics

Aggregate error patterns for:
- Common failure modes
- Provider reliability comparison
- Tenant-specific issues
- Time-based patterns (peak hour errors)

### 10.3 Self-Healing

Automatic responses to detected patterns:
- Circuit breakers for failing providers
- Automatic failover to backup services
- Rate limit adjustments based on error rates

---

## References

- [API Layer](api-layer.md) - HTTP API specification
- [ACF Specification](../acf/architecture/ACF_SPEC.md) - Error policy configuration
- [Observability](observability.md) - Logging and metrics standards
- [RFC 7807](https://tools.ietf.org/html/rfc7807) - Problem Details for HTTP APIs
