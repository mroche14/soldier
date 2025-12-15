Here we go, full canon version 👇

I’ll write this as if it were `ACF_ARCHITECTURE.md` for your repo, integrating:

* your intuition,
* the coding agent’s “comprehensive fix”,
* everything we discussed about tools, channels, AG-UI, LangGraph/Agno, supersede, etc.

---

# Agent Conversation Fabric (ACF) – Canonical Architecture

> **Status**: Draft, architecture-binding
> **Scope**: Multi-agent, multi-channel conversational runtime for FOCAL, LangGraph, Agno and other “CognitivePipelines”.

---

## 1. Purpose & Scope

### 1.1 What problem ACF solves

Even with a very good alignment engine (FOCAL, LangGraph graphs, Agno workflows, etc.), conversations feel:

* unsafe (double actions, race conditions),
* “non-human” (interruptions ignored, no notion of beats),
* brittle (tool side effects vs user corrections),

if the **conversation mechanics** are naive.

**ACF exists to solve conversation mechanics**, not “what the agent thinks or says”.

Concretely, ACF provides:

* **Session mutex** – exactly one logical turn per (tenant, agent, user, channel) at a time.
* **Turn aggregation** – “beats” or logical turns, not per-message chaos.
* **Supersede signalling** – when new messages arrive mid-turn.
* **Durable orchestration** – via Hatchet (or equivalent workflow engine).
* **Fabric events** – a unified event stream for observability & UI.

ACF does **not** decide:

* which tools to call,
* whether to refund or not,
* how to ask for confirmation,
* how to handle AG-UI, etc.

Those are Agent-level concerns.

---

## 2. High-Level Layers & Roles

### 2.1 Global view

```text
[User on Channel] 
    ↓
[ChannelAdapter]  (WhatsApp, Webchat, Email, etc.)
    ↓
[ChannelGateway]  (normalize to RawMessage / OutboundMessage)
    ↓
[TurnGateway]     (ACF ingress)
    ↓
[LogicalTurnWorkflow] (Hatchet, owned by ACF)
    ↓
[AgentRuntime] → [AgentContext] (Agent + CognitiveBrain + Toolbox + channels)
    ↓
[CognitiveBrain.run/plan/finalize]  (FOCAL, LangGraph wrapper, Agno, etc.)
    ↓
[Toolbox → ToolGateway → external systems]
    ↓
[ACF Commit Step → SessionStore, TurnStore, AuditStore]
    ↓
[ChannelGateway] → [ChannelAdapter] → [User]
```

### 2.2 Main concepts

* **ACF (Agent Conversation Fabric)**
  Thin conversation runtime: mutex, logical turns, supersede signalling, workflow orchestration, fabric events.

* **Agent**
  Configuration entity per tenant:

  * which **CognitiveBrain**,
  * which **tools**,
  * which **channels**,
  * which **scenarios/rules** (for FOCAL).

* **AgentRuntime**
  Runtime manager, responsible for:

  * loading agent config from `ConfigStore`,
  * building & caching `AgentContext` (brain + toolbox + channel bindings),
  * invalidating on config changes.

* **AgentContext**
  In-memory representation of an Agent at runtime:

  * `agent`: config object,
  * `brain`: `CognitiveBrain` implementation,
  * `toolbox`: agent-level tool facade,
  * `channel_bindings`: mapping channel → channel-specific config (webchat vs WhatsApp, etc.).

* **AgentTurnContext**
  The per-turn object passed to the brain:

  * wraps both `FabricTurnContext` (ACF side) and `AgentContext` (Agent side),
  * is the main entry point for CognitivePipelines.

* **Toolbox & ToolGateway**

  * `Toolbox`: agent-level tool facade, aware of per-agent tool configuration and side-effect policy.
  * `ToolGateway`: infra-level executor (wrapping Composio, HTTP, internal functions, etc.) with idempotency and provider adapters.

* **ChannelGateway & ChannelAdapters**
  Infrastructure for:

  * normalizing inbound events to `RawMessage`,
  * formatting outbound responses per channel,
  * optional AG-UI integration for webchat.

---

## 3. Design Principles

1. **Separation of concerns**

   * ACF knows about turns, locks, workflows, events.
   * Agent knows about brain, tools, channels, scenarios.
   * Toolbox/ToolGateway know about external systems & side effects.

