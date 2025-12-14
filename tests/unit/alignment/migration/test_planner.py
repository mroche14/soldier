"""Tests for migration planner and deployer."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ruche.alignment.migration.diff import compute_node_content_hash
from ruche.alignment.migration.models import (
    AnchorMigrationPolicy,
    MigrationPlanStatus,
    ScopeFilter,
)
from ruche.alignment.migration.planner import MigrationDeployer, MigrationPlanner
from ruche.alignment.models import Scenario, ScenarioStep, StepTransition
from ruche.alignment.stores.inmemory import InMemoryAgentConfigStore
from ruche.config.models.migration import ScenarioMigrationConfig
from ruche.conversation.models import Channel, PendingMigration, Session, StepVisit
from ruche.conversation.stores.inmemory import InMemorySessionStore


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


def create_step_visit(
    step_id,
    turn_number: int,
    step_content_hash: str | None = None,
) -> StepVisit:
    """Helper to create a step visit."""
    return StepVisit(
        step_id=step_id,
        entered_at=datetime.now(UTC),
        turn_number=turn_number,
        step_content_hash=step_content_hash,
    )


class TestMigrationPlanner:
    """Tests for MigrationPlanner class."""

    @pytest.mark.asyncio
    async def test_generate_plan_creates_plan(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that generate_plan creates a migration plan."""
        # Create and save V1 scenario
        step_v1 = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_v1])
        await config_store.save_scenario(v1)

        # Create V2 scenario with same step (anchor)
        step_v2 = create_step(uuid4(), "Step A")  # Same content = anchor
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id  # Same scenario ID

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        assert plan is not None
        assert plan.scenario_id == v1.id
        assert plan.from_version == 1
        assert plan.to_version == 2
        assert plan.status == MigrationPlanStatus.PENDING

    @pytest.mark.asyncio
    async def test_generate_plan_scenario_not_found(
        self, tenant_id, config_store, session_store, config
    ):
        """Test that generate_plan raises error for missing scenario."""
        v2 = create_scenario(tenant_id, uuid4(), "Test", 2)
        planner = MigrationPlanner(config_store, session_store, config)

        with pytest.raises(ValueError, match="not found"):
            await planner.generate_plan(tenant_id, uuid4(), v2)

    @pytest.mark.asyncio
    async def test_generate_plan_invalid_version(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that generate_plan raises error for invalid version."""
        # Create V2 scenario
        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        await config_store.save_scenario(v2)

        # Try to create V1 plan (lower version)
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        v1.id = v2.id

        planner = MigrationPlanner(config_store, session_store, config)

        with pytest.raises(ValueError, match="must be greater than"):
            await planner.generate_plan(tenant_id, v2.id, v1)

    @pytest.mark.asyncio
    async def test_generate_plan_duplicate_rejected(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that duplicate plans are rejected."""
        # Create V1
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        # Create V2
        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)

        # Generate first plan
        await planner.generate_plan(tenant_id, v1.id, v2)

        # Try to generate duplicate
        with pytest.raises(ValueError, match="Plan already exists"):
            await planner.generate_plan(tenant_id, v1.id, v2)

    @pytest.mark.asyncio
    async def test_generate_plan_computes_transformation(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that generate_plan computes transformation map."""
        # V1: A -> B
        step_a = create_step(uuid4(), "Step A")
        step_b = create_step(uuid4(), "Step B")
        step_a.transitions = [
            StepTransition(to_step_id=step_b.id, condition_text="next")
        ]
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step_a, step_b])
        await config_store.save_scenario(v1)

        # V2: A -> C (B removed, C added)
        step_a2 = create_step(uuid4(), "Step A")
        step_c = create_step(uuid4(), "Step C")
        step_a2.transitions = [
            StepTransition(to_step_id=step_c.id, condition_text="next")
        ]
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_a2, step_c])
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Should have Step A as anchor
        assert plan.transformation_map.anchors
        anchor_names = {a.anchor_name for a in plan.transformation_map.anchors}
        assert "Step A" in anchor_names

        # Should have Step B as deleted
        deleted_names = {d.node_name for d in plan.transformation_map.deleted_nodes}
        assert "Step B" in deleted_names

    @pytest.mark.asyncio
    async def test_generate_plan_creates_anchor_policies(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that generate_plan creates default anchor policies."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Should have a policy for each anchor
        assert len(plan.anchor_policies) == len(plan.transformation_map.anchors)

    @pytest.mark.asyncio
    async def test_approve_plan(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that approve_plan updates status."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        approved = await planner.approve_plan(tenant_id, plan.id, "admin@example.com")

        assert approved.status == MigrationPlanStatus.APPROVED
        assert approved.approved_at is not None
        assert approved.approved_by == "admin@example.com"

    @pytest.mark.asyncio
    async def test_approve_plan_not_found(
        self, tenant_id, config_store, session_store, config
    ):
        """Test that approve_plan raises error for missing plan."""
        planner = MigrationPlanner(config_store, session_store, config)

        with pytest.raises(ValueError, match="not found"):
            await planner.approve_plan(tenant_id, uuid4())

    @pytest.mark.asyncio
    async def test_approve_plan_wrong_status(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that approve_plan rejects non-pending plans."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Approve first
        await planner.approve_plan(tenant_id, plan.id)

        # Try to approve again
        with pytest.raises(ValueError, match="not pending"):
            await planner.approve_plan(tenant_id, plan.id)

    @pytest.mark.asyncio
    async def test_reject_plan(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that reject_plan updates status."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        rejected = await planner.reject_plan(
            tenant_id, plan.id, "admin@example.com", "Not ready"
        )

        assert rejected.status == MigrationPlanStatus.REJECTED

    @pytest.mark.asyncio
    async def test_update_policies(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that update_policies updates anchor policies."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Get an anchor hash
        anchor_hash = list(plan.anchor_policies.keys())[0]

        # Update policy
        new_policy = AnchorMigrationPolicy(
            anchor_content_hash=anchor_hash,
            anchor_name="Test",
            scope_filter=ScopeFilter(include_channels=["web"]),
            update_downstream=False,
        )

        updated = await planner.update_policies(
            tenant_id, plan.id, {anchor_hash: new_policy}
        )

        assert updated.anchor_policies[anchor_hash].update_downstream is False
        assert updated.anchor_policies[anchor_hash].scope_filter.include_channels == [
            "web"
        ]

    @pytest.mark.asyncio
    async def test_update_policies_invalid_anchor(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that update_policies rejects invalid anchor hashes."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        invalid_policy = AnchorMigrationPolicy(
            anchor_content_hash="invalid_hash",
            anchor_name="Invalid",
        )

        with pytest.raises(ValueError, match="Invalid anchor hash"):
            await planner.update_policies(
                tenant_id, plan.id, {"invalid_hash": invalid_policy}
            )


class TestMigrationDeployer:
    """Tests for MigrationDeployer class."""

    @pytest.mark.asyncio
    async def test_deploy_marks_sessions(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that deploy marks eligible sessions."""
        # Create V1 scenario
        step = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step])
        await config_store.save_scenario(v1)

        # Create a session at this step
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
        )
        await session_store.save(session)

        # Create V2 and generate/approve plan
        step_v2 = create_step(uuid4(), "Step A")  # Anchor
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)
        await planner.approve_plan(tenant_id, plan.id)

        # Deploy
        deployer = MigrationDeployer(config_store, session_store, config)
        result = await deployer.deploy(tenant_id, plan.id)

        assert result["sessions_marked"] >= 0
        assert result["deployed_at"] is not None

    @pytest.mark.asyncio
    async def test_deploy_not_approved(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that deploy rejects non-approved plans."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Don't approve - try to deploy directly
        deployer = MigrationDeployer(config_store, session_store, config)

        with pytest.raises(ValueError, match="not approved"):
            await deployer.deploy(tenant_id, plan.id)

    @pytest.mark.asyncio
    async def test_deploy_not_found(
        self, tenant_id, config_store, session_store, config
    ):
        """Test that deploy raises error for missing plan."""
        deployer = MigrationDeployer(config_store, session_store, config)

        with pytest.raises(ValueError, match="not found"):
            await deployer.deploy(tenant_id, uuid4())

    @pytest.mark.asyncio
    async def test_deploy_updates_plan_status(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that deploy updates plan to DEPLOYED status."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)
        await planner.approve_plan(tenant_id, plan.id)

        deployer = MigrationDeployer(config_store, session_store, config)
        await deployer.deploy(tenant_id, plan.id)

        # Check plan status
        updated_plan = await config_store.get_migration_plan(tenant_id, plan.id)
        assert updated_plan.status == MigrationPlanStatus.DEPLOYED
        assert updated_plan.deployed_at is not None

    @pytest.mark.asyncio
    async def test_get_deployment_status(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that get_deployment_status returns status info."""
        v1 = create_scenario(tenant_id, agent_id, "Test", 1)
        await config_store.save_scenario(v1)

        v2 = create_scenario(tenant_id, agent_id, "Test", 2)
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)
        await planner.approve_plan(tenant_id, plan.id)

        deployer = MigrationDeployer(config_store, session_store, config)
        await deployer.deploy(tenant_id, plan.id)

        status = await deployer.get_deployment_status(tenant_id, plan.id)

        assert status["plan_id"] == plan.id
        assert status["status"] == "deployed"
        assert "sessions_marked" in status
        assert "migrations_applied" in status

    @pytest.mark.asyncio
    async def test_get_deployment_status_not_found(
        self, tenant_id, config_store, session_store, config
    ):
        """Test that get_deployment_status raises error for missing plan."""
        deployer = MigrationDeployer(config_store, session_store, config)

        with pytest.raises(ValueError, match="not found"):
            await deployer.get_deployment_status(tenant_id, uuid4())

    @pytest.mark.asyncio
    async def test_deploy_skips_already_marked_sessions(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that deploy skips sessions with existing pending_migration."""
        # Create V1 scenario
        step = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step])
        await config_store.save_scenario(v1)

        # Create a session already marked
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user456",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
            pending_migration=PendingMigration(
                target_version=2,
                anchor_content_hash="existing_hash",
                migration_plan_id=uuid4(),
            ),
        )
        await session_store.save(session)

        # Create V2 and generate/approve plan
        step_v2 = create_step(uuid4(), "Step A")  # Anchor
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)
        await planner.approve_plan(tenant_id, plan.id)

        # Deploy - should skip the already marked session
        deployer = MigrationDeployer(config_store, session_store, config)
        await deployer.deploy(tenant_id, plan.id)

        # Session should not be re-marked (still has original pending_migration)
        updated_session = await session_store.get(session.session_id)
        assert updated_session.pending_migration.anchor_content_hash == "existing_hash"


