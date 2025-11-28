"""Scenario filtering and navigation decisions."""

from uuid import UUID

from soldier.alignment.context.models import Context, ScenarioSignal
from soldier.alignment.filtering.models import ScenarioAction, ScenarioFilterResult
from soldier.alignment.retrieval.models import ScoredScenario
from soldier.alignment.stores import ConfigStore
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


class ScenarioFilter:
    """Determine scenario navigation actions for a turn.

    Handles scenario lifecycle including:
    - Starting new scenarios when entry conditions match
    - Continuing within active scenarios
    - Detecting and handling loops via relocalization
    - Exiting scenarios when requested
    """

    def __init__(
        self,
        config_store: ConfigStore,
        max_loop_count: int = 3,
    ) -> None:
        """Initialize the scenario filter.

        Args:
            config_store: Store for scenario definitions
            max_loop_count: Maximum visits to a step before triggering relocalization
        """
        self._config_store = config_store
        self._max_loop_count = max_loop_count

    async def evaluate(
        self,
        tenant_id: UUID,
        context: Context,
        *,
        candidates: list[ScoredScenario],
        active_scenario_id: UUID | None = None,
        current_step_id: UUID | None = None,
        visited_steps: dict[UUID, int] | None = None,
    ) -> ScenarioFilterResult:
        """Evaluate scenario navigation for the current turn.

        Args:
            tenant_id: Tenant identifier
            context: Extracted context from user message
            candidates: Candidate scenarios from retrieval
            active_scenario_id: Currently active scenario (if any)
            current_step_id: Current step within active scenario
            visited_steps: Map of step_id -> visit count for loop detection

        Returns:
            ScenarioFilterResult with navigation action and target
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

            return ScenarioFilterResult(
                action=ScenarioAction.CONTINUE,
                scenario_id=active_scenario_id,
                source_step_id=current_step_id,
                target_step_id=current_step_id,
                reasoning="Continue active scenario",
            )

        if candidates:
            top = candidates[0]
            scenario = await self._config_store.get_scenario(tenant_id, top.scenario_id)
            if scenario:
                return ScenarioFilterResult(
                    action=ScenarioAction.START,
                    scenario_id=scenario.id,
                    target_step_id=scenario.entry_step_id,
                    reasoning="Start best matching scenario",
                )

        return ScenarioFilterResult(
            action=ScenarioAction.NONE,
            scenario_id=None,
            reasoning="No scenario action",
        )