2. **Thin waist**

   * A minimal, stable interface between ACF and CognitivePipelines (run/plan/finalize).
   * Many brains on top (FOCAL, LangGraph, Agno).
   * Many channels below (WhatsApp, webchat, email), unified by ACF’s `RawMessage` / `OutboundMessage`.

3. **Brain autonomy**

   * Brains can implement complex mechanics (multi-step plans, retry loops, confirmations, agendas, etc.) **without** changing ACF.
   * ACF gives signals (pending messages, events), brains decide how to use them.

4. **Supersede ≠ ACF policy**

   * ACF detects new messages during a turn.
   * Brain decides: supersede, absorb, queue, or ignore.

5. **Events, not callbacks**

   * ACF offers `emit_event(FabricEvent)`.
   * Other systems (logging, AG-UI, analytics) subscribe.

6. **Tool control stays near the agent**

   * Tool choice, side-effect policy, and confirmation logic live in the CognitiveBrain + Toolbox, not in ACF.

---

## 4. Core Data Models

### 4.1 RawMessage (ingress)

```python
class RawMessage(BaseModel):
    id: str
    tenant_id: UUID
    agent_id: UUID           # Which agent handles this
    customer_id: str         # Channel-specific user id
    channel: str             # "whatsapp", "webchat", "email", ...
    timestamp: datetime

    content_type: Literal["text", "attachment", "event"]
    text: str | None = None
    # + optional metadata like locale, attachments, etc.
```

### 4.2 LogicalTurn

A “beat” / logical turn (aggregated from 1..N RawMessages).

```python
class LogicalTurn(BaseModel):
    id: UUID
    turn_group_id: UUID            # all attempts related to a “conversation attempt”
    session_key: str               # (tenant, agent, customer, channel)
    messages: list[RawMessage]     # aggregated messages
    started_at: datetime
    superseded_by: UUID | None = None

    side_effects: list["SideEffectRecord"] = []
    # Optional: references to artifacts (retrieval, rerank etc.) – brain-specific.
```

### 4.3 SideEffectRecord

```python
class SideEffectPolicy(str, Enum):
    PURE = "pure"              # no external state
    IDEMPOTENT = "idempotent"  # safe to retry
    COMPENSATABLE = "compensatable"
    IRREVERSIBLE = "irreversible"

class SideEffectRecord(BaseModel):
    tool_name: str
    policy: SideEffectPolicy
    executed_at: datetime
    status: Literal["executed", "failed"]
    result_summary: dict | None = None   # redacted/result summary
    external_reference: str | None = None  # e.g. refund id, ticket id
```

### 4.4 FabricEvent

Infrastructure-level event for observability + UI:

```python
class FabricEventType(str, Enum):
    TURN_STARTED = "turn_started"
    TURN_SUPERSEDED = "turn_superseded"
    TURN_COMMITTED = "turn_committed"

    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"

    PIPELINE_ERROR = "pipeline_error"
    TOOL_ERROR = "tool_error"

    # Optional: UI streaming stuff (token, partial step…)
    PARTIAL_RESPONSE = "partial_response"
```

```python
class FabricEvent(BaseModel):
    type: FabricEventType
    logical_turn_id: UUID
    session_key: str
    timestamp: datetime
    payload: dict[str, Any] = {}
    trace_context: dict[str, Any] = {}   # for tracing (OpenTelemetry etc.)
```

### 4.5 PipelineResult / PlanResult / FinalizeResult

These are what brains return; ACF doesn’t care what happens inside.

```python
class ResponseSegment(BaseModel):
    # minimal; can be extended later
    text: str | None = None
    # could later add: structured actions, UI hints etc.

class PipelineResult(BaseModel):
    responses: list[ResponseSegment] = []
    staged_mutations: dict[str, Any] = {}   # e.g. handoff
    # Brain may also include brain-specific artifacts.

class PlanResult(BaseModel):
    planned_tools: list["PlannedToolExecution"] = []
    plan_metadata: dict[str, Any] = {}
    artifacts: list[Any] = []

class FinalizeResult(BaseModel):
    responses: list[ResponseSegment]
    staged_mutations: dict[str, Any] = {}
```

### 4.6 PlannedToolExecution & ToolExecutionContext

```python
class PlannedToolExecution(BaseModel):
    tool_name: str
    args: dict
    side_effect_policy: SideEffectPolicy
    # optional: business-key for idempotency, derived later if not provided
    business_key: str | None = None
```

