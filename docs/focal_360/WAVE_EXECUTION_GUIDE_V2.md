# FOCAL 360 Wave Execution Guide v2.0

> **Purpose**: Step-by-step guide for implementing FOCAL 360 with Agent Conversation Fabric (ACF)
> **Status**: SUPERSEDES original WAVE_EXECUTION_GUIDE.md
> **Key Change**: Phase 1 implements complete ACF layer with single execution model
> **Updated**: 2025-12-12 (Single execution model - Toolbox as enforcement boundary)
> **See Also**: [ACF_SPEC.md](architecture/ACF_SPEC.md) for the authoritative specification

---

## Architectural Foundation

### The Agent Conversation Fabric (ACF)

> ACF is the **conversation control plane** that governs *when and how an agent responds*, separate from *what the agent says* (CognitivePipeline).

### Execution Model

FOCAL uses a **single execution style**: Pipeline calls `toolbox.execute()` inline.

```
acquire_mutex → accumulate → run_pipeline → commit_and_respond
```

**Key principles**:
- Toolbox is the enforcement boundary (policy, idempotency, confirmation, audit)
- ACF is NOT in the tool execution path
- Pipeline conformance via Toolbox + ASA validation, not runtime modes

### The Core Insight

> "A message is not a turn."

The semantic unit is a **conversational beat**: one or more rapid messages forming one coherent user intent.

