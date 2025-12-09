<a id="focal.api.middleware.idempotency"></a>

# focal.api.middleware.idempotency

Idempotency middleware for preventing duplicate request processing.

Implements idempotency via the Idempotency-Key header with a 5-minute cache.

<a id="focal.api.middleware.idempotency.CachedResponse"></a>

## CachedResponse Objects

```python
@dataclass
class CachedResponse()
```

Cached response for idempotent requests.

<a id="focal.api.middleware.idempotency.IdempotencyCache"></a>

## IdempotencyCache Objects

```python
class IdempotencyCache()
```

In-memory idempotency cache.

Stores responses keyed by (tenant_id, idempotency_key) with automatic
expiration after 5 minutes.

For production use with multiple instances, use Redis-backed storage.

<a id="focal.api.middleware.idempotency.IdempotencyCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None
```

Initialize the cache.

**Arguments**:

- `ttl_seconds` - Time-to-live for cached responses

<a id="focal.api.middleware.idempotency.IdempotencyCache.get"></a>

#### get

```python
def get(tenant_id: str, idempotency_key: str) -> CachedResponse | None
```

Get cached response for an idempotency key.

**Arguments**:

- `tenant_id` - Tenant identifier
- `idempotency_key` - Client-provided idempotency key
  

**Returns**:

  Cached response if found and not expired, None otherwise

<a id="focal.api.middleware.idempotency.IdempotencyCache.set"></a>

#### set

```python
def set(tenant_id: str,
        idempotency_key: str,
        status_code: int,
        body: dict[str, Any],
        headers: dict[str, str] | None = None) -> None
```

Cache a response for an idempotency key.

**Arguments**:

- `tenant_id` - Tenant identifier
- `idempotency_key` - Client-provided idempotency key
- `status_code` - HTTP status code
- `body` - Response body as dict
- `headers` - Optional response headers to cache

<a id="focal.api.middleware.idempotency.IdempotencyCache.clear"></a>

#### clear

```python
def clear() -> None
```

Clear all cached responses.

<a id="focal.api.middleware.idempotency.get_idempotency_cache"></a>

#### get\_idempotency\_cache

```python
def get_idempotency_cache() -> IdempotencyCache
```

Get the global idempotency cache instance.

**Returns**:

  IdempotencyCache instance

<a id="focal.api.middleware.idempotency.compute_request_fingerprint"></a>

#### compute\_request\_fingerprint

```python
def compute_request_fingerprint(method: str, path: str,
                                body: bytes | None) -> str
```

Compute a fingerprint for a request.

Used to detect if the same idempotency key is reused with different
request content (which is an error).

**Arguments**:

- `method` - HTTP method
- `path` - Request path
- `body` - Request body bytes
  

**Returns**:

  SHA256 hash of request content

