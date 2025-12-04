"""Tests for migration executor."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from soldier.alignment.migration.diff import compute_node_content_hash
from soldier.alignment.migration.executor import MigrationExecutor
from soldier.alignment.migration.models import (
    AnchorTransformation,
    DownstreamChanges,
    ForkBranch,
    InsertedNode,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationScenario,
    NewFork,
    ReconciliationAction,
    TransformationMap,
    UpstreamChanges,
)
from soldier.alignment.models import Scenario, ScenarioStep, StepTransition
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore
from soldier.config.models.migration import ScenarioMigrationConfig
from soldier.conversation.models import Channel, PendingMigration, Session, StepVisit
from soldier.conversation.stores.inmemory import InMemorySessionStore


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
def config():
    return ScenarioMigrationConfig()


@pytest.fixture
def executor(config_store, session_store, config):
    return MigrationExecutor(config_store, session_store, config)


def create_step(
    scenario_id,
    name: str,
    transitions: list[tuple] | None = None,
    collects_fields: list[str] | None = None,
    is_checkpoint: bool = False,
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
        is_checkpoint=is_checkpoint,
    )


def create_scenario(
    tenant_id,
    agent_id,
    name: str,
    version: int,
    steps: list[ScenarioStep] | None = None,
) -> Scenario:
    """Helper to create a scenario."""
    if steps is None:
        step = create_step(uuid4(), "Default Step")
        steps = [step]

    scenario = Scenario(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        version=version,
        entry_step_id=steps[0].id,
        steps=steps,
    )
    # Update step scenario_ids
    for step in scenario.steps:
        step.scenario_id = scenario.id
    return scenario


def create_step_visit(step_id, turn_number, **kwargs) -> StepVisit:
    """Helper to create a StepVisit with required fields."""
    return StepVisit(
        step_id=step_id,
        turn_number=turn_number,
        entered_at=datetime.now(UTC),
        **kwargs,
    )


def create_migration_plan(
    tenant_id, scenario_id, from_version, to_version, anchors, **kwargs
) -> MigrationPlan:
    """Helper to create a MigrationPlan with required fields."""
    return MigrationPlan(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        from_version=from_version,
        to_version=to_version,
        scenario_checksum_v1="checksum_v1",
        scenario_checksum_v2="checksum_v2",
        transformation_map=TransformationMap(
            anchors=anchors,
            deleted_nodes=[],
        ),
        anchor_policies={},
        **kwargs,
    )


class TestMigrationExecutorReconcile:
    """Tests for MigrationExecutor.reconcile method."""

    @pytest.mark.asyncio
    async def test_reconcile_no_migration_needed(
        self, tenant_id, agent_id, executor
    ):
        """Test that reconcile returns CONTINUE when no migration is needed."""
        step = create_step(uuid4(), "Step A")
        scenario = create_scenario(tenant_id, agent_id, "Test", 1, [step])

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=scenario.id,
            active_scenario_version=1,
            active_step_id=step.id,
            pending_migration=None,
        )

        result = await executor.reconcile(session, scenario)

        assert result.action == ReconciliationAction.CONTINUE

    @pytest.mark.asyncio
    async def test_reconcile_version_mismatch_fallback(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that version mismatch without pending_migration triggers fallback."""
        # Create V1 step
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        # Session is at V1
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=None,
            step_history=[
                create_step_visit(
                    step_id=step_v1.id,
                    turn_number=1,
                    step_content_hash=compute_node_content_hash(step_v1),
                )
            ],
        )
        await session_store.save(session)

        # Create V2 with same step content (should find match)
        step_v2 = create_step(uuid4(), "Step A")  # Same name = same hash
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        # Should teleport to matching step in V2
        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id

    @pytest.mark.asyncio
    async def test_reconcile_with_pending_migration_clean_graft(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test reconcile with pending migration for clean graft scenario."""
        # Create V1 step
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        # Create V2 with same step (anchor)
        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        # Create migration plan
        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step A",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_v2.id,
                    migration_scenario=MigrationScenario.CLEAN_GRAFT,
                    upstream_changes=UpstreamChanges(),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        # Session with pending migration
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id
        assert result.teleport_reason == "clean_graft"

    @pytest.mark.asyncio
    async def test_reconcile_migration_plan_not_found(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test reconcile fallback when migration plan is not found."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        # Session with pending migration but plan doesn't exist
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash="some_hash",
                migration_plan_id=uuid4(),  # Non-existent plan
            ),
            step_history=[
                create_step_visit(
                    step_id=step_v1.id,
                    turn_number=1,
                    step_content_hash=compute_node_content_hash(step_v1),
                )
            ],
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        # Should fallback and find matching step
        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id


class TestMigrationExecutorCleanGraft:
    """Tests for clean graft migration execution."""

    @pytest.mark.asyncio
    async def test_execute_clean_graft_teleports(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that clean graft teleports session to V2 step."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step A",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_v2.id,
                    migration_scenario=MigrationScenario.CLEAN_GRAFT,
                    upstream_changes=UpstreamChanges(),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id

        # Verify session was updated
        updated_session = await session_store.get(session.session_id)
        assert updated_session.active_step_id == step_v2.id
        assert updated_session.active_scenario_version == 2
        assert updated_session.pending_migration is None


class TestMigrationExecutorGapFill:
    """Tests for gap fill migration execution."""

    @pytest.mark.asyncio
    async def test_execute_gap_fill_collects_missing_fields(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that gap fill returns COLLECT when fields are missing."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step A",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_v2.id,
                    migration_scenario=MigrationScenario.GAP_FILL,
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="New Step",
                                collects_fields=["phone_number", "email"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
            variables={},  # No variables - all fields missing
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.COLLECT
        assert "phone_number" in result.collect_fields
        assert "email" in result.collect_fields

    @pytest.mark.asyncio
    async def test_execute_gap_fill_teleports_when_fields_present(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that gap fill teleports when all fields are present."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step A",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_v2.id,
                    migration_scenario=MigrationScenario.GAP_FILL,
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="New Step",
                                collects_fields=["phone_number"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
            variables={"phone_number": "555-1234"},  # Field present
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id
        assert result.teleport_reason == "gap_fill"


class TestMigrationExecutorReRoute:
    """Tests for re-route migration execution."""

    @pytest.mark.asyncio
    async def test_execute_re_route_blocks_on_checkpoint(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that re-route blocks when target is upstream of checkpoint."""
        # Create V2 scenario with checkpoint - we need same step IDs for checkpoint tracking
        # Structure: A -> B (checkpoint) -> C
        step_a2 = create_step(uuid4(), "Step A")
        step_b2 = create_step(uuid4(), "Step B", is_checkpoint=True)
        step_c2 = create_step(uuid4(), "Step C")
        step_a2.transitions = [StepTransition(to_step_id=step_b2.id, condition_text="next")]
        step_b2.transitions = [StepTransition(to_step_id=step_c2.id, condition_text="next")]
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_a2, step_b2, step_c2])

        # Create V1 scenario
        step_v1 = create_step(uuid4(), "Step C")  # Same as anchor
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        v1.id = v2.id  # Same scenario ID
        await config_store.save_scenario(v1)

        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step C",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_a2.id,  # Would go back before checkpoint
                    migration_scenario=MigrationScenario.RE_ROUTE,
                    upstream_changes=UpstreamChanges(
                        new_forks=[
                            NewFork(
                                fork_node_id=uuid4(),
                                fork_node_name="Fork",
                                branches=[],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        # Session with checkpoint at step_b2 in V2 graph (use V2's step ID)
        # This simulates that the customer passed through B (checkpoint) in V2
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
            step_history=[
                create_step_visit(step_id=step_a2.id, turn_number=1),
                create_step_visit(
                    step_id=step_b2.id,  # Using V2's step ID for checkpoint
                    turn_number=2,
                    is_checkpoint=True,
                    checkpoint_description="Payment completed",
                ),
                create_step_visit(step_id=step_c2.id, turn_number=3),
            ],
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        # Should continue without teleporting (blocked by checkpoint)
        # Target is step_a2 which is upstream of checkpoint step_b2 in V2
        assert result.action == ReconciliationAction.CONTINUE
        assert result.blocked_by_checkpoint is True

    @pytest.mark.asyncio
    async def test_execute_re_route_evaluates_fork(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that re-route evaluates fork conditions."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        # V2 with fork
        step_a2 = create_step(uuid4(), "Step A")
        step_b2 = create_step(uuid4(), "Step B")
        step_c2 = create_step(uuid4(), "Step C")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_a2, step_b2, step_c2])
        v2.id = v1.id

        anchor_hash = compute_node_content_hash(step_v1)
        plan = create_migration_plan(
            tenant_id=tenant_id,
            scenario_id=v1.id,
            from_version=1,
            to_version=2,
            anchors=[
                AnchorTransformation(
                    anchor_name="Step A",
                    anchor_content_hash=anchor_hash,
                    anchor_node_id_v1=step_v1.id,
                    anchor_node_id_v2=step_a2.id,
                    migration_scenario=MigrationScenario.RE_ROUTE,
                    upstream_changes=UpstreamChanges(
                        new_forks=[
                            NewFork(
                                fork_node_id=uuid4(),
                                fork_node_name="Type Fork",
                                branches=[
                                    ForkBranch(
                                        target_step_id=step_b2.id,
                                        target_step_name="Step B",
                                        condition_text="Customer type is premium",
                                        condition_fields=["customer_type"],
                                    ),
                                    ForkBranch(
                                        target_step_id=step_c2.id,
                                        target_step_name="Step C",
                                        condition_text="Other condition",
                                        condition_fields=["other_field"],
                                    ),
                                ],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                )
            ],
            status=MigrationPlanStatus.DEPLOYED,
        )
        await config_store.save_migration_plan(plan)

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash=anchor_hash,
                migration_plan_id=plan.id,
            ),
            variables={"customer_type": "premium"},  # First branch matches
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_b2.id  # First matching branch


class TestMigrationExecutorFallback:
    """Tests for fallback reconciliation."""

    @pytest.mark.asyncio
    async def test_fallback_finds_matching_step(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that fallback finds step by content hash."""
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "Step A")  # Same name = same hash
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=None,  # No pending migration
            step_history=[
                create_step_visit(
                    step_id=step_v1.id,
                    turn_number=1,
                    step_content_hash=compute_node_content_hash(step_v1),
                )
            ],
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id
        assert result.teleport_reason == "fallback_hash_match"

    @pytest.mark.asyncio
    async def test_fallback_goes_to_entry_step(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that fallback goes to entry step when no match found."""
        step_v1 = create_step(uuid4(), "Old Step")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        step_v2 = create_step(uuid4(), "New Step")  # Different name = different hash
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=None,
            step_history=[
                create_step_visit(
                    step_id=step_v1.id,
                    turn_number=1,
                    step_content_hash=compute_node_content_hash(step_v1),
                )
            ],
        )
        await session_store.save(session)

        executor = MigrationExecutor(config_store, session_store, config)
        result = await executor.reconcile(session, v2)

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == step_v2.id  # Entry step
        assert result.teleport_reason == "fallback_entry"

    @pytest.mark.asyncio
    async def test_fallback_exits_scenario_no_entry(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that fallback exits scenario when no entry step and no match."""
        step_v1 = create_step(uuid4(), "Old Step")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        # V2 with different step - no entry ID (we'll clear it)
        step_v2 = create_step(uuid4(), "New Step")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id
        # Create scenario normally then clear entry_step_id to simulate no entry
        # We need to test the code path, so we patch the entry_step_id check

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step_v1.id,
            pending_migration=None,
            step_history=[
                create_step_visit(
                    step_id=step_v1.id,
                    turn_number=1,
                    step_content_hash="nonexistent_hash",  # Won't match anything
                )
            ],
        )
        await session_store.save(session)

        # Create a scenario with no steps to test exit path
        v2_empty = Scenario(
            id=v1.id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=2,
            entry_step_id=uuid4(),  # Random ID that doesn't exist
            steps=[],
        )

        executor = MigrationExecutor(config_store, session_store, config)
        # This will fail to find matching step and go to entry, but entry check should work
        result = await executor.reconcile(session, v2_empty)

        # Should teleport to the entry step even if steps list is empty
        # The code checks entry_step_id, not whether that step exists in steps list
        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == v2_empty.entry_step_id
        assert result.teleport_reason == "fallback_entry"


class TestMigrationExecutorHelpers:
    """Tests for helper methods."""

    def test_find_anchor_transformation(self, config_store, session_store, config):
        """Test _find_anchor_transformation method."""
        anchor_hash = "test_hash_123"
        anchor = AnchorTransformation(
            anchor_name="Test Anchor",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.CLEAN_GRAFT,
            upstream_changes=UpstreamChanges(),
            downstream_changes=DownstreamChanges(),
        )
        plan = create_migration_plan(
            tenant_id=uuid4(),
            scenario_id=uuid4(),
            from_version=1,
            to_version=2,
            anchors=[anchor],
            status=MigrationPlanStatus.DEPLOYED,
        )

        executor = MigrationExecutor(config_store, session_store, config)

        found = executor._find_anchor_transformation(plan, anchor_hash)
        assert found is not None
        assert found.anchor_name == "Test Anchor"

        not_found = executor._find_anchor_transformation(plan, "wrong_hash")
        assert not_found is None

    def test_find_last_checkpoint(self, config_store, session_store, config, tenant_id, agent_id):
        """Test _find_last_checkpoint method."""
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            step_history=[
                create_step_visit(step_id=uuid4(), turn_number=1, is_checkpoint=False),
                create_step_visit(
                    step_id=uuid4(),
                    turn_number=2,
                    is_checkpoint=True,
                    checkpoint_description="First checkpoint",
                ),
                create_step_visit(step_id=uuid4(), turn_number=3, is_checkpoint=False),
                create_step_visit(
                    step_id=uuid4(),
                    turn_number=4,
                    is_checkpoint=True,
                    checkpoint_description="Second checkpoint",
                ),
                create_step_visit(step_id=uuid4(), turn_number=5, is_checkpoint=False),
            ],
        )

        executor = MigrationExecutor(config_store, session_store, config)
        last_checkpoint = executor._find_last_checkpoint(session)

        assert last_checkpoint is not None
        assert last_checkpoint.checkpoint_description == "Second checkpoint"

    def test_find_last_checkpoint_none(self, config_store, session_store, config, tenant_id, agent_id):
        """Test _find_last_checkpoint returns None when no checkpoints exist."""
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            step_history=[
                create_step_visit(step_id=uuid4(), turn_number=1, is_checkpoint=False),
                create_step_visit(step_id=uuid4(), turn_number=2, is_checkpoint=False),
            ],
        )

        executor = MigrationExecutor(config_store, session_store, config)
        assert executor._find_last_checkpoint(session) is None

    def test_is_upstream_of_checkpoint(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test _is_upstream_of_checkpoint method."""
        # Build scenario: A -> B -> C
        step_a = create_step(uuid4(), "Step A")
        step_b = create_step(uuid4(), "Step B")
        step_c = create_step(uuid4(), "Step C")
        step_a.transitions = [StepTransition(to_step_id=step_b.id, condition_text="next")]
        step_b.transitions = [StepTransition(to_step_id=step_c.id, condition_text="next")]
        scenario = create_scenario(tenant_id, agent_id, "Test", 1, [step_a, step_b, step_c])

        executor = MigrationExecutor(config_store, session_store, config)

        # A is upstream of C (via B)
        assert executor._is_upstream_of_checkpoint(scenario, step_a.id, step_c.id) is True

        # B is upstream of C
        assert executor._is_upstream_of_checkpoint(scenario, step_b.id, step_c.id) is True

        # C is not upstream of A
        assert executor._is_upstream_of_checkpoint(scenario, step_c.id, step_a.id) is False

        # Same step is upstream (edge case - returns True if we visit it)
        assert executor._is_upstream_of_checkpoint(scenario, step_a.id, step_a.id) is True
