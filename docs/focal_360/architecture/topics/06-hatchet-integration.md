# Hatchet Integration

> **Topic**: Durable workflow execution for logical turns
> **ACF Runtime**: Hatchet provides the execution environment for ACF
> **Architecture**: See [ACF_ARCHITECTURE.md](../ACF_ARCHITECTURE.md) for overall architecture
> **Dependencies**: LogicalTurn, Session Mutex, Adaptive Accumulation, AgentRuntime
> **Impacts**: Scalability, fault tolerance, stateless pods
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md), [AGENT_RUNTIME_SPEC.md](../AGENT_RUNTIME_SPEC.md)

---

## Architecture Context (v3.0)

> **IMPORTANT**: Tool execution is now owned by **Toolbox** (Agent layer), not ACF.
> The workflow calls AgentRuntime to get AgentContext, then delegates to Pipeline.

Hatchet is the **runtime for ACF**. The Agent Conversation Fabric is implemented as a Hatchet workflow, providing durability, event-driven accumulation, and stateless scaling.

### Key Changes in v3.0

| Aspect | v2.0 | v3.0 |
|--------|------|------|
| Tool execution | ACF callbacks | Toolbox (Agent layer) |
| Pipeline context | `FabricTurnContext` | `AgentTurnContext` wrapping `FabricTurnContext` |
| Agent loading | N/A | `AgentRuntime.get_or_create()` |
| Side effects | ACF SideEffectLedger | Toolbox emits FabricEvents → ACF stores |

### Workflow Steps

FOCAL uses a **single execution style** with four workflow steps:

```
acquire_mutex → accumulate → run_pipeline → commit_and_respond
```

| Step | Purpose |
|------|---------|
| `acquire_mutex` | Get session lock, prevent parallel turns |
| `accumulate` | Aggregate messages into LogicalTurn |
| `run_pipeline` | Pipeline processes turn, executes tools via Toolbox |
| `commit_and_respond` | Persist state, send response, release mutex |

### ACF ↔ Hatchet Mapping

| ACF Concept | Hatchet Implementation |
|-------------|------------------------|
| LogicalTurn lifecycle | Workflow instance |
| Session mutex | Step 1: `acquire_mutex` |
| Accumulation | Step 2: `accumulate` with `wait_for_event` |
| Agent loading | `AgentRuntime.get_or_create()` in step 3 |
| Pipeline execution | Step 3: `pipeline.run(AgentTurnContext)` |
| Tool execution | `ctx.toolbox.execute()` inside Pipeline (Toolbox enforces) |
| Commit & respond | Step 4: persist state, send response, release mutex |
| New message during processing | Hatchet event: `new_message` |
| Supersede signal | `ctx.has_pending_messages()` (ACF provides) |
| Supersede decision | Pipeline decides (SUPERSEDE/ABSORB/QUEUE/FORCE_COMPLETE) |
| FabricEvent stream | Workflow step outputs + external events |

### The LogicalTurnWorkflow IS ACF

The workflow implementation is not just "using Hatchet"—it IS the Agent Conversation Fabric:

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    """
    This workflow IS the Agent Conversation Fabric.

    It orchestrates:
    - Session mutex (single-writer)
    - Message accumulation (turn boundaries)
    - AgentContext loading (via AgentRuntime)
    - Pipeline invocation (Agent owns meaning)
    - FabricEvent routing (side effects stored here)
    - Supersede signals (ACF provides facts, Pipeline decides)
    """

    def __init__(self, agent_runtime: AgentRuntime):
        self._agent_runtime = agent_runtime
```

---

## Overview

**Hatchet** is used as the "actor runtime" for Soldier. It provides durable execution that:
- Persists workflow state across pod restarts
- Enables event-driven accumulation without sticky sessions
- Handles retries and failure recovery automatically

### The Problem Without Hatchet

```
Traditional approach (sticky sessions):
  Pod A receives "Hello" → starts processing
  Pod A receives "How are you?" → can absorb (same pod)
  Pod A crashes → STATE LOST, customer confused

