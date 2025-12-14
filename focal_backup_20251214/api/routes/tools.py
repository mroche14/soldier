"""Tool activation management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from focal.alignment.models import ToolActivation
from focal.api.dependencies import AgentConfigStoreDep
from focal.api.exceptions import AgentNotFoundError, ToolActivationNotFoundError
from focal.api.middleware.auth import TenantContextDep
from focal.api.models.crud import (
    ToolActivationCreate,
    ToolActivationResponse,
    ToolActivationUpdate,
)
from focal.api.models.pagination import PaginatedResponse
from focal.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/tools")


def _map_tool_activation_to_response(activation: ToolActivation) -> ToolActivationResponse:
    """Map ToolActivation model to ToolActivationResponse."""
    return ToolActivationResponse(
        id=activation.id,
        tool_id=activation.tool_id,
        status="enabled" if activation.enabled_at and not activation.disabled_at else "disabled",
        policy_override=activation.policy_override,
        enabled_at=activation.enabled_at,
        disabled_at=activation.disabled_at,
        created_at=activation.created_at,
        updated_at=activation.updated_at,
    )


async def _verify_agent_exists(
    config_store: AgentConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant."""
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


@router.get("", response_model=PaginatedResponse[ToolActivationResponse])
async def list_tool_activations(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Literal["enabled", "disabled"] | None = Query(default=None),
) -> PaginatedResponse[ToolActivationResponse]:
    """List tool activations for an agent."""
    logger.debug(
        "list_tool_activations_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    activations = await config_store.get_tool_activations(
        tenant_context.tenant_id, agent_id
    )

    # Apply status filter
    if status == "enabled":
        activations = [a for a in activations if a.enabled_at and not a.disabled_at]
    elif status == "disabled":
        activations = [a for a in activations if a.disabled_at or not a.enabled_at]

    total = len(activations)
    paginated = activations[offset : offset + limit]
    items = [_map_tool_activation_to_response(a) for a in paginated]

    return PaginatedResponse[ToolActivationResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated) < total,
    )


@router.post("", response_model=ToolActivationResponse, status_code=201)
async def enable_tool(
    agent_id: UUID,
    request: ToolActivationCreate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> ToolActivationResponse:
    """Enable a tool for an agent."""
    logger.info(
        "enable_tool_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        tool_id=request.tool_id,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    # Check if activation already exists
    existing = await config_store.get_tool_activation(
        tenant_context.tenant_id, agent_id, request.tool_id
    )

    if existing:
        # Re-enable existing activation
        existing.enable()
        if request.policy_override is not None:
            existing.policy_override = request.policy_override
        await config_store.save_tool_activation(existing)
        return _map_tool_activation_to_response(existing)

    # Create new activation
    activation = ToolActivation.create(
        tenant_id=tenant_context.tenant_id,
        agent_id=agent_id,
        tool_id=request.tool_id,
        policy_override=request.policy_override,
    )

    await config_store.save_tool_activation(activation)

    logger.info(
        "tool_enabled",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        tool_id=request.tool_id,
    )

    return _map_tool_activation_to_response(activation)


@router.put("/{tool_id}", response_model=ToolActivationResponse)
async def update_tool_activation(
    agent_id: UUID,
    tool_id: str,
    request: ToolActivationUpdate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> ToolActivationResponse:
    """Update a tool activation (policy override)."""
    logger.info(
        "update_tool_activation_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        tool_id=tool_id,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    activation = await config_store.get_tool_activation(
        tenant_context.tenant_id, agent_id, tool_id
    )
    if activation is None:
        raise ToolActivationNotFoundError(f"Tool activation for {tool_id} not found")

    if request.policy_override is not None:
        activation.policy_override = request.policy_override

    activation.touch()
    await config_store.save_tool_activation(activation)

    logger.info("tool_activation_updated", tool_id=tool_id)

    return _map_tool_activation_to_response(activation)


@router.delete("/{tool_id}", status_code=204)
async def disable_tool(
    agent_id: UUID,
    tool_id: str,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> None:
    """Disable a tool for an agent."""
    logger.info(
        "disable_tool_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        tool_id=tool_id,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    activation = await config_store.get_tool_activation(
        tenant_context.tenant_id, agent_id, tool_id
    )
    if activation is None:
        raise ToolActivationNotFoundError(f"Tool activation for {tool_id} not found")

    activation.disable()
    await config_store.save_tool_activation(activation)

    logger.info("tool_disabled", tool_id=tool_id)
