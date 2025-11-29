"""Rate limiting middleware for per-tenant request limits."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from soldier.api.exceptions import RateLimitExceededError
from soldier.api.models.context import RateLimitResult, TenantContext
from soldier.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Tier-based rate limits (requests per minute)
TIER_LIMITS: dict[Literal["free", "pro", "enterprise"], int] = {
    "free": 60,
    "pro": 600,
    "enterprise": 6000,  # High default, can be customized per-tenant
}


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    def check(self, tenant_id: str, limit: int) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum requests allowed in the window

        Returns:
            RateLimitResult indicating if request is allowed
        """
        pass

    @abstractmethod
    def reset(self, tenant_id: str) -> None:
        """Reset rate limit state for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        pass


@dataclass
class RateLimitWindow:
    """Sliding window rate limit state."""

    requests: list[float] = field(default_factory=list)
    """Timestamps of requests within the window."""


class SlidingWindowRateLimiter(RateLimiter):
    """In-memory sliding window rate limiter.

    Implements a sliding window algorithm that tracks request timestamps
    within a 60-second window. Each request outside the window is pruned.

    For production use with multiple instances, use Redis-backed storage.
    """

    def __init__(self, window_seconds: int = 60) -> None:
        """Initialize the rate limiter.

        Args:
            window_seconds: Size of the sliding window in seconds
        """
        self._window_seconds = window_seconds
        self._windows: dict[str, RateLimitWindow] = defaultdict(RateLimitWindow)

    def check(
        self, tenant_id: str, limit: int
    ) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum requests allowed in the window

        Returns:
            RateLimitResult indicating if request is allowed
        """
        now = time.time()
        window_start = now - self._window_seconds
        window = self._windows[tenant_id]

        # Prune old requests outside the window
        window.requests = [ts for ts in window.requests if ts > window_start]

        # Calculate remaining capacity
        current_count = len(window.requests)
        remaining = max(0, limit - current_count)
        allowed = current_count < limit

        # Calculate reset time (end of current window)
        if window.requests:
            oldest = min(window.requests)
            reset_at = datetime.fromtimestamp(oldest + self._window_seconds)
        else:
            reset_at = datetime.fromtimestamp(now + self._window_seconds)

        if allowed:
            # Record this request
            window.requests.append(now)

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining - (1 if allowed else 0),
            reset_at=reset_at,
        )

    def reset(self, tenant_id: str) -> None:
        """Reset rate limit state for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._windows:
            del self._windows[tenant_id]


class RedisRateLimiter(RateLimiter):
    """Redis-backed sliding window rate limiter.

    Implements a sliding window algorithm using Redis sorted sets.
    Each request is stored with its timestamp as the score, allowing
    efficient range queries to count requests within the window.

    This implementation is suitable for distributed deployments where
    multiple application instances need to share rate limit state.
    """

    def __init__(
        self,
        redis_client: Any,  # Redis client (sync or async)
        window_seconds: int = 60,
        key_prefix: str = "ratelimit:",
    ) -> None:
        """Initialize the Redis rate limiter.

        Args:
            redis_client: Redis client instance (sync or async)
            window_seconds: Size of the sliding window in seconds
            key_prefix: Prefix for Redis keys
        """
        self._redis = redis_client
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix

    def _get_key(self, tenant_id: str) -> str:
        """Get the Redis key for a tenant's rate limit data."""
        return f"{self._key_prefix}{tenant_id}"

    def check(self, tenant_id: str, limit: int) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Uses Redis sorted sets with timestamps as scores:
        1. Remove entries older than window_seconds
        2. Count remaining entries
        3. If under limit, add new entry
        4. Return result with remaining count

        Args:
            tenant_id: Tenant identifier
            limit: Maximum requests allowed in the window

        Returns:
            RateLimitResult indicating if request is allowed
        """
        now = time.time()
        window_start = now - self._window_seconds
        key = self._get_key(tenant_id)

        # Use pipeline for atomic operations
        pipe = self._redis.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries in window
        pipe.zcard(key)

        # Execute pipeline
        results = pipe.execute()
        current_count = results[1]

        # Check if request is allowed
        allowed = current_count < limit
        remaining = max(0, limit - current_count)

        if allowed:
            # Add this request with current timestamp as score
            # Use timestamp + random suffix to avoid collisions
            member = f"{now}:{id(self)}:{current_count}"
            self._redis.zadd(key, {member: now})
            # Set TTL on key to auto-expire after window
            self._redis.expire(key, self._window_seconds + 10)
            remaining = remaining - 1

        # Calculate reset time
        oldest_entry = self._redis.zrange(key, 0, 0, withscores=True)
        if oldest_entry:
            oldest_score = oldest_entry[0][1]
            reset_at = datetime.fromtimestamp(oldest_score + self._window_seconds)
        else:
            reset_at = datetime.fromtimestamp(now + self._window_seconds)

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    def reset(self, tenant_id: str) -> None:
        """Reset rate limit state for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        key = self._get_key(tenant_id)
        self._redis.delete(key)


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Returns:
        RateLimiter instance (in-memory by default)
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter()
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter instance.

    Use this to configure Redis-backed rate limiting:

        import redis
        from soldier.api.middleware.rate_limit import (
            RedisRateLimiter,
            set_rate_limiter,
        )

        client = redis.Redis(host='localhost', port=6379)
        set_rate_limiter(RedisRateLimiter(client))

    Args:
        limiter: RateLimiter instance to use globally
    """
    global _rate_limiter
    _rate_limiter = limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter to None.

    Useful for testing to ensure fresh state between tests.
    """
    global _rate_limiter
    _rate_limiter = None


