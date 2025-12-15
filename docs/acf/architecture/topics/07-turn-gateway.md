# Turn Gateway

> **Topic**: Entry point for message ingress and turn orchestration
> **ACF Component**: Message ingress, absorbed into Agent Conversation Fabric
> **Dependencies**: LogicalTurn, Session Mutex, Hatchet Integration
> **Impacts**: All message processing, workflow triggering
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification

---

## ACF Context

The Turn Gateway is **absorbed into ACF** as the message ingress layer. It's not a separate component—it's how messages enter the Agent Conversation Fabric.

### ACF Ownership

| Aspect | Owner | Description |
|--------|-------|-------------|
| Message Reception | ACF | Receives RawMessage from channel adapters |
| Workflow Discovery | ACF | Finds active workflow for session |
| Workflow Triggering | ACF | Starts new LogicalTurnWorkflow |
| Event Routing | ACF | Routes messages to existing workflows |
| Rate Limiting | ACF | Optional, before workflow |
| Abuse Detection | ACF | Optional, before workflow |

### Position in ACF Architecture

The Turn Gateway is the **entry boundary** of ACF:

```
Channel Adapters → [Turn Gateway] → ACF Workflows → Brain
                   ╰─────────────────╯
                     This is ACF's ingress
```

---

## Overview

The **Turn Gateway** is the single entry point for all incoming user messages. It decides how to handle each message:
- Start a new LogicalTurn workflow (ACF)
- Signal an existing workflow to absorb the message (ACF event)
- Queue the message if the session is busy

### Position in Architecture

```
                    ┌────────────────────────────────────────┐
                    │            Channel Adapters            │
                    │  (WhatsApp, SMS, Web, Email, Voice)   │
                    └─────────────────┬──────────────────────┘
                                      │
                                      ▼
                    ┌────────────────────────────────────────┐
                    │            TURN GATEWAY                │
                    │  - Route to workflow                   │
                    │  - Trigger or signal                   │
                    │  - Handle edge cases                   │
                    └─────────────────┬──────────────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ▼                         ▼
              ┌──────────────────┐      ┌──────────────────┐
              │  New Workflow    │      │  Signal Workflow │
              │  (first message) │      │  (absorb message)│
              └──────────────────┘      └──────────────────┘
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                    ┌────────────────────────────────────────┐
                    │          Hatchet Workflows             │
                    │       (LogicalTurnWorkflow)            │
                    └────────────────────────────────────────┘
```

---

## Core Implementation

