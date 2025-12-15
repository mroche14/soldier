# Agent Runtime Specification

> **Status**: AUTHORITATIVE SPECIFICATION
> **Version**: 1.0
> **Date**: 2025-12-11
> **Parent**: [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md)

---

## Overview

The **Agent Runtime** layer manages the lifecycle of Agent instances. It sits above ACF and provides the business entity abstraction that ACF orchestrates.

**Key Components**:
- `Agent` - Configuration model (stored in ConfigStore)
- `AgentContext` - Runtime instance (Brain + Toolbox + Channels)
- `AgentRuntime` - Lifecycle manager (caching, invalidation)
- `AgentTurnContext` - Per-turn context wrapper

---

## 1. Agent Model (Configuration)

The `Agent` model represents a configured conversational AI instance for a tenant.

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    """LLM and behavior settings for an agent."""

    model: str = "openrouter/anthropic/claude-3-5-sonnet"
    temperature: float = 0.7
    max_tokens: int = 4096


class Agent(BaseModel):
    """
    Agent configuration model (stored in ConfigStore).

    An Agent is a configured conversational AI instance for a tenant.
    It defines WHAT the agent is; AgentContext defines HOW it runs.
    """

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None

    # System prompt for LLM
    system_prompt: str

    # LLM and behavior settings
    settings: AgentSettings = Field(default_factory=AgentSettings)

    # Brain type (determines which Brain to use)
    pipeline_type: str = "focal"  # "focal", "langgraph", "agno"

    # Brain-specific configuration (scenarios/rules for FOCAL, graph config for LangGraph, etc.)
    pipeline_config: dict = Field(default_factory=dict)

    # Version for cache invalidation
    version: str = "1"

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 2. AgentContext (Runtime Instance)

`AgentContext` is the runtime representation of a configured Agent. It holds the instantiated components needed to process turns.

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass
class AgentContext:
    """
    Runtime instance of a configured Agent.

    Created by AgentRuntime, cached for reuse, invalidated on config change.
    Contains all components needed to process a turn.
    """

    # Configuration (from ConfigStore)
    agent: Agent

    # Brain (FOCAL, LangGraph, Agno)
    brain: Brain

    # Tool execution facade
    toolbox: Toolbox

    # Available channels for this agent
    channel_bindings: dict[str, ChannelBinding]

    # Channel policies (single source of truth for channel behavior)
    # Loaded from ConfigStore, used by ACF, Agent, and ChannelGateway
    channel_policies: dict[str, ChannelPolicy]

    # Optional: Agent-specific LLM executor (if different from default)
    llm_executor: LLMExecutor | None = None

    @property
    def agent_id(self) -> UUID:
        return self.agent.id

    @property
    def tenant_id(self) -> UUID:
        return self.agent.tenant_id
```

### 2.1 ChannelBinding

Defines how an agent is accessible on a specific channel:

```python
class ChannelBinding(BaseModel):
    """
    Agent's configuration for a specific channel.

    Defines which adapter to use. Channel behavior is defined by
    ChannelPolicy (stored separately in AgentContext.channel_policies).
    """

    channel: str              # "webchat", "whatsapp", "email"
    adapter_key: str          # "webchat_agui", "whatsapp_twilio", etc.
    enabled: bool = True

    # AG-UI specific (only for webchat_agui adapter)
    agui_config: dict | None = None
```

### 2.2 ChannelPolicy (Single Source of Truth)

ChannelPolicy is the **canonical model** for channel behavior, loaded into `AgentContext.channel_policies`:

```python
from enum import Enum

class SupersedeMode(str, Enum):
    """How to handle new messages during turn processing."""
    QUEUE = "queue"      # Queue new messages, finish current turn
    INTERRUPT = "interrupt"  # Cancel current turn, start new one
    IGNORE = "ignore"    # Discard new messages until turn completes

