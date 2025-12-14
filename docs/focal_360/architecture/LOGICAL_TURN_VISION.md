# Logical Turn (Beat) Management: Founding Vision

> **Status**: FOUNDING VISION DOCUMENT
> **Date**: 2025-12-10
> **Superseded by**: [ACF_SPEC.md](ACF_SPEC.md) (implementation-ready specification)
> **Purpose**: Captures the original architectural vision that led to the Agent Conversation Fabric (ACF)

---

## Relationship to ACF

This document captures the founding vision for best-in-class conversational turn management. The ideas here have been refined and formalized into the **Agent Conversation Fabric (ACF)** specification.

**For implementation, refer to [ACF_SPEC.md](ACF_SPEC.md)** which includes:
- Explicit boundary between ACF (mechanics) and CognitivePipeline (meaning)
- Four-state SupersedeDecision model
- Two-phase commit for tool side effects
- Pipeline-declared artifact reuse semantics
- Channel capabilities vs policies split

---

## The Key Reframing

### A Message is Not a Turn

For human-like UX, the semantic unit is a **conversational beat**:

* 1 or more rapid messages that form one coherent user intent.
* Example: "Hello" → "How are you?" should yield **one** response.

The legacy pipeline spec processed “a single user message through 11 phases.” With ACF, the pipeline runs **once per LogicalTurn** (one or more messages).
Best-in-class adds a layer **above** that acting as a *Turn Gateway*.

---

## The "Perfect" Architecture (Best-in-Class Everywhere)

### 1) Session Actor / Single-Writer Rule (Foundation)

**Rule:** No two pipeline executions concurrently for the same logical conversation key:
`(tenant_id, agent_id, customer_id, channel_identity)`.

This is the "session mutex." It prevents:

* scenario/rule race conditions
* double-advancement
* inconsistent audit trails

This pattern exists in production bot frameworks:
**Rasa uses a lock store** to ensure only one message for a conversation is processed at a time.

**Minimal sketch:**

```python
# Redis-based session mutex
lock_key = f"sesslock:{tenant}:{agent}:{customer}:{channel}"

with redis.lock(lock_key, timeout=30, blocking_timeout=5):
    # Only one active logical turn runner here
    handle_incoming_message(msg)
```

---

### 2) First-Class LogicalTurn (Beat) Object

```python
class LogicalTurn(BaseModel):
    id: UUID
    session_key: str
    messages: list[UserMessage]  # ordered
    status: Literal["ACCUMULATING", "PROCESSING", "COMPLETE", "SUPERSEDED"]

    # for adaptive waiting
    first_at: datetime
    last_at: datetime
    completion_confidence: float = 0.0
    completion_reason: str | None = None  # timeout | ai_predicted | explicit_signal

    # for "don't redo everything"
    phase_artifacts: dict[int, "PhaseArtifact"] = {}
    side_effects: list["SideEffect"] = []
```

**Critical semantics:**

* **Scenario/rule advancement commits at turn completion**, not per raw message.
  This avoids thrashing when a user says "yes… wait no."

---

### 3) Adaptive Accumulation Instead of Dumb Microbatch

Best-in-class uses **adaptive silence windows** with *channel + user pattern awareness*:

**Signals (ranked):**

1. **Required-info missing** (from P6/P8 plan):
   if the plan says "ASK order_id," you can *expect more user input soon*.
2. **User typing cadence stats** (per customer, per channel)
3. **Message shape**:
   * greeting-only
   * fragment
   * incomplete entity ("Order #")
4. **Channel hints** (if available later)

**Algorithm sketch:**

```python
def suggested_wait_ms(msg, session_stats, channel_profile, plan_hint=None):
    base = channel_profile.default_turn_window_ms  # e.g., 800-1500
    if msg.is_greeting_only:
        base += 500
    if plan_hint == "awaiting_required_field":
        base += 1000
    base = adapt_to_user_cadence(base, session_stats.inter_message_p95_ms)
    return clamp(base, 200, 3000)
```

This is **turn-taking**, not rate limiting.

---

### 4) Superseding with Checkpoint Reuse ("Don't Redo Everything")

#### The Principle

When a new message arrives:

* **Before commit points** → supersede current logical turn.
* **After irreversible side effects** → finish current turn, queue next.

But the best-in-class twist is:

> **Reuse phase artifacts whose inputs are still valid.**

#### PhaseArtifact with Fingerprints

```python
class PhaseArtifact(BaseModel):
    phase: int
    data: dict
    input_fingerprint: str
    dependency_fingerprint: str  # e.g., session_state_version, ruleset_version
    created_at: datetime

def is_valid(artifact, new_fp, new_dep_fp) -> bool:
    return artifact.input_fingerprint == new_fp and \
           artifact.dependency_fingerprint == new_dep_fp
```

#### What This Buys You

If Message B arrives right after Message A:

* You **reuse P1** (identity/context loading) unless session changed.
* You may reuse P4 retrieval if the intent fingerprint is unchanged.
* You almost always recompute P2 snapshot (cheap) because it depends on the new message list.

This also aligns with the design principle of **stateless pods** because artifacts live in external stores.

---

### 5) Tool Side-Effect Policy as First-Class Contract

The core risk is **business-system mutation**.

Best-in-class categorization:

```python
class SideEffectPolicy(str, Enum):
    PURE = "pure"                 # read-only, safe to restart
    IDEMPOTENT = "idempotent"     # safe to retry
    COMPENSATABLE = "compensatable"  # can be undone via known action
    IRREVERSIBLE = "irreversible"    # point of no return
```

**Runtime rule:**

* The system can absorb/supersede freely until it hits a non-PURE tool
* For COMPENSATABLE/IRREVERSIBLE tools:
  * check for newer messages and explicit cancel intents
  * optionally require a confirmation pattern in the scenario

