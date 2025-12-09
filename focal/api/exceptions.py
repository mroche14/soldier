"""API exception hierarchy for consistent error handling.

All API exceptions inherit from FocalAPIError, which provides
status_code and error_code attributes used by the global exception
handler to generate consistent error responses.
"""

from focal.api.models.errors import ErrorCode


class FocalAPIError(Exception):
    """Base exception for all API errors.

    Subclasses set status_code and error_code to define the HTTP response.
    The global exception handler uses these to generate ErrorResponse.
    """

    status_code: int = 500
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidRequestError(FocalAPIError):
    """Raised when request validation fails."""

    status_code = 400
    error_code = ErrorCode.INVALID_REQUEST


class TenantNotFoundError(FocalAPIError):
    """Raised when tenant_id doesn't exist."""

    status_code = 400
    error_code = ErrorCode.TENANT_NOT_FOUND


class AgentNotFoundError(FocalAPIError):
    """Raised when agent_id doesn't exist for the tenant."""

    status_code = 400
    error_code = ErrorCode.AGENT_NOT_FOUND


class SessionNotFoundError(FocalAPIError):
    """Raised when session_id doesn't exist."""

    status_code = 404
    error_code = ErrorCode.SESSION_NOT_FOUND


class RuleViolationError(FocalAPIError):
    """Raised when a rule constraint is violated."""

    status_code = 400
    error_code = ErrorCode.RULE_VIOLATION

    def __init__(self, message: str, rule_id: str | None = None) -> None:
        super().__init__(message)
        self.rule_id = rule_id


class ToolFailedError(FocalAPIError):
    """Raised when a tool execution fails."""

    status_code = 500
    error_code = ErrorCode.TOOL_FAILED


class RateLimitExceededError(FocalAPIError):
    """Raised when tenant exceeds rate limit."""

    status_code = 429
    error_code = ErrorCode.RATE_LIMIT_EXCEEDED


class LLMProviderError(FocalAPIError):
    """Raised when LLM provider fails or is unavailable."""

    status_code = 502
    error_code = ErrorCode.LLM_ERROR


class RuleNotFoundError(FocalAPIError):
    """Raised when rule_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.RULE_NOT_FOUND


class ScenarioNotFoundError(FocalAPIError):
    """Raised when scenario_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.SCENARIO_NOT_FOUND


class TemplateNotFoundError(FocalAPIError):
    """Raised when template_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.TEMPLATE_NOT_FOUND


class VariableNotFoundError(FocalAPIError):
    """Raised when variable_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.VARIABLE_NOT_FOUND


class ToolActivationNotFoundError(FocalAPIError):
    """Raised when tool activation doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.TOOL_ACTIVATION_NOT_FOUND


class EntryStepDeletionError(FocalAPIError):
    """Raised when attempting to delete a scenario's entry step."""

    status_code = 400
    error_code = ErrorCode.ENTRY_STEP_DELETION


class PublishInProgressError(FocalAPIError):
    """Raised when a publish operation is already in progress."""

    status_code = 409
    error_code = ErrorCode.PUBLISH_IN_PROGRESS


class PublishFailedError(FocalAPIError):
    """Raised when a publish operation fails."""

    status_code = 500
    error_code = ErrorCode.PUBLISH_FAILED


class InvalidTransitionError(FocalAPIError):
    """Raised when a scenario transition is invalid."""

    status_code = 400
    error_code = ErrorCode.INVALID_TRANSITION


class PublishJobNotFoundError(FocalAPIError):
    """Raised when a publish job doesn't exist."""

    status_code = 404
    error_code = ErrorCode.PUBLISH_JOB_NOT_FOUND