### Implementation Phases

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PHASE 1: ACF CORE                                │
│  LogicalTurn + SupersedeDecision + Single Execution Model + Hatchet │
│  turn_group_id + Three-Layer Idempotency + Mutex Lifecycle Fix      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼───────┐          ┌────────▼────────┐         ┌────────▼────────┐
│   PHASE 2     │          │    PHASE 3      │         │                 │
│  Safety &     │          │   Proactive     │         │    (Future)     │
│  Config       │          │   Features      │         │                 │
└───────────────┘          └─────────────────┘         └─────────────────┘
```

**Critical Rule**: Phase 1 (ACF Core) MUST complete before any other phase begins.

---

## Before Starting Any Phase

### CRITICAL: Codebase Exploration Rule

**Before implementing ANYTHING**, every agent MUST:

1. **Read the ACF specification**: `docs/focal_360/architecture/ACF_SPEC.md`
2. **Read the founding vision**: `docs/focal_360/architecture/LOGICAL_TURN_VISION.md`
3. **Search the existing codebase** for similar functionality
4. **Modify existing code** instead of creating parallel implementations

### CRITICAL: Checkbox Rule

Every agent MUST:
1. **Check boxes `[x]` immediately after completing each item** - not at the end
2. Edit the checklist file directly using the Edit tool
3. Add implementation notes under checked items
4. Mark blocked items with `BLOCKED:` and continue

### Coordinator Checklist

Before launching each phase:

- [ ] Previous phase is 100% complete
- [ ] All blocked items from previous phase are resolved
- [ ] Integration tests pass for completed features
- [ ] No merge conflicts in codebase
- [ ] Code quality checks pass (ruff, mypy)
- [ ] Data model reservations in place (TurnRecord.beat_id, etc.)

---

## PHASE 1: ACF Core (FOUNDATIONAL)

> **CRITICAL**: This phase MUST complete before ANY other phase begins.
> All subsequent features depend on the Agent Conversation Fabric layer.
> **Reference**: [ACF_SPEC.md](architecture/ACF_SPEC.md)

### ACF Components Overview

| Component | ACF Role | Files | Notes |
|-----------|----------|-------|-------|
| `LogicalTurn` + `SupersedeDecision` + `turn_group_id` | Core abstraction | `focal/alignment/models/logical_turn.py` | turn_group_id for idempotency scoping |
| Session Mutex | Concurrency | `focal/alignment/gateway/session_lock.py` | **CRITICAL**: No context manager - hold across steps |
| Turn Gateway (ACF ingress) | Entry point | `focal/alignment/gateway/turn_gateway.py` | Message queue with overflow strategy |
| Adaptive Accumulation + Pipeline Hints | Aggregation | `focal/alignment/gateway/accumulator.py` | Hints from PREVIOUS turn |
| `LogicalTurnWorkflow` | ACF runtime | `focal/jobs/workflows/logical_turn.py` | Single workflow: acquire → accumulate → run_pipeline → commit |
| `PhaseArtifact` + ReusePolicy | Optimization | `focal/alignment/models/phase_artifact.py` | `input_fp`, `dep_fp` fingerprints |
| `SideEffectPolicy` + Toolbox | Commit gating | `focal/alignment/models/side_effect.py` | Toolbox enforces policy inline |
| `ChannelModel` (facts + policies) | Channel model | `focal/alignment/models/channel.py` | Consolidated: ChannelFacts + ChannelPolicy |
| Three-Layer Idempotency | Safety | `focal/alignment/idempotency.py` | API (5min), Beat (60s), Tool (24h) |

### Agent 1A: LogicalTurn Model + SupersedeDecision + Session Mutex

**Prerequisites**: None (this is the absolute foundation)

**Prompt**:

```markdown
# Task: Implement LogicalTurn Model with ACF Types

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/architecture/ACF_SPEC.md` - THE AUTHORITATIVE SPECIFICATION
2. `docs/focal_360/architecture/ACF_ARCHITECTURE.md` - Canonical architecture (v3.0)
3. `CLAUDE.md` - Project conventions

## The Core Insight

> "A message is not a turn."

A LogicalTurn (beat) is one or more rapid messages forming one coherent user intent.
Example: "Hello" then "How are you?" should yield ONE agent response, not two.

## ACF Context

You are implementing the **core abstractions** of the Agent Conversation Fabric.
ACF owns the LogicalTurn lifecycle; CognitivePipeline operates on it to produce meaning.

## Your Assignment

### Part 1: LogicalTurn Model

Create `focal/alignment/models/logical_turn.py`:

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class LogicalTurnStatus(str, Enum):
    """Lifecycle states for a logical turn (ACF-managed)."""
    ACCUMULATING = "accumulating"  # Waiting for more messages
    PROCESSING = "processing"       # Pipeline running
    COMPLETE = "complete"           # Response sent
    SUPERSEDED = "superseded"       # Cancelled by newer turn


class SupersedeAction(str, Enum):
    """
    Four-state supersede model (ACF core concept).

    When a new message arrives during processing, CognitivePipeline
    advises ACF which action to take. ACF enforces the decision.

    See ACF_SPEC.md for SupersedeDecision model (action + strategy + reason).
    """
    SUPERSEDE = "supersede"       # Cancel current, start new with all messages
    ABSORB = "absorb"             # Add message to current turn, may restart
    QUEUE = "queue"               # Finish current, then process new
    FORCE_COMPLETE = "force_complete"  # Almost done, just finish

class LogicalTurn(BaseModel):
    """A conversational beat: atomic unit of user intent."""

    id: UUID = Field(default_factory=uuid4)
    session_key: str  # (tenant, agent, customer, channel) composite
    messages: list[UUID] = Field(default_factory=list)  # Message IDs, ordered
    status: LogicalTurnStatus = LogicalTurnStatus.ACCUMULATING

    # Adaptive waiting
    first_at: datetime
    last_at: datetime
    completion_confidence: float = 0.0
    completion_reason: str | None = None  # "timeout" | "ai_predicted" | "explicit_signal"

    # Checkpoint reuse (populated during processing)
    phase_artifacts: dict[int, "PhaseArtifact"] = Field(default_factory=dict)
    side_effects: list["SideEffect"] = Field(default_factory=list)

    # Scenario state at turn start (for safe superseding)
    scenario_states_at_start: dict[UUID, "ScenarioStepRef"] = Field(default_factory=dict)

    def can_absorb_message(self) -> bool:
        """Can this turn absorb another message?"""
        if self.status in [LogicalTurnStatus.COMPLETE, LogicalTurnStatus.SUPERSEDED]:
            return False
        if self.status == LogicalTurnStatus.PROCESSING:
            # Can only absorb if no irreversible side effects executed
            return not any(se.irreversible for se in self.side_effects)
        return True  # ACCUMULATING status
```

### Part 2: Session Mutex

Create `focal/alignment/gateway/session_lock.py`:

```python
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis

class SessionLock:
    """Ensures single-writer semantics per conversation session."""

    def __init__(self, redis: Redis, lock_timeout: int = 30):
        self._redis = redis
        self._lock_timeout = lock_timeout

    def _key(self, session_key: str) -> str:
        return f"sesslock:{session_key}"

    @asynccontextmanager
    async def acquire(
        self,
        session_key: str,
        blocking_timeout: float = 5.0,
    ) -> AsyncGenerator[bool, None]:
        """
        Acquire exclusive lock for session.

        Args:
            session_key: Composite key (tenant:agent:customer:channel)
            blocking_timeout: How long to wait for lock

        Yields:
            True if lock acquired, False if timed out
        """
        lock = self._redis.lock(
            self._key(session_key),
            timeout=self._lock_timeout,
            blocking_timeout=blocking_timeout,
        )
        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                await lock.release()
```

