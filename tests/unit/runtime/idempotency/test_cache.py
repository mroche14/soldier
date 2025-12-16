"""Unit tests for IdempotencyCache implementations."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ruche.runtime.idempotency.cache import (
    LAYER_TTL,
    InMemoryIdempotencyCache,
    RedisIdempotencyCache,
)
from ruche.runtime.idempotency.models import (
    IdempotencyCheckResult,
    IdempotencyLayer,
    IdempotencyStatus,
)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def redis_cache(mock_redis):
    """Create Redis idempotency cache with mock."""
    return RedisIdempotencyCache(redis=mock_redis)


@pytest.fixture
def inmemory_cache():
    """Create in-memory idempotency cache."""
    return InMemoryIdempotencyCache()


class TestLayerTTL:
    """Tests for TTL constants."""

    def test_api_layer_ttl_is_300_seconds(self) -> None:
        """API layer has 5 minute TTL."""
        assert LAYER_TTL[IdempotencyLayer.API] == 300

    def test_beat_layer_ttl_is_60_seconds(self) -> None:
        """Beat layer has 60 second TTL."""
        assert LAYER_TTL[IdempotencyLayer.BEAT] == 60

    def test_tool_layer_ttl_is_24_hours(self) -> None:
        """Tool layer has 24 hour TTL."""
        assert LAYER_TTL[IdempotencyLayer.TOOL] == 86400


class TestRedisIdempotencyCacheKeyFormat:
    """Tests for Redis key formatting."""

    def test_make_key_api_layer(self, redis_cache: RedisIdempotencyCache) -> None:
        """API layer key format is correct."""
        key = redis_cache._make_key("test-key", IdempotencyLayer.API)
        assert key == "idem:api:test-key"

    def test_make_key_beat_layer(self, redis_cache: RedisIdempotencyCache) -> None:
        """Beat layer key format is correct."""
        key = redis_cache._make_key("test-key", IdempotencyLayer.BEAT)
        assert key == "idem:beat:test-key"

    def test_make_key_tool_layer(self, redis_cache: RedisIdempotencyCache) -> None:
        """Tool layer key format is correct."""
        key = redis_cache._make_key("test-key", IdempotencyLayer.TOOL)
        assert key == "idem:tool:test-key"

    def test_make_key_custom_prefix(self, mock_redis) -> None:
        """Custom key prefix is used."""
        cache = RedisIdempotencyCache(redis=mock_redis, key_prefix="custom")
        key = cache._make_key("test-key", IdempotencyLayer.API)
        assert key == "custom:api:test-key"


class TestRedisIdempotencyCacheCheck:
    """Tests for Redis idempotency check."""

    async def test_check_returns_new_when_key_missing(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Returns NEW status when key doesn't exist."""
        mock_redis.get.return_value = None

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.NEW
        assert result.cached_result is None

    async def test_check_returns_processing_when_marked(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Returns PROCESSING status when key has 'processing' value."""
        mock_redis.get.return_value = b"processing"

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.PROCESSING
        assert result.cached_result is None

    async def test_check_returns_complete_with_result(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Returns COMPLETE status with cached result."""
        cached_data = json.dumps({"result": {"status": "success", "data": 123}})
        mock_redis.get.return_value = cached_data.encode()

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.COMPLETE
        assert result.cached_result == {"status": "success", "data": 123}

    async def test_check_handles_string_value(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Handles string values from Redis."""
        mock_redis.get.return_value = "processing"

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.PROCESSING

    async def test_check_handles_corrupted_json(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Returns NEW status for corrupted JSON."""
        mock_redis.get.return_value = b"invalid json {"

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.NEW

    async def test_check_handles_missing_result_key(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Returns NEW status when JSON lacks 'result' key."""
        mock_redis.get.return_value = b'{"other": "data"}'

        result = await redis_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.NEW


class TestRedisIdempotencyCacheMarkProcessing:
    """Tests for marking keys as processing."""

    async def test_mark_processing_sets_with_ttl(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Sets Redis key with correct TTL."""
        mock_redis.set.return_value = True

        await redis_cache.mark_processing("test-key", IdempotencyLayer.API)

        mock_redis.set.assert_called_once_with(
            "idem:api:test-key",
            "processing",
            nx=True,
            ex=300,  # API layer TTL
        )

    async def test_mark_processing_beat_layer_ttl(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Beat layer uses correct TTL."""
        await redis_cache.mark_processing("test-key", IdempotencyLayer.BEAT)

        mock_redis.set.assert_called_once_with(
            "idem:beat:test-key",
            "processing",
            nx=True,
            ex=60,  # Beat layer TTL
        )

    async def test_mark_processing_tool_layer_ttl(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Tool layer uses correct TTL."""
        await redis_cache.mark_processing("test-key", IdempotencyLayer.TOOL)

        mock_redis.set.assert_called_once_with(
            "idem:tool:test-key",
            "processing",
            nx=True,
            ex=86400,  # Tool layer TTL
        )

    async def test_mark_processing_when_key_exists(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Handles case when key already exists."""
        mock_redis.set.return_value = False

        await redis_cache.mark_processing("test-key", IdempotencyLayer.API)


class TestRedisIdempotencyCacheMarkComplete:
    """Tests for marking keys as complete."""

    async def test_mark_complete_stores_result(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Stores result as JSON with TTL."""
        result_data = {"status": "success", "data": 123}

        await redis_cache.mark_complete("test-key", IdempotencyLayer.API, result_data)

        expected_value = json.dumps({"result": result_data})
        mock_redis.set.assert_called_once_with(
            "idem:api:test-key",
            expected_value,
            ex=300,
        )

    async def test_mark_complete_overwrites_existing(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Overwrites existing value (no NX flag)."""
        await redis_cache.mark_complete("test-key", IdempotencyLayer.API, {"data": 1})

        call_kwargs = mock_redis.set.call_args[1]
        assert "nx" not in call_kwargs

    async def test_mark_complete_with_none_result(
        self, redis_cache: RedisIdempotencyCache, mock_redis
    ) -> None:
        """Handles None result."""
        await redis_cache.mark_complete("test-key", IdempotencyLayer.API, None)

        expected_value = json.dumps({"result": None})
        mock_redis.set.assert_called_once_with(
            "idem:api:test-key",
            expected_value,
            ex=300,
        )


class TestInMemoryIdempotencyCacheCheck:
    """Tests for in-memory cache check."""

    async def test_check_returns_new_when_missing(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Returns NEW for missing key."""
        result = await inmemory_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.NEW
        assert result.cached_result is None

    async def test_check_returns_processing(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Returns PROCESSING for processing key."""
        await inmemory_cache.mark_processing("test-key", IdempotencyLayer.API)

        result = await inmemory_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.PROCESSING
        assert result.cached_result is None

    async def test_check_returns_complete_with_result(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Returns COMPLETE with cached result."""
        result_data = {"status": "success"}
        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.API, result_data)

        result = await inmemory_cache.check("test-key", IdempotencyLayer.API)

        assert result.status == IdempotencyStatus.COMPLETE
        assert result.cached_result == result_data


class TestInMemoryIdempotencyCacheMarkProcessing:
    """Tests for in-memory mark processing."""

    async def test_mark_processing_sets_status(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Sets processing status."""
        await inmemory_cache.mark_processing("test-key", IdempotencyLayer.API)

        cache_key = ("test-key", IdempotencyLayer.API)
        assert cache_key in inmemory_cache._cache
        status, result = inmemory_cache._cache[cache_key]
        assert status == IdempotencyStatus.PROCESSING
        assert result is None

    async def test_mark_processing_only_if_not_exists(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Doesn't overwrite existing entry."""
        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.API, {"data": 1})
        await inmemory_cache.mark_processing("test-key", IdempotencyLayer.API)

        result = await inmemory_cache.check("test-key", IdempotencyLayer.API)
        assert result.status == IdempotencyStatus.COMPLETE


class TestInMemoryIdempotencyCacheMarkComplete:
    """Tests for in-memory mark complete."""

    async def test_mark_complete_stores_result(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Stores result and status."""
        result_data = {"status": "success", "value": 123}

        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.API, result_data)

        cache_key = ("test-key", IdempotencyLayer.API)
        status, result = inmemory_cache._cache[cache_key]
        assert status == IdempotencyStatus.COMPLETE
        assert result == result_data

    async def test_mark_complete_overwrites_processing(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Overwrites processing status."""
        await inmemory_cache.mark_processing("test-key", IdempotencyLayer.API)
        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.API, {"done": True})

        result = await inmemory_cache.check("test-key", IdempotencyLayer.API)
        assert result.status == IdempotencyStatus.COMPLETE
        assert result.cached_result == {"done": True}


class TestInMemoryIdempotencyCacheClear:
    """Tests for clearing in-memory cache."""

    async def test_clear_removes_all_entries(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Clear removes all cached entries."""
        await inmemory_cache.mark_complete("key1", IdempotencyLayer.API, {"a": 1})
        await inmemory_cache.mark_complete("key2", IdempotencyLayer.BEAT, {"b": 2})

        inmemory_cache.clear()

        result1 = await inmemory_cache.check("key1", IdempotencyLayer.API)
        result2 = await inmemory_cache.check("key2", IdempotencyLayer.BEAT)

        assert result1.status == IdempotencyStatus.NEW
        assert result2.status == IdempotencyStatus.NEW


class TestInMemoryIdempotencyCacheLayerIsolation:
    """Tests for layer isolation in in-memory cache."""

    async def test_different_layers_separate_entries(
        self, inmemory_cache: InMemoryIdempotencyCache
    ) -> None:
        """Same key in different layers are separate."""
        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.API, {"api": True})
        await inmemory_cache.mark_complete("test-key", IdempotencyLayer.BEAT, {"beat": True})

        api_result = await inmemory_cache.check("test-key", IdempotencyLayer.API)
        beat_result = await inmemory_cache.check("test-key", IdempotencyLayer.BEAT)

        assert api_result.cached_result == {"api": True}
        assert beat_result.cached_result == {"beat": True}
