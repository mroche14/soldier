# LogicalTurn Architecture: Impact on FOCAL 360 Waves

> **Date**: 2025-12-10
> **Purpose**: Analyze how the LogicalTurn (Beat) architecture changes the FOCAL 360 wave structure
> **Status**: ARCHITECTURAL REVISION

---

## Executive Summary

The introduction of **LogicalTurn (Beat) Management** as a foundational layer fundamentally restructures the FOCAL 360 implementation. Rather than 6 independent feature waves, we now have:

1. **Wave 0 (NEW)**: Turn Gateway Foundation - the actor-style per-session coordinator
2. **Waves 1-6**: Features that build ON TOP of the Turn Gateway

### Key Insight

> "A message is not a turn."

The semantic unit is a **conversational beat**: one or more rapid messages that form one coherent user intent. This reframe changes everything.

---

## The New Wave Structure

### Before: Independent Feature Waves

```
Wave 1: Idempotency + AgentConfig
Wave 2: Debouncing + Abuse Detection
Wave 3: ChannelCapability + ScenarioConfig
Wave 4: SideEffectRegistry + Turn Cancellation
Wave 5: Agenda/Goals + Hot Reload
Wave 6: Reporter + ASA
```

### After: Foundation + Feature Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WAVE 0: TURN GATEWAY                         │
│  LogicalTurn + Session Actor + Hatchet Orchestration + PhaseArtifacts│
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼───────┐          ┌────────▼────────┐         ┌────────▼────────┐
│   WAVE 1      │          │    WAVE 2       │         │    WAVE 3       │
│  Foundation   │          │  Side-Effects   │         │   Proactive     │
│  (Config)     │          │  & Interruption │         │   (Agenda)      │
└───────────────┘          └─────────────────┘         └─────────────────┘
```

---

## Wave-by-Wave Impact Analysis

### Wave 0: Turn Gateway (NEW - FOUNDATIONAL)

**This wave MUST come first.** Everything else depends on it.

#### Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `LogicalTurn` model | First-class beat object | Medium |
| Session Mutex | Single-writer rule per session | Low |
| Turn Gateway | Ingress controller for message arrival | High |
| Adaptive Accumulation | Channel/user-aware waiting | Medium |
| Hatchet `LogicalTurnWorkflow` | Durable execution substrate | High |
| `PhaseArtifact` | Checkpoint reuse mechanism | Medium |

#### Key Data Models

```python
class LogicalTurn(BaseModel):
    id: UUID
    session_key: str
    messages: list[UserMessage]  # ordered
    status: Literal["ACCUMULATING", "PROCESSING", "COMPLETE", "SUPERSEDED"]

    # Adaptive waiting
    first_at: datetime
    last_at: datetime
    completion_confidence: float = 0.0
    completion_reason: str | None = None  # timeout | ai_predicted | explicit_signal

    # Checkpoint reuse
    phase_artifacts: dict[int, PhaseArtifact] = {}
    side_effects: list[SideEffect] = []

class PhaseArtifact(BaseModel):
    phase: int
    data: dict
    input_fingerprint: str
    dependency_fingerprint: str  # session_state_version, ruleset_version
    created_at: datetime
```

#### Critical Semantics

1. **Scenario advancement commits at turn completion**, not per raw message
2. **Superseding with checkpoint reuse**: Don't redo P1-P6 if inputs unchanged
3. **Session mutex**: No concurrent brain runs for same `(tenant, agent, customer, channel)`

#### Hatchet Integration

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
            side_effect_guard=True,
        )
        return result

    @hatchet.step()
    async def commit_and_respond(self, ctx):
        # Commit scenario transitions atomically
        # Persist TurnRecord with beat/message links
        # Send response via channel adapter
        pass
```

#### Estimated Effort

**5-8 days** for core implementation, plus integration testing.

---

### Wave 1: Foundation (Config) - REVISED

**Original Scope**: Idempotency + AgentConfig
**New Scope**: Idempotency + AgentConfig + TurnRecord Extensions

#### What Changes

