"""Episode model for memory domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Episode(BaseModel):
    """Atomic unit of memory.

    Episodes represent individual pieces of information stored
    in the memory system, with bi-temporal attributes for
    tracking when events occurred vs when they were recorded.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    group_id: str = Field(..., description="Composite key: tenant_id:session_id for isolation")
    content: str = Field(..., description="Memory content")
    content_type: str = Field(
        default="message",
        description="Type: message, event, document, summary",
    )
    source: str = Field(..., description="Origin: user, agent, system, external")
    source_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional source info"
    )
    occurred_at: datetime = Field(..., description="When it happened")
    recorded_at: datetime = Field(default_factory=utc_now, description="When we learned it")
    embedding: list[float] | None = Field(default=None, description="Semantic vector")
    embedding_model: str | None = Field(default=None, description="Model that generated vector")
    entity_ids: list[UUID] = Field(default_factory=list, description="Linked entities")
