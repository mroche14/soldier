# ACF Scalability Analysis

> **Date**: 2025-12-15
> **Status**: DESIGN ANALYSIS
> **Scope**: Session Mutex Scaling Strategies

---

## Executive Summary

The ACF (Agent Conversation Fabric) uses a **session mutex** to prevent concurrent brain execution for the same conversation. While this design is correct for data consistency, it presents **scalability challenges** at high concurrency. This document analyzes the problem and proposes solutions.

**Current State**: Single Redis lock per session with 30s timeout, 5s blocking timeout.

**Core Problem**: Lock contention increases linearly with concurrent sessions × messages-per-session.

**Recommended Solution**: Use Hatchet's built-in concurrency controls with `GROUP_ROUND_ROBIN` strategy to replace the Redis mutex entirely.

---

## 1. Current Architecture

### 1.1 Session Mutex Design

```
Lock Key: sesslock:{tenant_id}:{agent_id}:{interlocutor_id}:{channel}
Lock Timeout: 30 seconds (auto-release for deadlock prevention)
Blocking Timeout: 5 seconds (wait time to acquire)
Scope: Entire turn processing (acquire_mutex → commit_and_respond)
```

### 1.2 Workflow Steps (Hatchet)

```
Message arrives
    │
    ▼
┌─────────────────┐
│ acquire_mutex   │  ← Redis LOCK (blocking up to 5s)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ accumulate      │  ← Aggregate messages into LogicalTurn
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ run_agent       │  ← Brain execution (LLM calls, tools)
└────────┬────────┘    Duration: 500ms - 30s depending on complexity
         │
         ▼
┌─────────────────┐
│ commit_respond  │  ← Persist state, send response, release lock
└─────────────────┘
```

### 1.3 Lock Holding Duration

| Phase | Typical Duration | Variable |
|-------|------------------|----------|
| acquire_mutex | 0-5000ms | Depends on contention |
| accumulate | 100-3000ms | Aggregation window |
| run_agent | 500-30000ms | **Highly variable** |
| commit_respond | 50-200ms | DB writes |
| **Total** | **650ms - 38s** | |

**The Problem**: Lock is held during the entire turn, including LLM inference (slow) and tool execution (unpredictable).

---

## 2. Scalability Analysis

### 2.1 Concurrency Model

For N concurrent sessions with M messages per second per session:

```
Lock Operations/second = N × M
Lock Contention = f(N × M × avg_lock_duration)
```

**Example at modest scale (1,000 concurrent conversations)**:
- 1,000 sessions × 0.5 msg/sec = 500 lock operations/second
- Average lock duration: 3 seconds
- Expected contention: ~1,500 locks held at any moment
- Redis single-thread: Can handle ~100k ops/sec (not the bottleneck)
- **Real bottleneck**: Queue depth per session

### 2.2 Failure Modes

| Scale | Sessions | Issue | Symptom |
|-------|----------|-------|---------|
| Small | < 100 | None | Works fine |
| Medium | 100-1,000 | Queue delays | 5s+ response times for fast-typing users |
| Large | 1,000-10,000 | Lock timeouts | "Session busy" errors |
| Very Large | > 10,000 | Redis memory | Lock keys consume memory |

### 2.3 Specific Problem Scenarios

**Scenario 1: Chatty User**
```
User sends 5 messages in 10 seconds
Turn 1: [LOCK held for 8 seconds]
Messages 2,3,4,5: [BLOCKED waiting for lock]
User experience: First response after 8s, then rapid-fire 4 responses
```

**Scenario 2: Slow Tool Execution**
```
Turn 1: Calls external API (15 second timeout)
Message 2 arrives at T+2s
Message 2: [BLOCKED for 13+ seconds]
Lock timeout (30s) may be reached
```

**Scenario 3: LLM Provider Degradation**
```
LLM latency increases from 1s to 10s (provider issue)
All sessions: Lock duration increases 10x
Cascade: All sessions start timing out
```

---

## 3. Solution Analysis

### 3.1 Option A: Hatchet-Native Concurrency (RECOMMENDED)

**Concept**: Leverage Hatchet's built-in concurrency controls to enforce sequential processing per session. No separate Redis mutex or message queue needed.

