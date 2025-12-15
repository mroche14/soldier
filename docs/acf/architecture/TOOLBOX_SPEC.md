# Toolbox Specification

> **Status**: AUTHORITATIVE SPECIFICATION
> **Version**: 1.0
> **Date**: 2025-12-11
> **Parent**: [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md)

---

## Overview

The **Toolbox** layer handles tool execution for Agents. It bridges the business layer (Agent/Brain) with the infrastructure layer (ToolGateway/Providers).

**Key Components**:
- `Toolbox` - Agent-level facade (knows tool semantics)
- `ToolGateway` - Infrastructure-level execution (knows providers)
- `ToolExecutionContext` - Bridges ACF turn_group_id to tool idempotency
- `ToolDefinition` / `ToolActivation` - Configuration in ConfigStore

**Key Principle**: Toolbox owns tool semantics (reversible, compensatable). ToolGateway owns execution mechanics (providers, idempotency).

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DISCOVERY LAYER (MCP)                                │
│                                                                          │
│  MCP Server (Read-only)                                                 │
│  - focal://tools/tenant/{id}/available                                  │
│  - focal://tools/agent/{id}/enabled                                     │
│  - focal://tools/agent/{id}/unavailable                                 │
│                                                                          │
│  Used by: ASA, Admin UI, LLM Discovery                                  │
│                                                                          │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ Read ConfigStore
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AGENT LAYER                                          │
│                                                                          │
│  Brain                                                      │
│       │                                                                  │
│       │ ctx.toolbox.execute(planned_tool, ctx)  [EXECUTION PATH]        │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Toolbox                                      │   │
│  │  - Tracks Tier 2 (tenant-available) + Tier 3 (agent-enabled)     │   │
│  │  - get_unavailable_tools() for agent awareness                   │   │
│  │  - Knows side effect policy (PURE/IDEMPOTENT/COMPENSATABLE/IRR)  │   │
│  │  - Builds ToolExecutionContext with turn_group_id                │   │
│  │  - Emits ACFEvents for side effects                          │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│                              │                                          │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │ Native Execution (NOT via MCP)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     INFRASTRUCTURE LAYER                                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     ToolGateway                                   │   │
│  │  - Routes to appropriate provider                                │   │
│  │  - Manages operation idempotency (via idempotency cache)         │   │
│  │  - Does NOT know tool semantics                                  │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              ▼               ▼               ▼                          │
│      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│      │ Composio     │ │ HTTP         │ │ Internal     │                │
│      │ Provider     │ │ Provider     │ │ Provider     │                │
│      └──────────────┘ └──────────────┘ └──────────────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tool Configuration (ConfigStore)

### 2.1 ToolDefinition

Stored per-tenant in ConfigStore:

```python
class SideEffectPolicy(str, Enum):
    """Classification of tool side effects."""

    PURE = "pure"
    """Read-only. No external state modified. Safe to cancel/retry."""

    IDEMPOTENT = "idempotent"
    """Can be safely retried with same result."""

    COMPENSATABLE = "compensatable"
    """Modifies state but can be undone via compensation action."""

    IRREVERSIBLE = "irreversible"
    """Point of no return. Cannot be undone."""


class ToolDefinition(BaseModel):
    """
    Tool definition stored in ConfigStore.

    Tenant-wide definition of a tool's capabilities and semantics.
    """

    id: UUID
    tenant_id: UUID
    name: str
    description: str

    # Execution configuration
    gateway: str  # "composio", "http", "internal"
    gateway_config: dict = Field(default_factory=dict)

    # Side effect classification (Toolbox uses this for supersede decisions)
    side_effect_policy: SideEffectPolicy = SideEffectPolicy.PURE

    # For COMPENSATABLE tools
    compensation_tool_id: UUID | None = None

    # User confirmation
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None

    # Parameter schema (JSON Schema)
    parameter_schema: dict = Field(default_factory=dict)

    # Metadata
    categories: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.2 ToolActivation

Per-agent tool enablement:

```python
class ToolActivation(BaseModel):
    """
    Per-agent tool activation.

    Controls which tools an agent can use and any policy overrides.
    """

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    tool_id: UUID

    # Enablement
    enabled: bool = True

    # Policy overrides (agent-specific)
    policy_overrides: dict = Field(default_factory=dict)
    # e.g., {"requires_confirmation": True} even if tool definition says False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 3. Three-Tier Tool Visibility Model

