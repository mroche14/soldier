"""Tests for TurnGateway and ActiveTurnIndex."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ruche.runtime.acf.gateway import (
    ActiveTurnIndex,
    RawMessage,
    TurnAction,
    TurnDecision,
    TurnGateway,
)


class TestRawMessage:
    """Tests for RawMessage model."""

    def test_create_raw_message(self):
        """Should create a raw message."""
        message = RawMessage(
            content="Hello",
            message_id="msg-123",
            timestamp="2024-01-01T00:00:00Z",
            metadata={"channel": "whatsapp"},
        )

        assert message.content == "Hello"
        assert message.message_id == "msg-123"
        assert message.timestamp == "2024-01-01T00:00:00Z"
        assert message.metadata["channel"] == "whatsapp"

    def test_raw_message_default_metadata(self):
        """Should default metadata to empty dict."""
        message = RawMessage(content="Hello", message_id="msg-123")

        assert message.metadata == {}
        assert message.timestamp is None


class TestTurnDecision:
    """Tests for TurnDecision model."""

    def test_trigger_new_decision(self):
        """Should create a trigger_new decision."""
        decision = TurnDecision(action=TurnAction.TRIGGER_NEW)

        assert decision.action == TurnAction.TRIGGER_NEW
        assert decision.workflow_id is None
        assert decision.reason is None

    def test_signal_existing_decision(self):
        """Should create a signal_existing decision with workflow_id."""
        decision = TurnDecision(
            action=TurnAction.SIGNAL_EXISTING, workflow_id="workflow-123"
        )

        assert decision.action == TurnAction.SIGNAL_EXISTING
        assert decision.workflow_id == "workflow-123"

    def test_reject_decision_with_reason(self):
        """Should create a reject decision with reason."""
        decision = TurnDecision(
            action=TurnAction.REJECT, reason="Rate limit exceeded"
        )

        assert decision.action == TurnAction.REJECT
        assert decision.reason == "Rate limit exceeded"

    def test_queue_decision_with_position(self):
        """Should create a queue decision with position."""
        decision = TurnDecision(action=TurnAction.QUEUE, queue_position=5)

        assert decision.action == TurnAction.QUEUE
        assert decision.queue_position == 5


class TestActiveTurnIndex:
    """Tests for ActiveTurnIndex."""

    @pytest.fixture
    def index(self):
        """Create an index without Redis (local cache fallback)."""
        return ActiveTurnIndex(redis_client=None)

    @pytest.fixture
    def redis_mock(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        return mock

    @pytest.fixture
    def redis_index(self, redis_mock):
        """Create an index with Redis."""
        return ActiveTurnIndex(redis_client=redis_mock)

    @pytest.mark.asyncio
    async def test_get_workflow_id_not_found(self, index):
        """Should return None when workflow ID not found."""
        workflow_id = await index.get_workflow_id("session-123")
        assert workflow_id is None

    @pytest.mark.asyncio
    async def test_set_and_get_workflow_id(self, index):
        """Should store and retrieve workflow ID."""
        session_key = "session-123"
        workflow_id = "workflow-456"

        await index.set_workflow_id(session_key, workflow_id)
        result = await index.get_workflow_id(session_key)

        assert result == workflow_id

    @pytest.mark.asyncio
    async def test_clear_workflow_id(self, index):
        """Should clear workflow ID."""
        session_key = "session-123"
        workflow_id = "workflow-456"

        await index.set_workflow_id(session_key, workflow_id)
        await index.clear_workflow_id(session_key)
        result = await index.get_workflow_id(session_key)

        assert result is None

    @pytest.mark.asyncio
    async def test_set_workflow_id_with_redis(self, redis_index, redis_mock):
        """Should set workflow ID in Redis."""
        session_key = "session-123"
        workflow_id = "workflow-456"

        await redis_index.set_workflow_id(session_key, workflow_id, ttl_seconds=300)

        redis_mock.set.assert_called_once_with(
            "active_turn:session-123", "workflow-456", ex=300
        )

    @pytest.mark.asyncio
    async def test_get_workflow_id_from_redis(self, redis_index, redis_mock):
        """Should get workflow ID from Redis."""
        redis_mock.get.return_value = "workflow-789"

        result = await redis_index.get_workflow_id("session-123")

        redis_mock.get.assert_called_once_with("active_turn:session-123")
        assert result == "workflow-789"

    @pytest.mark.asyncio
    async def test_clear_workflow_id_from_redis(self, redis_index, redis_mock):
        """Should clear workflow ID from Redis."""
        await redis_index.clear_workflow_id("session-123")

        redis_mock.delete.assert_called_once_with("active_turn:session-123")

    @pytest.mark.asyncio
    async def test_local_cache_isolation(self, index):
        """Should isolate different session keys in local cache."""
        await index.set_workflow_id("session-1", "workflow-1")
        await index.set_workflow_id("session-2", "workflow-2")

        result1 = await index.get_workflow_id("session-1")
        result2 = await index.get_workflow_id("session-2")

        assert result1 == "workflow-1"
        assert result2 == "workflow-2"


class TestTurnGateway:
    """Tests for TurnGateway."""

    @pytest.fixture
    def active_turn_index(self):
        """Create an active turn index."""
        return ActiveTurnIndex(redis_client=None)

    @pytest.fixture
    def rate_limiter(self):
        """Create a mock rate limiter."""
        mock = AsyncMock()
        mock.check = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def gateway(self, active_turn_index, rate_limiter):
        """Create a turn gateway."""
        return TurnGateway(
            active_turn_index=active_turn_index,
            rate_limiter=rate_limiter,
            workflow_client=None,
        )

    @pytest.fixture
    def message(self):
        """Create a sample message."""
        return RawMessage(
            content="Hello", message_id="msg-123", timestamp="2024-01-01T00:00:00Z"
        )

    def test_make_session_key(self, gateway):
        """Should create session key from identifiers."""
        tenant_id = uuid4()
        agent_id = uuid4()
        channel = "whatsapp"
        channel_user_id = "+1234567890"

        session_key = gateway._make_session_key(
            tenant_id, agent_id, channel, channel_user_id
        )

        assert session_key == f"{tenant_id}:{agent_id}:{channel}:{channel_user_id}"

    @pytest.mark.asyncio
    async def test_receive_message_triggers_new_workflow(self, gateway, message):
        """Should trigger new workflow when no active workflow exists."""
        tenant_id = uuid4()
        agent_id = uuid4()

        decision = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+1234567890",
            message=message,
        )

        assert decision.action == TurnAction.TRIGGER_NEW
        assert decision.workflow_id is None

    @pytest.mark.asyncio
    async def test_receive_message_signals_existing_workflow(
        self, gateway, active_turn_index, message
    ):
        """Should signal existing workflow when one is active."""
        tenant_id = uuid4()
        agent_id = uuid4()
        session_key = f"{tenant_id}:{agent_id}:whatsapp:+1234567890"
        workflow_id = "existing-workflow-123"

        # Set up existing workflow
        await active_turn_index.set_workflow_id(session_key, workflow_id)

        decision = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+1234567890",
            message=message,
        )

        assert decision.action == TurnAction.SIGNAL_EXISTING
        assert decision.workflow_id == workflow_id

    @pytest.mark.asyncio
    async def test_receive_message_rejects_when_rate_limited(
        self, active_turn_index, message
    ):
        """Should reject message when rate limit is exceeded."""
        rate_limiter = AsyncMock()
        rate_limiter.check = AsyncMock(return_value=False)

        gateway = TurnGateway(
            active_turn_index=active_turn_index,
            rate_limiter=rate_limiter,
            workflow_client=None,
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        decision = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+1234567890",
            message=message,
        )

        assert decision.action == TurnAction.REJECT
        assert decision.reason == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_receive_message_no_rate_limiter(
        self, active_turn_index, message
    ):
        """Should work without rate limiter."""
        gateway = TurnGateway(
            active_turn_index=active_turn_index,
            rate_limiter=None,
            workflow_client=None,
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        decision = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+1234567890",
            message=message,
        )

        assert decision.action == TurnAction.TRIGGER_NEW

    @pytest.mark.asyncio
    async def test_register_workflow(self, gateway):
        """Should register a workflow for a session."""
        session_key = "test-session-key"
        workflow_id = "workflow-123"

        await gateway.register_workflow(session_key, workflow_id)

        result = await gateway._index.get_workflow_id(session_key)
        assert result == workflow_id

    @pytest.mark.asyncio
    async def test_unregister_workflow(self, gateway):
        """Should unregister a workflow for a session."""
        session_key = "test-session-key"
        workflow_id = "workflow-123"

        await gateway.register_workflow(session_key, workflow_id)
        await gateway.unregister_workflow(session_key)

        result = await gateway._index.get_workflow_id(session_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limiter_checks_session_key(self, gateway, rate_limiter, message):
        """Should check rate limiter with correct session key."""
        tenant_id = uuid4()
        agent_id = uuid4()
        channel = "webchat"
        channel_user_id = "user-123"

        await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=channel,
            channel_user_id=channel_user_id,
            message=message,
        )

        expected_session_key = f"{tenant_id}:{agent_id}:{channel}:{channel_user_id}"
        rate_limiter.check.assert_called_once_with(expected_session_key)

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self, gateway, message):
        """Should handle multiple sessions independently."""
        tenant_id = uuid4()
        agent_id = uuid4()

        # Session 1
        session1_key = f"{tenant_id}:{agent_id}:whatsapp:+1111111111"
        await gateway.register_workflow(session1_key, "workflow-1")

        # Session 2
        decision2 = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+2222222222",
            message=message,
        )

        # Session 2 should trigger new workflow
        assert decision2.action == TurnAction.TRIGGER_NEW

        # Session 1 should still signal existing
        decision1 = await gateway.receive_message(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            channel_user_id="+1111111111",
            message=message,
        )
        assert decision1.action == TurnAction.SIGNAL_EXISTING
        assert decision1.workflow_id == "workflow-1"
