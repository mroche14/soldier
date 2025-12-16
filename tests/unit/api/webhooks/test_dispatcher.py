"""Unit tests for WebhookDispatcher HMAC signing and delivery."""

import hashlib
import hmac
import time
from datetime import datetime
from uuid import uuid4

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from ruche.api.webhooks.dispatcher import WebhookDispatcher, WebhookMatcher
from ruche.api.webhooks.models import WebhookPayload, WebhookStatus, WebhookSubscription


@pytest.fixture
def dispatcher() -> WebhookDispatcher:
    """Create webhook dispatcher."""
    return WebhookDispatcher()


@pytest.fixture
def subscription() -> WebhookSubscription:
    """Create sample webhook subscription."""
    return WebhookSubscription(
        id=uuid4(),
        tenant_id=uuid4(),
        url="https://example.com/webhook",
        secret="test-secret-key-must-be-32-chars-long",
        event_patterns=["*"],
        status=WebhookStatus.ACTIVE,
    )


@pytest.fixture
def payload() -> WebhookPayload:
    """Create sample webhook payload."""
    return WebhookPayload(
        webhook_id=str(uuid4()),
        timestamp=datetime.utcnow(),
        event_type="scenario.activated",
        event_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_key="tenant:agent:customer:web",
        logical_turn_id=uuid4(),
        trace_id="trace-123",
        payload={"scenario_id": str(uuid4()), "step_name": "start"},
    )


class TestSignPayload:
    """Tests for HMAC-SHA256 signature generation."""

    def test_sign_payload_generates_valid_signature(
        self, dispatcher: WebhookDispatcher
    ) -> None:
        """Generates valid HMAC-SHA256 signature."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        timestamp = int(time.time())

        signature = dispatcher.sign_payload(payload, secret, timestamp)

        assert signature.startswith("v1=")
        assert len(signature) > 3  # v1= plus hex

    def test_sign_payload_deterministic(self, dispatcher: WebhookDispatcher) -> None:
        """Same inputs produce same signature."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        timestamp = 1234567890

        sig1 = dispatcher.sign_payload(payload, secret, timestamp)
        sig2 = dispatcher.sign_payload(payload, secret, timestamp)

        assert sig1 == sig2

    def test_sign_payload_different_timestamp_different_signature(
        self, dispatcher: WebhookDispatcher
    ) -> None:
        """Different timestamps produce different signatures."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"

        sig1 = dispatcher.sign_payload(payload, secret, 1000)
        sig2 = dispatcher.sign_payload(payload, secret, 2000)

        assert sig1 != sig2

    def test_sign_payload_different_secret_different_signature(
        self, dispatcher: WebhookDispatcher
    ) -> None:
        """Different secrets produce different signatures."""
        payload = '{"test": "data"}'
        timestamp = 1234567890

        sig1 = dispatcher.sign_payload(payload, "secret1", timestamp)
        sig2 = dispatcher.sign_payload(payload, "secret2", timestamp)

        assert sig1 != sig2

    def test_sign_payload_different_payload_different_signature(
        self, dispatcher: WebhookDispatcher
    ) -> None:
        """Different payloads produce different signatures."""
        secret = "my-secret-key"
        timestamp = 1234567890

        sig1 = dispatcher.sign_payload('{"a": 1}', secret, timestamp)
        sig2 = dispatcher.sign_payload('{"a": 2}', secret, timestamp)

        assert sig1 != sig2

    def test_sign_payload_correct_format(self, dispatcher: WebhookDispatcher) -> None:
        """Signature has correct format."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        timestamp = 1234567890

        signature = dispatcher.sign_payload(payload, secret, timestamp)

        # Should be v1={64-char-hex}
        parts = signature.split("=")
        assert parts[0] == "v1"
        assert len(parts[1]) == 64  # SHA256 hex is 64 chars

    def test_sign_payload_verifiable(self, dispatcher: WebhookDispatcher) -> None:
        """Generated signature can be verified."""
        payload = '{"test": "data"}'
        secret = "my-secret-key"
        timestamp = 1234567890

        signature = dispatcher.sign_payload(payload, secret, timestamp)

        # Verify manually
        signed_payload = f"{timestamp}.{payload}"
        expected_hmac = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()

        assert signature == f"v1={expected_hmac}"


