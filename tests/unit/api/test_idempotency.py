"""Unit tests for idempotency middleware."""

import time

import pytest

from ruche.api.middleware.idempotency import (
    IDEMPOTENCY_TTL_SECONDS,
    CachedResponse,
    IdempotencyCache,
    compute_request_fingerprint,
    get_idempotency_cache,
)


@pytest.fixture
def cache() -> IdempotencyCache:
    """Create fresh idempotency cache."""
    return IdempotencyCache()


class TestIdempotencyCache:
    """Tests for IdempotencyCache."""

    def test_get_returns_none_for_missing_key(self, cache: IdempotencyCache) -> None:
        """Returns None when key doesn't exist."""
        result = cache.get("tenant_1", "key_1")
        assert result is None

    def test_set_and_get(self, cache: IdempotencyCache) -> None:
        """Can store and retrieve cached response."""
        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_1",
            status_code=200,
            body={"result": "success"},
            headers={"X-Custom": "value"},
        )

        result = cache.get("tenant_1", "key_1")
        assert result is not None
        assert result.status_code == 200
        assert result.body == {"result": "success"}
        assert result.headers == {"X-Custom": "value"}

    def test_tenant_isolation(self, cache: IdempotencyCache) -> None:
        """Different tenants have separate cache entries."""
        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_1",
            status_code=200,
            body={"tenant": "1"},
        )
        cache.set(
            tenant_id="tenant_2",
            idempotency_key="key_1",  # Same key, different tenant
            status_code=201,
            body={"tenant": "2"},
        )

        result_1 = cache.get("tenant_1", "key_1")
        result_2 = cache.get("tenant_2", "key_1")

        assert result_1 is not None
        assert result_1.body == {"tenant": "1"}
        assert result_2 is not None
        assert result_2.body == {"tenant": "2"}

    def test_different_keys_stored_separately(self, cache: IdempotencyCache) -> None:
        """Different keys for same tenant are stored separately."""
        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_a",
            status_code=200,
            body={"key": "a"},
        )
        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_b",
            status_code=201,
            body={"key": "b"},
        )

        result_a = cache.get("tenant_1", "key_a")
        result_b = cache.get("tenant_1", "key_b")

        assert result_a is not None
        assert result_a.body == {"key": "a"}
        assert result_b is not None
        assert result_b.body == {"key": "b"}

    def test_expired_entries_pruned(self) -> None:
        """Expired entries are automatically removed."""
        # Create cache with 1 second TTL
        cache = IdempotencyCache(ttl_seconds=1)

        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_1",
            status_code=200,
            body={"data": "test"},
        )

        # Should be available immediately
        assert cache.get("tenant_1", "key_1") is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should be pruned
        assert cache.get("tenant_1", "key_1") is None

    def test_clear_removes_all_entries(self, cache: IdempotencyCache) -> None:
        """Clear removes all cached entries."""
        cache.set("tenant_1", "key_1", 200, {"a": 1})
        cache.set("tenant_2", "key_2", 201, {"b": 2})

        cache.clear()

        assert cache.get("tenant_1", "key_1") is None
        assert cache.get("tenant_2", "key_2") is None

    def test_headers_optional(self, cache: IdempotencyCache) -> None:
        """Headers are optional when setting cache entry."""
        cache.set(
            tenant_id="tenant_1",
            idempotency_key="key_1",
            status_code=200,
            body={"data": "value"},
        )

        result = cache.get("tenant_1", "key_1")
        assert result is not None
        assert result.headers == {}


class TestCachedResponse:
    """Tests for CachedResponse dataclass."""

    def test_creation(self) -> None:
        """Can create CachedResponse."""
        now = time.time()
        response = CachedResponse(
            status_code=200,
            body={"data": "test"},
            headers={"X-Test": "value"},
            created_at=now,
        )

        assert response.status_code == 200
        assert response.body == {"data": "test"}
        assert response.headers == {"X-Test": "value"}
        assert response.created_at == now


class TestComputeRequestFingerprint:
    """Tests for compute_request_fingerprint function."""

    def test_same_request_same_fingerprint(self) -> None:
        """Identical requests produce same fingerprint."""
        fp1 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"hello"}')
        fp2 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"hello"}')

        assert fp1 == fp2

    def test_different_method_different_fingerprint(self) -> None:
        """Different HTTP methods produce different fingerprints."""
        fp1 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"hello"}')
        fp2 = compute_request_fingerprint("PUT", "/v1/chat", b'{"message":"hello"}')

        assert fp1 != fp2

    def test_different_path_different_fingerprint(self) -> None:
        """Different paths produce different fingerprints."""
        fp1 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"hello"}')
        fp2 = compute_request_fingerprint("POST", "/v1/sessions", b'{"message":"hello"}')

        assert fp1 != fp2

    def test_different_body_different_fingerprint(self) -> None:
        """Different bodies produce different fingerprints."""
        fp1 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"hello"}')
        fp2 = compute_request_fingerprint("POST", "/v1/chat", b'{"message":"goodbye"}')

        assert fp1 != fp2

    def test_none_body_handled(self) -> None:
        """None body is handled correctly."""
        fp1 = compute_request_fingerprint("GET", "/v1/sessions", None)
        fp2 = compute_request_fingerprint("GET", "/v1/sessions", None)

        assert fp1 == fp2

    def test_returns_hex_string(self) -> None:
        """Fingerprint is a hex string."""
        fp = compute_request_fingerprint("POST", "/test", b"body")

        assert isinstance(fp, str)
        assert len(fp) == 16  # SHA256 truncated to 16 chars
        # Should be valid hex
        int(fp, 16)


class TestGetIdempotencyCache:
    """Tests for get_idempotency_cache function."""

    def test_returns_singleton(self) -> None:
        """Returns the same instance on multiple calls."""
        # Reset the global
        import ruche.api.middleware.idempotency as idem_module
        idem_module._idempotency_cache = None

        cache1 = get_idempotency_cache()
        cache2 = get_idempotency_cache()

        assert cache1 is cache2

    def test_creates_cache_if_none(self) -> None:
        """Creates new cache if none exists."""
        import ruche.api.middleware.idempotency as idem_module
        idem_module._idempotency_cache = None

        cache = get_idempotency_cache()

        assert isinstance(cache, IdempotencyCache)


class TestIdempotencyTTL:
    """Tests for idempotency TTL constant."""

    def test_ttl_is_5_minutes(self) -> None:
        """TTL should be 5 minutes (300 seconds)."""
        assert IDEMPOTENCY_TTL_SECONDS == 300
