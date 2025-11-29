"""API middleware package.

Exports middleware components for request processing.
"""

from soldier.api.middleware.auth import (
    TenantContextDep,
    get_tenant_context,
    security_scheme,
)
from soldier.api.middleware.context import (
    RequestContextMiddleware,
    get_request_context,
    set_request_context,
    update_request_context,
)
from soldier.api.middleware.idempotency import (
    IdempotencyCache,
    compute_request_fingerprint,
    get_idempotency_cache,
)
from soldier.api.middleware.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
    RedisRateLimiter,
    SlidingWindowRateLimiter,
    add_rate_limit_headers,
    get_rate_limiter,
    get_tenant_limit,
    reset_rate_limiter,
    set_rate_limiter,
)

__all__ = [
    # Auth middleware
    "get_tenant_context",
    "TenantContextDep",
    "security_scheme",
    # Context middleware
    "RequestContextMiddleware",
    "get_request_context",
    "set_request_context",
    "update_request_context",
    # Rate limit middleware
    "RateLimiter",
    "RateLimitMiddleware",
    "RedisRateLimiter",
    "SlidingWindowRateLimiter",
    "get_rate_limiter",
    "get_tenant_limit",
    "add_rate_limit_headers",
    "set_rate_limiter",
    "reset_rate_limiter",
    # Idempotency middleware
    "IdempotencyCache",
    "get_idempotency_cache",
    "compute_request_fingerprint",
]
