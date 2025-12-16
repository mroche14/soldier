"""Redis implementation of SessionStore with PostgreSQL fallback.

Implements hot cache (30 min TTL) in Redis with PostgreSQL as
persistent storage fallback. Write-through to both tiers.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as redis
from pydantic import BaseModel

from ruche.brains.focal.migration.models import ScopeFilter
from ruche.config.models.storage import RedisSessionConfig
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.store import SessionStore
from ruche.infrastructure.db.errors import ConnectionError
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


def _json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class RedisSessionStore(SessionStore):
    """Redis implementation of SessionStore with PostgreSQL fallback.

    Uses Redis as hot cache (30 min TTL) and PostgreSQL as persistent
    storage. Write-through to both on save. Read from Redis first, then
    PostgreSQL on cache miss.

    Key structure:
    - session:hot:{session_id} - Hot cache (30 min TTL)
    - session:index:agent:{tenant_id}:{agent_id} - Session IDs by agent
    - session:index:customer:{tenant_id}:{profile_id} - Session IDs by customer
    - session:index:channel:{tenant_id}:{channel}:{user_id} - Session by channel
    """

    def __init__(
        self,
        client: redis.Redis,
        pg_pool: asyncpg.Pool | None = None,
        config: RedisSessionConfig | None = None,
    ) -> None:
        """Initialize Redis session store with PostgreSQL fallback.

        Args:
            client: Redis client instance
            pg_pool: PostgreSQL connection pool for persistent storage
            config: Redis session configuration (uses defaults if not provided)
        """
        self._client = client
        self._pg_pool = pg_pool
        self._config = config or RedisSessionConfig()
        self._prefix = self._config.key_prefix

    def _hot_key(self, session_id: UUID) -> str:
        """Get hot cache key for session."""
        return f"{self._prefix}:hot:{session_id}"

    def _agent_index_key(self, tenant_id: UUID, agent_id: UUID) -> str:
        """Get agent index key."""
        return f"{self._prefix}:index:agent:{tenant_id}:{agent_id}"

    def _customer_index_key(self, tenant_id: UUID, profile_id: UUID) -> str:
        """Get customer index key."""
        return f"{self._prefix}:index:customer:{tenant_id}:{profile_id}"

    def _channel_index_key(
        self, tenant_id: UUID, channel: Channel, user_channel_id: str
    ) -> str:
        """Get channel index key."""
        return f"{self._prefix}:index:channel:{tenant_id}:{channel.value}:{user_channel_id}"

    def _serialize_session(self, session: Session) -> str:
        """Serialize session to JSON string."""
        return session.model_dump_json()

    def _deserialize_session(self, data: str) -> Session:
        """Deserialize session from JSON string."""
        return Session.model_validate_json(data)

    async def get(self, session_id: UUID) -> Session | None:
        """Get a session by ID.

        Checks Redis cache first, then PostgreSQL on cache miss.
        Auto-caches to Redis if found in PostgreSQL.
        """
        try:
            # Try Redis cache first
            hot_key = self._hot_key(session_id)
            data = await self._client.get(hot_key)

            if data:
                logger.debug(
                    "session_retrieved_cache",
                    session_id=str(session_id),
                )
                return self._deserialize_session(data)

            # Fall back to PostgreSQL if configured
            if self._pg_pool:
                session = await self._get_from_postgres(session_id)
                if session:
                    logger.debug(
                        "session_retrieved_postgres",
                        session_id=str(session_id),
                    )
                    # Cache in Redis for future reads
                    await self._cache_to_redis(session)
                    return session

            logger.debug(
                "session_not_found",
                session_id=str(session_id),
            )
            return None

        except redis.RedisError as e:
            logger.error(
                "redis_get_error",
                session_id=str(session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get session: {e}", cause=e) from e

    async def save(self, session: Session) -> UUID:
        """Save a session to both Redis cache and PostgreSQL.

        Write-through pattern: writes to both tiers.
        Updates last_activity_at and maintains indexes.
        """
        try:
            session.last_activity_at = datetime.now(UTC)

            # Write to PostgreSQL first (persistent storage)
            if self._pg_pool:
                await self._save_to_postgres(session)

            # Then cache in Redis
            await self._cache_to_redis(session)

            # Update indexes
            await self._update_indexes(session)

            logger.info(
                "session_saved",
                session_id=str(session.session_id),
                tenant_id=str(session.tenant_id),
                agent_id=str(session.agent_id),
            )

            return session.session_id

        except (redis.RedisError, asyncpg.PostgresError) as e:
            logger.error(
                "session_save_error",
                session_id=str(session.session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save session: {e}", cause=e) from e

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session from both Redis cache and PostgreSQL.

        Also removes from all indexes.
        """
        try:
            # Get session first to clean up indexes
            session = await self.get(session_id)

            # Delete from Redis cache
            hot_key = self._hot_key(session_id)
            await self._client.delete(hot_key)

            # Delete from PostgreSQL if configured
            if self._pg_pool:
                await self._delete_from_postgres(session_id)

            # Clean up indexes if session existed
            if session:
                await self._remove_from_indexes(session)

            logger.info(
                "session_deleted",
                session_id=str(session_id),
                deleted=session is not None,
            )

            return session is not None

        except (redis.RedisError, asyncpg.PostgresError) as e:
            logger.error(
                "session_delete_error",
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
        """Get session by channel identity using index."""
        try:
            channel_key = self._channel_index_key(tenant_id, channel, user_channel_id)
            session_id_str = await self._client.get(channel_key)

            if not session_id_str:
                logger.debug(
                    "session_not_found_by_channel",
                    tenant_id=str(tenant_id),
                    channel=channel.value,
                    user_channel_id=user_channel_id,
                )
                return None

            session_id = UUID(session_id_str)
            return await self.get(session_id)

        except redis.RedisError as e:
            logger.error(
                "redis_get_by_channel_error",
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
        """List sessions for an agent using index set."""
        try:
            index_key = self._agent_index_key(tenant_id, agent_id)
            session_ids = await self._client.smembers(index_key)

            sessions = []
            for session_id_str in session_ids:
                session = await self.get(UUID(session_id_str))
                if session:
                    if status is None or session.status == status:
                        sessions.append(session)

            # Sort by last_activity_at descending
            sessions.sort(key=lambda x: x.last_activity_at, reverse=True)

            logger.debug(
                "sessions_listed_by_agent",
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
                count=len(sessions[:limit]),
            )

            return sessions[:limit]

        except redis.RedisError as e:
            logger.error(
                "redis_list_by_agent_error",
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
        """List sessions for a customer profile using index set."""
        try:
            index_key = self._customer_index_key(tenant_id, customer_profile_id)
            session_ids = await self._client.smembers(index_key)

            sessions = []
            for session_id_str in session_ids:
                session = await self.get(UUID(session_id_str))
                if session:
                    sessions.append(session)

            # Sort by last_activity_at descending
            sessions.sort(key=lambda x: x.last_activity_at, reverse=True)

            logger.debug(
                "sessions_listed_by_customer",
                tenant_id=str(tenant_id),
                customer_profile_id=str(customer_profile_id),
                count=len(sessions[:limit]),
            )

            return sessions[:limit]

        except redis.RedisError as e:
            logger.error(
                "redis_list_by_customer_error",
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
        Uses PostgreSQL for efficient query if available, otherwise scans Redis.
        """
        # Use PostgreSQL for efficient query if available
        if self._pg_pool:
            return await self._find_sessions_by_step_hash_postgres(
                tenant_id, scenario_id, scenario_version, step_content_hash, scope_filter
            )

        # Fallback to Redis scan (less efficient)
        try:
            pattern = f"{self._prefix}:hot:*"
            results = []

            async for key in self._client.scan_iter(match=pattern):
                data = await self._client.get(key)
                if not data:
                    continue

                session = self._deserialize_session(data)

                # Filter conditions
                if session.tenant_id != tenant_id:
                    continue
                if session.active_scenario_id != scenario_id:
                    continue
                if session.active_scenario_version != scenario_version:
                    continue
                if session.status != SessionStatus.ACTIVE:
                    continue

                # Check current step hash
                current_step_hash = None
                if session.step_history:
                    last_visit = session.step_history[-1]
                    current_step_hash = last_visit.step_content_hash

                if current_step_hash != step_content_hash:
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

        except redis.RedisError as e:
            logger.error(
                "redis_find_by_step_hash_error",
                tenant_id=str(tenant_id),
                scenario_id=str(scenario_id),
                error=str(e),
            )
            raise ConnectionError(
                f"Failed to find sessions by step hash: {e}", cause=e
            ) from e

    async def _cache_to_redis(self, session: Session) -> None:
        """Cache a session to Redis with TTL."""
        data = self._serialize_session(session)
        hot_key = self._hot_key(session.session_id)
        await self._client.setex(
            hot_key,
            self._config.hot_ttl_seconds,
            data,
        )

    async def _get_from_postgres(self, session_id: UUID) -> Session | None:
        """Get session from PostgreSQL."""
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM sessions
                WHERE session_id = $1
                """,
                session_id,
            )

            if not row:
                return None

            return self._dict_to_session(dict(row))

    async def _save_to_postgres(self, session: Session) -> None:
        """Save session to PostgreSQL."""
        data = self._session_to_dict(session)

        async with self._pg_pool.acquire() as conn:
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

    async def _delete_from_postgres(self, session_id: UUID) -> None:
        """Delete session from PostgreSQL."""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM sessions
                WHERE session_id = $1
                """,
                session_id,
            )

    async def _find_sessions_by_step_hash_postgres(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None,
    ) -> list[Session]:
        """Find sessions by step hash using PostgreSQL query."""
        async with self._pg_pool.acquire() as conn:
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

            return results

    def _session_to_dict(self, session: Session) -> dict:
        """Convert Session to dict for PostgreSQL storage."""
        data = session.model_dump(mode="json")
        data["channel"] = session.channel.value
        data["status"] = session.status.value
        return data

    def _dict_to_session(self, row: dict) -> Session:
        """Convert PostgreSQL row to Session model."""
        row["channel"] = Channel(row["channel"])
        row["status"] = SessionStatus(row["status"])
        return Session.model_validate(row)

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self._client.ping()
            logger.debug("redis_health_check_passed")
            return True
        except redis.RedisError as e:
            logger.warning(
                "redis_health_check_failed",
                error=str(e),
            )
            return False

    async def _update_indexes(self, session: Session) -> None:
        """Update all indexes for a session."""
        session_id_str = str(session.session_id)

        # Agent index
        agent_key = self._agent_index_key(session.tenant_id, session.agent_id)
        await self._client.sadd(agent_key, session_id_str)
        await self._client.expire(agent_key, self._config.persist_ttl_seconds)

        # Customer index (if profile linked)
        if session.customer_profile_id:
            customer_key = self._customer_index_key(
                session.tenant_id, session.customer_profile_id
            )
            await self._client.sadd(customer_key, session_id_str)
            await self._client.expire(customer_key, self._config.persist_ttl_seconds)

        # Channel index
        channel_key = self._channel_index_key(
            session.tenant_id, session.channel, session.user_channel_id
        )
        await self._client.setex(
            channel_key,
            self._config.persist_ttl_seconds,
            session_id_str,
        )

    async def _remove_from_indexes(self, session: Session) -> None:
        """Remove session from all indexes."""
        session_id_str = str(session.session_id)

        # Agent index
        agent_key = self._agent_index_key(session.tenant_id, session.agent_id)
        await self._client.srem(agent_key, session_id_str)

        # Customer index
        if session.customer_profile_id:
            customer_key = self._customer_index_key(
                session.tenant_id, session.customer_profile_id
            )
            await self._client.srem(customer_key, session_id_str)

        # Channel index
        channel_key = self._channel_index_key(
            session.tenant_id, session.channel, session.user_channel_id
        )
        await self._client.delete(channel_key)

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
