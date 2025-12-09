"""ToolActivation model for per-agent tool enablement."""

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID, uuid4

from pydantic import Field

from focal.alignment.models.base import AgentScopedModel, utc_now


class ToolActivation(AgentScopedModel):
    """Per-agent tool enablement status.

    Controls which tools are available for a specific agent
    and any policy overrides for those tools.

    Unique constraint: (tenant_id, agent_id, tool_id)
    """

    id: UUID = Field(default_factory=uuid4, description="Unique activation identifier")

    tool_id: str = Field(..., description="External tool reference identifier")

    status: Literal["enabled", "disabled"] = Field(
        default="enabled", description="Current activation state"
    )

    policy_override: dict[str, Any] | None = Field(
        default=None, description="Custom policy settings (e.g., timeout)"
    )

    enabled_at: datetime | None = Field(
        default=None, description="Timestamp when tool was last enabled"
    )

    disabled_at: datetime | None = Field(
        default=None, description="Timestamp when tool was last disabled"
    )

    @property
    def is_enabled(self) -> bool:
        """Check if tool is currently enabled."""
        return self.status == "enabled"

    def enable(self) -> None:
        """Enable this tool activation."""
        self.status = "enabled"
        self.enabled_at = utc_now()
        self.disabled_at = None
        self.touch()

    def disable(self) -> None:
        """Disable this tool activation."""
        self.status = "disabled"
        self.disabled_at = utc_now()
        self.touch()

    @classmethod
    def create(
        cls,
        tenant_id: UUID,
        agent_id: UUID,
        tool_id: str,
        policy_override: dict[str, Any] | None = None,
    ) -> Self:
        """Create a new enabled tool activation.

        Args:
            tenant_id: Owning tenant
            agent_id: Agent this tool is activated for
            tool_id: External tool identifier
            policy_override: Optional policy overrides

        Returns:
            New ToolActivation instance
        """
        now = utc_now()
        return cls(
            tenant_id=tenant_id,
            agent_id=agent_id,
            tool_id=tool_id,
            status="enabled",
            policy_override=policy_override,
            enabled_at=now,
        )
