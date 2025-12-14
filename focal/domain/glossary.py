"""Glossary domain model.

Domain-specific term definitions for LLM context.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class GlossaryItem(BaseModel):
    """Domain term definition for LLM context.

    Used in Phase 2 (Situational Sensor) and Phase 9 (Generation)
    to ensure consistent terminology.
    """

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")

    # Definition
    term: str = Field(..., description="Term to define (e.g., 'CSAT score')")
    definition: str = Field(
        ..., description="Meaning (e.g., 'Customer Satisfaction score from 1-5')"
    )
    usage_hint: str | None = Field(
        default=None, description="Usage guidance (e.g., 'Use when discussing surveys')"
    )
    aliases: list[str] = Field(
        default_factory=list, description="Alternative terms"
    )

    # Categorization
    category: str | None = Field(
        default=None, description="Category (e.g., 'metrics', 'products', 'policies')"
    )
    priority: int = Field(
        default=0, description="Priority (higher = more important)"
    )

    # Status
    enabled: bool = Field(default=True, description="Is active")
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update"
    )
