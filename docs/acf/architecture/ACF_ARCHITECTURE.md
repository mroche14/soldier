# Focal Platform Architecture

> **Status**: AUTHORITATIVE ARCHITECTURE DOCUMENT
> **Version**: 3.0
> **Date**: 2025-12-11
> **Supersedes**: Previous ACF_SPEC.md tool ownership sections

---

## Executive Summary

This document defines the **canonical architecture** for Focal's conversational AI platform. It establishes clear boundaries between:

1. **ACF (Agent Conversation Fabric)** - Pure conversation runtime infrastructure
2. **Agent** - Business entity with brain, tools, and channel bindings
3. **Toolbox + ToolGateway** - Tool execution infrastructure
4. **ChannelGateway** - Channel protocol infrastructure

**Core Principle**: ACF is a thin waist. It knows about turns, mutexes, and workflow orchestration. It does NOT know about tools, scenarios, or channel UX.

---

## 1. Architecture Overview

### 1.1 Layer Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            RUNTIME LAYER                                    │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentRuntime                                      │  │
│  │   Per-tenant-agent instance lifecycle manager                       │  │
│  │   - Creates AgentContext on demand                                  │  │
│  │   - Caches warm agents for reuse                                    │  │
│  │   - Invalidates on config change                                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentContext                                      │  │
│  │   The configured "business entity" for conversations                │  │
│  │   - agent: Agent (configuration)                                    │  │
│  │   - brain: Brain (FOCAL, LangGraph, Agno)                     │  │
│  │   - toolbox: Toolbox (tool facade)                                 │  │
│  │   - channel_bindings: dict[str, ChannelBinding]                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
└────────────────────────────────────┼───────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            ACF LAYER                                        │
│                     (Pure Conversation Infrastructure)                      │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │SessionMutex  │  │ TurnManager  │  │ Supersede    │  │ Hatchet      │  │
│  │- acquire     │  │- aggregate   │  │ Coordinator  │  │ Workflow     │  │
│  │- release     │  │- accumulate  │  │- signal      │  │- orchestrate │  │
│  │- extend      │  │- boundary    │  │- query state │  │- retry       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                            │
│  ACF provides to Agent:                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ FabricTurnContext:                                                    │ │
│  │   logical_turn: LogicalTurn                                          │ │
│  │   session_key: str                                                   │ │
│  │   has_pending_messages: Callable[[], Awaitable[bool]]                │ │
│  │   emit_event: Callable[[ACFEvent], Awaitable[None]]               │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                               │
│                                                                            │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │ToolGateway                       │  │ChannelGateway                   ││
│  │- Execute tool calls              │  │- Route messages                 ││
│  │- Provider adapters (Composio,    │  │- Protocol adapters (AG-UI,      ││
│  │  HTTP, Internal)                 │  │  Twilio, SMTP)                  ││
│  │- Operation idempotency           │  │                                 ││
│  └──────────────────────────────────┘  └─────────────────────────────────┘│
│                                                                            │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │ Stores                           │  │ Providers                       ││
│  │- ConfigStore                     │  │- LLMExecutor                    ││
│  │- SessionStore                    │  │- EmbeddingProvider              ││
│  │- MemoryStore                     │  │- RerankProvider                 ││
│  │- AuditStore                      │  │                                 ││
│  └──────────────────────────────────┘  └─────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Boundaries

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| **ACF** | Mutex, turns, accumulation, supersede signals, Hatchet orchestration, ACFEvent routing | Tool execution, tool metadata, channel UX, business logic |
| **AgentRuntime** | Agent lifecycle, caching, invalidation | Turn processing, tool calls |
| **AgentContext** | Brain, Toolbox, ChannelBindings (configuration) | Runtime turn state |
| **Toolbox** | Tool resolution, execution via gateway, side effect recording | Tool backend implementation, idempotency storage |
| **ToolGateway** | Provider adapters, operation idempotency, external API calls | Tool metadata, side effect policies |
| **ChannelGateway** | Protocol adapters, message normalization | Routing decisions, agent selection |

---

## 2. ACF: Agent Conversation Fabric

### 2.1 What ACF Owns

ACF is the **conversation runtime**. It handles:

1. **Session Mutex**
   - Key: `sesslock:{tenant_id}:{agent_id}:{customer_id}:{channel}`
   - Guarantee: Never run two brains in parallel for the same session
   - Implementation: Redis lock + Hatchet workflow coordination

2. **Turn Aggregation (TurnManager)**
   - Collect incoming messages into a LogicalTurn
   - Use time windows, typing indicators, or brain hints
   - ACF aggregates; it does NOT interpret intent

3. **Supersede Signals (SupersedeCoordinator)**
   - Query: "Has a new message arrived during this turn?"
   - Signal: Provide fact to Brain, not make decision
   - Brain decides SUPERSEDE/ABSORB/QUEUE/FORCE_COMPLETE

