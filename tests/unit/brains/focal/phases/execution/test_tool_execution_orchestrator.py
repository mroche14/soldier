"""Tests for ToolExecutionOrchestrator - Phase 7 tool execution flow.

Tests cover:
- Full execute_phase flow (P7.1-P7.7)
- Tool binding collection
- Variable requirement analysis
- Variable resolution
- Tool scheduling and execution
- Result merging
- Future tool queuing
"""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.execution.models import ToolExecutionResult, ToolResult
from ruche.brains.focal.phases.execution.tool_execution_orchestrator import (
    ToolExecutionOrchestrator,
)
from ruche.brains.focal.phases.execution.tool_scheduler import FutureToolQueue
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.planning.models import (
    ContributionType,
    ScenarioContribution,
    ScenarioContributionPlan,
)
from ruche.conversation.models.session import Session
from ruche.domain.interlocutor.models import InterlocutorDataStore


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_binding_collector():
    """Create mock tool binding collector."""
    collector = AsyncMock()
    collector.collect_bindings = AsyncMock(return_value=[])
    return collector


@pytest.fixture
def mock_requirement_analyzer():
    """Create mock variable requirement analyzer."""
    analyzer = MagicMock()
    analyzer.compute_required_variables = MagicMock(return_value=set())
    return analyzer


@pytest.fixture
def mock_variable_resolver():
    """Create mock variable resolver."""
    resolver = AsyncMock()
    resolver.resolve_variables = AsyncMock(return_value=({}, set()))
    return resolver


@pytest.fixture
def mock_scheduler():
    """Create mock tool scheduler."""
    scheduler = MagicMock()
    scheduler.schedule_tools = MagicMock(return_value=[])
    return scheduler


@pytest.fixture
def mock_executor():
    """Create mock tool executor."""
    executor = AsyncMock()
    executor.execute = AsyncMock(return_value=[])
    return executor


@pytest.fixture
def mock_merger():
    """Create mock variable merger."""
    merger = MagicMock()
    merger.merge_tool_results = MagicMock(return_value={})
    return merger


@pytest.fixture
def mock_future_queue():
    """Create mock future tool queue."""
    queue = MagicMock(spec=FutureToolQueue)
    queue.add_tools = MagicMock()
    return queue


@pytest.fixture
def orchestrator(
    mock_binding_collector,
    mock_requirement_analyzer,
    mock_variable_resolver,
    mock_scheduler,
    mock_executor,
    mock_merger,
    mock_future_queue,
):
    """Create orchestrator with mock dependencies."""
    return ToolExecutionOrchestrator(
        binding_collector=mock_binding_collector,
        requirement_analyzer=mock_requirement_analyzer,
        variable_resolver=mock_variable_resolver,
        scheduler=mock_scheduler,
        executor=mock_executor,
        merger=mock_merger,
        future_queue=mock_future_queue,
    )


@pytest.fixture
def sample_session():
    """Create sample session."""
    return Session(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel="webchat",
        user_channel_id="user123",
        config_version=1,
    )


@pytest.fixture
def sample_customer_profile():
    """Create sample customer profile."""
    return InterlocutorDataStore(
        tenant_id=uuid4(),
        interlocutor_id=uuid4(),
    )


@pytest.fixture
def sample_snapshot():
    """Create sample situation snapshot."""
    return SituationSnapshot(
        message="Hello, I need help",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
    )


@pytest.fixture
def empty_contribution_plan():
    """Create empty contribution plan."""
    return ScenarioContributionPlan(contributions=[])


@pytest.fixture
def sample_contribution_plan():
    """Create sample contribution plan with one contribution."""
    return ScenarioContributionPlan(
        contributions=[
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Test Scenario",
                current_step_id=uuid4(),
                current_step_name="Step 1",
                contribution_type=ContributionType.INFORM,
            )
        ]
    )