def get_tenant_limit(tier: Literal["free", "pro", "enterprise"]) -> int:
    """Get the rate limit for a tenant tier.

    Args:
        tier: Tenant tier

    Returns:
        Requests per minute limit
    """
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces per-tenant rate limits.

    Rate limits are based on tenant tier:
    - Free: 60 requests/minute
    - Pro: 600 requests/minute
    - Enterprise: 6000 requests/minute (customizable)

    Rate limit headers are added to all responses:
    - X-RateLimit-Limit: Maximum requests in window
    - X-RateLimit-Remaining: Remaining requests
    - X-RateLimit-Reset: Unix timestamp when limit resets
    """

    def __init__(
        self,
        app: Callable[..., Any],
        enabled: bool = True,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: ASGI application
            enabled: Whether rate limiting is enabled
            exclude_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self._enabled = enabled
        self._exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with rate limiting."""
        # Skip if disabled or excluded path
        if not self._enabled or request.url.path in self._exclude_paths:
            return await call_next(request)  # type: ignore[no-any-return, misc]

        # Get tenant context from request state (set by auth middleware)
        tenant_context: TenantContext | None = getattr(
            request.state, "tenant_context", None
        )

        if not tenant_context:
            # No tenant context = no rate limiting (auth will handle this)
            return await call_next(request)  # type: ignore[no-any-return, misc]

        tenant_id = str(tenant_context.tenant_id)
        limit = get_tenant_limit(tenant_context.tier)

        # Check rate limit
        rate_limiter = get_rate_limiter()
        result = rate_limiter.check(tenant_id, limit)

        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                tenant_id=tenant_id,
                tier=tenant_context.tier,
                limit=limit,
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded. Try again after {result.reset_at.isoformat()}"
            )

        # Process request
        response = await call_next(request)  # type: ignore[misc]

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))

        return response  # type: ignore[no-any-return]


def add_rate_limit_headers(response: Response, result: RateLimitResult) -> None:
    """Add rate limit headers to a response.

    Helper function for adding rate limit headers outside middleware.

    Args:
        response: Response object to modify
        result: Rate limit check result
    """
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))
