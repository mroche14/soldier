"""SessionStore abstract interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from soldier.conversation.models import Channel, Session, SessionStatus


class SessionStore(ABC):
    """Abstract interface for session storage.

    Manages session state with support for channel-based
    lookup and status filtering.
    """

    @abstractmethod
    async def get(self, session_id: UUID) -> Session | None:
        """Get a session by ID."""
        pass

    @abstractmethod
    async def save(self, session: Session) -> UUID:
        """Save a session, returning its ID."""
        pass

    @abstractmethod
    async def delete(self, session_id: UUID) -> bool:
        """Delete a session."""
        pass

    @abstractmethod
    async def get_by_channel(
        self,
        tenant_id: UUID,
        channel: Channel,
        user_channel_id: str,
    ) -> Session | None:
        """Get session by channel identity."""
        pass

    @abstractmethod
    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        status: SessionStatus | None = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for an agent with optional status filter."""
        pass

    @abstractmethod
    async def list_by_customer(
        self,
        tenant_id: UUID,
        customer_profile_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for a customer profile."""
        pass