4. **Workflow Orchestration (Hatchet)**
   - Run per-session workflows with durable steps
   - Provide step boundaries for durability
   - Handle retries, error recovery, scheduling

5. **ACFEvent Routing**
   - Receive events from Agent/Brain/Toolbox
   - Route to logs, analytics, live UIs
   - Persist effects in LogicalTurn for supersede decisions

### 2.2 What ACF Does NOT Own

**Critical**: ACF has zero knowledge of:

- Tool semantics (reversible, compensatable, etc.)
- Tool execution logic
- Scenario/rule semantics
- Channel-specific behavior (only routing keys)
- Confirmation logic
- Business decisions

These belong to **Agent** (Brain + Toolbox).

### 2.3 FabricTurnContext Interface

What ACF provides to Agent for each turn:

```python
class FabricTurnContext(Protocol):
    """
    ACF's interface to Agent - infrastructure only.

    IMPORTANT: This context is NOT serializable. It contains live callbacks
    (has_pending_messages, emit_event) that point back to ACF.

    Hatchet serializes only DATA (logical_turn, session_key, IDs).
    FabricTurnContext is REBUILT fresh at the start of each Hatchet step.
    """

    logical_turn: LogicalTurn
    session_key: str
    channel: str

    async def has_pending_messages(self) -> bool:
        """
        Query: Did any new message arrive during this turn?

        This is a FACT query. Brain decides what to do with the answer.
        Must be monotonic within a turn (once True, stays True).
        """
        ...

    async def emit_event(self, event: ACFEvent) -> None:
        """
        Emit a ACFEvent for routing/persistence.

        ACF will:
        - Route to appropriate listeners
        - Persist side effects to LogicalTurn
        - Forward to analytics/live UIs
        """
        ...
```

**Serialization Note**: Between Hatchet workflow steps, only data is persisted:
- `logical_turn` (serialized as dict)
- `session_key`, `tenant_id`, `agent_id` (strings/UUIDs)

The context with live callbacks is reconstructed when a step starts.

### 2.4 Supersede: Facts vs Decisions

**ACF provides FACTS**:
```python
class SupersedeCoordinator:
    """ACF component - knows if new messages arrived."""

    async def has_pending_messages(self, session_key: str) -> bool:
        """Pure fact query."""
        return await self._message_queue.has_pending(session_key)

    async def get_pending_messages(self, session_key: str) -> list[RawMessage]:
        """Get actual pending messages (for ABSORB)."""
        return await self._message_queue.get_pending(session_key)
```

**Brain makes DECISIONS**:

### 2.5 Commit Points

A **commit point** is the moment in a turn when side effects can no longer be safely undone.

```python
# Commit point = first IRREVERSIBLE tool execution
class CommitPointTracker:
    """Tracks whether a turn has reached its commit point."""

    def __init__(self):
        self._commit_point_reached = False

    def mark_commit_point(self) -> None:
        """Called when IRREVERSIBLE tool completes successfully."""
        self._commit_point_reached = True

    @property
    def commit_point_reached(self) -> bool:
        """True if turn cannot be safely superseded."""
        return self._commit_point_reached
```

**Commit Point Implications**:

| State | Supersede Behavior |
|-------|-------------------|
| Before commit point | SUPERSEDE allowed - cancel and restart with all messages |
| After commit point | QUEUE required - finish current, then process new turn |

**What Constitutes a Commit Point**:
- `IRREVERSIBLE` tool executed successfully (refund processed, email sent)
- `COMPENSATABLE` tool may also mark commit if compensation is costly
- Never: `SAFE` or `RETRIABLE` tools

The commit point is tracked on `LogicalTurn.commit_point_reached: bool` and influences `default_supersede_decision()` in ACF_SPEC.md.

**Brain makes DECISIONS**:

```python
class FocalBrain(Brain):
    async def _check_supersede_before_tool(
        self,
        tool: PlannedToolExecution,
        ctx: AgentTurnContext,
    ) -> SupersedeAction | None:
        """Brain decides what to do with supersede signal."""

        if tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
            if await ctx.has_pending_messages():
                # BRAIN decides: abort? queue? continue?
                return await self._decide_supersede_action(ctx, tool)

        return None  # Continue with tool execution
```

---

## 3. Agent: The Business Entity

### 3.1 Agent as Primary Abstraction

An **Agent** is a configured conversational AI instance for a tenant. It contains:

- **Brain**: The thinking unit (FOCAL, LangGraph, Agno) - Agent owns its Brain
- **Toolbox**: What tools it can use
- **ChannelBindings**: Where it's reachable

**Key principle**: ACF calls `agent.process_turn()`. Agent uses its Brain internally. ACF doesn't know or care what Brain an agent has.

### 3.2 AgentContext

Runtime representation of a configured Agent:

