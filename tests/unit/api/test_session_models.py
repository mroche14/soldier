"""Unit tests for session response models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from soldier.api.models.chat import ScenarioState
from soldier.api.models.session import (
    SessionResponse,
    TurnListResponse,
    TurnResponse,
)


class TestSessionResponse:
    """Tests for SessionResponse model."""

    def test_minimal_response(self) -> None:
        """SessionResponse with required fields only."""
        now = datetime.now(UTC)
        response = SessionResponse(
            session_id="sess_123",
            tenant_id="tenant_456",
            agent_id="agent_789",
            channel="webchat",
            user_channel_id="user@example.com",
            created_at=now,
            last_activity_at=now,
        )
        assert response.session_id == "sess_123"
        assert response.tenant_id == "tenant_456"
        assert response.turn_count == 0
        assert response.variables == {}
        assert response.active_scenario_id is None

    def test_full_response(self) -> None:
        """SessionResponse with all fields."""
        now = datetime.now(UTC)
        response = SessionResponse(
            session_id="sess_123",
            tenant_id="tenant_456",
            agent_id="agent_789",
            channel="whatsapp",
            user_channel_id="+1234567890",
            active_scenario_id="scenario_001",
            active_step_id="step_002",
            turn_count=5,
            variables={"user_name": "Alice", "order_id": "ORD-123"},
            rule_fires={"rule_greeting": 1, "rule_order": 2},
            config_version=3,
            created_at=now,
            last_activity_at=now,
        )
        assert response.active_scenario_id == "scenario_001"
        assert response.active_step_id == "step_002"
        assert response.turn_count == 5
        assert response.variables["user_name"] == "Alice"
        assert response.rule_fires["rule_order"] == 2
        assert response.config_version == 3

    def test_required_fields(self) -> None:
        """SessionResponse requires essential fields."""
        with pytest.raises(ValidationError):
            SessionResponse(
                session_id="sess_123",
                # Missing other required fields
            )


class TestTurnResponse:
    """Tests for TurnResponse model."""

    def test_minimal_response(self) -> None:
        """TurnResponse with required fields."""
        now = datetime.now(UTC)
        response = TurnResponse(
            turn_id="turn_123",
            turn_number=1,
            user_message="Hello",
            agent_response="Hi there!",
            timestamp=now,
        )
        assert response.turn_id == "turn_123"
        assert response.turn_number == 1
        assert response.matched_rules == []
        assert response.tools_called == []
        assert response.latency_ms == 0

    def test_full_response(self) -> None:
        """TurnResponse with all fields."""
        now = datetime.now(UTC)
        response = TurnResponse(
            turn_id="turn_123",
            turn_number=3,
            user_message="What's my order status?",
            agent_response="Your order is being shipped.",
            matched_rules=["rule_order_status"],
            tools_called=["tool_order_lookup"],
            scenario_before=ScenarioState(id="scenario_1", step="step_a"),
            scenario_after=ScenarioState(id="scenario_1", step="step_b"),
            latency_ms=250,
            tokens_used=150,
            timestamp=now,
        )
        assert response.turn_number == 3
        assert len(response.matched_rules) == 1
        assert response.scenario_before is not None
        assert response.scenario_before.step == "step_a"
        assert response.scenario_after is not None
        assert response.scenario_after.step == "step_b"

    def test_scenario_states_optional(self) -> None:
        """Scenario states are optional."""
        now = datetime.now(UTC)
        response = TurnResponse(
            turn_id="turn_1",
            turn_number=1,
            user_message="Hi",
            agent_response="Hello",
            timestamp=now,
        )
        assert response.scenario_before is None
        assert response.scenario_after is None


class TestTurnListResponse:
    """Tests for TurnListResponse model."""

    def test_empty_list(self) -> None:
        """TurnListResponse with no items."""
        response = TurnListResponse(
            items=[],
            total=0,
            limit=20,
            offset=0,
            has_more=False,
        )
        assert len(response.items) == 0
        assert response.total == 0
        assert not response.has_more

    def test_with_items(self) -> None:
        """TurnListResponse with turns."""
        now = datetime.now(UTC)
        turns = [
            TurnResponse(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_message=f"Message {i}",
                agent_response=f"Response {i}",
                timestamp=now,
            )
            for i in range(1, 4)
        ]
        response = TurnListResponse(
            items=turns,
            total=10,
            limit=3,
            offset=0,
            has_more=True,
        )
        assert len(response.items) == 3
        assert response.total == 10
        assert response.has_more

    def test_pagination_fields(self) -> None:
        """Pagination fields are correct."""
        response = TurnListResponse(
            items=[],
            total=100,
            limit=20,
            offset=40,
            has_more=True,
        )
        assert response.limit == 20
        assert response.offset == 40
        assert response.has_more