```python
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from soldier.alignment.models.logical_turn import LogicalTurn, LogicalTurnStatus
from soldier.alignment.gateway.session_lock import SessionLock

class TurnAction(str, Enum):
    """Actions the gateway can take."""
    WORKFLOW_STARTED = "workflow_started"    # New workflow triggered
    EVENT_SENT = "event_sent"                # Event sent to existing workflow
    QUEUED = "queued"                        # Message queued for later
    REJECTED = "rejected"                    # Message rejected (rate limit, etc.)

class TurnDecision(BaseModel):
    """Result of gateway processing."""
    action: TurnAction
    turn_id: UUID | None = None
    workflow_run_id: str | None = None
    queue_position: int | None = None
    rejection_reason: str | None = None


class ActiveTurnIndex:
    """
    O(1) index for finding active workflows by session_key.

    Uses Redis to store session_key → workflow_run_id mappings.
    Updated when workflows start (set) and complete (clear).

    This avoids the O(n) scan anti-pattern of list_workflow_runs().
    """

    def __init__(self, redis: Redis):
        self._redis = redis

    def _key(self, session_key: str) -> str:
        return f"active_turn:{session_key}"

    async def set(self, session_key: str, workflow_run_id: str, ttl: int = 300) -> None:
        """Register active workflow for session. TTL prevents stale entries."""
        await self._redis.set(self._key(session_key), workflow_run_id, ex=ttl)

    async def get_workflow_run_id(self, session_key: str) -> str | None:
        """Get workflow_run_id for session, or None if no active workflow."""
        return await self._redis.get(self._key(session_key))

    async def clear(self, session_key: str) -> None:
        """Clear index when workflow completes."""
        await self._redis.delete(self._key(session_key))


class TurnGateway:
    """
    Single entry point for all incoming messages.

    Responsibilities:
    1. Build session key from message context
    2. Check for existing active workflows
    3. Decide: start new workflow, signal existing, or queue
    4. Handle rate limiting and abuse detection
    """

    def __init__(
        self,
        hatchet_client: Hatchet,
        turn_store: LogicalTurnStore,
        active_turn_index: ActiveTurnIndex,  # O(1) workflow lookup
        message_queue: MessageQueue,
        rate_limiter: RateLimiter,
        abuse_detector: AbuseDetector | None = None,
    ):
        self._hatchet = hatchet_client
        self._turn_store = turn_store
        self._active_turn_index = active_turn_index
        self._message_queue = message_queue
        self._rate_limiter = rate_limiter
        self._abuse_detector = abuse_detector

    async def receive_message(
        self,
        message: UserMessage,
    ) -> TurnDecision:
        """
        Process an incoming message.

        Args:
            message: The incoming user message

        Returns:
            TurnDecision indicating what action was taken
        """
        # 1. Build session key
        session_key = self._build_session_key(message)

        # 2. Rate limiting check
        if not await self._rate_limiter.allow(
            tenant_id=message.tenant_id,
            customer_id=message.customer_id,
        ):
            logger.warning(
                "message_rate_limited",
                session_key=session_key,
                message_id=str(message.id),
            )
            return TurnDecision(
                action=TurnAction.REJECTED,
                rejection_reason="rate_limit_exceeded",
            )

        # 3. Abuse detection (if enabled)
        if self._abuse_detector:
            abuse_result = await self._abuse_detector.check(message)
            if abuse_result.is_abusive:
                logger.warning(
                    "message_abuse_detected",
                    session_key=session_key,
                    abuse_type=abuse_result.abuse_type,
                )
                return TurnDecision(
                    action=TurnAction.REJECTED,
                    rejection_reason=f"abuse_detected:{abuse_result.abuse_type}",
                )

        # 4. Check for existing active workflow (O(1) indexed lookup)
        workflow_run_id = await self._find_active_workflow(session_key)

        if workflow_run_id is None:
            # No active workflow - start new one
            return await self._start_new_workflow(message, session_key)
        else:
            # Active workflow exists - signal it with new message
            return await self._signal_existing_workflow(
                message, workflow_run_id
            )

    def _build_session_key(self, message: UserMessage) -> str:
        """Build composite session key."""
        return f"{message.tenant_id}:{message.agent_id}:{message.customer_id}:{message.channel}"

    async def _find_active_workflow(
        self,
        session_key: str,
    ) -> str | None:
        """
        Find workflow_run_id for any active LogicalTurnWorkflow on this session.

        Uses indexed lookup via ActiveTurnIndex, NOT workflow scan.
        The ActiveTurnIndex is updated when workflows start/complete.

        Returns:
            workflow_run_id if active workflow exists, None otherwise
        """
        # CORRECT: O(1) indexed lookup, not O(n) scan
        return await self._active_turn_index.get_workflow_run_id(session_key)

        # ⚠️ ANTI-PATTERN (DO NOT USE):
        # The following pattern has race conditions and is O(n):
        #
        # runs = await self._hatchet.list_workflow_runs(
        #     workflow_name="LogicalTurnWorkflow",
        #     status=["RUNNING", "PENDING"],
        # )
        # for run in runs:
        #     if run.input.get("session_key") == session_key:
        #         return run  # Race: workflow may complete between check and signal

    async def _start_new_workflow(
        self,
        message: UserMessage,
        session_key: str,
    ) -> TurnDecision:
        """Start a new LogicalTurnWorkflow."""
        turn_id = uuid4()

        try:
            run = await self._hatchet.run_workflow(
                "LogicalTurnWorkflow",
                input={
                    "turn_id": str(turn_id),
                    "session_key": session_key,
                    "tenant_id": str(message.tenant_id),
                    "agent_id": str(message.agent_id),
                    "customer_id": str(message.customer_id),
                    "message_id": str(message.id),
                    "message_content": message.content,
                    "channel": message.channel,
                    "timestamp": message.timestamp.isoformat(),
                },
            )

            # Register in index for O(1) lookup by subsequent messages
            await self._active_turn_index.set(session_key, run.id)

            logger.info(
                "workflow_started",
                session_key=session_key,
                turn_id=str(turn_id),
                workflow_run_id=run.id,
            )

            return TurnDecision(
                action=TurnAction.WORKFLOW_STARTED,
                turn_id=turn_id,
                workflow_run_id=run.id,
            )

        except HatchetError as e:
            logger.error(
                "workflow_start_failed",
                session_key=session_key,
                error=str(e),
            )
            # Queue message for retry
            return await self._queue_message(message, session_key)

    async def _signal_existing_workflow(
        self,
        message: UserMessage,
        workflow_run_id: str,  # From indexed lookup, not WorkflowRun object
    ) -> TurnDecision:
        """Send event to existing workflow."""
        session_key = self._build_session_key(message)

        try:
            await self._hatchet.send_event(
                workflow_run_id=workflow_run_id,
                event_type="new_message",
                payload={
                    "message_id": str(message.id),
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                },
            )

            logger.info(
                "event_sent_to_workflow",
                workflow_run_id=workflow_run_id,
                message_id=str(message.id),
            )

            return TurnDecision(
                action=TurnAction.EVENT_SENT,
                workflow_run_id=workflow_run_id,
            )

        except HatchetError as e:
            logger.error(
                "event_send_failed",
                workflow_run_id=workflow_run_id,
                error=str(e),
            )
            # Workflow may have completed - clear index and start new one
            await self._active_turn_index.clear(session_key)
            return await self._start_new_workflow(message, session_key)

    async def _queue_message(
        self,
        message: UserMessage,
        session_key: str,
    ) -> TurnDecision:
        """Queue message for later processing."""
        position = await self._message_queue.enqueue(
            session_key=session_key,
            message=message,
        )

        logger.info(
            "message_queued",
            session_key=session_key,
            message_id=str(message.id),
            queue_position=position,
        )

        return TurnDecision(
            action=TurnAction.QUEUED,
            queue_position=position,
        )
```