# =============================================================================
# Tests: ToolExecutionOrchestrator.__init__()
# =============================================================================


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_creates_with_all_dependencies(
        self,
        mock_binding_collector,
        mock_requirement_analyzer,
        mock_variable_resolver,
        mock_scheduler,
        mock_executor,
        mock_merger,
        mock_future_queue,
    ):
        """Creates orchestrator with all dependencies."""
        orchestrator = ToolExecutionOrchestrator(
            binding_collector=mock_binding_collector,
            requirement_analyzer=mock_requirement_analyzer,
            variable_resolver=mock_variable_resolver,
            scheduler=mock_scheduler,
            executor=mock_executor,
            merger=mock_merger,
            future_queue=mock_future_queue,
        )

        assert orchestrator._binding_collector is mock_binding_collector
        assert orchestrator._requirement_analyzer is mock_requirement_analyzer
        assert orchestrator._variable_resolver is mock_variable_resolver
        assert orchestrator._scheduler is mock_scheduler
        assert orchestrator._executor is mock_executor
        assert orchestrator._merger is mock_merger
        assert orchestrator._future_queue is mock_future_queue

    def test_creates_default_future_queue_when_not_provided(
        self,
        mock_binding_collector,
        mock_requirement_analyzer,
        mock_variable_resolver,
        mock_scheduler,
        mock_executor,
        mock_merger,
    ):
        """Creates default FutureToolQueue when not provided."""
        orchestrator = ToolExecutionOrchestrator(
            binding_collector=mock_binding_collector,
            requirement_analyzer=mock_requirement_analyzer,
            variable_resolver=mock_variable_resolver,
            scheduler=mock_scheduler,
            executor=mock_executor,
            merger=mock_merger,
        )

        assert orchestrator._future_queue is not None
        assert isinstance(orchestrator._future_queue, FutureToolQueue)


# =============================================================================
# Tests: ToolExecutionOrchestrator.execute_phase() - Basic Flow
# =============================================================================