class ChannelPolicy(BaseModel):
    """
    Single source of truth for channel behavior.

    Loaded from ConfigStore into AgentContext.channel_policies.
    Used by: ACF (accumulation), Agent (brain), ChannelGateway (formatting).
    """
    channel: str  # "whatsapp", "webchat", "email", "voice"

    # === ACF Accumulation Behavior ===
    aggregation_window_ms: int = 3000
    """How long to wait for message bursts before processing."""

    supersede_default: SupersedeMode = SupersedeMode.QUEUE
    """Default behavior when new message arrives during turn."""

    # === ChannelAdapter Capabilities ===
    supports_typing_indicator: bool = True
    """Whether channel supports typing indicators."""

    supports_read_receipts: bool = True
    """Whether channel supports read receipts."""

    max_message_length: int | None = None
    """Maximum characters per message (None = unlimited)."""

    supports_markdown: bool = True
    """Whether channel renders markdown formatting."""

    supports_rich_media: bool = True
    """Whether channel supports images, buttons, etc."""

    # === Agent/Brain Behavior ===
    natural_response_delay_ms: int = 0
    """Delay before sending response (to feel more natural)."""

    # === Rate Limiting ===
    max_messages_per_minute: int = 60
    """Rate limit for outbound messages."""
```

**Key Principle**: Everyone (ACF, Agent, ChannelAdapter) reads from the same ChannelPolicy object loaded into AgentContext. No duplicate policy definitions.

---

## 3. AgentTurnContext (Per-Turn Context)

`AgentTurnContext` wraps ACF's `FabricTurnContext` with the Agent's runtime components. This is what gets passed to the Brain.

```python
@dataclass
class AgentTurnContext:
    """
    Per-turn context passed to Brain.

    Wraps FabricTurnContext (ACF infrastructure) with AgentContext (business).
    Brain uses this to access everything it needs for turn processing.
    """

    # ACF infrastructure context
    fabric: FabricTurnContext

    # Agent runtime instance
    agent_context: AgentContext

    # Convenience properties for common access patterns

    @property
    def toolbox(self) -> Toolbox:
        """Access toolbox for tool execution."""
        return self.agent_context.toolbox

    @property
    def logical_turn(self) -> LogicalTurn:
        """Access current turn from ACF."""
        return self.fabric.logical_turn

    @property
    def session_key(self) -> str:
        """Access session key from ACF."""
        return self.fabric.session_key

    @property
    def channel(self) -> str:
        """Access channel from ACF."""
        return self.fabric.channel

    @property
    def agent(self) -> Agent:
        """Access agent configuration."""
        return self.agent_context.agent

    # Delegate ACF signals

    async def has_pending_messages(self) -> bool:
        """
        Query ACF: Has a new message arrived during this turn?

        Brain uses this to decide supersede behavior before irreversible tools.
        """
        return await self.fabric.has_pending_messages()

    async def emit_event(self, event: ACFEvent) -> None:
        """
        Emit event to ACF for routing/persistence.

        Brain/Toolbox emit events; ACF routes to listeners.
        """
        await self.fabric.emit_event(event)

    # Convenience for tools

    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        **kwargs,
    ) -> ToolResult:
        """
        Convenience: Execute a tool via toolbox.

        Equivalent to: self.toolbox.execute(PlannedToolExecution(...), self)
        """
        planned = PlannedToolExecution(tool_name=tool_name, args=args, **kwargs)
        return await self.toolbox.execute(planned, self)
```

---

## 4. AgentRuntime (Lifecycle Manager)

`AgentRuntime` manages the lifecycle of `AgentContext` instances:
- Creates on first request
- Caches for performance
- Invalidates on config change

```python
from typing import Protocol
import asyncio