| Original Task | Impact | New Status |
|---------------|--------|------------|
| Idempotency integration | **Now operates at LogicalTurn level**, not raw message | MODIFIED |
| AgentConfig integration | Unchanged | KEEP |
| --- | --- | --- |
| TurnRecord extensions | **NEW**: Add `beat_id`, `message_sequence`, `superseded_by` | NEW |

#### Idempotency Changes

**Before**: Idempotency key = raw message fingerprint
**After**: Idempotency key = logical turn fingerprint (all accumulated messages)

```python
# Old: One message = one idempotency check
idempotency_key = f"{tenant}:{hash(message)}"

# New: Logical turn = one idempotency check
idempotency_key = f"{tenant}:{logical_turn.id}"
# OR
idempotency_key = f"{tenant}:{hash(sorted(m.id for m in logical_turn.messages))}"
```

#### TurnRecord Extensions (Data Model Insurance)

```python
class TurnRecord(BaseModel):
    turn_id: UUID
    beat_id: UUID | None = None  # Default to turn_id for backwards compatibility
    message_sequence: list[UUID] = []  # Raw messages in this logical turn
    superseded_by: UUID | None = None  # If this turn was cancelled

    # Optional observability
    interruptions: list[dict] = []  # Cancel attempts, supersede events
    phase_artifact_summaries: dict[int, dict] = {}  # What was reused
```

#### Revised Effort

**Original**: 3-6 days
**New**: 4-7 days (additional TurnRecord work)

---

### Wave 2: Ingress & Safety - MASSIVELY REVISED

**Original Scope**: Debouncing + Abuse Detection
**New Scope**: ABSORBED INTO WAVE 0 + Abuse Detection

#### Critical Change: "Debouncing" No Longer Exists

The original Wave 2 "debouncing" feature is **completely replaced** by Wave 0's LogicalTurn layer.

| Original Concept | New Concept |
|------------------|-------------|
| Time-based message coalescing | Adaptive accumulation with completion signals |
| Fixed 50-200ms window | Channel-aware, user-cadence-aware waiting |
| Simple merge | Intelligent beat boundary detection |

**Wave 2 "Debouncing" becomes:**
- The accumulation logic in `LogicalTurnWorkflow.accumulate()`
- The `assess_completion_window()` function
- The "is user done typing?" prediction

#### What Remains in Wave 2

Only **Abuse Detection** remains, and it's cleaner now:

```python
class AbuseDetectionWorkflow:
    """Analyze logical turn patterns, not raw messages."""

    async def detect_patterns(self, tenant_id: UUID):
        # Now we analyze LogicalTurns, not raw messages
        # Much cleaner signal: "X abusive beats" vs "X messages that might be one intent"

        recent_turns = await audit_store.get_recent_logical_turns(
            tenant_id=tenant_id,
            hours=24,
        )

        for customer_id, turns in group_by_customer(recent_turns):
            if count_safety_refusals(turns) > 5:
                yield AbuseAlert(customer_id, "repeated_policy_violations")
```

#### Revised Effort

**Original**: 3-5 days
**New**: 1-2 days (abuse detection only, debouncing absorbed into Wave 0)

---

### Wave 3: Config & Channels - SIMPLIFIED

**Original Scope**: ChannelCapability + ScenarioConfig
**New Scope**: Channel-Aware Accumulation Config Only

#### What Changes

| Original Task | Impact | New Status |
|---------------|--------|------------|
| ChannelCapability model | **Repurposed**: Now provides accumulation hints | REPURPOSED |
| ScenarioConfig | Still too complex, still deferred | DEFER |

#### ChannelCapability Repurposed

Instead of duplicating formatter metadata, `ChannelCapability` now informs **adaptive accumulation**:

```python
class ChannelCapability(BaseModel):
    """Channel characteristics for turn boundary detection."""

    channel: str

    # Accumulation behavior
    default_turn_window_ms: int = 800  # Base wait time
    typing_indicator_available: bool = False
    message_batching: Literal["none", "whatsapp_style", "telegram_style"] = "none"

    # Still useful for formatters
    max_message_length: int = 4096
    supports_markdown: bool = True
    supports_rich_media: bool = True
```

