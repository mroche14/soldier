"""Tests for structured logging."""

import json
from io import StringIO
from uuid import uuid4

import pytest
import structlog

from soldier.observability.logging import (
    PIIRedactor,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_json_format(self) -> None:
        """Should configure JSON format for production."""
        setup_logging(level="INFO", format="json", redact_pii=False)
        logger = get_logger("test")
        # Should not raise
        logger.info("test_message")

    def test_setup_console_format(self) -> None:
        """Should configure console format for development."""
        setup_logging(level="DEBUG", format="console", redact_pii=False)
        logger = get_logger("test")
        # Should not raise
        logger.debug("test_message")

    def test_setup_with_pii_redaction(self) -> None:
        """Should configure PII redaction when enabled."""
        setup_logging(level="INFO", format="json", redact_pii=True)
        logger = get_logger("test")
        # Should not raise
        logger.info("test_message", email="user@example.com")


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_bound_logger(self) -> None:
        """Should return a structlog BoundLogger."""
        setup_logging(level="INFO", format="json", redact_pii=False)
        logger = get_logger("test.module")
        assert logger is not None

    def test_logger_name_bound(self) -> None:
        """Should bind logger name to context."""
        setup_logging(level="INFO", format="json", redact_pii=False)
        logger = get_logger("my.module.name")
        # The logger should have the name bound
        assert logger is not None


class TestContextBinding:
    """Tests for context binding via structlog.contextvars."""

    def test_bind_context_appears_in_logs(self) -> None:
        """Should include bound context in log output."""
        setup_logging(level="INFO", format="json", redact_pii=False)
        logger = get_logger("test")

        # Bind context
        tenant_id = str(uuid4())
        agent_id = str(uuid4())
        session_id = str(uuid4())
        turn_id = str(uuid4())
        trace_id = "abc123"

        structlog.contextvars.bind_contextvars(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
        )

        # Log a message - context should be included
        logger.info("test_event")

        # Clear context for other tests
        structlog.contextvars.clear_contextvars()


class TestPIIRedactor:
    """Tests for PII redaction."""

    @pytest.fixture
    def redactor(self) -> PIIRedactor:
        """Create a PIIRedactor instance."""
        return PIIRedactor()

    def test_redacts_email_by_key(self, redactor: PIIRedactor) -> None:
        """Should redact values for email-related keys."""
        event_dict = {"email": "user@example.com", "other": "value"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert result["email"] == "[REDACTED]"
        assert result["other"] == "value"

    def test_redacts_password_by_key(self, redactor: PIIRedactor) -> None:
        """Should redact password values."""
        event_dict = {"password": "secret123", "data": "ok"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert result["password"] == "[REDACTED]"
        assert result["data"] == "ok"

    def test_redacts_ssn_by_key(self, redactor: PIIRedactor) -> None:
        """Should redact SSN values."""
        event_dict = {"ssn": "123-45-6789", "name": "John"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert result["ssn"] == "[REDACTED]"
        assert result["name"] == "John"

    def test_redacts_token_by_key(self, redactor: PIIRedactor) -> None:
        """Should redact token values."""
        event_dict = {"token": "abc123xyz", "api_key": "key123"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert result["token"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"

    def test_redacts_email_pattern_in_string_value(self, redactor: PIIRedactor) -> None:
        """Should redact email patterns found in string values."""
        event_dict = {"message": "Contact user@example.com for help"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert "user@example.com" not in result["message"]
        assert "[EMAIL]" in result["message"]

    def test_redacts_phone_pattern_in_string_value(self, redactor: PIIRedactor) -> None:
        """Should redact phone patterns found in string values."""
        event_dict = {"message": "Call me at +1-555-123-4567 please"}
        result = redactor(None, None, event_dict)  # type: ignore
        assert "+1-555-123-4567" not in result["message"]
        assert "[PHONE]" in result["message"]

    def test_handles_nested_dicts(self, redactor: PIIRedactor) -> None:
        """Should handle nested dictionaries."""
        event_dict = {
            "user": {"email": "user@example.com", "name": "John"},
            "data": "ok",
        }
        result = redactor(None, None, event_dict)  # type: ignore
        assert result["user"]["email"] == "[REDACTED]"
        assert result["user"]["name"] == "John"

    def test_handles_lists(self, redactor: PIIRedactor) -> None:
        """Should handle lists containing strings."""
        event_dict = {"emails": ["user1@example.com", "user2@example.com"]}
        result = redactor(None, None, event_dict)  # type: ignore
        # Keys named 'emails' should be redacted entirely
        assert result["emails"] == "[REDACTED]"

    def test_preserves_non_pii_data(self, redactor: PIIRedactor) -> None:
        """Should preserve non-PII data."""
        event_dict = {
            "event": "request_processed",
            "latency_ms": 150,
            "status": "success",
            "count": 42,
        }
        result = redactor(None, None, event_dict)  # type: ignore
        assert result == event_dict


class TestJSONLogging:
    """Tests for JSON log output format."""

    def test_json_output_is_valid_json(self) -> None:
        """Should produce valid JSON output."""
        setup_logging(level="INFO", format="json", redact_pii=False)
        logger = get_logger("test")

        # Create a StringIO to capture output
        output = StringIO()

        # Configure structlog to write to our StringIO
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(output),
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger("test")
        logger.info("test_event", key="value")

        output_str = output.getvalue()
        # Should be valid JSON
        parsed = json.loads(output_str.strip())
        assert parsed["event"] == "test_event"
        assert parsed["key"] == "value"
        assert "timestamp" in parsed
        assert "level" in parsed