class TestDeliver:
    """Tests for webhook delivery."""

    async def test_deliver_skips_inactive_subscription(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Skips delivery for inactive subscriptions."""
        subscription.status = WebhookStatus.PAUSED

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "skipped"
        assert "not active" in result["reason"]

    async def test_deliver_sends_post_request(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Sends POST request to subscription URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert mock_client.post.called
        call_args = mock_client.post.call_args
        assert str(subscription.url) in str(call_args[0][0])

    async def test_deliver_includes_signature_header(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Includes X-Ruche-Signature header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        await dispatcher.deliver(subscription, payload)

        call_kwargs = mock_client.post.call_args[1]
        headers = call_kwargs["headers"]
        assert "X-Ruche-Signature" in headers
        assert headers["X-Ruche-Signature"].startswith("v1=")

    async def test_deliver_includes_metadata_headers(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Includes delivery metadata headers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        await dispatcher.deliver(subscription, payload)

        headers = mock_client.post.call_args[1]["headers"]
        assert "X-Ruche-Timestamp" in headers
        assert "X-Ruche-Delivery-Id" in headers
        assert "X-Ruche-Event-Type" in headers
        assert headers["X-Ruche-Event-Type"] == payload.event_type

    async def test_deliver_success_2xx_status(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """2xx status codes are considered success."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.text = "Created"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "delivered"
        assert result["status_code"] == 201

    async def test_deliver_client_error_4xx_no_retry(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """4xx status codes fail without retry."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "failed"
        assert result["status_code"] == 400
        assert result["retry"] is False

    async def test_deliver_server_error_5xx_with_retry(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """5xx status codes fail with retry."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "failed"
        assert result["status_code"] == 503
        assert result["retry"] is True

    async def test_deliver_timeout_with_retry(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Timeout errors trigger retry."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "failed"
        assert "Timeout" in result["error"]
        assert result["retry"] is True

    async def test_deliver_http_error_with_retry(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """HTTP errors trigger retry."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert result["status"] == "failed"
        assert result["retry"] is True

    async def test_deliver_respects_timeout(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Uses subscription timeout setting."""
        subscription.timeout_ms = 5000

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        await dispatcher.deliver(subscription, payload)

        timeout = mock_client.post.call_args[1]["timeout"]
        assert timeout == 5.0  # 5000ms = 5s

    async def test_deliver_records_response_time(
        self, dispatcher: WebhookDispatcher, subscription: WebhookSubscription, payload: WebhookPayload
    ) -> None:
        """Records response time in result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        dispatcher._client = mock_client

        result = await dispatcher.deliver(subscription, payload)

        assert "response_time_ms" in result
        assert result["response_time_ms"] >= 0


class TestClose:
    """Tests for client cleanup."""

    async def test_close_closes_http_client(self, dispatcher: WebhookDispatcher) -> None:
        """Closes HTTP client if it exists."""
        mock_client = AsyncMock()
        dispatcher._client = mock_client

        await dispatcher.close()

        mock_client.aclose.assert_called_once()
        assert dispatcher._client is None

    async def test_close_when_no_client(self, dispatcher: WebhookDispatcher) -> None:
        """Doesn't error when no client exists."""
        await dispatcher.close()


class TestWebhookMatcher:
    """Tests for webhook pattern matching."""

    @pytest.fixture
    def matcher(self) -> WebhookMatcher:
        """Create webhook matcher."""
        return WebhookMatcher()

    def test_matches_pattern_wildcard_all(self, matcher: WebhookMatcher) -> None:
        """Wildcard '*' matches all events."""
        assert matcher.matches_pattern("scenario.activated", ["*"])
        assert matcher.matches_pattern("tool.execution.completed", ["*"])

    def test_matches_pattern_exact_match(self, matcher: WebhookMatcher) -> None:
        """Exact pattern matches event."""
        assert matcher.matches_pattern("scenario.activated", ["scenario.activated"])

    def test_matches_pattern_exact_no_match(self, matcher: WebhookMatcher) -> None:
        """Exact pattern doesn't match different event."""
        assert not matcher.matches_pattern("scenario.activated", ["scenario.completed"])

    def test_matches_pattern_prefix_wildcard(self, matcher: WebhookMatcher) -> None:
        """Prefix wildcard matches category."""
        assert matcher.matches_pattern("scenario.activated", ["scenario.*"])
        assert matcher.matches_pattern("scenario.completed", ["scenario.*"])

    def test_matches_pattern_prefix_no_match(self, matcher: WebhookMatcher) -> None:
        """Prefix wildcard doesn't match different category."""
        assert not matcher.matches_pattern("tool.executed", ["scenario.*"])

    def test_matches_pattern_multiple_patterns(self, matcher: WebhookMatcher) -> None:
        """Matches if any pattern matches."""
        patterns = ["scenario.*", "tool.executed"]
        assert matcher.matches_pattern("scenario.activated", patterns)
        assert matcher.matches_pattern("tool.executed", patterns)
        assert not matcher.matches_pattern("turn.started", patterns)

    def test_matches_subscription_active_status(
        self, matcher: WebhookMatcher, subscription: WebhookSubscription
    ) -> None:
        """Only matches active subscriptions."""
        subscription.status = WebhookStatus.ACTIVE
        assert matcher.matches_subscription("scenario.activated", str(uuid4()), subscription)

        subscription.status = WebhookStatus.PAUSED
        assert not matcher.matches_subscription("scenario.activated", str(uuid4()), subscription)

    def test_matches_subscription_agent_filter(
        self, matcher: WebhookMatcher, subscription: WebhookSubscription
    ) -> None:
        """Filters by agent ID if specified."""
        agent_id = uuid4()
        subscription.agent_ids = [agent_id]

        assert matcher.matches_subscription("scenario.activated", str(agent_id), subscription)
        assert not matcher.matches_subscription("scenario.activated", str(uuid4()), subscription)

    def test_matches_subscription_no_agent_filter(
        self, matcher: WebhookMatcher, subscription: WebhookSubscription
    ) -> None:
        """No agent filter matches all agents."""
        subscription.agent_ids = None

        assert matcher.matches_subscription("scenario.activated", str(uuid4()), subscription)

    def test_matches_subscription_event_pattern(
        self, matcher: WebhookMatcher, subscription: WebhookSubscription
    ) -> None:
        """Matches based on event patterns."""
        subscription.event_patterns = ["scenario.*"]

        assert matcher.matches_subscription("scenario.activated", str(uuid4()), subscription)
        assert not matcher.matches_subscription("tool.executed", str(uuid4()), subscription)
