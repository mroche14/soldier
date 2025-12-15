# Webhook System Specification

> **Status**: PROPOSED
> **Date**: 2025-12-15
> **Scope**: Event delivery to tenant systems
> **Dependencies**: Event Model (`event-model.md`), API Layer (`api-layer.md`), Hatchet (workflow orchestration)

---

## Executive Summary

The Webhook System delivers platform events to tenant-owned HTTP endpoints. It extends the internal `AgentEvent` / `ACFEvent` model to external subscribers with guaranteed delivery, security signatures, and durable retry via Hatchet.

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Push-based delivery** | Tenants don't need to poll; events delivered as they happen |
| **At-least-once semantics** | Industry standard for webhooks; tenants handle duplicates via `webhook_id` |
| **Hatchet-based delivery** | Leverage existing infrastructure; durable retries without custom queue |
| **HMAC-SHA256 signatures** | Cryptographic proof that payload came from Ruche |
| **Subscription filtering** | Tenants only receive events they care about |

**Why At-Least-Once?** Exactly-once would require tracking delivery state for every event indefinitely. At-least-once is simpler, industry-standard (Stripe, GitHub, Twilio), and tenants already expect to deduplicate via `webhook_id`.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Event Sources                                    │
│  (ACF, Brain, Toolbox emit AgentEvents via ctx.emit_event())            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ACF EventRouter                                  │
│                                                                          │
│  Routes ACFEvent to:                                                     │
│  ├── AuditStore (all events)                                            │
│  ├── Metrics (counters)                                                  │
│  ├── Live UI (SSE streams)                                              │
│  └── WebhookDispatcher (tenant subscriptions) ◄─── THIS SPEC           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       WebhookDispatcher                                  │
│                                                                          │
│  1. Match event to tenant subscriptions                                  │
│  2. Filter by event patterns                                             │
│  3. Trigger Hatchet workflow (fire-and-forget)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Hatchet: WebhookDeliveryWorkflow                      │
│                                                                          │
│  - Sign payload with tenant secret                                       │
│  - POST to tenant endpoint                                               │
│  - Retry with exponential backoff (built-in)                            │
│  - on_failure: increment subscription failure count                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Tenant Endpoints                                   │
│                                                                          │
│  POST https://tenant-a.com/webhooks/ruche                               │
│  POST https://tenant-b.com/api/events                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Models

### 2.1 WebhookSubscription

```python
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class WebhookStatus(str, Enum):
    """Subscription lifecycle states."""
    ACTIVE = "active"
    PAUSED = "paused"         # Manually paused by tenant
    DISABLED = "disabled"     # Auto-disabled after too many failures
    PENDING = "pending"       # Awaiting verification


class WebhookSubscription(BaseModel):
    """
    Tenant webhook subscription.

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
```

### 2.2 WebhookDelivery

```python
class DeliveryStatus(str, Enum):
    """Delivery attempt states."""
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXHAUSTED = "exhausted"  # All retries failed


class WebhookDelivery(BaseModel):
    """
    Record of a webhook delivery attempt.

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
```

### 2.3 WebhookPayload

```python
class WebhookPayload(BaseModel):
    """
    Payload sent to tenant endpoint.

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
```

---

## 3. Subscription Management API

### 3.1 Endpoints

```
POST   /v1/webhooks                    # Create subscription
GET    /v1/webhooks                    # List subscriptions
GET    /v1/webhooks/{id}               # Get subscription
PATCH  /v1/webhooks/{id}               # Update subscription
DELETE /v1/webhooks/{id}               # Delete subscription
POST   /v1/webhooks/{id}/verify        # Trigger verification
POST   /v1/webhooks/{id}/test          # Send test event
GET    /v1/webhooks/{id}/deliveries    # List delivery history
```

### 3.2 Create Subscription

