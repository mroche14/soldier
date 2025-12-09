"""Tests for conversation domain models."""

from datetime import UTC, datetime
from uuid import uuid4

from focal.conversation.models import (
    Channel,
    Session,
    SessionStatus,
    StepVisit,
    ToolCall,
    Turn,
)


class TestSession:
    """Tests for Session model."""

    def test_create_valid_session(self) -> None:
        """Should create a valid session."""
        session = Session(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            channel=Channel.WEBCHAT,
            user_channel_id="user@example.com",
            config_version=1,
        )
        assert session.channel == Channel.WEBCHAT
        assert session.status == SessionStatus.ACTIVE
        assert session.turn_count == 0

    def test_session_with_scenario_tracking(self) -> None:
        """Should track active scenario and step."""
        scenario_id = uuid4()
        step_id = uuid4()
        session = Session(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            channel=Channel.WHATSAPP,
            user_channel_id="+1234567890",
            config_version=1,
            active_scenario_id=scenario_id,
            active_step_id=step_id,
            active_scenario_version=2,
        )
        assert session.active_scenario_id == scenario_id
        assert session.active_step_id == step_id
        assert session.active_scenario_version == 2

    def test_session_rule_tracking(self) -> None:
        """Should track rule fires."""
        session = Session(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            channel=Channel.API,
            user_channel_id="api-client",
            config_version=1,
            rule_fires={"rule-1": 3, "rule-2": 1},
            rule_last_fire_turn={"rule-1": 5, "rule-2": 7},
        )
        assert session.rule_fires["rule-1"] == 3
        assert session.rule_last_fire_turn["rule-2"] == 7

    def test_session_with_step_history(self) -> None:
        """Should track step history."""
        visit = StepVisit(
            step_id=uuid4(),
            entered_at=datetime.now(UTC),
            turn_number=1,
            confidence=0.95,
        )
        session = Session(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            channel=Channel.SLACK,
            user_channel_id="U12345",
            config_version=1,
            step_history=[visit],
        )
        assert len(session.step_history) == 1
        assert session.step_history[0].confidence == 0.95


class TestStepVisit:
    """Tests for StepVisit model."""

    def test_create_valid_step_visit(self) -> None:
        """Should create a valid step visit."""
        visit = StepVisit(
            step_id=uuid4(),
            entered_at=datetime.now(UTC),
            turn_number=5,
            transition_reason="User confirmed",
        )
        assert visit.turn_number == 5
        assert visit.transition_reason == "User confirmed"
        assert visit.confidence == 1.0  # Default


class TestTurn:
    """Tests for Turn model."""

    def test_create_valid_turn(self) -> None:
        """Should create a valid turn."""
        turn = Turn(
            tenant_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="Hello",
            agent_response="Hi! How can I help you?",
            latency_ms=150,
            tokens_used=100,
        )
        assert turn.user_message == "Hello"
        assert turn.latency_ms == 150
        assert turn.enforcement_triggered is False

    def test_turn_with_tool_calls(self) -> None:
        """Should track tool calls."""
        tool_call = ToolCall(
            tool_id="get_order",
            tool_name="Get Order Details",
            input={"order_id": "12345"},
            output={"status": "shipped"},
            success=True,
            latency_ms=50,
        )
        turn = Turn(
            tenant_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="What's my order status?",
            agent_response="Your order has shipped.",
            latency_ms=200,
            tokens_used=150,
            tool_calls=[tool_call],
        )
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].success is True

    def test_turn_with_matched_rules(self) -> None:
        """Should track matched rules."""
        rule_ids = [uuid4(), uuid4()]
        turn = Turn(
            tenant_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="Test",
            agent_response="Response",
            latency_ms=100,
            tokens_used=50,
            matched_rule_ids=rule_ids,
        )
        assert len(turn.matched_rule_ids) == 2


class TestToolCall:
    """Tests for ToolCall model."""

    def test_create_successful_tool_call(self) -> None:
        """Should create a successful tool call."""
        tool_call = ToolCall(
            tool_id="search",
            tool_name="Search Knowledge Base",
            input={"query": "refund policy"},
            output={"results": ["..."]*3},
            success=True,
            latency_ms=75,
        )
        assert tool_call.success is True
        assert tool_call.error is None

    def test_create_failed_tool_call(self) -> None:
        """Should create a failed tool call."""
        tool_call = ToolCall(
            tool_id="api_call",
            tool_name="External API",
            input={"endpoint": "/users"},
            output=None,
            success=False,
            error="Connection timeout",
            latency_ms=30000,
        )
        assert tool_call.success is False
        assert tool_call.error == "Connection timeout"