This is **useful and non-duplicative**:
- Formatters handle output transformation
- ChannelCapability informs input accumulation behavior

#### Revised Scope

**Wave 3 becomes**: "Channel-Aware Turn Accumulation"
- Define ChannelCapability model (as above)
- Wire into `assess_completion_window()` in Turn Gateway
- Skip ScenarioConfig (still premature)

#### Revised Effort

**Original**: 5-7 days
**New**: 2-3 days (focused scope)

---

### Wave 4: Side-Effects & Tools - VALIDATED AND ELEVATED

**Original Scope**: SideEffectRegistry + Turn Cancellation
**New Scope**: SideEffectPolicy + Supersede-Aware Execution

#### Critical Change: No Longer "Deprioritized"

The original analysis said Wave 4 was "over-engineered for a rare edge case." The LogicalTurn architecture **validates and requires** this feature:

| Original Problem | Why It's Real Now |
|------------------|-------------------|
| "User can't type 'CANCEL' fast enough" | **Wrong frame**: New message = implicit supersede |
| "Race conditions unavoidable" | **Solved**: Single-writer mutex + atomic phase checkpoints |
| "Partial execution inconsistencies" | **Solved**: SideEffectPolicy + checkpoint reuse |

#### SideEffectPolicy is Now Required

```python
class SideEffectPolicy(str, Enum):
    PURE = "pure"                   # Read-only, safe to restart
    IDEMPOTENT = "idempotent"       # Safe to retry
    COMPENSATABLE = "compensatable" # Can be undone
    IRREVERSIBLE = "irreversible"   # Point of no return
```

**Every tool MUST declare a policy.** This enables:
- **Safe superseding**: Can absorb new message if only PURE tools executed
- **Checkpoint optimization**: Reuse artifacts from PURE phases
- **Clear commit points**: User warned before IRREVERSIBLE actions

#### Supersede-Aware Execution

```python
async def run_pipeline_with_supersede(
    self,
    turn: LogicalTurn,
    interrupt_check: Callable[[], bool],
):
    for phase in PHASES:
        # Check for supersede before committing phase
        if phase.has_side_effects and interrupt_check():
            turn.status = "SUPERSEDED"
            return SupersededResult(phase=phase.number)

        # Check artifact reuse
        if turn.phase_artifacts.get(phase.number):
            if self._artifact_still_valid(turn.phase_artifacts[phase.number], turn):
                continue  # Reuse

        result = await phase.execute(turn)
        turn.phase_artifacts[phase.number] = PhaseArtifact(
            phase=phase.number,
            data=result,
            input_fingerprint=self._compute_fingerprint(turn, phase),
        )
```

#### ASA's New Role: Side-Effect Strategist

From your vision:
> "ASA as a 'side-effect strategist.' When a tenant defines tools/scenarios, ASA forces every tool to declare a SideEffectPolicy, proposes compensation workflows, generates edge-case rules."

This is **design-time safety**, not runtime complexity.

#### Revised Effort

**Original**: 6-10 days (deprioritized)
**New**: 4-6 days (elevated, required for Turn Gateway)

---

### Wave 5: Lifecycle & Proactive - ENHANCED

**Original Scope**: Agenda/Goals (proceed) + Hot Reload (defer)
**New Scope**: Agenda/Goals ENHANCED + Hot Reload (still defer)

#### Agenda/Goals Enhancement

The LogicalTurn architecture **improves** Agenda/Goals:

| Original Design | Enhanced Design |
|-----------------|-----------------|
| Follow-up triggered by message count | Follow-up triggered by **beat completion** |
| Goal evaluated per message | Goal evaluated per **logical turn** |
| Unclear turn boundaries | Clear: beat = atomic intent unit |

```python
class Goal(BaseModel):
    """Proactive follow-up attached to a logical turn."""

    id: UUID
    beat_id: UUID  # The logical turn that created this goal

    trigger_condition: str  # "no_response_24h" | "case_unresolved_3d"
    action: str  # "send_follow_up" | "escalate"

    # Cleaner: goals are scoped to beats, not raw messages
    context_from_beat: dict  # Snapshot from the beat that created it
```