### Part 3: PhaseArtifact Model

Create `focal/alignment/models/phase_artifact.py`:

```python
from datetime import datetime
from pydantic import BaseModel

class PhaseArtifact(BaseModel):
    """Cached result from a pipeline phase for checkpoint reuse."""

    phase: int
    data: dict  # Phase-specific output
    input_fingerprint: str  # Hash of inputs
    dependency_fingerprint: str  # Hash of dependencies (session_state, ruleset_version)
    created_at: datetime

    def is_valid(self, new_input_fp: str, new_dep_fp: str) -> bool:
        """Check if this artifact can be reused."""
        return (
            self.input_fingerprint == new_input_fp
            and self.dependency_fingerprint == new_dep_fp
        )
```

### Part 4: Data Model Reservations

Update `focal/audit/models/turn_record.py` to reserve fields:

```python
class TurnRecord(BaseModel):
    # ... existing fields ...

    # NEW: Beat integration (reserve now, use later)
    beat_id: UUID | None = None  # Links to LogicalTurn.id
    message_sequence: list[UUID] = Field(default_factory=list)  # Raw messages in this turn
    superseded_by: UUID | None = None  # If this turn was cancelled
    interruptions: list[dict] = Field(default_factory=list)  # Cancel attempts
    phase_artifact_summaries: dict[int, dict] = Field(default_factory=dict)
```

## Key Deliverables
1. `LogicalTurn` model with status enum
2. `SupersedeDecision` enum (four-state model)
3. `SessionLock` with Redis-backed mutex
4. `PhaseArtifact` for checkpoint reuse with `ReusePolicy`
5. TurnRecord field reservations
6. Unit tests for all models
7. Export all new models from `focal/alignment/models/__init__.py`

## Testing Commands
```bash
uv run pytest tests/unit/alignment/models/test_logical_turn.py -v
uv run pytest tests/unit/alignment/gateway/test_session_lock.py -v
uv run ruff check focal/alignment/models/ focal/alignment/gateway/
uv run mypy focal/alignment/models/ focal/alignment/gateway/
```

## Report Format
Provide a final implementation summary with files changed, tests added, and any open issues.
```

---

### Agent 1B: ACF Ingress (Turn Gateway) + Adaptive Accumulation

**Prerequisites**: Agent 1A (LogicalTurn model + Session Mutex) complete

**Prompt**:

```markdown
# Task: Implement ACF Ingress (Turn Gateway) with Adaptive Accumulation

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/architecture/ACF_SPEC.md` - THE AUTHORITATIVE SPECIFICATION
2. `docs/focal_360/architecture/TOOLBOX_SPEC.md` - Tool execution spec
3. `CLAUDE.md` - Project conventions
4. Agent 1A's completed code (LogicalTurn, SupersedeDecision, SessionLock, PhaseArtifact)

## ACF Context

The Turn Gateway is **absorbed into ACF** as the message ingress layer.
It's not a separate component—it's how messages enter the Agent Conversation Fabric.

It decides whether to:
- Start a new LogicalTurnWorkflow (ACF)
- Route message to existing workflow as event
- Queue message if session is busy

## Your Assignment

### Part 1: Turn Gateway

Create `focal/alignment/gateway/turn_gateway.py`:

```python
from datetime import datetime
from uuid import UUID

from soldier.alignment.gateway.session_lock import SessionLock
from soldier.alignment.gateway.accumulator import AdaptiveAccumulator
from soldier.alignment.models.logical_turn import LogicalTurn, LogicalTurnStatus

