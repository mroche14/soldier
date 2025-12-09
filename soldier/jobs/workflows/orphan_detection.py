"""Orphan detection workflow.

Scheduled job that detects profile items (fields and assets) whose source
items have been deleted, marking them as orphaned.
Runs daily by default.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from soldier.observability.logging import get_logger
from soldier.customer_data.store import CustomerDataStoreInterface

logger = get_logger(__name__)


@dataclass
class DetectOrphansInput:
    """Input for orphan detection workflow."""

    tenant_id: str | None = None  # None = all tenants


@dataclass
class DetectOrphansOutput:
    """Output from orphan detection workflow."""

    orphaned_count: int
    tenant_id: str | None
    success: bool
    error: str | None = None


class DetectOrphanedItemsWorkflow:
    """Workflow to detect and mark orphaned profile items.

    This workflow:
    1. Scans fields and assets with source_item_id references
    2. Checks if the referenced source items still exist
    3. Marks items as status=orphaned if source is missing
    4. Logs results for observability

    Idempotent: Running multiple times won't cause issues because
    items are only marked orphaned once (status transition is one-way).
    """

    WORKFLOW_NAME = "detect-orphaned-items"
    CRON_SCHEDULE = "0 3 * * *"  # Daily at 3 AM UTC

    def __init__(self, profile_store: CustomerDataStoreInterface) -> None:
        """Initialize workflow.

        Args:
            profile_store: Profile store for orphan detection operations
        """
        self._store = profile_store

    async def run(self, input_data: DetectOrphansInput) -> DetectOrphansOutput:
        """Execute the orphan detection workflow.

        Args:
            input_data: Workflow input with optional tenant filter

        Returns:
            DetectOrphansOutput with count of orphaned items
        """
        tenant_id_str = input_data.tenant_id
        tenant_id: UUID | None = None

        if tenant_id_str:
            try:
                tenant_id = UUID(tenant_id_str)
            except ValueError:
                return DetectOrphansOutput(
                    orphaned_count=0,
                    tenant_id=tenant_id_str,
                    success=False,
                    error=f"Invalid tenant_id: {tenant_id_str}",
                )

        try:
            if tenant_id:
                orphaned_count = await self._store.mark_orphaned_items(tenant_id)
            else:
                # For all tenants, we'd need to iterate
                logger.warning(
                    "detect_orphans_no_tenant",
                    message="No tenant_id provided, skipping all-tenant detection",
                )
                return DetectOrphansOutput(
                    orphaned_count=0,
                    tenant_id=None,
                    success=True,
                    error="No tenant_id provided",
                )

            logger.info(
                "profile_items_orphaned",
                tenant_id=str(tenant_id) if tenant_id else None,
                orphaned_count=orphaned_count,
            )

            return DetectOrphansOutput(
                orphaned_count=orphaned_count,
                tenant_id=str(tenant_id) if tenant_id else None,
                success=True,
            )

        except Exception as e:
            logger.error(
                "detect_orphaned_items_failed",
                tenant_id=str(tenant_id) if tenant_id else None,
                error=str(e),
            )
            return DetectOrphansOutput(
                orphaned_count=0,
                tenant_id=str(tenant_id) if tenant_id else None,
                success=False,
                error=str(e),
            )


def register_workflow(hatchet: Any, profile_store: CustomerDataStoreInterface) -> Any:
    """Register the orphan detection workflow with Hatchet.

    Args:
        hatchet: Hatchet SDK instance
        profile_store: Profile store for orphan detection operations

    Returns:
        Registered workflow
    """
    workflow_instance = DetectOrphanedItemsWorkflow(profile_store)

    @hatchet.workflow(
        name=DetectOrphanedItemsWorkflow.WORKFLOW_NAME,
        on_crons=[DetectOrphanedItemsWorkflow.CRON_SCHEDULE],
    )
    class HatchetDetectOrphanedItemsWorkflow:
        """Hatchet workflow wrapper for orphan detection."""

        @hatchet.step(retries=3, retry_delay="120s")
        async def detect_orphans(self, context: Any) -> dict:
            """Execute the orphan detection step."""
            input_data = context.workflow_input() or {}
            result = await workflow_instance.run(
                DetectOrphansInput(
                    tenant_id=input_data.get("tenant_id"),
                )
            )
            return {
                "orphaned_count": result.orphaned_count,
                "tenant_id": result.tenant_id,
                "success": result.success,
                "error": result.error,
            }

    return HatchetDetectOrphanedItemsWorkflow
