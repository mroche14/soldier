"""Unit tests for ScenarioOrchestrator."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.context.models import ScenarioSignal
from ruche.brains.focal.phases.filtering.models import (
    ScenarioLifecycleAction,
    ScenarioLifecycleDecision,
)
from ruche.brains.focal.models import Rule
from ruche.brains.focal.models.scenario import Scenario, ScenarioStep, StepTransition
from ruche.brains.focal.phases.orchestration.orchestrator import ScenarioOrchestrator
from ruche.brains.focal.retrieval.models import ScoredScenario
from ruche.brains.focal.stores.inmemory import InMemoryAgentConfigStore
from ruche.conversation.models.session import ScenarioInstance


@pytest.fixture
def config_store():
    """Create in-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def orchestrator(config_store):
    """Create scenario orchestrator."""
    return ScenarioOrchestrator(config_store=config_store)


@pytest.fixture
def tenant_id():
    """Create tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Create agent ID."""
    return uuid4()


@pytest.fixture
def test_scenario(tenant_id, agent_id):
    """Create a test scenario."""
    scenario_id = uuid4()
    entry_step_id = uuid4()
    terminal_step_id = uuid4()

    entry_step = ScenarioStep(
        id=entry_step_id,
        scenario_id=scenario_id,
        name="entry",
        transitions=[StepTransition(to_step_id=terminal_step_id, condition_text="default", priority=0)],
    )

    terminal_step = ScenarioStep(
        id=terminal_step_id,
        scenario_id=scenario_id,
        name="terminal",
        is_terminal=True,
        transitions=[],
    )

    return Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Test Scenario",
        description="Test scenario",
        enabled=True,
        entry_step_id=entry_step_id,
        steps=[entry_step, terminal_step],
    )


@pytest.fixture
def snapshot():
    """Create a test snapshot."""
    return SituationSnapshot(
        message="test message",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        scenario_signal=ScenarioSignal.UNKNOWN,
    )


@pytest.fixture
def active_instance(test_scenario):
    """Create an active scenario instance."""
    return ScenarioInstance(
        scenario_id=test_scenario.id,
        scenario_version=1,
        current_step_id=test_scenario.entry_step_id,
        visited_steps={test_scenario.entry_step_id: 1},
        started_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
        status="active",
    )


