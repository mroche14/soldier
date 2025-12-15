"""PostgreSQL implementation of AuditStore.

Uses asyncpg for async database access.
"""

import json
from datetime import datetime
from uuid import UUID

from ruche.audit.models import AuditEvent, TurnRecord
from ruche.audit.store import AuditStore
from ruche.infrastructure.db.errors import ConnectionError
from ruche.infrastructure.db.pool import PostgresPool
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class PostgresAuditStore(AuditStore):
    """PostgreSQL implementation of AuditStore.

    Uses asyncpg connection pool for efficient database access.
    All records are immutable once written.
    """

    def __init__(self, pool: PostgresPool) -> None:
        """Initialize with connection pool.

        Args:
            pool: PostgreSQL connection pool
        """
        self._pool = pool

    # Turn record operations
    async def save_turn(self, turn: TurnRecord) -> UUID:
        """Save a turn record."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO turn_records (
                        id, tenant_id, session_id, turn_number,
                        user_message, assistant_response, context_extracted,
                        rules_matched, scenario_state, tools_executed,
                        token_usage, latency_ms, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                    turn.turn_id,
                    turn.tenant_id,
                    turn.session_id,
                    turn.turn_number,
                    turn.user_message,
                    turn.agent_response,
                    None,  # context_extracted - not in model
                    json.dumps([str(rid) for rid in turn.matched_rule_ids]),
                    json.dumps({
                        "scenario_id": str(turn.scenario_id) if turn.scenario_id else None,
                        "step_id": str(turn.step_id) if turn.step_id else None,
                    }),
                    json.dumps([tc.model_dump(mode="json") for tc in turn.tool_calls]),
                    json.dumps({"total": turn.tokens_used}),
                    turn.latency_ms,
                    turn.timestamp,
                )
                logger.debug("turn_record_saved", turn_id=str(turn.turn_id))
                return turn.turn_id
        except Exception as e:
            logger.error(
                "postgres_save_turn_error", turn_id=str(turn.turn_id), error=str(e)
            )
            raise ConnectionError(f"Failed to save turn record: {e}", cause=e) from e

    async def get_turn(self, turn_id: UUID) -> TurnRecord | None:
        """Get a turn record by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, session_id, turn_number,
                           user_message, assistant_response, context_extracted,
                           rules_matched, scenario_state, tools_executed,
                           token_usage, latency_ms, created_at
                    FROM turn_records
                    WHERE id = $1
                    """,
                    turn_id,
                )
                if row:
                    return self._row_to_turn_record(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_turn_error", turn_id=str(turn_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get turn record: {e}", cause=e) from e

    async def list_turns_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turn records for a session in chronological order."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, tenant_id, session_id, turn_number,
                           user_message, assistant_response, context_extracted,
                           rules_matched, scenario_state, tools_executed,
                           token_usage, latency_ms, created_at
                    FROM turn_records
                    WHERE session_id = $1
                    ORDER BY turn_number ASC
                    LIMIT $2 OFFSET $3
                    """,
                    session_id,
                    limit,
                    offset,
                )
                return [self._row_to_turn_record(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_list_turns_by_session_error",
                session_id=str(session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to list turn records: {e}", cause=e) from e

    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[TurnRecord]:
        """List turn records for a tenant with optional time filter."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, session_id, turn_number,
                           user_message, assistant_response, context_extracted,
                           rules_matched, scenario_state, tools_executed,
                           token_usage, latency_ms, created_at
                    FROM turn_records
                    WHERE tenant_id = $1
                """
                params: list = [tenant_id]

                if start_time is not None:
                    params.append(start_time)
                    query += f" AND created_at >= ${len(params)}"

                if end_time is not None:
                    params.append(end_time)
                    query += f" AND created_at <= ${len(params)}"

                params.append(limit)
                query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

                rows = await conn.fetch(query, *params)
                return [self._row_to_turn_record(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_list_turns_by_tenant_error",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to list turn records: {e}", cause=e) from e

    # Audit event operations
    async def save_event(self, event: AuditEvent) -> UUID:
        """Save an audit event."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events (
                        id, tenant_id, session_id, turn_id,
                        event_type, event_data, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    event.id,
                    event.tenant_id,
                    event.session_id,
                    event.turn_id,
                    event.event_type,
                    json.dumps(event.event_data),
                    event.timestamp,
                )
                logger.debug("audit_event_saved", event_id=str(event.id))
                return event.id
        except Exception as e:
            logger.error(
                "postgres_save_event_error", event_id=str(event.id), error=str(e)
            )
            raise ConnectionError(f"Failed to save audit event: {e}", cause=e) from e

    async def get_event(self, event_id: UUID) -> AuditEvent | None:
        """Get an audit event by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, session_id, turn_id,
                           event_type, event_data, created_at
                    FROM audit_events
                    WHERE id = $1
                    """,
                    event_id,
                )
                if row:
                    return self._row_to_audit_event(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_event_error", event_id=str(event_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get audit event: {e}", cause=e) from e

    async def list_events_by_session(
        self,
        session_id: UUID,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """List audit events for a session."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, session_id, turn_id,
                           event_type, event_data, created_at
                    FROM audit_events
                    WHERE session_id = $1
                """
                params: list = [session_id]

                if event_type is not None:
                    params.append(event_type)
                    query += f" AND event_type = ${len(params)}"

                params.append(limit)
                query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

                rows = await conn.fetch(query, *params)
                return [self._row_to_audit_event(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_list_events_by_session_error",
                session_id=str(session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to list audit events: {e}", cause=e) from e

    # Helper methods
    def _row_to_turn_record(self, row) -> TurnRecord:
        """Convert database row to TurnRecord model."""
        from ruche.conversation.models.turn import ToolCall

        rules_matched = json.loads(row["rules_matched"]) if row["rules_matched"] else []
        scenario_state = json.loads(row["scenario_state"]) if row["scenario_state"] else {}
        tools_executed = json.loads(row["tools_executed"]) if row["tools_executed"] else []
        token_usage = json.loads(row["token_usage"]) if row["token_usage"] else {}

        return TurnRecord(
            turn_id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["tenant_id"],  # Not stored separately, using tenant_id
            session_id=row["session_id"],
            turn_number=row["turn_number"],
            user_message=row["user_message"],
            agent_response=row["assistant_response"] or "",
            matched_rule_ids=[UUID(rid) for rid in rules_matched],
            scenario_id=UUID(scenario_state.get("scenario_id")) if scenario_state.get("scenario_id") else None,
            step_id=UUID(scenario_state.get("step_id")) if scenario_state.get("step_id") else None,
            tool_calls=[ToolCall.model_validate(tc) for tc in tools_executed],
            latency_ms=row["latency_ms"] or 0,
            tokens_used=token_usage.get("total", 0),
            timestamp=row["created_at"],
        )

    def _row_to_audit_event(self, row) -> AuditEvent:
        """Convert database row to AuditEvent model."""
        return AuditEvent(
            id=row["id"],
            tenant_id=row["tenant_id"],
            event_type=row["event_type"],
            event_data=json.loads(row["event_data"]) if row["event_data"] else {},
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            timestamp=row["created_at"],
        )