```python
@dataclass
class ToolExecutionContext:
    tenant_id: UUID
    agent_id: UUID
    turn_group_id: UUID      # from LogicalTurn
    tool_name: str
    args: dict

    def build_idempotency_key(self, business_key: str) -> str:
        return f"{self.tool_name}:{business_key}:turn_group:{self.turn_group_id}"
```

---

## 5. Interfaces & Boundaries

### 5.1 FabricTurnContext (ACF → Agent)

```python
class FabricTurnContext(Protocol):
    logical_turn: LogicalTurn
    session_key: str

    async def has_pending_messages(self) -> bool:
        """
        True if any new RawMessage arrived for this session_key
        since the current LogicalTurn started.
        """

    async def get_pending_messages(self) -> list[RawMessage]:
        """
        Optional: actual pending messages for ABSORB strategies.
        """

    async def emit_event(self, event: FabricEvent) -> None:
        """
        Publish an infrastructure-level event for logging, UI, etc.
        """
```

### 5.2 AgentContext & AgentTurnContext

```python
@dataclass
class AgentContext:
    agent: "Agent"                     # config
    brain: "CognitiveBrain"      # FOCAL / LangGraph / Agno wrapper
    toolbox: "Toolbox"
    channel_bindings: dict[str, "ChannelBinding"]
```

```python
@dataclass
class AgentTurnContext:
    fabric: FabricTurnContext
    agent_context: AgentContext

    @property
    def toolbox(self) -> "Toolbox":
        return self.agent_context.toolbox

    @property
    def agent(self) -> "Agent":
        return self.agent_context.agent

    @property
    def logical_turn(self) -> LogicalTurn:
        return self.fabric.logical_turn

    async def has_pending_messages(self) -> bool:
        return await self.fabric.has_pending_messages()

    async def emit_event(self, event: FabricEvent) -> None:
        await self.fabric.emit_event(event)
```

### 5.3 CognitiveBrain

This is the “brain” contract.

```python
class CognitiveBrain(Protocol):
    """Main interface between ACF and brains (FOCAL, LangGraph, Agno, etc.)."""

    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        """
        Process one LogicalTurn.

        - Can execute tools through ctx.toolbox
        - Can check for supersede via ctx.has_pending_messages()
        - Can emit FabricEvents via ctx.emit_event()
        """

    # Optional for Mode 2:
    async def plan(self, ctx: AgentTurnContext) -> PlanResult:
        """
        Plan tools / structure before tool execution.
        Used only if Agent is configured for Mode 2.
        """

    async def finalize(
        self,
        ctx: AgentTurnContext,
        tool_results: list["ToolResult"],
    ) -> FinalizeResult:
        """
        Final response construction after tools.
        Only used in Mode 2.
        """
```

This interface is intentionally small so you can:

* wrap FOCAL as one implementation,
* wrap LangGraph (graph.invoke / graph.stream),
* wrap Agno workflows/agents.

### 5.4 Toolbox & ToolGateway

```python
class ToolResult(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None
```

```python
class ToolGateway(Protocol):
    """Infrastructure-level tool executor (provider adapters)."""

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        ...
```

