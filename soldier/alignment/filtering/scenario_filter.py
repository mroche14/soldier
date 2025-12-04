"""Scenario filtering and navigation decisions.

Enhanced with profile requirements support (T155, T156).
"""

from typing import TYPE_CHECKING
from uuid import UUID

from soldier.alignment.context.models import Context, ScenarioSignal
from soldier.alignment.filtering.models import ScenarioAction, ScenarioFilterResult
from soldier.alignment.retrieval.models import ScoredScenario
from soldier.alignment.stores import AgentConfigStore
from soldier.observability.logging import get_logger
from soldier.profile.enums import RequiredLevel

if TYPE_CHECKING:
    from soldier.profile.models import CustomerProfile
    from soldier.profile.store import ProfileStore

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
        profile_store: "ProfileStore | None" = None,
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
        context: Context,
        *,
        candidates: list[ScoredScenario],
        active_scenario_id: UUID | None = None,
        current_step_id: UUID | None = None,
        visited_steps: dict[UUID, int] | None = None,
        customer_profile: "CustomerProfile | None" = None,
    ) -> ScenarioFilterResult:
        """Evaluate scenario navigation for the current turn.

        Enhanced with profile requirements checking (T155).

        Args:
            tenant_id: Tenant identifier
            context: Extracted context from user message
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
            if context.scenario_signal == ScenarioSignal.EXIT:
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
        profile: "CustomerProfile | None",
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
