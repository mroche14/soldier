"""Customer data loader for Phase 1.

Loads InterlocutorDataStore snapshot from InterlocutorDataStoreInterface.
"""

from uuid import UUID

from ruche.domain.interlocutor import (
    InterlocutorDataField,
    InterlocutorDataStore,
)
from ruche.interlocutor_data.enums import ItemStatus
from ruche.infrastructure.stores.interlocutor.interface import InterlocutorDataStore as InterlocutorDataStoreInterface
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class InterlocutorDataLoader:
    """Loads InterlocutorDataStore snapshot from InterlocutorDataStoreInterface."""

    def __init__(self, profile_store: InterlocutorDataStoreInterface):
        """Initialize loader.

        Args:
            profile_store: InterlocutorDataStoreInterface implementation
        """
        self._profile_store = profile_store

    async def load(
        self,
        interlocutor_id: UUID,
        tenant_id: UUID,
        schema: dict[str, InterlocutorDataField],
    ) -> InterlocutorDataStore:
        """Load customer data snapshot.

        Returns runtime wrapper with VariableEntry objects.

        Args:
            interlocutor_id: Customer ID
            tenant_id: Tenant ID
            schema: Field name -> InterlocutorDataField definition

        Returns:
            InterlocutorDataStore with current field values
        """
        # Get InterlocutorDataStore from InterlocutorDataStoreInterface
        profile = await self._profile_store.get_by_interlocutor_id(
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
        )

        if not profile:
            # New customer, empty store
            logger.info(
                "customer_data_new",
                interlocutor_id=str(interlocutor_id),
                tenant_id=str(tenant_id),
            )
            return InterlocutorDataStore(
                id=interlocutor_id,
                tenant_id=tenant_id,
                interlocutor_id=interlocutor_id,
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
                    interlocutor_id=str(interlocutor_id),
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
            interlocutor_id=str(interlocutor_id),
            tenant_id=str(tenant_id),
            field_count=len(active_fields),
        )

        return profile  # InterlocutorDataStore is an alias for InterlocutorDataStore
