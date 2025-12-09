"""Exception classes for memory ingestion system."""

from uuid import UUID


class IngestionError(Exception):
    """Raised when episode ingestion fails."""

    def __init__(
        self,
        message: str,
        episode_id: UUID | None = None,
        group_id: str | None = None,
        cause: Exception | None = None,
    ):
        self.episode_id = episode_id
        self.group_id = group_id
        self.cause = cause
        super().__init__(message)


class ExtractionError(Exception):
    """Raised when entity/relationship extraction fails."""

    def __init__(
        self,
        message: str,
        episode_id: UUID | None = None,
        provider_error: str | None = None,
        cause: Exception | None = None,
    ):
        self.episode_id = episode_id
        self.provider_error = provider_error
        self.cause = cause
        super().__init__(message)


class SummarizationError(Exception):
    """Raised when summarization fails."""

    def __init__(
        self,
        message: str,
        group_id: str | None = None,
        summary_type: str | None = None,
        cause: Exception | None = None,
    ):
        self.group_id = group_id
        self.summary_type = summary_type
        self.cause = cause
        super().__init__(message)
