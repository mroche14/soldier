"""Unit tests for chat request and response models."""

import pytest
from pydantic import ValidationError

from soldier.api.models.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    ErrorEvent,
    ScenarioState,
    TokenEvent,
)


class TestChatRequest:
    """Tests for ChatRequest model."""

    def test_valid_request(self) -> None:
        """Valid request with all required fields is accepted."""
        request = ChatRequest(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            channel="whatsapp",
            user_channel_id="+1234567890",
            message="Hello, I need help",
        )
        assert str(request.tenant_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert request.channel == "whatsapp"
        assert request.message == "Hello, I need help"
        assert request.session_id is None
        assert request.metadata is None

    def test_request_with_optional_fields(self) -> None:
        """Request with optional fields is accepted."""
        request = ChatRequest(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            channel="webchat",
            user_channel_id="user123",
            message="What's my order status?",
            session_id="sess_abc123",
            metadata={"locale": "en-US", "device": "mobile"},
        )
        assert request.session_id == "sess_abc123"
        assert request.metadata == {"locale": "en-US", "device": "mobile"}

    def test_tenant_id_required(self) -> None:
        """tenant_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="Hello",
            )
        assert "tenant_id" in str(exc_info.value)

    def test_agent_id_required(self) -> None:
        """agent_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="Hello",
            )
        assert "agent_id" in str(exc_info.value)

    def test_channel_required_and_non_empty(self) -> None:
        """channel is required and must be non-empty."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="",
                user_channel_id="+1234567890",
                message="Hello",
            )

    def test_user_channel_id_required_and_non_empty(self) -> None:
        """user_channel_id is required and must be non-empty."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="whatsapp",
                user_channel_id="",
                message="Hello",
            )

    def test_message_required_and_non_empty(self) -> None:
        """message is required and must be non-empty."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="",
            )

    def test_message_max_length(self) -> None:
        """message must not exceed 10000 characters."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="x" * 10001,
            )

    def test_invalid_tenant_id_uuid(self) -> None:
        """tenant_id must be a valid UUID."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="not-a-uuid",
                agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="Hello",
            )

    def test_invalid_agent_id_uuid(self) -> None:
        """agent_id must be a valid UUID."""
        with pytest.raises(ValidationError):
            ChatRequest(
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                agent_id="not-a-uuid",
                channel="whatsapp",
                user_channel_id="+1234567890",
                message="Hello",
            )


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_minimal_response(self) -> None:
        """Response with only required fields."""
        response = ChatResponse(
            response="Hello! How can I help you?",
            session_id="sess_abc123",
            turn_id="turn_xyz789",
        )
        assert response.response == "Hello! How can I help you?"
        assert response.session_id == "sess_abc123"
        assert response.turn_id == "turn_xyz789"
        assert response.scenario is None
        assert response.matched_rules == []
        assert response.tools_called == []
        assert response.tokens_used == 0
        assert response.latency_ms == 0

    def test_full_response(self) -> None:
        """Response with all fields populated."""
        response = ChatResponse(
            response="Your order will be delivered tomorrow.",
            session_id="sess_abc123",
            turn_id="turn_xyz789",
            scenario=ScenarioState(id="scenario_order", step="step_delivery"),
            matched_rules=["rule_greeting", "rule_order_status"],
            tools_called=["tool_order_lookup"],
            tokens_used=250,
            latency_ms=450,
        )
        assert response.scenario is not None
        assert response.scenario.id == "scenario_order"
        assert response.scenario.step == "step_delivery"
        assert len(response.matched_rules) == 2
        assert "rule_greeting" in response.matched_rules
        assert response.tokens_used == 250
        assert response.latency_ms == 450


class TestScenarioState:
    """Tests for ScenarioState model."""

    def test_empty_state(self) -> None:
        """ScenarioState can be empty."""
        state = ScenarioState()
        assert state.id is None
        assert state.step is None

    def test_with_values(self) -> None:
        """ScenarioState with values."""
        state = ScenarioState(id="scenario_returns", step="step_verify")
        assert state.id == "scenario_returns"
        assert state.step == "step_verify"


class TestStreamEvents:
    """Tests for streaming event models."""

    def test_token_event(self) -> None:
        """TokenEvent has correct type."""
        event = TokenEvent(content="Hello ")
        assert event.type == "token"
        assert event.content == "Hello "

    def test_done_event(self) -> None:
        """DoneEvent has all fields."""
        event = DoneEvent(
            turn_id="turn_123",
            session_id="sess_456",
            matched_rules=["rule_1"],
            tools_called=["tool_1"],
            tokens_used=100,
            latency_ms=300,
        )
        assert event.type == "done"
        assert event.turn_id == "turn_123"
        assert event.session_id == "sess_456"
        assert event.matched_rules == ["rule_1"]
        assert event.tokens_used == 100

    def test_error_event(self) -> None:
        """ErrorEvent has code and message."""
        event = ErrorEvent(code="LLM_ERROR", message="Provider unavailable")
        assert event.type == "error"
        assert event.code == "LLM_ERROR"
        assert event.message == "Provider unavailable"