### 3.1 Visibility Tiers

The Toolbox supports a three-tier visibility model to help agents understand what tools exist beyond what they can currently use:

| Tier | Name | Description | Who Sees It |
|------|------|-------------|-------------|
| **Tier 1** | **Catalog** | All tools in ecosystem (marketplace) | Discovery UI, ASA (Agent Suggestion Agent) |
| **Tier 2** | **Tenant-Available** | Tools tenant has connected/purchased | Tenant admin, MCP discovery, Agent (via Toolbox) |
| **Tier 3** | **Agent-Enabled** | Tools this agent can use | Toolbox, Brain (for execution) |

**Key Principle**: Agents should know what tools they COULD have access to but don't currently have. This enables:
- "I could help you schedule a meeting if you enable the Calendar tool"
- Agent Suggestion Agent (ASA) can recommend tool activations
- Operators can see usage patterns that inform tool enablement decisions

### 3.2 MCP Discovery Integration

**Decision §7.3**: MCP for discovery, Toolbox for execution

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCOVERY (MCP Server)                       │
│                                                                  │
│  Exposes Tier 2 (tenant-available) tools for:                  │
│  - LLM discovery: "What tools does this tenant have?"           │
│  - Agent Suggestion Agent (ASA): "What should I recommend?"     │
│  - Admin UI: "What can I enable?"                               │
│                                                                  │
│  MCP Resources:                                                  │
│    focal://tools/tenant/{tenant_id}/available                   │
│    focal://tools/agent/{agent_id}/enabled                       │
│    focal://tools/agent/{agent_id}/unavailable                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ Read-only discovery
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION (Toolbox Native)                   │
│                                                                  │
│  Tier 3 (agent-enabled) tools executed via:                    │
│  - Toolbox → ToolGateway → ToolProvider                         │
│  - NOT via MCP (native execution for reliability)               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Why this split?**
- **MCP for discovery**: Standardized protocol for LLMs to discover capabilities
- **Native for execution**: Direct control, no protocol overhead, better observability
- **Best of both worlds**: Discoverability + reliability

### 3.3 Tool Availability Flow

```python
# Example: Agent realizes it needs a tool it doesn't have

# 1. Toolbox knows Tier 2 (tenant-available) and Tier 3 (agent-enabled)
unavailable = toolbox.get_unavailable_tools()  # Tier 2 - Tier 3

# 2. Agent can suggest tool activation
if "calendar" in [t.name for t in unavailable]:
    response = (
        "I could help you schedule a meeting if the Calendar tool is enabled. "
        "Ask your admin to enable it for me."
    )

# 3. ASA can analyze and recommend
# (via MCP discovery endpoint)
recommendations = asa.analyze_conversation(session_id)
# → ["Enable Calendar tool based on 3 scheduling requests"]
```

---

## 4. Toolbox (Agent Layer)

### 4.1 Interface