Stateless without durability:
  Pod A receives "Hello" → starts processing
  Pod B receives "How are you?" → doesn't know about Pod A's work
  Result: Two parallel turns, race conditions
```

### The Solution

```
With Hatchet:
  Pod A receives "Hello" → starts LogicalTurnWorkflow
  Workflow state saved to Hatchet
  Pod A crashes
  Pod B picks up workflow → continues from saved state
  Pod B receives "How are you?" → sends event to workflow
  Workflow absorbs message → continues
```

---

## LogicalTurnWorkflow

The main workflow orchestrating turn processing:

```python
from hatchet_sdk import Hatchet, Context
from datetime import datetime

hatchet = Hatchet()

@hatchet.workflow()
class LogicalTurnWorkflow:
    """
    Durable workflow for processing a logical turn.

    This workflow acts as an "actor" for a conversation session:
    - Single instance per session
    - Sequential message processing
    - Durable state across pod failures
    - Event-driven accumulation
    """

    @hatchet.step()
    async def acquire_mutex(self, ctx: Context) -> dict:
        """
        Step 1: Acquire exclusive session lock.

        This ensures no other workflow instance processes
        the same session concurrently.
        """
        session_key = ctx.workflow_input()["session_key"]
        tenant_id = ctx.workflow_input()["tenant_id"]

        session_lock = SessionLock(redis=ctx.services.redis)

        async with session_lock.acquire(
            session_key,
            blocking_timeout=10,
        ) as acquired:
            if not acquired:
                ctx.log.warning(
                    "lock_acquisition_failed",
                    session_key=session_key,
                )
                # Retry with backoff
                return {
                    "status": "lock_failed",
                    "retry": True,
                    "backoff_seconds": 2,
                }

            ctx.log.info(
                "lock_acquired",
                session_key=session_key,
            )
            return {
                "status": "locked",
                "session_key": session_key,
                "locked_at": datetime.utcnow().isoformat(),
            }

    @hatchet.step()
    async def accumulate(self, ctx: Context) -> dict:
        """
        Step 2: Accumulate messages until turn is complete.

        This step can receive "new_message" events and either:
        - Absorb the message into the current turn
        - Signal that accumulation is complete
        """
        turn_id = ctx.workflow_input()["turn_id"]
        initial_message_id = ctx.workflow_input()["message_id"]
        channel = ctx.workflow_input()["channel"]

        turn_store = ctx.services.turn_store
        accumulator = ctx.services.accumulator
        message_store = ctx.services.message_store

        # Initialize or load turn
        turn = await turn_store.get(turn_id)
        if turn is None:
            turn = LogicalTurn(
                id=turn_id,
                session_key=ctx.step_output("acquire_mutex")["session_key"],
                messages=[initial_message_id],
                first_at=datetime.utcnow(),
                last_at=datetime.utcnow(),
            )
            await turn_store.save(turn)

        # Get initial message content for wait calculation
        initial_message = await message_store.get(initial_message_id)
        wait_ms = accumulator.suggest_wait_ms(
            message_content=initial_message.content,
            channel=channel,
            messages_in_turn=len(turn.messages),
        )

        ctx.log.info(
            "accumulation_started",
            turn_id=str(turn_id),
            initial_wait_ms=wait_ms,
        )

        while True:
            # Wait for timeout or new message event
            event = await ctx.wait_for_event(
                timeout_ms=wait_ms,
                event_types=["new_message"],
            )

            if event is None:
                # Timeout - accumulation complete
                turn.mark_processing(reason="timeout")
                await turn_store.save(turn)

                ctx.log.info(
                    "accumulation_complete",
                    turn_id=str(turn_id),
                    message_count=len(turn.messages),
                    reason="timeout",
                )

                return {
                    "turn": turn.model_dump(),
                    "status": "ready_to_process",
                }

            # New message event received
            new_message_id = event.payload["message_id"]
            new_content = event.payload["content"]
            timestamp = datetime.fromisoformat(event.payload["timestamp"])

            ctx.log.info(
                "new_message_during_accumulation",
                turn_id=str(turn_id),
                new_message_id=str(new_message_id),
            )

            if turn.can_absorb_message():
                # Absorb into current turn
                turn.absorb_message(new_message_id, timestamp)
                await turn_store.save(turn)

                # Recalculate wait time
                wait_ms = accumulator.suggest_wait_ms(
                    message_content=new_content,
                    channel=channel,
                    messages_in_turn=len(turn.messages),
                )

                ctx.log.info(
                    "message_absorbed",
                    turn_id=str(turn_id),
                    message_count=len(turn.messages),
                    new_wait_ms=wait_ms,
                )
            else:
                # Cannot absorb - complete current turn, queue message
                turn.mark_processing(reason="cannot_absorb")
                await turn_store.save(turn)

                ctx.log.info(
                    "accumulation_complete_with_queued",
                    turn_id=str(turn_id),
                    queued_message_id=str(new_message_id),
                )

                return {
                    "turn": turn.model_dump(),
                    "status": "ready_to_process",
                    "queued_message_id": str(new_message_id),
                }

    @hatchet.step()
    async def run_pipeline(self, ctx: Context) -> dict:
        """
        Step 3: Execute the alignment pipeline.

        Runs P1-P11 with interrupt checking at safe points.
        """
        accumulate_output = ctx.step_output("accumulate")
        turn_data = accumulate_output["turn"]
        turn = LogicalTurn(**turn_data)

        engine: AlignmentEngine = ctx.services.alignment_engine

        ctx.log.info(
            "pipeline_starting",
            turn_id=str(turn.id),
            message_count=len(turn.messages),
        )

        # Define interrupt checker
        async def interrupt_check() -> bool:
            """Check if a new message has arrived."""
            event = await ctx.check_event("new_message", block=False)
            if event:
                ctx.log.info(
                    "interrupt_detected",
                    turn_id=str(turn.id),
                    interrupting_message=event.payload.get("message_id"),
                )
            return event is not None

        try:
            result = await engine.process_logical_turn(
                turn=turn,
                interrupt_check=interrupt_check,
                reuse_artifacts=True,
            )

            if result.interrupted:
                turn.mark_superseded()
                await ctx.services.turn_store.save(turn)

                ctx.log.info(
                    "turn_superseded",
                    turn_id=str(turn.id),
                    phase_reached=result.last_phase,
                )

                return {
                    "status": "superseded",
                    "turn_id": str(turn.id),
                    "phase_reached": result.last_phase,
                    "superseding_message_id": result.interrupt_message_id,
                }

            ctx.log.info(
                "pipeline_complete",
                turn_id=str(turn.id),
            )

            return {
                "status": "complete",
                "turn": turn.model_dump(),
                "response": result.response,
                "scenario_transitions": result.scenario_transitions,
            }

        except Exception as e:
            ctx.log.error(
                "pipeline_failed",
                turn_id=str(turn.id),
                error=str(e),
            )
            raise

    @hatchet.step()
    async def commit_and_respond(self, ctx: Context) -> dict:
        """
        Step 4: Commit changes and send response.

        Only runs if pipeline completed (not superseded).
        """
        pipeline_output = ctx.step_output("run_pipeline")

        if pipeline_output["status"] == "superseded":
            ctx.log.info(
                "skipping_commit_superseded",
                turn_id=pipeline_output["turn_id"],
            )
            return {
                "status": "superseded",
                "turn_id": pipeline_output["turn_id"],
            }

        turn_data = pipeline_output["turn"]
        turn = LogicalTurn(**turn_data)
        response = pipeline_output["response"]

        # 1. Commit scenario transitions atomically
        session_store = ctx.services.session_store
        if pipeline_output.get("scenario_transitions"):
            await session_store.commit_scenario_transitions(
                session_key=turn.session_key,
                transitions=pipeline_output["scenario_transitions"],
            )

        # 2. Persist TurnRecord with beat linkage
        audit_store = ctx.services.audit_store
        await audit_store.save_turn_record(
            turn_id=turn.id,
            beat_id=turn.id,  # Turn IS the beat
            message_sequence=turn.messages,
            response=response,
            phase_artifacts=turn.phase_artifacts,
            side_effects=turn.side_effects,
        )

        # 3. Send response via channel adapter
        channel_adapter = ctx.services.channel_adapter
        await channel_adapter.send_response(
            session_key=turn.session_key,
            response=response,
        )

        ctx.log.info(
            "turn_completed",
            turn_id=str(turn.id),
            message_count=len(turn.messages),
        )

        return {
            "status": "complete",
            "turn_id": str(turn.id),
            "response_sent": True,
        }

    @hatchet.on_failure()
    async def handle_failure(self, ctx: Context) -> None:
        """
        Handle workflow failure.

        Release lock and log failure for investigation.
        """
        session_key = ctx.workflow_input().get("session_key")

        if session_key:
            try:
                session_lock = SessionLock(redis=ctx.services.redis)
                await session_lock.force_release(session_key)
            except Exception as e:
                ctx.log.error(
                    "lock_release_failed",
                    session_key=session_key,
                    error=str(e),
                )

        ctx.log.error(
            "logical_turn_workflow_failed",
            session_key=session_key,
            error=str(ctx.error),
            step=ctx.failed_step,
        )
