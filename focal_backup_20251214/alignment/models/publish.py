"""Publish job models for configuration versioning."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from focal.alignment.models.base import TenantScopedModel


class PublishStage(BaseModel):
    """Progress tracking for a single publish stage.

    Each publish job goes through multiple stages:
    - validate: Check configuration consistency
    - compile: Compute embeddings, validate references
    - write_bundles: Serialize configuration
    - swap_pointer: Atomic version switch
    - invalidate_cache: Clear cached config
    """

    name: str = Field(..., description="Stage name")

    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="Stage execution status"
    )

    duration_ms: int | None = Field(
        default=None, description="Execution time in milliseconds"
    )

    error: str | None = Field(default=None, description="Stage-specific error message")


class PublishJob(TenantScopedModel):
    """Tracks publish operation progress.

    A publish job represents the process of making configuration
    changes live for an agent. It progresses through multiple
    stages and tracks success/failure for each.
    """

    id: UUID = Field(default_factory=uuid4, description="Job identifier")

    agent_id: UUID = Field(..., description="Target agent identifier")

    version: int = Field(..., ge=1, description="Target version number")

    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="Overall job status"
    )

    stages: list[PublishStage] = Field(
        default_factory=list, description="Stage progress tracking"
    )

    description: str | None = Field(
        default=None, description="User-provided publish description"
    )

    started_at: datetime = Field(..., description="Job start timestamp")

    completed_at: datetime | None = Field(
        default=None, description="Job completion timestamp"
    )

    error: str | None = Field(default=None, description="Overall failure message")

    @classmethod
    def create_with_stages(
        cls,
        tenant_id: UUID,
        agent_id: UUID,
        version: int,
        started_at: datetime,
        description: str | None = None,
    ) -> "PublishJob":
        """Create a new publish job with all stages initialized."""
        stages = [
            PublishStage(name="validate"),
            PublishStage(name="compile"),
            PublishStage(name="write_bundles"),
            PublishStage(name="swap_pointer"),
            PublishStage(name="invalidate_cache"),
        ]
        return cls(
            tenant_id=tenant_id,
            agent_id=agent_id,
            version=version,
            started_at=started_at,
            description=description,
            stages=stages,
        )
