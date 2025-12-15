"""Base models for alignment domain entities."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class TenantScopedModel(BaseModel):
    """Base for all tenant-scoped entities.

    All entities in the system must be scoped to a tenant for
    multi-tenant isolation. This base class provides:
    - tenant_id: Required tenant identifier
    - created_at/updated_at: Automatic timestamps
    - deleted_at: Soft delete marker
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="ignore",
    )

    tenant_id: UUID = Field(..., description="Owning tenant identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Last modification timestamp")
    deleted_at: datetime | None = Field(default=None, description="Soft delete marker")

    @property
    def is_deleted(self) -> bool:
        """Check if entity is soft-deleted."""
        return self.deleted_at is not None

    def touch(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = utc_now()

    def soft_delete(self) -> None:
        """Mark entity as soft-deleted."""
        self.deleted_at = utc_now()
        self.touch()


class AgentScopedModel(TenantScopedModel):
    """Base for entities scoped to a specific agent.

    Extends TenantScopedModel with agent_id for entities that
    belong to a specific agent within a tenant.
    """

    agent_id: UUID = Field(..., description="Owning agent identifier")
