"""Helper for extracting scenario contributions in the pipeline.

Temporary module to add contribution extraction without modifying pipeline during linting.
"""

from uuid import UUID

from ruche.brains.focal.phases.filtering.models import MatchedRule, ScenarioFilterResult
from ruche.brains.focal.phases.planning.models import (
    ContributionType,
    ScenarioContribution,
    ScenarioContributionPlan,
)
from ruche.brains.focal.stores import AgentConfigStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


async def extract_scenario_contributions(
    scenario_result: ScenarioFilterResult | None,
    tenant_id: UUID,
    matched_rules: list[MatchedRule],
    config_store: AgentConfigStore,
) -> ScenarioContributionPlan:
    """Extract scenario contributions from scenario filter result (P6.4).

    This method determines what the active scenario wants to contribute to the response.
    It examines the current step's metadata to determine contribution type:
    - ASK: Step collects profile fields
    - CONFIRM: Step is a checkpoint requiring confirmation
    - ACTION_HINT: Step has tool bindings
    - INFORM: Step has templates

    Args:
        scenario_result: Result from scenario filtering
        tenant_id: Tenant identifier
        matched_rules: Rules that matched this turn
        config_store: Configuration store for loading scenario data

    Returns:
        ScenarioContributionPlan with contributions from active scenario
    """
    contributions = []

    # If there's an active scenario, extract its contribution
    if scenario_result and scenario_result.scenario_id and scenario_result.target_step_id:
        # Load the scenario and step
        scenario = await config_store.get_scenario(tenant_id, scenario_result.scenario_id)
        if scenario:
            step = next(
                (s for s in scenario.steps if s.id == scenario_result.target_step_id),
                None,
            )
            if step:
                # Determine contribution type based on step metadata
                contribution_type = ContributionType.NONE

                if step.collects_profile_fields:
                    contribution_type = ContributionType.ASK
                elif step.is_checkpoint and step.checkpoint_description:
                    contribution_type = ContributionType.CONFIRM
                elif step.tool_bindings or step.tool_ids:
                    contribution_type = ContributionType.ACTION_HINT
                elif step.template_ids:
                    contribution_type = ContributionType.INFORM

                # Compute priority
                priority = 0
                if contribution_type == ContributionType.ASK:
                    priority = 40
                elif contribution_type == ContributionType.CONFIRM:
                    priority = 50
                elif contribution_type == ContributionType.ACTION_HINT:
                    priority = 30
                elif contribution_type == ContributionType.INFORM:
                    priority = 20

                contribution = ScenarioContribution(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    current_step_id=step.id,
                    current_step_name=step.name,
                    contribution_type=contribution_type,
                    fields_to_ask=step.collects_profile_fields or [],
                    inform_template_id=step.template_ids[0] if step.template_ids else None,
                    action_to_confirm=step.checkpoint_description
                    if step.is_checkpoint
                    else None,
                    suggested_tools=[b.tool_name for b in step.tool_bindings]
                    if step.tool_bindings
                    else step.tool_ids or [],
                    priority=priority,
                )
                contributions.append(contribution)

                logger.debug(
                    "scenario_contribution_extracted",
                    tenant_id=str(tenant_id),
                    scenario_id=str(scenario.id),
                    step_id=str(step.id),
                    contribution_type=contribution_type,
                )

    # Build contribution plan
    plan = ScenarioContributionPlan(contributions=contributions)

    # Set primary scenario if we have contributions
    if contributions:
        plan.primary_scenario_id = contributions[0].scenario_id

    # Set flags
    plan.has_asks = any(
        c.contribution_type == ContributionType.ASK for c in contributions
    )
    plan.has_confirms = any(
        c.contribution_type == ContributionType.CONFIRM for c in contributions
    )
    plan.has_action_hints = any(
        c.contribution_type == ContributionType.ACTION_HINT for c in contributions
    )

    logger.info(
        "scenario_contribution_plan_created",
        tenant_id=str(tenant_id),
        total_contributions=len(contributions),
        has_asks=plan.has_asks,
        has_confirms=plan.has_confirms,
        has_action_hints=plan.has_action_hints,
    )

    return plan
