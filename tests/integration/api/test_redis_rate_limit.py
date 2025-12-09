"""Integration tests for Redis-backed rate limiting."""

import os
import time
from uuid import uuid4

import pytest
import redis

from focal.api.middleware.rate_limit import (
    RedisRateLimiter,
    reset_rate_limiter,
)


@pytest.fixture(scope="module")
def redis_client():
    """Create a Redis client for testing.

    Assumes Redis is running on localhost:6379.
    """
    # Use port 6381 to match docker-compose.yml mapping, fallback to 6379 for local Redis
    port = int(os.environ.get("TEST_REDIS_PORT", "6379"))
    client = redis.Redis(host="localhost", port=port, db=15, decode_responses=True)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available for testing")
    yield client
    # Clean up test keys
    for key in client.scan_iter("ratelimit:test:*"):
        client.delete(key)
    client.close()


@pytest.fixture
def rate_limiter(redis_client):
    """Create a fresh Redis rate limiter for each test."""
    limiter = RedisRateLimiter(
        redis_client=redis_client,
        window_seconds=60,
        key_prefix="ratelimit:test:",
    )
    reset_rate_limiter()
    yield limiter
    reset_rate_limiter()


@pytest.fixture
def tenant_id():
    """Generate a unique tenant ID for each test."""
    return str(uuid4())


class TestRedisRateLimiter:
    """Tests for RedisRateLimiter implementation."""

    def test_first_request_allowed(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """First request should be allowed."""
        result = rate_limiter.check(tenant_id, limit=10)

        assert result.allowed is True
        assert result.limit == 10
        assert result.remaining == 9

    def test_remaining_decreases_with_requests(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """Remaining count should decrease with each request."""
        result1 = rate_limiter.check(tenant_id, limit=10)
        result2 = rate_limiter.check(tenant_id, limit=10)
        result3 = rate_limiter.check(tenant_id, limit=10)

        assert result1.remaining == 9
        assert result2.remaining == 8
        assert result3.remaining == 7

    def test_request_blocked_when_limit_exceeded(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """Request should be blocked when limit is exceeded."""
        # Use up all allowed requests
        for _ in range(5):
            result = rate_limiter.check(tenant_id, limit=5)
            assert result.allowed is True

        # Next request should be blocked
        result = rate_limiter.check(tenant_id, limit=5)
        assert result.allowed is False
        assert result.remaining == 0

    def test_different_tenants_have_separate_limits(
        self,
        rate_limiter: RedisRateLimiter,
    ) -> None:
        """Different tenants should have independent rate limits."""
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())

        # Exhaust tenant A's limit
        for _ in range(5):
            rate_limiter.check(tenant_a, limit=5)

        # Tenant B should still be allowed
        result = rate_limiter.check(tenant_b, limit=5)
        assert result.allowed is True
        assert result.remaining == 4

    def test_reset_clears_tenant_limit(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """Reset should clear a tenant's rate limit state."""
        # Use some requests
        for _ in range(3):
            rate_limiter.check(tenant_id, limit=10)

        # Reset
        rate_limiter.reset(tenant_id)

        # Should have full limit again
        result = rate_limiter.check(tenant_id, limit=10)
        assert result.remaining == 9

    def test_reset_at_is_set(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """Reset time should be set in response."""
        result = rate_limiter.check(tenant_id, limit=10)

        assert result.reset_at is not None
        # Reset time should be in the future
        assert result.reset_at.timestamp() > time.time()

    def test_limit_in_response_matches_input(
        self,
        rate_limiter: RedisRateLimiter,
        tenant_id: str,
    ) -> None:
        """Limit in response should match the input limit."""
        result = rate_limiter.check(tenant_id, limit=100)
        assert result.limit == 100

        result = rate_limiter.check(tenant_id, limit=50)
        assert result.limit == 50


class TestRedisRateLimiterSlidingWindow:
    """Tests for Redis sliding window behavior."""

    def test_window_expiration(
        self,
        redis_client,
        tenant_id: str,
    ) -> None:
        """Requests should expire after window period."""
        # Use a very short window for testing
        limiter = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=2,
            key_prefix="ratelimit:test:",
        )

        # Use up all requests
        for _ in range(3):
            limiter.check(tenant_id, limit=3)

        # Should be blocked
        result = limiter.check(tenant_id, limit=3)
        assert result.allowed is False

        # Wait for window to expire
        time.sleep(2.5)

        # Should be allowed again
        result = limiter.check(tenant_id, limit=3)
        assert result.allowed is True

    def test_requests_in_window_are_counted(
        self,
        redis_client,
        tenant_id: str,
    ) -> None:
        """Only requests within window should be counted."""
        limiter = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=2,
            key_prefix="ratelimit:test:",
        )

        # Make 2 requests
        limiter.check(tenant_id, limit=5)
        limiter.check(tenant_id, limit=5)

        # Wait for those to expire
        time.sleep(2.5)

        # New request should have full limit (minus 1)
        result = limiter.check(tenant_id, limit=5)
        assert result.remaining == 4


class TestRedisRateLimiterDistributed:
    """Tests for distributed rate limiting behavior."""

    def test_multiple_limiters_share_state(
        self,
        redis_client,
        tenant_id: str,
    ) -> None:
        """Multiple rate limiter instances should share state via Redis."""
        limiter_a = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=60,
            key_prefix="ratelimit:test:",
        )
        limiter_b = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=60,
            key_prefix="ratelimit:test:",
        )

        # Make requests from limiter A
        limiter_a.check(tenant_id, limit=10)
        limiter_a.check(tenant_id, limit=10)

        # Limiter B should see the same state
        result = limiter_b.check(tenant_id, limit=10)
        assert result.remaining == 7  # 10 - 3 requests

    def test_reset_from_one_limiter_affects_other(
        self,
        redis_client,
        tenant_id: str,
    ) -> None:
        """Reset from one limiter should affect state seen by others."""
        limiter_a = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=60,
            key_prefix="ratelimit:test:",
        )
        limiter_b = RedisRateLimiter(
            redis_client=redis_client,
            window_seconds=60,
            key_prefix="ratelimit:test:",
        )

        # Make requests from limiter A
        for _ in range(5):
            limiter_a.check(tenant_id, limit=10)

        # Reset from limiter B
        limiter_b.reset(tenant_id)

        # Limiter A should see cleared state
        result = limiter_a.check(tenant_id, limit=10)
        assert result.remaining == 9