```python
@dataclass
class AgentContext:
    """
    The configured business entity for conversations.

    Created by AgentRuntime, cached for reuse, invalidated on config change.
    Agent owns its Brain - ACF calls Agent, which uses Brain internally.
    """
    agent: Agent                           # Configuration from ConfigStore
    brain: Brain                           # FOCAL, LangGraph, Agno, etc.
    toolbox: Toolbox                       # Agent's tool facade
    channel_bindings: dict[str, ChannelBinding]  # Available channels

    # Optional: Agent-specific executors
    llm_executor: LLMExecutor | None = None

    async def process_turn(self, fabric_ctx: FabricTurnContext) -> BrainResult:
        """
        Process a turn - this is what ACF calls.

        Agent wraps the fabric context and delegates to its brain.
        """
        turn_ctx = AgentTurnContext(
            fabric=fabric_ctx,
            agent_context=self,
        )
        return await self.brain.think(turn_ctx)
```

### 3.3 AgentTurnContext

Per-turn context that wraps ACF's FabricTurnContext:

```python
@dataclass
class AgentTurnContext:
    """
    Per-turn context passed to Brain.

    Wraps FabricTurnContext (ACF) with AgentContext (business).
    """
    fabric: FabricTurnContext    # ACF infrastructure
    agent_context: AgentContext  # Business configuration

    @property
    def toolbox(self) -> Toolbox:
        """Convenience: Access toolbox for tool execution."""
        return self.agent_context.toolbox

    @property
    def logical_turn(self) -> LogicalTurn:
        """Convenience: Access current turn."""
        return self.fabric.logical_turn

    async def has_pending_messages(self) -> bool:
        """Delegate to ACF."""
        return await self.fabric.has_pending_messages()

    async def emit_event(self, event: ACFEvent) -> None:
        """Delegate to ACF."""
        await self.fabric.emit_event(event)
```

### 3.4 AgentRuntime

Manages Agent lifecycle:

```python
class AgentRuntime:
    """
    Manages AgentContext lifecycle.

    - Creates on first request
    - Caches for reuse (warm agents)
    - Invalidates on config change
    """

    def __init__(
        self,
        config_store: ConfigStore,
        tool_gateway: ToolGateway,
        channel_gateway: ChannelGateway,
    ):
        self._config_store = config_store
        self._tool_gateway = tool_gateway
        self._channel_gateway = channel_gateway
        self._cache: dict[tuple[UUID, UUID], AgentContext] = {}
        self._cache_versions: dict[tuple[UUID, UUID], str] = {}

    async def get_or_create(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentContext:
        """
        Get cached AgentContext or create fresh one.

        Uses version-based invalidation to detect config changes.
        """
        key = (tenant_id, agent_id)

        # Check cache validity
        if key in self._cache:
            current_version = await self._config_store.get_agent_version(
                tenant_id, agent_id
            )
            if self._cache_versions.get(key) == current_version:
                return self._cache[key]

        # Build fresh AgentContext
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        tool_defs = await self._config_store.get_tool_definitions(tenant_id)
        tool_activations = await self._config_store.get_tool_activations(
            tenant_id, agent_id
        )

        context = AgentContext(
            agent=agent,
            brain=self._build_pipeline(agent),
            toolbox=self._build_toolbox(agent_id, tool_defs, tool_activations),
            channel_bindings=await self._load_channel_bindings(tenant_id, agent_id),
        )

        # Cache with version
        self._cache[key] = context
        self._cache_versions[key] = await self._config_store.get_agent_version(
            tenant_id, agent_id
        )

        return context

    async def invalidate(self, tenant_id: UUID, agent_id: UUID) -> None:
        """Invalidate cached agent (called on config change)."""
        key = (tenant_id, agent_id)
        self._cache.pop(key, None)
        self._cache_versions.pop(key, None)
```

### 3.5 Tasks Bypass ACF Entirely

**Key Principle**: Tasks ≠ Conversations. Tasks are scheduled work items, not conversational turns.

**Architecture**:
- Hatchet orchestrates **TWO separate workflow types**:
  1. **LogicalTurnWorkflow** (ACF-managed) - for conversations
  2. **TaskWorkflow** (Agenda-managed) - for scheduled tasks

