"""MCP server for tool discovery.

This module implements the Model Context Protocol (MCP) server for exposing
tool catalog visibility to LLMs and AI agents. This is for discovery only,
not execution (execution goes through Toolbox).

The server exposes three-tier tool visibility:
- Tier 1: Catalog (all tools in ecosystem) - Not yet implemented
- Tier 2: Tenant-available (tools tenant has connected/purchased)
- Tier 3: Agent-enabled (tools this agent can use)

Resources exposed:
- focal://tools/tenant/{tenant_id}/available - List tenant-available tools
- focal://tools/agent/{agent_id}/enabled - List agent-enabled tools
- focal://tools/agent/{agent_id}/unavailable - List tenant-available but not agent-enabled
"""

from typing import Any
from uuid import UUID

from ruche.brains.focal.stores.agent_config_store import AgentConfigStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class MCPToolServer:
    """MCP server for tool discovery.

    Provides read-only access to tool catalog for discovery purposes.
    Execution happens through Toolbox, not via MCP.
    """

    def __init__(self, config_store: AgentConfigStore):
        """Initialize MCP server.

        Args:
            config_store: Store for retrieving tool definitions and activations
        """
        self._config_store = config_store

    async def list_tenant_available_tools(
        self, tenant_id: UUID
    ) -> list[dict[str, Any]]:
        """List all tools available to a tenant (Tier 2).

        These are tools the tenant has connected/purchased, regardless of
        whether any specific agent has them enabled.

        Args:
            tenant_id: Tenant to list tools for

        Returns:
            List of tool definitions as dictionaries
        """
        logger.debug("mcp_list_tenant_tools", tenant_id=str(tenant_id))

        # For now, we return tool activations across all agents
        # This is a placeholder until we have a proper ToolDefinition store
        # In the future, this should query ToolDefinition by tenant_id
        activations = await self._config_store.get_all_tool_activations(tenant_id)

        # Deduplicate by tool_id to get tenant-level availability
        seen_tool_ids = set()
        tools = []
        for activation in activations:
            if activation.tool_id not in seen_tool_ids:
                seen_tool_ids.add(activation.tool_id)
                tools.append(
                    {
                        "tool_id": activation.tool_id,
                        "tier": "tenant-available",
                        "tenant_id": str(activation.tenant_id),
                    }
                )

        logger.debug(
            "mcp_tenant_tools_listed",
            tenant_id=str(tenant_id),
            tool_count=len(tools),
        )

        return tools

    async def list_agent_enabled_tools(
        self, tenant_id: UUID, agent_id: UUID
    ) -> list[dict[str, Any]]:
        """List tools enabled for a specific agent (Tier 3).

        These are tools the agent can currently execute.

        Args:
            tenant_id: Tenant the agent belongs to
            agent_id: Agent to list tools for

        Returns:
            List of enabled tool activations as dictionaries
        """
        logger.debug(
            "mcp_list_agent_enabled_tools",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        activations = await self._config_store.get_tool_activations(tenant_id, agent_id)
        enabled = [a for a in activations if a.is_enabled]

        tools = [
            {
                "tool_id": activation.tool_id,
                "tier": "agent-enabled",
                "tenant_id": str(activation.tenant_id),
                "agent_id": str(activation.agent_id),
                "policy_override": activation.policy_override,
                "enabled_at": activation.enabled_at.isoformat()
                if activation.enabled_at
                else None,
            }
            for activation in enabled
        ]

        logger.debug(
            "mcp_agent_enabled_tools_listed",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            tool_count=len(tools),
        )

        return tools

    async def list_agent_unavailable_tools(
        self, tenant_id: UUID, agent_id: UUID
    ) -> list[dict[str, Any]]:
        """List tools available to tenant but not enabled for agent.

        These are tools the agent could have access to but currently doesn't.
        Useful for agent awareness: "I could help with X if you enable tool Y".

        Args:
            tenant_id: Tenant the agent belongs to
            agent_id: Agent to list tools for

        Returns:
            List of unavailable tools (Tier 2 - Tier 3)
        """
        logger.debug(
            "mcp_list_agent_unavailable_tools",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        # Get all tenant-available tools
        tenant_tools = await self.list_tenant_available_tools(tenant_id)
        tenant_tool_ids = {t["tool_id"] for t in tenant_tools}

        # Get agent-enabled tools
        agent_activations = await self._config_store.get_tool_activations(
            tenant_id, agent_id
        )
        enabled_tool_ids = {a.tool_id for a in agent_activations if a.is_enabled}

        # Unavailable = tenant-available - agent-enabled
        unavailable_tool_ids = tenant_tool_ids - enabled_tool_ids

        tools = [
            {
                "tool_id": tool_id,
                "tier": "tenant-available-not-agent-enabled",
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
            }
            for tool_id in unavailable_tool_ids
        ]

        logger.debug(
            "mcp_agent_unavailable_tools_listed",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            tool_count=len(tools),
        )

        return tools

    async def get_tool_details(
        self, tenant_id: UUID, tool_id: str
    ) -> dict[str, Any] | None:
        """Get detailed information about a specific tool.

        Args:
            tenant_id: Tenant the tool belongs to
            tool_id: Tool identifier

        Returns:
            Tool details or None if not found
        """
        logger.debug(
            "mcp_get_tool_details",
            tenant_id=str(tenant_id),
            tool_id=tool_id,
        )

        # For now, we look up the tool across all activations
        # In the future, this should query ToolDefinition directly
        all_activations = await self._config_store.get_all_tool_activations(tenant_id)

        for activation in all_activations:
            if activation.tool_id == tool_id:
                return {
                    "tool_id": activation.tool_id,
                    "tenant_id": str(activation.tenant_id),
                    "policy_override": activation.policy_override,
                    "status": "enabled" if activation.is_enabled else "disabled",
                }

        logger.debug(
            "mcp_tool_not_found",
            tenant_id=str(tenant_id),
            tool_id=tool_id,
        )

        return None
