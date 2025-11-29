"""Scenario management endpoints."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query

from soldier.alignment.models import Scenario, ScenarioStep, StepTransition
from soldier.api.dependencies import ConfigStoreDep
from soldier.api.exceptions import (
    AgentNotFoundError,
    EntryStepDeletionError,
    ScenarioNotFoundError,
)
from soldier.api.middleware.auth import TenantContextDep
from soldier.api.models.crud import (
    ScenarioCreate,
    ScenarioResponse,
    ScenarioUpdate,
    StepCreate,
    StepResponse,
    StepTransitionResponse,
    StepUpdate,
)
from soldier.api.models.pagination import PaginatedResponse
from soldier.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/scenarios")


def _map_step_to_response(step: ScenarioStep, entry_step_id: UUID) -> StepResponse:
    """Map ScenarioStep to StepResponse."""
    return StepResponse(
        id=step.id,
        name=step.name,
        description=step.description,
        is_entry=step.id == entry_step_id,
        is_terminal=step.is_terminal,
        transitions=[
            StepTransitionResponse(
                condition=t.condition_text,
                to_step_id=t.to_step_id,
            )
            for t in step.transitions
        ],
    )


def _map_scenario_to_response(scenario: Scenario) -> ScenarioResponse:
    """Map Scenario model to ScenarioResponse."""
    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        entry_step_id=scenario.entry_step_id,
        steps=[_map_step_to_response(s, scenario.entry_step_id) for s in scenario.steps],
        tags=scenario.tags,
        enabled=scenario.enabled,
        version=scenario.version,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


async def _verify_agent_exists(
    config_store: ConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant."""
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


async def _get_scenario_or_404(
    config_store: ConfigStoreDep, tenant_id: UUID, agent_id: UUID, scenario_id: UUID
) -> Scenario:
    """Get scenario or raise 404."""
    scenario = await config_store.get_scenario(tenant_id, scenario_id)
    if scenario is None or scenario.agent_id != agent_id:
        raise ScenarioNotFoundError(f"Scenario {scenario_id} not found")
    return scenario


