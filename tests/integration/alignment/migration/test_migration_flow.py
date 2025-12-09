"""Integration tests for JIT migration flow.

Tests the full migration lifecycle from plan generation through execution.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from focal.alignment.engine import AlignmentEngine
from focal.alignment.migration.diff import compute_node_content_hash
from focal.alignment.migration.models import (
    MigrationPlanStatus,
    MigrationScenario,
    ReconciliationAction,
)
from focal.alignment.migration.planner import MigrationDeployer, MigrationPlanner
from focal.alignment.models import Scenario, ScenarioStep, StepTransition
from focal.alignment.stores.inmemory import InMemoryAgentConfigStore
from focal.config.models.migration import ScenarioMigrationConfig
from focal.conversation.models import Channel, Session, StepVisit
from focal.conversation.stores.inmemory import InMemorySessionStore
from focal.providers.embedding.mock import MockEmbeddingProvider
from focal.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for testing."""

    def __init__(self, default_response: str = "Test response") -> None:
        super().__init__(model="mock/test", step_name="test")
        self._default_response = default_response

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        return LLMResponse(content=self._default_response, model="mock", usage={})


def create_test_executors() -> dict[str, LLMExecutor]:
    """Create mock executors for testing."""
    extraction_resp = json.dumps({
        "intent": "test",
        "entities": [],
        "sentiment": "neutral",
        "urgency": "normal",
    })
    filter_resp = json.dumps({"evaluations": []})

    return {
        "context_extraction": MockLLMExecutor(extraction_resp),
        "rule_filtering": MockLLMExecutor(filter_resp),
        "generation": MockLLMExecutor("Test response"),
    }


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def config_store():
    return InMemoryAgentConfigStore()


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.fixture
def migration_config():
    return ScenarioMigrationConfig()


@pytest.fixture
def embedding_provider():
    return MockEmbeddingProvider()


def create_step(
    scenario_id,
    name: str,
    transitions: list[tuple] | None = None,
    collects_fields: list[str] | None = None,
) -> ScenarioStep:
    """Helper to create a step."""
    step_transitions = []
    if transitions:
        for to_id, condition in transitions:
            step_transitions.append(
                StepTransition(to_step_id=to_id, condition_text=condition)
            )
    return ScenarioStep(
        scenario_id=scenario_id,
        name=name,
        transitions=step_transitions,
        collects_profile_fields=collects_fields or [],
    )


def create_scenario(
    tenant_id,
    agent_id,
    name: str,
    version: int,
    steps: list[ScenarioStep],
) -> Scenario:
    """Helper to create a scenario."""
    scenario = Scenario(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        version=version,
        entry_step_id=steps[0].id,
        steps=steps,
    )
    for step in scenario.steps:
        step.scenario_id = scenario.id
    return scenario


