# Data Model: API Layer - Core

**Feature**: 006-api-layer-core
**Date**: 2025-11-28

## Overview

This document defines the Pydantic models for the API layer. These models handle request validation, response serialization, and internal state for middleware.

---

## 1. Request Models

### ChatRequest

The primary request model for message processing.

```python
class ChatRequest(BaseModel):
    """Request body for POST /v1/chat and POST /v1/chat/stream."""

    tenant_id: UUID
    """Tenant identifier (resolved upstream by gateway)."""

    agent_id: UUID
    """Agent to process the message."""

    channel: str
    """Channel source: whatsapp, slack, webchat, etc."""

    user_channel_id: str
    """User identifier on the channel (e.g., phone number, Slack user ID)."""

    message: str
    """The user's message text."""

    session_id: str | None = None
    """Optional existing session ID. Auto-created if omitted."""

    metadata: dict[str, Any] | None = None
    """Optional additional context (locale, device info, etc.)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "channel": "whatsapp",
                "user_channel_id": "+1234567890",
                "message": "I want to return my order",
                "session_id": "sess_abc123",
                "metadata": {"locale": "en-US"},
            }
        }
    )
```

**Validation Rules**:
- `tenant_id`: Required, valid UUID
- `agent_id`: Required, valid UUID
- `channel`: Required, non-empty string
- `user_channel_id`: Required, non-empty string
- `message`: Required, non-empty string, max 10,000 characters

---

## 2. Response Models

### ChatResponse

Response from synchronous chat processing.

```python
class ScenarioState(BaseModel):
    """Current scenario and step state."""
    id: str | None = None
    step: str | None = None

class ChatResponse(BaseModel):
    """Response body for POST /v1/chat."""

    response: str
    """The agent's response text."""

    session_id: str
    """Session identifier (existing or newly created)."""

    turn_id: str
    """Unique identifier for this turn."""

    scenario: ScenarioState | None = None
    """Current scenario state if in a scenario."""

    matched_rules: list[str] = Field(default_factory=list)
    """IDs of rules that matched this turn."""

    tools_called: list[str] = Field(default_factory=list)
    """IDs of tools that were executed."""

    tokens_used: int = 0
    """Total tokens consumed (prompt + completion)."""

    latency_ms: int = 0
    """Total processing time in milliseconds."""
```

### StreamEvent

Events for SSE streaming response.

```python
class StreamEventType(str, Enum):
    """Types of streaming events."""
    TOKEN = "token"
    DONE = "done"
    ERROR = "error"

class TokenEvent(BaseModel):
    """Incremental token during streaming."""
    type: Literal["token"] = "token"
    content: str

class DoneEvent(BaseModel):
    """Final event when streaming completes."""
    type: Literal["done"] = "done"
    turn_id: str
    session_id: str
    matched_rules: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    latency_ms: int = 0

class ErrorEvent(BaseModel):
    """Error event during streaming."""
    type: Literal["error"] = "error"
    code: str
    message: str

StreamEvent = TokenEvent | DoneEvent | ErrorEvent
```

---

## 3. Session Models

### SessionResponse

Response for GET /v1/sessions/{id}.

```python
class SessionResponse(BaseModel):
    """Session state response."""

    session_id: str
    tenant_id: str
    agent_id: str
    channel: str
    user_channel_id: str

    active_scenario_id: str | None = None
    active_step_id: str | None = None

    turn_count: int = 0
    variables: dict[str, Any] = Field(default_factory=dict)
    rule_fires: dict[str, int] = Field(default_factory=dict)

    config_version: int | None = None
    created_at: datetime
    last_activity_at: datetime
```

### TurnResponse

Individual turn in session history.

```python
class TurnResponse(BaseModel):
    """Single turn in conversation history."""

    turn_id: str
    turn_number: int
    user_message: str
    agent_response: str

    matched_rules: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)

    scenario_before: ScenarioState | None = None
    scenario_after: ScenarioState | None = None

    latency_ms: int = 0
    tokens_used: int = 0
    timestamp: datetime
```

