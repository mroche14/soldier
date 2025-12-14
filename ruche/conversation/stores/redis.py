"""Redis implementation of SessionStore with two-tier caching.

Implements hot cache (30 min TTL) + persistent tier (7 days TTL)
for session storage with automatic tier promotion on access.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from pydantic import BaseModel

from ruche.alignment.migration.models import ScopeFilter
from ruche.config.models.storage import RedisSessionConfig
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.store import SessionStore
from ruche.db.errors import ConnectionError
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
    """Redis implementation of SessionStore with two-tier caching.

    Uses hot cache for active sessions and persistent tier for
    inactive sessions. Automatically promotes sessions to hot
    tier on access.

    Key structure:
    - session:hot:{session_id} - Hot cache (30 min TTL)
    - session:persist:{session_id} - Persistent tier (7 days TTL)
    - session:index:agent:{tenant_id}:{agent_id} - Session IDs by agent
    - session:index:customer:{tenant_id}:{profile_id} - Session IDs by customer
    - session:index:channel:{tenant_id}:{channel}:{user_id} - Session by channel
    """

    def __init__(
        self,
        client: redis.Redis,
        config: RedisSessionConfig | None = None,
    ) -> None:
        """Initialize Redis session store.

        Args:
            client: Redis client instance
            config: Redis session configuration (uses defaults if not provided)
        """
        self._client = client
        self._config = config or RedisSessionConfig()
        self._prefix = self._config.key_prefix

    def _hot_key(self, session_id: UUID) -> str:
        """Get hot cache key for session."""
        return f"{self._prefix}:hot:{session_id}"

    def _persist_key(self, session_id: UUID) -> str:
        """Get persistent tier key for session."""
        return f"{self._prefix}:persist:{session_id}"

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

        Checks hot tier first, then persistent tier.
        Auto-promotes to hot tier if found in persistent.
        """
        try:
            # Try hot tier first
            hot_key = self._hot_key(session_id)
            data = await self._client.get(hot_key)

            if data:
                logger.debug(
                    "session_retrieved_hot",
                    session_id=str(session_id),
                )
                return self._deserialize_session(data)

            # Fall back to persistent tier
            persist_key = self._persist_key(session_id)
            data = await self._client.get(persist_key)

            if data:
                logger.debug(
                    "session_retrieved_persistent",
                    session_id=str(session_id),
                )
                session = self._deserialize_session(data)
                # Auto-promote to hot tier
                await self.promote_to_hot(session)
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
        """Save a session to hot tier.

        Updates last_activity_at and writes to hot tier with TTL.
        Also updates all indexes.
        """
        try:
            session.last_activity_at = datetime.now(UTC)
            data = self._serialize_session(session)

            # Write to hot tier with TTL
            hot_key = self._hot_key(session.session_id)
            await self._client.setex(
                hot_key,
                self._config.hot_ttl_seconds,
                data,
            )

            # Update indexes
            await self._update_indexes(session)

            logger.info(
                "session_saved",
                session_id=str(session.session_id),
                tenant_id=str(session.tenant_id),
                agent_id=str(session.agent_id),
            )

            return session.session_id

        except redis.RedisError as e:
            logger.error(
                "redis_save_error",
                session_id=str(session.session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save session: {e}", cause=e) from e

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session from both tiers.

        Also removes from all indexes.
        """
        try:
            # Get session first to clean up indexes
            session = await self.get(session_id)

            # Delete from both tiers
            hot_key = self._hot_key(session_id)
            persist_key = self._persist_key(session_id)

            deleted_count = await self._client.delete(hot_key, persist_key)

            # Clean up indexes if session existed
            if session:
                await self._remove_from_indexes(session)

            logger.info(
                "session_deleted",
                session_id=str(session_id),
                deleted=deleted_count > 0,
            )

            return deleted_count > 0

        except redis.RedisError as e:
            logger.error(
                "redis_delete_error",
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
        Scans all sessions - consider using a dedicated index for production.
        """
        try:
            # Get all keys matching session pattern
            # This is not optimal for large datasets - production should use a dedicated index
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

            # Also check persistent tier
            pattern = f"{self._prefix}:persist:*"
            async for key in self._client.scan_iter(match=pattern):
                data = await self._client.get(key)
                if not data:
                    continue

                session = self._deserialize_session(data)

                if session.tenant_id != tenant_id:
                    continue
                if session.active_scenario_id != scenario_id:
                    continue
                if session.active_scenario_version != scenario_version:
                    continue
                if session.status != SessionStatus.ACTIVE:
                    continue

                current_step_hash = None
                if session.step_history:
                    last_visit = session.step_history[-1]
                    current_step_hash = last_visit.step_content_hash

                if current_step_hash != step_content_hash:
                    continue

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

    async def promote_to_hot(self, session: Session) -> None:
        """Promote a session from persistent to hot tier.

        Writes to hot tier with TTL and removes from persistent.
        """
        try:
            data = self._serialize_session(session)

            hot_key = self._hot_key(session.session_id)
            persist_key = self._persist_key(session.session_id)

            # Write to hot tier
            await self._client.setex(
                hot_key,
                self._config.hot_ttl_seconds,
                data,
            )

            # Remove from persistent tier
            await self._client.delete(persist_key)

            logger.debug(
                "session_promoted_to_hot",
                session_id=str(session.session_id),
            )

        except redis.RedisError as e:
            logger.error(
                "redis_promote_error",
                session_id=str(session.session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to promote session: {e}", cause=e) from e

    async def demote_to_persistent(self, session: Session) -> None:
        """Demote a session from hot to persistent tier.

        Writes to persistent tier with TTL and removes from hot.
        """
        try:
            data = self._serialize_session(session)

            hot_key = self._hot_key(session.session_id)
            persist_key = self._persist_key(session.session_id)

            # Write to persistent tier
            await self._client.setex(
                persist_key,
                self._config.persist_ttl_seconds,
                data,
            )

            # Remove from hot tier
            await self._client.delete(hot_key)

            logger.debug(
                "session_demoted_to_persistent",
                session_id=str(session.session_id),
            )

        except redis.RedisError as e:
            logger.error(
                "redis_demote_error",
                session_id=str(session.session_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to demote session: {e}", cause=e) from e

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
