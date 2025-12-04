"""Agent management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from soldier.alignment.models import Agent, AgentSettings
from soldier.api.dependencies import AgentConfigStoreDep
from soldier.api.exceptions import AgentNotFoundError
from soldier.api.middleware.auth import TenantContextDep
from soldier.api.models.crud import AgentCreate, AgentResponse, AgentStats, AgentUpdate
from soldier.api.models.pagination import PaginatedResponse
from soldier.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents")


def _map_agent_to_response(agent: Agent, stats: AgentStats | None = None) -> AgentResponse:
    """Map Agent model to AgentResponse.

    Args:
        agent: Agent domain model
        stats: Optional usage statistics

    Returns:
        AgentResponse for API
    """
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        enabled=agent.enabled,
        current_version=agent.current_version,
        settings=agent.settings,
        stats=stats,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    sort_by: Literal["name", "created_at", "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> PaginatedResponse[AgentResponse]:
    """List agents for the tenant.

    Retrieve a paginated list of agents with optional filtering and sorting.

    Args:
        tenant_context: Authenticated tenant context
        config_store: Configuration store
        limit: Maximum number of agents to return (1-100)
        offset: Number of agents to skip
        enabled: Filter by enabled status
        sort_by: Field to sort by
        sort_order: Sort direction

    Returns:
        Paginated list of agents
    """
    logger.debug(
        "list_agents_request",
        tenant_id=str(tenant_context.tenant_id),
        limit=limit,
        offset=offset,
        enabled=enabled,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get all agents for tenant (no pagination from store - we sort first)
    # Use large limit to get all, then apply our own sorting/pagination
    all_agents, _ = await config_store.get_agents(
        tenant_context.tenant_id, enabled_only=False, limit=10000, offset=0
    )

    # Apply enabled filter
    if enabled is not None:
        all_agents = [a for a in all_agents if a.enabled == enabled]

    # Apply sorting
    reverse = sort_order == "desc"
    if sort_by == "name":
        all_agents = sorted(all_agents, key=lambda a: a.name.lower(), reverse=reverse)
    elif sort_by == "created_at":
        all_agents = sorted(all_agents, key=lambda a: a.created_at, reverse=reverse)
    elif sort_by == "updated_at":
        all_agents = sorted(all_agents, key=lambda a: a.updated_at, reverse=reverse)

    # Get total before pagination
    total = len(all_agents)

    # Apply pagination
    agents = all_agents[offset : offset + limit]

    # Map to response
    items = [_map_agent_to_response(agent) for agent in agents]

    return PaginatedResponse[AgentResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(agents) < total,
    )


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    request: AgentCreate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> AgentResponse:
    """Create a new agent.

    Args:
        request: Agent creation request
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Returns:
        Created agent
    """
    logger.info(
        "create_agent_request",
        tenant_id=str(tenant_context.tenant_id),
        name=request.name,
    )

    # Create agent with defaults
    agent = Agent.create(
        tenant_id=tenant_context.tenant_id,
        name=request.name,
        description=request.description,
        settings=request.settings or AgentSettings(),
    )

    # Save to store
    await config_store.save_agent(agent)

    logger.info(
        "agent_created",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent.id),
        name=agent.name,
    )

    return _map_agent_to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    include_stats: bool = Query(default=False, description="Include usage statistics"),
) -> AgentResponse:
    """Get an agent by ID.

    Args:
        agent_id: Agent identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store
        include_stats: Whether to include usage statistics

    Returns:
        Agent details

    Raises:
        AgentNotFoundError: If agent doesn't exist or belongs to different tenant
    """
    logger.debug(
        "get_agent_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    agent = await config_store.get_agent(tenant_context.tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")

    # Build stats if requested
    stats = None
    if include_stats:
        # For MVP, return zero stats - production would query audit store
        stats = AgentStats(
            total_sessions=0,
            total_turns=0,
            avg_turns_per_session=0.0,
        )

    return _map_agent_to_response(agent, stats)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    request: AgentUpdate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> AgentResponse:
    """Update an agent.

    Args:
        agent_id: Agent identifier
        request: Agent update request
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Returns:
        Updated agent

    Raises:
        AgentNotFoundError: If agent doesn't exist or belongs to different tenant
    """
    logger.info(
        "update_agent_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    agent = await config_store.get_agent(tenant_context.tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")

    # Apply updates
    if request.name is not None:
        agent.name = request.name
    if request.description is not None:
        agent.description = request.description
    if request.enabled is not None:
        agent.enabled = request.enabled
    if request.settings is not None:
        agent.settings = request.settings

    # Touch updated_at
    agent.touch()

    # Save changes
    await config_store.save_agent(agent)

    logger.info(
        "agent_updated",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    return _map_agent_to_response(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> None:
    """Delete an agent (soft delete).

    This performs a soft delete by setting deleted_at timestamp.
    The agent will no longer respond to requests.

    Args:
        agent_id: Agent identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Raises:
        AgentNotFoundError: If agent doesn't exist or belongs to different tenant
    """
    logger.info(
        "delete_agent_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    agent = await config_store.get_agent(tenant_context.tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")

    # Soft delete
    agent.soft_delete()
    await config_store.save_agent(agent)

    logger.info(
        "agent_deleted",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )
