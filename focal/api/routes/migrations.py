"""Migration API routes.

Provides endpoints for managing scenario migrations:
- Generate migration plans
- Review and configure policies
- Approve/reject plans
- Deploy migrations
- Monitor deployment status
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from focal.alignment.migration.models import (
    AnchorMigrationPolicy,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationSummary,
)
from focal.alignment.migration.planner import MigrationDeployer, MigrationPlanner
from focal.alignment.models import Scenario, ScenarioStep, StepTransition
from focal.alignment.stores import AgentConfigStore
from focal.api.dependencies import get_config_store, get_session_store, get_settings
from focal.conversation.store import SessionStore
from focal.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/migrations")


# =============================================================================
# Request/Response Models
# =============================================================================


class TransitionInput(BaseModel):
    """Input for a step transition."""

    to_step_id: UUID
    condition_text: str = ""
    priority: int = 0
    condition_fields: list[str] = Field(default_factory=list)


class ScenarioStepInput(BaseModel):
    """Input for a scenario step."""

    id: UUID
    name: str
    description: str | None = None
    transitions: list[TransitionInput] = Field(default_factory=list)
    rule_ids: list[UUID] = Field(default_factory=list)
    collects_profile_fields: list[str] = Field(default_factory=list)
    is_checkpoint: bool = False
    checkpoint_description: str | None = None
    is_entry: bool = False
    is_terminal: bool = False
    performs_action: bool = False
    is_required_action: bool = False


class ScenarioInput(BaseModel):
    """Input for a new scenario version."""

    name: str
    description: str | None = None
    version: int
    entry_step_id: UUID
    steps: list[ScenarioStepInput] = Field(default_factory=list)


class GenerateMigrationPlanRequest(BaseModel):
    """Request to generate a migration plan."""

    new_scenario: ScenarioInput
    created_by: str | None = None


class ApprovePlanRequest(BaseModel):
    """Request to approve a plan."""

    approved_by: str | None = None


class RejectPlanRequest(BaseModel):
    """Request to reject a plan."""

    rejected_by: str | None = None
    reason: str | None = None


class UpdatePoliciesRequest(BaseModel):
    """Request to update anchor policies."""

    policies: dict[str, AnchorMigrationPolicy]


class MigrationPlanSummaryItem(BaseModel):
    """Summary item for list view."""

    id: UUID
    scenario_id: UUID
    scenario_name: str | None = None
    from_version: int
    to_version: int
    status: MigrationPlanStatus
    total_anchors: int
    estimated_sessions_affected: int
    warning_count: int
    created_at: datetime


class DeploymentResult(BaseModel):
    """Result of deployment operation."""

    plan_id: UUID
    sessions_marked: int
    sessions_by_anchor: dict[str, int]
    deployed_at: datetime | None


class DeploymentStatus(BaseModel):
    """Current deployment status."""

    plan_id: UUID
    status: str
    sessions_marked: int
    migrations_applied: int
    migrations_pending: int
    migrations_by_scenario: dict[str, int]
    checkpoint_blocks: int
    deployed_at: datetime | None
    last_migration_at: datetime | None


# =============================================================================
# Helper Functions
# =============================================================================


def _convert_scenario_input(
    input_data: ScenarioInput,
    tenant_id: UUID,
    agent_id: UUID,
) -> Scenario:
    """Convert ScenarioInput to Scenario model."""
    steps = []
    for step_input in input_data.steps:
        transitions = [
            StepTransition(
                to_step_id=t.to_step_id,
                condition_text=t.condition_text,
                priority=t.priority,
                condition_fields=t.condition_fields,
            )
            for t in step_input.transitions
        ]
        step = ScenarioStep(
            id=step_input.id,
            scenario_id=UUID(int=0),  # Will be set below
            name=step_input.name,
            description=step_input.description,
            transitions=transitions,
            rule_ids=step_input.rule_ids,
            collects_profile_fields=step_input.collects_profile_fields,
            is_checkpoint=step_input.is_checkpoint,
            checkpoint_description=step_input.checkpoint_description,
            is_entry=step_input.is_entry,
            is_terminal=step_input.is_terminal,
            performs_action=step_input.performs_action,
            is_required_action=step_input.is_required_action,
        )
        steps.append(step)

    scenario = Scenario(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=input_data.name,
        description=input_data.description,
        version=input_data.version,
        entry_step_id=input_data.entry_step_id,
        steps=steps,
    )

    # Update step scenario_ids
    for step in scenario.steps:
        step.scenario_id = scenario.id

    return scenario


async def _get_planner(
    config_store: AgentConfigStore,
    session_store: SessionStore,
) -> MigrationPlanner:
    """Get configured MigrationPlanner instance."""
    settings = get_settings()
    return MigrationPlanner(
        config_store=config_store,
        session_store=session_store,
        config=settings.scenario_migration,
    )


async def _get_deployer(
    config_store: AgentConfigStore,
    session_store: SessionStore,
) -> MigrationDeployer:
    """Get configured MigrationDeployer instance."""
    settings = get_settings()
    return MigrationDeployer(
        config_store=config_store,
        session_store=session_store,
        config=settings.scenario_migration,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/scenarios/{scenario_id}/migration-plan",
    response_model=MigrationPlan,
    status_code=status.HTTP_201_CREATED,
)
async def generate_migration_plan(
    scenario_id: UUID,
    request: GenerateMigrationPlanRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> MigrationPlan:
    """Generate a migration plan for a scenario update.

    Computes the graph diff, identifies anchors, and determines
    migration scenarios (Clean Graft, Gap Fill, Re-Route) for each anchor.
    """
    try:
        # Get current scenario to determine agent_id
        current_scenario = await config_store.get_scenario(x_tenant_id, scenario_id)
        if not current_scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Convert input to Scenario model
        new_scenario = _convert_scenario_input(
            request.new_scenario,
            x_tenant_id,
            current_scenario.agent_id,
        )
        # Override ID to match existing scenario
        new_scenario.id = scenario_id

        planner = await _get_planner(config_store, session_store)
        plan = await planner.generate_plan(
            tenant_id=x_tenant_id,
            scenario_id=scenario_id,
            new_scenario=new_scenario,
            created_by=request.created_by,
        )

        return plan

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None


@router.get("/migration-plans", response_model=dict)
async def list_migration_plans(
    scenario_id: UUID | None = None,
    plan_status: MigrationPlanStatus | None = None,
    limit: int = 50,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
) -> dict[str, Any]:
    """List migration plans for a tenant."""
    plans = await config_store.list_migration_plans(
        tenant_id=x_tenant_id,
        scenario_id=scenario_id,
        status=plan_status,
        limit=limit,
    )

    items = [
        MigrationPlanSummaryItem(
            id=p.id,
            scenario_id=p.scenario_id,
            from_version=p.from_version,
            to_version=p.to_version,
            status=p.status,
            total_anchors=p.summary.total_anchors,
            estimated_sessions_affected=p.summary.estimated_sessions_affected,
            warning_count=len(p.summary.warnings),
            created_at=p.created_at,
        )
        for p in plans
    ]

    return {"plans": items, "total": len(items)}


@router.get("/migration-plans/{plan_id}", response_model=MigrationPlan)
async def get_migration_plan(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
) -> MigrationPlan:
    """Get full details of a migration plan."""
    plan = await config_store.get_migration_plan(x_tenant_id, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration plan {plan_id} not found",
        )
    return plan


@router.get("/migration-plans/{plan_id}/summary", response_model=MigrationSummary)
async def get_migration_summary(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
) -> MigrationSummary:
    """Get operator-friendly summary of a migration plan."""
    plan = await config_store.get_migration_plan(x_tenant_id, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration plan {plan_id} not found",
        )
    return plan.summary


@router.put("/migration-plans/{plan_id}/policies", response_model=MigrationPlan)
async def update_anchor_policies(
    plan_id: UUID,
    request: UpdatePoliciesRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> MigrationPlan:
    """Update per-anchor migration policies."""
    try:
        planner = await _get_planner(config_store, session_store)
        plan = await planner.update_policies(
            tenant_id=x_tenant_id,
            plan_id=plan_id,
            policies=request.policies,
        )
        return plan

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None


@router.post("/migration-plans/{plan_id}/approve", response_model=MigrationPlan)
async def approve_migration_plan(
    plan_id: UUID,
    request: ApprovePlanRequest | None = None,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> MigrationPlan:
    """Approve a migration plan for deployment."""
    try:
        planner = await _get_planner(config_store, session_store)
        approved_by = request.approved_by if request else None
        plan = await planner.approve_plan(
            tenant_id=x_tenant_id,
            plan_id=plan_id,
            approved_by=approved_by,
        )
        return plan

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None


@router.post("/migration-plans/{plan_id}/reject", response_model=MigrationPlan)
async def reject_migration_plan(
    plan_id: UUID,
    request: RejectPlanRequest | None = None,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> MigrationPlan:
    """Reject a migration plan."""
    try:
        planner = await _get_planner(config_store, session_store)
        rejected_by = request.rejected_by if request else None
        reason = request.reason if request else None
        plan = await planner.reject_plan(
            tenant_id=x_tenant_id,
            plan_id=plan_id,
            rejected_by=rejected_by,
            reason=reason,
        )
        return plan

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None


@router.post("/migration-plans/{plan_id}/deploy", response_model=DeploymentResult)
async def deploy_migration_plan(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> DeploymentResult:
    """Deploy an approved migration plan.

    Marks eligible sessions with pending_migration flag.
    Migrations are applied JIT at next customer message.
    """
    try:
        deployer = await _get_deployer(config_store, session_store)
        result = await deployer.deploy(
            tenant_id=x_tenant_id,
            plan_id=plan_id,
        )

        return DeploymentResult(
            plan_id=result["plan_id"],
            sessions_marked=result["sessions_marked"],
            sessions_by_anchor=result["sessions_by_anchor"],
            deployed_at=result["deployed_at"],
        )

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None


@router.get(
    "/migration-plans/{plan_id}/deployment-status",
    response_model=DeploymentStatus,
)
async def get_deployment_status(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: AgentConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store),
) -> DeploymentStatus:
    """Get current deployment status."""
    try:
        deployer = await _get_deployer(config_store, session_store)
        result = await deployer.get_deployment_status(
            tenant_id=x_tenant_id,
            plan_id=plan_id,
        )

        return DeploymentStatus(
            plan_id=result["plan_id"],
            status=result["status"],
            sessions_marked=result["sessions_marked"],
            migrations_applied=result["migrations_applied"],
            migrations_pending=result["migrations_pending"],
            migrations_by_scenario=result["migrations_by_scenario"],
            checkpoint_blocks=result["checkpoint_blocks"],
            deployed_at=result["deployed_at"],
            last_migration_at=result["last_migration_at"],
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
