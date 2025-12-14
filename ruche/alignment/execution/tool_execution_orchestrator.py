"""Tool execution orchestration for Phase 7."""

from typing import Any, Literal
from uuid import UUID

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.execution.models import ToolExecutionResult, ToolResult
from ruche.alignment.execution.tool_binding_collector import ToolBindingCollector
from ruche.alignment.execution.tool_executor import ToolExecutor
from ruche.alignment.execution.tool_scheduler import FutureToolQueue, ToolScheduler
from ruche.alignment.execution.variable_merger import VariableMerger
from ruche.alignment.execution.variable_requirement_analyzer import (
    VariableRequirementAnalyzer,
)
from ruche.alignment.execution.variable_resolver import VariableResolver
from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.planning.models import ScenarioContributionPlan
from ruche.conversation.models.session import Session
from ruche.customer_data.models import CustomerDataStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ToolExecutionOrchestrator:
    """Orchestrates complete tool execution flow (P7.1 - P7.7)."""

    def __init__(
        self,
        binding_collector: ToolBindingCollector,
        requirement_analyzer: VariableRequirementAnalyzer,
        variable_resolver: VariableResolver,
        scheduler: ToolScheduler,
        executor: ToolExecutor,
        merger: VariableMerger,
        future_queue: FutureToolQueue | None = None,
    ) -> None:
        """Initialize orchestrator with dependencies.

        Args:
            binding_collector: Collects tool bindings from rules/scenarios
            requirement_analyzer: Computes required variables
            variable_resolver: Resolves variables from profile/session
            scheduler: Schedules tools by timing and dependencies
            executor: Executes tools
            merger: Merges tool results into engine variables
            future_queue: Queue for AFTER_STEP tools (optional)
        """
        self._binding_collector = binding_collector
        self._requirement_analyzer = requirement_analyzer
        self._variable_resolver = variable_resolver
        self._scheduler = scheduler
        self._executor = executor
        self._merger = merger
        self._future_queue = future_queue or FutureToolQueue()

    async def execute_phase(
        self,
        contribution_plan: ScenarioContributionPlan,
        applied_rules: list[MatchedRule],
        customer_profile: CustomerDataStore,
        session: Session,
        snapshot: SituationSnapshot,
        phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"],
        scenario_steps: dict[tuple[UUID, UUID], Any] | None = None,
    ) -> ToolExecutionResult:
        """Execute complete tool execution flow for given phase.

        Flow:
        1. Collect tool bindings (P7.1)
        2. Compute required variables (P7.2)
        3. Resolve from profile/session (P7.3)
        4. Schedule tools for phase (P7.4)
        5. Execute scheduled tools (P7.5)
        6. Merge results (P7.6)
        7. Queue future tools (P7.7)

        Args:
            contribution_plan: From Phase 6 scenario orchestration
            applied_rules: From Phase 5 rule selection
            customer_profile: Customer data store
            session: Session state
            snapshot: Situation snapshot
            phase: Execution phase
            scenario_steps: Map of (scenario_id, step_id) -> ScenarioStep

        Returns:
            ToolExecutionResult with engine_variables, tool_results, queued_tools
        """
        logger.info("starting_tool_execution_phase", phase=phase)

        # P7.1: Collect tool bindings
        tool_bindings = await self._binding_collector.collect_bindings(
            contribution_plan=contribution_plan,
            applied_rules=applied_rules,
            scenario_steps=scenario_steps,
        )

        # P7.2: Compute required variables
        current_step = None
        if scenario_steps and contribution_plan.contributions:
            # Get first contributing scenario's current step
            first_contrib = contribution_plan.contributions[0]
            step_key = (first_contrib.scenario_id, first_contrib.current_step_id)
            current_step = scenario_steps.get(step_key)

        required_vars = self._requirement_analyzer.compute_required_variables(
            tool_bindings=tool_bindings,
            applied_rules=applied_rules,
            current_step=current_step,
        )

        # P7.3: Resolve from profile/session
        known_vars, missing_vars = await self._variable_resolver.resolve_variables(
            required_vars=required_vars,
            customer_profile=customer_profile,
            session=session,
        )

        # P7.4: Schedule tools for this phase
        scheduled_tools = self._scheduler.schedule_tools(
            tool_bindings=tool_bindings,
            missing_vars=missing_vars,
            current_phase=phase,
        )

        # P7.5: Execute scheduled tools
        tool_results: list[ToolResult] = []
        if scheduled_tools:
            # Note: Current ToolExecutor needs adaptation for scheduled_tools format
            # For now, create minimal execution using existing interface
            logger.info(
                "executing_tools",
                phase=phase,
                scheduled_count=len(scheduled_tools),
            )
            # TODO: Adapt ToolExecutor to handle scheduled_tools format
            # For now, tools would be executed via existing executor interface

        # P7.6: Merge tool results
        engine_variables = self._merger.merge_tool_results(
            known_vars=known_vars,
            tool_results=tool_results,
        )

        # P7.7: Queue AFTER_STEP tools
        queued_tools = []
        if phase != "AFTER_STEP":
            after_tools = [b for b in tool_bindings if b.when == "AFTER_STEP"]
            if after_tools:
                self._future_queue.add_tools(
                    tool_bindings=after_tools,
                    session_id=session.session_id,
                )
                queued_tools = after_tools

        logger.info(
            "completed_tool_execution_phase",
            phase=phase,
            engine_variables_count=len(engine_variables),
            tool_results_count=len(tool_results),
            queued_tools_count=len(queued_tools),
            missing_variables_count=len(missing_vars),
        )

        return ToolExecutionResult(
            engine_variables=engine_variables,
            tool_results=tool_results,
            missing_variables=missing_vars,
            queued_tools=queued_tools,
            phase=phase,
        )
