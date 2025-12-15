"""InterlocutorDataStore abstract interface.

Enhanced to support:
- Status-aware queries
- Lineage traversal
- Schema management
- Field history
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from ruche.conversation.models import Channel
from ruche.interlocutor_data.enums import ItemStatus
from ruche.interlocutor_data.models import (
    ChannelIdentity,
    InterlocutorDataStore,
    ProfileAsset,
    VariableEntry,
    InterlocutorDataField,
    ScenarioFieldRequirement,
)


class InterlocutorDataStore(ABC):
    """Abstract interface for customer data storage.

    Enhanced to support:
    - Status-aware queries
    - Lineage traversal
    - Schema management
    - Field history
    """

    # =========================================================================
    # PROFILE CRUD (Original + Enhanced)
    # =========================================================================

    @abstractmethod
    async def get_by_interlocutor_id(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by customer ID.

        Args:
            tenant_id: Tenant identifier
            interlocutor_id: Customer identifier
            include_history: If True, populate field_history and asset_history

        Returns:
            InterlocutorDataStore with active fields/assets, or None if not found
        """
        pass

    @abstractmethod
    async def get_by_id(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by profile ID."""
        pass

    @abstractmethod
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by channel identity."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> InterlocutorDataStore:
        """Get existing profile or create new one for channel identity."""
        pass

    @abstractmethod
    async def save(self, profile: InterlocutorDataStore) -> UUID:
        """Save a profile (create or update)."""
        pass

    @abstractmethod
    async def delete(self, tenant_id: UUID, profile_id: UUID) -> bool:
        """Soft-delete a profile."""
        pass

    # =========================================================================
    # FIELD OPERATIONS (Enhanced with Status)
    # =========================================================================

    @abstractmethod
    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: VariableEntry,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update a profile field.

        If supersede_existing is True and a field with the same name exists:
        - Existing field is marked status=superseded
        - New field is linked via superseded_by_id
        - New field gets status=active

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to update
            field: New field value
            supersede_existing: Whether to supersede existing field

        Returns:
            ID of the new field
        """
        pass

    @abstractmethod
    async def get_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> VariableEntry | None:
        """Get a specific field by name.

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to query
            field_name: Field name to retrieve
            status: Filter by status (None = any status, returns most recent)

        Returns:
            ProfileField or None
        """
        pass

    @abstractmethod
    async def get_field_history(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
    ) -> list[VariableEntry]:
        """Get all versions of a field (all statuses).

        Returns:
            List of ProfileField ordered by collected_at DESC
        """
        pass

    @abstractmethod
    async def expire_stale_fields(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark fields past expires_at as status=expired.

        Args:
            tenant_id: Tenant to process
            profile_id: Specific profile (None = all profiles in tenant)

        Returns:
            Number of fields marked as expired
        """
        pass

    @abstractmethod
    async def mark_orphaned_items(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark items whose source was deleted as orphaned.

        Scans fields and assets for source_item_id references that no longer exist.

        Args:
            tenant_id: Tenant to process
            profile_id: Specific profile (None = all profiles in tenant)

        Returns:
            Number of items marked as orphaned
        """
        pass

    # =========================================================================
    # ASSET OPERATIONS (Enhanced with Status)
    # =========================================================================

    @abstractmethod
    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
        *,
        supersede_existing: bool = False,
    ) -> UUID:
        """Add an asset to profile.

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to update
            asset: Asset to add
            supersede_existing: If True, supersede existing asset with same name

        Returns:
            ID of the new asset
        """
        pass

    @abstractmethod
    async def get_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_id: UUID,
    ) -> ProfileAsset | None:
        """Get a specific asset by ID."""
        pass

    @abstractmethod
    async def get_asset_by_name(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileAsset | None:
        """Get asset by name with optional status filter."""
        pass

    # =========================================================================
    # LINEAGE OPERATIONS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_derivation_chain(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> list[dict[str, Any]]:
        """Get full derivation chain for an item.

        Traverses source_item_id links back to root source.

        Args:
            tenant_id: Tenant identifier
            item_id: Starting item ID
            item_type: Type of item ("profile_field" or "profile_asset")

        Returns:
            List of items in chain, from root to item.
            Each dict has: {id, type, name, source_metadata}
        """
        pass

    @abstractmethod
    async def get_derived_items(
        self,
        tenant_id: UUID,
        source_item_id: UUID,
    ) -> dict[str, list[Any]]:
        """Get all items derived from a source.

        Args:
            tenant_id: Tenant identifier
            source_item_id: Source item ID

        Returns:
            Dict with "fields" and "assets" lists
        """
        pass

    @abstractmethod
    async def check_has_dependents(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Check if an item has dependent derived items.

        Used to prevent hard-delete of items with dependents.
        """
        pass

    # =========================================================================
    # CHANNEL OPERATIONS (Original)
    # =========================================================================

    @abstractmethod
    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        identity: ChannelIdentity,
    ) -> bool:
        """Link a new channel identity to profile."""
        pass

    @abstractmethod
    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_profile_id: UUID,
        target_profile_id: UUID,
    ) -> bool:
        """Merge source profile into target profile.

        - All channel identities moved to target
        - All fields/assets moved to target
        - Source profile is soft-deleted
        - Maintains lineage references
        """
        pass

    # =========================================================================
    # SCHEMA OPERATIONS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_field_definitions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[InterlocutorDataField]:
        """Get all field definitions for an agent."""
        pass

    @abstractmethod
    async def get_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> InterlocutorDataField | None:
        """Get a specific field definition by name."""
        pass

    @abstractmethod
    async def save_field_definition(
        self,
        definition: InterlocutorDataField,
    ) -> UUID:
        """Save a field definition."""
        pass

    @abstractmethod
    async def delete_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> bool:
        """Delete a field definition."""
        pass

    # =========================================================================
    # SCENARIO REQUIREMENTS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Get field requirements for a scenario/step.

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario to query
            step_id: Optional step filter (None = scenario-wide only)

        Returns:
            List of requirements ordered by collection_order
        """
        pass

    @abstractmethod
    async def save_scenario_requirement(
        self,
        requirement: ScenarioFieldRequirement,
    ) -> UUID:
        """Save a scenario field requirement."""
        pass

    @abstractmethod
    async def delete_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> int:
        """Delete requirements for a scenario/step.

        Returns:
            Number of requirements deleted
        """
        pass

    @abstractmethod
    async def get_missing_fields(
        self,
        tenant_id: UUID,
        profile: InterlocutorDataStore,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> list[ScenarioFieldRequirement]:
        """Get requirements not satisfied by the profile.

        Checks:
        - Field exists with status=active
        - Field meets freshness requirements
        - Field verified if required

        Args:
            tenant_id: Tenant identifier
            profile: Customer profile to check
            scenario_id: Scenario to check against
            step_id: Optional step filter
            required_level: Filter by level ("hard", "soft", or None for all)

        Returns:
            List of unmet requirements
        """
        pass