```python
class Toolbox:
    """
    Agent-level tool facade.

    Responsibilities:
    - Resolve tools from definitions + activations
    - Execute via ToolGateway
    - Record side effects via ACFEvents
    - Provide tool metadata for supersede decisions
    - Track unavailable tools for agent awareness
    """

    def __init__(
        self,
        agent_id: UUID,
        tool_definitions: dict[UUID, ToolDefinition],
        tool_activations: dict[UUID, ToolActivation],
        gateway: ToolGateway,
    ):
        self._agent_id = agent_id
        self._gateway = gateway

        # Build resolved tool map (Tier 3: agent-enabled tools)
        self._enabled_tools: dict[str, ResolvedTool] = {}

        # Track all tenant-available tools (Tier 2: for discovery)
        self._available_tools: dict[str, ToolDefinition] = {}

        for tool_id, defn in tool_definitions.items():
            # All definitions are tenant-available (Tier 2)
            self._available_tools[defn.name] = defn

            # Check if enabled for this agent (Tier 3)
            activation = tool_activations.get(tool_id)
            if activation and activation.enabled:
                self._enabled_tools[defn.name] = ResolvedTool(
                    definition=defn,
                    activation=activation,
                )
            elif not activation:
                # No activation = use defaults (enabled)
                self._enabled_tools[defn.name] = ResolvedTool(
                    definition=defn,
                    activation=None,
                )

    async def execute(
        self,
        tool: PlannedToolExecution,
        turn_context: AgentTurnContext,
    ) -> ToolResult:
        """
        Execute a single tool.

        Flow:
        1. Resolve tool from definitions
        2. Build ToolExecutionContext with turn_group_id
        3. Execute via ToolGateway
        4. Record side effect via ACFEvent
        5. Return result
        """
        resolved = self._enabled_tools.get(tool.tool_name)
        if not resolved:
            return ToolResult(
                status="error",
                error=f"Tool '{tool.tool_name}' not found or not enabled",
            )

        # Build execution context (bridges ACF turn_group_id to gateway)
        exec_ctx = ToolExecutionContext(
            tenant_id=turn_context.agent_context.agent.tenant_id,
            agent_id=self._agent_id,
            turn_group_id=turn_context.logical_turn.turn_group_id,
            tool_name=tool.tool_name,
            args=tool.args,
            gateway=resolved.definition.gateway,
            gateway_config=resolved.definition.gateway_config,
        )

        # Emit start event
        await turn_context.emit_event(ACFEvent(
            type=ACFEventType.TOOL_SIDE_EFFECT_STARTED,
            tenant_id=exec_ctx.tenant_id,
            agent_id=exec_ctx.agent_id,
            session_key=turn_context.session_key,
            turn_id=turn_context.logical_turn.id,
            payload={
                "tool_name": tool.tool_name,
                "side_effect_policy": resolved.definition.side_effect_policy.value,
            },
        ))

        # Execute via gateway
        try:
            result = await self._gateway.execute(exec_ctx)
        except Exception as e:
            # Emit failure event
            await turn_context.emit_event(ACFEvent(
                type=ACFEventType.TOOL_SIDE_EFFECT_FAILED,
                tenant_id=exec_ctx.tenant_id,
                agent_id=exec_ctx.agent_id,
                session_key=turn_context.session_key,
                turn_id=turn_context.logical_turn.id,
                payload={
                    "tool_name": tool.tool_name,
                    "error": str(e),
                },
            ))
            return ToolResult(status="error", error=str(e))

        # Build and emit side effect record
        effect = SideEffectRecord(
            tool_name=tool.tool_name,
            policy=resolved.definition.side_effect_policy,
            executed_at=datetime.utcnow(),
            args=tool.args,
            result=result.data if result.success else None,
            status="executed" if result.success else "failed",
            idempotency_key=exec_ctx.build_idempotency_key(
                self._extract_business_key(tool.args, resolved.definition)
            ),
        )

        await turn_context.emit_event(ACFEvent(
            type=ACFEventType.TOOL_SIDE_EFFECT_COMPLETED,
            tenant_id=exec_ctx.tenant_id,
            agent_id=exec_ctx.agent_id,
            session_key=turn_context.session_key,
            turn_id=turn_context.logical_turn.id,
            payload=effect.model_dump(),
        ))

        return result

    async def execute_batch(
        self,
        tools: list[PlannedToolExecution],
        turn_context: AgentTurnContext,
    ) -> list[ToolResult]:
        """Execute multiple tools sequentially."""
        results = []
        for tool in tools:
            result = await self.execute(tool, turn_context)
            results.append(result)
            # Stop on first failure if tool is critical
            if not result.success and tool.critical:
                break
        return results

    def get_metadata(self, tool_name: str) -> ToolMetadata | None:
        """
        Get metadata for a tool.

        Used by Brain to decide supersede behavior before execution.
        """
        resolved = self._enabled_tools.get(tool_name)
        if not resolved:
            return None

        # Apply activation overrides
        defn = resolved.definition
        activation = resolved.activation

        requires_confirmation = defn.requires_confirmation
        if activation and "requires_confirmation" in activation.policy_overrides:
            requires_confirmation = activation.policy_overrides["requires_confirmation"]

        return ToolMetadata(
            name=defn.name,
            side_effect_policy=defn.side_effect_policy,
            requires_confirmation=requires_confirmation,
            compensation_tool=defn.compensation_tool_id,
            categories=defn.categories,
        )

    def is_available(self, tool_name: str) -> bool:
        """Check if tool is available for this agent."""
        return tool_name in self._enabled_tools

    def list_available(self) -> list[str]:
        """List all available tool names."""
        return list(self._enabled_tools.keys())

    def get_unavailable_tools(self) -> list[ToolDefinition]:
        """
        Get tools available to tenant but not enabled for this agent.

        This is Tier 2 (tenant-available) minus Tier 3 (agent-enabled).

        Enables agents to say:
        - "I could help you schedule a meeting if the Calendar tool is enabled"
        - "This requires the Email tool, which I don't have access to"

        Used by:
        - Agent response generation (suggest tool activations)
        - Agent Suggestion Agent (ASA) for recommendations
        - Admin UI (show what could be enabled)
        """
        unavailable = []
        for tool_name, definition in self._available_tools.items():
            if tool_name not in self._enabled_tools:
                unavailable.append(definition)
        return unavailable

    def is_tenant_available(self, tool_name: str) -> bool:
        """
        Check if tool is available to the tenant (Tier 2).

        Returns True even if not enabled for this agent.
        """
        return tool_name in self._available_tools

    def get_tool_definition(self, tool_name: str) -> ToolDefinition | None:
        """
        Get tool definition (Tier 2 lookup).

        Returns definition even if not enabled for this agent.
        Used for discovery and recommendation flows.
        """
        return self._available_tools.get(tool_name)

    def _extract_business_key(
        self,
        args: dict,
        definition: ToolDefinition,
    ) -> str:
        """
        Extract business key from args for idempotency.

        Uses tool's parameter_schema to identify key fields.
        Falls back to hashing all args.
        """
        key_fields = definition.gateway_config.get("idempotency_key_fields", [])
        if key_fields:
            key_parts = [str(args.get(f, "")) for f in key_fields]
            return ":".join(key_parts)
        else:
            # Fallback: hash all args
            import hashlib
            import json
            return hashlib.sha256(
                json.dumps(args, sort_keys=True).encode()
            ).hexdigest()[:16]


@dataclass
class ResolvedTool:
    """Tool with resolved definition and activation."""
    definition: ToolDefinition
    activation: ToolActivation | None
```