---

## Edge Cases

### Workflow Just Completed

```python
async def _signal_existing_workflow(self, message, workflow_run):
    """Handle case where workflow completed between check and signal."""

    try:
        await self._hatchet.send_event(...)
    except WorkflowNotRunningError:
        # Workflow completed - start new one
        logger.info(
            "workflow_completed_starting_new",
            old_workflow_id=workflow_run.id,
        )
        return await self._start_new_workflow(
            message,
            workflow_run.input["session_key"],
        )
```

### Multiple Messages in Flight

```python
# Two messages arrive nearly simultaneously:
# Message A arrives at t=0
# Message B arrives at t=50ms

# Without coordination:
#   Message A → No workflow → Start workflow
#   Message B → No workflow (not yet visible) → Start ANOTHER workflow
#   Result: Two parallel workflows!

# With session lock in workflow:
#   Message A → Start workflow → acquire_lock step
#   Message B → Sees workflow → sends event
#   OR
#   Message B → Starts workflow → acquire_lock BLOCKS (A has lock)
```

### Hatchet Unavailable

```python
async def receive_message(self, message):
    try:
        return await self._process_with_hatchet(message)
    except HatchetConnectionError:
        # Fallback: process synchronously (degraded mode)
        logger.warning(
            "hatchet_unavailable_degraded_mode",
            message_id=str(message.id),
        )
        return await self._process_synchronously(message)
```

---

## Message Queue Integration

For messages that can't be immediately processed:

```python
class MessageQueue:
    """Queue for deferred message processing."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def enqueue(
        self,
        session_key: str,
        message: UserMessage,
    ) -> int:
        """Add message to session's queue."""
        queue_key = f"msgqueue:{session_key}"
        position = await self._redis.rpush(
            queue_key,
            message.model_dump_json(),
        )
        # Set TTL to prevent unbounded growth
        await self._redis.expire(queue_key, 300)  # 5 minutes
        return position

    async def dequeue(
        self,
        session_key: str,
    ) -> UserMessage | None:
        """Get next queued message for session."""
        queue_key = f"msgqueue:{session_key}"
        data = await self._redis.lpop(queue_key)
        if data:
            return UserMessage.model_validate_json(data)
        return None

    async def peek(
        self,
        session_key: str,
    ) -> list[UserMessage]:
        """View queued messages without removing."""
        queue_key = f"msgqueue:{session_key}"
        data = await self._redis.lrange(queue_key, 0, -1)
        return [UserMessage.model_validate_json(d) for d in data]
```

Processing queued messages after workflow completes:

```python
@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    # ... commit and respond logic ...

    # Check for queued messages
    session_key = ctx.workflow_input()["session_key"]
    queued = await ctx.services.message_queue.dequeue(session_key)

    if queued:
        # Start new workflow for queued message
        await ctx.services.hatchet.run_workflow(
            "LogicalTurnWorkflow",
            input={
                "message_id": str(queued.id),
                "session_key": session_key,
                # ... other fields
            },
        )

    return {"status": "complete", "queued_processed": queued is not None}
```

---

## API Integration

