"""Customer data loader for Phase 1.

Loads CustomerDataStore snapshot from CustomerDataStoreInterface.
"""

from uuid import UUID

from focal.customer_data import (
    CustomerDataField,
    CustomerDataStore,
)
from focal.customer_data.enums import ItemStatus
from focal.customer_data.store import CustomerDataStoreInterface
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class CustomerDataLoader:
    """Loads CustomerDataStore snapshot from CustomerDataStoreInterface."""

    def __init__(self, profile_store: CustomerDataStoreInterface):
        """Initialize loader.

        Args:
            profile_store: CustomerDataStoreInterface implementation
        """
        self._profile_store = profile_store

    async def load(
        self,
        customer_id: UUID,
        tenant_id: UUID,
        schema: dict[str, CustomerDataField],
    ) -> CustomerDataStore:
        """Load customer data snapshot.

        Returns runtime wrapper with VariableEntry objects.

        Args:
            customer_id: Customer ID
            tenant_id: Tenant ID
            schema: Field name -> CustomerDataField definition

        Returns:
            CustomerDataStore with current field values
        """
        # Get CustomerDataStore from CustomerDataStoreInterface
        profile = await self._profile_store.get_by_customer_id(
            tenant_id=tenant_id,
            customer_id=customer_id,
        )

        if not profile:
            # New customer, empty store
            logger.info(
                "customer_data_new",
                customer_id=str(customer_id),
                tenant_id=str(tenant_id),
            )
            return CustomerDataStore(
                id=customer_id,
                tenant_id=tenant_id,
                customer_id=customer_id,
                channel_identities=[],
                fields={},
                assets=[],
            )

        # Filter only active fields
        active_fields = {}
        for field_name, field in profile.fields.items():
            if field.status != ItemStatus.ACTIVE:
                continue  # Skip superseded/expired/orphaned

            # Warn if field not in schema (schema drift)
            field_def = schema.get(field_name)
            if not field_def:
                logger.warning(
                    "field_not_in_schema",
                    field_name=field_name,
                    customer_id=str(customer_id),
                    tenant_id=str(tenant_id),
                )
                # Still include the field but without schema validation
                active_fields[field_name] = field
                continue

            # Field is valid, include it
            active_fields[field_name] = field

        # Update the profile's fields dict to only active fields
        profile.fields = active_fields

        logger.info(
            "customer_data_loaded",
            customer_id=str(customer_id),
            tenant_id=str(tenant_id),
            field_count=len(active_fields),
        )

        return profile  # CustomerDataStore is an alias for CustomerDataStore
