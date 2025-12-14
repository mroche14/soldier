# Agent Conversation Fabric (ACF) Specification

> **Status**: AUTHORITATIVE IMPLEMENTATION SPEC
> **Version**: 3.0
> **Date**: 2025-12-11
> **Builds on**: [LOGICAL_TURN_VISION.md](LOGICAL_TURN_VISION.md) (founding vision)
> **Architecture**: See [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md) for the canonical architecture
> **Related**: [AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md), [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)

---

## Executive Summary

**Agent Conversation Fabric (ACF)** is **pure conversation infrastructure** that governs *when* an agent responds, while the **Agent** (Pipeline + Toolbox) governs *what* it says and does.

ACF is a **thin waist** between channels and Agents:

1. **Human-like turn behavior** (multi-message bursts become one logical turn)
2. **Concurrency correctness** (no parallel runs per session key)
3. **Supersede signals** (tells Pipeline new messages arrived; Pipeline decides action)
4. **Workflow orchestration** (Hatchet-backed durable execution)
5. **FabricEvent routing** (receives events from Pipeline/Toolbox, routes to listeners)

**Critical Boundary**:
- **ACF owns infrastructure**: Mutex, turns, workflow steps, event routing
- **Agent owns business logic**: Tool execution, side effect semantics, decisions
- **Toolbox owns tool execution**: See [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)

ACF does NOT own tool authorization, tool execution, or side effect tracking. Those are Agent-level concerns handled by Toolbox.

---

## Design Principles

### 1. ACF is Pure Infrastructure

ACF knows about turns, mutexes, and workflow orchestration. It does NOT know about:
- Tools or side effect semantics (Toolbox owns this)
- Scenarios or rules (Pipeline owns this)
- Channel UX (ChannelAdapters own this)

### 2. Facts vs Decisions

| ACF Provides (Facts) | Agent/Pipeline Provides (Decisions) |
|----------------------|-------------------------------------|
| Session mutex | When to release |
| Turn aggregation | Aggregation hints |
| `has_pending_messages()` signal | SUPERSEDE/ABSORB/QUEUE/FORCE_COMPLETE decision |
| Workflow step boundaries | What to do in each step |
| FabricEvent routing | What events to emit |

### 3. Toolbox Owns Tool Execution

**CRITICAL CHANGE from v2.0**: ACF no longer provides tool callbacks.

| Old (v2.0) | New (v3.0) |
|------------|------------|
| `ctx.callbacks.authorize_tool()` | `ctx.toolbox.execute()` |
| `ctx.callbacks.execute_tool()` | `ctx.toolbox.execute()` |
| `ctx.callbacks.record_side_effect()` | Toolbox emits FabricEvent |
| ACF owns SideEffectLedger | ACF stores events in LogicalTurn |

See [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) for the new tool execution model.

### 4. Explicit Orchestration Mode Selection

Mode selection MUST be explicit via configuration, not implicit protocol detection.

### 5. Agent as Primary Abstraction

The **Agent** (AgentContext) is the primary business abstraction, containing:
- Pipeline (brain)
- Toolbox (tools)
- ChannelBindings (channels)

See [AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md) for details.

---

## Execution Model

ACF uses a **single execution style**: Pipeline calls `toolbox.execute()` inline during turn processing.

### Workflow Steps

```
acquire_mutex → accumulate → run_pipeline → commit_and_respond
```

**Inside run_pipeline**:
- Pipeline runs all phases continuously
- Tools execute via `ctx.toolbox.execute()` during P7
- Pipeline checks `ctx.has_pending_messages()` before irreversible tools
- Toolbox handles policy enforcement, idempotency, and audit events
- Response generated in same pipeline invocation

### Why Single Execution Style

Previous designs included Mode 0/1/2 for different trust levels. This complexity is **not needed** because:

1. **Your team controls all pipelines** - No untrusted third-party brains
2. **Toolbox is the enforcement boundary** - Policy, idempotency, confirmation handled there
3. **ASA validates scenarios** - Design-time checks ensure conformance

### FabricTurnContext

What ACF provides to the Pipeline:

```python
class FabricTurnContext(Protocol):
    """ACF's interface to Agent - infrastructure only."""

    logical_turn: LogicalTurn
    session_key: str
    channel: str

    async def has_pending_messages(self) -> bool:
        """Query: Did any new message arrive during this turn?"""
        ...

    async def emit_event(self, event: FabricEvent) -> None:
        """Emit event for ACF to route/store."""
        ...
```

### Pipeline Tool Execution Pattern

```python
# Pipeline executes tools via Toolbox
async def run(self, ctx: AgentTurnContext) -> PipelineResult:
    # ... P1-P6 ...

    # P7: Tool execution via Toolbox
    for planned_tool in planned_tools:
        # Check supersede before irreversible (ACF signal)
        if metadata.is_irreversible and await ctx.has_pending_messages():
            return self._handle_supersede()

        # Execute via Toolbox (handles policy, idempotency, audit)
        result = await ctx.toolbox.execute(planned_tool, ctx)

    # ... P8-P11 ...
```

See [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) for the complete Toolbox interface.

### Pipeline Conformance Requirements

All pipelines must satisfy these invariants:

| Invariant | Description | Enforcement |
|-----------|-------------|-------------|
| **Tool calls through Toolbox** | Never call vendor SDK directly | ASA lints, code review |
| **Confirmation binding** | If `requires_confirmation`, enter confirm step | Scenario state |
| **Idempotency keys** | Side-effect tools have stable business key | Toolbox extracts/hashes |
| **Supersede awareness** | Check `has_pending_messages()` before irreversible | Pipeline responsibility |

### Framework Compatibility

