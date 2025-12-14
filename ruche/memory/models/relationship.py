"""Relationship model for memory domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Relationship(BaseModel):
    """Connection between entities.

    Relationships represent typed connections between entities
    with temporal validity tracking.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    group_id: str = Field(..., description="Isolation key")
    from_entity_id: UUID = Field(..., description="Source entity")
    to_entity_id: UUID = Field(..., description="Target entity")
    relation_type: str = Field(..., description="Type: ordered, owns, works_for, etc.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Relationship properties")
    valid_from: datetime = Field(..., description="When became valid")
    valid_to: datetime | None = Field(default=None, description="When stopped being valid")
    recorded_at: datetime = Field(default_factory=utc_now, description="When recorded")