```

---

## Triggering the Workflow

```python
class TurnGateway:
    """Entry point that triggers Hatchet workflows."""

    def __init__(
        self,
        hatchet_client: Hatchet,
        turn_store: LogicalTurnStore,
    ):
        self._hatchet = hatchet_client
        self._turn_store = turn_store

    async def receive_message(
        self,
        message: UserMessage,
    ) -> TurnDecision:
        """
        Handle incoming message by triggering or signaling workflow.
        """
        session_key = build_session_key(
            message.tenant_id,
            message.agent_id,
            message.customer_id,
            message.channel,
        )

        # Check for existing active workflow
        existing_workflow = await self._find_active_workflow(session_key)

        if existing_workflow is None:
            # No active workflow - start new one
            turn_id = uuid4()

            await self._hatchet.run_workflow(
                "LogicalTurnWorkflow",
                input={
                    "turn_id": str(turn_id),
                    "session_key": session_key,
                    "tenant_id": str(message.tenant_id),
                    "message_id": str(message.id),
                    "channel": message.channel,
                },
            )

            return TurnDecision(
                action=TurnAction.WORKFLOW_STARTED,
                turn_id=turn_id,
            )

        else:
            # Active workflow exists - send event
            await self._hatchet.send_event(
                workflow_run_id=existing_workflow.run_id,
                event_type="new_message",
                payload={
                    "message_id": str(message.id),
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                },
            )

            return TurnDecision(
                action=TurnAction.EVENT_SENT,
                workflow_run_id=existing_workflow.run_id,
            )

    async def _find_active_workflow(
        self,
        session_key: str,
    ) -> WorkflowRun | None:
        """Find any running workflow for this session."""
        # Query Hatchet for running workflows with this session_key
        runs = await self._hatchet.list_workflow_runs(
            workflow_name="LogicalTurnWorkflow",
            status=["RUNNING", "PENDING"],
            # Filter by input.session_key
        )

        for run in runs:
            if run.input.get("session_key") == session_key:
                return run

        return None