**ACF as "Conversation Envelope"**: ACF doesn't replace LangGraph, Agno, or custom brains—it wraps them as the conversation envelope.

**LangGraph Integration**:
```python
class LangGraphPipeline(CognitivePipeline):
    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        # Inject Toolbox into LangGraph's tool layer
        state = {"messages": ctx.logical_turn.raw_messages}
        state["tool_executor"] = LangGraphToolAdapter(ctx.toolbox)
        final_state = await self.graph.ainvoke(state)
        return self._to_pipeline_result(final_state)
```

**Agno Integration**:
```python
class AgnoPipeline(CognitivePipeline):
    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        workflow_result = await self._agno_workflow.execute(
            messages=ctx.logical_turn.raw_messages,
            tool_executor=AgnoToolAdapter(ctx.toolbox),
        )
        return self._to_pipeline_result(workflow_result)
```

---

## ACF Freedom vs Constraints (Philosophy)

**Key insight**: ACF is a "thin waist" that makes it *easier* to build complex pipelines, not harder. It constrains only what needs to be safe; everything else is your playground.

### The Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: CHANNELS / INGRESS                                │
│  WhatsApp, webchat, email, voice...                         │
│  Beat/LogicalTurn aggregation, session mutex, throttling    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: AGENT CONVERSATION FABRIC (ACF) ← THIN WAIST      │
│  One responsibility: turn lifecycle + safety                │
│  - Session mutex (no parallel turns per session)            │
│  - LogicalTurn aggregation & supersede                      │
│  - Orchestration mode (simple / single-pass / two-pass)     │
│  - FabricEvent routing (receives from Toolbox, stores)      │
│  - Commit point tracking                                    │
│  - Audit events                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: COGNITIVE PIPELINE (your playground)              │
│  FOCAL, LangGraph, Agno, custom...                          │
│  - Phases (11, 15, 20 - as many as you want)                │
│  - Mission planning                                         │
│  - Multi-step retries, LLM-driven loops                     │
│  - Scenario + rule engine                                   │
│  - Agenda integration, goals                                │
│  - Self-evaluation, self-correction                         │
│  - Confirmation-of-success steps                            │
└─────────────────────────────────────────────────────────────┘
```

### What You CAN Do (Freedom)

| Capability | Example | ACF Impact |
|------------|---------|------------|
| **More pipeline phases** | Go from 11 to 15 to 20 phases | ACF only sees `PipelineResult` at the end |
| **Mission planner phase** | P-NEW: Plan multi-step mission | Internal to pipeline |
| **LLM retry loops** | "Try mission up to X times until success" | Just more tool calls via Toolbox |
| **Success confirmation phase** | P10: `MissionStatusEvaluator` | Internal to pipeline |
| **Self-correction phases** | LLM evaluates and retries | Internal to pipeline |
| **Complex LangGraph graphs** | Loops, subgraphs, conditional branches | Wrap as `CognitivePipeline.run()` |
| **Agno workflows** | Any Agno agent complexity | Wrap as `CognitivePipeline.run()` |

**CSS analogy**: ACF cares about *where the outer box sits*, not about how many `<div>`s you put inside.

### What You CANNOT Do (Constraints)

These constraints exist because they would be **dangerous without them**:

#### 1. Side-Effects Must Go Through Toolbox

```python
# ❌ BAD - bypasses Toolbox
await refund_tool_direct(order_id="123")

# ✅ GOOD - goes through Toolbox (v3.0)
planned = PlannedToolExecution(tool_name="refund_order", args={"order_id": "123"})
result = await ctx.toolbox.execute(planned, ctx)
# Toolbox handles: authorization, execution, side-effect recording, event emission
```

**Why**: Consistent logging, idempotency, reversible/irreversible semantics, supersede safety.

#### 2. Long Loops Must Be Interrupt-Aware

If your pipeline runs a long mission loop, it must periodically check `has_pending_messages()` so it can make supersede decisions.

```python
# Before irreversible action
if tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
    if await ctx.has_pending_messages():
        # Pipeline decides: SUPERSEDE, ABSORB, QUEUE, or FORCE_COMPLETE
        return self._handle_supersede()
```

**Why**: Human-like behavior - if user says something new mid-action, you should be able to respond.

#### 3. Agree to Pipeline Contract

The pipeline contract is simple:

```python
async def run(ctx: AgentTurnContext) -> PipelineResult
```

With tools via `ctx.toolbox.execute()`. Inside that, you're free. Don't try to bypass commit model or invent parallel "partial commit" semantics.

### Concrete Example: Mission with Retries

**Goal**: "Mission with up to 3 tool-based retries + success confirmation by LLM"

```python
async def run(self, ctx: AgentTurnContext) -> PipelineResult:
    # P1-P6: Context, intent, rules...
    mission = await self._plan_mission(ctx)

    # Mission loop with retries
    max_attempts = 3
    for attempt in range(max_attempts):
        # Check for interrupts before each attempt
        if await ctx.has_pending_messages():
            decision = self._decide_supersede(ctx, mission)
            if decision.action != SupersedeAction.FORCE_COMPLETE:
                return PipelineResult(interrupted=True, last_phase="mission_loop")

        # Execute tools via Toolbox
        for planned_tool in mission.planned_tools:
            result = await ctx.toolbox.execute(planned_tool, ctx)
            # Toolbox handles: policy, idempotency, audit events

        # P10: Success confirmation by LLM
        success = await self._evaluate_mission_success(ctx, mission)
        if success.achieved:
            break
        elif attempt < max_attempts - 1:
            mission = await self._replan_mission(ctx, success.failure_reason)

    # P11: Generate response
    return PipelineResult(
        response_segments=[...],
        staged_mutations={...},
        accumulation_hint=AccumulationHint(expects_followup=not success.achieved),
    )
