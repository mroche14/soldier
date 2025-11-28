"""In-memory implementation of ProfileStore."""

from datetime import UTC, datetime
from uuid import UUID

from soldier.conversation.models import Channel
from soldier.profile.models import ChannelIdentity, CustomerProfile, ProfileAsset, ProfileField
from soldier.profile.store import ProfileStore


class InMemoryProfileStore(ProfileStore):
    """In-memory implementation of ProfileStore for testing and development."""

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._profiles: dict[UUID, CustomerProfile] = {}

    async def get_by_customer_id(
        self, tenant_id: UUID, customer_id: UUID
    ) -> CustomerProfile | None:
        """Get profile by customer ID."""
        for profile in self._profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.customer_id == customer_id
            ):
                return profile
        return None

    async def get_by_id(
        self, tenant_id: UUID, profile_id: UUID
    ) -> CustomerProfile | None:
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
    ) -> CustomerProfile | None:
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
    ) -> CustomerProfile:
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
        profile = CustomerProfile(
            tenant_id=tenant_id,
            channel_identities=[identity],
        )
        await self.save(profile)
        return profile

    async def save(self, profile: CustomerProfile) -> UUID:
        """Save a profile."""
        profile.updated_at = datetime.now(UTC)
        self._profiles[profile.id] = profile
        return profile.id

    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
    ) -> bool:
        """Update a profile field."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return False

        field.updated_at = datetime.now(UTC)
        profile.fields[field.name] = field
        profile.updated_at = datetime.now(UTC)
        return True

    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
    ) -> bool:
        """Add an asset to profile."""
        profile = await self.get_by_id(tenant_id, profile_id)
        if not profile:
            return False

        profile.assets.append(asset)
        profile.updated_at = datetime.now(UTC)
        return True

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