class TestExecutePhaseBasicFlow:
    """Tests for basic execute_phase flow."""

    @pytest.mark.asyncio
    async def test_executes_before_step_phase(
        self,
        orchestrator,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Executes BEFORE_STEP phase successfully."""
        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="BEFORE_STEP",
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.phase == "BEFORE_STEP"

    @pytest.mark.asyncio
    async def test_executes_during_step_phase(
        self,
        orchestrator,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Executes DURING_STEP phase successfully."""
        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        assert result.phase == "DURING_STEP"

    @pytest.mark.asyncio
    async def test_executes_after_step_phase(
        self,
        orchestrator,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Executes AFTER_STEP phase successfully."""
        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="AFTER_STEP",
        )

        assert result.phase == "AFTER_STEP"

    @pytest.mark.asyncio
    async def test_returns_empty_result_when_no_tools(
        self,
        orchestrator,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Returns empty result when no tools to execute."""
        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        assert result.engine_variables == {}
        assert result.tool_results == []
        assert result.missing_variables == set()
        assert result.queued_tools == []


# =============================================================================
# Tests: P7.1 - Tool Binding Collection
# =============================================================================


class TestToolBindingCollection:
    """Tests for P7.1 tool binding collection."""

    @pytest.mark.asyncio
    async def test_collects_bindings_from_contribution_plan(
        self,
        orchestrator,
        mock_binding_collector,
        sample_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Calls binding collector with contribution plan."""
        await orchestrator.execute_phase(
            contribution_plan=sample_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_binding_collector.collect_bindings.assert_called_once()
        call_kwargs = mock_binding_collector.collect_bindings.call_args.kwargs
        assert call_kwargs["contribution_plan"] is sample_contribution_plan

    @pytest.mark.asyncio
    async def test_collects_bindings_from_applied_rules(
        self,
        orchestrator,
        mock_binding_collector,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Passes applied rules to binding collector."""
        # Create mock matched rule
        mock_rule = MagicMock(spec=MatchedRule)

        await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[mock_rule],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        call_kwargs = mock_binding_collector.collect_bindings.call_args.kwargs
        assert mock_rule in call_kwargs["applied_rules"]


# =============================================================================
# Tests: P7.2 - Variable Requirement Analysis
# =============================================================================


class TestVariableRequirementAnalysis:
    """Tests for P7.2 variable requirement analysis."""

    @pytest.mark.asyncio
    async def test_computes_required_variables(
        self,
        orchestrator,
        mock_binding_collector,
        mock_requirement_analyzer,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Computes required variables from bindings and rules."""
        # Set up bindings
        mock_binding = MagicMock()
        mock_binding_collector.collect_bindings.return_value = [mock_binding]

        await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_requirement_analyzer.compute_required_variables.assert_called_once()
        call_kwargs = mock_requirement_analyzer.compute_required_variables.call_args.kwargs
        assert call_kwargs["tool_bindings"] == [mock_binding]

    @pytest.mark.asyncio
    async def test_passes_current_step_to_requirement_analyzer(
        self,
        orchestrator,
        mock_requirement_analyzer,
        sample_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Passes current step when scenario_steps provided."""
        scenario_id = sample_contribution_plan.contributions[0].scenario_id
        step_id = sample_contribution_plan.contributions[0].current_step_id
        mock_step = MagicMock()
        scenario_steps = {(scenario_id, step_id): mock_step}

        await orchestrator.execute_phase(
            contribution_plan=sample_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
            scenario_steps=scenario_steps,
        )

        call_kwargs = mock_requirement_analyzer.compute_required_variables.call_args.kwargs
        assert call_kwargs["current_step"] is mock_step


# =============================================================================
# Tests: P7.3 - Variable Resolution
# =============================================================================


class TestVariableResolution:
    """Tests for P7.3 variable resolution."""

    @pytest.mark.asyncio
    async def test_resolves_variables_from_profile_and_session(
        self,
        orchestrator,
        mock_requirement_analyzer,
        mock_variable_resolver,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Resolves variables from customer profile and session."""
        mock_requirement_analyzer.compute_required_variables.return_value = {"email", "name"}

        await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_variable_resolver.resolve_variables.assert_called_once()
        call_kwargs = mock_variable_resolver.resolve_variables.call_args.kwargs
        assert call_kwargs["required_vars"] == {"email", "name"}
        assert call_kwargs["customer_profile"] is sample_customer_profile
        assert call_kwargs["session"] is sample_session

    @pytest.mark.asyncio
    async def test_tracks_missing_variables(
        self,
        orchestrator,
        mock_requirement_analyzer,
        mock_variable_resolver,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Tracks variables that couldn't be resolved."""
        mock_requirement_analyzer.compute_required_variables.return_value = {"email", "phone"}
        mock_variable_resolver.resolve_variables.return_value = (
            {"email": "test@example.com"},
            {"phone"},  # Missing
        )

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        assert "phone" in result.missing_variables


# =============================================================================
# Tests: P7.4 & P7.5 - Tool Scheduling and Execution
# =============================================================================


class TestToolSchedulingAndExecution:
    """Tests for P7.4 scheduling and P7.5 execution."""

    @pytest.mark.asyncio
    async def test_schedules_tools_for_current_phase(
        self,
        orchestrator,
        mock_binding_collector,
        mock_scheduler,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Schedules tools for the specified phase."""
        mock_binding = MagicMock()
        mock_binding_collector.collect_bindings.return_value = [mock_binding]

        await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="BEFORE_STEP",
        )

        mock_scheduler.schedule_tools.assert_called_once()
        call_kwargs = mock_scheduler.schedule_tools.call_args.kwargs
        assert call_kwargs["tool_bindings"] == [mock_binding]
        assert call_kwargs["current_phase"] == "BEFORE_STEP"

    @pytest.mark.asyncio
    async def test_executes_scheduled_tools(
        self,
        orchestrator,
        mock_scheduler,
        mock_executor,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Executes tools when there are scheduled tools."""
        mock_scheduled_tool = MagicMock()
        mock_scheduler.schedule_tools.return_value = [mock_scheduled_tool]

        mock_tool_result = ToolResult(
            tool_name="test_tool",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=50.0,
        )
        mock_executor.execute.return_value = [mock_tool_result]

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_executor.execute.assert_called_once()
        assert len(result.tool_results) == 1
        assert result.tool_results[0].tool_name == "test_tool"

    @pytest.mark.asyncio
    async def test_skips_execution_when_no_scheduled_tools(
        self,
        orchestrator,
        mock_scheduler,
        mock_executor,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Skips execution when no tools scheduled."""
        mock_scheduler.schedule_tools.return_value = []

        await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_executor.execute.assert_not_called()


# =============================================================================
# Tests: P7.6 - Result Merging
# =============================================================================


class TestResultMerging:
    """Tests for P7.6 result merging."""

    @pytest.mark.asyncio
    async def test_merges_tool_results_into_engine_variables(
        self,
        orchestrator,
        mock_variable_resolver,
        mock_merger,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Merges known variables and tool results."""
        mock_variable_resolver.resolve_variables.return_value = (
            {"name": "John"},
            set(),
        )

        merged_vars = {"name": "John", "order_id": "ORD-123"}
        mock_merger.merge_tool_results.return_value = merged_vars

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_merger.merge_tool_results.assert_called_once()
        assert result.engine_variables == merged_vars


# =============================================================================
# Tests: P7.7 - Future Tool Queuing
# =============================================================================


class TestFutureToolQueuing:
    """Tests for P7.7 future tool queuing."""

    @pytest.mark.asyncio
    async def test_queues_after_step_tools_during_before_step(
        self,
        orchestrator,
        mock_binding_collector,
        mock_future_queue,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Queues AFTER_STEP tools when executing BEFORE_STEP."""
        mock_after_binding = MagicMock()
        mock_after_binding.when = "AFTER_STEP"
        mock_binding_collector.collect_bindings.return_value = [mock_after_binding]

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="BEFORE_STEP",
        )

        mock_future_queue.add_tools.assert_called_once()
        assert mock_after_binding in result.queued_tools

    @pytest.mark.asyncio
    async def test_queues_after_step_tools_during_during_step(
        self,
        orchestrator,
        mock_binding_collector,
        mock_future_queue,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Queues AFTER_STEP tools when executing DURING_STEP."""
        mock_after_binding = MagicMock()
        mock_after_binding.when = "AFTER_STEP"
        mock_binding_collector.collect_bindings.return_value = [mock_after_binding]

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        mock_future_queue.add_tools.assert_called_once()
        assert len(result.queued_tools) == 1

    @pytest.mark.asyncio
    async def test_does_not_queue_during_after_step_phase(
        self,
        orchestrator,
        mock_binding_collector,
        mock_future_queue,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Does not queue tools when already in AFTER_STEP phase."""
        mock_after_binding = MagicMock()
        mock_after_binding.when = "AFTER_STEP"
        mock_binding_collector.collect_bindings.return_value = [mock_after_binding]

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="AFTER_STEP",
        )

        mock_future_queue.add_tools.assert_not_called()
        assert result.queued_tools == []

    @pytest.mark.asyncio
    async def test_does_not_queue_non_after_step_tools(
        self,
        orchestrator,
        mock_binding_collector,
        mock_future_queue,
        empty_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Does not queue BEFORE_STEP or DURING_STEP tools."""
        mock_before_binding = MagicMock()
        mock_before_binding.when = "BEFORE_STEP"
        mock_during_binding = MagicMock()
        mock_during_binding.when = "DURING_STEP"
        mock_binding_collector.collect_bindings.return_value = [
            mock_before_binding,
            mock_during_binding,
        ]

        result = await orchestrator.execute_phase(
            contribution_plan=empty_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="BEFORE_STEP",
        )

        mock_future_queue.add_tools.assert_not_called()
        assert result.queued_tools == []


# =============================================================================
# Tests: Integration - Full Flow
# =============================================================================


class TestFullFlow:
    """Integration tests for complete execute_phase flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_tool_execution(
        self,
        mock_binding_collector,
        mock_requirement_analyzer,
        mock_variable_resolver,
        mock_scheduler,
        mock_executor,
        mock_merger,
        mock_future_queue,
        sample_contribution_plan,
        sample_session,
        sample_customer_profile,
        sample_snapshot,
    ):
        """Tests complete flow with actual tool execution."""
        # Setup: Binding collection
        mock_binding = MagicMock()
        mock_binding.when = "DURING_STEP"
        mock_binding_collector.collect_bindings.return_value = [mock_binding]

        # Setup: Variable analysis
        mock_requirement_analyzer.compute_required_variables.return_value = {"order_id"}

        # Setup: Variable resolution
        mock_variable_resolver.resolve_variables.return_value = (
            {"order_id": "ORD-123"},
            set(),
        )

        # Setup: Scheduling
        mock_scheduler.schedule_tools.return_value = [mock_binding]

        # Setup: Execution
        mock_tool_result = ToolResult(
            tool_name="get_order",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            outputs={"status": "shipped"},
        )
        mock_executor.execute.return_value = [mock_tool_result]

        # Setup: Merging
        mock_merger.merge_tool_results.return_value = {
            "order_id": "ORD-123",
            "order_status": "shipped",
        }

        # Create orchestrator
        orchestrator = ToolExecutionOrchestrator(
            binding_collector=mock_binding_collector,
            requirement_analyzer=mock_requirement_analyzer,
            variable_resolver=mock_variable_resolver,
            scheduler=mock_scheduler,
            executor=mock_executor,
            merger=mock_merger,
            future_queue=mock_future_queue,
        )

        # Execute
        result = await orchestrator.execute_phase(
            contribution_plan=sample_contribution_plan,
            applied_rules=[],
            customer_profile=sample_customer_profile,
            session=sample_session,
            snapshot=sample_snapshot,
            phase="DURING_STEP",
        )

        # Verify
        assert result.phase == "DURING_STEP"
        assert result.engine_variables == {"order_id": "ORD-123", "order_status": "shipped"}
        assert len(result.tool_results) == 1
        assert result.tool_results[0].success is True
        assert result.missing_variables == set()
