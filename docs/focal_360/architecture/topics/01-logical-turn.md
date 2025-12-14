# LogicalTurn (Beat) Model

> **Topic**: Core data model for conversational beats
> **ACF Component**: Core abstraction owned by Agent Conversation Fabric
> **Dependencies**: None (foundational)
> **Impacts**: All pipeline phases, TurnRecord, Session management
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification (incl. Orchestration Modes)

---

## ACF Context

LogicalTurn is the **central abstraction** in the Agent Conversation Fabric. ACF owns the LogicalTurn lifecycle (creation, accumulation, state transitions) while CognitivePipeline operates on a LogicalTurn to produce meaning.

### ACF Ownership

| Aspect | Owner | Description |
|--------|-------|-------------|
| Creation | ACF | Creates LogicalTurn from first RawMessage |
| Accumulation | ACF | Adds messages, tracks timing |
| Status Transitions | ACF | ACCUMULATING → PROCESSING → COMPLETE/SUPERSEDED |
| Supersede Decisions | CognitivePipeline (via ACF) | Pipeline advises, ACF enforces |
| Artifact Storage | ACF | Stores phase artifacts |
| Side Effect Tracking | ACF | Records executed effects |

---

## Overview

A **LogicalTurn** (or "beat") is the atomic unit of user intent in a conversation. It may contain one or more raw messages that together form a single coherent request.

### The Problem

```
User sends: "Hello"
User sends: "How are you?"
                          ← 200ms apart

Current behavior: Agent responds TWICE
Desired behavior: Agent responds ONCE to the combined intent
```

### The Solution

Introduce a first-class `LogicalTurn` object that:
1. Accumulates rapid messages
2. Tracks processing status
3. Enables safe superseding
4. Supports checkpoint reuse

---

## Data Model

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class LogicalTurnStatus(str, Enum):
    """Lifecycle states for a logical turn (ACF-managed)."""
    ACCUMULATING = "accumulating"  # Waiting for more messages
    PROCESSING = "processing"       # Pipeline is running
    COMPLETE = "complete"           # Response sent successfully
    SUPERSEDED = "superseded"       # Cancelled by newer turn


class SupersedeAction(str, Enum):
    """
    Four-state supersede model (ACF core concept).

    When a new message arrives during processing, CognitivePipeline
    advises ACF which action to take. ACF enforces the decision.

    Note: SupersedeAction is the enum of possible actions.
    SupersedeDecision (in ACF_SPEC) is the full model: action + absorb_strategy + reason.
    """
    SUPERSEDE = "supersede"       # Cancel current, start new with all messages
    ABSORB = "absorb"             # Add message to current turn, may restart from checkpoint
    QUEUE = "queue"               # Finish current, then process new as separate turn
    FORCE_COMPLETE = "force_complete"  # Almost done, just finish (ignore new message briefly)

