# Session Mutex (Single-Writer Rule)

> **Topic**: Preventing concurrent brain execution per conversation
> **ACF Component**: Core infrastructure owned by Agent Conversation Fabric
> **Dependencies**: None (foundational)
> **Impacts**: All message processing, race condition prevention
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification

---

## ACF Context

The Session Mutex is a **foundational ACF component**. ACF acquires the mutex before any turn processing begins and holds it until the turn completes or is superseded.

### ACF Ownership

| Aspect | Owner | Description |
|--------|-------|-------------|
| Lock Acquisition | ACF | First step in LogicalTurnWorkflow |
| Lock Extension | ACF | Extended during long brain runs |
| Lock Release | ACF | On turn complete, supersede, or failure |
| Lock Key Format | ACF | `sesslock:{tenant}:{agent}:{customer}:{channel}` |

### Why ACF Owns This

The mutex ensures the single-writer rule that makes everything else work:
- No race conditions between concurrent turn attempts
- Clean supersede semantics (only one turn active per session)
- Consistent audit trail

---

## Overview

The **Session Mutex** enforces a single-writer rule: no two brain executions can run concurrently for the same conversation.

### The Problem

Without coordination:

```
Time →
Pod A: [───── Processing "Hello" ─────]
Pod B:          [───── Processing "How are you?" ─────]

Result: Race conditions, double responses, scenario thrashing
```

### The Solution

A distributed lock ensures sequential processing:

```
Time →
Pod A: [LOCK] [───── Processing "Hello" ─────] [UNLOCK]
Pod B:        [WAIT.....................] [LOCK] [─── "How are you?" ───]

Result: Clean sequential processing, no races
```

---

## Lock Key Format

```python
def build_lock_key(
    tenant_id: UUID,
    agent_id: UUID,
    customer_id: UUID,
    channel: str,
) -> str:
    """
    Build Redis lock key for session mutex.

    Format: sesslock:{tenant}:{agent}:{customer}:{channel}
    """
    return f"sesslock:{tenant_id}:{agent_id}:{customer_id}:{channel}"
```

The key identifies a **conversation stream**, not just a session. This allows:
- Same customer on different channels = different locks
- Same customer with different agents = different locks

---

## Implementation

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from redis.asyncio import Redis