class TurnGateway:
    """
    Ingress controller for user messages.

    Responsibilities:
    1. Build session key from message context
    2. Acquire session lock
    3. Decide: new turn, absorb, or supersede
    4. Manage accumulation window
    """

    def __init__(
        self,
        session_lock: SessionLock,
        accumulator: AdaptiveAccumulator,
        turn_store: "LogicalTurnStore",
    ):
        self._session_lock = session_lock
        self._accumulator = accumulator
        self._turn_store = turn_store

    def build_session_key(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        customer_id: UUID,
        channel: str,
    ) -> str:
        return f"{tenant_id}:{agent_id}:{customer_id}:{channel}"

    async def receive_message(
        self,
        message_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        customer_id: UUID,
        channel: str,
        content: str,
        timestamp: datetime,
    ) -> "TurnDecision":
        """
        Process incoming message and return decision.

        Returns:
            TurnDecision with action (ACCUMULATE, PROCESS, SUPERSEDE, QUEUE)
        """
        session_key = self.build_session_key(
            tenant_id, agent_id, customer_id, channel
        )

        # Check for existing in-flight turn
        current_turn = await self._turn_store.get_active_turn(session_key)

        if current_turn is None:
            # No active turn - create new one
            turn = LogicalTurn(
                session_key=session_key,
                messages=[message_id],
                first_at=timestamp,
                last_at=timestamp,
            )
            await self._turn_store.save(turn)
            return TurnDecision(
                action=TurnAction.ACCUMULATE,
                turn=turn,
                wait_ms=self._accumulator.suggest_wait_ms(content, channel),
            )

        if current_turn.can_absorb_message():
            # Absorb into existing turn
            current_turn.messages.append(message_id)
            current_turn.last_at = timestamp
            await self._turn_store.save(current_turn)
            return TurnDecision(
                action=TurnAction.ACCUMULATE,
                turn=current_turn,
                wait_ms=self._accumulator.suggest_wait_ms(content, channel),
            )

        if current_turn.status == LogicalTurnStatus.PROCESSING:
            # Check if we can supersede
            if self._can_supersede(current_turn):
                current_turn.status = LogicalTurnStatus.SUPERSEDED
                await self._turn_store.save(current_turn)

                # Create new turn
                new_turn = LogicalTurn(
                    session_key=session_key,
                    messages=[message_id],
                    first_at=timestamp,
                    last_at=timestamp,
                )
                await self._turn_store.save(new_turn)
                return TurnDecision(
                    action=TurnAction.SUPERSEDE,
                    turn=new_turn,
                    superseded_turn_id=current_turn.id,
                )

        # Cannot absorb or supersede - queue for next turn
        return TurnDecision(
            action=TurnAction.QUEUE,
            turn=None,
            queued_message_id=message_id,
        )

    def _can_supersede(self, turn: LogicalTurn) -> bool:
        """Check if turn can be safely superseded."""
        # Can supersede if no irreversible side effects
        return not any(
            se.policy == "irreversible"
            for se in turn.side_effects
        )
```

### Part 2: Adaptive Accumulator

Create `focal/alignment/gateway/accumulator.py`:

```python
class AdaptiveAccumulator:
    """
    Determines how long to wait for additional messages.

    Factors:
    1. Channel characteristics (WhatsApp vs SMS vs web)
    2. Message shape (greeting, fragment, complete)
    3. User typing cadence (learned over sessions)
    """

    # Default wait times by channel
    CHANNEL_DEFAULTS = {
        "whatsapp": 1200,  # WhatsApp users often send in bursts
        "sms": 800,        # SMS typically more deliberate
        "web": 600,        # Web chat is faster
        "email": 0,        # Email is always complete
        "voice": 0,        # Voice is streamed differently
    }

    def __init__(
        self,
        min_wait_ms: int = 200,
        max_wait_ms: int = 3000,
    ):
        self._min_wait_ms = min_wait_ms
        self._max_wait_ms = max_wait_ms

    def suggest_wait_ms(
        self,
        message_content: str,
        channel: str,
        user_cadence_p95_ms: int | None = None,
    ) -> int:
        """
        Suggest how long to wait before processing.

        Args:
            message_content: The message text
            channel: Channel identifier
            user_cadence_p95_ms: User's 95th percentile inter-message time

        Returns:
            Milliseconds to wait
        """
        # Start with channel default
        base = self.CHANNEL_DEFAULTS.get(channel, 800)

        # Adjust for message shape
        if self._is_greeting_only(message_content):
            base += 500  # Greetings often followed by actual request
        elif self._is_fragment(message_content):
            base += 300  # Incomplete thought

        # Adjust for user's historical cadence
        if user_cadence_p95_ms:
            base = (base + user_cadence_p95_ms) // 2

        return self._clamp(base)

    def _is_greeting_only(self, text: str) -> bool:
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon"}
        return text.strip().lower() in greetings

    def _is_fragment(self, text: str) -> bool:
        # Incomplete sentence indicators
        return (
            text.endswith("...")
            or text.endswith(",")
            or len(text.split()) < 3
        )

    def _clamp(self, value: int) -> int:
        return max(self._min_wait_ms, min(value, self._max_wait_ms))
```

### Part 3: Decision Models

```python
from enum import Enum

