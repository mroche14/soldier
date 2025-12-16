"""Idempotency models and enums.

Data models for the three-layer idempotency system (API, Beat, Tool).
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IdempotencyStatus(str, Enum):
    """Status of an idempotency check."""

    NEW = "new"
    PROCESSING = "processing"
    COMPLETE = "complete"


class IdempotencyLayer(str, Enum):
    """Idempotency layer identifier."""

    API = "api"
    BEAT = "beat"
    TOOL = "tool"


class IdempotencyCheckResult(BaseModel):
    """Result of an idempotency check.

    Indicates whether a request is new, currently processing,
    or already completed with cached result.
    """

    status: IdempotencyStatus = Field(
        description="Current status of the idempotency key"
    )
    cached_result: Any | None = Field(
        default=None, description="Cached result if status is COMPLETE"
    )