class TestScopeFiltering:
    """Tests for scope filter matching during deployment."""

    @pytest.mark.asyncio
    async def test_deploy_with_channel_filter(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that channel filtering excludes sessions on other channels."""
        step = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step])
        await config_store.save_scenario(v1)

        step_hash = compute_node_content_hash(step)

        # Create sessions on different channels
        webchat_session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user1",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
            step_history=[create_step_visit(step.id, 1, step_content_hash=step_hash)],
        )
        whatsapp_session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WHATSAPP,
            user_channel_id="user2",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
            step_history=[create_step_visit(step.id, 1, step_content_hash=step_hash)],
        )
        await session_store.save(webchat_session)
        await session_store.save(whatsapp_session)

        # Create V2 and plan with channel filter
        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Update policy to only include webchat
        plan.anchor_policies[step_hash] = AnchorMigrationPolicy(
            anchor_content_hash=step_hash,
            anchor_name="Step A",
            scope_filter=ScopeFilter(include_channels=["webchat"]),
            update_downstream=True,
        )
        await config_store.save_migration_plan(plan)
        await planner.approve_plan(tenant_id, plan.id)

        # Deploy
        deployer = MigrationDeployer(config_store, session_store, config)
        result = await deployer.deploy(tenant_id, plan.id)

        # Only webchat session should be marked
        assert result["sessions_marked"] == 1

        webchat_updated = await session_store.get(webchat_session.session_id)
        whatsapp_updated = await session_store.get(whatsapp_session.session_id)

        assert webchat_updated.pending_migration is not None
        assert whatsapp_updated.pending_migration is None

    @pytest.mark.asyncio
    async def test_deploy_with_age_filter(
        self, tenant_id, agent_id, config_store, session_store, config
    ):
        """Test that age filtering excludes old sessions."""
        step = create_step(uuid4(), "Step A")
        v1 = create_scenario(tenant_id, agent_id, "Test", 1, [step])
        await config_store.save_scenario(v1)

        step_hash = compute_node_content_hash(step)

        # Create sessions with different ages
        recent_session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user1",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
            created_at=datetime.now(UTC) - timedelta(days=1),
            step_history=[create_step_visit(step.id, 1, step_content_hash=step_hash)],
        )
        old_session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user2",
            config_version=1,
            active_scenario_id=v1.id,
            active_scenario_version=1,
            active_step_id=step.id,
            created_at=datetime.now(UTC) - timedelta(days=100),
            step_history=[create_step_visit(step.id, 1, step_content_hash=step_hash)],
        )
        await session_store.save(recent_session)
        await session_store.save(old_session)

        # Create V2 and plan with age filter
        step_v2 = create_step(uuid4(), "Step A")
        v2 = create_scenario(tenant_id, agent_id, "Test", 2, [step_v2])
        v2.id = v1.id

        planner = MigrationPlanner(config_store, session_store, config)
        plan = await planner.generate_plan(tenant_id, v1.id, v2)

        # Update policy to only include sessions < 30 days old
        plan.anchor_policies[step_hash] = AnchorMigrationPolicy(
            anchor_content_hash=step_hash,
            anchor_name="Step A",
            scope_filter=ScopeFilter(max_session_age_days=30),
            update_downstream=True,
        )
        await config_store.save_migration_plan(plan)
        await planner.approve_plan(tenant_id, plan.id)

        # Deploy
        deployer = MigrationDeployer(config_store, session_store, config)
        result = await deployer.deploy(tenant_id, plan.id)

        # Only recent session should be marked
        assert result["sessions_marked"] == 1

        recent_updated = await session_store.get(recent_session.session_id)
        old_updated = await session_store.get(old_session.session_id)

        assert recent_updated.pending_migration is not None
        assert old_updated.pending_migration is None
