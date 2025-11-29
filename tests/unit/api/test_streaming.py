"""Unit tests for streaming event models."""

import pytest

from soldier.api.models.chat import (
    DoneEvent,
    ErrorEvent,
    StreamEvent,
    TokenEvent,
)


class TestTokenEvent:
    """Tests for TokenEvent model."""

    def test_type_is_token(self) -> None:
        """TokenEvent has type 'token'."""
        event = TokenEvent(content="Hello")
        assert event.type == "token"

    def test_content_required(self) -> None:
        """TokenEvent requires content."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TokenEvent()  # type: ignore

    def test_content_can_be_empty(self) -> None:
        """Content can be an empty string."""
        event = TokenEvent(content="")
        assert event.content == ""

    def test_content_with_whitespace(self) -> None:
        """Content preserves whitespace."""
        event = TokenEvent(content="  hello  ")
        assert event.content == "  hello  "

    def test_serialization(self) -> None:
        """TokenEvent serializes correctly."""
        event = TokenEvent(content="test")
        data = event.model_dump()
        assert data == {"type": "token", "content": "test"}

    def test_json_serialization(self) -> None:
        """TokenEvent JSON serialization."""
        event = TokenEvent(content="hello")
        json_str = event.model_dump_json()
        assert '"type":"token"' in json_str
        assert '"content":"hello"' in json_str


class TestDoneEvent:
    """Tests for DoneEvent model."""

    def test_type_is_done(self) -> None:
        """DoneEvent has type 'done'."""
        event = DoneEvent(turn_id="turn_123", session_id="sess_456")
        assert event.type == "done"

    def test_required_fields(self) -> None:
        """DoneEvent requires turn_id and session_id."""
        event = DoneEvent(turn_id="turn_123", session_id="sess_456")
        assert event.turn_id == "turn_123"
        assert event.session_id == "sess_456"

    def test_default_values(self) -> None:
        """DoneEvent has sensible defaults."""
        event = DoneEvent(turn_id="t1", session_id="s1")
        assert event.matched_rules == []
        assert event.tools_called == []
        assert event.tokens_used == 0
        assert event.latency_ms == 0

    def test_with_all_fields(self) -> None:
        """DoneEvent with all fields populated."""
        event = DoneEvent(
            turn_id="turn_123",
            session_id="sess_456",
            matched_rules=["rule_1", "rule_2"],
            tools_called=["tool_1"],
            tokens_used=150,
            latency_ms=500,
        )
        assert len(event.matched_rules) == 2
        assert event.tokens_used == 150
        assert event.latency_ms == 500

    def test_serialization(self) -> None:
        """DoneEvent serializes correctly."""
        event = DoneEvent(
            turn_id="t1",
            session_id="s1",
            matched_rules=["r1"],
            tokens_used=100,
        )
        data = event.model_dump()
        assert data["type"] == "done"
        assert data["turn_id"] == "t1"
        assert data["matched_rules"] == ["r1"]


class TestErrorEvent:
    """Tests for ErrorEvent model."""

    def test_type_is_error(self) -> None:
        """ErrorEvent has type 'error'."""
        event = ErrorEvent(code="LLM_ERROR", message="Provider failed")
        assert event.type == "error"

    def test_required_fields(self) -> None:
        """ErrorEvent requires code and message."""
        event = ErrorEvent(code="INTERNAL_ERROR", message="Something went wrong")
        assert event.code == "INTERNAL_ERROR"
        assert event.message == "Something went wrong"

    def test_serialization(self) -> None:
        """ErrorEvent serializes correctly."""
        event = ErrorEvent(code="RATE_LIMIT_EXCEEDED", message="Too many requests")
        data = event.model_dump()
        assert data == {
            "type": "error",
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests",
        }


class TestStreamEventUnion:
    """Tests for StreamEvent union type."""

    def test_token_event_is_stream_event(self) -> None:
        """TokenEvent is a valid StreamEvent."""
        event: StreamEvent = TokenEvent(content="hello")
        assert event.type == "token"

    def test_done_event_is_stream_event(self) -> None:
        """DoneEvent is a valid StreamEvent."""
        event: StreamEvent = DoneEvent(turn_id="t1", session_id="s1")
        assert event.type == "done"

    def test_error_event_is_stream_event(self) -> None:
        """ErrorEvent is a valid StreamEvent."""
        event: StreamEvent = ErrorEvent(code="ERROR", message="Failed")
        assert event.type == "error"