### 3.2 Supporting Types

```python
class PlannedToolExecution(BaseModel):
    """
    Brain's proposal to execute a tool.

    Created by Brain during planning, executed by Toolbox.
    """

    tool_name: str
    args: dict
    idempotency_key: str | None = None  # Optional override
    when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] = "DURING_STEP"
    bound_rule_id: UUID | None = None
    bound_step_id: str | None = None
    critical: bool = True  # Stop batch on failure?


class ToolResult(BaseModel):
    """Result of tool execution."""

    status: str  # "success", "error", "skipped", "cached"
    data: dict | None = None
    error: str | None = None
    cached: bool = False
    execution_time_ms: int | None = None


class ToolMetadata(BaseModel):
    """
    Tool metadata for Brain decisions.

    Used by Brain to decide:
    - Should I check supersede before this tool?
    - Does this tool require user confirmation?
    """

    name: str
    side_effect_policy: SideEffectPolicy
    requires_confirmation: bool = False
    compensation_tool: UUID | None = None
    categories: list[str] = Field(default_factory=list)

    @property
    def is_irreversible(self) -> bool:
        return self.side_effect_policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def is_safe_to_retry(self) -> bool:
        return self.side_effect_policy in [
            SideEffectPolicy.PURE,
            SideEffectPolicy.IDEMPOTENT,
        ]


class SideEffectRecord(BaseModel):
    """
    Record of an executed side effect.

    Emitted via ACFEvent; ACF stores in LogicalTurn.side_effects.
    """

    id: UUID = Field(default_factory=uuid4)
    tool_name: str
    policy: SideEffectPolicy
    executed_at: datetime
    args: dict
    result: dict | None = None
    status: str  # "executed", "failed", "compensated"
    idempotency_key: str | None = None

    # For compensation tracking
    compensation_id: UUID | None = None
    compensation_executed: bool = False
    compensation_result: dict | None = None

    @property
    def irreversible(self) -> bool:
        return self.policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def needs_compensation(self) -> bool:
        return (
            self.policy == SideEffectPolicy.COMPENSATABLE
            and not self.compensation_executed
        )
```

---

## 5. MCP Server for Tool Discovery