```

**From ACF's perspective**: This is just a longer turn with several tool calls. Side-effect safety holds because every tool call passes through Toolbox.

### Framework Compatibility Patterns

#### LangGraph Integration

```python
class LangGraphPipeline(CognitivePipeline):
    name = "langgraph"

    def __init__(self, graph):
        self.graph = graph

    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        # Inject Toolbox into LangGraph's tool layer
        state = {
            "messages": ctx.logical_turn.raw_messages,
            "tool_executor": LangGraphToolAdapter(ctx.toolbox),
        }
        final_state = await self.graph.ainvoke(state)
        return self._to_pipeline_result(final_state)
```

The graph can be arbitrarily complex (loops, retries, subgraphs). ACF only sees a single `run()` call. Toolbox handles tool execution correctness.

#### Agno Workflow Integration

```python
class AgnoPipeline(CognitivePipeline):
    name = "agno"

    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        # Agno workflow with Toolbox adapter
        workflow_result = await self._agno_workflow.execute(
            messages=ctx.logical_turn.raw_messages,
            tool_executor=AgnoToolAdapter(ctx.toolbox),
        )
        return self._to_pipeline_result(workflow_result)
```

### Summary: ACF's True Constraints

The **only** things ACF "forbids" are things that would **already be dangerous**:

| Forbidden | Why Dangerous |
|-----------|---------------|
| Side-effects outside ACF's knowledge | No logging, no idempotency, no audit |
| Ignoring new messages mid-critical action | Bad UX, user feels unheard |
| Parallel pipelines mutating same session | Race conditions, data corruption |
| Tools with irreversible effects retried blindly | Double refunds, duplicate orders |

Everything else — number of phases, mission loops, multi-step planning, agent self-evaluation, ASA-based auto-configuration — is **inside** your CognitivePipeline and **fully compatible** with ACF.

---

## Execution Model Design Rationale

This section documents the strategic thinking behind the single execution style.

### Why Single Execution Style

Previous designs included Mode 0/1/2 for different trust levels. After analysis, this complexity was **removed** because:

1. **Your team controls all pipelines** - No untrusted third-party brains requiring platform enforcement
2. **Toolbox is the enforcement boundary** - Policy, idempotency, confirmation already handled there
3. **ASA validates scenarios at design time** - Conformance checked before deployment

### What We Avoided

By using a single execution style, we avoid:

| Avoided Complexity | Why Not Needed |
|-------------------|----------------|
| Multiple workflow patterns | One workflow handles all cases |
| Mode configuration per agent | No config needed - all pipelines same |
| Mode-specific observability | One event model, one dashboard |
| Plan/Finalize protocols | Pipeline handles everything in `run()` |
| State serialization between steps | LLM context stays warm |

### What We Kept

Despite simplification, we maintain all safety guarantees:

| Guarantee | How Maintained |
|-----------|----------------|
| No bypass of policy | Toolbox enforces on every `execute()` |
| Audit trail | Toolbox emits FabricEvents |
| Idempotency | ToolGateway handles via turn_group_id |
| Supersede safety | Pipeline checks `has_pending_messages()` |
| Confirmation binding | Scenario state + Toolbox validation |

### What This Design Does NOT Block

The single execution style does **not** prevent:

| Future Capability | Why Still Possible |
|-------------------|-------------------|
| More pipeline phases | Internal to `run()` |
| Mission planning | Internal to pipeline |
| Self-correction loops | Internal to pipeline |
| Complex LangGraph graphs | Wrap as `run()` |
| Agno workflows | Wrap as `run()` |
| ASA validation | Works on any pipeline |

**Key principle**: Toolbox as enforcement boundary means we get safety without orchestration complexity.

---

## Scope Definition

### ACF Owns (Conversation Mechanics)

- Raw message normalization
- Session mutex (one in-flight logical turn per session key)
- Logical turn aggregation
- Supersede orchestration (not semantic intent classification)
- Commit gating for tool side effects
- Channel capability registry + policy resolution
- Audit envelope + event stream
- Scheduling primitives (infrastructure-only, Hatchet-backed)

### CognitivePipeline Owns (Meaning & Domain Semantics)

- Scenarios and rules logic
- Scenario transition semantics
- Domain memory logic
- Agenda/goals reasoning
- Tool intent planning
- Response plan strategy
- "Given what I asked, user can't be done yet" reasoning
- Supersede decision logic (when domain understanding required)

### Separate Components (Clients of ACF)

- **ASA (Agent Setter Agent)**: Config and design intelligence using admin APIs + simulation
- **Reporter**: Reads audit/outcomes and narrates tenant activity

### Explicitly NOT in ACF

- Scenario engine
- Rule engine
- Agenda logic
- ASA/Reporter logic
- Business truth evaluation

---

## Core Types

### RawMessage

A single inbound event from a channel.

```python
class RawMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str
    channel: str
    channel_user_id: str
    tenant_id: UUID
    agent_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)
```

### SessionKey

The concurrency boundary: `(tenant_id, agent_id, customer_id, channel_identity)`

```python
def compute_session_key(
    tenant_id: UUID,
    agent_id: UUID,
    customer_id: UUID,
    channel: str,
) -> str:
    return f"{tenant_id}:{agent_id}:{customer_id}:{channel}"
```

### LogicalTurn

ACF's atomic unit of processing. May contain multiple raw messages.

```python
class LogicalTurnStatus(str, Enum):
    ACCUMULATING = "accumulating"
    PROCESSING = "processing"
    COMMITTING = "committing"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"

