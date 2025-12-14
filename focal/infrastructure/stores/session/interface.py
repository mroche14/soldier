"""SessionStore abstract interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

from focal.conversation.models import Channel, Session, SessionStatus

if TYPE_CHECKING:
    from focal.alignment.migration.models import ScopeFilter


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

    @abstractmethod
    async def find_sessions_by_step_hash(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: "ScopeFilter | None" = None,
    ) -> list[Session]:
        """Find sessions at a step matching the content hash.

        Used for migration deployment to mark eligible sessions.

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario identifier
            scenario_version: Scenario version
            step_content_hash: Step content hash to match
            scope_filter: Optional filter for eligible sessions

        Returns:
            List of matching sessions
        """
        pass
