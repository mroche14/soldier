"""Webhook subscription management API routes."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

from ruche.api.middleware.auth import TenantContextDep
from ruche.api.models.pagination import PaginatedResponse
from ruche.api.webhooks.models import WebhookStatus, WebhookSubscription
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# Request/Response models
class WebhookCreateRequest(BaseModel):
    """Request to create a webhook subscription."""

    url: HttpUrl = Field(description="HTTPS endpoint to receive webhooks")
    secret: str = Field(
        min_length=32, description="Secret for HMAC signing (min 32 chars)"
    )
    event_patterns: list[str] = Field(
        default=["*"], description="Event patterns to subscribe to"
    )
    agent_ids: list[UUID] | None = Field(
        default=None, description="Filter by agent IDs (None = all agents)"
    )
    name: str | None = Field(default=None, description="Friendly name")
    description: str | None = Field(default=None, description="Description")
    timeout_ms: int = Field(default=10000, ge=1000, le=60000)
    max_retries: int = Field(default=5, ge=0, le=10)


class WebhookUpdateRequest(BaseModel):
    """Request to update a webhook subscription."""

    url: HttpUrl | None = None
    secret: str | None = Field(default=None, min_length=32)
    event_patterns: list[str] | None = None
    agent_ids: list[UUID] | None = None
    name: str | None = None
    description: str | None = None
    status: WebhookStatus | None = None
    timeout_ms: int | None = Field(default=None, ge=1000, le=60000)
    max_retries: int | None = Field(default=None, ge=0, le=10)


class WebhookResponse(BaseModel):
    """Webhook subscription response."""

    id: UUID
    tenant_id: UUID
    url: HttpUrl
    event_patterns: list[str]
    agent_ids: list[UUID] | None
    status: WebhookStatus
    name: str | None
    description: str | None
    timeout_ms: int
    max_retries: int
    consecutive_failures: int
    last_success_at: str | None
    last_failure_at: str | None
    last_failure_reason: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_subscription(cls, sub: WebhookSubscription) -> "WebhookResponse":
        """Convert WebhookSubscription to response model."""
        return cls(
            id=sub.id,
            tenant_id=sub.tenant_id,
            url=sub.url,
            event_patterns=sub.event_patterns,
            agent_ids=sub.agent_ids,
            status=sub.status,
            name=sub.name,
            description=sub.description,
            timeout_ms=sub.timeout_ms,
            max_retries=sub.max_retries,
            consecutive_failures=sub.consecutive_failures,
            last_success_at=sub.last_success_at.isoformat() if sub.last_success_at else None,
            last_failure_at=sub.last_failure_at.isoformat() if sub.last_failure_at else None,
            last_failure_reason=sub.last_failure_reason,
            created_at=sub.created_at.isoformat(),
            updated_at=sub.updated_at.isoformat(),
        )


class WebhookCreateResponse(WebhookResponse):
    """Response after creating a webhook (includes secret once)."""

    secret: str = Field(description="Webhook secret (only shown on creation)")


# In-memory storage (temporary - should use ConfigStore in production)
_webhooks: dict[UUID, dict[UUID, WebhookSubscription]] = {}


@router.get("", response_model=PaginatedResponse[WebhookResponse])
async def list_webhooks(
    tenant_context: TenantContextDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: WebhookStatus | None = Query(default=None),
    agent_id: UUID | None = Query(default=None),
) -> PaginatedResponse[WebhookResponse]:
    """List webhook subscriptions for the tenant.

    Args:
        tenant_context: Authenticated tenant context
        limit: Maximum number of webhooks to return
        offset: Number of webhooks to skip
        status: Filter by status
        agent_id: Filter by agent ID

    Returns:
        Paginated list of webhook subscriptions
    """
    logger.debug(
        "list_webhooks_request",
        tenant_id=str(tenant_context.tenant_id),
        limit=limit,
        offset=offset,
        status=status,
        agent_id=str(agent_id) if agent_id else None,
    )

    # Get all webhooks for tenant
    tenant_webhooks = _webhooks.get(tenant_context.tenant_id, {})
    all_webhooks = list(tenant_webhooks.values())

    # Apply filters
    if status:
        all_webhooks = [w for w in all_webhooks if w.status == status]

    if agent_id:
        all_webhooks = [
            w
            for w in all_webhooks
            if w.agent_ids is None or agent_id in w.agent_ids
        ]

    # Sort by created_at desc
    all_webhooks.sort(key=lambda w: w.created_at, reverse=True)

    # Get total before pagination
    total = len(all_webhooks)

    # Apply pagination
    webhooks = all_webhooks[offset : offset + limit]

    # Map to response
    items = [WebhookResponse.from_subscription(w) for w in webhooks]

    return PaginatedResponse[WebhookResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(webhooks) < total,
    )


@router.post("", response_model=WebhookCreateResponse, status_code=201)
async def create_webhook(
    request: WebhookCreateRequest,
    tenant_context: TenantContextDep,
) -> WebhookCreateResponse:
    """Create a new webhook subscription.

    Args:
        request: Webhook creation request
        tenant_context: Authenticated tenant context

    Returns:
        Created webhook subscription (with secret)
    """
    logger.info(
        "create_webhook_request",
        tenant_id=str(tenant_context.tenant_id),
        url=str(request.url),
        event_patterns=request.event_patterns,
    )

    # Create subscription
    subscription = WebhookSubscription(
        tenant_id=tenant_context.tenant_id,
        url=request.url,
        secret=request.secret,
        event_patterns=request.event_patterns,
        agent_ids=request.agent_ids,
        name=request.name,
        description=request.description,
        timeout_ms=request.timeout_ms,
        max_retries=request.max_retries,
    )

    # Store in memory (temporary - should use ConfigStore)
    if tenant_context.tenant_id not in _webhooks:
        _webhooks[tenant_context.tenant_id] = {}
    _webhooks[tenant_context.tenant_id][subscription.id] = subscription

    logger.info(
        "webhook_created",
        tenant_id=str(tenant_context.tenant_id),
        webhook_id=str(subscription.id),
    )

    # Return with secret (only time it's exposed)
    response = WebhookResponse.from_subscription(subscription)
    return WebhookCreateResponse(**response.model_dump(), secret=subscription.secret)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    tenant_context: TenantContextDep,
) -> WebhookResponse:
    """Get a webhook subscription by ID.

    Args:
        webhook_id: Webhook subscription ID
        tenant_context: Authenticated tenant context

    Returns:
        Webhook subscription details
    """
    tenant_webhooks = _webhooks.get(tenant_context.tenant_id, {})
    subscription = tenant_webhooks.get(webhook_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse.from_subscription(subscription)


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    request: WebhookUpdateRequest,
    tenant_context: TenantContextDep,
) -> WebhookResponse:
    """Update a webhook subscription.

    Args:
        webhook_id: Webhook subscription ID
        request: Update request
        tenant_context: Authenticated tenant context

    Returns:
        Updated webhook subscription
    """
    tenant_webhooks = _webhooks.get(tenant_context.tenant_id, {})
    subscription = tenant_webhooks.get(webhook_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Update fields
    if request.url is not None:
        subscription.url = request.url
    if request.secret is not None:
        subscription.secret = request.secret
    if request.event_patterns is not None:
        subscription.event_patterns = request.event_patterns
    if request.agent_ids is not None:
        subscription.agent_ids = request.agent_ids
    if request.name is not None:
        subscription.name = request.name
    if request.description is not None:
        subscription.description = request.description
    if request.status is not None:
        subscription.status = request.status
    if request.timeout_ms is not None:
        subscription.timeout_ms = request.timeout_ms
    if request.max_retries is not None:
        subscription.max_retries = request.max_retries

    subscription.updated_at = datetime.utcnow()

    logger.info(
        "webhook_updated",
        tenant_id=str(tenant_context.tenant_id),
        webhook_id=str(webhook_id),
    )

    return WebhookResponse.from_subscription(subscription)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    tenant_context: TenantContextDep,
) -> None:
    """Delete a webhook subscription.

    Args:
        webhook_id: Webhook subscription ID
        tenant_context: Authenticated tenant context
    """
    tenant_webhooks = _webhooks.get(tenant_context.tenant_id, {})

    if webhook_id not in tenant_webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    del tenant_webhooks[webhook_id]

    logger.info(
        "webhook_deleted",
        tenant_id=str(tenant_context.tenant_id),
        webhook_id=str(webhook_id),
    )