class TurnAction(str, Enum):
    ACCUMULATE = "accumulate"  # Wait for more messages
    PROCESS = "process"        # Start pipeline now
    SUPERSEDE = "supersede"    # Cancel old turn, start new
    QUEUE = "queue"            # Queue for next turn

class TurnDecision(BaseModel):
    action: TurnAction
    turn: LogicalTurn | None = None
    wait_ms: int = 0
    superseded_turn_id: UUID | None = None
    queued_message_id: UUID | None = None
```

## Key Deliverables
1. `TurnGateway` with absorb/supersede logic
2. `AdaptiveAccumulator` with channel-aware waiting
3. `TurnDecision` and `TurnAction` models
4. `LogicalTurnStore` interface (InMemory implementation)
5. Comprehensive tests
6. Wire gateway into API layer (chat endpoint)

## Testing Commands
```bash
uv run pytest tests/unit/alignment/gateway/ -v
uv run ruff check focal/alignment/gateway/
uv run mypy focal/alignment/gateway/
```

## Report Format
Provide a final implementation summary with files changed, tests added, and any open issues.
```

---

### Agent 1C: Hatchet LogicalTurnWorkflow (ACF Runtime)

**Prerequisites**: Agents 1A and 1B complete

**Prompt**:

```markdown
# Task: Implement Hatchet LogicalTurnWorkflow (ACF Runtime)

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/architecture/ACF_SPEC.md` - THE AUTHORITATIVE SPECIFICATION
2. `docs/focal_360/architecture/TOOLBOX_SPEC.md` - Tool execution spec
3. `CLAUDE.md` - Project conventions
4. Agent 1A and 1B's completed code
5. Existing Hatchet patterns in `focal/jobs/workflows/`

## ACF Context

The LogicalTurnWorkflow IS the Agent Conversation Fabric.

It implements the four ACF workflow steps:
1. `acquire_mutex` - Session lock (ACF concurrency)
2. `accumulate` - Message aggregation (ACF aggregation)
3. `run_pipeline` - CognitivePipeline invocation (ACF ↔ Pipeline boundary)
4. `commit_and_respond` - Final commit (ACF commit point)

This replaces sticky sessions with Hatchet's durable state.

## Your Assignment

Create `focal/jobs/workflows/logical_turn.py`:

