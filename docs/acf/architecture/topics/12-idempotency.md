# Idempotency

> **ACF Component**: Safety layer for restart-friendly architecture
> **Topic**: Preventing duplicate side-effects when ACF restarts, retries, or supersedes turns
> **Dependencies**: LogicalTurn, SideEffectPolicy, Hatchet workflows
> **Impacts**: Tool execution safety, supersede correctness, crash recovery
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for the authoritative ACF specification

---

## Three-Layer Idempotency Architecture

Idempotency in ACF operates at **three separate layers**, not one unified system:

| Layer | Location | Key Format | TTL | Protects |
|-------|----------|------------|-----|----------|
| **API** | Before workflow | `{tenant}:{client_idem_key}` | 5min | Duplicate HTTP requests |
| **Beat** | After accumulation | `{tenant}:beat:{session}:{msg_hash}` | 60s | Duplicate turn processing |
| **Tool** | During P7 tool execution | `{tool}:{business_key}:turn_group:{turn_group_id}` | 24hrs | Duplicate business actions |

### Layer 1: API Idempotency

Prevents duplicate HTTP requests from creating duplicate workflows:

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    if request.idempotency_key:
        cached = await idem_cache.get(f"{request.tenant_id}:{request.idempotency_key}")
        if cached:
            return cached  # Return cached response, no workflow started
    # ... process ...
```

### Layer 2: Beat Idempotency

Prevents the same logical turn from being processed twice:

```python
beat_key = f"{tenant_id}:beat:{session_key}:{hash(sorted_message_ids)}"
if await beat_cache.exists(beat_key):
    return "already_processing"
await beat_cache.set(beat_key, turn.id, ttl=60)
```

### Layer 3: Tool Idempotency

Prevents the same tool from executing twice for the same conversation attempt, using `turn_group_id`:

```python
def build_tool_idempotency_key(
    tool_name: str,
    business_key: str,
    turn: LogicalTurn,
) -> str:
    """
    Includes turn_group_id to scope idempotency to conversation attempt.

    - Supersede chain shares turn_group_id → one execution
    - QUEUE creates new turn_group_id → allows re-execution
    """
    return f"{tool_name}:{business_key}:turn_group:{turn.turn_group_id}"