```json
POST /v1/webhooks
Authorization: Bearer {jwt}

{
  "url": "https://example.com/webhooks/ruche",
  "secret": "whsec_a1b2c3d4e5f6...",
  "event_patterns": ["scenario.*", "tool.execution.*"],
  "agent_ids": ["uuid-1", "uuid-2"],
  "name": "Production webhook",
  "timeout_ms": 15000,
  "max_retries": 3
}

Response:
{
  "id": "webhook_uuid",
  "status": "pending",
  "verification_token": "verify_abc123...",
  "created_at": "2025-12-15T10:00:00Z"
}
```

### 3.3 Verification Flow

Subscriptions start in `pending` status. Tenants must verify ownership:

```python
# Option 1: Challenge-response (recommended)
POST https://example.com/webhooks/ruche
X-Ruche-Verification: verify_abc123...

# Tenant must respond with:
{
  "challenge": "verify_abc123..."
}

# Option 2: Manual verification
POST /v1/webhooks/{id}/verify
{
  "verification_code": "code_from_dashboard"
}
```

---

## 4. Payload Signing

### 4.1 Signature Generation

All webhook payloads are signed using HMAC-SHA256:

```python
import hmac
import hashlib
import time

def sign_payload(payload: str, secret: str, timestamp: int) -> str:
    """
    Generate signature for webhook payload.

    Args:
        payload: JSON-encoded payload string
        secret: Tenant's webhook secret
        timestamp: Unix timestamp (seconds)

    Returns:
        Signature string: "v1={hmac_hex}"
    """
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"v1={signature}"
```

### 4.2 Request Headers

```http
POST https://example.com/webhooks/ruche
Content-Type: application/json
X-Ruche-Signature: v1=5d41402abc4b2a76b9719d911017c592...
X-Ruche-Timestamp: 1734264000
X-Ruche-Delivery-Id: del_abc123...
X-Ruche-Event-Type: scenario.activated
User-Agent: Ruche-Webhook/1.0
```

### 4.3 Signature Verification (Tenant Side)

```python
def verify_signature(
    payload: str,
    signature_header: str,
    timestamp_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify webhook signature.

    Args:
        payload: Raw request body
        signature_header: X-Ruche-Signature header value
        timestamp_header: X-Ruche-Timestamp header value
        secret: Webhook secret
        tolerance_seconds: Max age of request (prevents replay)

    Returns:
        True if signature is valid
    """
    # Check timestamp freshness (prevent replay attacks)
    timestamp = int(timestamp_header)
    if abs(time.time() - timestamp) > tolerance_seconds:
        return False

    # Extract signature
    if not signature_header.startswith("v1="):
        return False
    expected_sig = signature_header[3:]

    # Compute expected signature
    signed_payload = f"{timestamp}.{payload}"
    computed_sig = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected_sig, computed_sig)
```

---

## 5. Delivery Logic (Hatchet-Based)

### 5.1 Event Matching

```python
class WebhookMatcher:
    """Match events to subscriptions."""

    def matches(
        self,
        event: ACFEvent,
        subscription: WebhookSubscription,
    ) -> bool:
        """Check if event matches subscription filters."""

        # Check subscription status
        if subscription.status != WebhookStatus.ACTIVE:
            return False

        # Check tenant match
        if event.tenant_id != subscription.tenant_id:
            return False

        # Check agent filter
        if subscription.agent_ids is not None:
            if event.agent_id not in subscription.agent_ids:
                return False

        # Check event pattern
        return self._matches_patterns(
            event.event.full_type,
            subscription.event_patterns,
        )

    def _matches_patterns(
        self,
        event_type: str,
        patterns: list[str],
    ) -> bool:
        """Check if event type matches any pattern."""
        for pattern in patterns:
            if pattern == "*":
                return True
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix + "."):
                    return True
            elif pattern == event_type:
                return True
        return False
```

### 5.2 Hatchet Workflow for Delivery

Webhook delivery uses Hatchet for durable execution with built-in retries:

