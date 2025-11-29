"""Idempotency middleware for preventing duplicate request processing.

Implements idempotency via the Idempotency-Key header with a 5-minute cache.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from soldier.observability.logging import get_logger

logger = get_logger(__name__)

# Cache TTL in seconds (5 minutes)
IDEMPOTENCY_TTL_SECONDS = 300


@dataclass
class CachedResponse:
    """Cached response for idempotent requests."""

    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]
    created_at: float


class IdempotencyCache:
    """In-memory idempotency cache.

    Stores responses keyed by (tenant_id, idempotency_key) with automatic
    expiration after 5 minutes.

    For production use with multiple instances, use Redis-backed storage.
    """

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None:
        """Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cached responses
        """
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, CachedResponse] = {}

    def _make_key(self, tenant_id: str, idempotency_key: str) -> str:
        """Create cache key from tenant and idempotency key.

        Args:
            tenant_id: Tenant identifier
            idempotency_key: Client-provided idempotency key

        Returns:
            Combined cache key
        """
        return f"{tenant_id}:{idempotency_key}"

    def _prune_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            key
            for key, value in self._cache.items()
            if now - value.created_at > self._ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]

    def get(
        self, tenant_id: str, idempotency_key: str
    ) -> CachedResponse | None:
        """Get cached response for an idempotency key.

        Args:
            tenant_id: Tenant identifier
            idempotency_key: Client-provided idempotency key

        Returns:
            Cached response if found and not expired, None otherwise
        """
        self._prune_expired()

        key = self._make_key(tenant_id, idempotency_key)
        cached = self._cache.get(key)

        if cached:
            logger.debug(
                "idempotency_cache_hit",
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
            )
            return cached

        return None

    def set(
        self,
        tenant_id: str,
        idempotency_key: str,
        status_code: int,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        """Cache a response for an idempotency key.

        Args:
            tenant_id: Tenant identifier
            idempotency_key: Client-provided idempotency key
            status_code: HTTP status code
            body: Response body as dict
            headers: Optional response headers to cache
        """
        key = self._make_key(tenant_id, idempotency_key)
        self._cache[key] = CachedResponse(
            status_code=status_code,
            body=body,
            headers=headers or {},
            created_at=time.time(),
        )
        logger.debug(
            "idempotency_cache_set",
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )

    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()


# Global cache instance
_idempotency_cache: IdempotencyCache | None = None


def get_idempotency_cache() -> IdempotencyCache:
    """Get the global idempotency cache instance.

    Returns:
        IdempotencyCache instance
    """
    global _idempotency_cache
    if _idempotency_cache is None:
        _idempotency_cache = IdempotencyCache()
    return _idempotency_cache


def compute_request_fingerprint(
    method: str, path: str, body: bytes | None
) -> str:
    """Compute a fingerprint for a request.

    Used to detect if the same idempotency key is reused with different
    request content (which is an error).

    Args:
        method: HTTP method
        path: Request path
        body: Request body bytes

    Returns:
        SHA256 hash of request content
    """
    content = f"{method}:{path}:{body.decode() if body else ''}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
