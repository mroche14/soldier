"""In-memory implementation of InterlocutorDataStore."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from focal.conversation.models import Channel
from focal.observability.logging import get_logger
from focal.customer_data.enums import ItemStatus, RequiredLevel
from focal.customer_data.models import (
    ChannelIdentity,
    CustomerDataStore,
    ProfileAsset,
    VariableEntry,
    CustomerDataField,
    ScenarioFieldRequirement,
)
from focal.customer_data.store import InterlocutorDataStore

logger = get_logger(__name__)


class InMemoryCustomerDataStore(InterlocutorDataStore):
    """In-memory implementation of InterlocutorDataStore for testing and development.

    Enhanced to support:
    - Status-aware queries
    - Lineage traversal
    - Schema management
    - Field history
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._profiles: dict[UUID, CustomerDataStore] = {}
        # Field history storage: {profile_id: {field_name: [VariableEntry, ...]}}
        self._field_history: dict[UUID, dict[str, list[VariableEntry]]] = {}
        # Asset history storage: {profile_id: {asset_name: [ProfileAsset, ...]}}
        self._asset_history: dict[UUID, dict[str, list[ProfileAsset]]] = {}
        # Schema storage
        self._field_definitions: dict[tuple[UUID, UUID, str], CustomerDataField] = {}
        self._scenario_requirements: dict[UUID, ScenarioFieldRequirement] = {}

    # =========================================================================
    # PROFILE CRUD
    # =========================================================================

    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by customer ID."""
        for profile in self._profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.customer_id == customer_id
            ):
                return profile
        return None

    async def get_by_id(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by profile ID."""
        profile = self._profiles.get(profile_id)
        if profile and profile.tenant_id == tenant_id:
            return profile
        return None

    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by channel identity."""
        for profile in self._profiles.values():
            if profile.tenant_id != tenant_id:
                continue
            for identity in profile.channel_identities:
                if (
                    identity.channel == channel
                    and identity.channel_user_id == channel_user_id
                ):
                    return profile
        return None

    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerDataStore:
        """Get existing profile or create new one for channel identity."""
        existing = await self.get_by_channel_identity(
            tenant_id, channel, channel_user_id
        )
        if existing:
            return existing

        # Create new profile with channel identity
        identity = ChannelIdentity(
            channel=channel,
            channel_user_id=channel_user_id,
            primary=True,
        )
        profile = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[identity],
        )
        await self.save(profile)
        return profile

    async def save(self, profile: CustomerDataStore) -> UUID:
        """Save a profile."""
        profile.updated_at = datetime.now(UTC)
        self._profiles[profile.id] = profile
        return profile.id

    async def delete(self, tenant_id: UUID, profile_id: UUID) -> bool:
        """Soft-delete a profile (actually removes from memory in this impl)."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return False
        del self._profiles[profile_id]
        # Clean up history
        self._field_history.pop(profile_id, None)
        self._asset_history.pop(profile_id, None)
        return True

    # =========================================================================
    # FIELD OPERATIONS
    # =========================================================================

    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: VariableEntry,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update a profile field with supersession support."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Initialize history storage
        if profile_id not in self._field_history:
            self._field_history[profile_id] = {}
        if field.name not in self._field_history[profile_id]:
            self._field_history[profile_id][field.name] = []

        # Handle supersession
        if supersede_existing and field.name in profile.fields:
            existing = profile.fields[field.name]
            if existing.status == ItemStatus.ACTIVE:
                existing.status = ItemStatus.SUPERSEDED
                existing.superseded_by_id = field.id
                existing.superseded_at = datetime.now(UTC)
                # Add to history
                self._field_history[profile_id][field.name].append(existing)
                # T167: Log supersession event
                logger.info(
                    "profile_field_superseded",
                    tenant_id=str(tenant_id),
                    profile_id=str(profile_id),
                    field_name=field.name,
                    old_field_id=str(existing.id),
                    new_field_id=str(field.id),
                )

        # Set new field as active
        field.status = ItemStatus.ACTIVE
        field.updated_at = datetime.now(UTC)
        profile.fields[field.name] = field
        profile.updated_at = datetime.now(UTC)

        return field.id

    async def get_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> VariableEntry | None:
        """Get a specific field by name."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return None

        # Check current fields first
        if field_name in profile.fields:
            field = profile.fields[field_name]
            if status is None or field.status == status:
                return field

        # Check history if looking for non-active
        if status != ItemStatus.ACTIVE:
            history = self._field_history.get(profile_id, {}).get(field_name, [])
            for field in sorted(history, key=lambda f: f.collected_at, reverse=True):
                if status is None or field.status == status:
                    return field

        return None

    async def get_field_history(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
    ) -> list[VariableEntry]:
        """Get all versions of a field."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return []

        result = []

        # Add current field
        if field_name in profile.fields:
            result.append(profile.fields[field_name])

        # Add historical fields
        history = self._field_history.get(profile_id, {}).get(field_name, [])
        result.extend(history)

        # Sort by collected_at DESC
        return sorted(result, key=lambda f: f.collected_at, reverse=True)

    async def expire_stale_fields(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark fields past expires_at as status=expired."""
        count = 0
        now = datetime.now(UTC)

        profiles_to_check = (
            [self._profiles[profile_id]]
            if profile_id and profile_id in self._profiles
            else [p for p in self._profiles.values() if p.tenant_id == tenant_id]
        )

        for profile in profiles_to_check:
            for field in profile.fields.values():
                if (
                    field.status == ItemStatus.ACTIVE
                    and field.expires_at is not None
                    and field.expires_at < now
                ):
                    field.status = ItemStatus.EXPIRED
                    count += 1
                    # T168: Log expiration event
                    logger.info(
                        "profile_field_expired",
                        tenant_id=str(tenant_id),
                        profile_id=str(profile.id),
                        field_name=field.name,
                        field_id=str(field.id),
                        expires_at=field.expires_at.isoformat(),
                    )

        return count

    async def mark_orphaned_items(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark items whose source was deleted as orphaned."""
        count = 0

        profiles_to_check = (
            [self._profiles[profile_id]]
            if profile_id and profile_id in self._profiles
            else [p for p in self._profiles.values() if p.tenant_id == tenant_id]
        )

        for profile in profiles_to_check:
            # Check fields
            for field in profile.fields.values():
                if (
                    field.status == ItemStatus.ACTIVE
                    and field.source_item_id is not None
                ):
                    # Check if source exists
                    source_exists = await self._find_item(
                        tenant_id,
                        field.source_item_id,
                        field.source_item_type.value if field.source_item_type else None,
                    )
                    if source_exists is None:
                        field.status = ItemStatus.ORPHANED
                        count += 1
                        # T169: Log orphan event
                        logger.info(
                            "profile_field_orphaned",
                            tenant_id=str(tenant_id),
                            profile_id=str(profile.id),
                            field_name=field.name,
                            field_id=str(field.id),
                            source_item_id=str(field.source_item_id),
                            source_item_type=field.source_item_type.value if field.source_item_type else None,
                        )

            # Check assets
            for asset in profile.assets:
                if (
                    asset.status == ItemStatus.ACTIVE
                    and asset.source_item_id is not None
                ):
                    source_exists = await self._find_item(
                        tenant_id,
                        asset.source_item_id,
                        asset.source_item_type.value if asset.source_item_type else None,
                    )
                    if source_exists is None:
                        asset.status = ItemStatus.ORPHANED
                        count += 1
                        # T169: Log orphan event for asset
                        logger.info(
                            "profile_field_orphaned",
                            tenant_id=str(tenant_id),
                            profile_id=str(profile.id),
                            asset_name=asset.name,
                            asset_id=str(asset.id),
                            source_item_id=str(asset.source_item_id),
                            source_item_type=asset.source_item_type.value if asset.source_item_type else None,
                        )

        return count

    # =========================================================================
    # ASSET OPERATIONS
    # =========================================================================

    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
        *,
        supersede_existing: bool = False,
    ) -> UUID:
        """Add an asset to profile."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Initialize history storage
        if profile_id not in self._asset_history:
            self._asset_history[profile_id] = {}
        if asset.name not in self._asset_history[profile_id]:
            self._asset_history[profile_id][asset.name] = []

        # Handle supersession
        if supersede_existing:
            for existing in profile.assets:
                if existing.name == asset.name and existing.status == ItemStatus.ACTIVE:
                    existing.status = ItemStatus.SUPERSEDED
                    existing.superseded_by_id = asset.id
                    existing.superseded_at = datetime.now(UTC)
                    self._asset_history[profile_id][asset.name].append(existing)

        asset.status = ItemStatus.ACTIVE
        profile.assets.append(asset)
        profile.updated_at = datetime.now(UTC)

        return asset.id

    async def get_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_id: UUID,
    ) -> ProfileAsset | None:
        """Get a specific asset by ID."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return None

        for asset in profile.assets:
            if asset.id == asset_id:
                return asset
        return None

    async def get_asset_by_name(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileAsset | None:
        """Get asset by name with optional status filter."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return None

        for asset in profile.assets:
            if asset.name == asset_name:
                if status is None or asset.status == status:
                    return asset
        return None

    # =========================================================================
    # LINEAGE OPERATIONS
    # =========================================================================

    async def get_derivation_chain(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> list[dict[str, Any]]:
        """Get full derivation chain for an item."""
        chain: list[dict[str, Any]] = []
        visited: set[UUID] = set()
        current_id: UUID | None = item_id
        current_type = item_type
        max_depth = 10

        while current_id and len(chain) < max_depth:
            if current_id in visited:
                break  # Cycle detected
            visited.add(current_id)

            item = await self._find_item(tenant_id, current_id, current_type)
            if not item:
                break

            if current_type == "profile_field":
                chain.insert(0, {
                    "id": str(item.id),
                    "type": "profile_field",
                    "name": item.name,
                    "source_metadata": item.source_metadata,
                })
                current_id = item.source_item_id
                current_type = item.source_item_type.value if item.source_item_type else None
            else:  # profile_asset
                chain.insert(0, {
                    "id": str(item.id),
                    "type": "profile_asset",
                    "name": item.name,
                    "source_metadata": {},
                })
                current_id = item.source_item_id
                current_type = item.source_item_type.value if item.source_item_type else None

            if not current_type:
                break

        # T170: Log derivation chain traversal
        if chain:
            logger.info(
                "derivation_chain_traversed",
                tenant_id=str(tenant_id),
                item_id=str(item_id),
                item_type=item_type,
                chain_depth=len(chain),
            )

        return chain

    async def _find_item(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str | None,
    ) -> VariableEntry | ProfileAsset | None:
        """Find a field or asset by ID across all profiles."""
        for profile in self._profiles.values():
            if profile.tenant_id != tenant_id:
                continue

            if item_type == "profile_field":
                for field in profile.fields.values():
                    if field.id == item_id:
                        return field
                # Check history
                for history in self._field_history.get(profile.id, {}).values():
                    for field in history:
                        if field.id == item_id:
                            return field
            elif item_type == "profile_asset":
                for asset in profile.assets:
                    if asset.id == item_id:
                        return asset

        return None

    async def get_derived_items(
        self,
        tenant_id: UUID,
        source_item_id: UUID,
    ) -> dict[str, list[Any]]:
        """Get all items derived from a source."""
        result: dict[str, list[Any]] = {"fields": [], "assets": []}

        for profile in self._profiles.values():
            if profile.tenant_id != tenant_id:
                continue

            # Check fields
            for field in profile.fields.values():
                if field.source_item_id == source_item_id:
                    result["fields"].append(field)

            # Check field history
            for history in self._field_history.get(profile.id, {}).values():
                for field in history:
                    if field.source_item_id == source_item_id:
                        result["fields"].append(field)

            # Check assets
            for asset in profile.assets:
                if asset.source_item_id == source_item_id:
                    result["assets"].append(asset)

        return result

    async def check_has_dependents(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Check if an item has dependent derived items."""
        derived = await self.get_derived_items(tenant_id, item_id)
        return bool(derived["fields"] or derived["assets"])

    # =========================================================================
    # CHANNEL OPERATIONS
    # =========================================================================

    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        identity: ChannelIdentity,
    ) -> bool:
        """Link a new channel identity to profile."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return False

        # Check if this identity is already linked to another profile
        existing = await self.get_by_channel_identity(
            tenant_id, identity.channel, identity.channel_user_id
        )
        if existing and existing.id != profile_id:
            return False  # Already linked to different profile

        profile.channel_identities.append(identity)
        profile.updated_at = datetime.now(UTC)
        return True

    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_profile_id: UUID,
        target_profile_id: UUID,
    ) -> bool:
        """Merge source profile into target profile."""
        source = await self.get_by_id(tenant_id, source_profile_id)
        target = await self.get_by_id(tenant_id, target_profile_id)

        if not source or not target:
            return False

        # Merge channel identities
        for identity in source.channel_identities:
            if identity not in target.channel_identities:
                target.channel_identities.append(identity)

        # Merge fields (source overwrites if newer)
        for name, field in source.fields.items():
            if name not in target.fields or field.updated_at > target.fields[name].updated_at:
                target.fields[name] = field

        # Merge field history
        source_history = self._field_history.pop(source_profile_id, {})
        if target_profile_id not in self._field_history:
            self._field_history[target_profile_id] = {}
        for name, history in source_history.items():
            if name not in self._field_history[target_profile_id]:
                self._field_history[target_profile_id][name] = []
            self._field_history[target_profile_id][name].extend(history)

        # Merge assets
        for asset in source.assets:
            if asset not in target.assets:
                target.assets.append(asset)

        # Merge consents
        for consent in source.consents:
            if consent not in target.consents:
                target.consents.append(consent)

        target.updated_at = datetime.now(UTC)

        # Delete source profile
        del self._profiles[source_profile_id]

        return True

    # =========================================================================
    # SCHEMA OPERATIONS
    # =========================================================================

    async def get_field_definitions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[CustomerDataField]:
        """Get all field definitions for an agent."""
        result = []
        for key, definition in self._field_definitions.items():
            if key[0] == tenant_id and key[1] == agent_id:
                if not enabled_only or definition.enabled:
                    result.append(definition)
        return result

    async def get_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> CustomerDataField | None:
        """Get a specific field definition by name."""
        return self._field_definitions.get((tenant_id, agent_id, field_name))

    async def save_field_definition(
        self,
        definition: CustomerDataField,
    ) -> UUID:
        """Save a field definition."""
        definition.updated_at = datetime.now(UTC)
        key = (definition.tenant_id, definition.agent_id, definition.name)
        self._field_definitions[key] = definition
        return definition.id

    async def delete_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> bool:
        """Delete a field definition."""
        key = (tenant_id, agent_id, field_name)
        if key in self._field_definitions:
            del self._field_definitions[key]
            return True
        return False

    # =========================================================================
    # SCENARIO REQUIREMENTS
    # =========================================================================

    async def get_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Get field requirements for a scenario/step."""
        result = []
        for req in self._scenario_requirements.values():
            if req.tenant_id != tenant_id or req.scenario_id != scenario_id:
                continue
            if step_id is not None and req.step_id != step_id:
                continue
            result.append(req)
        return sorted(result, key=lambda r: r.collection_order)

    async def save_scenario_requirement(
        self,
        requirement: ScenarioFieldRequirement,
    ) -> UUID:
        """Save a scenario field requirement."""
        requirement.updated_at = datetime.now(UTC)
        self._scenario_requirements[requirement.id] = requirement
        return requirement.id

    async def delete_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> int:
        """Delete requirements for a scenario/step."""
        to_delete = []
        for req_id, req in self._scenario_requirements.items():
            if req.tenant_id != tenant_id or req.scenario_id != scenario_id:
                continue
            if step_id is not None and req.step_id != step_id:
                continue
            to_delete.append(req_id)

        for req_id in to_delete:
            del self._scenario_requirements[req_id]

        return len(to_delete)

    async def get_missing_fields(
        self,
        tenant_id: UUID,
        profile: CustomerDataStore,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> list[ScenarioFieldRequirement]:
        """Get requirements not satisfied by the profile."""
        requirements = await self.get_scenario_requirements(
            tenant_id, scenario_id, step_id=step_id
        )

        missing = []
        for req in requirements:
            # Filter by required level
            if required_level and req.required_level.value != required_level:
                continue

            # Check if field exists and is active
            field = profile.fields.get(req.field_name)
            if not field or field.status != ItemStatus.ACTIVE:
                missing.append(req)
                continue

            # Check freshness if definition exists
            definition = await self.get_field_definition(
                tenant_id, profile.tenant_id, req.field_name  # Note: using profile.tenant_id for agent lookup
            )
            if definition and definition.freshness_seconds:
                age = (datetime.now(UTC) - field.collected_at).total_seconds()
                if age > definition.freshness_seconds:
                    missing.append(req)
                    continue

            # Check verification if required
            if definition and definition.required_verification and not field.verified:
                missing.append(req)

        return missing