```

---

## Event Flow

```
┌─────────────┐    new message    ┌──────────────┐
│   Channel   │ ─────────────────►│ Turn Gateway │
│   Adapter   │                   └──────┬───────┘
└─────────────┘                          │
                                         │ No active workflow?
                        ┌────────────────┴────────────────┐
                        │                                 │
                        ▼                                 ▼
              ┌─────────────────┐             ┌─────────────────┐
              │  Start Workflow │             │   Send Event    │
              │  (new turn)     │             │  (absorb msg)   │
              └────────┬────────┘             └────────┬────────┘
                       │                               │
                       ▼                               ▼
              ┌─────────────────────────────────────────────────┐
              │                Hatchet Engine                    │
              │  ┌─────────────────────────────────────────────┐│
              │  │           LogicalTurnWorkflow               ││
              │  │  ┌──────────┐ ┌───────────┐ ┌────────────┐ ││
              │  │  │ acquire  │→│accumulate │→│run_pipeline│ ││
              │  │  │  lock    │ │ (waits    │ │            │ ││
              │  │  │          │ │  for      │ │            │ ││
              │  │  │          │ │  events)  │ │            │ ││
              │  │  └──────────┘ └───────────┘ └────────────┘ ││
              │  └─────────────────────────────────────────────┘│
              └─────────────────────────────────────────────────┘