```python
# In chat route handler
@router.post("/chat")
async def chat(
    request: ChatRequest,
    turn_gateway: TurnGateway = Depends(get_turn_gateway),
):
    message = UserMessage(
        id=uuid4(),
        tenant_id=request.tenant_id,
        agent_id=request.agent_id,
        customer_id=request.customer_id,
        channel=request.channel,
        content=request.message,
        timestamp=datetime.utcnow(),
    )

    decision = await turn_gateway.receive_message(message)

    if decision.action == TurnAction.REJECTED:
        raise HTTPException(
            status_code=429 if "rate_limit" in decision.rejection_reason else 403,
            detail=decision.rejection_reason,
        )

    if decision.action == TurnAction.QUEUED:
        return ChatResponse(
            status="queued",
            message="Your message is being processed",
            queue_position=decision.queue_position,
        )

    # For WORKFLOW_STARTED or EVENT_SENT, response will come via callback/SSE
    return ChatResponse(
        status="processing",
        turn_id=decision.turn_id,
    )
```

---

## Configuration

```toml
[gateway]
# Enable/disable components
rate_limiting_enabled = true
abuse_detection_enabled = true
message_queue_enabled = true

# Fallback behavior
fallback_to_sync = false  # Process synchronously if Hatchet unavailable

# Queue settings
queue_ttl_seconds = 300
max_queue_size_per_session = 10
```

---

## Observability

### Metrics

```python
# Gateway decisions
gateway_decision_count = Counter(
    "turn_gateway_decision_total",
    "Gateway routing decisions",
    ["action"],  # workflow_started, event_sent, queued, rejected
)

# Decision latency
gateway_latency_ms = Histogram(
    "turn_gateway_latency_ms",
    "Time to make gateway decision",
    buckets=[1, 5, 10, 25, 50, 100],
)

# Queue depth
queue_depth = Gauge(
    "turn_gateway_queue_depth",
    "Messages queued per session",
    ["session_key_pattern"],  # Anonymized
)
```

### Logging

```python
logger.info(
    "gateway_decision",
    session_key=session_key,
    action=decision.action.value,
    message_id=str(message.id),
    workflow_run_id=decision.workflow_run_id,
    latency_ms=latency,
)
```

---

## Testing

```python
# Test: First message starts workflow
async def test_first_message_starts_workflow(turn_gateway, mock_hatchet):
    message = UserMessage(...)

    decision = await turn_gateway.receive_message(message)

    assert decision.action == TurnAction.WORKFLOW_STARTED
    assert mock_hatchet.run_workflow.called_once()

# Test: Second message sends event
async def test_second_message_sends_event(turn_gateway, mock_hatchet):
    # Setup: workflow already running
    mock_hatchet.list_workflow_runs.return_value = [
        WorkflowRun(id="run-1", input={"session_key": "..."})
    ]

    message = UserMessage(...)
    decision = await turn_gateway.receive_message(message)

    assert decision.action == TurnAction.EVENT_SENT
    assert mock_hatchet.send_event.called_once()

# Test: Rate limited message rejected
async def test_rate_limited_rejected(turn_gateway, mock_rate_limiter):
    mock_rate_limiter.allow.return_value = False

    message = UserMessage(...)
    decision = await turn_gateway.receive_message(message)

    assert decision.action == TurnAction.REJECTED
    assert "rate_limit" in decision.rejection_reason
```

---

## ACF Entry Point Implementation

The Turn Gateway implements ACF's message ingress:

```python
class ACFTurnGateway:
    """
    ACF message ingress.

    This class IS part of ACF, not an external component.
    It receives messages from channel adapters and routes
    them into the ACF workflow system.
    """

    async def receive_raw_message(
        self,
        message: RawMessage,  # ACF's message type
    ) -> FabricDecision:
        """
        ACF entry point.

        Returns a FabricDecision indicating what ACF did:
        - WORKFLOW_STARTED: New LogicalTurn began
        - EVENT_SENT: Message routed to existing turn
        - QUEUED: Message queued for later
        - REJECTED: Rate limited or abuse detected
        """
        # Build session key
        session_key = build_session_key(message)

        # Check for active ACF workflow
        active_workflow = await self._find_acf_workflow(session_key)

        if active_workflow:
            # Route to existing workflow as event
            await self._hatchet.send_event(
                workflow_run_id=active_workflow.id,
                event_type="new_message",
                payload=message.model_dump(),
            )
            return FabricDecision(action=FabricAction.EVENT_SENT)
        else:
            # Start new ACF workflow
            await self._hatchet.run_workflow(
                "LogicalTurnWorkflow",  # ACF workflow
                input={"message": message.model_dump(), ...},
            )
            return FabricDecision(action=FabricAction.WORKFLOW_STARTED)
```

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [01-logical-turn.md](01-logical-turn.md) - Turn model created by gateway (ACF core)
- [02-session-mutex.md](02-session-mutex.md) - Lock used by workflows (ACF component)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Workflow orchestration (ACF runtime)
- [10-channel-capabilities.md](10-channel-capabilities.md) - Channel facts for routing