### 5.1 Purpose

The MCP Server exposes read-only tool discovery endpoints for:
- LLMs to discover what tools are available
- Agent Suggestion Agent (ASA) to recommend tool activations
- Admin UI to show enablement options

**IMPORTANT**: MCP is for discovery only. Execution happens via native Toolbox → ToolGateway flow.

### 5.2 MCP Resources

```python
# MCP Resource URIs

# Tier 2: All tools available to tenant
focal://tools/tenant/{tenant_id}/available

# Tier 3: Tools enabled for specific agent
focal://tools/agent/{agent_id}/enabled

# Tier 2 - Tier 3: Tools agent could use but doesn't have
focal://tools/agent/{agent_id}/unavailable
```

### 5.3 Example MCP Resource Handler

```python
class ToolDiscoveryMCPHandler:
    """MCP resource handler for tool discovery."""

    def __init__(self, config_store: ConfigStore):
        self._config_store = config_store

    async def handle_resource(self, uri: str) -> dict:
        """Handle MCP resource request."""
        if uri.startswith("focal://tools/tenant/"):
            # Extract tenant_id from URI
            tenant_id = self._parse_tenant_id(uri)
            return await self._get_tenant_available_tools(tenant_id)

        elif uri.startswith("focal://tools/agent/") and "/enabled" in uri:
            # Extract agent_id from URI
            agent_id = self._parse_agent_id(uri)
            return await self._get_agent_enabled_tools(agent_id)

        elif uri.startswith("focal://tools/agent/") and "/unavailable" in uri:
            # Extract agent_id from URI
            agent_id = self._parse_agent_id(uri)
            return await self._get_agent_unavailable_tools(agent_id)

        raise ValueError(f"Unknown resource URI: {uri}")

    async def _get_tenant_available_tools(self, tenant_id: UUID) -> dict:
        """Get all tools available to tenant (Tier 2)."""
        definitions = await self._config_store.get_tool_definitions(tenant_id)
        return {
            "tools": [
                {
                    "name": defn.name,
                    "description": defn.description,
                    "categories": defn.categories,
                    "gateway": defn.gateway,
                    "requires_confirmation": defn.requires_confirmation,
                    "side_effect_policy": defn.side_effect_policy.value,
                    "parameter_schema": defn.parameter_schema,
                }
                for defn in definitions
            ]
        }

    async def _get_agent_enabled_tools(self, agent_id: UUID) -> dict:
        """Get tools enabled for agent (Tier 3)."""
        agent = await self._config_store.get_agent(agent_id)
        definitions = await self._config_store.get_tool_definitions(agent.tenant_id)
        activations = await self._config_store.get_tool_activations(agent_id)

        enabled = []
        for defn in definitions:
            activation = activations.get(defn.id)
            if (activation and activation.enabled) or not activation:
                enabled.append({
                    "name": defn.name,
                    "description": defn.description,
                    "categories": defn.categories,
                    "parameter_schema": defn.parameter_schema,
                })

        return {"tools": enabled}

    async def _get_agent_unavailable_tools(self, agent_id: UUID) -> dict:
        """Get tools tenant has but agent doesn't (Tier 2 - Tier 3)."""
        agent = await self._config_store.get_agent(agent_id)
        definitions = await self._config_store.get_tool_definitions(agent.tenant_id)
        activations = await self._config_store.get_tool_activations(agent_id)

        unavailable = []
        for defn in definitions:
            activation = activations.get(defn.id)
            # If explicitly disabled or not present
            if activation and not activation.enabled:
                unavailable.append({
                    "name": defn.name,
                    "description": defn.description,
                    "categories": defn.categories,
                    "why_unavailable": "disabled_for_agent",
                })

        return {"tools": unavailable}
```

### 5.4 Discovery vs Execution

```python
# Discovery flow (via MCP)
# ASA asks: "What tools could this agent use?"

mcp_response = await mcp_client.read_resource(
    f"focal://tools/agent/{agent_id}/unavailable"
)
# → {"tools": [{"name": "calendar", "description": "...", ...}]}

# Recommendation
if "calendar" in conversation_analysis.needed_capabilities:
    return "Enable the Calendar tool for better scheduling support"


# Execution flow (native, NOT via MCP)
# Brain executes tool directly

result = await ctx.toolbox.execute(
    PlannedToolExecution(tool_name="calendar", args={...}),
    ctx,
)
# → ToolResult(status="success", data={...})
```

