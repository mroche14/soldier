"""PostgreSQL implementation of SessionStore.

Provides persistent storage for sessions with full query support.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from ruche.brains.focal.migration.models import ScopeFilter
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.store import SessionStore
from ruche.infrastructure.db.errors import ConnectionError, NotFoundError
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


def _serialize_json(obj: Any) -> Any:
    """Serialize objects for JSON storage."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return obj


class PostgresSessionStore(SessionStore):
    """PostgreSQL implementation of SessionStore.

    Stores sessions in PostgreSQL for long-term persistence.
    Used as fallback/persistent tier for Redis cache.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Initialize PostgreSQL session store.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    def _session_to_dict(self, session: Session) -> dict[str, Any]:
        """Convert Session to dict for database storage."""
        data = session.model_dump(mode="json")
        # Convert enums and UUIDs
        data["channel"] = session.channel.value
        data["status"] = session.status.value
        return data

    def _dict_to_session(self, row: dict[str, Any]) -> Session:
        """Convert database row to Session model."""
        # Convert channel and status back to enums
        row["channel"] = Channel(row["channel"])
        row["status"] = SessionStatus(row["status"])
        return Session.model_validate(row)

    async def get(self, session_id: UUID) -> Session | None:
        """Get a session by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM sessions
                    WHERE session_id = $1
                    """,
                    session_id,
                )

                if not row:
                    logger.debug(
                        "session_not_found",
                        session_id=str(session_id),
                    )
                    return None

                session = self._dict_to_session(dict(row))
                logger.debug(
                    "session_retrieved",
                    session_id=str(session_id),
                    tenant_id=str(session.tenant_id),
                )
                return session

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_get_error",
                session_id=str(session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get session: {e}", cause=e) from e

    async def save(self, session: Session) -> UUID:
        """Save a session to PostgreSQL.

        Updates last_activity_at and upserts the session.
        """
        try:
            session.last_activity_at = datetime.now(UTC)
            data = self._session_to_dict(session)

            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, tenant_id, agent_id, channel, user_channel_id,
                        customer_profile_id, config_version, active_scenarios,
                        active_scenario_id, active_step_id, active_scenario_version,
                        step_history, relocalization_count, rule_fires, rule_last_fire_turn,
                        variables, variable_updated_at, turn_count, status,
                        pending_migration, scenario_checksum, created_at, last_activity_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                    )
                    ON CONFLICT (session_id) DO UPDATE SET
                        customer_profile_id = EXCLUDED.customer_profile_id,
                        config_version = EXCLUDED.config_version,
                        active_scenarios = EXCLUDED.active_scenarios,
                        active_scenario_id = EXCLUDED.active_scenario_id,
                        active_step_id = EXCLUDED.active_step_id,
                        active_scenario_version = EXCLUDED.active_scenario_version,
                        step_history = EXCLUDED.step_history,
                        relocalization_count = EXCLUDED.relocalization_count,
                        rule_fires = EXCLUDED.rule_fires,
                        rule_last_fire_turn = EXCLUDED.rule_last_fire_turn,
                        variables = EXCLUDED.variables,
                        variable_updated_at = EXCLUDED.variable_updated_at,
                        turn_count = EXCLUDED.turn_count,
                        status = EXCLUDED.status,
                        pending_migration = EXCLUDED.pending_migration,
                        scenario_checksum = EXCLUDED.scenario_checksum,
                        last_activity_at = EXCLUDED.last_activity_at
                    """,
                    data["session_id"],
                    data["tenant_id"],
                    data["agent_id"],
                    data["channel"],
                    data["user_channel_id"],
                    data.get("customer_profile_id"),
                    data["config_version"],
                    data["active_scenarios"],
                    data.get("active_scenario_id"),
                    data.get("active_step_id"),
                    data.get("active_scenario_version"),
                    data["step_history"],
                    data["relocalization_count"],
                    data["rule_fires"],
                    data["rule_last_fire_turn"],
                    data["variables"],
                    data["variable_updated_at"],
                    data["turn_count"],
                    data["status"],
                    data.get("pending_migration"),
                    data.get("scenario_checksum"),
                    data["created_at"],
                    data["last_activity_at"],
                )

                logger.info(
                    "session_saved",
                    session_id=str(session.session_id),
                    tenant_id=str(session.tenant_id),
                    agent_id=str(session.agent_id),
                )

                return session.session_id

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_save_error",
                session_id=str(session.session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save session: {e}", cause=e) from e

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session from PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM sessions
                    WHERE session_id = $1
                    """,
                    session_id,
                )

                deleted = result.split()[-1] == "1"
                logger.info(
                    "session_deleted",
                    session_id=str(session_id),
                    deleted=deleted,
                )
                return deleted

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_delete_error",
                session_id=str(session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete session: {e}", cause=e) from e

    async def get_by_channel(
        self,
        tenant_id: UUID,
        channel: Channel,
        user_channel_id: str,
    ) -> Session | None:
        """Get session by channel identity."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM sessions
                    WHERE tenant_id = $1
                      AND channel = $2
                      AND user_channel_id = $3
                    ORDER BY last_activity_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                    channel.value,
                    user_channel_id,
                )

                if not row:
                    logger.debug(
                        "session_not_found_by_channel",
                        tenant_id=str(tenant_id),
                        channel=channel.value,
                        user_channel_id=user_channel_id,
                    )
                    return None

                return self._dict_to_session(dict(row))

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_get_by_channel_error",
                tenant_id=str(tenant_id),
                channel=channel.value,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get session by channel: {e}", cause=e) from e

    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        status: SessionStatus | None = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for an agent."""
        try:
            async with self._pool.acquire() as conn:
                if status:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM sessions
                        WHERE tenant_id = $1
                          AND agent_id = $2
                          AND status = $3
                        ORDER BY last_activity_at DESC
                        LIMIT $4
                        """,
                        tenant_id,
                        agent_id,
                        status.value,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM sessions
                        WHERE tenant_id = $1
                          AND agent_id = $2
                        ORDER BY last_activity_at DESC
                        LIMIT $3
                        """,
                        tenant_id,
                        agent_id,
                        limit,
                    )

                sessions = [self._dict_to_session(dict(row)) for row in rows]
                logger.debug(
                    "sessions_listed_by_agent",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    count=len(sessions),
                )
                return sessions

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_list_by_agent_error",
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to list sessions by agent: {e}", cause=e) from e

    async def list_by_customer(
        self,
        tenant_id: UUID,
        customer_profile_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for a customer profile."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE tenant_id = $1
                      AND customer_profile_id = $2
                    ORDER BY last_activity_at DESC
                    LIMIT $3
                    """,
                    tenant_id,
                    customer_profile_id,
                    limit,
                )

                sessions = [self._dict_to_session(dict(row)) for row in rows]
                logger.debug(
                    "sessions_listed_by_customer",
                    tenant_id=str(tenant_id),
                    customer_profile_id=str(customer_profile_id),
                    count=len(sessions),
                )
                return sessions

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_list_by_customer_error",
                tenant_id=str(tenant_id),
                customer_profile_id=str(customer_profile_id),
                error=str(e),
            )
            raise ConnectionError(
                f"Failed to list sessions by customer: {e}", cause=e
            ) from e

    async def find_sessions_by_step_hash(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None,
    ) -> list[Session]:
        """Find sessions at a step matching the content hash.

        Used for migration deployment to mark eligible sessions.
        """
        try:
            async with self._pool.acquire() as conn:
                # Base query for active sessions in scenario
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE tenant_id = $1
                      AND active_scenario_id = $2
                      AND active_scenario_version = $3
                      AND status = 'active'
                    """,
                    tenant_id,
                    scenario_id,
                    scenario_version,
                )

                results = []
                for row in rows:
                    session = self._dict_to_session(dict(row))

                    # Check current step hash
                    if not session.step_history:
                        continue

                    last_visit = session.step_history[-1]
                    if last_visit.step_content_hash != step_content_hash:
                        continue

                    # Apply scope filter
                    if scope_filter and not self._matches_scope_filter(session, scope_filter):
                        continue

                    results.append(session)

                logger.info(
                    "sessions_found_by_step_hash",
                    tenant_id=str(tenant_id),
                    scenario_id=str(scenario_id),
                    step_content_hash=step_content_hash,
                    count=len(results),
                )

                return results

        except asyncpg.PostgresError as e:
            logger.error(
                "postgres_find_by_step_hash_error",
                tenant_id=str(tenant_id),
                scenario_id=str(scenario_id),
                error=str(e),
            )
            raise ConnectionError(
                f"Failed to find sessions by step hash: {e}", cause=e
            ) from e

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
