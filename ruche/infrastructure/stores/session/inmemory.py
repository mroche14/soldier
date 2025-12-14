"""In-memory implementation of SessionStore."""

from datetime import UTC, datetime
from uuid import UUID

from ruche.alignment.migration.models import ScopeFilter
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.store import SessionStore


class InMemorySessionStore(SessionStore):
    """In-memory implementation of SessionStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._sessions: dict[UUID, Session] = {}
        self._step_hash_index: dict[str, set[UUID]] = {}

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

    async def find_sessions_by_step_hash(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None,
    ) -> list[Session]:
        """Find sessions at a step matching the content hash."""
        results = []
        for session in self._sessions.values():
            if session.tenant_id != tenant_id:
                continue
            if session.active_scenario_id != scenario_id:
                continue
            if session.active_scenario_version != scenario_version:
                continue
            if session.status != SessionStatus.ACTIVE:
                continue

            # Check if current step matches the content hash
            current_step_hash = None
            if session.step_history:
                last_visit = session.step_history[-1]
                current_step_hash = last_visit.step_content_hash

            if current_step_hash != step_content_hash:
                continue

            # Apply scope filter if provided
            if scope_filter and not self._matches_scope_filter(session, scope_filter):
                continue

            results.append(session)

        return results

    def _matches_scope_filter(
        self, session: Session, scope_filter: ScopeFilter
    ) -> bool:
        """Check if session matches the scope filter."""
        # Channel filtering
        if (
            scope_filter.include_channels
            and session.channel.value not in scope_filter.include_channels
        ):
            return False
        if (
            scope_filter.exclude_channels
            and session.channel.value in scope_filter.exclude_channels
        ):
            return False

        # Node filtering (check last step visit name)
        step_name = None
        if session.step_history:
            step_name = session.step_history[-1].step_name

        if (
            scope_filter.include_current_nodes
            and step_name not in scope_filter.include_current_nodes
        ):
            return False
        if (
            scope_filter.exclude_current_nodes
            and step_name in scope_filter.exclude_current_nodes
        ):
            return False

        # Age filtering
        now = datetime.now(UTC)
        age_days = (now - session.created_at).days

        if (
            scope_filter.max_session_age_days is not None
            and age_days > scope_filter.max_session_age_days
        ):
            return False

        return not (
            scope_filter.min_session_age_days is not None
            and age_days < scope_filter.min_session_age_days
        )