```

---

## Durability Guarantees

### What Survives Pod Crashes

| State | Storage | Recovery |
|-------|---------|----------|
| Workflow status | Hatchet DB | Automatic |
| Step outputs | Hatchet DB | Automatic |
| LogicalTurn | Turn Store (Redis/DB) | Loaded on resume |
| Session lock | Redis (with TTL) | Auto-releases on timeout |
| Phase artifacts | Turn Store | Loaded on resume |

### What Doesn't Survive

| State | Impact | Mitigation |
|-------|--------|------------|
| In-memory LLM response | Re-run generation | Phase artifacts help |
| Partial tool execution | May need compensation | SideEffectPolicy |
| Uncommitted scenario transition | Lost | Idempotent retry |

---

## Configuration

```toml
[hatchet]
# Hatchet server connection
host = "localhost"
port = 7070

# Workflow settings
[hatchet.workflows.logical_turn]
# Maximum time for entire workflow
timeout_seconds = 300

# Retry configuration
max_retries = 3
retry_backoff_seconds = 2

# Concurrency limit per tenant
max_concurrent_per_tenant = 100
```

---

## Monitoring

### Workflow Metrics

```python
# Workflow duration
workflow_duration_seconds = Histogram(
    "logical_turn_workflow_duration_seconds",
    "Total workflow duration",
    buckets=[1, 2, 5, 10, 30, 60, 120],
)

# Step duration
step_duration_seconds = Histogram(
    "logical_turn_step_duration_seconds",
    "Duration of each workflow step",
    ["step_name"],
)

# Workflow outcomes
workflow_outcome_count = Counter(
    "logical_turn_workflow_outcome_total",
    "Workflow completion outcomes",
    ["outcome"],  # complete, superseded, failed
)

# Event counts
event_count = Counter(
    "logical_turn_event_total",
    "Events sent to workflows",
    ["event_type"],
)
```

### Hatchet Dashboard

Hatchet provides a built-in dashboard for:
- Workflow run history
- Step execution traces
- Failed workflow investigation
- Event logs

---

## Testing

### Unit Testing (Mock Hatchet)

```python
@pytest.fixture
def mock_hatchet():
    """Mock Hatchet client for unit tests."""
    return MockHatchetClient()

async def test_workflow_starts_on_new_message(mock_hatchet, turn_gateway):
    message = UserMessage(...)

    decision = await turn_gateway.receive_message(message)

    assert decision.action == TurnAction.WORKFLOW_STARTED
    assert mock_hatchet.workflows_started == 1

async def test_event_sent_to_existing_workflow(mock_hatchet, turn_gateway):
    # First message starts workflow
    await turn_gateway.receive_message(message1)

    # Second message sends event
    decision = await turn_gateway.receive_message(message2)

    assert decision.action == TurnAction.EVENT_SENT
```

### Integration Testing

```python
@pytest.mark.integration
async def test_full_workflow_execution(hatchet_test_client):
    """Test complete workflow with real Hatchet."""

    # Start workflow
    run = await hatchet_test_client.run_workflow(
        "LogicalTurnWorkflow",
        input={...},
    )

    # Wait for completion
    result = await run.wait(timeout=30)

    assert result["status"] == "complete"
    assert result["response_sent"] is True
