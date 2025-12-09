"""Contract tests for ConfigStore migration plan methods.

These tests define the contract that ALL ConfigStore implementations must satisfy.
Each implementation (InMemory, PostgreSQL, etc.) should pass these tests.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from focal.alignment.migration.models import (
    MigrationPlan,
    MigrationPlanStatus,
    MigrationSummary,
    TransformationMap,
)
from focal.alignment.stores.inmemory import InMemoryAgentConfigStore


class ConfigStoreMigrationContract(ABC):
    """Contract tests for migration plan methods.

    All ConfigStore implementations must pass these tests.
    """

    @abstractmethod
    @pytest.fixture
    def store(self):
        """Return a ConfigStore implementation to test."""
        pass

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def scenario_id(self):
        return uuid4()

    @pytest.fixture
    def sample_plan(self, tenant_id, scenario_id):
        """Create a sample migration plan."""
        return MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="checksum_v1",
            scenario_checksum_v2="checksum_v2",
            status=MigrationPlanStatus.PENDING,
            transformation_map=TransformationMap(
                anchors=[],
                deleted_nodes=[],
            ),
            summary=MigrationSummary(
                anchor_count=0,
                estimated_sessions_affected=0,
            ),
        )

    # =========================================================================
    # Save and Get Migration Plan
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_and_get_migration_plan(self, store, sample_plan):
        """Test saving and retrieving a migration plan."""
        await store.save_migration_plan(sample_plan)

        retrieved = await store.get_migration_plan(
            sample_plan.tenant_id,
            sample_plan.id,
        )

        assert retrieved is not None
        assert retrieved.id == sample_plan.id
        assert retrieved.tenant_id == sample_plan.tenant_id
        assert retrieved.from_version == sample_plan.from_version
        assert retrieved.to_version == sample_plan.to_version

    @pytest.mark.asyncio
    async def test_get_migration_plan_not_found(self, store, tenant_id):
        """Test getting a non-existent plan."""
        result = await store.get_migration_plan(tenant_id, uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_migration_plan_wrong_tenant(self, store, sample_plan):
        """Test tenant isolation - cannot get plan from different tenant."""
        await store.save_migration_plan(sample_plan)

        other_tenant = uuid4()
        result = await store.get_migration_plan(other_tenant, sample_plan.id)
        assert result is None

    # =========================================================================
    # Get Migration Plan for Versions
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_migration_plan_for_versions(
        self, store, sample_plan, tenant_id, scenario_id
    ):
        """Test retrieving plan by version transition."""
        await store.save_migration_plan(sample_plan)

        retrieved = await store.get_migration_plan_for_versions(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
        )

        assert retrieved is not None
        assert retrieved.id == sample_plan.id

    @pytest.mark.asyncio
    async def test_get_migration_plan_for_versions_not_found(
        self, store, tenant_id, scenario_id
    ):
        """Test getting plan for non-existent version transition."""
        result = await store.get_migration_plan_for_versions(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=99,
            to_version=100,
        )
        assert result is None

    # =========================================================================
    # List Migration Plans
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_migration_plans_empty(self, store, tenant_id):
        """Test listing plans when none exist."""
        plans = await store.list_migration_plans(tenant_id)
        assert len(plans) == 0

    @pytest.mark.asyncio
    async def test_list_migration_plans(self, store, tenant_id, scenario_id):
        """Test listing multiple plans."""
        # Create plans for different version transitions
        plan1 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="c1",
            scenario_checksum_v2="c2",
            status=MigrationPlanStatus.DEPLOYED,
            transformation_map=TransformationMap(anchors=[], deleted_nodes=[]),
        )
        plan2 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=2,
            to_version=3,
            scenario_checksum_v1="c2",
            scenario_checksum_v2="c3",
            status=MigrationPlanStatus.PENDING,
            transformation_map=TransformationMap(anchors=[], deleted_nodes=[]),
        )

        await store.save_migration_plan(plan1)
        await store.save_migration_plan(plan2)

        plans = await store.list_migration_plans(tenant_id)
        assert len(plans) == 2

    @pytest.mark.asyncio
    async def test_list_migration_plans_by_scenario(
        self, store, tenant_id, scenario_id
    ):
        """Test filtering plans by scenario."""
        other_scenario = uuid4()

        plan1 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="c1",
            scenario_checksum_v2="c2",
            status=MigrationPlanStatus.DEPLOYED,
            transformation_map=TransformationMap(anchors=[], deleted_nodes=[]),
        )
        plan2 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=other_scenario,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="c1",
            scenario_checksum_v2="c2",
            status=MigrationPlanStatus.DEPLOYED,
            transformation_map=TransformationMap(anchors=[], deleted_nodes=[]),
        )

        await store.save_migration_plan(plan1)
        await store.save_migration_plan(plan2)

        plans = await store.list_migration_plans(tenant_id, scenario_id=scenario_id)
        assert len(plans) == 1
        assert plans[0].scenario_id == scenario_id

    # =========================================================================
    # Delete Migration Plan
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_migration_plan(self, store, sample_plan):
        """Test deleting a migration plan."""
        await store.save_migration_plan(sample_plan)

        # Verify it exists
        assert await store.get_migration_plan(
            sample_plan.tenant_id, sample_plan.id
        ) is not None

        # Delete
        await store.delete_migration_plan(sample_plan.tenant_id, sample_plan.id)

        # Verify deleted
        assert await store.get_migration_plan(
            sample_plan.tenant_id, sample_plan.id
        ) is None

    # =========================================================================
    # Update Migration Plan Status
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_migration_plan_status(self, store, sample_plan):
        """Test updating plan status persists correctly."""
        await store.save_migration_plan(sample_plan)

        # Update status
        sample_plan.status = MigrationPlanStatus.APPROVED
        sample_plan.approved_at = datetime.now(UTC)
        await store.save_migration_plan(sample_plan)

        # Retrieve and verify
        retrieved = await store.get_migration_plan(
            sample_plan.tenant_id, sample_plan.id
        )
        assert retrieved.status == MigrationPlanStatus.APPROVED
        assert retrieved.approved_at is not None


class TestInMemoryAgentConfigStoreMigration(ConfigStoreMigrationContract):
    """Test InMemoryAgentConfigStore against the migration contract."""

    @pytest.fixture
    def store(self):
        return InMemoryAgentConfigStore()
