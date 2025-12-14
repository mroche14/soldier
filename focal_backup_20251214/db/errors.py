"""Store error hierarchy for production backends.

All store implementations must raise these errors for consistent error handling.
"""


class StoreError(Exception):
    """Base exception for all store errors.

    All store implementations should wrap backend-specific errors
    in one of the StoreError subclasses.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class ConnectionError(StoreError):
    """Raised when store connection fails.

    Examples:
        - Database connection timeout
        - Redis server unavailable
        - Network errors
    """

    pass


class NotFoundError(StoreError):
    """Raised when requested entity is not found.

    This should be raised when a specific entity lookup fails,
    not for empty search results.
    """

    pass


class ConflictError(StoreError):
    """Raised on unique constraint violation.

    Examples:
        - Duplicate primary key
        - Unique index violation
        - Optimistic locking conflict
    """

    pass


class ValidationError(StoreError):
    """Raised on invalid data.

    Examples:
        - Invalid enum value
        - Required field missing
        - Data type mismatch
    """

    pass