class AgentRuntime:
    """
    Manages AgentContext lifecycle.

    Responsibilities:
    - Create AgentContext from ConfigStore data
    - Cache warm agents for reuse
    - Invalidate on config changes
    - Prevent duplicate creation (singleflight)
    """

    def __init__(
        self,
        config_store: ConfigStore,
        tool_gateway: ToolGateway,
        pipeline_factory: PipelineFactory,
        max_cache_size: int = 1000,
    ):
        self._config_store = config_store
        self._tool_gateway = tool_gateway
        self._pipeline_factory = pipeline_factory
        self._max_cache_size = max_cache_size

        # Cache: (tenant_id, agent_id) -> AgentContext
        self._cache: dict[tuple[UUID, UUID], AgentContext] = {}

        # Version tracking for invalidation
        self._cache_versions: dict[tuple[UUID, UUID], str] = {}

        # Singleflight: prevent duplicate creation
        self._creation_locks: dict[tuple[UUID, UUID], asyncio.Lock] = {}

    async def get_or_create(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentContext:
        """
        Get cached AgentContext or create fresh one.

        Thread-safe with singleflight to prevent duplicate creation.
        Uses version-based invalidation to detect config changes.
        """
        key = (tenant_id, agent_id)

        # Fast path: valid cache hit
        if key in self._cache:
            current_version = await self._config_store.get_agent_version(
                tenant_id, agent_id
            )
            if self._cache_versions.get(key) == current_version:
                return self._cache[key]

        # Slow path: need to create (with singleflight)
        if key not in self._creation_locks:
            self._creation_locks[key] = asyncio.Lock()

        async with self._creation_locks[key]:
            # Double-check after acquiring lock
            if key in self._cache:
                current_version = await self._config_store.get_agent_version(
                    tenant_id, agent_id
                )
                if self._cache_versions.get(key) == current_version:
                    return self._cache[key]

            # Build fresh AgentContext
            context = await self._build_agent_context(tenant_id, agent_id)

            # Cache with version (respect max size)
            if len(self._cache) >= self._max_cache_size:
                self._evict_oldest()

            self._cache[key] = context
            self._cache_versions[key] = context.agent.version

            return context

    async def _build_agent_context(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentContext:
        """Build fresh AgentContext from ConfigStore data."""

        # Load agent configuration
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if not agent:
            raise AgentNotFoundError(tenant_id, agent_id)

        # Load tool definitions and activations
        tool_defs = await self._config_store.get_tool_definitions(tenant_id)
        tool_activations = await self._config_store.get_tool_activations(
            tenant_id, agent_id
        )

        # Build toolbox
        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_defs,
            tool_activations=tool_activations,
            gateway=self._tool_gateway,
        )

        # Build brain based on type
        brain = self._pipeline_factory.create(
            pipeline_type=agent.pipeline_type,
            agent=agent,
        )

        # Load channel bindings
        channel_bindings = await self._load_channel_bindings(tenant_id, agent_id)

        # Load channel policies (single source of truth)
        channel_policies = await self._load_channel_policies(tenant_id, agent_id)

        return AgentContext(
            agent=agent,
            brain=brain,
            toolbox=toolbox,
            channel_bindings=channel_bindings,
            channel_policies=channel_policies,
        )

    async def _load_channel_bindings(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, ChannelBinding]:
        """Load channel bindings for agent from ConfigStore."""
        bindings = await self._config_store.get_channel_bindings(tenant_id, agent_id)
        return {b.channel: b for b in bindings if b.enabled}

    async def _load_channel_policies(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, ChannelPolicy]:
        """
        Load channel policies for agent from ConfigStore.

        These policies are the single source of truth for channel behavior,
        used by ACF (accumulation), Agent (brain), and ChannelGateway (formatting).
        """
        policies = await self._config_store.get_channel_policies(tenant_id, agent_id)
        return {p.channel: p for p in policies}

    async def invalidate(self, tenant_id: UUID, agent_id: UUID) -> None:
        """
        Invalidate cached agent.

        Called when agent config changes (webhook from admin API).
        """
        key = (tenant_id, agent_id)
        self._cache.pop(key, None)
        self._cache_versions.pop(key, None)

    async def invalidate_tenant(self, tenant_id: UUID) -> None:
        """Invalidate all agents for a tenant."""
        keys_to_remove = [k for k in self._cache if k[0] == tenant_id]
        for key in keys_to_remove:
            self._cache.pop(key, None)
            self._cache_versions.pop(key, None)

    def _evict_oldest(self) -> None:
        """Evict oldest entry when cache is full (simple LRU)."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
            self._cache_versions.pop(oldest_key, None)
```

---

## 5. PipelineFactory

Creates Brain instances based on agent configuration:

```python
class PipelineFactory:
    """
    Factory for creating Brain instances.

    Supports: FOCAL, LangGraph, Agno, custom brains.
    """

    def __init__(
        self,
        focal_factory: Callable[[Agent], Brain] | None = None,
        langgraph_factory: Callable[[Agent], Brain] | None = None,
        agno_factory: Callable[[Agent], Brain] | None = None,
    ):
        self._factories = {
            "focal": focal_factory,
            "langgraph": langgraph_factory,
            "agno": agno_factory,
        }

    def create(
        self,
        pipeline_type: str,
        agent: Agent,
    ) -> Brain:
        """Create brain based on type."""
        factory = self._factories.get(pipeline_type)
        if not factory:
            raise ValueError(f"Unknown brain type: {pipeline_type}")
        return factory(agent)

    def register(
        self,
        pipeline_type: str,
        factory: Callable[[Agent], Brain],
    ) -> None:
        """Register custom brain factory."""
        self._factories[pipeline_type] = factory
```

---

## 6. Integration with ACF

### 6.1 Hatchet Workflow Integration

The Hatchet workflow uses AgentRuntime to get AgentContext:

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    """ACF workflow - uses AgentRuntime for Agent execution."""

    def __init__(self, agent_runtime: AgentRuntime):
        self._agent_runtime = agent_runtime

    @hatchet.step()
    async def run_agent(self, ctx: Context) -> dict:
        """Run Agent's Brain."""
        tenant_id = UUID(ctx.workflow_input()["tenant_id"])
        agent_id = UUID(ctx.workflow_input()["agent_id"])

        # Get AgentContext (cached or fresh)
        agent_ctx = await self._agent_runtime.get_or_create(tenant_id, agent_id)

        # Build FabricTurnContext (ACF provides this)
        fabric_ctx = self._build_fabric_context(ctx)

        # Build AgentTurnContext (wraps both)
        turn_ctx = AgentTurnContext(
            fabric=fabric_ctx,
            agent_context=agent_ctx,
        )

        # Run Brain
        result = await agent_ctx.brain.think(turn_ctx)

        return {"result": result.model_dump()}
```

### 6.2 Config Change Webhook

When agent config changes, invalidate cache:

```python
@router.post("/webhooks/config-change")
async def handle_config_change(
    payload: ConfigChangePayload,
    agent_runtime: AgentRuntime = Depends(get_agent_runtime),
):
    """Handle config change webhook from admin API."""
    if payload.entity_type == "agent":
        await agent_runtime.invalidate(payload.tenant_id, payload.entity_id)
    elif payload.entity_type == "tool_definition":
        # Tools are tenant-wide, invalidate all agents
        await agent_runtime.invalidate_tenant(payload.tenant_id)
```

---

## 7. Brain Protocol

### 7.1 Base Protocol

```python
class Brain(Protocol):
    """
    The brain interface.

    FOCAL, LangGraph, Agno all implement this.
    ACF doesn't care which implementation; it just calls think().
    """

    name: str

    async def think(self, ctx: AgentTurnContext) -> BrainResult:
        """
        Process a logical turn and return results.

        Brain is free to:
        - Run any number of phases
        - Call ctx.toolbox.execute() for tools
        - Check ctx.has_pending_messages() for supersede
        - Emit events via ctx.emit_event()
        """
        ...
```

### 7.2 Result Models

```python
class BrainResult(BaseModel):
    """Result from Brain.run()."""

    # Response to send to user
    response_segments: list[dict]

    # State mutations to commit atomically
    staged_mutations: dict = Field(default_factory=dict)

    # Artifacts for potential reuse
    artifacts: list[Artifact] = Field(default_factory=list)

    # Signals
    expects_more_input: bool = False

    # Handoff request (optional)
    handoff: HandoffRequest | None = None


class HandoffRequest(BaseModel):
    """Request to transfer session to another agent."""

    target_agent_id: UUID
    context_summary: dict
    reason: str | None = None
```

---

## 8. Error Handling

```python
class AgentNotFoundError(Exception):
    """Agent not found in ConfigStore."""

    def __init__(self, tenant_id: UUID, agent_id: UUID):
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found for tenant {tenant_id}")


class AgentDisabledError(Exception):
    """Agent is disabled."""

    def __init__(self, agent_id: UUID):
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} is disabled")


