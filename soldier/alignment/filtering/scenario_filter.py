"""Scenario filtering and navigation decisions.

Enhanced with profile requirements support (T155, T156).
"""

from typing import TYPE_CHECKING
from uuid import UUID

from soldier.alignment.context.models import ScenarioSignal
from soldier.alignment.context.situation_snapshot import SituationSnapshot
from soldier.alignment.filtering.models import ScenarioAction, ScenarioFilterResult
from soldier.alignment.retrieval.models import ScoredScenario
from soldier.alignment.stores import AgentConfigStore
from soldier.customer_data.enums import RequiredLevel
from soldier.observability.logging import get_logger

if TYPE_CHECKING:
    from soldier.customer_data.models import CustomerDataStore
    from soldier.customer_data.store import CustomerDataStoreInterface

logger = get_logger(__name__)


class ScenarioFilter:
    """Determine scenario navigation actions for a turn.

    Handles scenario lifecycle including:
    - Starting new scenarios when entry conditions match
    - Continuing within active scenarios
    - Detecting and handling loops via relocalization
    - Exiting scenarios when requested
    - Checking profile requirements (T155)
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        profile_store: "CustomerDataStoreInterface | None" = None,
        max_loop_count: int = 3,
        block_on_missing_hard_fields: bool = True,
    ) -> None:
        """Initialize the scenario filter.

        Args:
            config_store: Store for scenario definitions
            profile_store: Store for profile and schema operations (T155)
            max_loop_count: Maximum visits to a step before triggering relocalization
            block_on_missing_hard_fields: If True, block scenario entry when hard requirements are missing
        """
        self._config_store = config_store
        self._profile_store = profile_store
        self._max_loop_count = max_loop_count
        self._block_on_missing_hard_fields = block_on_missing_hard_fields

    async def evaluate(
        self,
        tenant_id: UUID,
        snapshot: SituationSnapshot,
        *,
        candidates: list[ScoredScenario],
        active_scenario_id: UUID | None = None,
        current_step_id: UUID | None = None,
        visited_steps: dict[UUID, int] | None = None,
        customer_profile: "CustomerDataStore | None" = None,
    ) -> ScenarioFilterResult:
        """Evaluate scenario navigation for the current turn.

        Enhanced with profile requirements checking (T155).

        Args:
            tenant_id: Tenant identifier
            snapshot: Situation snapshot from user message
            candidates: Candidate scenarios from retrieval
            active_scenario_id: Currently active scenario (if any)
            current_step_id: Current step within active scenario
            visited_steps: Map of step_id -> visit count for loop detection
            customer_profile: Customer profile for requirements checking (T155)

        Returns:
            ScenarioFilterResult with navigation action, target, and missing fields (T156)
        """
        visited_steps = visited_steps or {}

        if current_step_id and visited_steps.get(current_step_id, 0) >= self._max_loop_count:
            return ScenarioFilterResult(
                action=ScenarioAction.RELOCALIZE,
                scenario_id=active_scenario_id,
                source_step_id=current_step_id,
                target_step_id=None,
                was_relocalized=True,
                original_step_id=current_step_id,
                reasoning="Loop detected",
            )

        if active_scenario_id:
            if snapshot.scenario_signal == ScenarioSignal.EXIT:
                return ScenarioFilterResult(
                    action=ScenarioAction.EXIT,
                    scenario_id=active_scenario_id,
                    source_step_id=current_step_id,
                    reasoning="User requested exit",
                )

            # Check for missing fields in active scenario (T155)
            missing_fields, hard_missing = await self._check_profile_requirements(
                tenant_id=tenant_id,
                scenario_id=active_scenario_id,
                step_id=current_step_id,
                profile=customer_profile,
            )

            # Try step skipping if customer profile is available
            if customer_profile and current_step_id:
                scenario = await self._config_store.get_scenario(tenant_id, active_scenario_id)
                if scenario:
                    customer_data = {f.name: f.value for f in customer_profile.fields}
                    session_vars = {}  # TODO: Get from session when available

                    furthest_step, skipped = await self._find_furthest_reachable_step(
                        scenario=scenario,
                        current_step_id=current_step_id,
                        customer_data=customer_data,
                        session_variables=session_vars,
                    )

                    if furthest_step != current_step_id:
                        logger.info(
                            "scenario_steps_skipped",
                            scenario_id=str(active_scenario_id),
                            source_step=str(current_step_id),
                            target_step=str(furthest_step),
                            skipped_count=len(skipped),
                        )
                        return ScenarioFilterResult(
                            action=ScenarioAction.TRANSITION,
                            scenario_id=active_scenario_id,
                            source_step_id=current_step_id,
                            target_step_id=furthest_step,
                            reasoning=f"Skipped {len(skipped)} steps with available data",
                            skipped_steps=skipped,
                            missing_profile_fields=missing_fields,
                        )

            return ScenarioFilterResult(
                action=ScenarioAction.CONTINUE,
                scenario_id=active_scenario_id,
                source_step_id=current_step_id,
                target_step_id=current_step_id,
                reasoning="Continue active scenario",
                missing_profile_fields=missing_fields,
                blocked_by_missing_fields=False,  # Don't block continue, just report
            )

        if candidates:
            top = candidates[0]
            scenario = await self._config_store.get_scenario(tenant_id, top.scenario_id)
            if scenario:
                # Check for missing fields before starting scenario (T155)
                missing_fields, hard_missing = await self._check_profile_requirements(
                    tenant_id=tenant_id,
                    scenario_id=scenario.id,
                    step_id=scenario.entry_step_id,
                    profile=customer_profile,
                )

                # Block scenario entry if hard requirements are missing
                if self._block_on_missing_hard_fields and hard_missing:
                    logger.warning(
                        "scenario_entry_blocked_missing_fields",
                        scenario_id=str(scenario.id),
                        missing_fields=missing_fields,
                        hard_missing=hard_missing,
                    )
                    return ScenarioFilterResult(
                        action=ScenarioAction.NONE,
                        scenario_id=scenario.id,
                        target_step_id=scenario.entry_step_id,
                        reasoning=f"Blocked by missing hard requirements: {hard_missing}",
                        missing_profile_fields=missing_fields,
                        blocked_by_missing_fields=True,
                    )

                return ScenarioFilterResult(
                    action=ScenarioAction.START,
                    scenario_id=scenario.id,
                    target_step_id=scenario.entry_step_id,
                    reasoning="Start best matching scenario",
                    missing_profile_fields=missing_fields,
                )

        return ScenarioFilterResult(
            action=ScenarioAction.NONE,
            scenario_id=None,
            reasoning="No scenario action",
        )

    async def _check_profile_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        step_id: UUID | None,
        profile: "CustomerDataStore | None",
    ) -> tuple[list[str], list[str]]:
        """Check profile requirements for a scenario/step (T155).

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario to check
            step_id: Optional specific step
            profile: Customer profile to check against

        Returns:
            Tuple of (all_missing_fields, hard_required_missing_fields)
        """
        if not self._profile_store:
            return [], []

        try:
            # Get missing fields from profile store
            missing_fields = await self._profile_store.get_missing_fields(
                tenant_id=tenant_id,
                profile=profile,
                scenario_id=scenario_id,
                step_id=step_id,
            )

            if not missing_fields:
                return [], []

            # Get requirements to determine which are hard
            requirements = await self._profile_store.get_scenario_requirements(
                tenant_id=tenant_id,
                scenario_id=scenario_id,
            )

            # Filter requirements for this step if specified
            if step_id:
                requirements = [
                    r for r in requirements
                    if r.step_id is None or r.step_id == step_id
                ]

            # Identify hard requirements among missing fields
            hard_missing = []
            for req in requirements:
                if req.field_name in missing_fields:
                    if req.required_level == RequiredLevel.HARD:
                        hard_missing.append(req.field_name)

            logger.info(
                "scenario_profile_requirements_checked",
                scenario_id=str(scenario_id),
                step_id=str(step_id) if step_id else None,
                total_missing=len(missing_fields),
                hard_missing_count=len(hard_missing),
            )

            return missing_fields, hard_missing

        except Exception as e:
            logger.warning(
                "scenario_profile_requirements_check_failed",
                scenario_id=str(scenario_id),
                error=str(e),
            )
            return [], []

    async def _find_furthest_reachable_step(
        self,
        scenario,
        current_step_id: UUID,
        customer_data: dict[str, any],
        session_variables: dict[str, any],
    ) -> tuple[UUID, list[UUID]]:
        """Find furthest step we can skip to based on available data.

        Example:
            Steps: [collect_order_id] → [collect_reason] → [confirm_refund]
            User message: "Refund order #123, item was damaged"
            Available data: order_id="123", reason="damaged"
            Result: Skip to [confirm_refund], skipped=[collect_order_id, collect_reason]

        Args:
            scenario: Scenario definition
            current_step_id: Where we are now
            customer_data: Data from CustomerProfile
            session_variables: Data from Session

        Returns:
            (furthest_step_id, list_of_skipped_step_ids)
        """
        current_step = next((s for s in scenario.steps if s.id == current_step_id), None)
        if not current_step:
            return current_step_id, []

        all_data = {**customer_data, **session_variables}

        # BFS to find furthest reachable step
        furthest = current_step_id
        skipped = []

        # Check each downstream step as potential target
        for step in scenario.steps:
            # Skip if not reachable from current
            if not self._is_downstream_of(scenario, current_step_id, step.id):
                continue

            # Get intermediate steps (steps we would need to skip)
            intermediate = self._get_intermediate_steps(
                scenario, current_step_id, step.id
            )

            # Check if all intermediate steps can be skipped
            can_skip_all = True
            for int_step_id in intermediate:
                int_step = next((s for s in scenario.steps if s.id == int_step_id), None)
                if not int_step:
                    can_skip_all = False
                    break
                # Step must be skippable AND have all required data
                if not int_step.can_skip:
                    can_skip_all = False
                    break
                if not self._has_required_fields(int_step, all_data):
                    can_skip_all = False
                    break

            if can_skip_all:
                # Include the current step in skipped count since we're skipping FROM it
                all_skipped = [current_step_id] + intermediate if intermediate else [current_step_id]

                # Check if current step can be skipped (has required data)
                if not current_step.can_skip or not self._has_required_fields(current_step, all_data):
                    continue

                # Found a valid target - check if it's further than current furthest
                # (we want the furthest reachable step)
                if len(all_skipped) > len(skipped):
                    furthest = step.id
                    skipped = all_skipped

        return furthest, skipped

    def _has_required_fields(
        self, step, available_data: dict[str, any]
    ) -> bool:
        """Check if step's required fields are available."""
        required = step.collects_profile_fields or []
        return all(field in available_data for field in required)

    def _is_downstream_of(
        self, scenario, source_id: UUID, target_id: UUID
    ) -> bool:
        """Check if target is reachable from source via transitions."""
        if source_id == target_id:
            return False

        # BFS through transitions
        visited = set()
        queue = [source_id]

        while queue:
            current = queue.pop(0)
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)

            current_step = next((s for s in scenario.steps if s.id == current), None)
            if current_step:
                for transition in current_step.transitions:
                    queue.append(transition.to_step_id)

        return False

    def _get_intermediate_steps(
        self, scenario, source_id: UUID, target_id: UUID
    ) -> list[UUID]:
        """Get steps between source and target (for skipping).

        Uses BFS to find shortest path and returns intermediate steps.
        Does NOT include source or target in the returned list.
        """
        if source_id == target_id:
            return []

        # BFS with path tracking - path tracks intermediate steps only
        visited = set()
        # Queue contains: (current_step_id, list_of_intermediate_steps_to_get_here)
        queue = [(source_id, [])]

        while queue:
            current, intermediate = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            current_step = next((s for s in scenario.steps if s.id == current), None)
            if not current_step:
                continue

            for transition in current_step.transitions:
                next_step_id = transition.to_step_id
                if next_step_id == target_id:
                    # Found target - return the intermediate steps
                    # (current is an intermediate step if it's not the source)
                    if current != source_id:
                        return intermediate + [current]
                    return intermediate
                # Add next step to queue with updated intermediate list
                if next_step_id not in visited:
                    new_intermediate = intermediate + ([current] if current != source_id else [])
                    queue.append((next_step_id, new_intermediate))

        return []