**Key Discovery**: Hatchet already uses RabbitMQ internally for workflow queuing. By configuring concurrency groups with `expression="input.session_key"` and `max_runs=1`, Hatchet handles all session-level serialization natively.

**Implementation**:
```python
from hatchet_sdk import Hatchet, Context
from hatchet_sdk.concurrency import ConcurrencyLimitStrategy

hatchet = Hatchet()

@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.concurrency(
        expression="input.session_key",  # Group by session
        max_runs=1,                       # Only one at a time per session
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,  # Queue others
    )
    @hatchet.step()
    async def process_turn(self, ctx: Context):
        session_key = ctx.workflow_input()["session_key"]
        messages = ctx.workflow_input()["messages"]

        # No explicit lock needed - Hatchet guarantees single execution
        state = await session_store.get(session_key)
        turn = aggregate_messages(messages, state)
        result = await brain.think(turn, state)
        await session_store.save(session_key, result.new_state)
        await send_response(result.response)

        return {"status": "completed"}
```

**Concurrency Strategies Available**:

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `GROUP_ROUND_ROBIN` | Queue subsequent runs, execute in order | **Default - maintains message order** |
| `CANCEL_IN_PROGRESS` | Cancel current run when new one arrives | Supersede behavior |
| `QUEUE` | Global queue across all keys | Rate limiting |

**Configuration**:
```toml
[acf.concurrency]
enabled = true
strategy = "GROUP_ROUND_ROBIN"  # or "CANCEL_IN_PROGRESS" for supersede
max_runs_per_session = 1
# No Redis lock configuration needed
```

**Handling Supersede**:
```python
# For channels that support supersede (user sends new message, cancel old processing)
@hatchet.workflow()
class SupersedeableWorkflow:
    @hatchet.concurrency(
        expression="input.session_key",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    )
    @hatchet.step()
    async def process_turn(self, ctx: Context):
        # If cancelled, Hatchet raises CancelledError
        # No orphaned locks, no cleanup needed
        ...
```

**Architecture Comparison**:

```
BEFORE (Redis Mutex):
┌─────────────────────────────────────────────────────────────────┐
│  Message → API → Hatchet → acquire_redis_lock → run_pipeline   │
│                            └─── if blocked, wait up to 5s      │
│                            └─── if timeout, return error       │
└─────────────────────────────────────────────────────────────────┘

AFTER (Hatchet-Native):
┌─────────────────────────────────────────────────────────────────┐
│  Message → API → Hatchet.trigger() → [internal RabbitMQ queue] │
│                                       └─── GROUP_ROUND_ROBIN   │
│                                       └─── automatic ordering  │
│                                       └─── no explicit locks   │
└─────────────────────────────────────────────────────────────────┘
```

**Pros**:
- **Zero custom lock code** - Hatchet handles serialization
- **Built-in queuing** - RabbitMQ provides durable message queue
- **Native supersede** - `CANCEL_IN_PROGRESS` handles this cleanly
- **Operational simplicity** - One less system (Redis locks) to monitor
- **Automatic retry** - Hatchet handles failed workflow retries
- **Observability** - Hatchet dashboard shows queue depth, execution time

