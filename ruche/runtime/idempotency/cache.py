"""Idempotency cache implementation.

Three-layer idempotency system for preventing duplicate operations:
- API layer (5min TTL): Prevent duplicate HTTP requests
- Beat layer (60s TTL): Prevent duplicate turn processing
- Tool layer (24hr TTL): Prevent duplicate business actions
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from redis.asyncio import Redis

from ruche.observability.logging import get_logger
from ruche.runtime.idempotency.models import (
    IdempotencyCheckResult,
    IdempotencyLayer,
    IdempotencyStatus,
)

logger = get_logger(__name__)

# TTL values per layer (in seconds)
LAYER_TTL = {
    IdempotencyLayer.API: 300,  # 5 minutes
    IdempotencyLayer.BEAT: 60,  # 60 seconds
    IdempotencyLayer.TOOL: 86400,  # 24 hours
}


class IdempotencyCache(ABC):
    """Abstract interface for idempotency cache."""

    @abstractmethod
    async def check(self, key: str, layer: IdempotencyLayer) -> IdempotencyCheckResult:
        """Check idempotency status for a key.

        Args:
            key: Idempotency key
            layer: Which layer (API, BEAT, TOOL)

        Returns:
            IdempotencyCheckResult with status and optional cached result
        """
        pass

    @abstractmethod
    async def mark_processing(self, key: str, layer: IdempotencyLayer) -> None:
        """Mark a key as currently processing.

        Args:
            key: Idempotency key
            layer: Which layer (API, BEAT, TOOL)
        """
        pass

    @abstractmethod
    async def mark_complete(
        self, key: str, layer: IdempotencyLayer, result: Any
    ) -> None:
        """Mark a key as completed with result.

        Args:
            key: Idempotency key
            layer: Which layer (API, BEAT, TOOL)
            result: Result to cache (will be JSON serialized)
        """
        pass


class RedisIdempotencyCache(IdempotencyCache):
    """Redis-backed idempotency cache.

    Key format: idem:{layer}:{key}
    Value format:
        - PROCESSING: "processing"
        - COMPLETE: {"result": ...}
    """

    def __init__(self, redis: Redis, key_prefix: str = "idem"):
        """Initialize Redis idempotency cache.

        Args:
            redis: Redis client instance
            key_prefix: Prefix for Redis keys
        """
        self._redis = redis
        self._key_prefix = key_prefix

    def _make_key(self, key: str, layer: IdempotencyLayer) -> str:
        """Build Redis key.

        Format: {prefix}:{layer}:{key}
        """
        return f"{self._key_prefix}:{layer.value}:{key}"

    async def check(self, key: str, layer: IdempotencyLayer) -> IdempotencyCheckResult:
        """Check idempotency status for a key.

        Returns:
            - NEW if key doesn't exist
            - PROCESSING if currently being processed
            - COMPLETE if finished with cached result
        """
        redis_key = self._make_key(key, layer)
        value = await self._redis.get(redis_key)

        if value is None:
            logger.debug(
                "idempotency_check_new",
                key=key,
                layer=layer.value,
            )
            return IdempotencyCheckResult(status=IdempotencyStatus.NEW)

        value_str = value.decode() if isinstance(value, bytes) else value

        if value_str == "processing":
            logger.debug(
                "idempotency_check_processing",
                key=key,
                layer=layer.value,
            )
            return IdempotencyCheckResult(status=IdempotencyStatus.PROCESSING)

        # Parse JSON result
        try:
            result_data = json.loads(value_str)
            logger.debug(
                "idempotency_check_complete",
                key=key,
                layer=layer.value,
            )
            return IdempotencyCheckResult(
                status=IdempotencyStatus.COMPLETE, cached_result=result_data["result"]
            )
        except (json.JSONDecodeError, KeyError):
            # Corrupted value, treat as new
            logger.warning(
                "idempotency_corrupted_value",
                key=key,
                layer=layer.value,
                value=value_str,
            )
            return IdempotencyCheckResult(status=IdempotencyStatus.NEW)

    async def mark_processing(self, key: str, layer: IdempotencyLayer) -> None:
        """Mark a key as currently processing.

        Uses SET with NX (only if not exists) and EX (expiry) for atomicity.
        """
        redis_key = self._make_key(key, layer)
        ttl = LAYER_TTL[layer]

        # SET with NX ensures we only set if key doesn't exist
        success = await self._redis.set(redis_key, "processing", nx=True, ex=ttl)

        if success:
            logger.info(
                "idempotency_marked_processing",
                key=key,
                layer=layer.value,
                ttl=ttl,
            )
        else:
            logger.debug(
                "idempotency_already_exists",
                key=key,
                layer=layer.value,
            )

    async def mark_complete(
        self, key: str, layer: IdempotencyLayer, result: Any
    ) -> None:
        """Mark a key as completed with result.

        Overwrites any existing value (including "processing").
        """
        redis_key = self._make_key(key, layer)
        ttl = LAYER_TTL[layer]

        # Store result as JSON
        value = json.dumps({"result": result})
        await self._redis.set(redis_key, value, ex=ttl)

        logger.info(
            "idempotency_marked_complete",
            key=key,
            layer=layer.value,
            ttl=ttl,
        )


class InMemoryIdempotencyCache(IdempotencyCache):
    """In-memory idempotency cache for testing.

    Does not implement TTL - entries persist until explicitly cleared.
    """

    def __init__(self):
        """Initialize in-memory cache."""
        self._cache: dict[tuple[str, IdempotencyLayer], tuple[IdempotencyStatus, Any]] = {}

    async def check(self, key: str, layer: IdempotencyLayer) -> IdempotencyCheckResult:
        """Check idempotency status."""
        cache_key = (key, layer)
        entry = self._cache.get(cache_key)

        if entry is None:
            return IdempotencyCheckResult(status=IdempotencyStatus.NEW)

        status, result = entry
        return IdempotencyCheckResult(status=status, cached_result=result)

    async def mark_processing(self, key: str, layer: IdempotencyLayer) -> None:
        """Mark as processing."""
        cache_key = (key, layer)
        if cache_key not in self._cache:
            self._cache[cache_key] = (IdempotencyStatus.PROCESSING, None)

    async def mark_complete(
        self, key: str, layer: IdempotencyLayer, result: Any
    ) -> None:
        """Mark as complete with result."""
        cache_key = (key, layer)
        self._cache[cache_key] = (IdempotencyStatus.COMPLETE, result)

    def clear(self) -> None:
        """Clear all cache entries (test utility)."""
        self._cache.clear()
