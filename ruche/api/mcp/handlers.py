"""MCP resource handlers for tool discovery.

FastAPI route handlers for MCP tool discovery endpoints.
These provide read-only access to tool visibility tiers.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Path

from ruche.api.dependencies import AgentConfigStoreDep
from ruche.api.exceptions import AgentNotFoundError
from ruche.api.mcp.server import MCPToolServer
from ruche.api.middleware.auth import TenantContextDep
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp/tools")


@router.get("/tenant/{tenant_id}/available")
async def list_tenant_available_tools(
    tenant_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> list[dict[str, Any]]:
    """List all tools available to a tenant (Tier 2).

    Returns tools the tenant has connected/purchased, regardless of
    whether any specific agent has them enabled.

    Args:
        tenant_id: Tenant to list tools for
        tenant_context: Authenticated tenant context
        config_store: Configuration store dependency

    Returns:
        List of tenant-available tools
    """
    # Verify tenant access
    if tenant_id != tenant_context.tenant_id:
        raise AgentNotFoundError("Access denied: tenant ID mismatch")

    server = MCPToolServer(config_store)
    return await server.list_tenant_available_tools(tenant_id)


@router.get("/agent/{agent_id}/enabled")
async def list_agent_enabled_tools(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> list[dict[str, Any]]:
    """List tools enabled for a specific agent (Tier 3).

    Returns tools the agent can currently execute.

    Args:
        agent_id: Agent to list tools for
        tenant_context: Authenticated tenant context
        config_store: Configuration store dependency

    Returns:
        List of agent-enabled tools
    """
    # Verify agent exists and belongs to tenant
    agent = await config_store.get_agent(tenant_context.tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")

    server = MCPToolServer(config_store)
    return await server.list_agent_enabled_tools(tenant_context.tenant_id, agent_id)


@router.get("/agent/{agent_id}/unavailable")
async def list_agent_unavailable_tools(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> list[dict[str, Any]]:
    """List tools available to tenant but not enabled for agent.

    These are tools the agent could have access to but currently doesn't.
    Useful for agent awareness: "I could help with X if you enable tool Y".

    Args:
        agent_id: Agent to list tools for
        tenant_context: Authenticated tenant context
        config_store: Configuration store dependency

    Returns:
        List of unavailable tools (Tier 2 - Tier 3)
    """
    # Verify agent exists and belongs to tenant
    agent = await config_store.get_agent(tenant_context.tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")

    server = MCPToolServer(config_store)
    return await server.list_agent_unavailable_tools(
        tenant_context.tenant_id, agent_id
    )


@router.get("/tenant/{tenant_id}/tool/{tool_id}")
async def get_tool_details(
    tenant_id: UUID,
    tool_id: str = Path(..., description="Tool identifier"),
    tenant_context: TenantContextDep = ...,
    config_store: AgentConfigStoreDep = ...,
) -> dict[str, Any]:
    """Get detailed information about a specific tool.

    Args:
        tenant_id: Tenant the tool belongs to
        tool_id: Tool identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store dependency

    Returns:
        Tool details

    Raises:
        AgentNotFoundError: If tool not found or access denied
    """
    # Verify tenant access
    if tenant_id != tenant_context.tenant_id:
        raise AgentNotFoundError("Access denied: tenant ID mismatch")

    server = MCPToolServer(config_store)
    tool = await server.get_tool_details(tenant_id, tool_id)

    if tool is None:
        raise AgentNotFoundError(f"Tool {tool_id} not found")

    return tool