```python
class Toolbox:
    """Agent-level tool facade."""

    def __init__(
        self,
        agent_id: UUID,
        tool_definitions: dict[str, "ToolDefinition"],
        tool_activations: dict[str, "ToolActivation"],
        gateway: ToolGateway,
    ):
        self._agent_id = agent_id
        self._tools = {
            t.name: t
            for t in tool_definitions.values()
            if tool_activations.get(t.id, ToolActivation(enabled=True)).enabled
        }
        self._gateway = gateway

    def get_metadata(self, tool_name: str) -> "ToolMetadata":
        defn = self._tools[tool_name]
        return ToolMetadata(
            name=defn.name,
            side_effect_policy=defn.side_effect_policy,
            requires_confirmation=defn.requires_confirmation,
            # ...
        )

    async def execute(
        self,
        planned_tool: PlannedToolExecution,
        turn_context: AgentTurnContext,
    ) -> ToolResult:
        tool_def = self._tools[planned_tool.tool_name]
        exec_ctx = ToolExecutionContext(
            tenant_id=turn_context.agent.tenant_id,
            agent_id=turn_context.agent.id,
            turn_group_id=turn_context.logical_turn.turn_group_id,
            tool_name=planned_tool.tool_name,
            args=planned_tool.args,
        )

        # Build idempotency key:
        business_key = planned_tool.business_key or self._derive_business_key(planned_tool, tool_def)
        idem_key = exec_ctx.build_idempotency_key(business_key)

        # Optionally emit TOOL_EXECUTION_STARTED event
        await turn_context.emit_event(FabricEvent(
            type=FabricEventType.TOOL_EXECUTION_STARTED,
            logical_turn_id=turn_context.logical_turn.id,
            session_key=turn_context.fabric.session_key,
            timestamp=datetime.utcnow(),
            payload={
                "tool_name": planned_tool.tool_name,
                "policy": tool_def.side_effect_policy.value,
            },
        ))

        result = await self._gateway.execute(exec_ctx)

        # Record side-effect for audit / supersede:
        effect = SideEffectRecord(
            tool_name=planned_tool.tool_name,
            policy=tool_def.side_effect_policy,
            executed_at=datetime.utcnow(),
            status="executed" if result.success else "failed",
            result_summary=None,  # to be determined by tool type
        )
        await turn_context.emit_event(FabricEvent(
            type=FabricEventType.TOOL_EXECUTION_COMPLETED,
            logical_turn_id=turn_context.logical_turn.id,
            session_key=turn_context.fabric.session_key,
            timestamp=datetime.utcnow(),
            payload=effect.model_dump(),
        ))

        return result
```

Note: **ACF does not know** how tools are executed; it only sees FabricEvents and side effects attached to LogicalTurn.

---

## 6. ACF: Runtime Mechanics

### 6.1 SessionMutex & TurnManager

ACF provides:

* **SessionMutex**: ensure one LogicalTurnWorkflow per `session_key`.
* **TurnManager**:

  * accumulates RawMessages into LogicalTurns,
  * sets `turn_group_id` (for one “conversation attempt”),
  * marks turns as superseded.

### 6.2 TurnGateway & Hatchet workflow

Pseudo-flow:

```python
class TurnGateway:
    async def receive_message(self, message: RawMessage) -> None:
        session_key = build_session_key(
            tenant_id=message.tenant_id,
            agent_id=message.agent_id,
            customer_id=message.customer_id,
            channel=message.channel,
        )

        # Start or signal Hatchet workflow
        await self._hatchet.run_or_signal(
            workflow="LogicalTurnWorkflow",
            session_key=session_key,
            message=message,
        )
```

Hatchet workflow (Mode 1 / SIMPLE):

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.step()
    async def acquire_mutex(self, ctx: Context) -> dict:
        # Use SessionMutex to lock based on session_key
        ...

    @hatchet.step()
    async def accumulate(self, ctx: Context) -> dict:
        # Aggregate messages for a short window (if configured)
        # Build LogicalTurn
        logical_turn = await self._turn_manager.build_turn(ctx)
        return {"logical_turn": logical_turn.model_dump()}

    @hatchet.step()
    async def run_pipeline(self, ctx: Context) -> dict:
        logical_turn = LogicalTurn(**ctx.step_output("accumulate")["logical_turn"])

        # Build FabricTurnContext
        fabric_ctx = self._build_fabric_context(ctx, logical_turn)

        # Resolve AgentContext
        tenant_id = logical_turn.session_key_tenant
        agent_id = logical_turn.session_key_agent
        agent_ctx = await self._agent_runtime.get_or_create(tenant_id, agent_id)

        # Build AgentTurnContext
        turn_ctx = AgentTurnContext(fabric=fabric_ctx, agent_context=agent_ctx)

        # Run cognitive pipeline
        result = await agent_ctx.brain.run(turn_ctx)
        return {"result": result.model_dump()}

    @hatchet.step()
    async def commit_and_respond(self, ctx: Context) -> dict:
        # Persist session & turn, handle staged mutations, send response
        ...
```

Mode 2 adds:

* `plan` step,
* `execute_tools` step (Agent’s Toolbox),
* `finalize` step.

---

## 7. Orchestration Modes

To reconcile single-pass and two-pass architectures we support **three modes** per Agent.

```python
class OrchestrationMode(str, Enum):
    SIMPLE = "simple"        # text-only, or tools with trivial semantics
    SINGLE_PASS = "single"   # Mode 1: run() does everything
    TWO_PASS = "two_pass"    # Mode 2: plan / tools / finalize