**Why the separation**:
- Conversations need mutex, accumulation, supersede → ACF handles
- Tasks need scheduled execution, retries, idempotency → Agenda handles
- Tasks should NOT block on session mutex (customer isn't waiting)
- Tasks should NOT accumulate messages (there are no messages)

**Execution Flow**:

```
┌──────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER (Hatchet)                 │
│                                                                   │
│   ┌─────────────────────┐       ┌─────────────────────┐         │
│   │  LogicalTurnWorkflow │       │   TaskWorkflow       │         │
│   │  (ACF-managed)       │       │   (Agenda-managed)   │         │
│   │  - mutex            │       │   - no mutex         │         │
│   │  - accumulate       │       │   - no accumulate    │         │
│   │  - supersede        │       │   - direct execute   │         │
│   └─────────────────────┘       └─────────────────────┘         │
│            ↑                              ↑                       │
│   ChannelGateway.receive()      AgendaScheduler.execute_due()    │
└──────────────────────────────────────────────────────────────────┘
```

**TaskWorkflow Steps**:
```python
@hatchet.workflow(name="task_execution")
class TaskWorkflow:
    """Agenda-managed task execution (bypasses ACF)."""

    @hatchet.step()
    async def execute_task(self, ctx: Context) -> dict:
        """Execute scheduled task directly (no mutex, no ACF)."""
        task_id = ctx.workflow_input()["task_id"]
        task = await self._agenda_store.get_task(task_id)

        # Direct execution - no ACF layer
        agent_ctx = await self._agent_runtime.get_or_create(
            task.tenant_id, task.agent_id
        )

        # Toolbox execution without conversational context
        result = await agent_ctx.toolbox.execute_task(task)

        return {"result": result.model_dump()}
```

**Design Decision**: Tasks go through Agenda → Hatchet TaskWorkflow, **NOT** through ACF. This keeps ACF focused on conversation runtime.

---

## 4. Brain: The Thinking Unit

### 4.1 Brain Interface

```python
class Brain(ABC):
    """
    The brain interface - FOCAL, LangGraph, Agno all implement this.

    Brain is owned by Agent. ACF calls Agent, which uses its Brain internally.
    """

    name: str

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        """
        Process a logical turn and return results.

        Brain is free to:
        - Run any number of internal phases (e.g., FOCAL's 11-phase pipeline)
        - Call ctx.toolbox.execute() for tools
        - Check ctx.has_pending_messages() for supersede
        - Emit events via ctx.emit_event()
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> BrainCapabilities:
        """Declare what this brain can do."""
        ...


class BrainCapabilities(BaseModel):
    """What a brain can do - used by Agent for validation."""
    supports_streaming: bool = False
    supports_tools: bool = True
    supports_supersede: bool = True


class ResponseSegment(BaseModel):
    """
    A single segment of the agent's response.

    Responses are segmented to support:
    - Streaming (each segment can be sent independently)
    - Multi-modal responses (text vs structured actions)
    - Channel-specific formatting (adapter transforms segments)
    """

    text: str | None = None

    # For structured responses (buttons, cards, etc.)
    structured_content: dict | None = None

    # Hints for channel adapters
    content_type: Literal["text", "markdown", "html", "structured"] = "text"

    # For streaming: is this the final segment?
    is_final: bool = True


class BrainResult(BaseModel):
    """What Brain returns to Agent (and Agent returns to ACF)."""

    response_segments: list[ResponseSegment] = Field(default_factory=list)
    staged_mutations: dict = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)

    # Signals
    expects_more_input: bool = False

    # For handoffs
    handoff: HandoffRequest | None = None
```

### 4.2 Tool Execution in Brain

Brain executes tools via Toolbox during its internal processing:

```python
class FocalBrain(Brain):
    """FOCAL's 11-phase pipeline implementation."""

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        # ... internal phases P1-P6 ...

        # P7: Tool execution via Toolbox
        for tool in planned_tools:
            # Check supersede before irreversible tools
            if tool.is_irreversible and await ctx.has_pending_messages():
                return self._handle_supersede()

            # Execute via Toolbox (handles policy, idempotency, audit)
            result = await ctx.toolbox.execute(tool, ctx)

        # ... internal phases P8-P11 ...
```

Toolbox is the enforcement boundary - Brain trusts it to handle correctness.

### 4.3 ChannelPolicy: Single Source of Truth

**Problem**: Channel behavior is currently scattered across multiple components:
- ACF needs aggregation window, supersede mode
- ChannelAdapter needs typing indicators, message limits
- Brain may need response delays

**Solution**: `ChannelPolicy` as the canonical model, stored in ConfigStore.

```python
class ChannelPolicy(BaseModel):
    """
    Single source of truth for channel behavior.

    Loaded from ConfigStore → AgentContext.channel_policies: dict[str, ChannelPolicy]
    All components read from this shared source.
    """
    channel: str  # "whatsapp", "webchat", "email", "voice"

    # ACF behavior
    aggregation_window_ms: int = 3000
    supersede_default: SupersedeMode = SupersedeMode.QUEUE

    # ChannelAdapter capabilities
    supports_typing_indicator: bool = True
    supports_read_receipts: bool = True
    max_message_length: int | None = None
    supports_streaming: bool = False

    # Natural delay (UX feel)
    natural_response_delay_ms: int = 0  # Simulate human typing time

    # Rate limiting
    max_messages_per_minute: int | None = None
```

**Storage**: ConfigStore interface extension:
```python
class ConfigStore(Protocol):
    async def get_channel_policy(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
    ) -> ChannelPolicy:
        """
        Get channel policy for agent/channel combination.

        Falls back to platform defaults if not customized.
        """
        ...
```

**Loading into AgentContext**:
```python
@dataclass
class AgentContext:
    agent: Agent
    brain: Brain
    toolbox: Toolbox
    channel_bindings: dict[str, ChannelBinding]
    channel_policies: dict[str, ChannelPolicy]  # NEW: Loaded from ConfigStore
```

**Usage**:
- **ACF**: `policy = agent_ctx.channel_policies[channel]` → use `aggregation_window_ms`, `supersede_default`
- **ChannelAdapter**: `policy = agent_ctx.channel_policies[channel]` → use `max_message_length`, `supports_typing_indicator`
- **Brain**: `policy = agent_ctx.channel_policies[channel]` → use `natural_response_delay_ms`

**Benefits**:
- Single definition per agent/channel pair
- No inconsistency between ACF and adapter behavior
- Tenant-level overrides possible (e.g., enterprise customer wants longer aggregation window)
- Easy to add new channel-specific parameters

### 4.4 Framework Compatibility

**FOCAL**:
```python
class FocalBrain(Brain):
    name = "focal"

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        # Internal 11-phase pipeline:
        # P1-P6: Context extraction, retrieval, filtering
        # P7: Tool execution via ctx.toolbox.execute()
        # P8-P11: Generation, enforcement, persistence
        ...
```

**LangGraph**:
```python
class LangGraphBrain(Brain):
    name = "langgraph"

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        # Translate AgentTurnContext to graph state
        state = self._build_state(ctx)

        # Inject toolbox into graph's tool layer
        state["tool_executor"] = LangGraphToolAdapter(ctx.toolbox)

        # Run graph
        final_state = await self.graph.ainvoke(state)

        return self._to_brain_result(final_state)
```

**Agno**:
```python
class AgnoBrain(Brain):
    name = "agno"

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        result = await self._agno_workflow.execute(
            messages=ctx.logical_turn.messages,
            tool_executor=AgnoToolAdapter(ctx.toolbox),
        )
        return self._to_brain_result(result)
```

**Note**: All brains are conversational. For scheduled tasks, see §3.5 (TaskWorkflow bypasses brains entirely).

---

## 5. Toolbox: Agent's Tool Facade

### 5.1 Toolbox Interface

```python
class Toolbox:
    """
    Agent-level tool facade.

    - Resolves tools from ConfigStore definitions
    - Executes via ToolGateway
    - Records side effects via ACFEvents
    - Knows tool metadata (reversible, compensatable, etc.)
    """

    def __init__(
        self,
        agent_id: UUID,
        tool_definitions: dict[str, ToolDefinition],
        tool_activations: dict[str, ToolActivation],
        gateway: ToolGateway,
    ):
        self._agent_id = agent_id
        self._gateway = gateway

        # Build resolved tool map (only enabled tools)
        self._tools = {
            t.name: t for t in tool_definitions.values()
            if tool_activations.get(str(t.id), ToolActivation()).enabled
        }

    async def execute(
        self,
        tool: PlannedToolExecution,
        turn_context: AgentTurnContext,
    ) -> ToolResult:
        """
        Execute a single tool.

        1. Build ToolExecutionContext with turn_group_id from ACF
        2. Execute via ToolGateway
        3. Record side effect via ACFEvent
        4. Return result
        """
        defn = self._tools.get(tool.tool_name)
        if not defn:
            return ToolResult(
                status="error",
                error=f"Tool '{tool.tool_name}' not found or not enabled",
            )

        # Build execution context (bridges ACF turn_group_id to ToolGateway)
        exec_ctx = ToolExecutionContext(
            tenant_id=turn_context.agent_context.agent.tenant_id,
            agent_id=self._agent_id,
            turn_group_id=turn_context.logical_turn.turn_group_id,
            tool_name=tool.tool_name,
            args=tool.args,
            gateway=defn.gateway,
            gateway_config=defn.gateway_config,
        )

        # Execute via gateway
        result = await self._gateway.execute(exec_ctx)

        # Record side effect via ACFEvent
        effect = SideEffectRecord(
            tool_name=tool.tool_name,
            policy=defn.side_effect_policy,
            executed_at=datetime.utcnow(),
            args=tool.args,
            result=result.data if result.success else None,
            status="executed" if result.success else "failed",
            idempotency_key=exec_ctx.build_idempotency_key(
                self._extract_business_key(tool.args)
            ),
        )

        await turn_context.emit_event(ACFEvent(
            type=ACFEventType.TOOL_SIDE_EFFECT_COMPLETED,
            turn_id=turn_context.logical_turn.id,
            session_key=turn_context.fabric.session_key,
            payload=effect.model_dump(),
        ))

        return result

    async def execute_batch(
        self,
        tools: list[PlannedToolExecution],
        turn_context: AgentTurnContext,
    ) -> list[ToolResult]:
        """Execute multiple tools sequentially."""
        return [await self.execute(t, turn_context) for t in tools]

    def get_metadata(self, tool_name: str) -> ToolMetadata | None:
        """Get metadata for a tool (for supersede decisions)."""
        defn = self._tools.get(tool_name)
        if not defn:
            return None
        return ToolMetadata(
            name=defn.name,
            side_effect_policy=defn.side_effect_policy,
            requires_confirmation=defn.requires_confirmation,
            compensation_tool=defn.compensation_tool_id,
        )

    def is_available(self, tool_name: str) -> bool:
        """Check if tool is available for this agent."""
        return tool_name in self._tools
```

### 5.2 ToolExecutionContext

Bridges ACF (turn_group_id) to ToolGateway (idempotency):

```python
@dataclass
class ToolExecutionContext:
    """Context passed to ToolGateway for each execution."""

    tenant_id: UUID
    agent_id: UUID
    turn_group_id: UUID  # From LogicalTurn (ACF-provided)
    tool_name: str
    args: dict
    gateway: str         # "composio", "http", "internal"
    gateway_config: dict

    def build_idempotency_key(self, business_key: str) -> str:
        """
        Build idempotency key scoped to conversation attempt.

        turn_group_id ensures:
        - Supersede chain shares key -> one execution
        - QUEUE creates new key -> allows re-execution in new context
        """
        return f"{self.tool_name}:{business_key}:turn_group:{self.turn_group_id}"
```

### 5.3 ToolGateway

Infrastructure-level tool execution:

```python
class ToolGateway(Protocol):
    """
    Infrastructure-level tool execution.

    - Manages provider adapters (Composio, HTTP, internal)
    - Handles operation idempotency
    - Does NOT know tool semantics (that's Toolbox)
    """

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        """Execute tool via appropriate provider."""
        ...

class ToolGatewayImpl(ToolGateway):
    def __init__(
        self,
        providers: dict[str, ToolProvider],  # "composio", "http", etc.
        idem_cache: IdempotencyCache,
    ):
        self._providers = providers
        self._idem_cache = idem_cache

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        # Check idempotency
        idem_key = ctx.build_idempotency_key(
            self._extract_business_key(ctx.args)
        )
        if cached := await self._idem_cache.get(idem_key):
            return cached

        # Get provider
        provider = self._providers.get(ctx.gateway)
        if not provider:
            return ToolResult(
                status="error",
                error=f"Unknown gateway: {ctx.gateway}",
            )

        # Execute
        result = await provider.call(ctx.tool_name, ctx.args, ctx.gateway_config)

        # Cache result (24hr TTL for idempotency)
        if result.success:
            await self._idem_cache.set(idem_key, result, ttl=86400)

        return result
```

---

## 6. Channels: Protocol Adapters

### 6.1 ChannelGateway

Shared infrastructure for all channels:

```python
class ChannelGateway:
    """
    Shared channel infrastructure.

    - Routes inbound messages to TurnGateway
    - Sends outbound messages via appropriate adapter
    - Does NOT know agent logic
    """

    def __init__(
        self,
        adapters: dict[str, ChannelAdapter],
        turn_gateway: TurnGateway,
    ):
        self._adapters = adapters
        self._turn_gateway = turn_gateway

    async def receive(self, raw_payload: dict, channel: str) -> None:
        """Receive inbound message from channel webhook."""
        adapter = self._adapters.get(channel)
        if not adapter:
            raise ValueError(f"Unknown channel: {channel}")

        # Normalize to RawMessage
        message = await adapter.normalize_inbound(raw_payload)

        # Forward to ACF
        await self._turn_gateway.receive_message(message)

    async def send(
        self,
        channel: str,
        adapter_key: str,
        message: OutboundMessage,
    ) -> None:
        """Send outbound message via channel adapter."""
        adapter = self._adapters.get(adapter_key)
        await adapter.send(message)
```

### 6.2 ChannelAdapter

Protocol-specific implementations:

```python
class ChannelAdapter(Protocol):
    """Protocol-specific channel implementation."""

    async def normalize_inbound(self, raw_payload: dict) -> RawMessage:
        """Convert channel-specific format to RawMessage."""
        ...

    async def send(self, message: OutboundMessage) -> None:
        """Send message in channel-specific format."""
        ...
```

**Examples**:
- `AGUIWebchatAdapter` - AG-UI protocol for rich webchat
- `SimpleWebchatAdapter` - Plain WebSocket for simple webchat
- `TwilioWhatsAppAdapter` - Twilio API for WhatsApp
- `SMTPEmailAdapter` - SMTP for email

### 6.3 AG-UI: Just Another Adapter

**Key principle**: AG-UI is NOT in ACF. It's an implementation detail of one webchat adapter.

```python
class AGUIWebchatAdapter(ChannelAdapter):
    """AG-UI protocol adapter for webchat."""

    async def normalize_inbound(self, raw_payload: dict) -> RawMessage:
        # Parse AG-UI wire format
        ...

    async def send(self, message: OutboundMessage) -> None:
        # Convert to AG-UI events
        # Map ACFEvents to AG-UI event types
        ...
```

ACF doesn't know AG-UI exists. It just sees `channel="webchat"`.

---

## 7. ACFEvents: Universal Event Model

### 7.1 Event Types

```python
class ACFEventType(str, Enum):
    # ACF lifecycle events
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    TURN_SUPERSEDED = "turn_superseded"
    MESSAGE_ABSORBED = "message_absorbed"

    # Inbound/outbound (ACF routes)
    INBOUND_MESSAGE = "inbound_message"
    OUTBOUND_MESSAGE = "outbound_message"

    # Brain status (Brain emits)
    STATUS_UPDATE = "status_update"
    PIPELINE_ERROR = "pipeline_error"

    # Tool events (Toolbox emits)
    TOOL_SIDE_EFFECT_STARTED = "tool_side_effect_started"
    TOOL_SIDE_EFFECT_COMPLETED = "tool_side_effect_completed"
    TOOL_SIDE_EFFECT_FAILED = "tool_side_effect_failed"
```

### 7.2 Event Model

```python
class ACFEvent(BaseModel):
    """Universal event model for the platform."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Routing keys
    tenant_id: UUID
    agent_id: UUID
    session_key: str
    logical_turn_id: UUID | None = None  # Canonical ID, not turn_id
    channel: str | None = None

    # Event data
    type: ACFEventType
    payload: dict[str, Any]
```

### 7.3 Event Flow

```
Brain/Toolbox → emit_event() → ACF FabricTurnContext
                                        │
                                        ▼
                                  ACF EventRouter
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
              TurnManager         AuditStore         Live UI Listeners
              (side effects       (persist)          (AG-UI, dashboards)
               in LogicalTurn)
```

**Important**: Only ONE write path to `LogicalTurn.side_effects`:
- Toolbox emits `TOOL_SIDE_EFFECT_*` events
- ACF EventRouter listens and updates TurnManager
- No direct Toolbox → TurnManager calls

---

## 8. Execution Model

### 8.1 Single Execution Style

Agents use a **single execution style**: Brain calls `toolbox.execute()` inline.

```
acquire_mutex → accumulate → run_agent → commit_and_respond
```

**Inside run_agent**:
- ACF calls `agent.process_turn(fabric_ctx)`
- Agent wraps context and calls `brain.think()`
- Brain runs its internal phases (e.g., FOCAL's 11-phase pipeline)
- Tools execute via `ctx.toolbox.execute()`
- Toolbox handles policy enforcement, idempotency, and audit events

```python
@hatchet.step()
async def run_agent(self, ctx: Context) -> dict:
    # Deserialize DATA from workflow input
    turn_data = ctx.workflow_input()
    logical_turn = LogicalTurn.from_dict(turn_data["logical_turn"])
    session_key = turn_data["session_key"]

    # Rebuild FabricTurnContext with LIVE callbacks
    fabric_ctx = FabricTurnContext(
        logical_turn=logical_turn,
        session_key=session_key,
        channel=turn_data["channel"],
        has_pending_messages=lambda: self._check_pending(session_key),
        emit_event=lambda e: self._route_event(e),
    )

    # Get agent and call process_turn
    agent_ctx = await self._agent_runtime.get_or_create(
        turn_data["tenant_id"], turn_data["agent_id"]
    )

    # ACF calls Agent, Agent uses Brain internally
    result = await agent_ctx.process_turn(fabric_ctx)

    return {"result": result.model_dump()}
```

### 8.2 Why Single Style (Not Multiple Modes)

Previous designs included Mode 0/1/2 for different trust levels. This complexity is **not needed** when:

1. **Your team controls all brains** - No untrusted third-party brains
2. **Toolbox is the enforcement boundary** - Policy, idempotency, confirmation handled there
3. **ASA validates scenarios** - Design-time checks ensure conformance

**Toolbox as enforcement** means:
- Brain can't bypass policy checks (Toolbox enforces)
- Brain can't skip audit events (Toolbox emits them)
- Brain can't execute without idempotency (ToolGateway handles it)

### 8.3 Brain Conformance Requirements

All brains must satisfy these invariants:

| Invariant | Description | Enforcement |
|-----------|-------------|-------------|
| **Tool calls through Toolbox** | Never call vendor SDK directly | ASA lints, code review |
| **Confirmation binding** | If `requires_confirmation`, enter confirm step | Scenario state |
| **Idempotency keys** | Side-effect tools have stable business key | Toolbox extracts/hashes |
| **Supersede awareness** | Check `has_pending_messages()` before irreversible | Brain responsibility |

---

## 9. Multi-Agent Handoffs

> **Status**: Basic mechanism defined, implementation deferred.
> **Principle**: Don't block this capability in architectural decisions.
> **Future planning**: See [multi_agent_handoffs.md](../analysis/multi_agent_handoffs.md) for open questions and design considerations.

### 9.1 Handoff as Staged Mutation

Brain decides to hand off:

```python
class FocalBrain(Brain):
    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        if self._should_handoff(ctx, target_agent_id):
            return BrainResult(
                response_segments=[
                    ResponseSegment(text="Transferring you to our specialist...")
                ],
                handoff=HandoffRequest(
                    target_agent_id=target_agent_id,
                    context_summary=self._summarize_context(ctx),
                ),
            )
```

### 9.2 ACF Handles Transfer

```python
@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    result = BrainResult(**ctx.step_output("run_agent")["result"])

    if result.handoff:
        # Transfer session to new agent
        await self._session_store.transfer_session(
            from_session=old_session_key,
            to_agent_id=result.handoff.target_agent_id,
            context_summary=result.handoff.context_summary,
        )
        # Next message will route to new agent

    # Send response and release mutex
    ...
```

### 9.3 Session Transfer

```python
class SessionStore:
    async def transfer_session(
        self,
        from_session: str,
        to_agent_id: UUID,
        context_summary: dict,
    ) -> str:
        """
        Transfer session to new agent.

        - Creates new session_key with new agent_id
        - Copies relevant state
        - Stores context_summary for new agent
        """
        old_session = await self.get(from_session)

        new_session_key = build_session_key(
            tenant_id=old_session.tenant_id,
            agent_id=to_agent_id,
            customer_id=old_session.customer_id,
            channel=old_session.channel,
        )

        new_session = Session(
            session_key=new_session_key,
            tenant_id=old_session.tenant_id,
            agent_id=to_agent_id,
            customer_id=old_session.customer_id,
            channel=old_session.channel,
            transfer_context=context_summary,
            transferred_from=from_session,
        )

        await self.save(new_session)
        return new_session_key
```

---

## 10. Data Flow Summary

```
1. INGRESS
   Channel webhook → ChannelGateway.receive()
                   → ChannelAdapter.normalize_inbound() → RawMessage
                   → TurnGateway.receive_message()

2. ACF ORCHESTRATION
   TurnGateway → Hatchet LogicalTurnWorkflow
   Step 1: acquire_mutex (ACF)
   Step 2: accumulate (ACF) → LogicalTurn
   Step 3: run_agent (ACF calls Agent)

3. AGENT EXECUTION
   AgentRuntime.get_or_create() → AgentContext
   ACF calls agent_ctx.process_turn(fabric_ctx)

   Agent.process_turn():
     - Wraps fabric_ctx into AgentTurnContext
     - Calls brain.think(agent_turn_ctx)

   Brain.think() (e.g., FocalBrain's 11-phase pipeline):
     P1-P6: Context, retrieval, filtering
     P7: Tools via ctx.toolbox.execute()
         → Toolbox → ToolGateway.execute(ToolExecutionContext)
         → ToolGateway → Provider (Composio, HTTP)
         ← ToolResult
         → emit ACFEvent (TOOL_SIDE_EFFECT_COMPLETED)
     P8-P11: Generation, enforcement

   Returns BrainResult to Agent, Agent returns to ACF

4. COMMIT
   Step 4: commit_and_respond (ACF)
   → Persist session state, audit record
   → ChannelGateway.send(response)
   → ChannelAdapter.format_outbound()
   → User sees response
```

---

## 11. Related Documents

| Document | Purpose |
|----------|---------|
| [ACF_JUSTIFICATION.md](ACF_JUSTIFICATION.md) | Why ACF exists - problems solved, business case |
| [ACF_SPEC.md](ACF_SPEC.md) | Detailed ACF mechanics (mutex, turns, supersede) |
| [AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md) | Agent lifecycle management |
| [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) | Tool execution layer |
| [topics/01-logical-turn.md](topics/01-logical-turn.md) | LogicalTurn model |
| [topics/02-session-mutex.md](topics/02-session-mutex.md) | Session mutex |
| [topics/04-side-effect-policy.md](topics/04-side-effect-policy.md) | Side effect classification |
| [topics/06-hatchet-integration.md](topics/06-hatchet-integration.md) | Hatchet workflow |
| [../analysis/ag_ui_considerations.md](../analysis/ag_ui_considerations.md) | AG-UI integration (channel adapter concern, NOT ACF) |
| [../analysis/multi_agent_handoffs.md](../analysis/multi_agent_handoffs.md) | Multi-agent handoffs (deferred, don't block) |

---

## 12. Key Principles Summary

1. **ACF is infrastructure**: Mutex, turns, workflow. Zero business logic.

2. **Agent is business entity**: Brain + Toolbox + Channels. Owns all decisions.

3. **Toolbox is the enforcement boundary**: Policy, idempotency, confirmation, audit. Brain calls it.

4. **Supersede = Facts + Decisions**: ACF provides facts, Brain decides actions.

5. **Events are the glue**: ACFEvents flow from Brain/Toolbox → ACF → everywhere.

6. **Single execution style**: Brain executes tools inline via Toolbox. No mode complexity.

7. **Channels are adapters**: AG-UI is just one webchat adapter, not ACF concern.

8. **Handoffs are mutations**: Brain proposes, ACF executes session transfer.

9. **Brain conformance via Toolbox + ASA**: Not runtime mode enforcement.
