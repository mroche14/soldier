# soldier Deep Dive: Tools (Toolbox / ToolGateway / “ToolHub”)

## 1) Canonical Intent in soldier (Docs)

The most “authoritative” tool story in `soldier` is split across:

- `docs/acf/architecture/TOOLBOX_SPEC.md` (Toolbox + ToolGateway ownership model)
- `docs/acf/architecture/topics/04-side-effect-policy.md` (side-effect classification semantics)
- `docs/acf/architecture/topics/12-idempotency.md` + `docs/acf/architecture/ACF_SPEC.md` (3-layer idempotency and why it exists)
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md` (AgentTurnContext + how Brain calls toolbox)

**Core boundary claim (v3 framing):**
- *Toolbox* owns **semantics** (policy, confirmation, side-effect record emission)
- *ToolGateway* owns **mechanics** (provider adapters + idempotency cache)
- ACF should **not** own tool semantics; it stores events and exposes supersede facts only.

**Discovery vs execution split:**
- Discovery uses MCP (read-only metadata)
- Execution uses Toolbox → ToolGateway (native execution path)

## 2) What Exists in Code (Inventory)

### 2.1 Runtime Toolbox stack (most aligned with spec)

- `ruche/runtime/toolbox/models.py`
  - `ToolDefinition` (tenant-scoped, UUID id)
  - `ToolActivation` (agent-scoped, UUID tool_id)
  - `SideEffectPolicy` (PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE)
  - `PlannedToolExecution` and `ToolResult`, `ToolMetadata`, `SideEffectRecord`
- `ruche/runtime/toolbox/toolbox.py`
  - Resolves tenant-available vs agent-enabled tools and executes through gateway
  - Builds `ToolExecutionContext(turn_group_id=logical_turn.turn_group_id)` for idempotency
  - Emits “events” via `turn_context.emit_event(...)` (but see drift below)
- `ruche/runtime/toolbox/context.py`
  - `build_idempotency_key()` = `{tool_name}:{business_key}:turn_group:{turn_group_id}`
- `ruche/runtime/toolbox/gateway.py`
  - Provider dispatch (`ToolProvider.call(...)`)
  - Idempotency via `IdempotencyCache.get/set` protocol (TTL default 24h)

### 2.2 Runtime “idempotency cache” stack (separate and mismatched)

- `ruche/runtime/idempotency/cache.py`
  - Defines a different interface: `check/mark_processing/mark_complete` with explicit `IdempotencyLayer`
  - Provides `RedisIdempotencyCache` and `InMemoryIdempotencyCache`

This is conceptually the same “3-layer idempotency” from docs, but it is **not the same protocol** used by `ruche/runtime/toolbox/gateway.py` (which expects `.get/.set`).

### 2.3 MCP tool discovery in API (present, but definition-less)

- `ruche/api/mcp/server.py` + `ruche/api/mcp/handlers.py`
  - Implements endpoints similar to Toolbox spec URIs
  - But it currently infers tenant-available tools by aggregating **ToolActivations across agents**
  - It does not have a real ToolDefinition source (explicitly described as placeholder)

### 2.4 Brain-level “ToolHub” model (string tool IDs, used by current API + stores)

In contrast to runtime Toolbox models, FOCAL brain and ConfigStore currently operate with **string tool IDs**:

- `ruche/brains/focal/models/tool_binding.py` → `ToolBinding.tool_id: str` (“Tool identifier from ToolHub”)
- `ruche/brains/focal/models/tool_activation.py` → `ToolActivation.tool_id: str`
- `ruche/api/routes/tools.py` exposes “tool activation management endpoints” using the brain ToolActivation model
- `ruche/infrastructure/stores/config/interface.py` supports tool activations but has **no ToolDefinition CRUD**
- `ruche/infrastructure/stores/config/inmemory.py` stores tool activations keyed by `(tenant_id, agent_id, tool_id: str)`

### 2.5 Duplicate / legacy toolbox stack under `ruche/infrastructure/toolbox/`

The folder `ruche/infrastructure/toolbox/` defines a separate set of:
- `ToolDefinition` (string IDs, provider fields, simpler SideEffectPolicy)
- `ToolGateway` (register_provider/execute, no idempotency)
- Provider stubs (`providers/http.py`, `providers/composio.py`, `providers/internal.py`)
- `Toolbox` that is explicitly a stub

This appears to be an earlier draft that conflicts with the `ruche/runtime/toolbox/` implementation and the newer ACF/Toolbox docs.

## 3) Major Spec ↔ Code Drift (Integration-Relevant)

### 3.1 Event emission is not currently compatible with ACFEvent routing

ACF expects:
- `FabricTurnContext.emit_event(event: ACFEvent)` (see `ruche/runtime/acf/models.py`)
- `EventRouter.route(event: ACFEvent, ...)` (see `ruche/runtime/acf/event_router.py`)

But runtime Toolbox currently emits ad-hoc payloads like:
- `"TOOL_SIDE_EFFECT_STARTED"`, `"TOOL_SIDE_EFFECT_COMPLETED"`, `"TOOL_SIDE_EFFECT_FAILED"`
  - via `Toolbox._emit_event(turn_context, event_type: str, payload: dict)`

This diverges from:
- `ACFEventType.TOOL_AUTHORIZED = "tool.authorized"`
- `ACFEventType.TOOL_EXECUTED = "tool.executed"`
- `ACFEventType.TOOL_FAILED = "tool.failed"`

Net: if the runtime Toolbox is wired into the runtime ACF, it would need to emit real `ACFEvent` objects with canonical types.

### 3.2 Side-effect policy enums are inconsistent across layers

- Toolbox spec (and runtime toolbox models): `PURE / IDEMPOTENT / COMPENSATABLE / IRREVERSIBLE`
- Runtime ACF models store: `REVERSIBLE / IDEMPOTENT / IRREVERSIBLE` (`ruche/runtime/acf/models.py`)
- EventRouter `_record_side_effect` currently maps `policy` strings to that ACF enum

Net: either:
1) ACF side effect storage becomes “opaque record storage” (store the Toolbox `SideEffectRecord` without reinterpretation), or
2) a clean mapping is introduced (e.g., `COMPENSATABLE → REVERSIBLE`, `PURE → IDEMPOTENT` or “none”), with the canonical choice documented.

### 3.3 AgentTurnContext type hints + convenience method are out of sync

Docs show:
- `AgentTurnContext.execute_tool(...)` builds `PlannedToolExecution` and calls `self.toolbox.execute(planned, self)`

Runtime code currently has:
- `ruche/runtime/agent/context.py` with a convenience method `execute_tool()` that calls `self.toolbox.execute(tool_name, args, self)`
  - which is not compatible with `ruche/runtime/toolbox/toolbox.py` signature
  - and type hints refer to the *infrastructure* toolbox, not the runtime toolbox

Even if unused today, this will be a sharp edge when integrating tools into brains or channel adapters.

### 3.4 ToolDefinition sourcing is unresolved in the codebase

The runtime AgentRuntime tries to load:
- `tool_defs = await self._config_store.get_tool_definitions(tenant_id)` (in `ruche/runtime/agent/runtime.py`)

But the ConfigStore interfaces in use (`ruche/infrastructure/stores/config/interface.py` and `ruche/brains/focal/stores/agent_config_store.py`) do not define `get_tool_definitions`.

Net: tool definitions are not yet a “first-class persisted entity” in soldier’s current store contracts (despite Toolbox spec describing them).

## 4) What sb_agent_hub Brings (Relevant Contrast)

### 4.1 Tool definitions live in “manifests” (docs), not as an engine concern

In `sb_agent_hub`, the architecture doc (`docs/architecture/SMARTBEEZ_AGENT_PLATFORM_COMPLETE_ARCHITECTURE_V2.md`) treats tools as:
- Part of an authoring spec compiled into an immutable manifest
- Bound to connected accounts and scopes
- Executed via a sandbox / orchestration layer

### 4.2 Tool execution in code is currently split between

- LangChain/LangGraph tools in:
  - `3-backend/app/tools/*` (BaseAgentTool, HTTPRequestTool, etc.)
- Placeholder “tool node” execution in:
  - `3-backend/app/services/workflow_engine.py` (`_execute_tool` is a placeholder, mentions Composio/MCP)
- Celery placeholder:
  - `3-backend/app/tasks/tool_tasks.py`

So sb_agent_hub has strong *platform intent* but tool ecosystem execution is not yet “ToolHub-grade” in code.

## 5) Integration Implications (Practical)

### 5.1 Pick a single tool identity scheme

Right now:
- soldier brain-level uses **string tool IDs** (ToolHub-managed)
- soldier runtime Toolbox uses **UUID tool IDs**
- sb_agent_hub tooling mostly uses **names/strings**

For cross-repo integration, a stable string identity (e.g., `crm.create_ticket`) is usually the simplest common denominator.

**What `kernel_agent` adds**:
- A full ToolHub service already built around stable string tool names like `gmail.send_email`:
  - execution API: `kernel_agent/apps/toolhub/src/toolhub/api/execution.py` (`POST /execute-stream`, NDJSON)
  - per-tenant activation + audit logging: `kernel_agent/apps/toolhub/src/toolhub/services/execution.py`

This strongly supports choosing stable string tool names as the integration boundary, and treating UUID tool IDs as internal storage details only.

### 5.2 Decide the system of record for ToolDefinitions

Options:
1) `sb_agent_hub` is SoT for ToolDefinitions; `soldier` consumes definitions via bundles/API.
2) `soldier` becomes SoT for ToolDefinitions; `sb_agent_hub` only manages activation/connected accounts.
3) A separate ToolHub service (in sb_agent_hub) is SoT; both repos query it.

Given:
- soldier docs already allow an external control plane
- sb_agent_hub already has control plane + connected accounts concept

…Option (1) is the least invasive: `sb_agent_hub` owns ToolDefinitions and publishes them.

### 5.3 ToolGateway can be the technical “join point”

Even if tool definitions live in sb_agent_hub, soldier can still own:
- idempotency key strategy (turn_group scoping)
- policy checks + side effect record emission
- per-provider adapter selection (composio/http/internal)

But the actual execution can be delegated:
- ToolGateway provider “smartbeez” that calls `sb_agent_hub` tool execution endpoints, or publishes to its Celery/Restate queue.

This preserves the architectural boundary soldier’s docs want:
- **Ruche enforces the semantics**
- **SmartBeez orchestrates the integrations**
