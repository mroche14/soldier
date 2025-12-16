"""Shared fixtures for migration module tests."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4, UUID

from ruche.brains.focal.models import Scenario, ScenarioStep, StepTransition
from ruche.brains.focal.migration.models import (
    MigrationPlan,
    MigrationPlanStatus,
    TransformationMap,
    AnchorTransformation,
    UpstreamChanges,
    DownstreamChanges,
    InsertedNode,
    DeletedNode,
    NewFork,
    ForkBranch,
    MigrationScenario,
    MigrationSummary,
    AnchorMigrationPolicy,
    ScopeFilter,
    ReconciliationResult,
    ReconciliationAction,
    FieldResolutionResult,
    ResolutionSource,
)
from ruche.conversation.models import Session, PendingMigration


# =============================================================================
# Basic Fixtures
# =============================================================================


@pytest.fixture
def tenant_id() -> UUID:
    """Generate a tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id() -> UUID:
    """Generate an agent ID."""
    return uuid4()


@pytest.fixture
def scenario_id() -> UUID:
    """Generate a scenario ID."""
    return uuid4()


# =============================================================================
# Scenario Fixtures
# =============================================================================


@pytest.fixture
def simple_scenario_v1(scenario_id: UUID, tenant_id: UUID, agent_id: UUID) -> Scenario:
    """Create a simple scenario V1 with 3 steps in sequence.

    Flow: entry -> ask_question -> complete
    """
    entry_id = uuid4()
    ask_id = uuid4()
    complete_id = uuid4()

    steps = [
        ScenarioStep(
            id=entry_id,
            scenario_id=scenario_id,
            name="Entry",
            description="Entry point",
            rule_ids=[],
            collects_profile_fields=[],
            transitions=[
                StepTransition(
                    to_step_id=ask_id,
                    condition_text="always",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=ask_id,
            scenario_id=scenario_id,
            name="Ask Question",
            description="Ask for information",
            rule_ids=[],
            collects_profile_fields=["user_email"],
            transitions=[
                StepTransition(
                    to_step_id=complete_id,
                    condition_text="email provided",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=complete_id,
            scenario_id=scenario_id,
            name="Complete",
            description="Completion step",
            rule_ids=[],
            collects_profile_fields=[],
            is_terminal=True,
            transitions=[],
        ),
    ]

    return Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Simple Flow",
        version=1,
        entry_step_id=entry_id,
        steps=steps,
    )


@pytest.fixture
def simple_scenario_v2(scenario_id: UUID, tenant_id: UUID, agent_id: UUID, simple_scenario_v1: Scenario) -> Scenario:
    """Create V2 with one new step inserted upstream of ask_question.

    Flow: entry -> verify_identity -> ask_question -> complete
    New step: verify_identity (collects user_phone)
    """
    entry_id = simple_scenario_v1.steps[0].id
    verify_id = uuid4()  # New step
    ask_id = simple_scenario_v1.steps[1].id
    complete_id = simple_scenario_v1.steps[2].id

    steps = [
        ScenarioStep(
            id=entry_id,
            scenario_id=scenario_id,
            name="Entry",
            description="Entry point",
            rule_ids=[],
            collects_profile_fields=[],
            transitions=[
                StepTransition(
                    to_step_id=verify_id,  # Now goes to verify
                    condition_text="always",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=verify_id,
            scenario_id=scenario_id,
            name="Verify Identity",
            description="Verify user identity",
            rule_ids=[],
            collects_profile_fields=["user_phone"],  # New field
            transitions=[
                StepTransition(
                    to_step_id=ask_id,
                    condition_text="identity verified",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=ask_id,
            scenario_id=scenario_id,
            name="Ask Question",
            description="Ask for information",
            rule_ids=[],
            collects_profile_fields=["user_email"],
            transitions=[
                StepTransition(
                    to_step_id=complete_id,
                    condition_text="email provided",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=complete_id,
            scenario_id=scenario_id,
            name="Complete",
            description="Completion step",
            rule_ids=[],
            collects_profile_fields=[],
            is_terminal=True,
            transitions=[],
        ),
    ]

    return Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Simple Flow",
        version=2,
        entry_step_id=entry_id,
        steps=steps,
    )


@pytest.fixture
def fork_scenario_v2(scenario_id: UUID, tenant_id: UUID, agent_id: UUID, simple_scenario_v1: Scenario) -> Scenario:
    """Create V2 with a fork inserted upstream.

    Flow: entry -> route_customer -> [premium_path | standard_path] -> ask_question -> complete
    """
    entry_id = simple_scenario_v1.steps[0].id
    route_id = uuid4()  # New fork node
    premium_id = uuid4()  # New branch 1
    standard_id = uuid4()  # New branch 2
    ask_id = simple_scenario_v1.steps[1].id
    complete_id = simple_scenario_v1.steps[2].id

    steps = [
        ScenarioStep(
            id=entry_id,
            scenario_id=scenario_id,
            name="Entry",
            description="Entry point",
            rule_ids=[],
            collects_profile_fields=[],
            transitions=[
                StepTransition(
                    to_step_id=route_id,
                    condition_text="always",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=route_id,
            scenario_id=scenario_id,
            name="Route Customer",
            description="Determine customer tier",
            rule_ids=[],
            collects_profile_fields=["account_tier"],
            transitions=[
                StepTransition(
                    to_step_id=premium_id,
                    condition_text="account_tier == premium",
                    condition_fields=["account_tier"],
                    priority=1,
                ),
                StepTransition(
                    to_step_id=standard_id,
                    condition_text="account_tier == standard",
                    condition_fields=["account_tier"],
                    priority=2,
                ),
            ],
        ),
        ScenarioStep(
            id=premium_id,
            scenario_id=scenario_id,
            name="Premium Path",
            description="Premium customer flow",
            rule_ids=[],
            collects_profile_fields=[],
            transitions=[
                StepTransition(
                    to_step_id=ask_id,
                    condition_text="always",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=standard_id,
            scenario_id=scenario_id,
            name="Standard Path",
            description="Standard customer flow",
            rule_ids=[],
            collects_profile_fields=[],
            transitions=[
                StepTransition(
                    to_step_id=ask_id,
                    condition_text="always",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=ask_id,
            scenario_id=scenario_id,
            name="Ask Question",
            description="Ask for information",
            rule_ids=[],
            collects_profile_fields=["user_email"],
            transitions=[
                StepTransition(
                    to_step_id=complete_id,
                    condition_text="email provided",
                    priority=1,
                )
            ],
        ),
        ScenarioStep(
            id=complete_id,
            scenario_id=scenario_id,
            name="Complete",
            description="Completion step",
            rule_ids=[],
            collects_profile_fields=[],
            is_terminal=True,
            transitions=[],
        ),
    ]

    return Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Simple Flow",
        version=2,
        entry_step_id=entry_id,
        steps=steps,
    )


# =============================================================================
# Session Fixtures
# =============================================================================


@pytest.fixture
def sample_session(tenant_id: UUID, agent_id: UUID, scenario_id: UUID) -> Session:
    """Create a sample session."""
    return Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel="api",
        user_channel_id="test_user",
        config_version=1,
        turn_count=5,
        active_scenario_id=scenario_id,
        active_scenario_version=1,
    )


@pytest.fixture
def session_with_pending_migration(
    sample_session: Session,
    sample_migration_plan: MigrationPlan,
) -> Session:
    """Create a session with pending migration."""
    sample_session.pending_migration = PendingMigration(
        migration_plan_id=sample_migration_plan.id,
        anchor_content_hash="test_anchor_hash",
        marked_at=datetime.now(UTC),
    )
    return sample_session


# =============================================================================
# Migration Plan Fixtures
# =============================================================================


@pytest.fixture
def sample_transformation_map() -> TransformationMap:
    """Create a sample transformation map with one anchor."""
    anchor_v1 = uuid4()
    anchor_v2 = uuid4()

    upstream = UpstreamChanges(
        inserted_nodes=[
            InsertedNode(
                node_id=uuid4(),
                node_name="New Upstream Step",
                collects_fields=["new_field"],
                has_rules=False,
            )
        ],
        removed_node_ids=[],
        new_forks=[],
    )

    downstream = DownstreamChanges(
        inserted_nodes=[],
        removed_node_ids=[],
        new_forks=[],
    )

    anchor = AnchorTransformation(
        anchor_content_hash="test_anchor_hash",
        anchor_name="Test Anchor",
        anchor_node_id_v1=anchor_v1,
        anchor_node_id_v2=anchor_v2,
        upstream_changes=upstream,
        downstream_changes=downstream,
        migration_scenario=MigrationScenario.GAP_FILL,
    )

    return TransformationMap(
        anchors=[anchor],
        deleted_nodes=[],
        new_node_ids=[],
    )


@pytest.fixture
def sample_migration_plan(
    tenant_id: UUID,
    scenario_id: UUID,
    sample_transformation_map: TransformationMap,
) -> MigrationPlan:
    """Create a sample migration plan."""
    plan = MigrationPlan(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        from_version=1,
        to_version=2,
        scenario_checksum_v1="v1_checksum",
        scenario_checksum_v2="v2_checksum",
        transformation_map=sample_transformation_map,
        anchor_policies={
            "test_anchor_hash": AnchorMigrationPolicy(
                anchor_content_hash="test_anchor_hash",
                anchor_name="Test Anchor",
                scope_filter=ScopeFilter(),
                update_downstream=True,
            )
        },
        summary=MigrationSummary(
            total_anchors=1,
            anchors_with_gap_fill=1,
        ),
        status=MigrationPlanStatus.APPROVED,
    )
    return plan


# =============================================================================
# Mock Store Fixtures
# =============================================================================


class MockConfigStore:
    """Mock config store for testing."""

    def __init__(self):
        self.scenarios = {}
        self.migration_plans = {}
        self.archived_scenarios = {}

    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        key = (tenant_id, scenario_id)
        return self.scenarios.get(key)

    async def save_scenario(self, scenario: Scenario) -> None:
        key = (scenario.tenant_id if hasattr(scenario, "tenant_id") else uuid4(), scenario.id)
        self.scenarios[key] = scenario

    async def get_migration_plan(self, tenant_id: UUID, plan_id: UUID) -> MigrationPlan | None:
        key = (tenant_id, plan_id)
        return self.migration_plans.get(key)

    async def get_migration_plan_for_versions(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        from_version: int,
        to_version: int,
    ) -> MigrationPlan | None:
        for plan in self.migration_plans.values():
            if (
                plan.tenant_id == tenant_id
                and plan.scenario_id == scenario_id
                and plan.from_version == from_version
                and plan.to_version == to_version
            ):
                return plan
        return None

    async def save_migration_plan(self, plan: MigrationPlan) -> None:
        key = (plan.tenant_id, plan.id)
        self.migration_plans[key] = plan

    async def archive_scenario_version(self, tenant_id: UUID, scenario: Scenario) -> None:
        key = (tenant_id, scenario.id, scenario.version)
        self.archived_scenarios[key] = scenario


class MockSessionStore:
    """Mock session store for testing."""

    def __init__(self):
        self.sessions = {}

    async def get(self, session_id: UUID) -> Session | None:
        return self.sessions.get(session_id)

    async def save(self, session: Session) -> None:
        self.sessions[session.session_id] = session


@pytest.fixture
def mock_config_store() -> MockConfigStore:
    """Create a mock config store."""
    return MockConfigStore()


@pytest.fixture
def mock_session_store() -> MockSessionStore:
    """Create a mock session store."""
    return MockSessionStore()
