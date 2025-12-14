"""Entity model for memory domain.

Entities represent named things in the knowledge graph like people,
orders, products, etc.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Entity(BaseModel):
    """Named thing in knowledge graph.

    Entities represent real-world objects like people, orders,
    products, etc. with temporal validity tracking.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    group_id: str = Field(..., description="Isolation key")
    name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Type: person, order, product, etc.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Entity properties")
    valid_from: datetime = Field(..., description="When became valid")
    valid_to: datetime | None = Field(default=None, description="When stopped being valid")
    recorded_at: datetime = Field(default_factory=utc_now, description="When recorded")
    embedding: list[float] | None = Field(default=None, description="Semantic vector")