class TestLifecycleDecisions:
    """Test lifecycle decision making."""

    @pytest.mark.asyncio
    async def test_continue_active_scenario(
        self, orchestrator, tenant_id, snapshot, test_scenario, active_instance, config_store
    ):
        """Test continuing an active scenario."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[active_instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.CONTINUE
        assert decisions[0].scenario_id == test_scenario.id

    @pytest.mark.asyncio
    async def test_complete_at_terminal_step(
        self, orchestrator, tenant_id, snapshot, test_scenario, active_instance, config_store
    ):
        """Test completing scenario at terminal step."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        # Move to terminal step
        terminal_step = test_scenario.steps[1]
        active_instance.current_step_id = terminal_step.id

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[active_instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.COMPLETE
        assert decisions[0].scenario_id == test_scenario.id
        assert "terminal" in decisions[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_pause_on_user_signal(
        self, orchestrator, tenant_id, snapshot, test_scenario, active_instance, config_store
    ):
        """Test pausing scenario when user requests pause."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        # Set pause signal
        snapshot.scenario_signal = ScenarioSignal.PAUSE

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[active_instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.PAUSE
        assert decisions[0].scenario_id == test_scenario.id

    @pytest.mark.asyncio
    async def test_cancel_on_user_signal(
        self, orchestrator, tenant_id, snapshot, test_scenario, active_instance, config_store
    ):
        """Test cancelling scenario when user requests cancellation."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        # Set cancel signal
        snapshot.scenario_signal = ScenarioSignal.CANCEL

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[active_instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.CANCEL
        assert decisions[0].scenario_id == test_scenario.id

    @pytest.mark.asyncio
    async def test_pause_on_loop_detection(
        self, orchestrator, tenant_id, snapshot, test_scenario, active_instance, config_store
    ):
        """Test pausing scenario when loop is detected."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        # Simulate loop by visiting step multiple times
        active_instance.visited_steps[test_scenario.entry_step_id] = 5

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[active_instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.PAUSE
        assert "loop" in decisions[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_start_new_scenario(
        self, orchestrator, tenant_id, snapshot, test_scenario, config_store
    ):
        """Test starting a new scenario from candidates."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        candidates = [
            ScoredScenario(
                scenario_id=test_scenario.id,
                score=0.8,
                scenario_name="Test Scenario",
                reasoning="High relevance",
            )
        ]

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=candidates,
            active_instances=[],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.START
        assert decisions[0].scenario_id == test_scenario.id
        assert decisions[0].entry_step_id == test_scenario.entry_step_id

    @pytest.mark.asyncio
    async def test_dont_start_low_score_candidate(
        self, orchestrator, tenant_id, snapshot, test_scenario, config_store
    ):
        """Test not starting scenario with low relevance score."""
        # Add scenario to store
        await config_store.save_scenario(test_scenario)

        candidates = [
            ScoredScenario(
                scenario_id=test_scenario.id,
                score=0.3,  # Below threshold
                scenario_name="Test Scenario",
                reasoning="Low relevance",
            )
        ]

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=candidates,
            active_instances=[],
            applied_rules=[],
        )

        # Should not start scenario
        assert len(decisions) == 0

    @pytest.mark.asyncio
    async def test_multiple_active_scenarios(
        self, orchestrator, tenant_id, snapshot, test_scenario, config_store
    ):
        """Test handling multiple active scenarios."""
        # Create second scenario
        scenario2_id = uuid4()
        step_id = uuid4()
        scenario2 = Scenario(
            id=scenario2_id,
            tenant_id=tenant_id,
            agent_id=uuid4(),
            name="Second Scenario",
            description="Second test scenario",
            enabled=True,
            entry_step_id=step_id,
            steps=[
                ScenarioStep(
                    id=step_id,
                    scenario_id=scenario2_id,
                    name="step1",
                    is_terminal=True,
                    transitions=[],
                )
            ],
        )

        await config_store.save_scenario(test_scenario)
        await config_store.save_scenario(scenario2)

        instance1 = ScenarioInstance(
            scenario_id=test_scenario.id,
            scenario_version=1,
            current_step_id=test_scenario.entry_step_id,
            visited_steps={},
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        instance2 = ScenarioInstance(
            scenario_id=scenario2.id,
            scenario_version=1,
            current_step_id=scenario2.steps[0].id,
            visited_steps={},
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance1, instance2],
            applied_rules=[],
        )

        # Should have decisions for both scenarios
        assert len(decisions) == 2
        scenario_ids = {d.scenario_id for d in decisions}
        assert test_scenario.id in scenario_ids
        assert scenario2.id in scenario_ids


class TestTransitionDecisions:
    """Test step transition decisions."""

    @pytest.mark.asyncio
    async def test_make_transition_decisions(
        self, orchestrator, tenant_id, test_scenario, active_instance, config_store
    ):
        """Test making transition decisions for continuing scenarios."""
        await config_store.save_scenario(test_scenario)

        lifecycle_decisions = [
            ScenarioLifecycleDecision(
                scenario_id=test_scenario.id,
                action=ScenarioLifecycleAction.CONTINUE,
                reasoning="Continue",
            )
        ]

        transitions = await orchestrator.make_transition_decisions(
            tenant_id=tenant_id,
            active_instances=[active_instance],
            lifecycle_decisions=lifecycle_decisions,
        )

        assert len(transitions) == 1
        assert transitions[0].scenario_id == test_scenario.id
        assert transitions[0].source_step_id == active_instance.current_step_id

    @pytest.mark.asyncio
    async def test_no_transitions_for_non_continuing_scenarios(
        self, orchestrator, tenant_id, test_scenario, active_instance, config_store
    ):
        """Test no transitions for paused/completed/cancelled scenarios."""
        await config_store.save_scenario(test_scenario)

        lifecycle_decisions = [
            ScenarioLifecycleDecision(
                scenario_id=test_scenario.id,
                action=ScenarioLifecycleAction.PAUSE,
                reasoning="Paused",
            )
        ]

        transitions = await orchestrator.make_transition_decisions(
            tenant_id=tenant_id,
            active_instances=[active_instance],
            lifecycle_decisions=lifecycle_decisions,
        )

        # No transitions for paused scenarios
        assert len(transitions) == 0


class TestContributionPlanning:
    """Test contribution planning."""

    @pytest.mark.asyncio
    async def test_determine_contributions(
        self, orchestrator, tenant_id, test_scenario, config_store
    ):
        """Test determining contributions from active scenarios."""
        await config_store.save_scenario(test_scenario)

        lifecycle_decisions = [
            ScenarioLifecycleDecision(
                scenario_id=test_scenario.id,
                action=ScenarioLifecycleAction.START,
                reasoning="Start",
                entry_step_id=test_scenario.entry_step_id,
            )
        ]

        plan = await orchestrator.determine_contributions(
            tenant_id=tenant_id,
            lifecycle_decisions=lifecycle_decisions,
            transition_decisions=[],
            applied_rules=[],
        )

        assert len(plan.contributions) == 1
        assert plan.contributions[0].scenario_id == test_scenario.id

    @pytest.mark.asyncio
    async def test_no_contributions_from_paused_scenarios(
        self, orchestrator, tenant_id, test_scenario, config_store
    ):
        """Test that paused scenarios don't contribute."""
        await config_store.save_scenario(test_scenario)

        lifecycle_decisions = [
            ScenarioLifecycleDecision(
                scenario_id=test_scenario.id,
                action=ScenarioLifecycleAction.PAUSE,
                reasoning="Paused",
            )
        ]

        plan = await orchestrator.determine_contributions(
            tenant_id=tenant_id,
            lifecycle_decisions=lifecycle_decisions,
            transition_decisions=[],
            applied_rules=[],
        )

        # Paused scenarios don't contribute
        assert len(plan.contributions) == 0