```

---

## ACF Workflow Steps Detail

### Step 1: acquire_mutex (ACF Concurrency)

**CRITICAL**: Mutex must be held across ALL steps. See [02-session-mutex.md](02-session-mutex.md) for the correct lifecycle pattern.

```python
@hatchet.step()
async def acquire_mutex(self, ctx: Context) -> dict:
    """
    ACF: Enforce single-writer rule.

    IMPORTANT: Do NOT use context manager - lock must persist across steps.
    Lock is released explicitly in commit_and_respond or on_failure.
    """
    session_key = ctx.workflow_input()["session_key"]

    # Acquire WITHOUT context manager
    lock = self._redis.lock(f"sesslock:{session_key}", timeout=300)
    acquired = await lock.acquire(blocking_timeout=10)

    if not acquired:
        raise MutexAcquisitionFailed(session_key)

    # Store key for later release (NOT the lock object)
    ctx.workflow_state["session_lock_key"] = f"sesslock:{session_key}"

    return {"mutex_acquired": True}
```

### Step 2: accumulate (ACF Aggregation)

```python
@hatchet.step()
async def accumulate(self, ctx: Context) -> dict:
    """ACF: Aggregate messages into LogicalTurn."""
    # See 03-adaptive-accumulation.md
    # Uses Channel Capabilities (10-channel-capabilities.md)
    # Loads hints from PREVIOUS turn (no circular dependency)
```

### Step 3: run_pipeline

```python
@hatchet.step()
async def run_pipeline(self, ctx: Context) -> dict:
    """
    Pipeline runs all phases with tool execution inside.

    Tools execute INSIDE this step via ctx.toolbox.execute().
    Pipeline can check ctx.has_pending_messages() for supersede signals.
    Toolbox handles policy enforcement, idempotency, and audit events.
    """
    tenant_id = UUID(ctx.workflow_input()["tenant_id"])
    agent_id = UUID(ctx.workflow_input()["agent_id"])
    turn = LogicalTurn(**ctx.step_output("accumulate")["turn"])

    # Load AgentContext (cached or fresh)
    agent_ctx = await self._agent_runtime.get_or_create(tenant_id, agent_id)

    # Build FabricTurnContext (what ACF provides)
    fabric_ctx = FabricTurnContext(
        logical_turn=turn,
        session_key=turn.session_key,
        channel=ctx.workflow_input()["channel"],
        has_pending_messages=lambda: self._check_pending(ctx),
        emit_event=lambda e: self._route_event(e, turn),
    )

    # Build AgentTurnContext (wraps fabric + agent)
    turn_ctx = AgentTurnContext(
        fabric=fabric_ctx,
        agent_context=agent_ctx,
    )

    # Pipeline runs all phases - tools via ctx.toolbox.execute()
    # Toolbox is the enforcement boundary
    result = await agent_ctx.pipeline.run(turn_ctx)

    return {
        "turn": turn.model_dump(),
        "result": result.model_dump(),
    }

async def _check_pending(self, hatchet_ctx: Context) -> bool:
    """ACF signal: Check if new message arrived."""
    event = await hatchet_ctx.check_event("new_message", block=False)
    return event is not None
```

### Step 4: commit_and_respond

```python
@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    """ACF: Final commit and response delivery."""
    # Commit staged mutations
    # Record TurnRecord with beat linkage
    # Emit TURN_COMPLETED event
    # Store accumulation_hint for next turn
    # EXPLICITLY RELEASE MUTEX
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._redis.delete(lock_key)
```

### Failure Handler

```python
@hatchet.on_failure()
async def handle_failure(self, ctx: Context):
    """Always release lock on failure."""
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._redis.delete(lock_key)
```

---

## Related Topics

- [../ACF_ARCHITECTURE.md](../ACF_ARCHITECTURE.md) - Canonical architecture document
- [../AGENT_RUNTIME_SPEC.md](../AGENT_RUNTIME_SPEC.md) - Agent lifecycle management
- [../TOOLBOX_SPEC.md](../TOOLBOX_SPEC.md) - Tool execution layer
- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [01-logical-turn.md](01-logical-turn.md) - Turn model managed by workflow (ACF core)
- [02-session-mutex.md](02-session-mutex.md) - Lock acquired in workflow (ACF component)
- [03-adaptive-accumulation.md](03-adaptive-accumulation.md) - Logic in accumulate step (ACF component)
- [04-side-effect-policy.md](04-side-effect-policy.md) - Side effect classification (Toolbox owns)