#### Hot Reload: Still Deferred, But Now Cleaner

Hot Reload is still complex, but the LogicalTurn architecture makes it **conceptually cleaner**:

- **Reload boundary**: Between logical turns, not between raw messages
- **Pinning**: `LogicalTurn.config_version` is natural
- **Atomicity**: Turn completes with old config OR starts fresh with new config

Still defer, but future implementation is less scary.

#### Revised Effort

**Original**: 3-5 days (Agenda only)
**New**: 4-6 days (enhanced integration with beats)

---

### Wave 6: Meta-Agents - STILL SKIP, BUT ASA ROLE CLARIFIED

**Original Scope**: Reporter + ASA (both skip)
**New Scope**: Skip runtime agents, but ASA becomes design-time tool

#### Reporter: Still Skip

No change. Dashboards are still better than conversational analytics.

#### ASA: Design-Time Tool, Not Runtime Agent

From your vision, ASA's role is clarified:

> "When a tenant defines tools/scenarios, ASA forces every tool to declare a SideEffectPolicy, proposes compensation workflows, generates edge-case rules."

**This is NOT a runtime agent.** It's:
- A **wizard/validator** in the configuration UI
- A **static analyzer** for scenario definitions
- A **suggestion engine** for edge cases

```python
class ASAValidator:
    """Design-time validation for tools and scenarios."""

    def validate_tool(self, tool: ToolDefinition) -> list[Issue]:
        issues = []
        if not tool.side_effect_policy:
            issues.append(Issue(
                severity="error",
                message="Tool must declare SideEffectPolicy",
            ))
        if tool.side_effect_policy == "irreversible" and not tool.confirmation_required:
            issues.append(Issue(
                severity="warning",
                message="Irreversible tool should require confirmation",
            ))
        return issues

    def suggest_edge_cases(self, scenario: Scenario) -> list[SuggestedRule]:
        """Generate edge-case rules based on scenario structure."""
        suggestions = []
        for step in scenario.steps:
            if step.has_irreversible_tool:
                suggestions.append(SuggestedRule(
                    name=f"cancel_before_{step.name}",
                    trigger="user says 'cancel' or 'wait'",
                    action="confirm before proceeding",
                ))
        return suggestions
```

This is **much safer** than a runtime agent that modifies production configs.

#### Revised Effort

**Original**: Skip
**New**: ASA Validator can be built incrementally (2-3 days for basic validation)

---

## Revised Roadmap

### Phase 0: Turn Gateway Foundation (Weeks 1-2)

| Task | Effort | Priority | Dependency |
|------|--------|----------|------------|
| `LogicalTurn` model | 1 day | CRITICAL | None |
| Session mutex (Redis) | 1 day | CRITICAL | None |
| `PhaseArtifact` model + fingerprinting | 2 days | CRITICAL | LogicalTurn |
| Hatchet `LogicalTurnWorkflow` | 3 days | CRITICAL | All above |
| Basic adaptive accumulation | 2 days | HIGH | LogicalTurnWorkflow |

**Milestone**: Messages accumulate into beats, process sequentially per session.

### Phase 1: Foundation Config (Week 3)

| Task | Effort | Priority | Dependency |
|------|--------|----------|------------|
| TurnRecord extensions | 1 day | HIGH | LogicalTurn model |
| Idempotency at beat level | 2 days | HIGH | LogicalTurn |
| AgentConfig integration | 2-3 days | HIGH | None |

**Milestone**: Config per agent, idempotency per beat, audit trail with beat_id.

### Phase 2: Side-Effects & Interruption (Week 4)

| Task | Effort | Priority | Dependency |
|------|--------|----------|------------|
| `SideEffectPolicy` enum + tool declarations | 1 day | CRITICAL | None |
| Supersede-aware brain execution | 2 days | CRITICAL | LogicalTurnWorkflow |
| Checkpoint reuse logic | 2 days | HIGH | PhaseArtifact |