```python
from hatchet_sdk import Hatchet, Context
from soldier.alignment.gateway.turn_gateway import TurnGateway
from soldier.alignment.gateway.session_lock import SessionLock
from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.models.logical_turn import LogicalTurn, LogicalTurnStatus

hatchet = Hatchet()

@hatchet.workflow()
class LogicalTurnWorkflow:
    """
    Durable workflow for processing a logical turn.

    This is the actor-style coordinator that processes messages
    sequentially per session without requiring sticky pods.
    """

    @hatchet.step()
    async def acquire_lock(self, ctx: Context) -> dict:
        """Acquire exclusive session lock."""
        session_key = ctx.workflow_input()["session_key"]

        session_lock = SessionLock(redis=ctx.services.redis)
        async with session_lock.acquire(session_key, blocking_timeout=10) as acquired:
            if not acquired:
                return {"status": "lock_failed", "retry": True}

            # Store lock info for subsequent steps
            return {"status": "locked", "session_key": session_key}

    @hatchet.step()
    async def accumulate(self, ctx: Context) -> dict:
        """
        Wait for accumulation window to close.

        Can receive "new_message" events to extend the window.
        """
        turn_id = ctx.workflow_input()["turn_id"]
        wait_ms = ctx.workflow_input()["initial_wait_ms"]

        turn_store = ctx.services.turn_store
        accumulator = ctx.services.accumulator

        turn = await turn_store.get(turn_id)

        while True:
            # Wait for timeout or new message event
            event = await ctx.wait_for_event(
                timeout_ms=wait_ms,
                event_types=["new_message"],
            )

            if event is None:
                # Timeout - accumulation complete
                turn.status = LogicalTurnStatus.PROCESSING
                turn.completion_reason = "timeout"
                await turn_store.save(turn)
                return {"turn": turn.model_dump(), "status": "ready"}

            # New message arrived - absorb it
            message_id = event.payload["message_id"]
            message_content = event.payload["content"]

            if turn.can_absorb_message():
                turn.messages.append(message_id)
                turn.last_at = event.payload["timestamp"]
                await turn_store.save(turn)

                # Recalculate wait time
                wait_ms = accumulator.suggest_wait_ms(
                    message_content,
                    ctx.workflow_input()["channel"],
                )
            else:
                # Cannot absorb - queue for next turn
                return {
                    "turn": turn.model_dump(),
                    "status": "ready",
                    "queued_message": message_id,
                }

    @hatchet.step()
    async def run_pipeline(self, ctx: Context) -> dict:
        """
        Execute alignment pipeline with interrupt checks.
        """
        turn_data = ctx.step_output("accumulate")["turn"]
        turn = LogicalTurn(**turn_data)

        engine: AlignmentEngine = ctx.services.alignment_engine

        # Check for interrupts (new messages) at safe points
        async def interrupt_check() -> bool:
            event = await ctx.check_event("new_message", block=False)
            return event is not None

        result = await engine.process_logical_turn(
            turn=turn,
            interrupt_check=interrupt_check,
            reuse_artifacts=True,
        )

        if result.interrupted:
            turn.status = LogicalTurnStatus.SUPERSEDED
            return {
                "status": "superseded",
                "phase_reached": result.last_phase,
                "superseding_message": result.interrupt_message_id,
            }

        return {
            "status": "complete",
            "response": result.response,
            "turn": turn.model_dump(),
        }

    @hatchet.step()
    async def commit_and_respond(self, ctx: Context) -> dict:
        """
        Commit scenario transitions and send response.
        """
        pipeline_result = ctx.step_output("run_pipeline")

        if pipeline_result["status"] == "superseded":
            # Don't commit anything - new turn will handle
            return {"status": "superseded"}

        # Commit scenario transitions atomically
        turn_data = pipeline_result["turn"]
        turn = LogicalTurn(**turn_data)

        session_store = ctx.services.session_store
        await session_store.commit_scenario_transition(
            turn.session_key,
            turn.scenario_states_at_start,
        )

        # Persist TurnRecord with beat linkage
        audit_store = ctx.services.audit_store
        await audit_store.save_turn_record(
            turn_id=turn.id,
            beat_id=turn.id,  # turn IS the beat
            message_sequence=turn.messages,
            response=pipeline_result["response"],
        )

        # Send response via channel adapter
        channel_adapter = ctx.services.channel_adapter
        await channel_adapter.send_response(
            session_key=turn.session_key,
            response=pipeline_result["response"],
        )

        return {"status": "complete", "turn_id": str(turn.id)}

    @hatchet.on_failure()
    async def handle_failure(self, ctx: Context):
        """Release lock and log failure."""
        session_key = ctx.workflow_input().get("session_key")
        if session_key:
            session_lock = SessionLock(redis=ctx.services.redis)
            # Lock auto-releases on timeout, but be explicit
            await session_lock.force_release(session_key)

        ctx.log.error(
            "logical_turn_failed",
            session_key=session_key,
            error=str(ctx.error),
        )
```

## Key Deliverables
1. `LogicalTurnWorkflow` with all four steps
2. Integration with existing AlignmentEngine
3. Event-driven accumulation
4. Interrupt-aware pipeline execution
5. Atomic scenario commits
6. Tests using Hatchet test utilities
7. Register workflow in `focal/jobs/__init__.py`

## Integration Points
- `AlignmentEngine.process_logical_turn()` - New method (modify engine.py)
- Channel adapter for response sending
- AuditStore for TurnRecord with beat_id

## Testing Commands
```bash
uv run pytest tests/unit/jobs/workflows/test_logical_turn.py -v
uv run pytest tests/integration/jobs/test_logical_turn_workflow.py -v
```

## Report Format
Provide a final implementation summary with files changed, tests added, and any open issues.
```

---

### Verification After Phase 1

**MANDATORY checks before proceeding to Phase 2:**

- [ ] `LogicalTurn` model exists with status enum
- [ ] `SupersedeDecision` enum with four states
- [ ] `SessionLock` works with Redis
- [ ] ACF ingress (TurnGateway) handles message routing
- [ ] `AdaptiveAccumulator` provides channel-aware waiting
- [ ] `LogicalTurnWorkflow` runs in Hatchet with four steps
- [ ] Two-phase commit for tools implemented
- [ ] Pipeline-declared artifact reuse working
- [ ] `TurnRecord` has reserved fields (beat_id, message_sequence, superseded_by)
- [ ] Chat endpoint wired to ACF ingress
- [ ] All tests pass
- [ ] Code quality checks pass

```bash
# Phase 1 verification
uv run pytest tests/unit/alignment/models/test_logical_turn.py -v
uv run pytest tests/unit/alignment/gateway/ -v
uv run pytest tests/unit/jobs/workflows/test_logical_turn.py -v
uv run ruff check focal/alignment/ focal/jobs/
uv run mypy focal/alignment/ focal/jobs/
```

---

## PHASE 2: Safety & Configuration (After Phase 1)

**Prerequisites**: Wave 0 100% complete

Wave 1 is largely unchanged, but now operates at the **beat level**:
- Idempotency key = logical turn fingerprint (not raw message)
- AgentConfig loaded once per beat, not per message

### Agent 1A: Idempotency at Beat Level

**Prompt** (key changes from original):

```markdown
# Task: Integrate Idempotency at Beat Level