class PipelineTypeNotFoundError(Exception):
    """Unknown brain type."""

    def __init__(self, pipeline_type: str):
        self.pipeline_type = pipeline_type
        super().__init__(f"Unknown brain type: {pipeline_type}")
```

---

## 9. Configuration

```toml
[agent_runtime]
# Maximum number of AgentContexts to cache
max_cache_size = 1000

# Cache TTL (seconds) - backup to version-based invalidation
cache_ttl_seconds = 3600
```

---

## 10. Observability

### 10.1 Metrics

```python
# AgentContext cache metrics
agent_cache_hits = Counter(
    "agent_runtime_cache_hits_total",
    "Number of cache hits",
    ["tenant_id"],
)

agent_cache_misses = Counter(
    "agent_runtime_cache_misses_total",
    "Number of cache misses",
    ["tenant_id"],
)

agent_context_build_duration = Histogram(
    "agent_runtime_build_duration_seconds",
    "Time to build AgentContext",
    ["tenant_id", "pipeline_type"],
)

# Brain execution metrics
pipeline_execution_duration = Histogram(
    "pipeline_execution_duration_seconds",
    "Brain execution duration",
    ["tenant_id", "agent_id", "pipeline_type"],
)
```

### 10.2 Logging

```python
logger.info(
    "agent_context_created",
    tenant_id=tenant_id,
    agent_id=agent_id,
    pipeline_type=agent.pipeline_type,
)