```python
@hatchet.workflow()
class WebhookDeliveryWorkflow:
    """
    Durable webhook delivery via Hatchet.

    Benefits over custom implementation:
    - Built-in retry with exponential backoff
    - Durable execution (survives service restarts)
    - Observability via Hatchet dashboard
    - No custom queue infrastructure needed
    """

    @hatchet.step(
        retries=5,
        backoff="exponential",
        backoff_factor=2,
        initial_backoff_seconds=10,
        max_backoff_seconds=3600,
    )
    async def deliver(self, ctx: Context) -> dict:
        """Deliver webhook payload to tenant endpoint."""
        subscription = WebhookSubscription(**ctx.workflow_input()["subscription"])
        payload = WebhookPayload(**ctx.workflow_input()["payload"])

        # Sign payload
        timestamp = int(datetime.utcnow().timestamp())
        payload_json = payload.model_dump_json()
        signature = self._sign_payload(payload_json, subscription.secret, timestamp)

        # Deliver
        async with httpx.AsyncClient() as client:
            response = await client.post(
                str(subscription.url),
                content=payload_json,
                headers={
                    "Content-Type": "application/json",
                    "X-Ruche-Signature": signature,
                    "X-Ruche-Timestamp": str(timestamp),
                    "X-Ruche-Delivery-Id": str(payload.webhook_id),
                    "X-Ruche-Event-Type": payload.event_type,
                    "User-Agent": "Ruche-Webhook/1.0",
                },
                timeout=subscription.timeout_ms / 1000,
            )

        # 2xx = success
        if 200 <= response.status_code < 300:
            await self._record_success(subscription.id)
            return {
                "status": "delivered",
                "status_code": response.status_code,
            }

        # 4xx = client error, don't retry
        if 400 <= response.status_code < 500:
            raise NonRetryableError(
                f"Client error: {response.status_code} - {response.text[:200]}"
            )

        # 5xx = server error, retry
        raise RetryableError(
            f"Server error: {response.status_code} - {response.text[:200]}"
        )

    @hatchet.on_failure()
    async def handle_exhausted(self, ctx: Context):
        """Called after all retries exhausted."""
        subscription_id = ctx.workflow_input()["subscription"]["id"]

        # Increment failure count
        subscription = await self._config_store.get_webhook(subscription_id)
        subscription.consecutive_failures += 1
        subscription.last_failure_at = datetime.utcnow()
        subscription.last_failure_reason = ctx.failure_reason()

        # Auto-disable after threshold
        if subscription.consecutive_failures >= 10:
            subscription.status = WebhookStatus.DISABLED
            logger.warning(
                "webhook_subscription_disabled",
                subscription_id=str(subscription_id),
                consecutive_failures=subscription.consecutive_failures,
            )

        await self._config_store.save_webhook(subscription)

    async def _record_success(self, subscription_id: UUID) -> None:
        """Reset failure count on success."""
        subscription = await self._config_store.get_webhook(subscription_id)
        subscription.consecutive_failures = 0
        subscription.last_success_at = datetime.utcnow()
        await self._config_store.save_webhook(subscription)

    def _sign_payload(self, payload: str, secret: str, timestamp: int) -> str:
        """Generate HMAC-SHA256 signature."""
        signed_payload = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"v1={signature}"
```

### 5.3 Dispatching from EventRouter

```python
class WebhookDispatcher:
    """Dispatch webhooks via Hatchet workflows."""

    def __init__(self, hatchet: Hatchet, config_store: ConfigStore):
        self._hatchet = hatchet
        self._config_store = config_store
        self._matcher = WebhookMatcher()

    async def dispatch(self, event: ACFEvent) -> None:
        """
        Match event to subscriptions and trigger delivery workflows.

        This is fire-and-forget; Hatchet handles retries durably.
        """
        subscriptions = await self._config_store.get_webhooks_for_tenant(
            event.tenant_id
        )

        for sub in subscriptions:
            if not self._matcher.matches(event, sub):
                continue

            payload = WebhookPayload(
                webhook_id=str(uuid4()),
                timestamp=datetime.utcnow(),
                event_type=event.event.full_type,
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                agent_id=event.agent_id,
                session_key=event.session_key,
                logical_turn_id=event.logical_turn_id,
                trace_id=event.trace_id,
                payload=event.event.payload,
            )

            # Fire-and-forget to Hatchet
            await self._hatchet.workflow("webhook_delivery").trigger({
                "subscription": sub.model_dump(mode="json"),
                "payload": payload.model_dump(mode="json"),
            })

            logger.info(
                "webhook_delivery_triggered",
                subscription_id=str(sub.id),
                event_type=event.event.full_type,
                webhook_id=payload.webhook_id,
            )
```

