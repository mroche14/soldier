"""AuditStore abstract interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ruche.audit.models import AuditEvent, TurnRecord


class AuditStore(ABC):
    """Abstract interface for audit storage.

    Manages turn records and audit events with support
    for time-series queries.
    """

    # Turn record operations
    @abstractmethod
    async def save_turn(self, turn: TurnRecord) -> UUID:
        """Save a turn record."""
        pass

    @abstractmethod
    async def get_turn(self, turn_id: UUID) -> TurnRecord | None:
        """Get a turn record by ID."""
        pass

    @abstractmethod
    async def list_turns_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turn records for a session in chronological order."""
        pass

    @abstractmethod
    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[TurnRecord]:
        """List turn records for a tenant with optional time filter."""
        pass

    # Audit event operations
    @abstractmethod
    async def save_event(self, event: AuditEvent) -> UUID:
        """Save an audit event."""
        pass

    @abstractmethod
    async def get_event(self, event_id: UUID) -> AuditEvent | None:
        """Get an audit event by ID."""
        pass

    @abstractmethod
    async def list_events_by_session(
        self,
        session_id: UUID,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """List audit events for a session."""
        pass