## CRITICAL CHANGE FROM ORIGINAL

Idempotency now operates on LogicalTurns, not raw messages.

Key format: `idempotency:{tenant_id}:{beat_id}` OR
            `idempotency:{tenant_id}:{hash(sorted_message_ids)}`

## Your Assignment
1. Update IdempotencyCache to work with LogicalTurn
2. Cache key includes beat_id, not single message
3. Response cached for entire beat
4. Tests verify beat-level deduplication

[Rest of original prompt applies]
```

### Agent 1B: AgentConfig Integration

**Unchanged** - AgentConfig integration remains the same.
Config is loaded once per beat in P1.6.

---

## WAVE 2: Side-Effects & Interruption (After Wave 1)

**MAJOR CHANGE**: This wave is ELEVATED from "deprioritize" to REQUIRED.

The LogicalTurn architecture **requires** side-effect awareness for safe superseding.

### Agent 2A: SideEffectPolicy

**Prompt**:

```markdown
# Task: Implement SideEffectPolicy System

## CRITICAL: This is REQUIRED for LogicalTurn Architecture

The Turn Gateway needs to know which side effects have executed
to decide if a turn can be superseded.

## Your Assignment

### Part 1: SideEffectPolicy Enum

Create/update `focal/alignment/models/side_effect.py`:

```python
from enum import Enum

class SideEffectPolicy(str, Enum):
    PURE = "pure"                   # Read-only, safe to restart
    IDEMPOTENT = "idempotent"       # Safe to retry
    COMPENSATABLE = "compensatable" # Can be undone via compensation action
    IRREVERSIBLE = "irreversible"   # Point of no return

class SideEffect(BaseModel):
    tool_name: str
    policy: SideEffectPolicy
    executed_at: datetime
    phase: int
    compensation_tool: str | None = None  # For COMPENSATABLE

    @property
    def irreversible(self) -> bool:
        return self.policy == SideEffectPolicy.IRREVERSIBLE
```

### Part 2: Tool Registry

Every tool MUST declare its policy:

```python
class ToolDefinition(BaseModel):
    # ... existing fields ...
    side_effect_policy: SideEffectPolicy = SideEffectPolicy.PURE
    confirmation_required: bool = False  # For IRREVERSIBLE
```

### Part 3: Integration with LogicalTurn

The Turn Gateway uses this to decide superseding:

```python
def _can_supersede(self, turn: LogicalTurn) -> bool:
    return not any(se.irreversible for se in turn.side_effects)
```

## Key Deliverables
1. `SideEffectPolicy` enum
2. `SideEffect` model
3. Tool declaration of policies
4. P7 records side effects to LogicalTurn
5. Turn Gateway checks before superseding
6. Tests for all scenarios
```

### Agent 2B: Supersede-Aware Pipeline

**Prompt**:

```markdown
# Task: Make Pipeline Supersede-Aware

## Your Assignment

Update AlignmentEngine to:
1. Accept interrupt_check callback
2. Check at phase boundaries (especially before P7)
3. Record side effects to LogicalTurn
4. Support artifact reuse via PhaseArtifact

```python
async def process_logical_turn(
    self,
    turn: LogicalTurn,
    interrupt_check: Callable[[], Awaitable[bool]],
    reuse_artifacts: bool = True,
) -> TurnResult:
    for phase in self.phases:
        # Check for interrupt before side-effect phases
        if phase.has_side_effects and await interrupt_check():
            return TurnResult(
                interrupted=True,
                last_phase=phase.number,
            )

        # Check artifact reuse
        if reuse_artifacts and turn.phase_artifacts.get(phase.number):
            artifact = turn.phase_artifacts[phase.number]
            if artifact.is_valid(current_fingerprint, dep_fingerprint):
                continue  # Skip this phase

        # Execute phase
        result = await phase.execute(turn)

        # Record side effects
        if phase.side_effects:
            turn.side_effects.extend(phase.side_effects)

        # Save artifact
        turn.phase_artifacts[phase.number] = PhaseArtifact(...)

    return TurnResult(response=final_response)
```

