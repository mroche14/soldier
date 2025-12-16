"""Tests for SessionMutex - Redis-backed distributed lock.

Tests cover:
- Lock acquisition and release
- Context manager behavior
- Force release and extension
- Direct acquire/release for Hatchet workflows
- Session key building
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ruche.runtime.acf.mutex import SessionMutex, build_session_key


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()

    # Mock lock object
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=True)
    mock_lock.release = AsyncMock()
    mock_lock.extend = AsyncMock(return_value=True)

    redis.lock = MagicMock(return_value=mock_lock)
    redis.exists = AsyncMock(return_value=0)
    redis.delete = AsyncMock(return_value=1)

    return redis


@pytest.fixture
def mutex(mock_redis):
    """Create SessionMutex instance."""
    return SessionMutex(
        redis=mock_redis,
        lock_timeout=30,
        blocking_timeout=5.0,
    )


# =============================================================================
# Tests: SessionMutex initialization
# =============================================================================


class TestSessionMutexInit:
    """Tests for SessionMutex initialization."""

    def test_creates_with_default_timeouts(self, mock_redis):
        """Creates mutex with default timeout values."""
        mutex = SessionMutex(redis=mock_redis)

        assert mutex._lock_timeout == 30
        assert mutex._blocking_timeout == 5.0

    def test_creates_with_custom_timeouts(self, mock_redis):
        """Creates mutex with custom timeout values."""
        mutex = SessionMutex(
            redis=mock_redis,
            lock_timeout=60,
            blocking_timeout=10.0,
        )

        assert mutex._lock_timeout == 60
        assert mutex._blocking_timeout == 10.0


# =============================================================================
# Tests: SessionMutex._key()
# =============================================================================


class TestSessionMutexKey:
    """Tests for lock key generation."""

    def test_builds_redis_key(self, mutex):
        """Builds Redis key with sesslock prefix."""
        key = mutex._key("tenant:agent:customer:channel")
        assert key == "sesslock:tenant:agent:customer:channel"


# =============================================================================
# Tests: SessionMutex.acquire() context manager
# =============================================================================


class TestSessionMutexAcquire:
    """Tests for acquire context manager."""

    @pytest.mark.asyncio
    async def test_acquires_lock_successfully(self, mutex, mock_redis):
        """Acquires lock and yields True."""
        async with mutex.acquire("test:session") as acquired:
            assert acquired is True

    @pytest.mark.asyncio
    async def test_yields_false_when_lock_unavailable(self, mutex, mock_redis):
        """Yields False when lock cannot be acquired."""
        mock_lock = mock_redis.lock.return_value
        mock_lock.acquire = AsyncMock(return_value=False)

        async with mutex.acquire("test:session") as acquired:
            assert acquired is False

    @pytest.mark.asyncio
    async def test_releases_lock_on_exit(self, mutex, mock_redis):
        """Releases lock when exiting context."""
        mock_lock = mock_redis.lock.return_value

        async with mutex.acquire("test:session") as acquired:
            assert acquired is True

        mock_lock.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_custom_blocking_timeout(self, mutex, mock_redis):
        """Uses custom blocking timeout when provided."""
        async with mutex.acquire("test:session", blocking_timeout=15.0):
            pass

        # Verify lock was created with custom timeout
        mock_redis.lock.assert_called_once()
        call_kwargs = mock_redis.lock.call_args.kwargs
        assert call_kwargs["blocking_timeout"] == 15.0


# =============================================================================
# Tests: SessionMutex.is_locked()
# =============================================================================


class TestSessionMutexIsLocked:
    """Tests for is_locked check."""

    @pytest.mark.asyncio
    async def test_returns_true_when_locked(self, mutex, mock_redis):
        """Returns True when session is locked."""
        mock_redis.exists = AsyncMock(return_value=1)

        result = await mutex.is_locked("test:session")

        assert result is True
        mock_redis.exists.assert_called_with("sesslock:test:session")

    @pytest.mark.asyncio
    async def test_returns_false_when_unlocked(self, mutex, mock_redis):
        """Returns False when session is not locked."""
        mock_redis.exists = AsyncMock(return_value=0)

        result = await mutex.is_locked("test:session")

        assert result is False


# =============================================================================
# Tests: SessionMutex.force_release()
# =============================================================================


class TestSessionMutexForceRelease:
    """Tests for force_release."""

    @pytest.mark.asyncio
    async def test_deletes_lock_key(self, mutex, mock_redis):
        """Deletes the lock key from Redis."""
        mock_redis.delete = AsyncMock(return_value=1)

        result = await mutex.force_release("test:session")

        assert result is True
        mock_redis.delete.assert_called_with("sesslock:test:session")

    @pytest.mark.asyncio
    async def test_returns_false_when_key_not_exists(self, mutex, mock_redis):
        """Returns False when lock key doesn't exist."""
        mock_redis.delete = AsyncMock(return_value=0)

        result = await mutex.force_release("test:session")

        assert result is False


