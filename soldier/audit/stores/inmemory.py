"""In-memory implementation of AuditStore."""

from datetime import datetime
from uuid import UUID

from soldier.audit.models import AuditEvent, TurnRecord
from soldier.audit.store import AuditStore


class InMemoryAuditStore(AuditStore):
    """In-memory implementation of AuditStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._turns: dict[UUID, TurnRecord] = {}
        self._events: dict[UUID, AuditEvent] = {}

    # Turn record operations
    async def save_turn(self, turn: TurnRecord) -> UUID:
        """Save a turn record."""
        self._turns[turn.turn_id] = turn
        return turn.turn_id

    async def get_turn(self, turn_id: UUID) -> TurnRecord | None:
        """Get a turn record by ID."""
        return self._turns.get(turn_id)

    async def list_turns_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turn records for a session in chronological order."""
        results = [
            turn for turn in self._turns.values()
            if turn.session_id == session_id
        ]
        # Sort by timestamp ascending (chronological)
        results.sort(key=lambda x: x.timestamp)
        return results[offset:offset + limit]

    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[TurnRecord]:
        """List turn records for a tenant with optional time filter."""
        results = []
        for turn in self._turns.values():
            if turn.tenant_id != tenant_id:
                continue
            if start_time is not None and turn.timestamp < start_time:
                continue
            if end_time is not None and turn.timestamp > end_time:
                continue
            results.append(turn)
        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    # Audit event operations
    async def save_event(self, event: AuditEvent) -> UUID:
        """Save an audit event."""
        self._events[event.id] = event
        return event.id

    async def get_event(self, event_id: UUID) -> AuditEvent | None:
        """Get an audit event by ID."""
        return self._events.get(event_id)

    async def list_events_by_session(
        self,
        session_id: UUID,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """List audit events for a session."""
        results = []
        for event in self._events.values():
            if event.session_id != session_id:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            results.append(event)
        # Sort by timestamp ascending (chronological)
        results.sort(key=lambda x: x.timestamp)
        return results[:limit]