class LogicalTurn(BaseModel):
    """
    A conversational beat: the atomic unit of user intent.

    A LogicalTurn may contain multiple raw messages that arrived
    in rapid succession and should be treated as one request.
    """

    id: UUID = Field(default_factory=uuid4)
    session_key: str  # Composite: tenant:agent:customer:channel

    # Turn grouping for idempotency scoping
    turn_group_id: UUID = Field(default_factory=uuid4)
    """
    Groups turns in a supersede chain. Same turn_group_id = same conversation attempt.

    - Turns in supersede chain (A→B→C) share same turn_group_id (inherited from A)
    - QUEUE decision creates NEW turn_group_id (different conversation attempt)
    - Used in tool idempotency keys: "{tool}:{business_key}:turn_group:{turn_group_id}"

    Example: User says "Refund order #123" → turn A
             User says "Actually order #456" → turn B (supersedes A, same turn_group_id)
             Both try to execute refund tool → same idempotency key → one refund
    """

    # Message accumulation
    messages: list[UUID] = Field(default_factory=list)  # Ordered message IDs
    status: LogicalTurnStatus = LogicalTurnStatus.ACCUMULATING

    # Timing for adaptive accumulation
    first_at: datetime  # When first message arrived
    last_at: datetime   # When last message arrived

    # Completion detection
    completion_confidence: float = 0.0
    completion_reason: str | None = None
    # Possible reasons: "timeout", "ai_predicted", "explicit_signal", "channel_hint"

    # Checkpoint reuse (see: 05-checkpoint-reuse.md)
    phase_artifacts: dict[int, "PhaseArtifact"] = Field(default_factory=dict)

    # Side effect tracking (see: 04-side-effect-policy.md)
    side_effects: list["SideEffect"] = Field(default_factory=list)

    # Scenario state snapshot for safe superseding
    scenario_states_at_start: dict[UUID, "ScenarioStepRef"] = Field(default_factory=dict)

    # Supersede tracking (ACF)
    superseded_by: UUID | None = None  # If superseded, which turn replaced this
    superseded_from: UUID | None = None  # If this superseded another, which turn
    interrupt_point: str | None = None  # Where in pipeline when interrupted

    def can_absorb_message(self) -> bool:
        """
        Determine if this turn can absorb another incoming message.

        Note: This is a quick check. For PROCESSING status, ACF will
        consult CognitivePipeline via decide_supersede() for the full decision.

        Returns:
            True if message can potentially be added to this turn
        """
        if self.status in [LogicalTurnStatus.COMPLETE, LogicalTurnStatus.SUPERSEDED]:
            return False

        if self.status == LogicalTurnStatus.PROCESSING:
            # Can only absorb if no irreversible side effects executed yet
            # Full decision requires consulting CognitivePipeline
            return not any(se.irreversible for se in self.side_effects)

        # ACCUMULATING status - always can absorb
        return True

    def absorb_message(self, message_id: UUID, timestamp: datetime) -> None:
        """Add a message to this turn."""
        if not self.can_absorb_message():
            raise ValueError(f"Cannot absorb message in status {self.status}")
        self.messages.append(message_id)
        self.last_at = timestamp

    def mark_processing(self, reason: str = "timeout") -> None:
        """Transition from ACCUMULATING to PROCESSING."""
        if self.status != LogicalTurnStatus.ACCUMULATING:
            raise ValueError(f"Cannot start processing from status {self.status}")
        self.status = LogicalTurnStatus.PROCESSING
        self.completion_reason = reason

    def mark_complete(self) -> None:
        """Mark turn as successfully completed."""
        self.status = LogicalTurnStatus.COMPLETE

    def mark_superseded(self, by_turn_id: UUID | None = None, at_point: str | None = None) -> None:
        """Mark turn as superseded by a newer turn."""
        self.status = LogicalTurnStatus.SUPERSEDED
        self.superseded_by = by_turn_id
        self.interrupt_point = at_point
```

---

## SupersedeDecision Flow

When a new message arrives during PROCESSING, ACF coordinates with CognitivePipeline:

```
New Message Arrives
        │
        ▼
┌───────────────────────┐
│ ACF checks turn state │
│ - Has commit point?   │
│ - Has IRREVERSIBLE?   │
└───────────┬───────────┘
            │
            ▼ (if no automatic decision)
┌───────────────────────────────────────┐
│ ACF calls Pipeline.decide_supersede() │
│ - current: LogicalTurn                │
│ - new: RawMessage                     │
│ - interrupt_point: str                │
└───────────────────┬───────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
  SUPERSEDE/ABSORB         QUEUE/FORCE_COMPLETE
        │                       │
        ▼                       ▼
  Restart with            Finish current,
  all messages            then process new
```

### Decision Matrix

| Scenario | Decision | Why |
|----------|----------|-----|
| "Book Paris" → "I meant London" | SUPERSEDE | Correction invalidates intent |
| "Refund order" → "Order #12345" | ABSORB | Clarification completes intent |
| New message after tool executed | QUEUE | Commit point reached |
| Response 90% generated | FORCE_COMPLETE | Almost done, finish first |

---

## Turn Group ID and Idempotency

The `turn_group_id` field enables precise idempotency scoping for tool execution.

### Inheritance Rules

```python
def handle_supersede_decision(
    decision: SupersedeDecision,
    current_turn: LogicalTurn,
    new_message: RawMessage,
) -> LogicalTurn:
    """Create new turn based on supersede decision."""

    if decision.action == SupersedeAction.SUPERSEDE:
        # Inherit turn_group_id - same conversation attempt
        return LogicalTurn(
            session_key=current_turn.session_key,
            turn_group_id=current_turn.turn_group_id,  # INHERITED
            messages=[new_message.id],
            superseded_from=current_turn.id,
            first_at=new_message.timestamp,
            last_at=new_message.timestamp,
        )

    elif decision.action == SupersedeAction.ABSORB:
        # Same turn, just add message
        current_turn.messages.append(new_message.id)
        current_turn.last_at = new_message.timestamp
        return current_turn

    elif decision.action == SupersedeAction.QUEUE:
        # NEW turn_group_id - different conversation attempt
        return LogicalTurn(
            session_key=current_turn.session_key,
            turn_group_id=uuid4(),  # NEW
            messages=[new_message.id],
            first_at=new_message.timestamp,
            last_at=new_message.timestamp,
        )

    # FORCE_COMPLETE: no new turn created
    return current_turn
