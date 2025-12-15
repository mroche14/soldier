"""Unit tests for scenario lifecycle transitions."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.context.models import ScenarioSignal
from ruche.brains.focal.phases.filtering.models import ScenarioLifecycleAction
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
def multi_step_scenario(tenant_id, agent_id):
    """Create a multi-step scenario for lifecycle testing."""
    scenario_id = uuid4()
    step1_id = uuid4()
    step2_id = uuid4()
    step3_id = uuid4()

    step1 = ScenarioStep(
        id=step1_id,
        scenario_id=scenario_id,
        name="step1",
        transitions=[StepTransition(to_step_id=step2_id, condition_text="default", priority=0)],
    )

    step2 = ScenarioStep(
        id=step2_id,
        scenario_id=scenario_id,
        name="step2",
        transitions=[StepTransition(to_step_id=step3_id, condition_text="default", priority=0)],
    )

    step3 = ScenarioStep(
        id=step3_id,
        scenario_id=scenario_id,
        name="step3",
        is_terminal=True,
        transitions=[],
    )

    return Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Multi-Step Scenario",
        description="Scenario for lifecycle testing",
        enabled=True,
        entry_step_id=step1_id,
        steps=[step1, step2, step3],
    )


class TestLifecycleFlows:
    """Test complete lifecycle flows."""

    @pytest.mark.asyncio
    async def test_start_continue_complete_flow(
        self, orchestrator, tenant_id, multi_step_scenario, config_store
    ):
        """Test START -> CONTINUE -> COMPLETE flow."""
        await config_store.save_scenario(multi_step_scenario)

        # 1. START scenario
        snapshot = SituationSnapshot(
            message="start",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )
        candidates = [
            ScoredScenario(
                scenario_id=multi_step_scenario.id,
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

        # 2. CONTINUE scenario (at step 1)
        instance = ScenarioInstance(
            scenario_id=multi_step_scenario.id,
            scenario_version=1,
            current_step_id=multi_step_scenario.steps[0].id,
            visited_steps={multi_step_scenario.steps[0].id: 1},
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.CONTINUE

        # 3. CONTINUE scenario (at step 2)
        instance.current_step_id = multi_step_scenario.steps[1].id

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.CONTINUE

        # 4. COMPLETE scenario (reached terminal step)
        instance.current_step_id = multi_step_scenario.steps[2].id  # Terminal step

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.COMPLETE

    @pytest.mark.asyncio
    async def test_start_pause_continue_complete_flow(
        self, orchestrator, tenant_id, multi_step_scenario, config_store
    ):
        """Test START -> PAUSE -> CONTINUE -> COMPLETE flow."""
        await config_store.save_scenario(multi_step_scenario)

        # 1. START scenario
        snapshot = SituationSnapshot(
            message="start",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )
        candidates = [
            ScoredScenario(
                scenario_id=multi_step_scenario.id,
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

        assert decisions[0].action == ScenarioLifecycleAction.START

        # 2. PAUSE scenario
        instance = ScenarioInstance(
            scenario_id=multi_step_scenario.id,
            scenario_version=1,
            current_step_id=multi_step_scenario.steps[0].id,
            visited_steps={multi_step_scenario.steps[0].id: 1},
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        pause_snapshot = SituationSnapshot(
            message="hold on",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.PAUSE,
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=pause_snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert decisions[0].action == ScenarioLifecycleAction.PAUSE

        # 3. CONTINUE scenario (resume from pause)
        instance.status = "paused"
        resume_snapshot = SituationSnapshot(
            message="continue",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=resume_snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert decisions[0].action == ScenarioLifecycleAction.CONTINUE

        # 4. COMPLETE scenario
        instance.current_step_id = multi_step_scenario.steps[2].id

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=resume_snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert decisions[0].action == ScenarioLifecycleAction.COMPLETE

    @pytest.mark.asyncio
    async def test_start_cancel_flow(
        self, orchestrator, tenant_id, multi_step_scenario, config_store
    ):
        """Test START -> CANCEL flow."""
        await config_store.save_scenario(multi_step_scenario)

        # 1. START scenario
        snapshot = SituationSnapshot(
            message="start",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )
        candidates = [
            ScoredScenario(
                scenario_id=multi_step_scenario.id,
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

        assert decisions[0].action == ScenarioLifecycleAction.START

        # 2. CANCEL scenario
        instance = ScenarioInstance(
            scenario_id=multi_step_scenario.id,
            scenario_version=1,
            current_step_id=multi_step_scenario.steps[0].id,
            visited_steps={multi_step_scenario.steps[0].id: 1},
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        cancel_snapshot = SituationSnapshot(
            message="never mind",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.CANCEL,
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=cancel_snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.CANCEL

    @pytest.mark.asyncio
    async def test_multiple_scenarios_simultaneously(
        self, orchestrator, tenant_id, agent_id, multi_step_scenario, config_store
    ):
        """Test multiple scenarios running simultaneously."""
        # Create second scenario
        scenario2_id = uuid4()
        step_id = uuid4()
        scenario2 = Scenario(
            id=scenario2_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Second Scenario",
            description="Second test scenario",
            enabled=True,
            entry_step_id=step_id,
            steps=[
                ScenarioStep(
                    id=step_id,
                    scenario_id=scenario2_id,
                    name="step1",
                    transitions=[],
                )
            ],
        )

        await config_store.save_scenario(multi_step_scenario)
        await config_store.save_scenario(scenario2)

        # Both scenarios active
        instance1 = ScenarioInstance(
            scenario_id=multi_step_scenario.id,
            scenario_version=1,
            current_step_id=multi_step_scenario.steps[0].id,
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

        snapshot = SituationSnapshot(
            message="test",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance1, instance2],
            applied_rules=[],
        )

        # Should have decisions for both
        assert len(decisions) == 2
        assert all(d.action == ScenarioLifecycleAction.CONTINUE for d in decisions)

        # Complete first scenario
        instance1.current_step_id = multi_step_scenario.steps[2].id

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance1, instance2],
            applied_rules=[],
        )

        # First completes, second continues
        assert len(decisions) == 2
        scenario1_decision = next(
            d for d in decisions if d.scenario_id == multi_step_scenario.id
        )
        scenario2_decision = next(
            d for d in decisions if d.scenario_id == scenario2.id
        )
        assert scenario1_decision.action == ScenarioLifecycleAction.COMPLETE
        assert scenario2_decision.action == ScenarioLifecycleAction.CONTINUE

    @pytest.mark.asyncio
    async def test_pause_due_to_loop_detection(
        self, orchestrator, tenant_id, multi_step_scenario, config_store
    ):
        """Test automatic pause when loop is detected."""
        await config_store.save_scenario(multi_step_scenario)

        instance = ScenarioInstance(
            scenario_id=multi_step_scenario.id,
            scenario_version=1,
            current_step_id=multi_step_scenario.steps[0].id,
            visited_steps={multi_step_scenario.steps[0].id: 5},  # Visited 5 times
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            status="active",
        )

        snapshot = SituationSnapshot(
            message="test",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            scenario_signal=ScenarioSignal.UNKNOWN,
        )

        decisions = await orchestrator.make_lifecycle_decisions(
            tenant_id=tenant_id,
            snapshot=snapshot,
            candidates=[],
            active_instances=[instance],
            applied_rules=[],
        )

        assert len(decisions) == 1
        assert decisions[0].action == ScenarioLifecycleAction.PAUSE
        assert "loop" in decisions[0].reasoning.lower()
