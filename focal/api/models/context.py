"""Request context models for middleware and observability."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantContext(BaseModel):
    """Tenant context extracted from authentication.

    This is extracted from JWT claims by the auth middleware and made
    available throughout request processing.
    """

    tenant_id: UUID
    """Tenant identifier from JWT."""

    user_id: str | None = None
    """Optional user identifier from JWT 'sub' claim."""

    roles: list[str] = Field(default_factory=list)
    """User roles from JWT claims."""

    tier: Literal["free", "pro", "enterprise"] = "free"
    """Tenant tier for rate limiting and feature gating."""

    model_config = ConfigDict(frozen=True)


class RateLimitResult(BaseModel):
    """Result of a rate limit check.

    Returned by the rate limiter to indicate whether a request is allowed
    and to populate rate limit response headers.
    """

    allowed: bool
    """Whether the request is within rate limits."""

    limit: int
    """Maximum requests allowed in the window."""

    remaining: int
    """Remaining requests in the current window."""

    reset_at: datetime
    """When the rate limit window resets."""


class RequestContext(BaseModel):
    """Request context for observability and logging.

    Bound at the start of each request and used to correlate logs,
    traces, and metrics across the request lifecycle.
    """

    trace_id: str
    """OpenTelemetry trace ID."""

    span_id: str
    """OpenTelemetry span ID."""

    tenant_id: UUID | None = None
    """Tenant ID if authenticated."""

    agent_id: UUID | None = None
    """Agent ID if processing a chat request."""

    session_id: str | None = None
    """Session ID if in a conversation."""

    turn_id: str | None = None
    """Turn ID if processing a message."""

    request_id: str
    """Unique identifier for this request."""