### TurnListResponse

Paginated list of turns.

```python
class TurnListResponse(BaseModel):
    """Paginated turn history response."""

    items: list[TurnResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
```

---

## 4. Error Models

### ErrorCode

Enumeration of error codes.

```python
class ErrorCode(str, Enum):
    """Standardized error codes."""

    INVALID_REQUEST = "INVALID_REQUEST"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    RULE_VIOLATION = "RULE_VIOLATION"
    TOOL_FAILED = "TOOL_FAILED"
    LLM_ERROR = "LLM_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

### ErrorResponse

Standard error response format.

```python
class ErrorDetail(BaseModel):
    """Detailed error information."""
    field: str | None = None
    message: str

class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorBody

class ErrorBody(BaseModel):
    """Error body content."""

    code: ErrorCode
    message: str
    details: list[ErrorDetail] | None = None
    turn_id: str | None = None
    rule_id: str | None = None
```

---

## 5. Health Models

### HealthResponse

Response for GET /health.

```python
class ComponentHealth(BaseModel):
    """Health status of a single component."""
    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float | None = None
    message: str | None = None

class HealthResponse(BaseModel):
    """Overall health status."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    components: list[ComponentHealth] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## 6. Middleware Models

### TenantContext

Extracted from JWT for request processing.

```python
class TenantContext(BaseModel):
    """Tenant context extracted from authentication."""

    tenant_id: UUID
    user_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    tier: Literal["free", "pro", "enterprise"] = "free"

    model_config = ConfigDict(frozen=True)
```

### RateLimitResult

Result of rate limit check.

```python
class RateLimitResult(BaseModel):
    """Rate limit check result."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
```

### RequestContext

Full request context for logging and tracing.

```python
class RequestContext(BaseModel):
    """Request context for observability."""

    trace_id: str
    span_id: str
    tenant_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: str | None = None
    turn_id: str | None = None
    request_id: str
```

---

## 7. Relationships

```
ChatRequest
    └── validates → AlignmentEngine.process_turn()
                        └── produces → AlignmentResult
                                           └── maps to → ChatResponse

SessionStore
    └── Session → maps to → SessionResponse

AuditStore
    └── TurnRecord → maps to → TurnResponse
```

---

## 8. Exception Hierarchy

All API exceptions inherit from `FocalAPIError` for consistent error handling:

```python
class FocalAPIError(Exception):
    """Base exception for all API errors."""
    status_code: int = 500
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    message: str

class AgentNotFoundError(FocalAPIError):
    """Raised when agent_id doesn't exist."""
    status_code = 400
    error_code = ErrorCode.AGENT_NOT_FOUND

class SessionNotFoundError(FocalAPIError):
    """Raised when session_id doesn't exist."""
    status_code = 404
    error_code = ErrorCode.SESSION_NOT_FOUND

class RateLimitExceededError(FocalAPIError):
    """Raised when tenant exceeds rate limit."""
    status_code = 429
    error_code = ErrorCode.RATE_LIMIT_EXCEEDED

class LLMProviderError(FocalAPIError):
    """Raised when LLM provider fails."""
    status_code = 502
    error_code = ErrorCode.LLM_ERROR
```

**Location**: `focal/api/exceptions.py`

---

## 9. Model Location

All models defined in:
- `focal/api/models/chat.py` - ChatRequest, ChatResponse, StreamEvent
- `focal/api/models/errors.py` - ErrorCode, ErrorResponse
- `focal/api/models/session.py` - SessionResponse, TurnResponse
- `focal/api/models/health.py` - HealthResponse
- `focal/api/models/context.py` - TenantContext, RateLimitResult, RequestContext
- `focal/api/exceptions.py` - FocalAPIError and subclasses