### 5.4 Why Hatchet?

| Aspect | Custom Queue | Hatchet |
|--------|--------------|---------|
| **Infrastructure** | Redis/Postgres queue + workers | Already have it for ACF |
| **Retry logic** | Build exponential backoff | Declarative config |
| **Durability** | Must handle crashes | Built-in |
| **Observability** | Build dashboard | Hatchet UI |
| **Dead letter** | Build it | `on_failure` handler |
| **Scaling** | Manage worker pools | Hatchet manages |

---

## 6. Event Payload Examples

### 6.1 Scenario Activated

```json
{
  "webhook_id": "del_abc123",
  "timestamp": "2025-12-15T10:30:00Z",
  "event_type": "scenario.activated",
  "event_id": "evt_xyz789",
  "tenant_id": "tenant_uuid",
  "agent_id": "agent_uuid",
  "session_key": "tenant:agent:customer:whatsapp",
  "logical_turn_id": "turn_uuid",
  "trace_id": "trace_abc",
  "payload": {
    "scenario_id": "returns_flow",
    "scenario_name": "Product Returns",
    "entry_step": "greeting",
    "trigger": "user_intent"
  },
  "schema_version": "1.0"
}
```

### 6.2 Tool Execution Completed

```json
{
  "webhook_id": "del_def456",
  "timestamp": "2025-12-15T10:30:05Z",
  "event_type": "infra.tool.completed",
  "event_id": "evt_tool123",
  "tenant_id": "tenant_uuid",
  "agent_id": "agent_uuid",
  "session_key": "tenant:agent:customer:whatsapp",
  "logical_turn_id": "turn_uuid",
  "trace_id": "trace_abc",
  "payload": {
    "tool_name": "create_refund",
    "tool_id": "tool_uuid",
    "side_effect_policy": "irreversible",
    "execution_time_ms": 234,
    "result_summary": "Refund #12345 created for $50.00",
    "idempotency_key": "refund:order:12345:turn_group:xyz"
  },
  "schema_version": "1.0"
}
```

### 6.3 Policy Blocked

```json
{
  "webhook_id": "del_ghi789",
  "timestamp": "2025-12-15T10:30:10Z",
  "event_type": "policy.blocked",
  "event_id": "evt_policy456",
  "tenant_id": "tenant_uuid",
  "agent_id": "agent_uuid",
  "session_key": "tenant:agent:customer:whatsapp",
  "logical_turn_id": "turn_uuid",
  "trace_id": "trace_abc",
  "payload": {
    "policy_name": "max_refund_amount",
    "blocked_action": "approve_refund",
    "reason": "Amount $500 exceeds policy limit of $100",
    "escalation_required": true
  },
  "schema_version": "1.0"
}
```

---

## 7. Configuration

```toml
[webhooks]
enabled = true

# Delivery settings (Hatchet workflow config)
default_timeout_ms = 10000
max_payload_size_bytes = 65536  # 64KB

# Hatchet retry settings (applied to WebhookDeliveryWorkflow)
max_retries = 5
initial_backoff_seconds = 10
max_backoff_seconds = 3600
backoff_factor = 2

# Health settings
failure_threshold = 10  # Auto-disable after N consecutive failures

# Security
require_https = true  # Production: must be HTTPS
signature_tolerance_seconds = 300  # 5 minute replay window

# Rate limiting (per subscription)
max_deliveries_per_minute = 1000
```

---

## 8. Observability

### 8.1 Metrics

