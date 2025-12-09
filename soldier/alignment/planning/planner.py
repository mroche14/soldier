"""Response planning logic for Phase 8.

Builds ResponsePlan from scenario contributions and rule constraints.
"""

from typing import Any

from soldier.alignment.context.situation_snapshot import SituationSnapshot
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.planning.models import (
    ResponsePlan,
    ResponseType,
    RuleConstraint,
    ScenarioContributionPlan,
)
from soldier.observability.logging import get_logger
from soldier.observability.metrics import (
    constraints_extracted_counter,
    response_planning_duration,
    response_type_counter,
    scenario_contributions_gauge,
)


class ResponsePlanner:
    """Builds ResponsePlan from scenario contributions and rule constraints."""

    def __init__(self):
        """Initialize response planner."""
        self._logger = get_logger(__name__)

    async def build_response_plan(
        self,
        scenario_contribution_plan: ScenarioContributionPlan,
        matched_rules: list[MatchedRule],
        tool_results: dict[str, Any],
        snapshot: SituationSnapshot,
        tenant_id: str | None = None,
    ) -> ResponsePlan:
        """Build complete response plan (P8.1-P8.5).

        Args:
            scenario_contribution_plan: What scenarios want to contribute
            matched_rules: Rules that matched this turn
            tool_results: Results from tool execution
            context: Turn context
            tenant_id: Tenant ID for metrics

        Returns:
            Complete ResponsePlan for generation
        """
        with response_planning_duration.labels(tenant_id=tenant_id or "unknown").time():
            # P8.1: Determine global response type
            response_type = self._determine_response_type(
                scenario_contribution_plan, matched_rules, tool_results
            )
            response_type_counter.labels(
                type=response_type.value, tenant_id=tenant_id or "unknown"
            ).inc()

            self._logger.info(
                "response_type_determined",
                response_type=response_type.value,
                num_rules=len(matched_rules),
                num_contributions=len(scenario_contribution_plan.contributions),
            )

            # P8.2: Collect step-level templates
            template_ids = self._collect_templates(scenario_contribution_plan)

            self._logger.debug(
                "templates_collected",
                num_templates=len(template_ids),
                template_ids=template_ids,
            )

            # P8.3: Build per-scenario contribution plan (already provided)
            # P8.4: Synthesize global ResponsePlan
            plan = self._synthesize_plan(
                response_type, template_ids, scenario_contribution_plan
            )

            scenario_contributions_gauge.labels(tenant_id=tenant_id or "unknown").observe(
                len(scenario_contribution_plan.contributions)
            )

            self._logger.debug(
                "plan_synthesized",
                num_bullet_points=len(plan.bullet_points),
                num_scenarios=len(plan.scenario_contributions),
            )

            # P8.5: Inject explicit constraints
            plan = self._inject_constraints(plan, matched_rules)

            # Track constraint extraction metrics
            for constraint in plan.constraints_from_rules:
                constraints_extracted_counter.labels(
                    constraint_type=constraint.constraint_type,
                    tenant_id=tenant_id or "unknown",
                ).inc()

            self._logger.info(
                "response_plan_built",
                response_type=response_type.value,
                num_templates=len(template_ids),
                num_contributions=len(scenario_contribution_plan.contributions),
                num_must_include=len(plan.must_include),
                num_must_avoid=len(plan.must_avoid),
                num_constraints=len(plan.constraints_from_rules),
            )

        return plan

    def _determine_response_type(
        self,
        scenario_contribution_plan: ScenarioContributionPlan,
        matched_rules: list[MatchedRule],
        tool_results: dict[str, Any],
    ) -> ResponseType:
        """Determine overall response type based on scenarios and rules.

        Logic priority: ESCALATE > HANDOFF > ASK > REFUSE > CONFIRM > MIXED > ANSWER

        Args:
            scenario_contribution_plan: Scenario contributions
            matched_rules: Matched rules
            tool_results: Tool execution results

        Returns:
            Global response type
        """
        # Check for escalation rules
        for matched in matched_rules:
            rule = matched.rule
            if "escalate" in rule.action_text.lower():
                return ResponseType.ESCALATE

        # Check for handoff rules
        for matched in matched_rules:
            rule = matched.rule
            if "handoff" in rule.action_text.lower() or "transfer" in rule.action_text.lower():
                return ResponseType.HANDOFF

        # Check for mixed (both asking and informing)
        has_inform = any(
            c.contribution_type.value == "inform"
            for c in scenario_contribution_plan.contributions
        )
        if scenario_contribution_plan.has_asks and has_inform:
            return ResponseType.MIXED

        # Check if any scenario is asking for data (only if not mixed)
        if scenario_contribution_plan.has_asks:
            return ResponseType.ASK

        # Check if any scenario needs confirmation
        if scenario_contribution_plan.has_confirms:
            return ResponseType.CONFIRM

        # Default to ANSWER
        return ResponseType.ANSWER

    def _collect_templates(
        self, scenario_contribution_plan: ScenarioContributionPlan
    ) -> list[str]:
        """Collect template IDs from active scenario steps.

        Args:
            scenario_contribution_plan: Scenario contributions

        Returns:
            List of template IDs (may be empty)
        """
        template_ids = []
        for contribution in scenario_contribution_plan.contributions:
            if contribution.inform_template_id:
                template_ids.append(str(contribution.inform_template_id))
        return template_ids

    def _synthesize_plan(
        self,
        response_type: ResponseType,
        template_ids: list[str],
        scenario_contribution_plan: ScenarioContributionPlan,
    ) -> ResponsePlan:
        """Merge scenario contributions into a unified plan.

        Args:
            response_type: Global response type
            template_ids: Collected template IDs
            scenario_contribution_plan: Scenario contributions

        Returns:
            Synthesized ResponsePlan
        """
        # Sort contributions by priority (higher first)
        sorted_contributions = sorted(
            scenario_contribution_plan.contributions,
            key=lambda c: (-c.priority, str(c.scenario_id)),
        )

        # Build bullet points from contributions
        bullet_points = []
        for contribution in sorted_contributions:
            if contribution.contribution_type.value == "ask":
                bullet_points.append(
                    f"Ask for: {', '.join(contribution.fields_to_ask)}"
                )
            elif contribution.contribution_type.value == "inform":
                bullet_points.append(f"Inform about {contribution.current_step_name}")
            elif contribution.contribution_type.value == "confirm":
                if contribution.action_to_confirm:
                    bullet_points.append(f"Confirm: {contribution.action_to_confirm}")
            elif contribution.contribution_type.value == "action_hint":
                bullet_points.append(
                    f"Suggest tools: {', '.join(contribution.suggested_tools)}"
                )

        # Build scenario_contributions dict for debugging
        scenario_dict = {
            str(c.scenario_id): {
                "step_id": str(c.current_step_id),
                "step_name": c.current_step_name,
                "type": c.contribution_type.value,
                "priority": c.priority,
            }
            for c in sorted_contributions
        }

        return ResponsePlan(
            global_response_type=response_type,
            template_ids=template_ids,
            bullet_points=bullet_points,
            scenario_contributions=scenario_dict,
        )

    def _inject_constraints(
        self, plan: ResponsePlan, matched_rules: list[MatchedRule]
    ) -> ResponsePlan:
        """Extract and inject constraints from rules.

        Extracts:
        - must_include: Phrases/facts that MUST appear in response
        - must_avoid: Topics/phrases to avoid
        - constraints_from_rules: Full constraint objects for enforcement

        Args:
            plan: Initial response plan
            matched_rules: Matched rules

        Returns:
            Plan with injected constraints
        """
        for matched in matched_rules:
            rule = matched.rule

            # Extract must_include from rule.action_text
            must_include = self._extract_must_include(rule.action_text)
            plan.must_include.extend(must_include)

            # Extract must_avoid from rule.action_text
            must_avoid = self._extract_must_avoid(rule.action_text)
            plan.must_avoid.extend(must_avoid)

            # Build RuleConstraint objects for hard constraints
            if rule.is_hard_constraint:
                if must_include:
                    constraint = RuleConstraint(
                        rule_id=str(rule.id),
                        constraint_type="must_include",
                        text=rule.action_text,
                        priority=rule.priority,
                    )
                    plan.constraints_from_rules.append(constraint)
                if must_avoid:
                    constraint = RuleConstraint(
                        rule_id=str(rule.id),
                        constraint_type="must_avoid",
                        text=rule.action_text,
                        priority=rule.priority,
                    )
                    plan.constraints_from_rules.append(constraint)

        return plan

    def _extract_must_include(self, action_text: str) -> list[str]:
        """Extract must_include phrases from rule action text.

        Looks for patterns like:
        - "mention X"
        - "include Y"
        - "state that Z"
        - "must say X"

        Args:
            action_text: Rule action text

        Returns:
            List of phrases that must be included
        """
        must_include = []
        lower_text = action_text.lower()

        # Simple keyword-based extraction
        if "mention" in lower_text or "include" in lower_text or "must say" in lower_text:
            # For now, just include the full action text
            # A more sophisticated implementation would parse out specific phrases
            must_include.append(action_text)

        return must_include

    def _extract_must_avoid(self, action_text: str) -> list[str]:
        """Extract must_avoid phrases from rule action text.

        Looks for patterns like:
        - "never mention X"
        - "avoid Y"
        - "don't say Z"
        - "do not discuss X"

        Args:
            action_text: Rule action text

        Returns:
            List of phrases/topics to avoid
        """
        must_avoid = []
        lower_text = action_text.lower()

        # Simple keyword-based extraction
        if (
            "never" in lower_text
            or "avoid" in lower_text
            or "don't" in lower_text
            or "do not" in lower_text
        ):
            # For now, just include the full action text
            # A more sophisticated implementation would parse out specific phrases
            must_avoid.append(action_text)

        return must_avoid