class LogicalTurn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_key: str
    raw_messages: list[RawMessage] = Field(default_factory=list)
    status: LogicalTurnStatus = LogicalTurnStatus.ACCUMULATING

    # Turn grouping for idempotency scoping
    turn_group_id: UUID = Field(default_factory=uuid4)
    """
    Groups turns in a supersede chain. Same turn_group_id = same conversation attempt.

    - Turns in supersede chain (A→B→C) share same turn_group_id (inherited from A)
    - QUEUE decision creates NEW turn_group_id (different conversation attempt)
    - Used in tool idempotency keys: "{tool}:{business_key}:turn_group:{turn_group_id}"
    """

    first_at: datetime
    last_at: datetime
    aggregation_window_ms: int
    aggregation_reason: str | None = None  # timeout | adaptive | channel_bundle | pipeline_hint

    # Artifact tracking
    artifacts: dict[str, "Artifact"] = Field(default_factory=dict)

    # Side effect tracking
    side_effects_executed: list["SideEffectRecord"] = Field(default_factory=list)
    commit_point_reached: bool = False
```

### Commit Points

Moments after which ACF will not silently override or restart prior work.

Determined by:
1. `ToolSideEffectPolicy` of executed tools
2. Pipeline-exposed safe checkpoints
3. Scenario checkpoint semantics

---

## Channel Model

### ChannelCapabilities (Facts - ACF Owns)

Immutable facts about what a channel can do.

```python
class ChannelCapabilities(BaseModel):
    """Facts about channel capabilities. Read-only."""

    channel: str
    supports_typing_indicator: bool = False
    supports_delivery_receipts: bool = False
    supports_read_receipts: bool = False
    max_message_length: int | None = None
    supports_rich_media: bool = False
    supports_outbound: bool = True
```

### ChannelPolicy (Behavior - Configurable)

Behavioral choices that can be configured per tenant/agent/channel.

```python
class AggregationMode(str, Enum):
    OFF = "off"              # No aggregation, immediate processing
    FIXED = "fixed"          # Fixed window
    ADAPTIVE = "adaptive"    # Adaptive based on signals

class ChannelPolicy(BaseModel):
    """Configurable behavior for a channel."""

    channel: str
    aggregation_mode: AggregationMode = AggregationMode.ADAPTIVE
    default_window_ms: int = 800
    min_window_ms: int = 200
    max_window_ms: int = 3000
    fallback_channels: list[str] = Field(default_factory=list)
    retry_on_delivery_failure: bool = True
```

### Default Profiles

```python
CHANNEL_CAPABILITIES: dict[str, ChannelCapabilities] = {
    "whatsapp": ChannelCapabilities(
        channel="whatsapp",
        supports_typing_indicator=True,
        supports_delivery_receipts=True,
        supports_read_receipts=True,
        max_message_length=4096,
        supports_rich_media=True,
    ),
    "sms": ChannelCapabilities(
        channel="sms",
        max_message_length=160,
    ),
    "email": ChannelCapabilities(
        channel="email",
        max_message_length=None,  # Unlimited
        supports_rich_media=True,
    ),
    "web": ChannelCapabilities(
        channel="web",
        supports_typing_indicator=True,
        max_message_length=10000,
        supports_rich_media=True,
    ),
}

DEFAULT_CHANNEL_POLICIES: dict[str, ChannelPolicy] = {
    "whatsapp": ChannelPolicy(channel="whatsapp", default_window_ms=1200),
    "sms": ChannelPolicy(channel="sms", default_window_ms=800),
    "email": ChannelPolicy(channel="email", aggregation_mode=AggregationMode.OFF),
    "web": ChannelPolicy(channel="web", default_window_ms=600),
}
```

### Policy Resolution Order

1. Platform defaults
2. Tenant overrides
3. Agent overrides
4. Channel overrides
5. (Optional) Pipeline runtime override

---

## Session Mutex

**Invariant**: Only one active logical turn per SessionKey at a time.

```python
class SessionMutex(ABC):
    """Ensures single-writer semantics per session."""

    @abstractmethod
    async def acquire(
        self,
        session_key: str,
        ttl_ms: int = 30000,
        blocking_timeout_ms: int = 5000,
    ) -> bool:
        """Acquire lock. Returns True if acquired, False if timeout."""
        ...

    @abstractmethod
    async def release(self, session_key: str) -> None:
        """Release lock."""
        ...

    @abstractmethod
    async def extend(self, session_key: str, ttl_ms: int) -> bool:
        """Extend lock TTL. Returns True if extended."""
        ...
```

### Why This is Foundational

Prevents:
- Scenario state corruption
- Conflicting memory writes
- Double tool execution
- Audit ambiguity
- Race conditions in scenario advancement

---

## Supersede Semantics

### SupersedeDecision

When a new message arrives during processing, ACF needs to decide what to do.

```python
class SupersedeDecision(str, Enum):
    SUPERSEDE = "supersede"       # Cancel current, start new with all messages
    ABSORB = "absorb"             # Add message to current turn, may restart
    QUEUE = "queue"               # Finish current, then process new
    FORCE_COMPLETE = "force_complete"  # Almost done, just finish current
```

### When Each Applies

| Decision | When | Example |
|----------|------|---------|
| SUPERSEDE | New message changes intent | "Book Paris" → "I meant London" |
| ABSORB | New message completes intent | "Refund my order" → "Order #12345" |
| QUEUE | After commit point reached | New message after refund executed |
| FORCE_COMPLETE | 95% done, restart cost > benefit | Minor clarification near end |

### Absorb Strategies

When decision is ABSORB, the strategy determines how to handle existing work:

```python
class AbsorbStrategy(str, Enum):
    RESTART_WITH_MERGED = "restart"   # Discard work, start over with all messages
    CONTINUE_WITH_APPENDED = "continue"  # Keep work, add message to context
