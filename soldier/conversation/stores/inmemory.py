"""In-memory implementation of SessionStore."""

from datetime import UTC, datetime
from uuid import UUID

from soldier.conversation.models import Channel, Session, SessionStatus
from soldier.conversation.store import SessionStore


class InMemorySessionStore(SessionStore):
    """In-memory implementation of SessionStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._sessions: dict[UUID, Session] = {}

    async def get(self, session_id: UUID) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def save(self, session: Session) -> UUID:
        """Save a session, returning its ID."""
        session.last_activity_at = datetime.now(UTC)
        self._sessions[session.session_id] = session
        return session.session_id

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def get_by_channel(
        self,
        tenant_id: UUID,
        channel: Channel,
        user_channel_id: str,
    ) -> Session | None:
        """Get session by channel identity."""
        for session in self._sessions.values():
            if (
                session.tenant_id == tenant_id
                and session.channel == channel
                and session.user_channel_id == user_channel_id
            ):
                return session
        return None

    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        status: SessionStatus | None = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for an agent with optional status filter."""
        results = []
        for session in self._sessions.values():
            if session.tenant_id != tenant_id:
                continue
            if session.agent_id != agent_id:
                continue
            if status is not None and session.status != status:
                continue
            results.append(session)
        # Sort by last_activity_at descending
        results.sort(key=lambda x: x.last_activity_at, reverse=True)
        return results[:limit]

    async def list_by_customer(
        self,
        tenant_id: UUID,
        customer_profile_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for a customer profile."""
        results = []
        for session in self._sessions.values():
            if session.tenant_id != tenant_id:
                continue
            if session.customer_profile_id != customer_profile_id:
                continue
            results.append(session)
        # Sort by last_activity_at descending
        results.sort(key=lambda x: x.last_activity_at, reverse=True)
        return results[:limit]