```

### Tool Idempotency Key Construction

```python
def build_tool_idempotency_key(
    tool_name: str,
    business_key: str,
    turn: LogicalTurn,
) -> str:
    """
    Build idempotency key scoped to turn group.

    This ensures:
    - Supersede chain shares key → one execution
    - QUEUE creates new key → allows re-execution in new context
    """
    return f"{tool_name}:{business_key}:turn_group:{turn.turn_group_id}"
```

---

## Session Key Format

The session key uniquely identifies a conversation stream:

```python
def build_session_key(
    tenant_id: UUID,
    agent_id: UUID,
    customer_id: UUID,
    channel: str,
) -> str:
    """
    Build composite session key.

    Format: {tenant_id}:{agent_id}:{customer_id}:{channel}

    This key is used for:
    - Session mutex (single-writer rule)
    - Turn store lookups
    - Hatchet workflow correlation
    """
    return f"{tenant_id}:{agent_id}:{customer_id}:{channel}"
```

---

## Lifecycle

```
                    ┌─────────────────┐
                    │  Message Arrives │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ACCUMULATING   │◄──────┐
                    └────────┬────────┘       │
                             │                │
              ┌──────────────┼──────────────┐ │
              │              │              │ │
     Window expires    New message    Explicit signal
              │              │              │ │
              │              └──────────────┘ │
              │                   (absorb)    │
              │                               │
              ▼                               │
     ┌────────────────┐                       │
     │   PROCESSING   │───────────────────────┘
     └────────┬───────┘    (if can_absorb and
              │             no irreversible effects)
              │
    ┌─────────┴─────────┐
    │                   │
Success            Superseded
    │                   │
    ▼                   ▼
┌──────────┐    ┌─────────────┐
│ COMPLETE │    │ SUPERSEDED  │
└──────────┘    └─────────────┘
```

---

## Integration Points

### TurnRecord (Audit)

```python
class TurnRecord(BaseModel):
    turn_id: UUID
    beat_id: UUID | None = None  # Links to LogicalTurn.id
    message_sequence: list[UUID] = []  # All raw messages
    superseded_by: UUID | None = None  # If superseded
```

### Session State

```python
class Session(BaseModel):
    # Existing fields...

    # NEW: Pending scenario transition (commit on turn complete)
    pending_scenario_transition: ScenarioStepRef | None = None
```

### AlignmentEngine

```python
async def process_logical_turn(
    self,
    turn: LogicalTurn,
    interrupt_check: Callable[[], Awaitable[bool]],
    reuse_artifacts: bool = True,
) -> TurnResult:
    """Process a logical turn instead of single message."""
    ...
```

---

## Configuration

```toml
[pipeline.logical_turn]
enabled = true
default_accumulation_window_ms = 800
max_accumulation_window_ms = 3000
min_accumulation_window_ms = 200
```

---

## Testing Considerations

```python
# Test: Multiple messages form one turn
async def test_rapid_messages_form_single_turn():
    turn = LogicalTurn(
        session_key="tenant:agent:customer:web",
        messages=[msg1.id],
        first_at=now,
        last_at=now,
    )
    assert turn.can_absorb_message()

    turn.absorb_message(msg2.id, now + timedelta(milliseconds=100))
    assert len(turn.messages) == 2
    assert turn.status == LogicalTurnStatus.ACCUMULATING

# Test: Cannot absorb after irreversible effect
async def test_cannot_absorb_after_irreversible():
    turn = LogicalTurn(...)
    turn.status = LogicalTurnStatus.PROCESSING
    turn.side_effects = [SideEffect(policy=SideEffectPolicy.IRREVERSIBLE, ...)]

    assert not turn.can_absorb_message()
```

---

## ACF FabricEvent Stream

ACF emits events for observability and audit:

```python
class FabricEventType(str, Enum):
    TURN_STARTED = "turn_started"
    MESSAGE_ABSORBED = "message_absorbed"
    SUPERSEDE_REQUESTED = "supersede_requested"
    SUPERSEDE_EXECUTED = "supersede_executed"
    COMMIT_POINT_REACHED = "commit_point_reached"
    TOOL_AUTHORIZED = "tool_authorized"
    TOOL_EXECUTED = "tool_executed"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"

class FabricEvent(BaseModel):
    """Audit event emitted by ACF."""
    type: FabricEventType  # Canonical field name (not event_type)
    logical_turn_id: UUID
    session_key: str
    timestamp: datetime
    payload: dict
```

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [02-session-mutex.md](02-session-mutex.md) - Single-writer rule (ACF component)
- [03-adaptive-accumulation.md](03-adaptive-accumulation.md) - Window timing (ACF component)
- [04-side-effect-policy.md](04-side-effect-policy.md) - Effect classification (ACF component)
- [05-checkpoint-reuse.md](05-checkpoint-reuse.md) - PhaseArtifact model (Pipeline-declared)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Workflow orchestration (ACF runtime)
