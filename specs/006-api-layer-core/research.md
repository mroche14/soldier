# Research: API Layer - Core

**Feature**: 006-api-layer-core
**Date**: 2025-11-28

## Overview

This document captures research findings for implementing Focal's HTTP API layer. All "NEEDS CLARIFICATION" items from the technical context have been resolved.

---

## 1. FastAPI Application Factory Pattern

### Decision
Use FastAPI's application factory pattern with `create_app()` function for testability and configuration flexibility.

### Rationale
- Allows different configurations for testing vs production
- Enables lazy initialization of dependencies
- Follows existing Focal patterns (dependency injection)
- Standard practice in production FastAPI applications

### Implementation Pattern
```python
def create_app(
    settings: Settings | None = None,
    config_store: ConfigStore | None = None,
    session_store: SessionStore | None = None,
    # ... other dependencies
) -> FastAPI:
    app = FastAPI(title="Focal API", version="1.0.0")
    # Configure middleware, routes, exception handlers
    return app
```

### Alternatives Considered
- **Global app instance**: Rejected - hard to test, tight coupling
- **Class-based app wrapper**: Rejected - unnecessary complexity, FastAPI already provides good DI

---

## 2. SSE Streaming with FastAPI

### Decision
Use `sse-starlette` library with FastAPI's `StreamingResponse` for Server-Sent Events.

### Rationale
- `sse-starlette` provides proper SSE formatting and connection handling
- Works well with async generators
- Handles client disconnection gracefully
- Widely adopted in production FastAPI applications

### Implementation Pattern
```python
from sse_starlette.sse import EventSourceResponse

@router.post("/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for token in alignment_engine.stream_response(...):
            yield {"event": "token", "data": json.dumps({"content": token})}
        yield {"event": "done", "data": json.dumps({"turn_id": str(turn_id)})}

    return EventSourceResponse(event_generator())
```

### Alternatives Considered
- **WebSockets**: Rejected - SSE is simpler for unidirectional streaming, matches spec requirements
- **Raw StreamingResponse**: Rejected - requires manual SSE formatting

---

## 3. JWT Authentication Middleware

### Decision
Use `python-jose` for JWT validation with a custom FastAPI dependency for tenant extraction.

### Rationale
- `python-jose` is well-maintained and supports multiple algorithms
- FastAPI dependencies provide clean integration
- Can support both header-based and query-param tokens
- Existing observability patterns support tenant context binding

### Implementation Pattern
```python
from jose import jwt, JWTError

async def get_current_tenant(
    authorization: str = Header(..., alias="Authorization")
) -> TenantContext:
    token = authorization.replace("Bearer ", "")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return TenantContext(
        tenant_id=UUID(payload["tenant_id"]),
        user_id=payload.get("sub"),
        roles=payload.get("roles", []),
    )
```

### Alternatives Considered
- **FastAPI-Users**: Rejected - too opinionated, Focal handles auth upstream
- **Authlib**: Rejected - more complex, designed for OAuth flows we don't need

---

## 4. Rate Limiting Strategy

### Decision
Use sliding window counter algorithm with Redis storage for distributed rate limiting.

### Rationale
- Sliding window provides smoother rate limiting than fixed windows
- Redis enables distributed rate limiting across multiple pods
- Fallback to in-memory for development/testing
- Matches existing Redis usage pattern (session store)

### Implementation Pattern
```python
class SlidingWindowRateLimiter:
    async def check_rate_limit(
        self, tenant_id: UUID, tier: RateLimitTier
    ) -> RateLimitResult:
        key = f"rate:{tenant_id}:{window_start}"
        current = await redis.incr(key)
        await redis.expire(key, window_seconds)

        limit = TIER_LIMITS[tier]
        return RateLimitResult(
            allowed=current <= limit,
            limit=limit,
            remaining=max(0, limit - current),
            reset_at=window_end,
        )
```