**Cons**:
- Tied to Hatchet (acceptable since we're already using it)
- Less fine-grained control than custom locks
- Queue visibility through Hatchet only (not Redis CLI)

**Verdict**: **RECOMMENDED** - Simplest, most reliable solution leveraging existing infrastructure.

---

### 3.2 Option B: Message Queue Per Session (Alternative)

**Concept**: Instead of blocking on lock, queue messages and process sequentially.

```
                    ┌─────────────────────────────────┐
                    │     Per-Session Message Queue    │
                    │     (Redis List or Stream)       │
                    └─────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────┐
│                    Queue Consumer                         │
│  - Pops messages from queue                              │
│  - Acquires lock only during state mutation              │
│  - Releases lock quickly                                 │
└──────────────────────────────────────────────────────────┘
```

**Implementation**:
```python
# Instead of blocking on lock acquisition
async def handle_message(message: RawMessage):
    queue_key = f"msgqueue:{message.session_key}"

    # Non-blocking enqueue
    await redis.rpush(queue_key, message.model_dump_json())

    # Trigger processing (idempotent)
    await hatchet.trigger("process_session_queue", {
        "session_key": message.session_key
    })

# Consumer workflow
@hatchet.workflow()
class SessionQueueProcessor:
    @hatchet.step()
    async def process_queue(self, ctx: Context):
        session_key = ctx.workflow_input()["session_key"]

        # Process all queued messages as one logical turn
        messages = await self._drain_queue(session_key)

        if not messages:
            return {"status": "empty"}

        # Short lock for state mutation only
        async with self._session_lock.acquire(session_key, timeout=5):
            turn = self._aggregate_messages(messages)
            result = await self._run_pipeline(turn)
            await self._commit(result)

        # Check if more messages arrived during processing
        if await self._has_pending(session_key):
            await hatchet.trigger("process_session_queue", {
                "session_key": session_key
            })
```

**Pros**:
- No blocking for users (instant acknowledgment)
- Natural batching (multiple messages become one turn)
- Backpressure via queue depth limits

**Cons**:
- Added complexity (queue management)
- Message ordering guarantees needed
- Queue persistence/recovery on failures

**Verdict**: **ALTERNATIVE** - Use if not using Hatchet for orchestration.

---

### 3.3 Option C: Optimistic Concurrency Control (OCC)

**Concept**: No locks. Use version numbers and retry on conflict.

```python
class SessionState(BaseModel):
    version: int  # Incremented on every mutation
    # ... other fields

async def process_turn(session_key: str, turn: LogicalTurn):
    # Read current state with version
    state = await session_store.get(session_key)
    original_version = state.version

    # Process turn (potentially long)
    result = await brain.think(turn, state)

    # Attempt to commit with version check
    success = await session_store.compare_and_swap(
        session_key,
        expected_version=original_version,
        new_state=result.new_state,
    )

    if not success:
        # Conflict: another turn modified state
        # Option 1: Retry with fresh state
        # Option 2: Merge changes
        # Option 3: Fail and notify user
        raise ConflictError("Session modified by concurrent turn")
```

**Pros**:
- No lock contention
- Maximum parallelism for reads
- Works well with read-heavy workloads

**Cons**:
- Conflict resolution is complex (especially for scenario state)
- Wasted work on conflicts (brain ran but results discarded)
- Not suitable for side-effect-heavy turns (can't undo tools)

**Verdict**: **NOT RECOMMENDED alone** - Too risky for turns with side effects.

---

### 3.4 Option D: Sharded Locks

**Concept**: Distribute lock management across multiple Redis instances.

```
Session Key Hash → Shard Selection → Redis Instance N

Shard 0: sesslock:* where hash(key) % 4 == 0
Shard 1: sesslock:* where hash(key) % 4 == 1
Shard 2: sesslock:* where hash(key) % 4 == 2
Shard 3: sesslock:* where hash(key) % 4 == 3
```

**Implementation**:
```python
class ShardedSessionLock:
    def __init__(self, redis_clients: list[Redis], num_shards: int = 4):
        self._clients = redis_clients
        self._num_shards = num_shards

    def _get_shard(self, session_key: str) -> Redis:
        shard_id = hash(session_key) % self._num_shards
        return self._clients[shard_id]

    async def acquire(self, session_key: str) -> Lock:
        redis = self._get_shard(session_key)
        return await redis.lock(f"sesslock:{session_key}").acquire()
```

**Pros**:
- Linear scaling with shard count
- Simple conceptually
- Keeps existing lock semantics

**Cons**:
- Doesn't solve per-session contention (just distributes across Redis)
- Operational complexity (multiple Redis instances)
- Single session still bottlenecked by one Redis

**Verdict**: **USEFUL ADDITION** - Helps with Redis load, not session contention.

---

### 3.5 Option E: Lock Scope Reduction

**Concept**: Hold lock only for critical sections, not entire turn.

```
Current (Full Lock):
[LOCK ──────────────────────────────────────────── UNLOCK]
       accumulate   run_pipeline   commit_respond

Proposed (Scoped Locks):
[LOCK accumulate UNLOCK] [processing...] [LOCK commit UNLOCK]
```

**Implementation**:
```python
async def process_turn(session_key: str, messages: list[RawMessage]):
    # Lock 1: Read and aggregate (short)
    async with session_lock.acquire(session_key, timeout=2):
        state = await session_store.get(session_key)
        turn = aggregate_messages(messages, state)
        state_snapshot = state.model_copy()  # Snapshot for processing

    # Unlocked: Run brain (long, read-only on session state)
    result = await brain.think(turn, state_snapshot)

    # Lock 2: Commit (short)
    async with session_lock.acquire(session_key, timeout=2):
        # Verify state hasn't changed (optimistic check)
        current_state = await session_store.get(session_key)
        if current_state.version != state_snapshot.version:
            raise ConflictError("State changed during processing")

        await session_store.save(session_key, result.new_state)
        await send_response(result.response)
```

**Pros**:
- Lock held for milliseconds, not seconds
- Brain runs without blocking other messages
- Maintains correctness with version check

**Cons**:
- Requires state to be snapshotable
- Conflict handling still needed
- Tool execution complicates things (side effects during unlocked phase)

**Verdict**: **GOOD for read-heavy, RISKY for tool-heavy turns**.

---

### 3.6 Option F: Actor Model (Session as Actor)

**Concept**: Each session is an actor that processes messages sequentially.

```
                 ┌─────────────────────┐
   Message ──────│   Session Actor     │
                 │   (single-threaded) │
   Message ──────│                     │
                 │   Internal queue    │
   Message ──────│   Sequential exec   │
                 └─────────────────────┘
```

**Implementation** (using Python's asyncio):
```python
class SessionActor:
    def __init__(self, session_key: str):
        self.session_key = session_key
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._process_loop())

    async def send(self, message: RawMessage):
        await self._queue.put(message)

    async def _process_loop(self):
        while True:
            message = await self._queue.get()
            try:
                await self._process_message(message)
            except Exception as e:
                logger.error("actor_error", error=str(e))
            finally:
                self._queue.task_done()
```

**Pros**:
- Natural sequential processing per session
- No explicit locking
- Clear mental model

**Cons**:
- Requires actor management (lifecycle, recovery)
- State must be actor-local or carefully synchronized
- Horizontal scaling requires actor sharding (complex)
- Not native to Python ecosystem

**Verdict**: **INTERESTING but COMPLEX** - Better fit for Erlang/Akka.

---

### 3.7 Option G: Hybrid Queue + OCC

**Concept**: Combine message queue with optimistic concurrency.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Message Queue                             │
│  - Instant enqueue (never blocks user)                          │
│  - Ordered per session                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Queue Consumer                               │
│  - Drains queue into LogicalTurn                                │
│  - Reads session state (no lock)                                │
│  - Runs Brain with snapshot                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Commit with CAS                                │
│  - Check version unchanged                                      │
│  - Atomic commit OR retry                                       │
│  - Lock only for side-effect tools                             │
└─────────────────────────────────────────────────────────────────┘
```

**Key Innovation**: Lock ONLY when executing side-effect tools.

```python
async def process_turn(session_key: str, turn: LogicalTurn):
    # Read without lock
    state = await session_store.get(session_key)

    # Process brain (mostly unlocked)
    result = await brain.think(turn, state)

    # For each tool with side effects
    for tool in result.planned_tools:
        if tool.has_side_effects:
            # Lock only for side-effect tools
            async with session_lock.acquire(session_key, timeout=5):
                # Verify state, execute tool, update state
                current = await session_store.get(session_key)
                if current.version != state.version:
                    # Handle conflict (rollback plan, retry, etc.)
                    return self._handle_conflict(turn, current)

                tool_result = await toolbox.execute(tool)
                state = state.with_tool_result(tool_result)
                await session_store.save(session_key, state)

    # Final commit with CAS
    success = await session_store.compare_and_swap(
        session_key,
        expected_version=state.version,
        new_state=result.final_state,
    )

    if not success:
        # Conflict on final commit
        return self._handle_final_conflict(turn)
```

**Pros**:
- Lock held only during actual mutations
- Conflicts handled gracefully
- Tool execution remains safe
- Best throughput for mixed workloads

**Cons**:
- Most complex implementation
- Requires careful conflict resolution design
- Tool rollback strategy needed

**Verdict**: **BEST for production scale** - Worth the complexity.

---

## 4. Recommended Architecture

### 4.1 Primary Solution: Hatchet-Native Concurrency

The recommended approach is to leverage Hatchet's built-in concurrency controls, eliminating the need for a separate Redis mutex.

**Implementation Steps**:

1. **Configure LogicalTurnWorkflow with concurrency decorator**:
```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.concurrency(
        expression="input.session_key",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    )
    @hatchet.step()
    async def process_turn(self, ctx: Context):
        # Hatchet guarantees only one instance runs per session_key
        session_key = ctx.workflow_input()["session_key"]
        messages = ctx.workflow_input()["messages"]

        state = await session_store.get(session_key)
        turn = aggregate_messages(messages, state)
        result = await brain.think(turn, state)
        await session_store.save(session_key, result.new_state)
        await send_response(result.response)
```

2. **Remove Redis lock code** from `acquire_mutex` step (no longer needed)

3. **Configure TOML**:
```toml
[acf.concurrency]
enabled = true
strategy = "GROUP_ROUND_ROBIN"
max_runs_per_session = 1

# DEPRECATED - no longer used with Hatchet-native concurrency
# [acf.mutex]
# lock_timeout = 30
# blocking_timeout = 5
```

**Effort**: 1 week
**Impact**: Eliminates Redis lock contention, automatic message queuing via RabbitMQ

### 4.2 Channel-Specific Strategy (Optional Enhancement)

Different channels may benefit from different strategies:

```python
def get_concurrency_strategy(channel: str) -> ConcurrencyLimitStrategy:
    """Select strategy based on channel characteristics."""
    # WhatsApp: Users can send multiple messages quickly
    # Queue them and process in order
    if channel in ("whatsapp", "sms", "telegram"):
        return ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN

    # Web chat with "typing..." indicator:
    # User sending new message likely means they want to supersede
    if channel in ("web", "mobile_app"):
        return ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS

    # Default: Queue and process in order
    return ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN
```

**Effort**: Additional 3-5 days
**Impact**: Better UX per channel type

### 4.3 Future Enhancement: Tool-Scoped Locks (Deferred)

For tools with side effects, additional locking may be needed at the ToolGateway/ToolHub level. This is **deferred** to the separate ToolGateway implementation work.

```python
# Future consideration for ToolGateway
class SideEffectPolicy(str, Enum):
    SAFE = "safe"              # No lock needed
    IDEMPOTENT = "idempotent"  # Idempotency key protects
    COMPENSATABLE = "compensatable"  # Short lock during execution
    IRREVERSIBLE = "irreversible"    # Lock + confirmation required
```

**Status**: Deferred to ToolGateway/ToolHub implementation

---

## 5. Monitoring & Alerting

### 5.1 Key Metrics (Hatchet-Native)

With Hatchet handling concurrency, monitoring shifts to Hatchet workflow metrics:

```python
# Workflow queue depth per session_key pattern
hatchet_queue_depth_gauge = Gauge(
    "acf_hatchet_queue_depth",
    "Number of workflows queued per concurrency group",
    ["tenant_id", "strategy"],
)

# Workflow execution time
workflow_duration_seconds = Histogram(
    "acf_workflow_duration_seconds",
    "Total workflow execution time",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

# Cancelled workflows (from CANCEL_IN_PROGRESS strategy)
workflow_cancelled_counter = Counter(
    "acf_workflow_cancelled_total",
    "Workflows cancelled due to supersede",
    ["channel"],
)

# Workflow completion status
workflow_status_counter = Counter(
    "acf_workflow_status_total",
    "Workflow completion status",
    ["status"],  # completed, failed, cancelled
)
```

**Hatchet Dashboard**: The Hatchet UI provides built-in visibility into:
- Queue depths per concurrency group
- Workflow execution times
- Failed/cancelled workflows
- Worker health

### 5.2 Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Workflow duration P95 | > 10s | > 25s |
| Hatchet queue depth | > 10 | > 50 |
| Workflow failure rate | > 1% | > 5% |
| Cancelled workflow rate | > 10% | > 30% |
| Worker backlog | > 100 | > 500 |

---

## 6. Migration Path

### 6.1 Backward Compatibility

Hatchet-native concurrency is **backward compatible**:
- Existing API contracts unchanged
- Session state format unchanged
- No changes to SessionStore interface
- Redis still used for session state, just not for locks

### 6.2 Configuration

```toml
[acf.concurrency]
# Enable Hatchet-native concurrency
enabled = true
strategy = "GROUP_ROUND_ROBIN"  # or "CANCEL_IN_PROGRESS"
max_runs_per_session = 1

# DEPRECATED - will be removed
# [acf.mutex]
# enabled = false  # Disable Redis mutex
```

### 6.3 Rollout Strategy

1. **Dev/Staging**: Deploy with Hatchet concurrency, verify queue behavior
2. **Canary**: Enable for 5% of production traffic
3. **Measure**: Workflow duration, queue depth, cancellation rates
4. **Expand**: 25% → 50% → 100%
5. **Cleanup**: Remove Redis lock code after full rollout

---

## 7. Conclusion

The current ACF Redis mutex design is **correct but not scalable**. The recommended solution is **Hatchet-native concurrency**, which eliminates custom lock code entirely by leveraging Hatchet's built-in concurrency controls.

**Key Decision**: Use Hatchet's `@hatchet.concurrency()` decorator with `GROUP_ROUND_ROBIN` strategy instead of custom Redis locks.

**Why Hatchet-Native**:
1. **Simpler** - No custom lock code to maintain
2. **Reliable** - Hatchet handles queuing via RabbitMQ
3. **Observable** - Built-in dashboard for queue monitoring
4. **Flexible** - `CANCEL_IN_PROGRESS` strategy available for supersede behavior

**Implementation Path**:
1. **Week 1**: Add concurrency decorator to LogicalTurnWorkflow
2. **Week 1**: Remove Redis lock acquisition from workflow
3. **Week 2**: Deploy to staging, validate behavior
4. **Week 3+**: Gradual production rollout

**Expected Outcomes**:
- Redis lock contention: **Eliminated**
- Custom lock code: **Removed**
- Message queuing: **Automatic** (via RabbitMQ)
- Supersede support: **Native** (via `CANCEL_IN_PROGRESS`)

**Total Effort**: 1-2 weeks for core implementation + 1 week for rollout
**Deferred**: Tool-scoped locks (handled separately in ToolGateway/ToolHub)

---

## Appendix: Alternative Reference Implementations

> **Note**: These implementations are provided for reference if Hatchet-native concurrency is not suitable. The recommended approach is to use Hatchet's built-in concurrency controls (see Section 3.1).

### A.1 Redis Streams for Message Queue (Alternative to Hatchet-Native)

```python
class RedisStreamMessageQueue:
    def __init__(self, redis: Redis):
        self._redis = redis

    async def enqueue(self, session_key: str, message: RawMessage) -> str:
        stream_key = f"msgstream:{session_key}"
        message_id = await self._redis.xadd(
            stream_key,
            {"data": message.model_dump_json()},
            maxlen=100,  # Cap queue depth
        )
        return message_id

    async def drain(self, session_key: str) -> list[RawMessage]:
        stream_key = f"msgstream:{session_key}"
        entries = await self._redis.xread(
            {stream_key: "0"},
            count=50,
            block=0,
        )

        messages = []
        for entry in entries:
            msg = RawMessage.model_validate_json(entry["data"])
            messages.append(msg)
            await self._redis.xdel(stream_key, entry["id"])

        return messages
```

### A.2 Compare-and-Swap for Session State

```python
class SessionStoreWithCAS:
    async def compare_and_swap(
        self,
        session_key: str,
        expected_version: int,
        new_state: SessionState,
    ) -> bool:
        # Lua script for atomic CAS
        script = """
        local current = redis.call('HGET', KEYS[1], 'version')
        if current == ARGV[1] then
            redis.call('HSET', KEYS[1], 'data', ARGV[2])
            redis.call('HSET', KEYS[1], 'version', ARGV[3])
            return 1
        else
            return 0
        end
        """
        result = await self._redis.eval(
            script,
            1,
            f"session:{session_key}",
            str(expected_version),
            new_state.model_dump_json(),
            str(new_state.version),
        )
        return result == 1
```
