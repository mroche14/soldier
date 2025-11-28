"""Structured logging configuration using structlog.

Provides JSON logging for production and console logging for development,
with automatic context binding and PII redaction.
"""

import re
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog
from structlog.types import EventDict, WrappedLogger

# Sensitive key names (O(1) lookup)
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "credentials",
    "email",
    "emails",
    "phone",
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
    "private_key",
    "access_token",
    "refresh_token",
    "bearer",
})

# Regex patterns for PII in string values
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\+?[\d\s\-\(\)]{10,}")
SSN_PATTERN = re.compile(r"\d{3}-\d{2}-\d{4}")


class PIIRedactor:
    """Processor that redacts PII from log events.

    Uses two-tier approach:
    1. Key-name lookup via frozenset (O(1)) for known sensitive keys
    2. Regex patterns on string values as fallback for accidental PII
    """

    def __call__(
        self,
        _logger: WrappedLogger,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Redact PII from event dictionary."""
        return cast(EventDict, self._redact_dict(event_dict))

    def _redact_dict(self, data: MutableMapping[str, Any]) -> dict[str, Any]:
        """Recursively redact PII from a dictionary."""
        result: dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key is sensitive
            if key_lower in SENSITIVE_KEYS:
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = self._redact_dict(value)
            elif isinstance(value, str):
                result[key] = self._redact_string(value)
            elif isinstance(value, list):
                result[key] = self._redact_list(value)
            else:
                result[key] = value

        return result

    def _redact_string(self, value: str) -> str:
        """Redact PII patterns from a string."""
        # Replace email patterns
        value = EMAIL_PATTERN.sub("[EMAIL]", value)
        # Replace phone patterns
        value = PHONE_PATTERN.sub("[PHONE]", value)
        # Replace SSN patterns
        value = SSN_PATTERN.sub("[SSN]", value)
        return value

    def _redact_list(self, items: list[Any]) -> list[Any]:
        """Redact PII from list items."""
        result: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                result.append(self._redact_dict(item))
            elif isinstance(item, str):
                result.append(self._redact_string(item))
            elif isinstance(item, list):
                result.append(self._redact_list(item))
            else:
                result.append(item)
        return result


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    redact_pii: bool = True,
    _include_trace_id: bool = True,  # Reserved for future trace ID injection
) -> None:
    """Configure structured logging.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format - "json" for production, "console" for development
        redact_pii: Whether to redact PII from logs
        include_trace_id: Whether to include trace_id in logs
    """
    # Build processor chain
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Add PII redaction if enabled
    if redact_pii:
        processors.append(PIIRedactor())

    # Add final renderer based on format
    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console format for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Convert level string to int
    level_map = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }
    level_num = level_map.get(level.upper(), 20)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance bound to the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        A bound structlog logger
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