## Key Deliverables
1. `process_logical_turn()` method on AlignmentEngine
2. Interrupt checking at safe points
3. Artifact reuse logic
4. Side effect recording
5. Tests for superseding scenarios
```

---

## WAVE 3: Channel Intelligence (After Wave 2)

### Agent 3A: ChannelCapability for Accumulation

**REPURPOSED**: ChannelCapability now informs adaptive accumulation, not just formatting.

```markdown
# Task: Implement ChannelCapability for Turn Accumulation

## Context

ChannelCapability now serves TWO purposes:
1. **Accumulation hints** (NEW) - How long to wait for more messages
2. **Formatting constraints** (existing) - Max length, markdown support

## Your Assignment

```python
class ChannelCapability(BaseModel):
    channel: str

    # Accumulation behavior (NEW)
    default_turn_window_ms: int = 800
    typing_indicator_available: bool = False
    message_batching: Literal["none", "whatsapp_style", "telegram_style"] = "none"

    # Formatting (existing)
    max_message_length: int = 4096
    supports_markdown: bool = True
    supports_rich_media: bool = True
```

Wire into AdaptiveAccumulator to use channel-specific windows.
```

### Agent 3B: Abuse Detection (Background Job)

**Moved from Wave 2, now analyzes beats not raw messages**:

```markdown
# Task: Implement Abuse Detection on LogicalTurns

## Key Change

Abuse detection now analyzes LogicalTurns (beats), not raw messages.
This gives cleaner signal: "5 abusive interactions" vs "12 messages that might be 5 interactions".

[Implement as Hatchet background job]
```

---

## WAVE 4: Proactive Features (After Wave 3)

### Agent 4A: Agenda & Goals

**Enhanced to scope goals to beats**:

```markdown
# Task: Implement Agenda/Goals Scoped to Beats

## Key Enhancement

Goals are now scoped to LogicalTurns:

```python
class Goal(BaseModel):
    beat_id: UUID  # The LogicalTurn that created this goal
    # ... rest of model
```

This ensures follow-ups reference the correct conversational context.
```

---

## Deferred Features

| Feature | Reason | Revisit When |
|---------|--------|--------------|
| ScenarioConfig | Premature complexity | When AgentConfig proves insufficient |
| Hot Reload | Complex, now cleaner with beat boundaries | When deployments become painful |
| Reporter Agent | Dashboards sufficient | When tenants ask for NL analytics |
| ASA Runtime Agent | Still dangerous | Never (use design-time validator) |

---

## Post-Wave Quality Checks (MANDATORY)

```bash
# After EVERY wave
echo "=== WAVE QUALITY CHECK ===" && \
uv run ruff check focal/ && \
uv run ruff format --check focal/ && \
uv run mypy focal/ --ignore-missing-imports && \
uv run pytest tests/unit/ -v --tb=short && \
echo "=== ALL CHECKS PASSED ==="
```

---

## Summary: New Wave Structure

| Wave | Features | Agents | Dependency |
|------|----------|--------|------------|
| **0** | Turn Gateway, LogicalTurn, Session Mutex, Hatchet Workflow | 3 | NONE (foundational) |
| 1 | Idempotency (beat-level), AgentConfig | 2 | Wave 0 |
| 2 | SideEffectPolicy, Supersede-Aware Pipeline | 2 | Wave 0+1 |
| 3 | ChannelCapability (accumulation), Abuse Detection | 2 | Wave 0+1 |
| 4 | Agenda/Goals (beat-scoped) | 1-2 | Wave 0-3 |

**Total agents**: 10-12 invocations (vs 12 in original)
**Key difference**: Wave 0 is foundational, everything else builds on it

---

## Related Documents

- [ACF Architecture](architecture/ACF_ARCHITECTURE.md) - Canonical architecture (v3.0)
- [ACF Spec](architecture/ACF_SPEC.md) - Detailed ACF mechanics
- [Agent Runtime Spec](architecture/AGENT_RUNTIME_SPEC.md) - Agent lifecycle management
- [Toolbox Spec](architecture/TOOLBOX_SPEC.md) - Tool execution spec
- [LogicalTurn Impact Analysis](analysis/logical_turn_impact_analysis.md) - Architectural rationale