```python
# Delivery metrics
webhook_deliveries_total = Counter(
    "webhook_deliveries_total",
    "Webhook deliveries by status",
    ["tenant_id", "status"],  # delivered, failed, exhausted
)

webhook_delivery_latency = Histogram(
    "webhook_delivery_latency_seconds",
    "Webhook delivery latency",
    ["tenant_id"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

webhook_retry_count = Histogram(
    "webhook_retry_count",
    "Retries before successful delivery",
    ["tenant_id"],
    buckets=[0, 1, 2, 3, 4, 5],
)

# Health metrics
webhook_subscriptions_by_status = Gauge(
    "webhook_subscriptions_by_status",
    "Subscriptions by status",
    ["status"],  # active, paused, disabled
)
```

### 8.2 Structured Logging

```python
logger.info(
    "webhook_delivered",
    delivery_id=str(delivery.id),
    subscription_id=str(subscription.id),
    event_type=event.full_type,
    response_time_ms=response_time,
    attempt=delivery.attempt_count,
)

logger.warning(
    "webhook_delivery_failed",
    delivery_id=str(delivery.id),
    subscription_id=str(subscription.id),
    event_type=event.full_type,
    error=error_message,
    will_retry=will_retry,
    next_retry_at=next_retry_at,
)

logger.error(
    "webhook_subscription_disabled",
    subscription_id=str(subscription.id),
    tenant_id=str(subscription.tenant_id),
    consecutive_failures=subscription.consecutive_failures,
    reason="exceeded_failure_threshold",
)
```

---

## 9. Security Considerations

### 9.1 Secret Management

- Webhook secrets are stored encrypted in ConfigStore
- Minimum 32 character requirement
- Secrets are never logged or returned in API responses (except on creation)
- Rotation: Tenants can update secret; in-flight deliveries use old secret until confirmed

### 9.2 Endpoint Validation

- HTTPS required in production
- No localhost/private IP endpoints in production
- DNS resolution validated before enabling subscription

### 9.3 Payload Security

- PII is NOT included in webhook payloads by default
- Sensitive fields (e.g., customer email) require explicit opt-in
- Payloads are sanitized to remove internal identifiers

### 9.4 Replay Protection

- Timestamp included in signature
- 5-minute tolerance window
- Tenants should track `webhook_id` to detect duplicates

---

## 10. Implementation Notes

### 10.1 Async Delivery

Webhook delivery MUST NOT block turn processing:

```python
async def route_event(self, event: ACFEvent) -> None:
    """Route event to all destinations."""

    # Synchronous destinations (fast)
    await self._audit_store.save(event)
    self._metrics.record(event)

    # Async destinations (don't block)
    asyncio.create_task(self._dispatch_webhooks(event))
```

### 10.2 Delivery Queue

Use a persistent queue (Redis, PostgreSQL, or Hatchet) for reliable delivery:

```python
# Enqueue for delivery
await self._delivery_queue.enqueue(
    WebhookDeliveryJob(
        delivery_id=delivery.id,
        subscription_id=subscription.id,
        payload=payload.model_dump(),
        retry_at=datetime.utcnow(),
    )
)

# Worker processes deliveries
async def process_delivery_job(job: WebhookDeliveryJob):
    delivery = await self._get_delivery(job.delivery_id)
    subscription = await self._get_subscription(job.subscription_id)

    status = await self._dispatcher.deliver(delivery, subscription, job.payload)

    if status == DeliveryStatus.PENDING:
        # Re-enqueue for retry
        await self._delivery_queue.enqueue(job, delay=compute_retry_delay(delivery))
```

---

## 11. Future Considerations

### 11.1 Batch Delivery

For high-volume tenants, batch multiple events into single delivery:

```json
{
  "batch_id": "batch_123",
  "events": [
    { "event_type": "...", "payload": {...} },
    { "event_type": "...", "payload": {...} }
  ]
}
```

### 11.2 Fan-out Optimization

For tenants with multiple subscriptions matching same event, deduplicate payload signing.

### 11.3 Dead Letter Queue

Events that exhaust all retries go to a dead letter queue for manual inspection.

---

## References

- [Event Model Specification](event-model.md) - AgentEvent / ACFEvent definitions
- [API Layer](api-layer.md) - REST API patterns
- [ACF Specification](../acf/architecture/ACF_SPEC.md) - Event routing architecture
- [Stripe Webhooks](https://stripe.com/docs/webhooks) - Industry reference
