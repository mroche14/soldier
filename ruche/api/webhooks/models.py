"""Webhook subscription and delivery models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class WebhookStatus(str, Enum):
    """Subscription lifecycle states."""

    ACTIVE = "active"
    PAUSED = "paused"  # Manually paused by tenant
    DISABLED = "disabled"  # Auto-disabled after too many failures
    PENDING = "pending"  # Awaiting verification


class WebhookSubscription(BaseModel):
    """Tenant webhook subscription.

    Stored in ConfigStore, scoped to tenant.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    # Endpoint configuration
    url: HttpUrl
    secret: str  # Used to sign payloads (min 32 chars)

    # Event filtering
    event_patterns: list[str] = Field(default_factory=lambda: ["*"])
    """
    Patterns to filter events. Examples:
    - "*" → all events
    - "scenario.*" → all scenario events
    - "tool.execution.completed" → specific event
    - "infra.turn.*" → all turn lifecycle events
    """

    agent_ids: list[UUID] | None = None
    """If set, only events from these agents. None = all agents."""

    # Delivery settings
    status: WebhookStatus = WebhookStatus.PENDING
    timeout_ms: int = 10000  # 10 second default
    max_retries: int = 5

    # Metadata
    name: str | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Health tracking
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_failure_reason: str | None = None


class DeliveryStatus(str, Enum):
    """Delivery attempt states."""

    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXHAUSTED = "exhausted"  # All retries failed


class WebhookDelivery(BaseModel):
    """Record of a webhook delivery attempt.

    Stored in AuditStore for debugging and compliance.
    """

    id: UUID = Field(default_factory=uuid4)
    subscription_id: UUID
    tenant_id: UUID

    # Event reference
    event_id: UUID
    event_type: str  # e.g., "scenario.activated"

    # Delivery state
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_count: int = 0
    next_retry_at: datetime | None = None

    # Response tracking
    response_status_code: int | None = None
    response_body_preview: str | None = None  # First 500 chars
    response_time_ms: int | None = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: datetime | None = None

    # Error tracking
    last_error: str | None = None


class WebhookPayload(BaseModel):
    """Payload sent to tenant endpoint.

    Wraps AgentEvent with delivery metadata.
    """

    # Delivery metadata
    webhook_id: str  # Unique ID for this delivery (for deduplication)
    timestamp: datetime

    # Event data (from AgentEvent)
    event_type: str  # Full type: "scenario.activated"
    event_id: UUID

    # Routing context (from ACFEvent)
    tenant_id: UUID
    agent_id: UUID
    session_key: str
    logical_turn_id: UUID | None
    trace_id: str

    # Event payload (category-specific)
    payload: dict

    # Schema versioning
    schema_version: str = "1.0"
