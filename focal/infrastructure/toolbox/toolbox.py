"""Toolbox class - agent's facade for tool execution.

Provides a clean interface for agents to discover and execute tools.
"""

from typing import Any
from uuid import UUID

from focal.infrastructure.stores.config import ConfigStore
from focal.infrastructure.toolbox.gateway import ToolGateway
from focal.infrastructure.toolbox.models import ToolMetadata, ToolResult
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class Toolbox:
    """Agent's tool execution facade.

    Loads tool activations from ConfigStore and delegates execution to ToolGateway.
    Provides a simplified interface for agents to work with tools.
    """

    def __init__(
        self,
        config_store: ConfigStore,
        tool_gateway: ToolGateway,
    ) -> None:
        """Initialize the toolbox.

        Args:
            config_store: Store for tool activations
            tool_gateway: Gateway for routing tool executions
        """
        self._config_store = config_store
        self._tool_gateway = tool_gateway

    async def get_available_tools(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scenario_id: UUID | None = None,
    ) -> list[ToolMetadata]:
        """Get tools available to an agent.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            scenario_id: Optional scenario filter

        Returns:
            List of tool metadata for available tools
        """
        activations = await self._config_store.get_tool_activations(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Filter by scenario if specified
        if scenario_id:
            activations = [
                a
                for a in activations
                if a.allowed_scenarios is None or scenario_id in a.allowed_scenarios
            ]

        # Filter to enabled only
        activations = [a for a in activations if a.enabled]

        # Return metadata (stub - would load full tool definitions)
        return [
            ToolMetadata(
                id=a.tool_id,
                name=a.tool_id,  # Would load from tool registry
                description="Tool description",  # Would load from tool registry
                side_effect_policy="none",  # Would load from tool definition
                requires_confirmation=False,
            )
            for a in activations
        ]

    async def execute(
        self,
        tool_id: str,
        inputs: dict[str, Any],
        *,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> ToolResult:
        """Execute a tool.

        Args:
            tool_id: Tool identifier
            inputs: Tool input parameters
            tenant_id: Tenant context
            agent_id: Agent context

        Returns:
            ToolResult with execution outcome
        """
        # Get activation to check permissions
        activation = await self._config_store.get_tool_activation(
            tenant_id=tenant_id,
            agent_id=agent_id,
            tool_id=tool_id,
        )

        if not activation or not activation.enabled:
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error="Tool not activated for this agent",
                execution_time_ms=0,
                provider="unknown",
            )

        # Load tool definition (stub - would load from registry)
        # For now, return a stub result
        logger.info(
            "tool_execution_requested",
            tool_id=tool_id,
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        return ToolResult(
            tool_id=tool_id,
            success=True,
            output={"message": "Tool execution stub - implementation pending"},
            execution_time_ms=0,
            provider="stub",
        )