```

**SupersedeDecision is a model, not just an enum**:

```python
class SupersedeAction(str, Enum):
    """The action to take."""
    SUPERSEDE = "supersede"
    ABSORB = "absorb"
    QUEUE = "queue"
    FORCE_COMPLETE = "force_complete"

class SupersedeDecision(BaseModel):
    """
    Full decision from pipeline (or ACF default).

    Includes action AND strategy for ABSORB case.
    """
    action: SupersedeAction
    absorb_strategy: AbsorbStrategy | None = None  # Only if action=ABSORB
    reason: str | None = None
```

**Artifact reuse is ORTHOGONAL to absorb strategy** - both RESTART and CONTINUE can reuse artifacts if fingerprints match. The strategy determines what work to keep, artifact reuse determines what to re-validate.

### Default Behavior

If pipeline doesn't implement `SupersedeCapable`, ACF defaults conservatively:

```python
def default_supersede_decision(
    current: LogicalTurn,
    new: RawMessage,
) -> SupersedeDecision:
    """Conservative default: queue after commit point, otherwise supersede."""
    if current.commit_point_reached:
        return SupersedeDecision(action=SupersedeAction.QUEUE, reason="commit_point_reached")
    if current.side_effects_executed:
        return SupersedeDecision(action=SupersedeAction.QUEUE, reason="side_effects_executed")
    # Default: supersede and restart
    return SupersedeDecision(action=SupersedeAction.SUPERSEDE)
```

---

## Tool Side Effects

> **IMPORTANT**: Tool execution and side effect semantics are now owned by **Toolbox**, not ACF.
> See [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) for the authoritative specification.
>
> This section describes ACF's role: **storing side effects received via FabricEvents**.

### Ownership Change (v3.0)

| Component | v2.0 Ownership | v3.0 Ownership |
|-----------|----------------|----------------|
| `ToolSideEffectPolicy` | ACF | Toolbox |
| `PlannedToolExecution` | ACF | Pipeline/Toolbox |
| `SideEffectRecord` | ACF | Toolbox creates, ACF stores |
| Tool authorization | ACF (callbacks) | Toolbox (metadata checks) |
| Tool execution | ACF (via ToolHub) | Toolbox (via ToolGateway) |

### ACF's Role: Event Storage

ACF receives `TOOL_SIDE_EFFECT_*` events from Toolbox and stores them in `LogicalTurn.side_effects`:

```python
# Toolbox emits event after tool execution
await turn_context.emit_event(FabricEvent(
    type=FabricEventType.TOOL_SIDE_EFFECT_COMPLETED,
    payload=side_effect_record.model_dump(),
))

# ACF EventRouter listens and stores
async def handle_side_effect_event(event: FabricEvent) -> None:
    if event.type == FabricEventType.TOOL_SIDE_EFFECT_COMPLETED:
        await turn_manager.add_side_effect(
            turn_id=event.turn_id,
            record=SideEffectRecord(**event.payload),
        )
```

### Side Effect Storage in LogicalTurn

```python
class LogicalTurn(BaseModel):
    # ... other fields ...
    side_effects: list[SideEffectRecord] = Field(default_factory=list)
```

This enables:
- Audit trail of all side effects
- Supersede decisions to consider executed effects
- Compensation tracking

### What Moved to Toolbox

The following are now in [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md):

- `SideEffectPolicy` enum (PURE, IDEMPOTENT, COMPENSATABLE, IRREVERSIBLE)
- `ToolDefinition` with policy metadata
- `SideEffectRecord` creation
- Tool authorization logic
- Tool execution via ToolGateway

---

## Three-Layer Idempotency Architecture

Idempotency in ACF operates at **three separate layers**, not one unified system.

### Layer Overview

| Layer | Location | Key Format | TTL | Protects |
|-------|----------|------------|-----|----------|
| **API** | Before workflow | `{tenant}:{client_idem_key}` | 5min | Duplicate HTTP requests |
| **Beat** | After accumulation | `{tenant}:beat:{session}:{msg_hash}` | 60s | Duplicate turn processing |
| **Tool** | During P7 tool execution | `{tool}:{business_key}:turn_group:{turn_group_id}` | 24hrs | Duplicate business actions |

### API Layer Idempotency

Prevents duplicate HTTP requests from creating duplicate workflows.

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    if request.idempotency_key:
        cached = await idem_cache.get(f"{request.tenant_id}:{request.idempotency_key}")
        if cached:
            return cached  # Return cached response

    # Process request...
    # Cache response with 5min TTL
```

### Beat Layer Idempotency

Prevents the same logical turn from being processed twice.

```python
beat_key = f"{tenant_id}:beat:{session_key}:{hash(sorted_message_ids)}"
if await beat_cache.exists(beat_key):
    return "already_processing"
await beat_cache.set(beat_key, turn.id, ttl=60)
```

### Tool Layer Idempotency

> **Note**: Tool idempotency is owned by **ToolGateway** (infrastructure).
> See [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) for the complete specification.

**ACF's contribution**: Provides `turn_group_id` in `LogicalTurn`, which Toolbox uses via `ToolExecutionContext` to build idempotency keys.

```python
# Toolbox builds ToolExecutionContext with ACF's turn_group_id
exec_ctx = ToolExecutionContext(
    turn_group_id=turn_context.logical_turn.turn_group_id,  # From ACF
    tool_name=tool.tool_name,
    args=tool.args,
    # ...
)

# ToolGateway uses turn_group_id for idempotency key
def build_idempotency_key(self, business_key: str) -> str:
    """Includes turn_group_id to scope idempotency to conversation attempt."""
    return f"{self.tool_name}:{business_key}:turn_group:{self.turn_group_id}"
```

