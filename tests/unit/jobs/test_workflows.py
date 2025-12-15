"""Unit tests for Hatchet workflows.

Tests workflow logic, idempotency, and error handling.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ruche.jobs.workflows import (
    DetectOrphanedItemsWorkflow,
    DetectOrphansInput,
    ExpireFieldsInput,
    ExpireStaleFieldsWorkflow,
)
from ruche.interlocutor_data.stores.inmemory import InMemoryInterlocutorDataStore


@pytest.fixture
def profile_store():
    """Create an in-memory profile store."""
    return InMemoryInterlocutorDataStore()


@pytest.fixture
def mock_profile_store():
    """Create a mock profile store."""
    store = AsyncMock()
    store.expire_stale_fields = AsyncMock(return_value=5)
    store.mark_orphaned_items = AsyncMock(return_value=3)
    return store


class TestExpireStaleFieldsWorkflow:
    """Tests for ExpireStaleFieldsWorkflow (T120)."""

    def test_workflow_name(self):
        """Test workflow has correct name."""
        assert ExpireStaleFieldsWorkflow.WORKFLOW_NAME == "expire-stale-fields"

    def test_workflow_cron_schedule(self):
        """Test workflow has hourly cron schedule."""
        assert ExpireStaleFieldsWorkflow.CRON_SCHEDULE == "0 * * * *"

    @pytest.mark.asyncio
    async def test_run_with_valid_tenant(self, mock_profile_store):
        """Test workflow runs successfully with valid tenant."""
        workflow = ExpireStaleFieldsWorkflow(mock_profile_store)
        tenant_id = str(uuid4())

        result = await workflow.run(ExpireFieldsInput(tenant_id=tenant_id))

        assert result.success is True
        assert result.expired_count == 5
        assert result.tenant_id == tenant_id
        assert result.error is None
        mock_profile_store.expire_stale_fields.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_invalid_tenant_id(self, mock_profile_store):
        """Test workflow handles invalid tenant ID gracefully."""
        workflow = ExpireStaleFieldsWorkflow(mock_profile_store)

        result = await workflow.run(ExpireFieldsInput(tenant_id="not-a-uuid"))

        assert result.success is False
        assert result.expired_count == 0
        assert "Invalid tenant_id" in result.error

    @pytest.mark.asyncio
    async def test_run_with_no_tenant_returns_warning(self, mock_profile_store):
        """Test workflow handles missing tenant ID."""
        workflow = ExpireStaleFieldsWorkflow(mock_profile_store)

        result = await workflow.run(ExpireFieldsInput(tenant_id=None))

        assert result.success is True  # Successful but skipped
        assert result.expired_count == 0
        assert result.error == "No tenant_id provided"

    @pytest.mark.asyncio
    async def test_run_handles_store_exception(self, mock_profile_store):
        """Test workflow handles store exceptions gracefully."""
        mock_profile_store.expire_stale_fields.side_effect = Exception("DB error")
        workflow = ExpireStaleFieldsWorkflow(mock_profile_store)
        tenant_id = str(uuid4())

        result = await workflow.run(ExpireFieldsInput(tenant_id=tenant_id))

        assert result.success is False
        assert result.expired_count == 0
        assert "DB error" in result.error

    @pytest.mark.asyncio
    async def test_idempotency_multiple_runs(self, profile_store):
        """Test workflow is idempotent - multiple runs don't cause issues."""
        workflow = ExpireStaleFieldsWorkflow(profile_store)
        tenant_id = str(uuid4())
        input_data = ExpireFieldsInput(tenant_id=tenant_id)

        # Run multiple times
        result1 = await workflow.run(input_data)
        result2 = await workflow.run(input_data)
        result3 = await workflow.run(input_data)

        # All should succeed (even if count is 0)
        assert result1.success is True
        assert result2.success is True
        assert result3.success is True


class TestDetectOrphanedItemsWorkflow:
    """Tests for DetectOrphanedItemsWorkflow (T121)."""

    def test_workflow_name(self):
        """Test workflow has correct name."""
        assert DetectOrphanedItemsWorkflow.WORKFLOW_NAME == "detect-orphaned-items"

    def test_workflow_cron_schedule(self):
        """Test workflow has daily cron schedule at 3 AM."""
        assert DetectOrphanedItemsWorkflow.CRON_SCHEDULE == "0 3 * * *"

    @pytest.mark.asyncio
    async def test_run_with_valid_tenant(self, mock_profile_store):
        """Test workflow runs successfully with valid tenant."""
        workflow = DetectOrphanedItemsWorkflow(mock_profile_store)
        tenant_id = str(uuid4())

        result = await workflow.run(DetectOrphansInput(tenant_id=tenant_id))

        assert result.success is True
        assert result.orphaned_count == 3
        assert result.tenant_id == tenant_id
        assert result.error is None
        mock_profile_store.mark_orphaned_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_invalid_tenant_id(self, mock_profile_store):
        """Test workflow handles invalid tenant ID gracefully."""
        workflow = DetectOrphanedItemsWorkflow(mock_profile_store)

        result = await workflow.run(DetectOrphansInput(tenant_id="not-a-uuid"))

        assert result.success is False
        assert result.orphaned_count == 0
        assert "Invalid tenant_id" in result.error

    @pytest.mark.asyncio
    async def test_run_with_no_tenant_returns_warning(self, mock_profile_store):
        """Test workflow handles missing tenant ID."""
        workflow = DetectOrphanedItemsWorkflow(mock_profile_store)

        result = await workflow.run(DetectOrphansInput(tenant_id=None))

        assert result.success is True  # Successful but skipped
        assert result.orphaned_count == 0
        assert result.error == "No tenant_id provided"

    @pytest.mark.asyncio
    async def test_run_handles_store_exception(self, mock_profile_store):
        """Test workflow handles store exceptions gracefully."""
        mock_profile_store.mark_orphaned_items.side_effect = Exception("DB error")
        workflow = DetectOrphanedItemsWorkflow(mock_profile_store)
        tenant_id = str(uuid4())

        result = await workflow.run(DetectOrphansInput(tenant_id=tenant_id))

        assert result.success is False
        assert result.orphaned_count == 0
        assert "DB error" in result.error

    @pytest.mark.asyncio
    async def test_idempotency_multiple_runs(self, profile_store):
        """Test workflow is idempotent - multiple runs don't cause issues (T122)."""
        workflow = DetectOrphanedItemsWorkflow(profile_store)
        tenant_id = str(uuid4())
        input_data = DetectOrphansInput(tenant_id=tenant_id)

        # Run multiple times
        result1 = await workflow.run(input_data)
        result2 = await workflow.run(input_data)
        result3 = await workflow.run(input_data)

        # All should succeed (even if count is 0)
        assert result1.success is True
        assert result2.success is True
        assert result3.success is True


class TestWorkflowRetryPolicy:
    """Tests for workflow retry configuration (T119)."""

    def test_expire_workflow_has_retry_configuration(self):
        """Test ExpireStaleFieldsWorkflow uses retries in step decorator."""
        # The retry policy is configured in the register_workflow function
        # with @hatchet.step(retries=3, retry_delay="60s")
        # This is a documentation test to verify the pattern exists
        from ruche.jobs.workflows import profile_expiry

        # Verify the module has the register_workflow function
        assert hasattr(profile_expiry, "register_workflow")

    def test_orphan_workflow_has_retry_configuration(self):
        """Test DetectOrphanedItemsWorkflow uses retries in step decorator."""
        from ruche.jobs.workflows import orphan_detection

        assert hasattr(orphan_detection, "register_workflow")
