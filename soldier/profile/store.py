"""ProfileStore abstract interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from soldier.conversation.models import Channel
from soldier.profile.models import ChannelIdentity, CustomerProfile, ProfileAsset, ProfileField


class ProfileStore(ABC):
    """Abstract interface for customer profile storage.

    Manages customer profiles with support for channel
    identity lookup and field updates.
    """

    @abstractmethod
    async def get_by_customer_id(
        self, tenant_id: UUID, customer_id: UUID
    ) -> CustomerProfile | None:
        """Get profile by customer ID."""
        pass

    @abstractmethod
    async def get_by_id(
        self, tenant_id: UUID, profile_id: UUID
    ) -> CustomerProfile | None:
        """Get profile by profile ID."""
        pass

    @abstractmethod
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile | None:
        """Get profile by channel identity."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile:
        """Get existing profile or create new one for channel identity."""
        pass

    @abstractmethod
    async def save(self, profile: CustomerProfile) -> UUID:
        """Save a profile."""
        pass

    @abstractmethod
    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
    ) -> bool:
        """Update a profile field."""
        pass

    @abstractmethod
    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
    ) -> bool:
        """Add an asset to profile."""
        pass

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
        """Merge source profile into target profile."""
        pass
