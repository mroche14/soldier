"""Scenario orchestration for multi-scenario coordination.

Handles lifecycle decisions, step transitions, and contribution planning
for multiple simultaneously active scenarios.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from ruche.alignment.context.models import ScenarioSignal
from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.filtering.models import (
    ScenarioLifecycleAction,
    ScenarioLifecycleDecision,
    ScenarioStepTransitionDecision,
)
from ruche.alignment.models import Rule
from ruche.alignment.planning.models import (
    ContributionType,
    ScenarioContribution,
    ScenarioContributionPlan,
)
from ruche.alignment.retrieval.models import ScoredScenario
from ruche.alignment.stores import AgentConfigStore
from ruche.conversation.models.session import ScenarioInstance
from ruche.observability.logging import get_logger
from ruche.observability.metrics import (
    ACTIVE_SCENARIOS_PER_SESSION,
    SCENARIO_CONTRIBUTIONS,
    SCENARIO_LIFECYCLE_DECISIONS,
)

if TYPE_CHECKING:
    from ruche.customer_data.models import CustomerDataStore
    from ruche.customer_data.store import CustomerDataStoreInterface

logger = get_logger(__name__)


class ScenarioOrchestrator:
    """Orchestrates multiple simultaneous scenarios.

    Replaces single-scenario ScenarioFilter for multi-scenario support.
    Handles lifecycle decisions, step transitions, and contribution planning.
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        profile_store: "CustomerDataStoreInterface | None" = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config_store: Store for scenario definitions
            profile_store: Store for profile operations
        """
        self._config_store = config_store
        self._profile_store = profile_store

    async def make_lifecycle_decisions(
        self,
        tenant_id: UUID,
        snapshot: SituationSnapshot,
        candidates: list[ScoredScenario],
        active_instances: list[ScenarioInstance],
        applied_rules: list[Rule],
        customer_profile: "CustomerDataStore | None" = None,
    ) -> list[ScenarioLifecycleDecision]:
        """Decide lifecycle actions for all scenarios (P6.2).

        Returns decisions for:
        - Each active scenario (CONTINUE/PAUSE/COMPLETE/CANCEL)
        - Top candidates (START if conditions met)

        Args:
            tenant_id: Tenant identifier
            snapshot: Situation snapshot from user message
            candidates: Candidate scenarios from retrieval
            active_instances: Currently active scenarios
            applied_rules: Rules that matched this turn
            customer_profile: Customer profile data

        Returns:
            List of lifecycle decisions
        """
        decisions = []

        # Evaluate active scenarios
        for instance in active_instances:
            decision = await self._evaluate_active_scenario(
                tenant_id, instance, snapshot, customer_profile
            )
            decisions.append(decision)

        # Evaluate candidates for START
        for candidate in candidates:
            if not self._is_already_active(candidate.scenario_id, active_instances):
                decision = await self._evaluate_candidate(
                    tenant_id, candidate, snapshot, customer_profile
                )
                if decision and decision.action == ScenarioLifecycleAction.START:
                    decisions.append(decision)

        # Record metrics
        for decision in decisions:
            SCENARIO_LIFECYCLE_DECISIONS.labels(action=decision.action).inc()
            logger.info(
                "scenario_lifecycle_decision",
                tenant_id=str(tenant_id),
                scenario_id=str(decision.scenario_id),
                action=decision.action,
                reasoning=decision.reasoning,
                confidence=decision.confidence,
            )

        logger.info(
            "scenario_lifecycle_decisions_made",
            tenant_id=str(tenant_id),
            total_decisions=len(decisions),
            start_count=sum(
                1 for d in decisions if d.action == ScenarioLifecycleAction.START
            ),
            continue_count=sum(
                1 for d in decisions if d.action == ScenarioLifecycleAction.CONTINUE
            ),
            pause_count=sum(
                1 for d in decisions if d.action == ScenarioLifecycleAction.PAUSE
            ),
            complete_count=sum(
                1 for d in decisions if d.action == ScenarioLifecycleAction.COMPLETE
            ),
            cancel_count=sum(
                1 for d in decisions if d.action == ScenarioLifecycleAction.CANCEL
            ),
        )

        return decisions

    async def make_transition_decisions(
        self,
        tenant_id: UUID,
        active_instances: list[ScenarioInstance],
        lifecycle_decisions: list[ScenarioLifecycleDecision],
        customer_profile: "CustomerDataStore | None" = None,
    ) -> list[ScenarioStepTransitionDecision]:
        """Decide step transitions for continuing scenarios (P6.3).

        Args:
            tenant_id: Tenant identifier
            active_instances: Currently active scenarios
            lifecycle_decisions: Lifecycle decisions from previous step
            customer_profile: Customer profile data

        Returns:
            List of transition decisions
        """
        transitions = []

        # Only for scenarios that are CONTINUE
        continuing = [
            d
            for d in lifecycle_decisions
            if d.action == ScenarioLifecycleAction.CONTINUE
        ]

        for decision in continuing:
            instance = next(
                (i for i in active_instances if i.scenario_id == decision.scenario_id),
                None,
            )
            if instance:
                transition = await self._evaluate_transition(
                    tenant_id, instance, customer_profile
                )
                if transition:
                    transitions.append(transition)

        logger.info(
            "scenario_transition_decisions_made",
            tenant_id=str(tenant_id),
            total_transitions=len(transitions),
            skipped_count=sum(1 for t in transitions if t.was_skipped),
        )

        return transitions

    async def determine_contributions(
        self,
        tenant_id: UUID,
        lifecycle_decisions: list[ScenarioLifecycleDecision],
        transition_decisions: list[ScenarioStepTransitionDecision],
        applied_rules: list[Rule],
    ) -> ScenarioContributionPlan:
        """Determine what each scenario contributes to response (P6.4).

        Args:
            tenant_id: Tenant identifier
            lifecycle_decisions: Lifecycle decisions
            transition_decisions: Transition decisions
            applied_rules: Rules that matched

        Returns:
            ScenarioContributionPlan with contributions from each active scenario
        """
        contributions = []

        # Build contributions for each active scenario
        for decision in lifecycle_decisions:
            if decision.action not in [
                ScenarioLifecycleAction.CONTINUE,
                ScenarioLifecycleAction.START,
            ]:
                continue  # PAUSE/COMPLETE/CANCEL don't contribute

            # Find current step
            if decision.action == ScenarioLifecycleAction.START:
                step_id = decision.entry_step_id
            else:
                # Find from transition decisions
                transition = next(
                    (
                        t
                        for t in transition_decisions
                        if t.scenario_id == decision.scenario_id
                    ),
                    None,
                )
                step_id = transition.target_step_id if transition else None

            if not step_id:
                continue

            # Load scenario and step
            scenario = await self._config_store.get_scenario(
                tenant_id, decision.scenario_id
            )
            if not scenario:
                continue

            step = next((s for s in scenario.steps if s.id == step_id), None)
            if not step:
                continue

            # Determine contribution type
            contribution = await self._build_contribution(
                scenario, step, applied_rules
            )
            contributions.append(contribution)

        # Build plan
        plan = ScenarioContributionPlan(contributions=contributions)

        # Set primary scenario (highest priority)
        if contributions:
            plan.primary_scenario_id = max(
                contributions, key=lambda c: c.priority
            ).scenario_id

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

        # Record metrics
        for contribution in contributions:
            SCENARIO_CONTRIBUTIONS.labels(
                contribution_type=contribution.contribution_type
            ).inc()

        ACTIVE_SCENARIOS_PER_SESSION.observe(len(contributions))

        logger.info(
            "scenario_contribution_plan_created",
            tenant_id=str(tenant_id),
            total_scenarios=len(contributions),
            primary_scenario=str(plan.primary_scenario_id)
            if plan.primary_scenario_id
            else None,
            has_asks=plan.has_asks,
            has_confirms=plan.has_confirms,
            has_action_hints=plan.has_action_hints,
        )

        return plan

    async def _evaluate_active_scenario(
        self,
        tenant_id: UUID,
        instance: ScenarioInstance,
        snapshot: SituationSnapshot,
        customer_profile: "CustomerDataStore | None",
    ) -> ScenarioLifecycleDecision:
        """Evaluate lifecycle action for an active scenario."""
        # Load scenario
        scenario = await self._config_store.get_scenario(tenant_id, instance.scenario_id)
        if not scenario:
            return ScenarioLifecycleDecision(
                scenario_id=instance.scenario_id,
                action=ScenarioLifecycleAction.CANCEL,
                reasoning="Scenario not found",
                source_step_id=instance.current_step_id,
            )

        # Get current step
        current_step = next(
            (s for s in scenario.steps if s.id == instance.current_step_id), None
        )
        if not current_step:
            return ScenarioLifecycleDecision(
                scenario_id=instance.scenario_id,
                action=ScenarioLifecycleAction.CANCEL,
                reasoning="Current step not found",
                source_step_id=instance.current_step_id,
            )

        # Check for CANCEL signal (highest priority)
        should_cancel, cancel_reason = await self._should_cancel_scenario(
            scenario, current_step, snapshot
        )
        if should_cancel:
            return ScenarioLifecycleDecision(
                scenario_id=instance.scenario_id,
                action=ScenarioLifecycleAction.CANCEL,
                reasoning=cancel_reason,
                source_step_id=instance.current_step_id,
            )

        # Check for COMPLETE
        should_complete, complete_reason = await self._should_complete_scenario(
            scenario, current_step, snapshot
        )
        if should_complete:
            return ScenarioLifecycleDecision(
                scenario_id=instance.scenario_id,
                action=ScenarioLifecycleAction.COMPLETE,
                reasoning=complete_reason,
                source_step_id=instance.current_step_id,
            )

        # Check for PAUSE
        should_pause, pause_reason = await self._should_pause_scenario(
            scenario, current_step, snapshot, instance
        )
        if should_pause:
            return ScenarioLifecycleDecision(
                scenario_id=instance.scenario_id,
                action=ScenarioLifecycleAction.PAUSE,
                reasoning=pause_reason,
                source_step_id=instance.current_step_id,
            )

        # Default: CONTINUE
        return ScenarioLifecycleDecision(
            scenario_id=instance.scenario_id,
            action=ScenarioLifecycleAction.CONTINUE,
            reasoning="Continue active scenario",
        )

    async def _should_pause_scenario(
        self,
        scenario,
        current_step,
        snapshot: SituationSnapshot,
        instance: ScenarioInstance,
    ) -> tuple[bool, str]:
        """Determine if scenario should be paused.

        Pause when:
        - User explicitly requests pause ("hold on", "wait")
        - Loop detected (visited same step too many times)
        - Higher priority scenario takes over (future enhancement)

        Returns:
            (should_pause, reasoning)
        """
        # Detect pause intent from snapshot
        if snapshot.scenario_signal == ScenarioSignal.PAUSE:
            return True, "User requested pause"

        # Check for loop detection (visited step too many times)
        visit_count = instance.visited_steps.get(current_step.id, 0)
        max_loop_count = 3  # TODO: Get from config
        if visit_count >= max_loop_count:
            return True, f"Loop detected: visited step {visit_count} times"

        return False, ""

    async def _should_complete_scenario(
        self,
        scenario,
        current_step,
        snapshot: SituationSnapshot,
    ) -> tuple[bool, str]:
        """Determine if scenario should complete.

        Complete when:
        - Current step is terminal (is_terminal=True)
        - User explicitly confirms completion
        - All required actions performed

        Returns:
            (should_complete, reasoning)
        """
        if current_step.is_terminal:
            return True, f"Reached terminal step: {current_step.name}"

        # TODO: Add explicit completion detection
        # e.g., "thanks, that's all I needed"

        return False, ""

    async def _should_cancel_scenario(
        self,
        scenario,
        current_step,
        snapshot: SituationSnapshot,
    ) -> tuple[bool, str]:
        """Determine if scenario should be cancelled.

        Cancel when:
        - User explicitly requests cancellation ("never mind", "cancel")
        - Scenario becomes impossible (missing critical data)
        - User switches to incompatible scenario

        Returns:
            (should_cancel, reasoning)
        """
        # Detect cancellation intent
        if snapshot.scenario_signal == ScenarioSignal.CANCEL:
            return True, "User requested cancellation"

        # TODO: Add scenario impossibility detection
        # e.g., missing critical data that can't be obtained

        return False, ""

    async def _evaluate_candidate(
        self,
        tenant_id: UUID,
        candidate: ScoredScenario,
        snapshot: SituationSnapshot,
        customer_profile: "CustomerDataStore | None",
    ) -> ScenarioLifecycleDecision | None:
        """Evaluate if a candidate should START."""
        # Load scenario
        scenario = await self._config_store.get_scenario(tenant_id, candidate.scenario_id)
        if not scenario or not scenario.enabled:
            return None

        # Simple threshold check - could be enhanced with more logic
        if candidate.score < 0.5:
            return None

        return ScenarioLifecycleDecision(
            scenario_id=candidate.scenario_id,
            action=ScenarioLifecycleAction.START,
            reasoning=f"High relevance score: {candidate.score:.2f}",
            confidence=candidate.score,
            entry_step_id=scenario.entry_step_id,
        )

    async def _evaluate_transition(
        self,
        tenant_id: UUID,
        instance: ScenarioInstance,
        customer_profile: "CustomerDataStore | None",
    ) -> ScenarioStepTransitionDecision | None:
        """Evaluate step transition for a continuing scenario."""
        # For now, just stay at current step
        # TODO: Implement transition logic based on conditions
        return ScenarioStepTransitionDecision(
            scenario_id=instance.scenario_id,
            source_step_id=instance.current_step_id,
            target_step_id=instance.current_step_id,
            was_skipped=False,
            reasoning="Stay at current step",
        )

    async def _build_contribution(
        self,
        scenario,
        step,
        applied_rules: list[Rule],
    ) -> ScenarioContribution:
        """Build contribution for a single scenario/step."""
        # Determine contribution type based on step metadata
        contribution_type = ContributionType.NONE

        if step.collects_profile_fields:
            contribution_type = ContributionType.ASK
        elif step.performs_action and step.is_required_action:
            contribution_type = ContributionType.CONFIRM
        elif step.tool_ids:
            contribution_type = ContributionType.ACTION_HINT
        elif step.template_ids:
            contribution_type = ContributionType.INFORM

        return ScenarioContribution(
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
            suggested_tools=step.tool_ids or [],
            priority=0,  # TODO: Compute from scenario priority + step priority
        )

    def _is_already_active(
        self, scenario_id: UUID, active_instances: list[ScenarioInstance]
    ) -> bool:
        """Check if scenario is already active."""
        return any(i.scenario_id == scenario_id for i in active_instances)