**Key Difference**:
- **MCP**: Read-only discovery (what tools exist, metadata)
- **Native**: Write/execute (actually run the tool, record side effects)

---

## 6. ToolExecutionContext (Bridge)

Bridges ACF's `turn_group_id` to ToolGateway's idempotency:

```python
@dataclass
class ToolExecutionContext:
    """
    Context passed to ToolGateway for execution.

    Bridges Agent layer (Toolbox) to Infrastructure layer (ToolGateway).
    Carries turn_group_id from ACF for idempotency key construction.
    """

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

        Format: {tool_name}:{business_key}:turn_group:{turn_group_id}

        This ensures:
        - Supersede chain shares key -> one execution
        - QUEUE creates new turn_group_id -> allows re-execution
        """
        return f"{self.tool_name}:{business_key}:turn_group:{self.turn_group_id}"
```

---

## 7. ToolGateway (Infrastructure Layer)

### 7.1 Interface

```python
class ToolGateway(Protocol):
    """
    Infrastructure-level tool execution.

    Responsibilities:
    - Route to appropriate provider
    - Manage operation idempotency
    - Does NOT know tool semantics (that's Toolbox)
    """

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        """Execute tool via appropriate provider."""
        ...
```

### 7.2 Implementation

```python
class ToolGatewayImpl:
    """
    ToolGateway implementation.

    Routes to providers, handles idempotency.
    """

    def __init__(
        self,
        providers: dict[str, ToolProvider],
        idem_cache: IdempotencyCache,
        default_idem_ttl: int = 86400,  # 24 hours
    ):
        self._providers = providers
        self._idem_cache = idem_cache
        self._default_idem_ttl = default_idem_ttl

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        """Execute tool with idempotency check."""

        # Build idempotency key
        business_key = self._extract_business_key(ctx)
        idem_key = ctx.build_idempotency_key(business_key)

        # Check idempotency cache
        cached = await self._idem_cache.get(idem_key)
        if cached:
            return ToolResult(
                status="success",
                data=cached,
                cached=True,
            )

        # Get provider
        provider = self._providers.get(ctx.gateway)
        if not provider:
            return ToolResult(
                status="error",
                error=f"Unknown gateway: {ctx.gateway}",
            )

        # Execute
        start_time = datetime.utcnow()
        try:
            result_data = await provider.call(
                ctx.tool_name,
                ctx.args,
                ctx.gateway_config,
            )
            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            result = ToolResult(
                status="success",
                data=result_data,
                execution_time_ms=execution_time,
            )

            # Cache successful result
            await self._idem_cache.set(
                idem_key,
                result_data,
                ttl=self._default_idem_ttl,
            )

            return result

        except ToolExecutionError as e:
            return ToolResult(
                status="error",
                error=str(e),
            )

    def _extract_business_key(self, ctx: ToolExecutionContext) -> str:
        """Extract business key from args."""
        key_fields = ctx.gateway_config.get("idempotency_key_fields", [])
        if key_fields:
            return ":".join(str(ctx.args.get(f, "")) for f in key_fields)
        else:
            import hashlib
            import json
            return hashlib.sha256(
                json.dumps(ctx.args, sort_keys=True).encode()
            ).hexdigest()[:16]
```

---

## 8. Tool Providers

### 8.1 Provider Protocol

```python
class ToolProvider(Protocol):
    """
    Provider for executing tools against external services.

    Each provider knows how to call its specific backend.
    """

    async def call(
        self,
        tool_name: str,
        args: dict,
        config: dict,
    ) -> dict:
        """
        Execute tool and return result.

        Raises ToolExecutionError on failure.
        """
        ...


class ToolExecutionError(Exception):
    """Error during tool execution."""

    def __init__(self, tool_name: str, message: str, details: dict | None = None):
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(f"Tool '{tool_name}' failed: {message}")
```

### 8.2 Example Providers