```

---

## ACF Context: Why Idempotency is Critical

**Idempotency is not a generic best practice—it's directly required by ACF's architecture.**

ACF intentionally creates scenarios where duplicate execution can happen:

| ACF Feature | Creates Risk Of |
|-------------|-----------------|
| **Supersede** restarts from checkpoint | Re-running tools that already executed |
| **Hatchet retries** after crash/timeout | Re-executing failed step including tools |
| **Message absorption** triggers re-run | Brain may reach same tool call again |
| **Workflow resume** after pod failure | Continuing from uncertain state |

Without idempotency, these safe restart mechanisms become dangerous:
- Double refund
- Double booking
- Duplicate ticket creation
- Duplicated CRM updates

**Idempotency is the safety net that makes ACF's restart-friendly design actually safe.**

---

## Overview

**Idempotency** ensures that repeated requests produce the same result without side effects. In ACF context, this means:
- **Supersede safety**: Restarting a turn won't re-execute completed tools
- **Crash recovery**: Hatchet workflow retries won't duplicate effects
- **Artifact reuse**: Cached brain outputs are validated before reuse
- **Tool execution**: Same idempotency key = same real-world effect (once)

### Key Change: Beat-Level Idempotency

With LogicalTurn architecture, idempotency operates at the **beat level**, not the raw message level:

```
Old: idempotency_key = hash(single_message)
New: idempotency_key = logical_turn.id OR hash(sorted_message_ids)
```

This ensures that a multi-message beat produces one response, and retries of any message in the beat return the same result.

---

## Fingerprints and Artifact Reuse

ACF uses three fingerprint concepts to safely manage artifact reuse and idempotency:

### `input_fp` (Input Fingerprint)

A stable hash representing the **LogicalTurn inputs**:

```python
input_fp = hash(
    tenant_id,
    agent_id,
    session_key,
    channel,
    normalized_messages,  # ordered, sanitized
)
```

**Purpose**: If inputs are identical, cached brain artifacts *might* be reusable.

**Contains**:
- LogicalTurn message content + order
- Channel identifier
- Key metadata affecting meaning
- Sanitized customer context pointers (not raw PII)

### `dep_fp` (Dependency Fingerprint)

A hash representing **versions of things that affect semantics**:

```python
dep_fp = hash(
    scenario_set_version,
    rules_version,
    kb_version,
    agent_config_version,
    tool_registry_version,
)
```

**Purpose**: Even if user messages are the same, you should NOT reuse artifacts if the **meaning engine** changed.

**Why this matters**: You have a scenario migration protocol. `dep_fp` is how ACF respects version changes—if `dep_fp` differs, cached artifacts from the old version are invalid.

### `reuse_decl` (Reuse Declaration)

Brain-owned policy declaring what can be reused and when:

```python
reuse_decl = {
    "parsing": {"scope": "same_input"},
    "intent_candidates": {"scope": "same_input_same_dep"},
    "retrieval_candidates": {"scope": "same_input_same_dep"},
    "tool_plan": {"scope": "same_input_same_dep", "requires_revalidate": True},
    "tool_results": {"scope": "never"},  # unless idempotency keys present
}
```

**Purpose**: Keep domain knowledge in the Brain. ACF enforces, Brain declares.

### How Fingerprints Relate to Idempotency

| Concept | Protects Against |
|---------|------------------|
| `input_fp` + `dep_fp` + `reuse_decl` | Wasted computation, semantic mismatch |
| **Idempotency keys** | Duplicate real-world actions |

They solve different failure modes:
- **Artifact reuse** = "don't recompute"
- **Idempotency** = "don't re-execute effects"

Even if you reuse artifacts, you still need idempotency when:
- A turn is superseded and restarts
- A workflow retries after timeout
- A commit is re-attempted after crash

---

## Concrete Example: Supersede + Idempotency

User sends two messages in quick succession:

```
Message 1: "Refund my order"
Message 2: "Order #12345"  (500ms later)
```

**Without idempotency:**

```
Timeline:
  T+0ms    Turn A starts, processing "Refund my order"
  T+500ms  Message 2 arrives → ACF decides ABSORB
  T+600ms  Turn A restarts from checkpoint with both messages
  T+800ms  Brain reaches refund tool (first time in restarted turn)
  T+850ms  Meanwhile, original Turn A also reaches refund tool (race condition)
  T+900ms  TWO refund calls execute → customer refunded twice
```

**With idempotency:**

```
Timeline:
  T+0ms    Turn A starts, processing "Refund my order"
  T+500ms  Message 2 arrives → ACF decides ABSORB
  T+600ms  Turn A restarts from checkpoint with both messages
  T+800ms  Brain proposes refund tool with idempotency key:
           "refund:order:12345:turn_group:XYZ"
  T+850ms  Original Turn A also proposes refund (same key)
  T+900ms  Business system sees duplicate key → executes once
  T+950ms  Both calls return same result → customer refunded once
```

**Key insight**: The idempotency key includes the logical turn group, not just the order ID. This ensures:
- Same user + same order + same conversation = one refund
- Different conversation about same order = allowed (new turn group)

### Tool Idempotency Key Construction

```python
def build_tool_idempotency_key(
    tool_name: str,
    tool_args: dict,
    logical_turn: LogicalTurn,
) -> str:
    """
    Build idempotency key for tool execution.

    Includes logical_turn.turn_group_id to scope idempotency
    to this conversation flow, not globally.
    """
    # Extract business key from tool args
    business_key = extract_business_key(tool_name, tool_args)
    # e.g., "order:12345" for refund tool

    return f"{tool_name}:{business_key}:turn_group:{logical_turn.turn_group_id}"
```

---

## Idempotency Key Strategies

### Strategy 1: Client-Provided Key

Client explicitly provides an idempotency key:

```python
# API Request
POST /chat
{
    "message": "Hello",
    "idempotency_key": "client-generated-uuid-123"
}
```

**Pros**: Client controls deduplication
**Cons**: Requires client implementation

### Strategy 2: Turn-Based Key

Use LogicalTurn ID as idempotency key:

```python
# After turn is created/identified
idempotency_key = f"{tenant_id}:{logical_turn.id}"
```

**Pros**: Automatic, covers multi-message beats
**Cons**: Requires turn identification first

### Strategy 3: Content Hash

Hash the request content:

```python
def compute_idempotency_key(
    tenant_id: UUID,
    customer_id: UUID,
    messages: list[str],
    timestamp_bucket: int,  # e.g., 5-minute buckets
) -> str:
    content = {
        "tenant_id": str(tenant_id),
        "customer_id": str(customer_id),
        "messages": sorted(messages),  # Order-independent
        "bucket": timestamp_bucket,
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()
    ).hexdigest()[:32]
