"""Agent configuration and metadata models.

These models represent the runtime configuration view of an agent,
separate from the full Agent model used in the configuration layer.
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class AgentMetadata(BaseModel):
    """Runtime metadata for an agent.

    This is a lightweight view of agent configuration needed for
    runtime operations. Full configuration lives in ConfigStore.
    """

    agent_id: UUID = Field(..., description="Agent identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    name: str = Field(..., description="Agent display name")
    version: int = Field(..., description="Current published version")
    enabled: bool = Field(default=True, description="Whether agent is active")

    # LLM settings (if specified at agent level)
    default_model: str | None = Field(
        default=None, description="Default model for this agent"
    )
    default_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    default_max_tokens: int | None = Field(default=None, ge=1)

    # Timestamps
    loaded_at: datetime = Field(
        default_factory=utc_now, description="When config was loaded"
    )
    config_hash: str | None = Field(
        default=None, description="Hash of configuration for invalidation"
    )


class AgentCapabilities(BaseModel):
    """Agent capabilities and feature flags.

    Determines what features are enabled for this agent at runtime.
    """

    # Pipeline features
    supports_scenarios: bool = Field(
        default=True, description="Scenario orchestration enabled"
    )
    supports_tools: bool = Field(default=True, description="Tool execution enabled")
    supports_memory: bool = Field(
        default=True, description="Memory ingestion/retrieval enabled"
    )

    # Advanced features
    supports_multi_scenario: bool = Field(
        default=False, description="Multiple concurrent scenarios"
    )
    supports_handoffs: bool = Field(default=False, description="Agent handoffs")
    supports_proactive: bool = Field(
        default=False, description="Proactive outreach (agenda-driven)"
    )

    # Safety features
    requires_confirmation: list[str] = Field(
        default_factory=list, description="Tools requiring confirmation"
    )
    max_tool_executions_per_turn: int = Field(
        default=5, ge=1, description="Tool execution limit per turn"
    )
