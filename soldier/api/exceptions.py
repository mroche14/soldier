"""API exception hierarchy for consistent error handling.

All API exceptions inherit from SoldierAPIError, which provides
status_code and error_code attributes used by the global exception
handler to generate consistent error responses.
"""

from soldier.api.models.errors import ErrorCode


class SoldierAPIError(Exception):
    """Base exception for all API errors.

    Subclasses set status_code and error_code to define the HTTP response.
    The global exception handler uses these to generate ErrorResponse.
    """

    status_code: int = 500
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidRequestError(SoldierAPIError):
    """Raised when request validation fails."""

    status_code = 400
    error_code = ErrorCode.INVALID_REQUEST


class TenantNotFoundError(SoldierAPIError):
    """Raised when tenant_id doesn't exist."""

    status_code = 400
    error_code = ErrorCode.TENANT_NOT_FOUND


class AgentNotFoundError(SoldierAPIError):
    """Raised when agent_id doesn't exist for the tenant."""

    status_code = 400
    error_code = ErrorCode.AGENT_NOT_FOUND


class SessionNotFoundError(SoldierAPIError):
    """Raised when session_id doesn't exist."""

    status_code = 404
    error_code = ErrorCode.SESSION_NOT_FOUND


class RuleViolationError(SoldierAPIError):
    """Raised when a rule constraint is violated."""

    status_code = 400
    error_code = ErrorCode.RULE_VIOLATION

    def __init__(self, message: str, rule_id: str | None = None) -> None:
        super().__init__(message)
        self.rule_id = rule_id


class ToolFailedError(SoldierAPIError):
    """Raised when a tool execution fails."""

    status_code = 500
    error_code = ErrorCode.TOOL_FAILED


class RateLimitExceededError(SoldierAPIError):
    """Raised when tenant exceeds rate limit."""

    status_code = 429
    error_code = ErrorCode.RATE_LIMIT_EXCEEDED


class LLMProviderError(SoldierAPIError):
    """Raised when LLM provider fails or is unavailable."""

    status_code = 502
    error_code = ErrorCode.LLM_ERROR


class RuleNotFoundError(SoldierAPIError):
    """Raised when rule_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.RULE_NOT_FOUND


class ScenarioNotFoundError(SoldierAPIError):
    """Raised when scenario_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.SCENARIO_NOT_FOUND


class TemplateNotFoundError(SoldierAPIError):
    """Raised when template_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.TEMPLATE_NOT_FOUND


class VariableNotFoundError(SoldierAPIError):
    """Raised when variable_id doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.VARIABLE_NOT_FOUND


class ToolActivationNotFoundError(SoldierAPIError):
    """Raised when tool activation doesn't exist for the agent."""

    status_code = 404
    error_code = ErrorCode.TOOL_ACTIVATION_NOT_FOUND


class EntryStepDeletionError(SoldierAPIError):
    """Raised when attempting to delete a scenario's entry step."""

    status_code = 400
    error_code = ErrorCode.ENTRY_STEP_DELETION


class PublishInProgressError(SoldierAPIError):
    """Raised when a publish operation is already in progress."""

    status_code = 409
    error_code = ErrorCode.PUBLISH_IN_PROGRESS


class PublishFailedError(SoldierAPIError):
    """Raised when a publish operation fails."""

    status_code = 500
    error_code = ErrorCode.PUBLISH_FAILED


class InvalidTransitionError(SoldierAPIError):
    """Raised when a scenario transition is invalid."""

    status_code = 400
    error_code = ErrorCode.INVALID_TRANSITION


class PublishJobNotFoundError(SoldierAPIError):
    """Raised when a publish job doesn't exist."""

    status_code = 404
    error_code = ErrorCode.PUBLISH_JOB_NOT_FOUND