```

**Pros**: No client coordination needed
**Cons**: Time-sensitive, may miss some duplicates

---

## Implementation

### IdempotencyCache

```python
from datetime import datetime, timedelta
from redis.asyncio import Redis

class IdempotencyCache:
    """
    Cache for idempotent request handling.

    Stores request fingerprints and responses for deduplication.
    """

    def __init__(
        self,
        redis: Redis,
        default_ttl: timedelta = timedelta(hours=24),
    ):
        self._redis = redis
        self._default_ttl = default_ttl

    def _key(self, idempotency_key: str) -> str:
        return f"idempotency:{idempotency_key}"

    async def check_and_set(
        self,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> IdempotencyCheckResult:
        """
        Check if request is duplicate and mark as processing.

        Returns:
            PROCESSING_STARTED: New request, now marked as processing
            DUPLICATE_PROCESSING: Another request with same key is processing
            DUPLICATE_COMPLETED: Same request already completed
            FINGERPRINT_MISMATCH: Same key but different request content
        """
        key = self._key(idempotency_key)

        # Try to acquire processing lock
        # Value format: "processing:{fingerprint}" or "complete:{fingerprint}:{response}"
        result = await self._redis.get(key)

        if result is None:
            # New request - mark as processing
            success = await self._redis.set(
                key,
                f"processing:{request_fingerprint}",
                ex=int(self._default_ttl.total_seconds()),
                nx=True,  # Only if not exists
            )
            if success:
                return IdempotencyCheckResult(
                    status=IdempotencyStatus.PROCESSING_STARTED,
                )
            # Another request beat us - retry check
            result = await self._redis.get(key)

        # Parse existing value
        if result.startswith(b"processing:"):
            stored_fingerprint = result.decode().split(":", 1)[1]
            if stored_fingerprint == request_fingerprint:
                return IdempotencyCheckResult(
                    status=IdempotencyStatus.DUPLICATE_PROCESSING,
                )
            else:
                return IdempotencyCheckResult(
                    status=IdempotencyStatus.FINGERPRINT_MISMATCH,
                    stored_fingerprint=stored_fingerprint,
                )

        elif result.startswith(b"complete:"):
            parts = result.decode().split(":", 2)
            stored_fingerprint = parts[1]
            stored_response = parts[2] if len(parts) > 2 else None

            if stored_fingerprint == request_fingerprint:
                return IdempotencyCheckResult(
                    status=IdempotencyStatus.DUPLICATE_COMPLETED,
                    cached_response=stored_response,
                )
            else:
                return IdempotencyCheckResult(
                    status=IdempotencyStatus.FINGERPRINT_MISMATCH,
                    stored_fingerprint=stored_fingerprint,
                )

        # Unknown format - treat as new
        return IdempotencyCheckResult(
            status=IdempotencyStatus.PROCESSING_STARTED,
        )

    async def mark_complete(
        self,
        idempotency_key: str,
        request_fingerprint: str,
        response: str,
        ttl: timedelta | None = None,
    ) -> None:
        """Mark request as completed with response."""
        key = self._key(idempotency_key)
        ttl = ttl or self._default_ttl

        await self._redis.set(
            key,
            f"complete:{request_fingerprint}:{response}",
            ex=int(ttl.total_seconds()),
        )

    async def mark_failed(
        self,
        idempotency_key: str,
    ) -> None:
        """Remove processing marker on failure (allows retry)."""
        key = self._key(idempotency_key)
        await self._redis.delete(key)


class IdempotencyStatus(str, Enum):
    PROCESSING_STARTED = "processing_started"
    DUPLICATE_PROCESSING = "duplicate_processing"
    DUPLICATE_COMPLETED = "duplicate_completed"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"


class IdempotencyCheckResult(BaseModel):
    status: IdempotencyStatus
    cached_response: str | None = None
    stored_fingerprint: str | None = None
```

---

## API Integration

### Chat Endpoint

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    idempotency_cache: IdempotencyCache = Depends(get_idempotency_cache),
    turn_gateway: TurnGateway = Depends(get_turn_gateway),
):
    # Compute request fingerprint
    fingerprint = compute_request_fingerprint(request)

    # Determine idempotency key
    if request.idempotency_key:
        # Client-provided key
        idem_key = f"{request.tenant_id}:{request.idempotency_key}"
    else:
        # Auto-generate from content
        idem_key = compute_idempotency_key(
            tenant_id=request.tenant_id,
            customer_id=request.customer_id,
            messages=[request.message],
            timestamp_bucket=int(time.time() // 300),  # 5-min bucket
        )

    # Check idempotency
    check_result = await idempotency_cache.check_and_set(idem_key, fingerprint)

    if check_result.status == IdempotencyStatus.DUPLICATE_COMPLETED:
        # Return cached response
        logger.info(
            "idempotent_cache_hit",
            idempotency_key=idem_key,
        )
        return ChatResponse.model_validate_json(check_result.cached_response)

    if check_result.status == IdempotencyStatus.DUPLICATE_PROCESSING:
        # Another request is processing - return 409 or wait
        raise HTTPException(
            status_code=409,
            detail="Request is being processed. Retry in a moment.",
        )

    if check_result.status == IdempotencyStatus.FINGERPRINT_MISMATCH:
        # Same key, different content - reject
        raise HTTPException(
            status_code=422,
            detail="Idempotency key already used with different request",
        )

    # Process request
    try:
        decision = await turn_gateway.receive_message(
            UserMessage(
                tenant_id=request.tenant_id,
                customer_id=request.customer_id,
                channel=request.channel,
                content=request.message,
                idempotency_key=idem_key,
            )
        )

        response = ChatResponse(
            status="processing",
            turn_id=decision.turn_id,
        )

        # Note: Full response cached when turn completes (in workflow)

        return response

    except Exception as e:
        # Allow retry on failure
        await idempotency_cache.mark_failed(idem_key)
        raise
```

### Workflow Integration

Cache response when turn completes:

```python
@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    # ... generate response ...

    # Cache for idempotency
    idempotency_key = ctx.workflow_input().get("idempotency_key")
    if idempotency_key:
        await ctx.services.idempotency_cache.mark_complete(
            idempotency_key=idempotency_key,
            request_fingerprint=ctx.workflow_input()["fingerprint"],
            response=response.model_dump_json(),
        )

    # Send response
    await channel_adapter.send_response(...)

    return {"status": "complete"}
```

---

## Beat-Level Idempotency

With multi-message beats, idempotency must cover the entire beat:

```python
class BeatIdempotencyManager:
    """Manage idempotency at the LogicalTurn (beat) level."""

    def __init__(self, cache: IdempotencyCache):
        self._cache = cache

    async def check_beat(
        self,
        turn: LogicalTurn,
        tenant_id: UUID,
    ) -> IdempotencyCheckResult:
        """
        Check if this beat has already been processed.

        Uses sorted message IDs to ensure consistency
        regardless of message arrival order.
        """
        # Create deterministic key from beat messages
        message_hash = hashlib.sha256(
            ":".join(sorted(str(m) for m in turn.messages)).encode()
        ).hexdigest()[:16]

        beat_key = f"{tenant_id}:beat:{turn.session_key}:{message_hash}"

        return await self._cache.check_and_set(
            idempotency_key=beat_key,
            request_fingerprint=str(turn.id),
        )

    async def mark_beat_complete(
        self,
        turn: LogicalTurn,
        tenant_id: UUID,
        response: str,
    ) -> None:
        """Mark beat as completed."""
        message_hash = hashlib.sha256(
            ":".join(sorted(str(m) for m in turn.messages)).encode()
        ).hexdigest()[:16]

        beat_key = f"{tenant_id}:beat:{turn.session_key}:{message_hash}"

        await self._cache.mark_complete(
            idempotency_key=beat_key,
            request_fingerprint=str(turn.id),
            response=response,
        )
```

---

## Streaming Considerations

SSE/streaming endpoints cannot use traditional idempotency:

```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming endpoint - idempotency handled differently.

    Since we can't cache a stream, we:
    1. Check if request is duplicate of completed request → return error
    2. Check if request is duplicate of in-flight request → return existing stream
    3. Otherwise, start new stream
    """

    # Check for completed duplicate
    check_result = await idempotency_cache.check_and_set(...)

    if check_result.status == IdempotencyStatus.DUPLICATE_COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="This request was already completed. Use non-streaming endpoint to get response.",
        )

    if check_result.status == IdempotencyStatus.DUPLICATE_PROCESSING:
        # Could potentially redirect to existing stream
        # For simplicity, just error
        raise HTTPException(
            status_code=409,
            detail="Request is being processed",
        )

    # Start streaming
    return EventSourceResponse(generate_stream(...))
```

---

## Configuration

```toml
[idempotency]
enabled = true

# Cache TTL
default_ttl_hours = 24
processing_ttl_seconds = 300  # Max time in "processing" state

# Key generation
auto_generate_keys = true
timestamp_bucket_seconds = 300  # 5 minutes

# Redis configuration
key_prefix = "idempotency"
```

---

## Observability

### Metrics

```python
# Cache operations
idempotency_check = Counter(
    "idempotency_check_total",
    "Idempotency cache checks",
    ["status"],  # processing_started, duplicate_completed, etc.
)

idempotency_cache_hit = Counter(
    "idempotency_cache_hit_total",
    "Requests served from idempotency cache",
)

# Key types
idempotency_key_type = Counter(
    "idempotency_key_type_total",
    "Idempotency key types used",
    ["type"],  # client_provided, auto_generated, beat_based
)
```

### Logging

```python
logger.info(
    "idempotency_check",
    idempotency_key=idem_key[:20] + "...",  # Truncate for privacy
    status=check_result.status.value,
    cached=check_result.cached_response is not None,
)
```

---

## Testing

```python
# Test: Duplicate request returns cached response
async def test_duplicate_returns_cached():
    # First request
    response1 = await client.post("/chat", json={
        "message": "Hello",
        "idempotency_key": "test-key-1",
    })
    assert response1.status_code == 200

    # Mark complete
    await idempotency_cache.mark_complete(
        "tenant:test-key-1",
        fingerprint,
        response1.json(),
    )

    # Duplicate request
    response2 = await client.post("/chat", json={
        "message": "Hello",
        "idempotency_key": "test-key-1",
    })

    assert response2.status_code == 200
    assert response2.json() == response1.json()

# Test: Different content with same key rejected
async def test_fingerprint_mismatch_rejected():
    # First request
    await client.post("/chat", json={
        "message": "Hello",
        "idempotency_key": "test-key-2",
    })

    # Different content, same key
    response = await client.post("/chat", json={
        "message": "Goodbye",  # Different!
        "idempotency_key": "test-key-2",
    })

    assert response.status_code == 422

# Test: Beat-level idempotency
async def test_beat_idempotency():
    # Create beat with two messages
    turn = LogicalTurn(
        messages=[uuid4(), uuid4()],
        ...
    )

    # First check
    result1 = await beat_manager.check_beat(turn, tenant_id)
    assert result1.status == IdempotencyStatus.PROCESSING_STARTED

    # Same messages, same result
    result2 = await beat_manager.check_beat(turn, tenant_id)
    assert result2.status == IdempotencyStatus.DUPLICATE_PROCESSING
```

---

## Summary: The Shortest Definitions

| Concept | Definition |
|---------|------------|
| **Idempotency** | Calling this tool twice with the same key results in one real-world effect |
| **`input_fp`** | Hash of the logical-turn inputs |
| **`dep_fp`** | Hash of the meaning dependencies (rules/scenarios/KB/config/tool registry versions) |
| **`reuse_decl`** | Brain's explicit declaration of what artifacts are safe to reuse under which conditions |

---

## Related Topics

- [ACF_SPEC.md](../ACF_SPEC.md) - Authoritative ACF specification (ACF)
- [01-logical-turn.md](01-logical-turn.md) - Beat-level processing, SupersedeDecision (ACF)
- [04-side-effect-policy.md](04-side-effect-policy.md) - Tool policies, side-effect classification (Toolbox)
- [05-checkpoint-reuse.md](05-checkpoint-reuse.md) - Artifact reuse, ReusePolicy (ACF/Brain boundary)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Workflow retries, crash recovery (ACF runtime)
- [07-turn-gateway.md](07-turn-gateway.md) - Request entry point (ACF ingress)