### Tier Limits (from spec)
| Tier | Requests/min | Concurrent | Burst |
|------|--------------|------------|-------|
| Free | 60 | 5 | 10 |
| Pro | 600 | 50 | 50 |
| Enterprise | Custom | Custom | Custom |

### Alternatives Considered
- **Token bucket**: Rejected - more complex, sliding window sufficient for our scale
- **Fixed window**: Rejected - allows burst at window boundaries
- **Local-only limiting**: Rejected - doesn't work with horizontal scaling

---

## 5. Idempotency Implementation

### Decision
Use Redis with TTL for idempotency key storage, hash request body for cache key.

### Rationale
- 5-minute TTL matches spec requirement
- Redis provides atomic operations for race condition handling
- Request body hash prevents different requests with same key
- Graceful degradation when Redis unavailable

### Implementation Pattern
```python
class IdempotencyMiddleware:
    async def __call__(self, request: Request, call_next):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        cache_key = f"idem:{tenant_id}:{idempotency_key}"
        cached = await redis.get(cache_key)
        if cached:
            return JSONResponse(content=json.loads(cached))

        response = await call_next(request)
        await redis.setex(cache_key, 300, response.body)
        return response
```

### Cache Key Pattern
```
idem:{tenant_id}:{idempotency_key}
```

### Alternatives Considered
- **Database storage**: Rejected - Redis is faster for short-lived cache
- **Request hash as key**: Rejected - spec requires client-provided key

---

## 6. OpenTelemetry Integration

### Decision
Use existing `focal.observability` module with FastAPI instrumentation middleware.

### Rationale
- Focal already has OpenTelemetry setup in `observability/tracing.py`
- FastAPI has official OpenTelemetry instrumentation
- Trace context propagation via headers (W3C Trace Context)
- Consistent with existing pipeline step tracing

### Implementation Pattern
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def setup_tracing(app: FastAPI):
    FastAPIInstrumentor.instrument_app(app)
```

### Context Binding
Request context (tenant_id, agent_id, session_id, trace_id) bound via middleware:
```python
@app.middleware("http")
async def bind_context(request: Request, call_next):
    with structlog.contextvars.bind_contextvars(
        tenant_id=str(request.state.tenant_id),
        trace_id=get_trace_id(),
    ):
        return await call_next(request)
```

---

## 7. Error Handling

### Decision
Use FastAPI exception handlers with standardized ErrorResponse model.

### Rationale
- Consistent error format across all endpoints
- Maps internal exceptions to appropriate HTTP status codes
- Includes request context in error logs
- Matches error codes defined in spec

### Error Code Mapping
| Internal Exception | HTTP Status | Error Code |
|-------------------|-------------|------------|
| `ValidationError` | 400 | INVALID_REQUEST |
| `TenantNotFoundError` | 400 | TENANT_NOT_FOUND |
| `AgentNotFoundError` | 400 | AGENT_NOT_FOUND |
| `SessionNotFoundError` | 404 | SESSION_NOT_FOUND |
| `RuleViolationError` | 422 | RULE_VIOLATION |
| `ToolExecutionError` | 500 | TOOL_FAILED |
| `LLMProviderError` | 502 | LLM_ERROR |
| `RateLimitExceededError` | 429 | RATE_LIMIT_EXCEEDED |

---

## 8. Dependencies to Add

### Required (pyproject.toml)
```toml
dependencies = [
    # ... existing
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-jose[cryptography]>=3.3",
    "sse-starlette>=2.0",
    "httpx>=0.28",  # For async test client
]

[project.optional-dependencies]
api = [
    "redis>=5.0",  # For rate limiting and idempotency
]
```

### Development
```toml
dev = [
    # ... existing
    "httpx>=0.28",
    "pytest-httpx>=0.30",
]
```

---

## Summary

All technical decisions align with:
- Existing Focal patterns (DI, async-first, structured logging)
- Production best practices for FastAPI
- Spec requirements (SSE streaming, idempotency, rate limiting)
- Horizontal scaling requirements (stateless pods, Redis for shared state)