---

### 6) ASA's Expanded Responsibility (Design-Time Safety)

**ASA as a "side-effect strategist."**
When a tenant defines tools/scenarios, ASA:

* forces every tool to declare a SideEffectPolicy
* proposes compensation workflows
* generates edge-case rules
  *"If a customer does X then cancels, what do we do?"*
* verifies that scenario steps clearly encode commit points

This makes side effects **visible and controllable** in the "deterministic control" philosophy.

---

### 7) Hatchet as the Non-Sticky "Actor Runtime"

This is the cleanest way to get actor-like behavior without sticky pods.

Hatchet's durable execution model stores intermediate results so workflows can resume and can "wait for an event" without occupying a worker slot.

Map it like this:

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.step()
    async def acquire_lock(self, ctx):
        await redis_lock(ctx.input["session_key"])

    @hatchet.step()
    async def accumulate(self, ctx):
        turn = init_turn(ctx.input["message"])
        while True:
            wait_ms = assess_completion_window(turn)
            event = await ctx.wait_for_event(
                timeout_ms=wait_ms,
                event_types=["new_message"]
            )
            if not event:
                turn.status = "PROCESSING"
                return {"turn": turn.model_dump()}
            turn.messages.append(event.payload)

    @hatchet.step()
    async def run_pipeline(self, ctx):
        turn = LogicalTurn(**ctx.step_output("accumulate")["turn"])

        result = await alignment_engine.process_logical_turn(
            messages=turn.messages,
            reuse_artifacts=turn.phase_artifacts,
            interrupt_check=lambda: ctx.check_event("new_message", block=False),
            side_effect_guard=True,  # honor policies
        )
        return result

    @hatchet.step()
    async def commit_and_respond(self, ctx):
        # commit scenario transitions atomically
        # persist TurnRecord with beat/message links
        # send response via channel adapter
        pass
```

This looks like an **actor**:

* A single logical entity per session
* Processes messages sequentially
* Maintains durable state
* Eliminates internal race conditions

**What is an actor?**
In the actor model, each actor owns its state and processes messages one at a time from a mailbox; this makes concurrency safer by design. Frameworks like **Akka** implement this and pair well with event sourcing.
**Orleans** offers "virtual actors," scaling the actor concept across distributed systems.

---

## What This Implies Across Dimensions

### Software Engineering

**You add one layer, not rewrite everything:**

* A **Turn Gateway** that creates/manages LogicalTurns
* Minor adjustments in the engine:
  * accept `messages: list[str]` instead of a single message
  * checkpoint artifacts
  * consult SideEffectPolicy before P7

The phases stay intact.

### User Feel

You get:

* human-like pacing
* fewer "double replies"
* safer handling of cancellations
* better multi-intent coherence

### Scalability

* Still horizontally scalable because:
  * pods remain stateless
  * state is in Hatchet/Redis/DB
* Lock contention is naturally capped per session key.

### Resource Consumption

Costs:
* slight latency from accumulation window
* small storage for artifacts + richer TurnRecords

Gains:
* fewer redundant phase computations on supersede
* fewer unnecessary tool calls

---

## Reference Systems

Not with the exact 11-phase + scenario/rule stack, but the building blocks are real and proven:

* **Rasa**: conversation-level locking to avoid concurrent processing for the same conversation.
* **Akka Persistence**: event-sourced actors where state is rebuilt from stored events.
* **Orleans**: virtual actor model for scalable per-entity state + message handling.
* **Hatchet**: durable workflows that persist intermediate results and support event waits.

This architecture combines:
**bot turn management + actor single-writer + durable workflow + alignment phases.**

---

## Option Matrix (Conceptual)

| Option | Core idea | Human-like UX | Safety vs mid-turn cancel | Scaling | "Don't redo everything" |
|--------|-----------|---------------|---------------------------|---------|-------------------------|
| Plain pipeline | 1 message = 1 turn | Low | Medium | Great | N/A |
| Fixed microbatch | time-window merge | Medium | Medium | Good | Low |
| Session mutex + supersede | single-writer, restart before P7 | High | High | Great | Medium |
| Full LogicalTurn (Beat) layer | beats as first-class | Very high | Very high | Great | High |
| Actor + event sourcing | beats as projections | Very high | Very high | Complex but strong | Very high |

The best-in-class target is the **LogicalTurn + session actor + Hatchet durability + artifact reuse** combo.

---

## The "Perfect" Minimal Data-Model Insurance

Even if rolled out gradually, reserve the abstractions now:

```python
class TurnRecord(BaseModel):
    turn_id: UUID
    beat_id: UUID | None = None  # default = turn_id for now
    message_sequence: list[UUID] = []
    superseded_by: UUID | None = None

    # optional:
    interruptions: list[dict] = []
    phase_artifact_summaries: dict[int, dict] = {}
```

This avoids painful production refactors later.

---

## Recommendation Summary

If you want **one architecture that can be configured up/down later** (per channel, per agent), this is it:

1. **Turn Gateway**
   * adaptive accumulation
   * session mutex
   * builds LogicalTurn

2. **Engine upgrades**
   * multi-message input support
   * artifact fingerprints
   * supersede-aware execution

3. **SideEffectPolicy**
   * declared per tool
   * enforced before P7

4. **Hatchet as the runtime**
   * each LogicalTurn as a durable workflow instance
   * events = new messages

This keeps the Soldier philosophy intact while providing "best in class everywhere."

---

## References

- [Rasa Lock Stores](https://rasa.com/docs/rasa/next/lock-stores/)
- [Hatchet Durable Execution](https://docs.hatchet.run/home/features/durable-execution)
- [Akka Event Sourcing](https://doc.akka.io/libraries/akka-core/current/typed/persistence.html)