```

### 7.1 Mode 0 – SIMPLE

* No tools or trivial tools.
* Workflow: `acquire_mutex → accumulate → run_pipeline → commit`.

Use for:

* FAQ-style agents,
* prototypes,
* channels where only simple text responses matter.

### 7.2 Mode 1 – SINGLE_PASS (default)

* Tools executed **inside** `brain.run(ctx)` via `ctx.toolbox.execute()`.
* ACF doesn’t know about tools; it just runs `run()`.
* Supersede control via `await ctx.has_pending_messages()` inside brain, especially before irreversible tools.

Pros:

* Clean, single cognitive flow.
* Pipelined phases (P1–P11) stay intact.
* Works nicely for LangGraph/Agno where reasoning & tools are interleaved.

Constraints:

* `run()` may be long-running.
* Retry of the Hatchet step must rely on **tool idempotency** (via ToolGateway).

### 7.3 Mode 2 – TWO_PASS (high-stakes / enterprise)

* ACF workflow has steps:

  * `plan` (brain.plan),
  * `execute_tools` (Agent’s Toolbox),
  * `finalize` (brain.finalize).

Used when:

* Tools are **high-stakes** (money, legal, regulatory).
* You want:

  * separate durable step for tool execution,
  * clearer observability in workflow UI,
  * clean supersede points (between plan and tools).

Tradeoff:

* Requires brain to implement `plan` and `finalize`.
* You may “feel” like you have more state handoff (PlanResult → tool_results → FinalizeResult), but it’s manageable.

---

## 8. Supersede Semantics

### 8.1 What ACF does

Within a LogicalTurn, ACF:

* tracks if new RawMessages arrived for the same session_key,
* exposes `has_pending_messages()` and `get_pending_messages()`,
* can mark the current LogicalTurn as **superseded** and start a new one if the brain decides so.

ACF does **not** decide policy. It just:

* **applies** decisions coming from the brain (via the returned `PipelineResult`).

### 8.2 What the brain decides

Inside brain, before high-risk operations, you can do:

```python
if planned_tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
    if await ctx.has_pending_messages():
        action = await self._decide_supersede_action(ctx, planned_tool)
        if action == SupersedeAction.SUPERSEDE:
            # Return PipelineResult indicating supersede
            return PipelineResult(
                responses=[ResponseSegment(text="Let me restart with your latest instructions.")],
                staged_mutations={"supersede": {"mode": "restart"}},
            )
        elif action == SupersedeAction.ABSORB:
            pending = await ctx.fabric.get_pending_messages()
            # Incorporate them into the turn’s understanding
            self._absorb_into_context(pending)
        # FORCE_CONTINUE: proceed anyway

result = await ctx.toolbox.execute(planned_tool, ctx)
```

Possible decisions:

```python
class SupersedeAction(str, Enum):
    SUPERSEDE = "supersede"   # abort current turn and start new logical turn
    ABSORB = "absorb"         # treat new messages as part of this turn
    QUEUE = "queue"           # finish current turn, process later
    FORCE_CONTINUE = "continue"
```

### 8.3 ACF applying the decision

In `commit_and_respond`:

* If `staged_mutations["supersede"]` is present:

  * mark the current LogicalTurn as superseded,
  * create a new LogicalTurn (with new turn_id, same turn_group_id),
  * optionally carry some context over (e.g. retrieval artifacts),
  * not send a final “completed” signal for the aborted turn.

All the **semantics** (when to supersede, how to merge messages) stay in the brain.

---

## 9. Tool Side-Effects & Idempotency

### 9.1 Ownership split

* **Toolbox / ToolGateway**:

  * know about **tool semantics** (irreversible vs compensatable etc.),
  * implement idempotency,
  * record `SideEffectRecord`s and emit FabricEvents.

* **ACF**:

  * attaches side-effect records to `LogicalTurn.side_effects`,
  * uses them only as **facts** if needed for analytics/supersede review.

* **CognitiveBrain**:

  * decides **when** to execute which tools,
  * decides **if** to check for supersede before an irreversible tool,
  * knows confirmation needs, etc.

### 9.2 Idempotency details

ToolGateway uses `ToolExecutionContext`:

```python
class ToolGateway(Protocol):
    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        idem_key = ctx.build_idempotency_key(self._extract_business_key(ctx.args))

        if cached := await self._idem_cache.get(idem_key):
            return cached

        result = await self._provider.call(ctx.tool_name, ctx.args)

        if result.success:
            await self._idem_cache.set(idem_key, result, ttl=86400)

        return result