**Composio Provider**:
```python
class ComposioToolProvider(ToolProvider):
    """Provider for Composio-managed tools."""

    def __init__(self, composio_client: ComposioClient):
        self._client = composio_client

    async def call(
        self,
        tool_name: str,
        args: dict,
        config: dict,
    ) -> dict:
        try:
            result = await self._client.execute_action(
                action=config.get("composio_action", tool_name),
                params=args,
                entity_id=config.get("entity_id"),
            )
            return result.data
        except ComposioError as e:
            raise ToolExecutionError(tool_name, str(e), {"composio_error": e.code})
```

**HTTP Provider**:
```python
class HTTPToolProvider(ToolProvider):
    """Provider for HTTP-based tools."""

    def __init__(self, http_client: httpx.AsyncClient):
        self._client = http_client

    async def call(
        self,
        tool_name: str,
        args: dict,
        config: dict,
    ) -> dict:
        url = config["url"]
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=args,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ToolExecutionError(tool_name, str(e))
```

**Internal Provider**:
```python
class InternalToolProvider(ToolProvider):
    """Provider for internal Python tools."""

    def __init__(self, tools: dict[str, Callable]):
        self._tools = tools

    async def call(
        self,
        tool_name: str,
        args: dict,
        config: dict,
    ) -> dict:
        handler = self._tools.get(tool_name)
        if not handler:
            raise ToolExecutionError(tool_name, "Tool not registered")

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**args)
            else:
                result = handler(**args)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            raise ToolExecutionError(tool_name, str(e))
```

---

## 9. Idempotency Cache

```python
class IdempotencyCache(Protocol):
    """Cache for tool idempotency."""

    async def get(self, key: str) -> dict | None:
        """Get cached result if exists."""
        ...

    async def set(self, key: str, value: dict, ttl: int) -> None:
        """Cache result with TTL."""
        ...


class RedisIdempotencyCache(IdempotencyCache):
    """Redis-backed idempotency cache."""

    def __init__(self, redis: Redis, key_prefix: str = "tool_idem"):
        self._redis = redis
        self._key_prefix = key_prefix

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    async def get(self, key: str) -> dict | None:
        data = await self._redis.get(self._key(key))
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: dict, ttl: int) -> None:
        await self._redis.setex(
            self._key(key),
            ttl,
            json.dumps(value),
        )
```

---

## 10. Brain Integration

### 10.1 Supersede Check Before Irreversible Tools

```python
class FocalBrain(Brain):
    """FOCAL brain with supersede-aware tool execution."""

    async def _execute_tools(
        self,
        matched_rules: list[MatchedRule],
        ctx: AgentTurnContext,
    ) -> list[ToolResult]:
        """Execute tools with supersede checking."""
        results = []

        for rule in matched_rules:
            for tool_binding in rule.tool_bindings:
                planned = PlannedToolExecution(
                    tool_name=tool_binding.tool_id,
                    args=self._resolve_args(tool_binding, ctx),
                    bound_rule_id=rule.rule_id,
                )

                # Get metadata for supersede decision
                metadata = ctx.toolbox.get_metadata(planned.tool_name)
                if not metadata:
                    continue

                # Check supersede before irreversible tools
                if metadata.is_irreversible:
                    if await ctx.has_pending_messages():
                        # Brain decides what to do
                        decision = await self._decide_supersede_action(ctx, planned)
                        if decision == SupersedeAction.SUPERSEDE:
                            # Abort turn
                            raise SupersededError("New message before irreversible tool")
                        elif decision == SupersedeAction.ABSORB:
                            # Absorb pending messages into context
                            await self._absorb_pending_messages(ctx)
                        # FORCE_COMPLETE or QUEUE: continue

                # Execute tool
                result = await ctx.toolbox.execute(planned, ctx)
                results.append(result)

        return results
```

### 10.2 Confirmation Flow

```python
class FocalBrain(Brain):
    """Brain with confirmation support."""

    async def _execute_tool_with_confirmation(
        self,
        planned: PlannedToolExecution,
        ctx: AgentTurnContext,
    ) -> ToolResult | ConfirmationRequest:
        """Execute tool, possibly requesting confirmation first."""
        metadata = ctx.toolbox.get_metadata(planned.tool_name)

        if metadata and metadata.requires_confirmation:
            # Check if we already have confirmation
            if not self._has_confirmation(ctx, planned):
                # Return confirmation request instead of executing
                return ConfirmationRequest(
                    tool_name=planned.tool_name,
                    args=planned.args,
                    prompt=self._build_confirmation_prompt(metadata, planned),
                )

        # Execute tool
        return await ctx.toolbox.execute(planned, ctx)
```