@router.get("", response_model=PaginatedResponse[ScenarioResponse])
async def list_scenarios(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tag: str | None = Query(default=None, description="Filter by tag"),
    enabled: bool | None = Query(default=None),
    sort_by: Literal["name", "created_at", "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> PaginatedResponse[ScenarioResponse]:
    """List scenarios for an agent."""
    logger.debug(
        "list_scenarios_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    scenarios = await config_store.get_scenarios(
        tenant_context.tenant_id, agent_id, enabled_only=False
    )

    # Apply filters
    if tag is not None:
        scenarios = [s for s in scenarios if tag in s.tags]
    if enabled is not None:
        scenarios = [s for s in scenarios if s.enabled == enabled]

    # Apply sorting
    reverse = sort_order == "desc"
    if sort_by == "name":
        scenarios = sorted(scenarios, key=lambda s: s.name.lower(), reverse=reverse)
    elif sort_by == "created_at":
        scenarios = sorted(scenarios, key=lambda s: s.created_at, reverse=reverse)
    elif sort_by == "updated_at":
        scenarios = sorted(scenarios, key=lambda s: s.updated_at, reverse=reverse)

    total = len(scenarios)
    paginated = scenarios[offset : offset + limit]
    items = [_map_scenario_to_response(s) for s in paginated]

    return PaginatedResponse[ScenarioResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated) < total,
    )


@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    agent_id: UUID,
    request: ScenarioCreate,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> ScenarioResponse:
    """Create a new scenario with steps."""
    logger.info(
        "create_scenario_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        name=request.name,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    # Create scenario ID
    scenario_id = uuid4()

    # Build steps with auto-generated IDs if needed
    steps: list[ScenarioStep] = []
    entry_step_id: UUID | None = None

    for i, step_data in enumerate(request.steps):
        step_id = step_data.id or uuid4()
        if i == 0:
            entry_step_id = step_id

        transitions = [
            StepTransition(
                to_step_id=t.to_step_id,
                condition_text=t.condition,
            )
            for t in step_data.transitions
        ]

        step = ScenarioStep(
            id=step_id,
            scenario_id=scenario_id,
            name=step_data.name,
            description=step_data.description,
            is_entry=(i == 0),
            is_terminal=step_data.is_terminal,
            transitions=transitions,
        )
        steps.append(step)

    # If no steps, create a default entry step
    if not steps:
        entry_step_id = uuid4()
        steps.append(
            ScenarioStep(
                id=entry_step_id,
                scenario_id=scenario_id,
                name="Entry",
                is_entry=True,
                is_terminal=True,
            )
        )

    # entry_step_id is guaranteed to be set at this point
    assert entry_step_id is not None

    # Create scenario
    scenario = Scenario(
        id=scenario_id,
        tenant_id=tenant_context.tenant_id,
        agent_id=agent_id,
        name=request.name,
        description=request.description,
        entry_step_id=entry_step_id,
        steps=steps,
        entry_condition_text=request.entry_condition_text,
        tags=request.tags,
        enabled=request.enabled,
    )

    await config_store.save_scenario(scenario)

    logger.info(
        "scenario_created",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        scenario_id=str(scenario.id),
    )

    return _map_scenario_to_response(scenario)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    agent_id: UUID,
    scenario_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> ScenarioResponse:
    """Get a scenario by ID."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )
    return _map_scenario_to_response(scenario)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    agent_id: UUID,
    scenario_id: UUID,
    request: ScenarioUpdate,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> ScenarioResponse:
    """Update a scenario."""
    logger.info(
        "update_scenario_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        scenario_id=str(scenario_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )

    if request.name is not None:
        scenario.name = request.name
    if request.description is not None:
        scenario.description = request.description
    if request.entry_condition_text is not None:
        scenario.entry_condition_text = request.entry_condition_text
    if request.entry_step_id is not None:
        scenario.entry_step_id = request.entry_step_id
    if request.tags is not None:
        scenario.tags = request.tags
    if request.enabled is not None:
        scenario.enabled = request.enabled

    scenario.version += 1
    scenario.touch()
    await config_store.save_scenario(scenario)

    logger.info(
        "scenario_updated",
        tenant_id=str(tenant_context.tenant_id),
        scenario_id=str(scenario_id),
    )

    return _map_scenario_to_response(scenario)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    agent_id: UUID,
    scenario_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> None:
    """Delete a scenario (soft delete)."""
    logger.info(
        "delete_scenario_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        scenario_id=str(scenario_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )

    scenario.soft_delete()
    await config_store.save_scenario(scenario)

    logger.info("scenario_deleted", scenario_id=str(scenario_id))


@router.post("/{scenario_id}/steps", response_model=StepResponse, status_code=201)
async def add_step(
    agent_id: UUID,
    scenario_id: UUID,
    request: StepCreate,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> StepResponse:
    """Add a step to a scenario."""
    logger.info(
        "add_step_request",
        tenant_id=str(tenant_context.tenant_id),
        scenario_id=str(scenario_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )

    step_id = request.id or uuid4()
    transitions = [
        StepTransition(to_step_id=t.to_step_id, condition_text=t.condition)
        for t in request.transitions
    ]

    step = ScenarioStep(
        id=step_id,
        scenario_id=scenario_id,
        name=request.name,
        description=request.description,
        is_terminal=request.is_terminal,
        transitions=transitions,
    )

    scenario.steps.append(step)
    scenario.version += 1
    scenario.touch()
    await config_store.save_scenario(scenario)

    logger.info("step_added", scenario_id=str(scenario_id), step_id=str(step_id))

    return _map_step_to_response(step, scenario.entry_step_id)


@router.put("/{scenario_id}/steps/{step_id}", response_model=StepResponse)
async def update_step(
    agent_id: UUID,
    scenario_id: UUID,
    step_id: UUID,
    request: StepUpdate,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> StepResponse:
    """Update a scenario step."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )

    # Find step
    step = next((s for s in scenario.steps if s.id == step_id), None)
    if step is None:
        raise ScenarioNotFoundError(f"Step {step_id} not found in scenario")

    if request.name is not None:
        step.name = request.name
    if request.description is not None:
        step.description = request.description
    if request.is_terminal is not None:
        step.is_terminal = request.is_terminal
    if request.transitions is not None:
        step.transitions = [
            StepTransition(to_step_id=t.to_step_id, condition_text=t.condition)
            for t in request.transitions
        ]

    scenario.version += 1
    scenario.touch()
    await config_store.save_scenario(scenario)

    return _map_step_to_response(step, scenario.entry_step_id)


@router.delete("/{scenario_id}/steps/{step_id}", status_code=204)
async def delete_step(
    agent_id: UUID,
    scenario_id: UUID,
    step_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
) -> None:
    """Delete a scenario step.

    Cannot delete the entry step.
    """
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)
    scenario = await _get_scenario_or_404(
        config_store, tenant_context.tenant_id, agent_id, scenario_id
    )

    # Cannot delete entry step
    if step_id == scenario.entry_step_id:
        raise EntryStepDeletionError(
            "Cannot delete entry step. Set a different entry step first."
        )

    # Remove step
    scenario.steps = [s for s in scenario.steps if s.id != step_id]
    scenario.version += 1
    scenario.touch()
    await config_store.save_scenario(scenario)

    logger.info("step_deleted", scenario_id=str(scenario_id), step_id=str(step_id))