```

* For **retry after crash**, ACF just re-runs the Hatchet step; ToolGateway ensures the tool is not double-applied (if properly configured).
* For **supersede**, using `turn_group_id` in the idempotency key ties operations to a conversation attempt.

---

## 10. Agents & AgentRuntime

### 10.1 Agent

Config entity stored in `ConfigStore`:

```python
class Agent(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str

    # core:
    pipeline_type: Literal["focal", "langgraph", "agno", "custom"]
    orchestration_mode: OrchestrationMode

    # scenario/rules config for FOCAL, or paths/settings for other brains
    pipeline_config: dict

    # tool config:
    tool_activations: list["ToolActivationIdOrRef"]  # or looked up separately

    # channel bindings:
    channel_bindings: dict[str, "ChannelBindingConfig"]
```

### 10.2 AgentRuntime

Manages agent lifecycle & caching.

```python
class AgentRuntime:
    def __init__(self, config_store: ConfigStore, gateway_registry: ToolGatewayRegistry, channel_gateway: ChannelGateway):
        self._config_store = config_store
        self._gateway_registry = gateway_registry
        self._channel_gateway = channel_gateway
        self._cache: dict[tuple[UUID, UUID], AgentContext] = {}
        self._cache_versions: dict[tuple[UUID, UUID], str] = {}

    async def get_or_create(self, tenant_id: UUID, agent_id: UUID) -> AgentContext:
        key = (tenant_id, agent_id)
        if key in self._cache:
            current_version = await self._config_store.get_agent_version(tenant_id, agent_id)
            if self._cache_versions.get(key) == current_version:
                return self._cache[key]

        # Build fresh AgentContext
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        brain = self._build_pipeline(agent)
        toolbox = await self._build_toolbox(agent)
        channel_bindings = await self._load_channel_bindings(tenant_id, agent.id)

        ctx = AgentContext(
            agent=agent,
            brain=brain,
            toolbox=toolbox,
            channel_bindings=channel_bindings,
        )

        version = await self._config_store.get_agent_version(tenant_id, agent_id)
        self._cache[key] = ctx
        self._cache_versions[key] = version
        return ctx

    async def invalidate(self, tenant_id: UUID, agent_id: UUID) -> None:
        key = (tenant_id, agent_id)
        self._cache.pop(key, None)
        self._cache_versions.pop(key, None)
```

---

## 11. Channels & AG-UI

### 11.1 Channels live outside ACF

* **ChannelAdapters** normalize provider-specific payloads → `RawMessage` and `OutboundMessage`.
* **ChannelGateway** routes to/from ACF.

ACF only cares about:

* `channel` string in `session_key`,
* some optional channel metadata if needed for heuristics.

### 11.2 AG-UI specifically

AG-UI is:

* **not part of ACF**,
* not part of the CognitiveBrain.

It’s a **protocol & UI layer inside WebchatAdapter**.

You can configure per agent / per channel:

```yaml
agents:
  focal_support:
    channels:
      webchat:
        adapter: "webchat_agui"       # uses AG-UI protocol via CopilotKit or custom
        ag_ui_enabled: true
      whatsapp:
        adapter: "whatsapp_twilio"
        ag_ui_enabled: false
```

WebchatAdapter implementation:

* Maps ACF’s `FabricEvent` + `ResponseSegment` into AG-UI events (if enabled).
* Or maps them into your own webchat protocol (if AG-UI disabled).

The brain just says:

* “I need to ask the user for confirmation” (e.g. by generating normal text, or by using some structured instruction).

Adapter decides:

* In AG-UI webchat → show dialog / buttons.
* In WhatsApp → send Yes/No text.

No AG-UI logic bleeds into ACF; AG-UI is purely a channel implementation detail.

---

## 12. Error Handling & Observability

### 12.1 Error handling

Where errors are handled:

* **CognitiveBrain**:

  * wraps LLM calls,
  * catches & maps domain errors into `PipelineResult` (e.g. “I’m having trouble processing your order”).

* **Toolbox / ToolGateway**:

  * wraps external system calls,
  * returns `ToolResult(success=False, error=...)`,
  * emits `FabricEvent(TOOL_ERROR)`,
  * brain decides how to react.

* **ACF**:

  * catches uncaught exceptions from `run/plan/finalize`,
  * emits `FabricEvent(PIPELINE_ERROR, payload=...)`,
  * decides whether to retry Hatchet step based on a configurable `FabricErrorPolicy`.

Example:

```python
class FabricErrorPolicy(BaseModel):
    on_pipeline_error: Literal["retry", "fail", "escalate"]
    on_tool_error: Literal["retry", "fail", "escalate"]
    max_retries: int = 3
```

### 12.2 Observability

ACF is the main emitter of **FabricEvents**, but:

* Toolbox also emits events for tool execution,
* Brains can emit custom events via `ctx.emit_event()`.

You can plug:

* logging subscribers,
* metrics exporters,
* AG-UI streaming connectors,

onto the FabricEvent stream without impacting brain code.

---

## 13. Multi-Agent Handoffs

Handoff is modelled as a **staged mutation** in `PipelineResult`:

```python
# inside brain
if should_handoff_to_billing_specialist:
    return PipelineResult(
        responses=[ResponseSegment(text="I’ll transfer you to our billing specialist.")],
        staged_mutations={
            "handoff": {
                "target_agent_id": str(target_agent_id),
                "context_summary": self._summarize_context(ctx),
            }
        },
    )
```

In `commit_and_respond` step:

* ACF persists current turn and session,
* updates `session_key` to use `target_agent_id`,
* stores `context_summary` in `SessionStore` transfer field,
* next message for that (tenant, new_agent, customer, channel) will be routed to the new agent.

Agent B can then:

* load context summary,
* optionally fetch previous LogicalTurns for richer context.

---

## 14. Using LangGraph / Agno / Other Frameworks

Because CognitiveBrain is only:

```python
async def run(ctx: AgentTurnContext) -> PipelineResult
# optionally plan/finalize
```

You can write wrappers:

### 14.1 LangGraph

```python
class LangGraphPipeline(CognitiveBrain):
    def __init__(self, graph: StateGraph, config: dict):
        self._graph = graph
        self._config = config

    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        # Build initial graph state from ctx.logical_turn, session, etc.
        state = self._build_initial_state(ctx)
        # Optionally pass ctx.toolbox as a tool handler
        result_state = await self._graph.invoke(state)
        return self._map_state_to_pipeline_result(result_state)
```

### 14.2 Agno

```python
class AgnoPipeline(CognitiveBrain):
    def __init__(self, agno_agent):
        self._agent = agno_agent

    async def run(self, ctx: AgentTurnContext) -> PipelineResult:
        # Use Agno’s API, but feed ctx.logical_turn.text or messages
        result = await self._agent.run(ctx.logical_turn.messages)
        return PipelineResult(
            responses=[ResponseSegment(text=result.text)],
            staged_mutations=result.staged_mutations,
        )
```

FOCAL is just another implementation that happens to know about phases, scenarios, rules, etc.

---

## 15. Summary of Ownership

| Component             | Owns                                                                                   | Does **not** own                                  |
| --------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------- |
| **ACF**               | Mutex, logical turns, accumulation, supersede signals, workflows, FabricEvents routing | Tool semantics, scenario logic, confirmation text |
| **AgentRuntime**      | AgentContext lifecycle (build, cache, invalidate)                                      | Turn-level logic                                  |
| **AgentContext**      | Brain, Toolbox, channel bindings                                                    | Infrastructure state                              |
| **AgentTurnContext**  | Connects FabricTurnContext to AgentContext                                             | Long-lived cached state                           |
| **CognitiveBrain** | Alignment & reasoning, when/which tools to call, supersede decisions, confirmations    | Mutex, workflows, external APIs                   |
| **Toolbox**           | Resolve tools per agent, call ToolGateway, emit side-effect events                     | Provider details                                  |
| **ToolGateway**       | Provider adapters (Composio, HTTP, internal), operation idempotency                    | Tool metadata, per-agent policies                 |
| **ChannelGateway**    | Normalize inbound, format outbound, per-channel protocols                              | Agent selection & brain logic                  |

---

If you want, next step I can:

* break this into **three files** as suggested by the coding agent:

  * `ACF_SPEC.md` (just ACF),
  * `AGENT_RUNTIME_SPEC.md` (AgentRuntime, AgentContext),
  * `TOOLBOX_SPEC.md` (Toolbox, ToolGateway),
* or add a **shorter dev-facing “How to implement a new brain”** guide on top of this.

But this doc is the exhaustive “single source of truth” for ACF + Agent + Toolbox boundaries.
