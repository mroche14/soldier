"""Tests for audit domain models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ruche.audit.models import AuditEvent, TurnRecord
from ruche.conversation.models import ToolCall


class TestTurnRecord:
    """Tests for TurnRecord model."""

    def test_create_valid_turn_record(self) -> None:
        """Should create a valid turn record."""
        record = TurnRecord(
            turn_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="Hello",
            agent_response="Hi there!",
            latency_ms=150,
            tokens_used=100,
            timestamp=datetime.now(UTC),
        )
        assert record.turn_number == 1
        assert record.latency_ms == 150

    def test_turn_record_is_immutable(self) -> None:
        """Should be immutable (frozen=True)."""
        record = TurnRecord(
            turn_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="Hello",
            agent_response="Hi",
            latency_ms=100,
            tokens_used=50,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
            record.turn_number = 2  # type: ignore

    def test_turn_record_with_tool_calls(self) -> None:
        """Should include tool calls."""
        tool_call = ToolCall(
            tool_id="test",
            tool_name="Test Tool",
            input={"key": "value"},
            output={"result": "success"},
            success=True,
            latency_ms=50,
        )
        record = TurnRecord(
            turn_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            turn_number=1,
            user_message="Test",
            agent_response="Response",
            tool_calls=[tool_call],
            latency_ms=100,
            tokens_used=50,
            timestamp=datetime.now(UTC),
        )
        assert len(record.tool_calls) == 1

    def test_turn_record_with_scenario_context(self) -> None:
        """Should include scenario context."""
        record = TurnRecord(
            turn_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            turn_number=3,
            user_message="Yes, confirm",
            agent_response="Order confirmed!",
            scenario_id=uuid4(),
            step_id=uuid4(),
            latency_ms=200,
            tokens_used=75,
            timestamp=datetime.now(UTC),
        )
        assert record.scenario_id is not None
        assert record.step_id is not None


class TestAuditEvent:
    """Tests for AuditEvent model."""

    def test_create_valid_audit_event(self) -> None:
        """Should create a valid audit event."""
        event = AuditEvent(
            tenant_id=uuid4(),
            event_type="rule_fired",
            event_data={"rule_id": "rule-123", "turn": 5},
        )
        assert event.event_type == "rule_fired"
        assert event.event_data["rule_id"] == "rule-123"

    def test_audit_event_is_immutable(self) -> None:
        """Should be immutable (frozen=True)."""
        event = AuditEvent(
            tenant_id=uuid4(),
            event_type="test",
            event_data={"key": "value"},
        )
        with pytest.raises(Exception):
            event.event_type = "modified"  # type: ignore

    def test_audit_event_with_session_context(self) -> None:
        """Should include session context."""
        event = AuditEvent(
            tenant_id=uuid4(),
            event_type="scenario_started",
            event_data={"scenario_name": "Checkout"},
            session_id=uuid4(),
            turn_id=uuid4(),
        )
        assert event.session_id is not None
        assert event.turn_id is not None

    def test_audit_event_auto_timestamp(self) -> None:
        """Should auto-set timestamp."""
        event = AuditEvent(
            tenant_id=uuid4(),
            event_type="test",
            event_data={},
        )
        assert event.timestamp is not None