# =============================================================================
# Tests: SessionMutex.extend()
# =============================================================================


class TestSessionMutexExtend:
    """Tests for lock extension."""

    @pytest.mark.asyncio
    async def test_extends_lock_timeout(self, mutex, mock_redis):
        """Extends lock timeout successfully."""
        mock_lock = mock_redis.lock.return_value
        mock_lock.extend = AsyncMock(return_value=True)

        result = await mutex.extend("test:session", additional_time=60)

        assert result is True
        mock_lock.extend.assert_called_with(60)

    @pytest.mark.asyncio
    async def test_uses_default_extension_time(self, mutex, mock_redis):
        """Uses default 30 second extension."""
        mock_lock = mock_redis.lock.return_value

        await mutex.extend("test:session")

        mock_lock.extend.assert_called_with(30)


# =============================================================================
# Tests: SessionMutex.acquire_direct()
# =============================================================================


class TestSessionMutexAcquireDirect:
    """Tests for direct lock acquisition (Hatchet workflows)."""

    @pytest.mark.asyncio
    async def test_returns_lock_key_on_success(self, mutex, mock_redis):
        """Returns lock key when acquisition succeeds."""
        mock_lock = mock_redis.lock.return_value
        mock_lock.acquire = AsyncMock(return_value=True)

        result = await mutex.acquire_direct("test:session")

        assert result == "sesslock:test:session"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, mutex, mock_redis):
        """Returns None when acquisition fails."""
        mock_lock = mock_redis.lock.return_value
        mock_lock.acquire = AsyncMock(return_value=False)

        result = await mutex.acquire_direct("test:session")

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_custom_blocking_timeout(self, mutex, mock_redis):
        """Uses custom blocking timeout."""
        mock_lock = mock_redis.lock.return_value

        await mutex.acquire_direct("test:session", blocking_timeout=20.0)

        mock_lock.acquire.assert_called_with(blocking_timeout=20.0)


# =============================================================================
# Tests: SessionMutex.release_direct()
# =============================================================================


class TestSessionMutexReleaseDirect:
    """Tests for direct lock release."""

    @pytest.mark.asyncio
    async def test_deletes_lock_key(self, mutex, mock_redis):
        """Deletes the lock key directly."""
        await mutex.release_direct("sesslock:test:session")

        mock_redis.delete.assert_called_with("sesslock:test:session")


# =============================================================================
# Tests: build_session_key()
# =============================================================================


class TestBuildSessionKey:
    """Tests for session key builder."""

    def test_builds_composite_key(self):
        """Builds key from component IDs."""
        key = build_session_key(
            tenant_id="tenant-123",
            agent_id="agent-456",
            interlocutor_id="customer-789",
            channel="whatsapp",
        )

        assert key == "tenant-123:agent-456:customer-789:whatsapp"

    def test_handles_uuid_strings(self):
        """Handles UUID strings correctly."""
        key = build_session_key(
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            interlocutor_id="123e4567-e89b-12d3-a456-426614174000",
            channel="webchat",
        )

        parts = key.split(":")
        assert len(parts) == 4
        assert parts[3] == "webchat"

    def test_handles_special_characters_in_channel(self):
        """Handles various channel identifiers."""
        for channel in ["web", "whatsapp", "sms", "email", "api", "slack"]:
            key = build_session_key("t", "a", "c", channel)
            assert key.endswith(f":{channel}")
