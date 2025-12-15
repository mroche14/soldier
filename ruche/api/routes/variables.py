"""Variable management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from ruche.brains.focal.models import Variable
from ruche.api.dependencies import AgentConfigStoreDep
from ruche.api.exceptions import AgentNotFoundError, VariableNotFoundError
from ruche.api.middleware.auth import TenantContextDep
from ruche.api.models.crud import VariableCreate, VariableResponse, VariableUpdate
from ruche.api.models.pagination import PaginatedResponse
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/variables")


def _map_variable_to_response(variable: Variable) -> VariableResponse:
    """Map Variable model to VariableResponse."""
    return VariableResponse(
        id=variable.id,
        name=variable.name,
        description=variable.description,
        resolver_tool_id=variable.resolver_tool_id,
        update_policy=variable.update_policy,
        cache_ttl_seconds=variable.cache_ttl_seconds,
        created_at=variable.created_at,
        updated_at=variable.updated_at,
    )


async def _verify_agent_exists(
    config_store: AgentConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant."""
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


@router.get("", response_model=PaginatedResponse[VariableResponse])
async def list_variables(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["name", "created_at", "updated_at"] = Query(default="name"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
) -> PaginatedResponse[VariableResponse]:
    """List variables for an agent."""
    logger.debug(
        "list_variables_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    variables = await config_store.get_variables(tenant_context.tenant_id, agent_id)

    # Apply sorting
    reverse = sort_order == "desc"
    if sort_by == "name":
        variables = sorted(variables, key=lambda v: v.name.lower(), reverse=reverse)
    elif sort_by == "created_at":
        variables = sorted(variables, key=lambda v: v.created_at, reverse=reverse)
    elif sort_by == "updated_at":
        variables = sorted(variables, key=lambda v: v.updated_at, reverse=reverse)

    total = len(variables)
    paginated = variables[offset : offset + limit]
    items = [_map_variable_to_response(v) for v in paginated]

    return PaginatedResponse[VariableResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated) < total,
    )


@router.post("", response_model=VariableResponse, status_code=201)
async def create_variable(
    agent_id: UUID,
    request: VariableCreate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> VariableResponse:
    """Create a new variable."""
    logger.info(
        "create_variable_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        name=request.name,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    variable = Variable(
        tenant_id=tenant_context.tenant_id,
        agent_id=agent_id,
        name=request.name,
        description=request.description,
        resolver_tool_id=request.resolver_tool_id or "",
        update_policy=request.update_policy,
        cache_ttl_seconds=request.cache_ttl_seconds,
    )

    await config_store.save_variable(variable)

    logger.info(
        "variable_created",
        tenant_id=str(tenant_context.tenant_id),
        variable_id=str(variable.id),
    )

    return _map_variable_to_response(variable)


@router.get("/{variable_id}", response_model=VariableResponse)
async def get_variable(
    agent_id: UUID,
    variable_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> VariableResponse:
    """Get a variable by ID."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    variable = await config_store.get_variable(tenant_context.tenant_id, variable_id)
    if variable is None or variable.agent_id != agent_id:
        raise VariableNotFoundError(f"Variable {variable_id} not found")

    return _map_variable_to_response(variable)


@router.put("/{variable_id}", response_model=VariableResponse)
async def update_variable(
    agent_id: UUID,
    variable_id: UUID,
    request: VariableUpdate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> VariableResponse:
    """Update a variable."""
    logger.info(
        "update_variable_request",
        tenant_id=str(tenant_context.tenant_id),
        variable_id=str(variable_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    variable = await config_store.get_variable(tenant_context.tenant_id, variable_id)
    if variable is None or variable.agent_id != agent_id:
        raise VariableNotFoundError(f"Variable {variable_id} not found")

    if request.description is not None:
        variable.description = request.description
    if request.resolver_tool_id is not None:
        variable.resolver_tool_id = request.resolver_tool_id
    if request.update_policy is not None:
        variable.update_policy = request.update_policy
    if request.cache_ttl_seconds is not None:
        variable.cache_ttl_seconds = request.cache_ttl_seconds

    variable.touch()
    await config_store.save_variable(variable)

    logger.info("variable_updated", variable_id=str(variable_id))

    return _map_variable_to_response(variable)


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    agent_id: UUID,
    variable_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> None:
    """Delete a variable (soft delete)."""
    logger.info(
        "delete_variable_request",
        tenant_id=str(tenant_context.tenant_id),
        variable_id=str(variable_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    variable = await config_store.get_variable(tenant_context.tenant_id, variable_id)
    if variable is None or variable.agent_id != agent_id:
        raise VariableNotFoundError(f"Variable {variable_id} not found")

    variable.soft_delete()
    await config_store.save_variable(variable)

    logger.info("variable_deleted", variable_id=str(variable_id))
