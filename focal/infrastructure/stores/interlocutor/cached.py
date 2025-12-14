"""InterlocutorDataStore cache layer wrapper with Redis caching.

Implements write-through caching with configurable TTL.
Falls back to backend on Redis errors when configured.
"""

from typing import Any
from uuid import UUID

import redis.asyncio as redis

from focal.config.models.storage import RedisProfileCacheConfig
from focal.conversation.models import Channel
from focal.observability.logging import get_logger
from focal.observability.metrics import (
    PROFILE_CACHE_ERRORS,
    PROFILE_CACHE_HITS,
    PROFILE_CACHE_INVALIDATIONS,
    PROFILE_CACHE_MISSES,
)
from focal.customer_data.enums import ItemStatus
from focal.customer_data.models import (
    ChannelIdentity,
    CustomerDataStore,
    ProfileAsset,
    VariableEntry,
    CustomerDataField,
    ScenarioFieldRequirement,
)
from focal.customer_data.store import InterlocutorDataStore

logger = get_logger(__name__)


class CustomerDataStoreCacheLayer(InterlocutorDataStore):
    """InterlocutorDataStore wrapper with Redis caching.

    Caches read operations with configurable TTL.
    Invalidates cache on write operations.
    Falls back to backend on Redis errors when configured.

    Cache key patterns:
    - profile:{tenant_id}:{profile_id} - Full profile
    - profile:{tenant_id}:customer:{customer_id} - Profile by customer ID
    - profile:{tenant_id}:channel:{channel}:{user_id} - Profile by channel
    - profile:field_def:{tenant_id}:{agent_id} - Field definitions
    - profile:scenario_req:{tenant_id}:{scenario_id} - Scenario requirements
    """

    def __init__(
        self,
        backend: InterlocutorDataStore,
        redis_client: redis.Redis,
        config: RedisProfileCacheConfig | None = None,
    ) -> None:
        """Initialize cached profile store.

        Args:
            backend: Underlying InterlocutorDataStore (usually PostgresInterlocutorDataStore)
            redis_client: Redis client instance
            config: Cache configuration (uses defaults if not provided)
        """
        self._backend = backend
        self._redis = redis_client
        self._config = config or RedisProfileCacheConfig()
        self._prefix = self._config.key_prefix

    # =========================================================================
    # CACHE KEY HELPERS
    # =========================================================================

    def _profile_key(self, tenant_id: UUID, profile_id: UUID) -> str:
        """Get cache key for profile by ID."""
        return f"{self._prefix}:{tenant_id}:{profile_id}"

    def _customer_key(self, tenant_id: UUID, customer_id: UUID) -> str:
        """Get cache key for profile by customer ID."""
        return f"{self._prefix}:{tenant_id}:customer:{customer_id}"

    def _channel_key(
        self, tenant_id: UUID, channel: Channel, user_id: str
    ) -> str:
        """Get cache key for profile by channel identity."""
        return f"{self._prefix}:{tenant_id}:channel:{channel.value}:{user_id}"

    def _field_def_key(self, tenant_id: UUID, agent_id: UUID) -> str:
        """Get cache key for field definitions."""
        return f"{self._prefix}:field_def:{tenant_id}:{agent_id}"

    def _scenario_req_key(self, tenant_id: UUID, scenario_id: UUID) -> str:
        """Get cache key for scenario requirements."""
        return f"{self._prefix}:scenario_req:{tenant_id}:{scenario_id}"

    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================

    async def _get_cached(
        self, key: str, tenant_id: UUID, key_type: str
    ) -> str | None:
        """Get value from cache."""
        if not self._config.enabled:
            return None

        try:
            data = await self._redis.get(key)
            if data:
                PROFILE_CACHE_HITS.labels(
                    tenant_id=str(tenant_id), cache_key_type=key_type
                ).inc()
                logger.debug(
                    "profile_cache_hit",
                    key=key,
                    tenant_id=str(tenant_id),
                )
            else:
                PROFILE_CACHE_MISSES.labels(
                    tenant_id=str(tenant_id), cache_key_type=key_type
                ).inc()
                logger.debug(
                    "profile_cache_miss",
                    key=key,
                    tenant_id=str(tenant_id),
                )
            return data
        except redis.RedisError as e:
            PROFILE_CACHE_ERRORS.labels(
                tenant_id=str(tenant_id), operation="get"
            ).inc()
            logger.warning(
                "profile_cache_get_error",
                key=key,
                error=str(e),
            )
            if self._config.fallback_on_error:
                return None
            raise

    async def _set_cached(
        self, key: str, data: str, tenant_id: UUID
    ) -> None:
        """Set value in cache with TTL."""
        if not self._config.enabled:
            return

        try:
            await self._redis.setex(key, self._config.ttl_seconds, data)
            logger.debug(
                "profile_cache_set",
                key=key,
                ttl=self._config.ttl_seconds,
            )
        except redis.RedisError as e:
            PROFILE_CACHE_ERRORS.labels(
                tenant_id=str(tenant_id), operation="set"
            ).inc()
            logger.warning(
                "profile_cache_set_error",
                key=key,
                error=str(e),
            )
            if not self._config.fallback_on_error:
                raise

    async def _invalidate(
        self, keys: list[str], tenant_id: UUID, operation: str
    ) -> None:
        """Invalidate cache keys."""
        if not self._config.enabled or not keys:
            return

        try:
            await self._redis.delete(*keys)
            PROFILE_CACHE_INVALIDATIONS.labels(
                tenant_id=str(tenant_id), operation=operation
            ).inc()
            logger.debug(
                "profile_cache_invalidated",
                keys=keys,
                operation=operation,
            )
        except redis.RedisError as e:
            PROFILE_CACHE_ERRORS.labels(
                tenant_id=str(tenant_id), operation="invalidate"
            ).inc()
            logger.warning(
                "profile_cache_invalidate_error",
                keys=keys,
                error=str(e),
            )
            if not self._config.fallback_on_error:
                raise

    async def _invalidate_profile(
        self, tenant_id: UUID, profile: CustomerDataStore, operation: str
    ) -> None:
        """Invalidate all cache keys for a profile."""
        keys = [
            self._profile_key(tenant_id, profile.id),
            self._customer_key(tenant_id, profile.customer_id),
        ]
        # Add channel keys
        for identity in profile.channel_identities:
            keys.append(
                self._channel_key(tenant_id, identity.channel, identity.channel_user_id)
            )
        await self._invalidate(keys, tenant_id, operation)

    # =========================================================================
    # PROFILE CRUD (Cached)
    # =========================================================================

    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by customer ID with caching."""
        # Skip cache if history requested (too complex to cache)
        if include_history:
            return await self._backend.get_by_customer_id(
                tenant_id, customer_id, include_history=True
            )

        key = self._customer_key(tenant_id, customer_id)
        cached = await self._get_cached(key, tenant_id, "customer")

        if cached:
            return CustomerDataStore.model_validate_json(cached)

        profile = await self._backend.get_by_customer_id(
            tenant_id, customer_id, include_history=False
        )

        if profile:
            await self._set_cached(key, profile.model_dump_json(), tenant_id)
            # Also cache by profile_id
            profile_key = self._profile_key(tenant_id, profile.id)
            await self._set_cached(profile_key, profile.model_dump_json(), tenant_id)

        return profile

    async def get_by_id(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by ID with caching."""
        if include_history:
            return await self._backend.get_by_id(
                tenant_id, profile_id, include_history=True
            )

        key = self._profile_key(tenant_id, profile_id)
        cached = await self._get_cached(key, tenant_id, "profile")

        if cached:
            return CustomerDataStore.model_validate_json(cached)

        profile = await self._backend.get_by_id(
            tenant_id, profile_id, include_history=False
        )

        if profile:
            await self._set_cached(key, profile.model_dump_json(), tenant_id)

        return profile

    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
        *,
        include_history: bool = False,
    ) -> CustomerDataStore | None:
        """Get profile by channel identity with caching."""
        if include_history:
            return await self._backend.get_by_channel_identity(
                tenant_id, channel, channel_user_id, include_history=True
            )

        key = self._channel_key(tenant_id, channel, channel_user_id)
        cached = await self._get_cached(key, tenant_id, "channel")

        if cached:
            return CustomerDataStore.model_validate_json(cached)

        profile = await self._backend.get_by_channel_identity(
            tenant_id, channel, channel_user_id, include_history=False
        )

        if profile:
            await self._set_cached(key, profile.model_dump_json(), tenant_id)
            # Also cache by profile_id
            profile_key = self._profile_key(tenant_id, profile.id)
            await self._set_cached(profile_key, profile.model_dump_json(), tenant_id)

        return profile

    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerDataStore:
        """Get or create profile (invalidates cache on create)."""
        # Try cached get first
        profile = await self.get_by_channel_identity(
            tenant_id, channel, channel_user_id
        )
        if profile:
            return profile

        # Create via backend
        profile = await self._backend.get_or_create(
            tenant_id, channel, channel_user_id
        )

        # Cache the new profile
        key = self._profile_key(tenant_id, profile.id)
        await self._set_cached(key, profile.model_dump_json(), tenant_id)

        channel_key = self._channel_key(tenant_id, channel, channel_user_id)
        await self._set_cached(channel_key, profile.model_dump_json(), tenant_id)

        return profile

    async def save(self, profile: CustomerDataStore) -> UUID:
        """Save profile and invalidate cache."""
        result = await self._backend.save(profile)
        await self._invalidate_profile(profile.tenant_id, profile, "save")
        return result

    async def delete(self, tenant_id: UUID, profile_id: UUID) -> bool:
        """Delete profile and invalidate cache."""
        # Get profile first to invalidate all keys
        profile = await self._backend.get_by_id(tenant_id, profile_id)
        if profile:
            await self._invalidate_profile(tenant_id, profile, "delete")

        return await self._backend.delete(tenant_id, profile_id)

    # =========================================================================
    # FIELD OPERATIONS (Write-through invalidation)
    # =========================================================================

    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: VariableEntry,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update field and invalidate profile cache."""
        result = await self._backend.update_field(
            tenant_id, profile_id, field, supersede_existing=supersede_existing
        )
        # Invalidate profile cache
        key = self._profile_key(tenant_id, profile_id)
        await self._invalidate([key], tenant_id, "update_field")
        return result

    async def get_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> VariableEntry | None:
        """Get field (no caching - use get_by_id for cached profile)."""
        return await self._backend.get_field(
            tenant_id, profile_id, field_name, status=status
        )

    async def get_field_history(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
    ) -> list[VariableEntry]:
        """Get field history (no caching)."""
        return await self._backend.get_field_history(
            tenant_id, profile_id, field_name
        )

    async def expire_stale_fields(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Expire stale fields and invalidate cache."""
        result = await self._backend.expire_stale_fields(tenant_id, profile_id)
        if profile_id:
            key = self._profile_key(tenant_id, profile_id)
            await self._invalidate([key], tenant_id, "expire_fields")
        return result

    async def mark_orphaned_items(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark orphaned items and invalidate cache."""
        result = await self._backend.mark_orphaned_items(tenant_id, profile_id)
        if profile_id:
            key = self._profile_key(tenant_id, profile_id)
            await self._invalidate([key], tenant_id, "mark_orphaned")
        return result

    # =========================================================================
    # ASSET OPERATIONS (Write-through invalidation)
    # =========================================================================

    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
        *,
        supersede_existing: bool = False,
    ) -> UUID:
        """Add asset and invalidate profile cache."""
        result = await self._backend.add_asset(
            tenant_id, profile_id, asset, supersede_existing=supersede_existing
        )
        key = self._profile_key(tenant_id, profile_id)
        await self._invalidate([key], tenant_id, "add_asset")
        return result

    async def get_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_id: UUID,
    ) -> ProfileAsset | None:
        """Get asset (no caching)."""
        return await self._backend.get_asset(tenant_id, profile_id, asset_id)

    async def get_asset_by_name(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileAsset | None:
        """Get asset by name (no caching)."""
        return await self._backend.get_asset_by_name(
            tenant_id, profile_id, asset_name, status=status
        )

    # =========================================================================
    # LINEAGE OPERATIONS (No caching - traversal operations)
    # =========================================================================

    async def get_derivation_chain(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> list[dict[str, Any]]:
        """Get derivation chain (no caching)."""
        return await self._backend.get_derivation_chain(
            tenant_id, item_id, item_type
        )

    async def get_derived_items(
        self,
        tenant_id: UUID,
        source_item_id: UUID,
    ) -> dict[str, list[Any]]:
        """Get derived items (no caching)."""
        return await self._backend.get_derived_items(tenant_id, source_item_id)

    async def check_has_dependents(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Check for dependents (no caching)."""
        return await self._backend.check_has_dependents(tenant_id, item_id)

    # =========================================================================
    # CHANNEL OPERATIONS (Write-through invalidation)
    # =========================================================================

    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        identity: ChannelIdentity,
    ) -> bool:
        """Link channel and invalidate cache."""
        result = await self._backend.link_channel(tenant_id, profile_id, identity)
        if result:
            key = self._profile_key(tenant_id, profile_id)
            await self._invalidate([key], tenant_id, "link_channel")
        return result

    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_profile_id: UUID,
        target_profile_id: UUID,
    ) -> bool:
        """Merge profiles and invalidate both caches."""
        # Get both profiles for full invalidation
        source = await self._backend.get_by_id(tenant_id, source_profile_id)
        target = await self._backend.get_by_id(tenant_id, target_profile_id)

        result = await self._backend.merge_profiles(
            tenant_id, source_profile_id, target_profile_id
        )

        if result:
            if source:
                await self._invalidate_profile(tenant_id, source, "merge_source")
            if target:
                await self._invalidate_profile(tenant_id, target, "merge_target")

        return result

    # =========================================================================
    # SCHEMA OPERATIONS (Cached)
    # =========================================================================

    async def get_field_definitions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[CustomerDataField]:
        """Get field definitions with caching."""
        # Only cache when getting all enabled
        if not enabled_only:
            return await self._backend.get_field_definitions(
                tenant_id, agent_id, enabled_only=False
            )

        key = self._field_def_key(tenant_id, agent_id)
        cached = await self._get_cached(key, tenant_id, "field_definitions")

        if cached:
            import json
            data = json.loads(cached)
            return [CustomerDataField.model_validate(d) for d in data]

        definitions = await self._backend.get_field_definitions(
            tenant_id, agent_id, enabled_only=True
        )

        if definitions:
            import json
            data = json.dumps([d.model_dump(mode="json") for d in definitions])
            await self._set_cached(key, data, tenant_id)

        return definitions

    async def get_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> CustomerDataField | None:
        """Get specific field definition (uses cached list)."""
        definitions = await self.get_field_definitions(tenant_id, agent_id)
        for d in definitions:
            if d.name == field_name:
                return d
        return None

    async def save_field_definition(
        self,
        definition: CustomerDataField,
    ) -> UUID:
        """Save field definition and invalidate cache."""
        result = await self._backend.save_field_definition(definition)
        key = self._field_def_key(definition.tenant_id, definition.agent_id)
        await self._invalidate([key], definition.tenant_id, "save_field_definition")
        return result

    async def delete_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> bool:
        """Delete field definition and invalidate cache."""
        result = await self._backend.delete_field_definition(
            tenant_id, agent_id, field_name
        )
        if result:
            key = self._field_def_key(tenant_id, agent_id)
            await self._invalidate([key], tenant_id, "delete_field_definition")
        return result

    # =========================================================================
    # SCENARIO REQUIREMENTS (Cached)
    # =========================================================================

    async def get_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Get scenario requirements with caching."""
        # Only cache when getting all (no step filter)
        if step_id is not None:
            return await self._backend.get_scenario_requirements(
                tenant_id, scenario_id, step_id=step_id
            )

        key = self._scenario_req_key(tenant_id, scenario_id)
        cached = await self._get_cached(key, tenant_id, "scenario_requirements")

        if cached:
            import json
            data = json.loads(cached)
            return [ScenarioFieldRequirement.model_validate(d) for d in data]

        requirements = await self._backend.get_scenario_requirements(
            tenant_id, scenario_id
        )

        if requirements:
            import json
            data = json.dumps([r.model_dump(mode="json") for r in requirements])
            await self._set_cached(key, data, tenant_id)

        return requirements

    async def save_scenario_requirement(
        self,
        requirement: ScenarioFieldRequirement,
    ) -> UUID:
        """Save scenario requirement and invalidate cache."""
        result = await self._backend.save_scenario_requirement(requirement)
        key = self._scenario_req_key(requirement.tenant_id, requirement.scenario_id)
        await self._invalidate([key], requirement.tenant_id, "save_scenario_requirement")
        return result

    async def delete_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> int:
        """Delete scenario requirements and invalidate cache."""
        result = await self._backend.delete_scenario_requirements(
            tenant_id, scenario_id, step_id=step_id
        )
        key = self._scenario_req_key(tenant_id, scenario_id)
        await self._invalidate([key], tenant_id, "delete_scenario_requirements")
        return result

    async def get_missing_fields(
        self,
        tenant_id: UUID,
        profile: CustomerDataStore,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> list[ScenarioFieldRequirement]:
        """Get missing fields (no caching - depends on profile state)."""
        return await self._backend.get_missing_fields(
            tenant_id, profile, scenario_id,
            step_id=step_id, required_level=required_level
        )

    # =========================================================================
    # HEALTH CHECK
    # =========================================================================

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self._redis.ping()
            logger.debug("profile_cache_health_check_passed")
            return True
        except redis.RedisError as e:
            logger.warning(
                "profile_cache_health_check_failed",
                error=str(e),
            )
            return False