This ensures:
- Same user + same order + same conversation = one refund
- Different conversation about same order = allowed (new turn_group_id)

### Fingerprints (Orthogonal to Idempotency)

Fingerprints optimize computation, not prevent duplicate effects:

| Concept | Purpose | Protects |
|---------|---------|----------|
| `input_fp` | Hash of turn inputs | Wasted re-parsing |
| `dep_fp` | Hash of version dependencies | Semantic mismatch |
| `reuse_decl` | Pipeline's reuse policy | Inappropriate reuse |
| **Idempotency** | Prevent duplicate actions | Real-world duplicate effects |

**Both are needed** - fingerprints avoid computation, idempotency prevents duplicate effects.

---

## Artifact Reuse (Don't Redo Everything)

### Ownership Model

- **Pipeline declares** reuse semantics (what's safe to reuse)
- **ACF enforces** fingerprint matching and version compatibility

### Artifact Model

```python
class ReusePolicy(str, Enum):
    ALWAYS_SAFE = "always_safe"      # Can reuse if fingerprint matches
    CONDITIONAL = "conditional"       # Reuse if fingerprint + versions match
    NEVER = "never"                   # Never reuse

class Artifact(BaseModel):
    name: str
    data: dict
    input_fingerprint: str           # Hash of inputs that produced this
    dependency_fingerprint: str      # Hash of versions (rules, scenarios, etc.)
    reuse_policy: ReusePolicy
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Version Dependencies

ACF must track and validate these versions for artifact reuse:

- Scenario version
- Rule set version
- KB/knowledge version
- Agent config version
- Tool registry version

```python
class VersionSnapshot(BaseModel):
    scenario_version: str | None
    rules_version: str | None
    kb_version: str | None
    config_version: str | None
    tools_version: str | None

    def fingerprint(self) -> str:
        return hashlib.sha256(
            self.model_dump_json().encode()
        ).hexdigest()[:16]
```

### Reuse Validation

```python
def can_reuse_artifact(
    artifact: Artifact,
    new_input_fp: str,
    current_versions: VersionSnapshot,
) -> bool:
    if artifact.reuse_policy == ReusePolicy.NEVER:
        return False

    if artifact.input_fingerprint != new_input_fp:
        return False

    if artifact.reuse_policy == ReusePolicy.CONDITIONAL:
        if artifact.dependency_fingerprint != current_versions.fingerprint():
            return False

    return True
```

---

## CognitivePipeline Interface

### Minimal Core Protocol

```python
class CognitivePipeline(Protocol):
    """Minimal interface every brain must implement."""

    name: str

    async def run(self, ctx: "FabricTurnContext") -> "PipelineResult":
        """Process a logical turn and return results."""
        ...
```

### Optional Capability Mixins

```python
class SupersedeCapable(Protocol):
    """Brain can make intelligent supersede decisions."""

    async def decide_supersede(
        self,
        current: LogicalTurn,
        new: RawMessage,
        interrupt_point: str,  # "pre_processing" | "phase_boundary" | "pre_commit"
    ) -> SupersedeDecision:
        ...

class ArtifactReuseCapable(Protocol):
    """Brain declares what artifacts can be reused."""

    def declare_reuse_policies(self) -> dict[str, ReusePolicy]:
        """Return mapping of artifact_name -> ReusePolicy."""
        ...

class ChannelPolicyOverrideCapable(Protocol):
    """Brain can override channel policies at runtime."""

    def override_channel_policy(
        self,
        base_policy: ChannelPolicy,
        context: "FabricTurnContext",
    ) -> ChannelPolicy:
        ...

class AggregationHintCapable(Protocol):
    """Brain can hint that user isn't done yet."""

    async def should_extend_aggregation(
        self,
        current_messages: list[RawMessage],
        context: "FabricTurnContext",
    ) -> bool:
        """Return True if agent expects more user input."""
        ...
```

### FabricTurnContext

> **Canonical Definition**: See [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md) for the authoritative Protocol definition.

What ACF provides to the pipeline - a **minimal protocol**, not a data object:

```python
class FabricTurnContext(Protocol):
    """ACF's interface to Agent - infrastructure only."""

    logical_turn: LogicalTurn
    session_key: str
    channel: str

    async def has_pending_messages(self) -> bool:
        """Query: Did any new message arrive during this turn?"""
        ...

    async def emit_event(self, event: FabricEvent) -> None:
        """Emit a FabricEvent for routing/persistence."""
        ...
```

**Note**: Channel capabilities, config, versions, and artifacts are NOT part of FabricTurnContext. These are injected via `AgentContext` by `AgentRuntime`, maintaining the thin-waist boundary between ACF and Agent.

### PipelineResult

What the pipeline returns to ACF.

```python
class PipelineResult(BaseModel):
    # Response to send
    response_segments: list[dict]

    # Tool results from inline execution via Toolbox
    tool_results: list[ToolResult] = Field(default_factory=list)

    # State mutations to commit atomically
    staged_mutations: dict = Field(default_factory=dict)

    # Artifacts for potential reuse
    artifacts: list[Artifact] = Field(default_factory=list)

    # Trace data
    pipeline_trace: dict | None = None

    # Signals
    commit_point_reached: bool = False
    expects_more_input: bool = False
```

---

## Error Handling

### FabricErrorPolicy

```python
class ErrorAction(str, Enum):
    RETRY = "retry"
    FAIL = "fail"
    ESCALATE = "escalate"

class EscalationTarget(str, Enum):
    TENANT_WEBHOOK = "tenant_webhook"
    INTERNAL_ALERT = "internal_alert"
    USER_ERROR_MESSAGE = "user_error"
    SILENT_LOG = "silent_log"

class FabricErrorPolicy(BaseModel):
    on_pipeline_error: ErrorAction = ErrorAction.FAIL
    on_tool_error: ErrorAction = ErrorAction.ESCALATE
    on_tool_timeout: ErrorAction = ErrorAction.RETRY
    on_mutex_timeout: ErrorAction = ErrorAction.FAIL
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    escalation_target: EscalationTarget = EscalationTarget.SILENT_LOG
```

### Failure Scenarios

| Scenario | Default Action | Notes |
|----------|---------------|-------|
| Pipeline throws exception | FAIL | Return error to user |
| Tool execution fails | ESCALATE | May need human review |
| Tool timeout | RETRY | Respect idempotency |
| Mutex acquisition timeout | FAIL | Another turn is processing |
| Response delivery fails | Record + ESCALATE | Side effect may have committed |

---

## Observability

### FabricEvent

> **Canonical Definition**: Use `type` (not `event_type`) as the field name for consistency across all documents.

```python
class FabricEventType(str, Enum):
    # Turn lifecycle
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    TURN_SUPERSEDED = "turn_superseded"

    # Message handling
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_ABSORBED = "message_absorbed"
    AGGREGATION_COMPLETE = "aggregation_complete"

    # Pipeline
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"

    # Supersede
    SUPERSEDE_DECISION = "supersede_decision"

    # Tool side effects (emitted by Toolbox, routed by ACF)
    TOOL_SIDE_EFFECT_STARTED = "tool_side_effect_started"
    TOOL_SIDE_EFFECT_COMPLETED = "tool_side_effect_completed"
    TOOL_SIDE_EFFECT_FAILED = "tool_side_effect_failed"

    # Commit
    COMMIT_APPROVED = "commit_approved"

    # Errors
    ERROR_OCCURRED = "error_occurred"

class FabricEvent(BaseModel):
    """Canonical event envelope. All events use this structure."""

    type: FabricEventType  # NOT event_type
    tenant_id: UUID
    agent_id: UUID
    session_key: str
    logical_turn_id: UUID
    trace_id: str  # Required for end-to-end tracing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict = Field(default_factory=dict)
```

---

## Hatchet Integration

ACF is implemented as a **durable workflow** on Hatchet.

### Workflow Steps

```
acquire_mutex → accumulate → run_pipeline → commit_and_respond
```

| Step | Purpose |
|------|---------|
| `acquire_mutex` | Get session lock, prevent parallel turns |
| `accumulate` | Aggregate messages into LogicalTurn |
| `run_pipeline` | Pipeline processes turn, executes tools via Toolbox |
| `commit_and_respond` | Persist state, send response, release mutex |

### Critical: Mutex Lifecycle

**IMPORTANT**: The mutex MUST be held across all steps, not released after `acquire_mutex` returns.

```python
@hatchet.step()
async def acquire_mutex(self, ctx: Context) -> dict:
    """
    Acquire session mutex. Lock is held until commit_and_respond or on_failure.

    CRITICAL: Do NOT use context manager - lock must persist across steps.
    """
    session_key = ctx.workflow_input()["session_key"]

    # Acquire WITHOUT context manager - don't release on step exit
    lock = self._redis.lock(
        f"sesslock:{session_key}",
        timeout=300,  # 5min workflow max
    )
    acquired = await lock.acquire(blocking_timeout=10)

    if not acquired:
        raise MutexAcquisitionFailed(session_key)

    # Store lock reference for later release
    ctx.workflow_state["session_lock_key"] = f"sesslock:{session_key}"

    return {"mutex_acquired": True, "session_key": session_key}

@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    # ... commit work ...

    # Explicitly release mutex at end
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._force_release_lock(lock_key)

    return {"status": "complete"}

@hatchet.on_failure()
async def handle_failure(self, ctx: Context):
    """Always release lock on failure."""
    lock_key = ctx.workflow_state.get("session_lock_key")
    if lock_key:
        await self._force_release_lock(lock_key)
```

### Workflow Implementation

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    """ACF workflow - single execution style."""

    def __init__(self, agent_runtime: AgentRuntime):
        self._agent_runtime = agent_runtime

    @hatchet.step()
    async def acquire_mutex(self, ctx: Context) -> dict:
        """Acquire session mutex. Held until commit_and_respond."""
        session_key = ctx.workflow_input()["session_key"]
        lock = self._redis.lock(f"sesslock:{session_key}", timeout=300)
        acquired = await lock.acquire(blocking_timeout=10)
        if not acquired:
            raise MutexAcquisitionFailed(session_key)
        ctx.workflow_state["session_lock_key"] = f"sesslock:{session_key}"
        return {"mutex_acquired": True, "session_key": session_key}

    @hatchet.step()
    async def accumulate(self, ctx: Context) -> dict:
        """Aggregate messages into LogicalTurn."""
        # ... accumulation logic ...
        return {"turn": turn.model_dump()}

    @hatchet.step()
    async def run_pipeline(self, ctx: Context) -> dict:
        """
        Run pipeline with Toolbox for tool execution.

        Pipeline calls ctx.toolbox.execute() during tool phases.
        Toolbox handles policy, idempotency, audit events.
        """
        tenant_id = UUID(ctx.workflow_input()["tenant_id"])
        agent_id = UUID(ctx.workflow_input()["agent_id"])
        turn = LogicalTurn(**ctx.step_output("accumulate")["turn"])

        # Load AgentContext (cached or fresh)
        agent_ctx = await self._agent_runtime.get_or_create(tenant_id, agent_id)

        # Build FabricTurnContext (minimal protocol)
        fabric_ctx = FabricTurnContext(
            logical_turn=turn,
            session_key=turn.session_key,
            channel=ctx.workflow_input()["channel"],
            has_pending_messages=lambda: self._check_pending(ctx),
            emit_event=lambda e: self._route_event(e, turn),
        )

        # Build AgentTurnContext (wraps fabric + agent)
        turn_ctx = AgentTurnContext(fabric=fabric_ctx, agent_context=agent_ctx)

        # Pipeline runs with access to Toolbox via turn_ctx.toolbox
        result = await agent_ctx.pipeline.run(turn_ctx)

        return {
            "turn": turn.model_dump(),
            "result": result.model_dump(),
        }

    @hatchet.step()
    async def commit_and_respond(self, ctx: Context) -> dict:
        """Persist state, send response, release mutex."""
        result = PipelineResult(**ctx.step_output("run_pipeline")["result"])

        # Persist staged mutations
        # Send response via ChannelGateway
        # Release mutex
        lock_key = ctx.workflow_state.get("session_lock_key")
        if lock_key:
            await self._force_release_lock(lock_key)

        return {"status": "complete"}

    @hatchet.on_failure()
    async def handle_failure(self, ctx: Context):
        """Always release lock on failure."""
        lock_key = ctx.workflow_state.get("session_lock_key")
        if lock_key:
            await self._force_release_lock(lock_key)
```

---

## Implementation Strategy

### Phase 1: Internal Module

Implement ACF as `ruche/acf/` module within FOCAL:

```
ruche/
├── acf/
│   ├── __init__.py
│   ├── types.py           # Core types
│   ├── protocols.py       # CognitivePipeline, capabilities
│   ├── session_mutex.py   # SessionMutex implementations
│   ├── aggregation.py     # Turn aggregation logic
│   ├── supersede.py       # Supersede orchestration
│   ├── commit_gate.py     # Two-phase commit
│   ├── channel/
│   │   ├── capabilities.py
│   │   └── policies.py
│   ├── events.py          # FabricEvent definitions
│   ├── errors.py          # Error handling
│   └── workflow.py        # Hatchet workflow
```

### Phase 2: FOCAL Adapter

Make FOCAL implement CognitivePipeline:

```python
# ruche/alignment/acf_adapter.py

class FocalCognitivePipeline(
    CognitivePipeline,
    SupersedeCapable,
    ArtifactReuseCapable,
    AggregationHintCapable,
):
    name = "focal"

    def __init__(self, engine: AlignmentEngine):
        self._engine = engine

    async def run(self, ctx: FabricTurnContext) -> PipelineResult:
        # Translate and run FOCAL's 11-phase pipeline
        ...

    async def decide_supersede(
        self,
        current: LogicalTurn,
        new: RawMessage,
        interrupt_point: str,
    ) -> SupersedeDecision:
        # FOCAL-specific logic using intent classification
        ...

    def declare_reuse_policies(self) -> dict[str, ReusePolicy]:
        return {
            "P1_context": ReusePolicy.ALWAYS_SAFE,
            "P2_situational_snapshot": ReusePolicy.CONDITIONAL,
            "P4_retrieval": ReusePolicy.CONDITIONAL,
            "P7_tool_results": ReusePolicy.NEVER,
            "P9_response": ReusePolicy.NEVER,
        }
```

### Phase 3: Progressive Enablement

Enable ACF features progressively via config:

```toml
[acf]
enabled = true

[acf.features]
mutex = true
aggregation = true
supersede = "conservative"  # conservative | pipeline_driven
commit_gating = true
artifact_reuse = false  # Enable after measuring supersede rate

[acf.aggregation]
mode = "adaptive"
default_window_ms = 800
```

### Phase 4: Extract (If Needed)

Only extract to separate package when:
1. A second production brain needs the same mechanics
2. The interface has stabilized through real usage
3. The abstraction is simpler than the code it replaces

---

## Testing Strategy

### Pipeline Unit Tests (Mock ACF)

```python
class MockFabricContext:
    """For testing pipelines without real ACF."""
    raw_messages: list[RawMessage]
    config: dict
    versions: VersionSnapshot
    reusable_artifacts: dict[str, Artifact]

    def simulate_new_message(self, msg: RawMessage) -> None: ...
    def simulate_tool_result(self, tool: str, result: dict) -> None: ...
```

### ACF Integration Tests (Stub Pipeline)

```python
class StubPipeline(CognitivePipeline):
    """Predictable pipeline for testing ACF mechanics."""
    name = "stub"

    async def run(self, ctx: FabricTurnContext) -> PipelineResult:
        return PipelineResult(
            response_segments=[{"text": "OK"}],
        )
```

---

## Related Topics

- [01-logical-turn.md](topics/01-logical-turn.md) - LogicalTurn model details
- [02-session-mutex.md](topics/02-session-mutex.md) - Mutex implementation
- [03-adaptive-accumulation.md](topics/03-adaptive-accumulation.md) - Aggregation algorithms
- [04-side-effect-policy.md](topics/04-side-effect-policy.md) - Tool safety
- [05-checkpoint-reuse.md](topics/05-checkpoint-reuse.md) - Artifact reuse
- [06-hatchet-integration.md](topics/06-hatchet-integration.md) - Workflow implementation
- [10-channel-capabilities.md](topics/10-channel-capabilities.md) - Channel model

---

## Appendix: Boundary Definition

### ACF Owns (Mechanics)

- Session mutex
- Turn aggregation
- Supersede orchestration
- Commit gating
- Channel capabilities
- Event stream

### Pipeline Owns (Meaning)

- Intent classification
- Supersede decision logic
- Artifact reuse declarations
- Scenario semantics
- Agenda logic
- Response synthesis

### Neither Owns (External)

- ASA configuration logic
- Reporter analytics
- Tool execution (ToolHub)
- Business system integration
