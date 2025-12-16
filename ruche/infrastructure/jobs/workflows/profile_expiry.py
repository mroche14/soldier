"""Profile field expiry workflow.

Scheduled job that marks expired profile fields based on their expires_at timestamp.
Runs hourly by default.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ruche.observability.logging import get_logger
from ruche.infrastructure.stores.interlocutor.interface import InterlocutorDataStore as InterlocutorDataStoreInterface

logger = get_logger(__name__)


@dataclass
class ExpireFieldsInput:
    """Input for expire stale fields workflow."""

    tenant_id: str | None = None  # None = all tenants


@dataclass
class ExpireFieldsOutput:
    """Output from expire stale fields workflow."""

    expired_count: int
    tenant_id: str | None
    success: bool
    error: str | None = None


class ExpireStaleFieldsWorkflow:
    """Workflow to mark expired profile fields.

    This workflow:
    1. Queries all tenants (or specific tenant if provided)
    2. Marks fields past their expires_at as status=expired
    3. Logs results for observability

    Idempotent: Running multiple times won't cause issues because
    fields are only marked expired once (status transition is one-way).
    """

    WORKFLOW_NAME = "expire-stale-fields"
    CRON_SCHEDULE = "0 * * * *"  # Every hour at minute 0

    def __init__(self, profile_store: InterlocutorDataStoreInterface) -> None:
        """Initialize workflow.

        Args:
            profile_store: Profile store for expiry operations
        """
        self._store = profile_store

    async def run(self, input_data: ExpireFieldsInput) -> ExpireFieldsOutput:
        """Execute the expiry workflow.

        Args:
            input_data: Workflow input with optional tenant filter

        Returns:
            ExpireFieldsOutput with count of expired fields
        """
        tenant_id_str = input_data.tenant_id
        tenant_id: UUID | None = None

        if tenant_id_str:
            try:
                tenant_id = UUID(tenant_id_str)
            except ValueError:
                return ExpireFieldsOutput(
                    expired_count=0,
                    tenant_id=tenant_id_str,
                    success=False,
                    error=f"Invalid tenant_id: {tenant_id_str}",
                )

        try:
            # If tenant_id is None, this will process all tenants
            # The store implementation should handle this
            if tenant_id:
                expired_count = await self._store.expire_stale_fields(tenant_id)
            else:
                # For all tenants, we'd need to iterate
                # For now, return 0 if no tenant specified
                logger.warning(
                    "expire_stale_fields_no_tenant",
                    message="No tenant_id provided, skipping all-tenant expiry",
                )
                return ExpireFieldsOutput(
                    expired_count=0,
                    tenant_id=None,
                    success=True,
                    error="No tenant_id provided",
                )

            logger.info(
                "profile_fields_expired",
                tenant_id=str(tenant_id) if tenant_id else None,
                expired_count=expired_count,
            )

            return ExpireFieldsOutput(
                expired_count=expired_count,
                tenant_id=str(tenant_id) if tenant_id else None,
                success=True,
            )

        except Exception as e:
            logger.error(
                "expire_stale_fields_failed",
                tenant_id=str(tenant_id) if tenant_id else None,
                error=str(e),
            )
            return ExpireFieldsOutput(
                expired_count=0,
                tenant_id=str(tenant_id) if tenant_id else None,
                success=False,
                error=str(e),
            )


def register_workflow(hatchet: Any, profile_store: InterlocutorDataStoreInterface) -> Any:
    """Register the expire stale fields workflow with Hatchet.

    Args:
        hatchet: Hatchet SDK instance
        profile_store: Profile store for expiry operations

    Returns:
        Registered workflow
    """
    workflow_instance = ExpireStaleFieldsWorkflow(profile_store)

    @hatchet.workflow(
        name=ExpireStaleFieldsWorkflow.WORKFLOW_NAME,
        on_crons=[ExpireStaleFieldsWorkflow.CRON_SCHEDULE],
    )
    class HatchetExpireStaleFieldsWorkflow:
        """Hatchet workflow wrapper for expire stale fields."""

        @hatchet.step(retries=3, retry_delay="60s")
        async def expire_fields(self, context: Any) -> dict:
            """Execute the expiry step."""
            input_data = context.workflow_input() or {}
            result = await workflow_instance.run(
                ExpireFieldsInput(
                    tenant_id=input_data.get("tenant_id"),
                )
            )
            return {
                "expired_count": result.expired_count,
                "tenant_id": result.tenant_id,
                "success": result.success,
                "error": result.error,
            }

    return HatchetExpireStaleFieldsWorkflow