---

## 11. Configuration

```toml
[toolbox]
# Default idempotency TTL (seconds)
default_idempotency_ttl = 86400  # 24 hours

# Maximum batch size for execute_batch
max_batch_size = 10

# Timeout for tool execution (seconds)
default_timeout = 30

[tool_gateway]
# Provider configurations
[tool_gateway.providers.composio]
api_key_env = "COMPOSIO_API_KEY"

[tool_gateway.providers.http]
default_timeout = 30
max_retries = 3

# Idempotency cache
[tool_gateway.idempotency]
backend = "redis"
key_prefix = "tool_idem"
default_ttl = 86400
```

---

## 12. Observability

### 12.1 Metrics

```python
# Tool execution metrics
tool_execution_duration = Histogram(
    "tool_execution_duration_seconds",
    "Tool execution duration",
    ["tenant_id", "agent_id", "tool_name", "gateway"],
)

tool_execution_count = Counter(
    "tool_execution_total",
    "Total tool executions",
    ["tenant_id", "agent_id", "tool_name", "status"],
)

tool_idempotency_cache_hits = Counter(
    "tool_idempotency_cache_hits_total",
    "Idempotency cache hits",
    ["tenant_id", "tool_name"],
)

# Side effect metrics
side_effect_count = Counter(
    "tool_side_effect_total",
    "Side effects by policy",
    ["tenant_id", "agent_id", "policy"],
)
```

### 12.2 Logging

```python
logger.info(
    "tool_execution_started",
    tenant_id=ctx.tenant_id,
    agent_id=ctx.agent_id,
    tool_name=tool.tool_name,
    side_effect_policy=metadata.side_effect_policy,
)

logger.info(
    "tool_execution_completed",
    tenant_id=ctx.tenant_id,
    agent_id=ctx.agent_id,
    tool_name=tool.tool_name,
    status=result.status,
    cached=result.cached,
    execution_time_ms=result.execution_time_ms,
)
```

---

## 13. Testing

### 13.1 Unit Tests

```python
@pytest.fixture
def mock_gateway():
    return MockToolGateway()


@pytest.fixture
def toolbox(mock_gateway):
    tool_defs = {
        uuid4(): ToolDefinition(
            id=uuid4(),
            tenant_id=uuid4(),
            name="test_tool",
            gateway="internal",
            side_effect_policy=SideEffectPolicy.PURE,
        )
    }
    return Toolbox(
        agent_id=uuid4(),
        tool_definitions=tool_defs,
        tool_activations={},
        gateway=mock_gateway,
    )


async def test_execute_tool_success(toolbox, mock_gateway):
    """Test successful tool execution."""
    mock_gateway.set_response("test_tool", {"result": "success"})

    turn_ctx = create_mock_turn_context()
    planned = PlannedToolExecution(tool_name="test_tool", args={"key": "value"})

    result = await toolbox.execute(planned, turn_ctx)

    assert result.status == "success"
    assert result.data == {"result": "success"}


async def test_execute_tool_not_found(toolbox):
    """Test tool not found error."""
    turn_ctx = create_mock_turn_context()
    planned = PlannedToolExecution(tool_name="unknown_tool", args={})

    result = await toolbox.execute(planned, turn_ctx)

    assert result.status == "error"
    assert "not found" in result.error


async def test_idempotency_cache_hit(toolbox, mock_gateway):
    """Test idempotency cache prevents duplicate execution."""
    mock_gateway.set_response("test_tool", {"result": "first"})

    turn_ctx = create_mock_turn_context()
    planned = PlannedToolExecution(tool_name="test_tool", args={"key": "value"})

    # First execution
    result1 = await toolbox.execute(planned, turn_ctx)
    assert result1.cached is False

    # Second execution with same args + turn_group_id
    result2 = await toolbox.execute(planned, turn_ctx)
    assert result2.cached is True
    assert result2.data == result1.data
```

---

## 14. Related Documents

- [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md) - Overall architecture
- [AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md) - Agent abstraction
- [topics/04-side-effect-policy.md](topics/04-side-effect-policy.md) - Side effect classification
- [topics/12-idempotency.md](topics/12-idempotency.md) - Idempotency layers
