"""Session mutex implementation.

Redis-backed distributed lock ensuring single-writer rule per conversation.
ACF owns mutex acquisition, extension, and release during turn processing.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis


class SessionMutex:
    """Redis-backed distributed lock for session-level mutual exclusion.

    Ensures only one pipeline execution runs per conversation at a time.
    This is a foundational ACF component that prevents:
    - Scenario race conditions
    - Double responses
    - Rule matching inconsistency
    - Audit trail corruption

    Lock key format: sesslock:{tenant}:{agent}:{customer}:{channel}
    """

    def __init__(
        self,
        redis: Redis,
        lock_timeout: int = 30,
        blocking_timeout: float = 5.0,
    ):
        """Initialize session mutex.

        Args:
            redis: Redis client instance
            lock_timeout: How long lock is held before auto-release (seconds)
            blocking_timeout: How long to wait when trying to acquire (seconds)
        """
        self._redis = redis
        self._lock_timeout = lock_timeout
        self._blocking_timeout = blocking_timeout

    def _key(self, session_key: str) -> str:
        """Build Redis lock key."""
        return f"sesslock:{session_key}"

    @asynccontextmanager
    async def acquire(
        self,
        session_key: str,
        blocking_timeout: float | None = None,
    ) -> AsyncGenerator[bool, None]:
        """Acquire exclusive lock for a session.

        Args:
            session_key: The conversation identifier (tenant:agent:customer:channel)
            blocking_timeout: Override default blocking timeout

        Yields:
            True if lock was acquired, False if timed out

        Usage:
            async with session_mutex.acquire("tenant:agent:customer:web") as acquired:
                if acquired:
                    # Safe to process
                else:
                    # Lock not acquired, handle accordingly
        """
        timeout = blocking_timeout or self._blocking_timeout

        lock = self._redis.lock(
            self._key(session_key),
            timeout=self._lock_timeout,
            blocking_timeout=timeout,
        )

        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    await lock.release()
                except Exception:
                    # Lock may have expired, that's okay
                    pass

    async def is_locked(self, session_key: str) -> bool:
        """Check if a session is currently locked."""
        return await self._redis.exists(self._key(session_key)) > 0

    async def force_release(self, session_key: str) -> bool:
        """Force release a lock (use with caution).

        Only use for cleanup after failures.

        Returns:
            True if lock was released, False if it didn't exist
        """
        return await self._redis.delete(self._key(session_key)) > 0

    async def extend(self, session_key: str, additional_time: int = 30) -> bool:
        """Extend lock timeout for long-running operations.

        Call this periodically during long pipeline runs to prevent
        the lock from expiring mid-execution.

        Args:
            session_key: Session identifier
            additional_time: Seconds to extend

        Returns:
            True if extended successfully
        """
        lock = self._redis.lock(self._key(session_key))
        return await lock.extend(additional_time)

    async def acquire_direct(
        self, session_key: str, blocking_timeout: float | None = None
    ) -> str | None:
        """Acquire lock directly without context manager.

        CRITICAL: For Hatchet workflows where lock must persist across steps.
        Caller MUST call release_direct() when done.

        Args:
            session_key: Session identifier
            blocking_timeout: Override default blocking timeout

        Returns:
            Lock key if acquired, None if failed
        """
        timeout = blocking_timeout or self._blocking_timeout
        lock_key = self._key(session_key)

        lock = self._redis.lock(lock_key, timeout=self._lock_timeout)
        acquired = await lock.acquire(blocking_timeout=timeout)

        return lock_key if acquired else None

    async def release_direct(self, lock_key: str) -> None:
        """Release a directly-acquired lock.

        Args:
            lock_key: The full Redis key from acquire_direct()
        """
        await self._redis.delete(lock_key)


def build_session_key(
    tenant_id: str,
    agent_id: str,
    customer_id: str,
    channel: str,
) -> str:
    """Build composite session key for mutex.

    Format: {tenant_id}:{agent_id}:{customer_id}:{channel}

    This key is used for:
    - Session mutex (single-writer rule)
    - Turn store lookups
    - Hatchet workflow correlation

    Args:
        tenant_id: Tenant UUID as string
        agent_id: Agent UUID as string
        customer_id: Customer UUID as string
        channel: Channel identifier (whatsapp, web, etc.)

    Returns:
        Composite session key
    """
    return f"{tenant_id}:{agent_id}:{customer_id}:{channel}"