class SessionLock:
    """
    Redis-backed distributed lock for session-level mutual exclusion.

    Ensures only one brain execution runs per conversation at a time.
    """

    def __init__(
        self,
        redis: Redis,
        lock_timeout: int = 30,
        blocking_timeout: float = 5.0,
    ):
        """
        Args:
            redis: Redis client instance
            lock_timeout: How long lock is held before auto-release (seconds)
            blocking_timeout: How long to wait when trying to acquire (seconds)
        """
        self._redis = redis
        self._lock_timeout = lock_timeout
        self._blocking_timeout = blocking_timeout

    def _key(self, session_key: str) -> str:
        return f"sesslock:{session_key}"

    @asynccontextmanager
    async def acquire(
        self,
        session_key: str,
        blocking_timeout: float | None = None,
    ) -> AsyncGenerator[bool, None]:
        """
        Acquire exclusive lock for a session.

        Args:
            session_key: The conversation identifier
            blocking_timeout: Override default blocking timeout

        Yields:
            True if lock was acquired, False if timed out

        Usage:
            async with session_lock.acquire("tenant:agent:customer:web") as acquired:
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
        """
        Force release a lock (use with caution).

        Only use for cleanup after failures.
        """
        return await self._redis.delete(self._key(session_key)) > 0

    async def extend(self, session_key: str, additional_time: int = 30) -> bool:
        """
        Extend lock timeout for long-running operations.

        Call this periodically during long brain runs to prevent
        the lock from expiring mid-execution.
        """
        lock = self._redis.lock(self._key(session_key))
        return await lock.extend(additional_time)
```

---

## What It Prevents

### 1. Scenario Race Conditions

```
Without mutex:
  Turn 1: Read scenario at step A
  Turn 2: Read scenario at step A
  Turn 1: Advance to step B
  Turn 2: Advance to step B (but from stale state!)

With mutex:
  Turn 1: [LOCK] Read step A → Advance to B [UNLOCK]
  Turn 2: [LOCK] Read step B → Advance to C [UNLOCK]
```

### 2. Double Responses

```
Without mutex:
  "Hello" → Response 1
  "Hello" → Response 2 (duplicate processing)

With mutex:
  "Hello" → Response 1
  "Hello" (duplicate) → Handled by idempotency, not re-processed
```

### 3. Rule Matching Inconsistency

```
Without mutex:
  Turn 1: Match rules {A, B, C}
  Turn 2: Match rules {A, B, D} (rule C was applied, now seeing D)

With mutex:
  Turn 1: [LOCK] Match {A,B,C} → Apply → Commit [UNLOCK]
  Turn 2: [LOCK] Match {A,B,D} (correct current state) [UNLOCK]
```

### 4. Audit Trail Corruption

```
Without mutex:
  TurnRecord 1: turn_number=5
  TurnRecord 2: turn_number=5 (collision!)

With mutex:
  TurnRecord 1: turn_number=5 [UNLOCK]
  TurnRecord 2: turn_number=6 (correct sequence)
```

---

## Usage Patterns

### Basic Usage

```python
session_lock = SessionLock(redis=redis_client)

async def handle_message(message: UserMessage):
    session_key = build_session_key(
        message.tenant_id,
        message.agent_id,
        message.customer_id,
        message.channel,
    )

    async with session_lock.acquire(session_key) as acquired:
        if not acquired:
            # Could not acquire lock in time
            # Options: queue message, return "busy" response, retry
            raise SessionBusyError(session_key)

        # Safe to process
        result = await process_turn(message)
        return result
```

### With Hatchet Workflow

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.step()
    async def acquire_lock(self, ctx: Context) -> dict:
        session_key = ctx.workflow_input()["session_key"]
        session_lock = SessionLock(redis=ctx.services.redis)

        async with session_lock.acquire(session_key, blocking_timeout=10) as acquired:
            if not acquired:
                return {"status": "lock_failed", "retry": True}
            return {"status": "locked"}

    # Lock is held for duration of workflow via Hatchet's durable execution
```

### Lock Extension for Long Operations

```python
async def process_long_turn(session_key: str, turn: LogicalTurn):
    async with session_lock.acquire(session_key) as acquired:
        if not acquired:
            raise SessionBusyError()

        for phase in phases:
            # Extend lock every 10 seconds during long operations
            if phase.expected_duration_seconds > 10:
                await session_lock.extend(session_key, additional_time=30)

            await phase.execute(turn)
```

---

## Configuration

```toml
[session.lock]
# How long lock is held before auto-release (prevents deadlocks)
timeout_seconds = 30

# How long to wait when trying to acquire
blocking_timeout_seconds = 5.0

# Redis key prefix
key_prefix = "sesslock"
```

---

## Failure Handling

### Lock Timeout (Deadlock Prevention)

The lock auto-releases after `timeout_seconds` even if not explicitly released:

```python
# Pod A crashes while holding lock
# After 30 seconds, lock auto-releases
# Pod B can now acquire and process
```

### Blocking Timeout

If lock cannot be acquired in time:

```python
async with session_lock.acquire(session_key) as acquired:
    if not acquired:
        # Options:
        # 1. Queue message for later
        await message_queue.enqueue(message)

        # 2. Return "busy" response
        return BusyResponse("Please wait, processing previous message")

        # 3. Retry with backoff
        await asyncio.sleep(1)
        return await handle_message(message)  # Retry
```

### Redis Unavailable

```python
try:
    async with session_lock.acquire(session_key) as acquired:
        ...
except RedisConnectionError:
    # Fallback: process without lock (risky but keeps system running)
    logger.warning("Redis unavailable, processing without lock")
    await process_turn_unprotected(message)
```

---

## Monitoring

### Metrics to Track

```python
# Lock acquisition time
lock_acquire_duration_seconds = Histogram(
    "session_lock_acquire_duration_seconds",
    "Time to acquire session lock",
    ["session_key_pattern"],
)

# Lock contention
lock_wait_count = Counter(
    "session_lock_wait_total",
    "Number of times lock acquisition had to wait",
)

# Lock failures
lock_failure_count = Counter(
    "session_lock_failure_total",
    "Number of failed lock acquisitions",
    ["reason"],  # timeout, redis_error
)
```

### Health Check

```python
async def check_session_lock_health() -> bool:
    """Verify session lock system is operational."""
    test_key = "health_check_lock"
    try:
        async with session_lock.acquire(test_key, blocking_timeout=1) as acquired:
            return acquired
    except Exception:
        return False
```

---

## Testing Considerations

```python
# Test: Concurrent requests are serialized
async def test_concurrent_requests_serialized():
    results = []
    session_key = "test:session"

    async def process(value: str):
        async with session_lock.acquire(session_key):
            results.append(f"start:{value}")
            await asyncio.sleep(0.1)
            results.append(f"end:{value}")

    await asyncio.gather(
        process("A"),
        process("B"),
    )

    # Results should be serialized, not interleaved
    assert results in [
        ["start:A", "end:A", "start:B", "end:B"],
        ["start:B", "end:B", "start:A", "end:A"],
    ]

# Test: Lock timeout prevents deadlock
async def test_lock_auto_releases_on_timeout():
    session_key = "test:timeout"
    lock = SessionLock(redis, lock_timeout=1)

    async with lock.acquire(session_key):
        pass  # Don't release explicitly

    await asyncio.sleep(1.5)

    # Should be able to acquire again
    async with lock.acquire(session_key) as acquired:
        assert acquired
```

---

## ACF Integration

The session mutex is acquired in the first step of `LogicalTurnWorkflow`.

### CRITICAL: Mutex Lifecycle in Hatchet

**PROBLEM**: Using `async with session_lock.acquire()` in a Hatchet step releases the lock when the step returns!

```python
# WRONG - Lock released when step exits
@hatchet.step()
async def acquire_mutex(self, ctx: Context) -> dict:
    async with session_lock.acquire(session_key) as acquired:  # ❌
        if acquired:
            return {"status": "locked"}  # Lock released HERE
    # Steps 2, 3, 4 run WITHOUT lock protection!
```

**SOLUTION**: Acquire without context manager, release explicitly at commit/failure:

```python
@hatchet.step()
async def acquire_mutex(self, ctx: Context) -> dict:
    """
    Acquire session mutex. Lock held until commit_and_respond or on_failure.

    CRITICAL: Do NOT use context manager - lock must persist across steps.
    """
    session_key = ctx.workflow_input()["session_key"]

    # Acquire WITHOUT context manager
    lock = self._redis.lock(
        f"sesslock:{session_key}",
        timeout=300,  # 5min workflow max
    )
    acquired = await lock.acquire(blocking_timeout=10)

    if not acquired:
        raise MutexAcquisitionFailed(session_key)

    # Store lock key for later release (NOT the lock object - not serializable)
    ctx.workflow_state["session_lock_key"] = f"sesslock:{session_key}"

    # Emit ACF event
    await emit_fabric_event(ACFEventType.TURN_STARTED, ...)

    return {"mutex_acquired": True, "session_key": session_key}

@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    # ... commit work ...

    # Explicitly release mutex at end
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._redis.delete(lock_key)

    return {"status": "complete"}

@hatchet.on_failure()
async def handle_failure(self, ctx: Context):
    """Always release lock on failure."""
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._redis.delete(lock_key)

    logger.error("workflow_failed", session_key=ctx.workflow_input().get("session_key"))
```

### Timeline with Correct Mutex Lifecycle

```
Step 1 (acquire_mutex):
  → Redis lock acquired
  → Lock key stored in workflow state
  → Step returns (lock NOT released)

Step 2 (accumulate):
  → Lock still held ✅
  → Process messages

Step 3 (run_pipeline):
  → Lock still held ✅
  → Execute brain phases

Step 4 (commit_and_respond):
  → Lock still held ✅
  → Commit mutations
  → Send response
  → Explicitly delete lock key ← RELEASE HERE
```

### Lock Timeout as Safety Net

Even with explicit release, the lock timeout (300s) acts as a safety net:
- If workflow hangs → lock auto-releases after 5 minutes
- If pod crashes → lock auto-releases after timeout
- Normal operation → explicit release in commit_and_respond

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [01-logical-turn.md](01-logical-turn.md) - Turn model that mutex protects (ACF core)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Durable lock handling (ACF runtime)
- [07-turn-gateway.md](07-turn-gateway.md) - Entry point (absorbed into ACF)
