<a id="soldier.api.middleware.rate_limit"></a>

# soldier.api.middleware.rate\_limit

Rate limiting middleware for per-tenant request limits.

<a id="soldier.api.middleware.rate_limit.RateLimiter"></a>

## RateLimiter Objects

```python
class RateLimiter(ABC)
```

Abstract base class for rate limiters.

<a id="soldier.api.middleware.rate_limit.RateLimiter.check"></a>

#### check

```python
@abstractmethod
def check(tenant_id: str, limit: int) -> RateLimitResult
```

Check if a request is allowed under the rate limit.

**Arguments**:

- `tenant_id` - Tenant identifier
- `limit` - Maximum requests allowed in the window
  

**Returns**:

  RateLimitResult indicating if request is allowed

<a id="soldier.api.middleware.rate_limit.RateLimiter.reset"></a>

#### reset

```python
@abstractmethod
def reset(tenant_id: str) -> None
```

Reset rate limit state for a tenant.

**Arguments**:

- `tenant_id` - Tenant identifier

<a id="soldier.api.middleware.rate_limit.RateLimitWindow"></a>

## RateLimitWindow Objects

```python
@dataclass
class RateLimitWindow()
```

Sliding window rate limit state.

<a id="soldier.api.middleware.rate_limit.RateLimitWindow.requests"></a>

#### requests

Timestamps of requests within the window.

<a id="soldier.api.middleware.rate_limit.SlidingWindowRateLimiter"></a>

## SlidingWindowRateLimiter Objects

```python
class SlidingWindowRateLimiter(RateLimiter)
```

In-memory sliding window rate limiter.

Implements a sliding window algorithm that tracks request timestamps
within a 60-second window. Each request outside the window is pruned.

For production use with multiple instances, use Redis-backed storage.

<a id="soldier.api.middleware.rate_limit.SlidingWindowRateLimiter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(window_seconds: int = 60) -> None
```

Initialize the rate limiter.

**Arguments**:

- `window_seconds` - Size of the sliding window in seconds

<a id="soldier.api.middleware.rate_limit.SlidingWindowRateLimiter.check"></a>

#### check

```python
def check(tenant_id: str, limit: int) -> RateLimitResult
```

Check if a request is allowed under the rate limit.

**Arguments**:

- `tenant_id` - Tenant identifier
- `limit` - Maximum requests allowed in the window
  

**Returns**:

  RateLimitResult indicating if request is allowed

<a id="soldier.api.middleware.rate_limit.SlidingWindowRateLimiter.reset"></a>

#### reset

```python
def reset(tenant_id: str) -> None
```

Reset rate limit state for a tenant.

**Arguments**:

- `tenant_id` - Tenant identifier

<a id="soldier.api.middleware.rate_limit.RedisRateLimiter"></a>

## RedisRateLimiter Objects

```python
class RedisRateLimiter(RateLimiter)
```

Redis-backed sliding window rate limiter.

Implements a sliding window algorithm using Redis sorted sets.
Each request is stored with its timestamp as the score, allowing
efficient range queries to count requests within the window.

This implementation is suitable for distributed deployments where
multiple application instances need to share rate limit state.

<a id="soldier.api.middleware.rate_limit.RedisRateLimiter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(redis_client: Any,
             window_seconds: int = 60,
             key_prefix: str = "ratelimit:") -> None
```

Initialize the Redis rate limiter.

**Arguments**:

- `redis_client` - Redis client instance (sync or async)
- `window_seconds` - Size of the sliding window in seconds
- `key_prefix` - Prefix for Redis keys

<a id="soldier.api.middleware.rate_limit.RedisRateLimiter.check"></a>

#### check

```python
def check(tenant_id: str, limit: int) -> RateLimitResult
```

Check if a request is allowed under the rate limit.

Uses Redis sorted sets with timestamps as scores:
1. Remove entries older than window_seconds
2. Count remaining entries
3. If under limit, add new entry
4. Return result with remaining count

**Arguments**:

- `tenant_id` - Tenant identifier
- `limit` - Maximum requests allowed in the window
  

**Returns**:

  RateLimitResult indicating if request is allowed

<a id="soldier.api.middleware.rate_limit.RedisRateLimiter.reset"></a>

#### reset

```python
def reset(tenant_id: str) -> None
```

Reset rate limit state for a tenant.

**Arguments**:

- `tenant_id` - Tenant identifier

<a id="soldier.api.middleware.rate_limit.get_rate_limiter"></a>

#### get\_rate\_limiter

```python
def get_rate_limiter() -> RateLimiter
```

Get the global rate limiter instance.

**Returns**:

  RateLimiter instance (in-memory by default)

<a id="soldier.api.middleware.rate_limit.set_rate_limiter"></a>

#### set\_rate\_limiter

```python
def set_rate_limiter(limiter: RateLimiter) -> None
```

Set the global rate limiter instance.

Use this to configure Redis-backed rate limiting:

import redis
from soldier.api.middleware.rate_limit import (
RedisRateLimiter,
set_rate_limiter,
)

client = redis.Redis(host='localhost', port=6379)
set_rate_limiter(RedisRateLimiter(client))

**Arguments**:

- `limiter` - RateLimiter instance to use globally

<a id="soldier.api.middleware.rate_limit.reset_rate_limiter"></a>

#### reset\_rate\_limiter

```python
def reset_rate_limiter() -> None
```

Reset the global rate limiter to None.

Useful for testing to ensure fresh state between tests.

<a id="soldier.api.middleware.rate_limit.get_tenant_limit"></a>

#### get\_tenant\_limit

```python
def get_tenant_limit(tier: Literal["free", "pro", "enterprise"]) -> int
```

Get the rate limit for a tenant tier.

**Arguments**:

- `tier` - Tenant tier
  

**Returns**:

  Requests per minute limit

<a id="soldier.api.middleware.rate_limit.RateLimitMiddleware"></a>

## RateLimitMiddleware Objects

```python
class RateLimitMiddleware(BaseHTTPMiddleware)
```

Middleware that enforces per-tenant rate limits.

Rate limits are based on tenant tier:
- Free: 60 requests/minute
- Pro: 600 requests/minute
- Enterprise: 6000 requests/minute (customizable)

Rate limit headers are added to all responses:
- X-RateLimit-Limit: Maximum requests in window
- X-RateLimit-Remaining: Remaining requests
- X-RateLimit-Reset: Unix timestamp when limit resets

<a id="soldier.api.middleware.rate_limit.RateLimitMiddleware.__init__"></a>

#### \_\_init\_\_

```python
def __init__(app: Callable[..., Any],
             enabled: bool = True,
             exclude_paths: list[str] | None = None) -> None
```

Initialize the middleware.

**Arguments**:

- `app` - ASGI application
- `enabled` - Whether rate limiting is enabled
- `exclude_paths` - Paths to exclude from rate limiting

<a id="soldier.api.middleware.rate_limit.RateLimitMiddleware.dispatch"></a>

#### dispatch

```python
async def dispatch(request: Request,
                   call_next: Callable[[Request], Response]) -> Response
```

Process request with rate limiting.

<a id="soldier.api.middleware.rate_limit.add_rate_limit_headers"></a>

#### add\_rate\_limit\_headers

```python
def add_rate_limit_headers(response: Response,
                           result: RateLimitResult) -> None
```

Add rate limit headers to a response.

Helper function for adding rate limit headers outside middleware.

**Arguments**:

- `response` - Response object to modify
- `result` - Rate limit check result