class TestMigrationFullFlow:
    """Integration tests for complete migration workflow."""

    @pytest.mark.asyncio
    async def test_clean_graft_migration_flow(
        self,
        tenant_id,
        agent_id,
        config_store,
        session_store,
        migration_config,
        embedding_provider,
    ):
        """Test complete clean graft migration from plan to execution."""
        # Create V1 scenario: A -> B
        step_a_v1 = create_step(uuid4(), "Step A")
        step_b_v1 = create_step(uuid4(), "Step B")
        step_a_v1.transitions = [
            StepTransition(to_step_id=step_b_v1.id, condition_text="next")
        ]
        v1 = create_scenario(tenant_id, agent_id, "Test Flow", 1, [step_a_v1, step_b_v1])
        await config_store.save_scenario(v1)

        # Create a session at Step A in V1 with step_content_hash
        step_a_hash = compute_node_content_hash(step_a_v1)
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_a_v1.id,
            step_history=[
                StepVisit(
                    step_id=step_a_v1.id,
                    entered_at=datetime.now(UTC),
                    turn_number=1,
                    step_content_hash=step_a_hash,
                )
            ],
        )
        await session_store.save(session)

        # Create V2 scenario with same Step A (anchor) and Step B
        step_a_v2 = create_step(uuid4(), "Step A")  # Same content = anchor
        step_b_v2 = create_step(uuid4(), "Step B")  # Same content = anchor
        step_a_v2.transitions = [
            StepTransition(to_step_id=step_b_v2.id, condition_text="next")
        ]
        v2 = create_scenario(tenant_id, agent_id, "Test Flow", 2, [step_a_v2, step_b_v2])
        v2.id = v1.id  # Same scenario ID

        # Generate migration plan
        planner = MigrationPlanner(config_store, session_store, migration_config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        assert plan.status == MigrationPlanStatus.PENDING
        assert len(plan.transformation_map.anchors) == 2  # Step A and Step B are anchors

        # Find Step A anchor
        step_a_anchor = plan.transformation_map.get_anchor_by_hash(step_a_hash)
        assert step_a_anchor is not None
        assert step_a_anchor.migration_scenario == MigrationScenario.CLEAN_GRAFT

        # Approve the plan
        await planner.approve_plan(tenant_id, plan.id)
        approved_plan = await config_store.get_migration_plan(tenant_id, plan.id)
        assert approved_plan.status == MigrationPlanStatus.APPROVED

        # Deploy the plan
        deployer = MigrationDeployer(config_store, session_store, migration_config)
        result = await deployer.deploy(tenant_id, plan.id)

        assert result["sessions_marked"] == 1

        # Verify session was marked
        updated_session = await session_store.get(session.session_id)
        assert updated_session.pending_migration is not None
        assert updated_session.pending_migration.target_version == 2
        assert updated_session.pending_migration.anchor_content_hash == step_a_hash

        # Save V2 scenario (simulating scenario update)
        await config_store.save_scenario(v2)

        # Create alignment engine with migration support
        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            migration_config=migration_config,
            executors=create_test_executors(),
        )

        # Process a turn - should trigger JIT migration
        alignment_result = await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Verify migration was applied
        final_session = await session_store.get(session.session_id)
        assert final_session.pending_migration is None  # Cleared after migration
        assert final_session.active_step_id == step_a_v2.id  # Teleported to V2's Step A
        assert final_session.active_scenario_version == 2

        # Verify result includes reconciliation info
        assert alignment_result is not None

    @pytest.mark.asyncio
    async def test_gap_fill_migration_collects_data(
        self,
        tenant_id,
        agent_id,
        config_store,
        session_store,
        migration_config,
        embedding_provider,
    ):
        """Test that gap fill migration prompts for missing data."""
        # Create V1 scenario: Simple step
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test Flow", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v1_hash = compute_node_content_hash(step_v1)

        # Create session without phone_number
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user456",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            variables={},  # No phone number
            step_history=[
                StepVisit(
                    step_id=step_v1.id,
                    entered_at=datetime.now(UTC),
                    turn_number=1,
                    step_content_hash=step_v1_hash,
                )
            ],
        )
        await session_store.save(session)

        # Create V2 with new step that collects phone_number before Step A
        step_phone = create_step(uuid4(), "Collect Phone", collects_fields=["phone_number"])
        step_a_v2 = create_step(uuid4(), "Step A")
        step_phone.transitions = [
            StepTransition(to_step_id=step_a_v2.id, condition_text="after phone")
        ]
        v2 = create_scenario(tenant_id, agent_id, "Test Flow", 2, [step_phone, step_a_v2])
        v2.id = v1.id

        # Generate and approve plan
        planner = MigrationPlanner(config_store, session_store, migration_config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Find the Step A anchor and verify it has GAP_FILL scenario
        anchor = plan.transformation_map.get_anchor_by_hash(step_v1_hash)
        assert anchor is not None
        assert anchor.migration_scenario == MigrationScenario.GAP_FILL

        await planner.approve_plan(tenant_id, plan.id)

        # Deploy
        deployer = MigrationDeployer(config_store, session_store, migration_config)
        await deployer.deploy(tenant_id, plan.id)

        # Save V2
        await config_store.save_scenario(v2)

        # Create engine and process turn
        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            migration_config=migration_config,
            executors=create_test_executors(),
        )

        result = await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Should get COLLECT response asking for phone_number
        assert result.reconciliation_result is not None
        assert result.reconciliation_result.action == ReconciliationAction.COLLECT
        assert "phone_number" in result.reconciliation_result.collect_fields

    @pytest.mark.asyncio
    async def test_version_mismatch_fallback(
        self,
        tenant_id,
        agent_id,
        config_store,
        session_store,
        migration_config,
        embedding_provider,
    ):
        """Test fallback reconciliation when no migration plan exists."""
        # Create V1 scenario
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test Flow", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v1_hash = compute_node_content_hash(step_v1)

        # Create session at V1
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user789",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            step_history=[
                StepVisit(
                    step_id=step_v1.id,
                    entered_at=datetime.now(UTC),
                    turn_number=1,
                    step_content_hash=step_v1_hash,
                )
            ],
        )
        await session_store.save(session)

        # Create V2 with same step (for hash match in fallback)
        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test Flow", 2, [step_v2])
        v2.id = v1.id

        # Save V2 directly without migration plan
        await config_store.save_scenario(v2)

        # Create engine
        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            migration_config=migration_config,
            executors=create_test_executors(),
        )

        # Process turn - should trigger fallback reconciliation
        await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Should have relocated to matching step (by hash)
        final_session = await session_store.get(session.session_id)
        assert final_session.active_step_id == step_v2.id
        assert final_session.active_scenario_version == 2