**Milestone**: New message before commit = supersede old turn, reuse artifacts.

### Phase 3: Channel Intelligence (Week 5)

| Task | Effort | Priority | Dependency |
|------|--------|----------|------------|
| `ChannelCapability` model | 1 day | MEDIUM | None |
| Channel-aware accumulation | 2 days | MEDIUM | LogicalTurnWorkflow |
| Abuse detection (background) | 1-2 days | MEDIUM | LogicalTurn |

**Milestone**: WhatsApp batching vs SMS fragments handled correctly.

### Phase 4: Proactive (Weeks 6-7)

| Task | Effort | Priority | Dependency |
|------|--------|----------|------------|
| Agenda & Goals models | 1-2 days | HIGH | LogicalTurn |
| Follow-up Hatchet workflow | 2-3 days | HIGH | Goals |
| Outbound message trigger | 1-2 days | HIGH | Follow-up workflow |

**Milestone**: Agent proactively follows up on unresolved beats.

### Deferred

| Feature | Reason | Revisit When |
|---------|--------|--------------|
| ScenarioConfig | Still premature | When AgentConfig proves insufficient |
| Hot Reload | Complex, cleaner now but not urgent | When deployments become painful |
| Reporter | Dashboards sufficient | When tenants ask for NL analytics |
| ASA Runtime Agent | Still dangerous | Never (use design-time validator instead) |

---

## Data Model Reservations (Implement Now)

Even if full features are built later, reserve these fields now:

```python
# In TurnRecord
class TurnRecord(BaseModel):
    turn_id: UUID
    beat_id: UUID | None = None  # Reserved
    message_sequence: list[UUID] = []  # Reserved
    superseded_by: UUID | None = None  # Reserved
    interruptions: list[dict] = []  # Reserved
    phase_artifact_summaries: dict[int, dict] = {}  # Reserved

# In Session
class Session(BaseModel):
    # ... existing fields ...
    pending_scenario_transition: ScenarioStepRef | None = None  # Staged, not committed
    config_version: str | None = None  # For future hot reload

# In Tool definition (wherever tools are defined)
class ToolDefinition(BaseModel):
    # ... existing fields ...
    side_effect_policy: SideEffectPolicy = SideEffectPolicy.PURE
    confirmation_required: bool = False
```

**Cost**: ~30 minutes
**Benefit**: Avoids painful migrations later

---

## Summary: What Changed

| Original Wave | Original Verdict | New Verdict | Key Change |
|---------------|------------------|-------------|------------|
| Wave 1 | PROCEED | PROCEED (after Wave 0) | Idempotency now at beat level |
| Wave 2 | MODIFY | ABSORBED + SIMPLIFIED | Debouncing → Wave 0, only abuse detection remains |
| Wave 3 | DEFER | REPURPOSED | ChannelCapability → accumulation hints |
| Wave 4 | DEPRIORITIZE | ELEVATED | SideEffectPolicy is required for superseding |
| Wave 5 | SPLIT | ENHANCED | Goals scoped to beats, cleaner |
| Wave 6 | SKIP | CLARIFIED | ASA = design-time validator, not runtime agent |
| **NEW: Wave 0** | N/A | FOUNDATIONAL | Turn Gateway, LogicalTurn, Hatchet orchestration |

### Total Effort Comparison

| Approach | Estimated Effort |
|----------|------------------|
| Original Waves (all features) | 24-42 days |
| Revised Waves (LogicalTurn foundation + selective features) | 18-28 days |

**The LogicalTurn architecture is NOT more expensive.** It's a better foundation that makes later features cleaner.

---

## Decision Required

Before proceeding, the following architectural decisions need confirmation:

1. **Commit to LogicalTurn as foundation?** (All subsequent work depends on this)
2. **SideEffectPolicy declaration mandatory for all tools?**
3. **ASA as design-time validator only, not runtime agent?**
4. **Reserve data model fields now?**

---

*Analysis generated: 2025-12-10*
*Supersedes: wave_analysis_report.md for architectural direction*
*wave_analysis_report.md remains valid for individual feature analysis*
