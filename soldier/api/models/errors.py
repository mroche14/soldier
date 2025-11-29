"""Error response models for consistent API error handling."""

from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Standardized error codes for API responses.

    These codes provide machine-readable error identification across
    all API endpoints.
    """

    INVALID_REQUEST = "INVALID_REQUEST"
    """Request validation failed (malformed JSON, missing fields, etc.)."""

    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    """The specified tenant_id does not exist."""

    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    """The specified agent_id does not exist for this tenant."""

    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    """The specified session_id does not exist."""

    RULE_VIOLATION = "RULE_VIOLATION"
    """A rule constraint was violated during processing."""

    TOOL_FAILED = "TOOL_FAILED"
    """A tool execution failed during turn processing."""

    LLM_ERROR = "LLM_ERROR"
    """The LLM provider returned an error or was unavailable."""

    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    """The tenant has exceeded their rate limit."""

    INTERNAL_ERROR = "INTERNAL_ERROR"
    """An unexpected internal error occurred."""


class ErrorDetail(BaseModel):
    """Detailed error information for validation errors.

    Provides field-level error details for request validation failures.
    """

    field: str | None = None
    """The field that caused the error, if applicable."""

    message: str
    """Human-readable error description."""


class ErrorBody(BaseModel):
    """Error body content for API error responses."""

    code: ErrorCode
    """Machine-readable error code."""

    message: str
    """Human-readable error message."""

    details: list[ErrorDetail] | None = None
    """Additional error details for validation failures."""

    turn_id: str | None = None
    """Turn ID if the error occurred during turn processing."""

    rule_id: str | None = None
    """Rule ID if the error was caused by a rule violation."""


class ErrorResponse(BaseModel):
    """Standard error response format for all API errors.

    All error responses follow this structure for consistency.

    Example:
        {
            "error": {
                "code": "AGENT_NOT_FOUND",
                "message": "Agent with ID xyz does not exist"
            }
        }
    """

    error: ErrorBody