logger.info(
    "agent_context_invalidated",
    tenant_id=tenant_id,
    agent_id=agent_id,
    reason="config_change",
)
```

---

## 11. Testing

### 11.1 Unit Tests

```python
@pytest.fixture
def mock_config_store():
    return MockConfigStore()


@pytest.fixture
def agent_runtime(mock_config_store):
    return AgentRuntime(
        config_store=mock_config_store,
        tool_gateway=MockToolGateway(),
        pipeline_factory=MockPipelineFactory(),
    )


async def test_get_or_create_caches_agent(agent_runtime, mock_config_store):
    """Test that AgentContext is cached."""
    tenant_id = uuid4()
    agent_id = uuid4()

    # First call creates
    ctx1 = await agent_runtime.get_or_create(tenant_id, agent_id)

    # Second call returns cached
    ctx2 = await agent_runtime.get_or_create(tenant_id, agent_id)

    assert ctx1 is ctx2
    assert mock_config_store.get_agent_call_count == 1


async def test_invalidate_clears_cache(agent_runtime, mock_config_store):
    """Test that invalidate clears cache."""
    tenant_id = uuid4()
    agent_id = uuid4()

    # Create and cache
    ctx1 = await agent_runtime.get_or_create(tenant_id, agent_id)

    # Invalidate
    await agent_runtime.invalidate(tenant_id, agent_id)

    # Next call creates fresh
    ctx2 = await agent_runtime.get_or_create(tenant_id, agent_id)

    assert ctx1 is not ctx2
    assert mock_config_store.get_agent_call_count == 2


async def test_version_change_invalidates(agent_runtime, mock_config_store):
    """Test that version change triggers re-creation."""
    tenant_id = uuid4()
    agent_id = uuid4()

    # Create with version 1
    mock_config_store.set_agent_version(tenant_id, agent_id, "1")
    ctx1 = await agent_runtime.get_or_create(tenant_id, agent_id)

    # Change version
    mock_config_store.set_agent_version(tenant_id, agent_id, "2")

    # Next call creates fresh
    ctx2 = await agent_runtime.get_or_create(tenant_id, agent_id)

    assert ctx1 is not ctx2
```

---

## 12. Related Documents

- [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md) - Overall architecture
- [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) - Toolbox specification
- [ACF_SPEC.md](ACF_SPEC.md) - ACF mechanics
- [topics/06-hatchet-integration.md](topics/06-hatchet-integration.md) - Hatchet workflow
