"""Tool binding collection from scenarios and rules."""

from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.models.tool_binding import ToolBinding
from ruche.alignment.planning.models import ScenarioContributionPlan
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ToolBindingCollector:
    """Collects tool bindings from scenarios and rules.

    Collection order:
    1. Rules (GLOBAL → SCENARIO → STEP)
    2. Scenario steps (current + contributing)

    Deduplicates by (tool_id, when) tuple.
    """

    async def collect_bindings(
        self,
        contribution_plan: ScenarioContributionPlan,
        applied_rules: list[MatchedRule],
        scenario_steps: dict[tuple[object, object], object] | None = None,
    ) -> list[ToolBinding]:
        """Collect all tool bindings from contributing scenarios and rules.

        Args:
            contribution_plan: Plan from Phase 6 scenario orchestration
            applied_rules: Rules from Phase 5
            scenario_steps: Map of (scenario_id, step_id) -> ScenarioStep (optional)

        Returns:
            Deduplicated list of ToolBinding
        """
        bindings: dict[tuple[str, str], ToolBinding] = {}

        # Collect from rules (prioritize rule bindings)
        for matched in applied_rules:
            rule = matched.rule

            # Prefer new tool_bindings
            if rule.tool_bindings:
                for binding in rule.tool_bindings:
                    key = (binding.tool_id, binding.when)
                    if key not in bindings:
                        bindings[key] = binding

            # Fall back to legacy attached_tool_ids
            elif rule.attached_tool_ids:
                logger.warning(
                    "using_legacy_attached_tool_ids",
                    rule_id=str(rule.id),
                    tool_count=len(rule.attached_tool_ids),
                )
                for tool_id in rule.attached_tool_ids:
                    key = (tool_id, "DURING_STEP")
                    if key not in bindings:
                        bindings[key] = ToolBinding(
                            tool_id=tool_id,
                            when="DURING_STEP",
                            required_variables=[],
                            depends_on=[],
                        )

        # Collect from scenario steps if provided
        if scenario_steps:
            for contribution in contribution_plan.contributions:
                step_key = (contribution.scenario_id, contribution.current_step_id)
                step = scenario_steps.get(step_key)

                if step:
                    # Prefer new tool_bindings
                    if hasattr(step, "tool_bindings") and step.tool_bindings:
                        for binding in step.tool_bindings:
                            key = (binding.tool_id, binding.when)
                            if key not in bindings:
                                bindings[key] = binding

                    # Fall back to legacy tool_ids
                    elif hasattr(step, "tool_ids") and step.tool_ids:
                        logger.warning(
                            "using_legacy_tool_ids",
                            scenario_id=str(contribution.scenario_id),
                            step_id=str(contribution.current_step_id),
                            tool_count=len(step.tool_ids),
                        )
                        for tool_id in step.tool_ids:
                            key = (tool_id, "DURING_STEP")
                            if key not in bindings:
                                bindings[key] = ToolBinding(
                                    tool_id=tool_id,
                                    when="DURING_STEP",
                                    required_variables=[],
                                    depends_on=[],
                                )

        result = list(bindings.values())

        logger.info(
            "collected_tool_bindings",
            total_bindings=len(result),
            from_rules=sum(1 for m in applied_rules if m.rule.tool_bindings or m.rule.attached_tool_ids),
            from_scenarios=len(scenario_steps) if scenario_steps else 0,
        )

        return result
