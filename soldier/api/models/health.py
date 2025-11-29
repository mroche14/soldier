"""Health check response models."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    name: str
    """Component name."""

    status: Literal["healthy", "degraded", "unhealthy"]
    """Component status."""

    latency_ms: float | None = None
    """Time taken to check this component in milliseconds."""

    message: str | None = None
    """Optional status message or error description."""


class HealthResponse(BaseModel):
    """Overall health status response for GET /health."""

    status: Literal["healthy", "degraded", "unhealthy"]
    """Overall service status."""

    version: str
    """Service version."""

    components: list[ComponentHealth] = Field(default_factory=list)
    """Health status of individual components."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    """When this health check was performed."""
