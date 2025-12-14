"""Unit tests for rate limiting middleware."""

import time
from datetime import datetime, timedelta

from ruche.api.middleware.rate_limit import (
    TIER_LIMITS,
    SlidingWindowRateLimiter,
    get_tenant_limit,
)


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter."""

    def test_allows_requests_under_limit(self) -> None:
        """Requests under the limit are allowed."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_id = "test-tenant"
        limit = 10

        for i in range(10):
            result = limiter.check(tenant_id, limit)
            assert result.allowed, f"Request {i + 1} should be allowed"
            assert result.remaining == limit - i - 1

    def test_blocks_requests_over_limit(self) -> None:
        """Requests over the limit are blocked."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_id = "test-tenant"
        limit = 5

        # Use up the limit
        for _ in range(5):
            result = limiter.check(tenant_id, limit)
            assert result.allowed

        # Next request should be blocked
        result = limiter.check(tenant_id, limit)
        assert not result.allowed
        assert result.remaining == 0

    def test_limit_resets_after_window(self) -> None:
        """Limit resets after the window expires."""
        # Use a very short window for testing
        limiter = SlidingWindowRateLimiter(window_seconds=1)
        tenant_id = "test-tenant"
        limit = 2

        # Use up the limit
        limiter.check(tenant_id, limit)
        limiter.check(tenant_id, limit)

        result = limiter.check(tenant_id, limit)
        assert not result.allowed

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        result = limiter.check(tenant_id, limit)
        assert result.allowed

    def test_separate_limits_per_tenant(self) -> None:
        """Each tenant has their own limit."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_a = "tenant-a"
        tenant_b = "tenant-b"
        limit = 3

        # Use up tenant A's limit
        for _ in range(3):
            limiter.check(tenant_a, limit)

        result = limiter.check(tenant_a, limit)
        assert not result.allowed

        # Tenant B should still have capacity
        result = limiter.check(tenant_b, limit)
        assert result.allowed
        assert result.remaining == 2

    def test_reset_clears_tenant_state(self) -> None:
        """Reset clears rate limit state for a tenant."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_id = "test-tenant"
        limit = 3

        # Use up the limit
        for _ in range(3):
            limiter.check(tenant_id, limit)

        result = limiter.check(tenant_id, limit)
        assert not result.allowed

        # Reset
        limiter.reset(tenant_id)

        # Should be allowed again
        result = limiter.check(tenant_id, limit)
        assert result.allowed
        assert result.remaining == 2

    def test_result_includes_reset_time(self) -> None:
        """Result includes when the limit resets."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_id = "test-tenant"
        limit = 5

        result = limiter.check(tenant_id, limit)

        # Reset time should be approximately 60 seconds from now
        now = datetime.now()
        assert result.reset_at > now
        assert result.reset_at < now + timedelta(seconds=65)

    def test_result_includes_limit_info(self) -> None:
        """Result includes limit and remaining count."""
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        tenant_id = "test-tenant"
        limit = 10

        result = limiter.check(tenant_id, limit)

        assert result.limit == 10
        assert result.remaining == 9


class TestTierLimits:
    """Tests for tier-based rate limits."""

    def test_free_tier_limit(self) -> None:
        """Free tier has 60 requests/minute."""
        assert get_tenant_limit("free") == 60

    def test_pro_tier_limit(self) -> None:
        """Pro tier has 600 requests/minute."""
        assert get_tenant_limit("pro") == 600

    def test_enterprise_tier_limit(self) -> None:
        """Enterprise tier has 6000 requests/minute."""
        assert get_tenant_limit("enterprise") == 6000

    def test_tier_limits_constant(self) -> None:
        """Tier limits are correctly defined."""
        assert TIER_LIMITS["free"] == 60
        assert TIER_LIMITS["pro"] == 600
        assert TIER_LIMITS["enterprise"] == 6000
