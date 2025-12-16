"""Webhook delivery dispatcher with HMAC signing."""

import hashlib
import hmac
import time
from datetime import datetime
from uuid import uuid4

import httpx

from ruche.api.webhooks.models import (
    WebhookPayload,
    WebhookStatus,
    WebhookSubscription,
)
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class WebhookDispatcher:
    """Dispatch webhooks with HMAC-SHA256 signatures.

    Handles payload signing and HTTP delivery with retry logic.
    """

    def __init__(self) -> None:
        """Initialize dispatcher."""
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    def sign_payload(self, payload: str, secret: str, timestamp: int) -> str:
        """Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON-encoded payload string
            secret: Tenant's webhook secret
            timestamp: Unix timestamp (seconds)

        Returns:
            Signature string: "v1={hmac_hex}"
        """
        signed_payload = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        return f"v1={signature}"

    async def deliver(
        self,
        subscription: WebhookSubscription,
        payload: WebhookPayload,
    ) -> dict:
        """Deliver webhook payload to tenant endpoint.

        Args:
            subscription: Webhook subscription configuration
            payload: Event payload to send

        Returns:
            Delivery result with status and response details
        """
        if subscription.status != WebhookStatus.ACTIVE:
            logger.warning(
                "webhook_skipped_inactive",
                subscription_id=str(subscription.id),
                status=subscription.status,
            )
            return {
                "status": "skipped",
                "reason": f"subscription not active: {subscription.status}",
            }

        # Sign payload
        timestamp = int(datetime.utcnow().timestamp())
        payload_json = payload.model_dump_json()
        signature = self.sign_payload(payload_json, subscription.secret, timestamp)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Ruche-Signature": signature,
            "X-Ruche-Timestamp": str(timestamp),
            "X-Ruche-Delivery-Id": payload.webhook_id,
            "X-Ruche-Event-Type": payload.event_type,
            "User-Agent": "Ruche-Webhook/1.0",
        }

        logger.info(
            "webhook_delivery_attempt",
            subscription_id=str(subscription.id),
            event_type=payload.event_type,
            webhook_id=payload.webhook_id,
            url=str(subscription.url),
        )

        try:
            client = await self._ensure_client()
            start_time = time.time()

            response = await client.post(
                str(subscription.url),
                content=payload_json,
                headers=headers,
                timeout=subscription.timeout_ms / 1000,
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # 2xx = success
            if 200 <= response.status_code < 300:
                logger.info(
                    "webhook_delivered",
                    subscription_id=str(subscription.id),
                    event_type=payload.event_type,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                )

                return {
                    "status": "delivered",
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms,
                    "response_preview": response.text[:500] if response.text else None,
                }

            # 4xx = client error, don't retry
            if 400 <= response.status_code < 500:
                logger.warning(
                    "webhook_client_error",
                    subscription_id=str(subscription.id),
                    status_code=response.status_code,
                    response_preview=response.text[:200],
                )

                return {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": f"Client error: {response.status_code}",
                    "retry": False,
                }

            # 5xx = server error, should retry
            logger.warning(
                "webhook_server_error",
                subscription_id=str(subscription.id),
                status_code=response.status_code,
                response_preview=response.text[:200],
            )

            return {
                "status": "failed",
                "status_code": response.status_code,
                "error": f"Server error: {response.status_code}",
                "retry": True,
            }

        except httpx.TimeoutException as e:
            logger.warning(
                "webhook_timeout",
                subscription_id=str(subscription.id),
                timeout_ms=subscription.timeout_ms,
            )

            return {
                "status": "failed",
                "error": f"Timeout after {subscription.timeout_ms}ms",
                "retry": True,
            }

        except httpx.HTTPError as e:
            logger.error(
                "webhook_http_error",
                subscription_id=str(subscription.id),
                error=str(e),
            )

            return {
                "status": "failed",
                "error": str(e),
                "retry": True,
            }

        except Exception as e:
            logger.error(
                "webhook_delivery_failed",
                subscription_id=str(subscription.id),
                error=str(e),
                error_type=type(e).__name__,
            )

            return {
                "status": "failed",
                "error": str(e),
                "retry": False,
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class WebhookMatcher:
    """Match events to webhook subscriptions."""

    def matches_pattern(self, event_type: str, patterns: list[str]) -> bool:
        """Check if event type matches any pattern.

        Args:
            event_type: Full event type (e.g., "scenario.activated")
            patterns: List of patterns to match against

        Returns:
            True if event matches any pattern
        """
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

    def matches_subscription(
        self,
        event_type: str,
        event_agent_id: str,
        subscription: WebhookSubscription,
    ) -> bool:
        """Check if event matches subscription filters.

        Args:
            event_type: Full event type
            event_agent_id: Agent ID from event
            subscription: Webhook subscription to check

        Returns:
            True if event should be sent to this subscription
        """
        # Check subscription status
        if subscription.status != WebhookStatus.ACTIVE:
            return False

        # Check agent filter
        if subscription.agent_ids is not None:
            if event_agent_id not in [str(aid) for aid in subscription.agent_ids]:
                return False

        # Check event pattern
        return self.matches_pattern(event_type, subscription.event_patterns)
