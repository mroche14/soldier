# FOCAL 360 Architecture

> **Purpose**: Complete architectural documentation for Focal's conversational AI infrastructure
> **Core Abstraction**: Agent Conversation Fabric (ACF) - the conversation control plane
> **Status**: Authoritative reference for implementation
> **Version**: 3.0 (Agent/Toolbox ownership model)

---

## Start Here

### Primary Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| **[ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md)** | Canonical architecture (v3.0) | Starting any work |
| **[AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md)** | Agent lifecycle, caching | Building Agent layer |
| **[TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)** | Tool execution layer | Building Toolbox |
| **[ACF_SPEC.md](ACF_SPEC.md)** | Detailed ACF mechanics | Implementing ACF |
| **[LOGICAL_TURN_VISION.md](LOGICAL_TURN_VISION.md)** | Founding vision | Understanding the "why" |

### The Core Insight

> **A message is not a turn.**

The semantic unit is a **conversational beat** - one or more rapid messages forming one coherent user intent.

```
User: "Hello"          ┐
User: "How are you?"   ├─→ ONE LogicalTurn → ONE Response
                       ┘
```

---

## Architecture Overview (v3.0)

### Three-Layer Model

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            RUNTIME LAYER                                    │
│  AgentRuntime: lifecycle management, caching, invalidation                  │
│  AgentContext: agent + pipeline + toolbox + channel_bindings               │
│  AgentTurnContext: fabric (ACF) + agent_context (per-turn)                 │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
┌────────────────────────────────────────────────────────────────────────────┐
│                           ACF LAYER                                         │
│  SessionMutex | TurnManager | SupersedeCoordinator | Hatchet Workflow      │
│  FabricTurnContext: logical_turn, has_pending_messages, emit_event         │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
┌────────────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                                   │
│  ToolGateway (Composio, HTTP) | ChannelGateway | Stores | Providers        │
└────────────────────────────────────────────────────────────────────────────┘
```

### Key Boundaries (v3.0)

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| **ACF** | Mutex, turns, workflow, supersede signals, FabricEvent routing | Tool execution, tool semantics, business logic |
| **AgentRuntime** | Agent lifecycle, caching, invalidation | Turn processing |
| **Toolbox** | Tool resolution, execute via gateway, side effect recording | Backend impl, idempotency storage |
| **ToolGateway** | Provider adapters, operation idempotency | Tool metadata, policies |

### Execution Model

FOCAL uses a **single execution style**: Pipeline calls `toolbox.execute()` inline.

```
acquire_mutex → accumulate → run_pipeline → commit_and_respond
```

**Key principle**: Toolbox is the enforcement boundary. ACF is NOT in the tool execution path. Pipeline conformance is enforced via Toolbox + ASA validation, not runtime modes.

---

## Document Index

### Architecture Specifications

| Document | Status | Purpose |
|----------|--------|---------|
| **[ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md)** | ⭐ Canonical | Overall architecture |
| **[AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md)** | ⭐ Authoritative | Agent abstraction |
| **[TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)** | ⭐ Authoritative | Tool execution |
| **[ACF_SPEC.md](ACF_SPEC.md)** | ⭐ Authoritative | ACF mechanics |
| **[LOGICAL_TURN_VISION.md](LOGICAL_TURN_VISION.md)** | Reference | Founding vision |

### ACF Component Topics

| # | Topic | Owner | Description |
|---|-------|-------|-------------|
| 01 | [LogicalTurn Model](topics/01-logical-turn.md) | ACF | Beat data model, supersede semantics |
| 02 | [Session Mutex](topics/02-session-mutex.md) | ACF | Single-writer rule |
| 03 | [Adaptive Accumulation](topics/03-adaptive-accumulation.md) | ACF | Turn completion detection |
| 04 | [Side-Effect Policy](topics/04-side-effect-policy.md) | **Toolbox** | Tool safety classification |
| 05 | [Checkpoint Reuse](topics/05-checkpoint-reuse.md) | Pipeline | Artifact reuse |
| 06 | [Hatchet Integration](topics/06-hatchet-integration.md) | ACF | Durable workflow execution |
| 07 | [Turn Gateway](topics/07-turn-gateway.md) | ACF | Message ingress |
| 10 | [Channel Capabilities](topics/10-channel-capabilities.md) | ACF | Channel facts + policies |
| 12 | [Idempotency](topics/12-idempotency.md) | Multi | Three-layer protection |

### Agent/Pipeline Component Topics

| # | Topic | Owner | Description |
|---|-------|-------|-------------|
| 08 | [Config Hierarchy](topics/08-config-hierarchy.md) | ConfigStore | Multi-level config |
| 09 | [Agenda & Goals](topics/09-agenda-goals.md) | Pipeline | Proactive follow-up |
| 11 | [Abuse Detection](topics/11-abuse-detection.md) | Pipeline | Pattern-based handling |
| 13 | [ASA Validator](topics/13-asa-validator.md) | Admin | Design-time validation |

---

## Reading Order

### For Understanding the Architecture

1. **[ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md)** - Start here for v3.0 architecture
2. **[LOGICAL_TURN_VISION.md](LOGICAL_TURN_VISION.md)** - Why we designed it this way
3. **[01-logical-turn.md](topics/01-logical-turn.md)** - Core data model
4. **[AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md)** - Agent abstraction
5. **[TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)** - Tool execution

### For Implementation (Phase 1: ACF Core)

1. **Core types** - RawMessage, LogicalTurn, SessionKey
2. **[02-session-mutex.md](topics/02-session-mutex.md)** - Session mutex
3. **[03-adaptive-accumulation.md](topics/03-adaptive-accumulation.md)** - Turn aggregation
4. **[06-hatchet-integration.md](topics/06-hatchet-integration.md)** - Workflow
5. **[ACF_SPEC.md](ACF_SPEC.md)** - Detailed mechanics

### For Implementation (Phase 2: Agent Layer)

6. **[AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md)** - AgentRuntime, AgentContext
7. **AgentTurnContext** - Wraps FabricTurnContext
8. **PipelineFactory** - FOCAL, LangGraph, Agno

### For Implementation (Phase 3: Toolbox)

9. **[TOOLBOX_SPEC.md](TOOLBOX_SPEC.md)** - Toolbox, ToolGateway
10. **[04-side-effect-policy.md](topics/04-side-effect-policy.md)** - SideEffectPolicy
11. **[12-idempotency.md](topics/12-idempotency.md)** - Three-layer idempotency

---

## Key Concepts

### Supersede: Facts vs Decisions

ACF provides **facts** (`has_pending_messages()`), Pipeline makes **decisions**.

```python
# ACF provides fact
if await ctx.has_pending_messages():
    # Pipeline decides
    if tool_metadata.is_irreversible:
        return SupersedeAction.SUPERSEDE

class SupersedeAction(str, Enum):
    """The four possible actions when new message arrives during processing."""
    SUPERSEDE = "supersede"       # Cancel current, start new turn with all messages
    ABSORB = "absorb"             # Add message to current turn, may restart from checkpoint
    QUEUE = "queue"               # Finish current turn, process new as separate turn
    FORCE_COMPLETE = "force_complete"  # Almost done, just finish current
```

### Toolbox Owns Tool Execution (v3.0)

**Critical change from v2.0**: Tool execution moved from ACF to Toolbox.

| Old (v2.0) | New (v3.0) |
|------------|------------|
| `ctx.callbacks.authorize_tool()` | `ctx.toolbox.execute()` |
| `ctx.callbacks.execute_tool()` | `ctx.toolbox.execute()` |
| `ctx.callbacks.record_side_effect()` | Toolbox emits FabricEvent |
| ACF owns SideEffectLedger | ACF stores events in LogicalTurn |

### FabricEvents: Single Write Path

```
Toolbox/Pipeline → emit_event() → ACF EventRouter → TurnManager
                                                  → AuditStore
                                                  → Live UI listeners
```

No direct Toolbox → TurnManager calls. Events are the glue.

### Channel Facts vs Policies

| Type | Example | Who Owns |
|------|---------|----------|
| **Capability** (fact) | WhatsApp max 4096 chars | ACF |
| **Policy** (behavior) | Wait 1200ms on WhatsApp | Configurable |

---

## Architecture Diagram (v3.0)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            CHANNEL ADAPTERS                                   │
│          (WhatsApp, SMS, Web, Email, Voice, Telegram, Slack, Teams)          │
│                    AG-UI is just one webchat adapter                          │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     AGENT CONVERSATION FABRIC (ACF)                           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    LogicalTurnWorkflow (Hatchet)                        │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐ ┌─────────────┐  │  │
│  │  │   acquire    │→│  accumulate  │→│  run_pipeline  │→│   commit    │  │  │
│  │  │  mutex (02)  │ │   (03,10)    │ │                │ │ & respond   │  │  │
│  │  └──────────────┘ └──────────────┘ └────────────────┘ └─────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ACF provides: FabricTurnContext (logical_turn, has_pending_messages, emit)  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AGENT RUNTIME                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  AgentRuntime.get_or_create(tenant_id, agent_id) → AgentContext        │  │
│  │  AgentContext = { agent, pipeline, toolbox, channel_bindings }          │  │
│  │  AgentTurnContext = FabricTurnContext + AgentContext                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    COGNITIVE PIPELINE (FOCAL/LangGraph/Agno)                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│  │  P1  │→│  P2  │→│  P3  │→│  P4  │→│  P7  │→│  P8  │→│ P11  │            │
│  │      │ │      │ │      │ │      │ │Tools │ │      │ │      │            │
│  │      │ │      │ │      │ │      │ │  ↓   │ │      │ │      │            │
│  └──────┘ └──────┘ └──────┘ └──────┘ │Toolbx│ └──────┘ └──────┘            │
│                                      └──────┘                               │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              TOOLBOX                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  ctx.toolbox.execute(planned_tool, ctx) → ToolResult                    │  │
│  │  Knows tool metadata (SideEffectPolicy, requires_confirmation)          │  │
│  │  Emits FabricEvents for side effects                                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            TOOL GATEWAY                                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                    │
│  │   Composio    │  │     HTTP      │  │   Internal    │                    │
│  │   Provider    │  │   Provider    │  │   Provider    │                    │
│  └───────────────┘  └───────────────┘  └───────────────┘                    │
│  + Idempotency Cache (Redis)                                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Reference

```toml
# === ACF Core ===
[acf]
enabled = true

# === Session Mutex (02) ===
[acf.mutex]
backend = "redis"
ttl_ms = 30000
blocking_timeout_ms = 5000

# === Aggregation (03) ===
[acf.aggregation]
mode = "adaptive"  # off | fixed | adaptive
default_window_ms = 800

# === Agent Runtime ===
[agent_runtime]
max_cache_size = 1000
cache_ttl_seconds = 3600

# === Toolbox ===
[toolbox]
default_idempotency_ttl = 86400  # 24 hours
max_batch_size = 10

# === Tool Gateway ===
[tool_gateway.providers.composio]
api_key_env = "COMPOSIO_API_KEY"

[tool_gateway.idempotency]
backend = "redis"
key_prefix = "tool_idem"
```

---

## Related Documents

### Current
- [ACF_ARCHITECTURE.md](ACF_ARCHITECTURE.md) - Canonical architecture (v3.0)
- [AGENT_RUNTIME_SPEC.md](AGENT_RUNTIME_SPEC.md) - Agent lifecycle
- [TOOLBOX_SPEC.md](TOOLBOX_SPEC.md) - Tool execution
- [ACF_SPEC.md](ACF_SPEC.md) - Detailed ACF mechanics
- [LOGICAL_TURN_VISION.md](LOGICAL_TURN_VISION.md) - Founding vision

### Historical (Archived in `../old/`)
- Original analysis documents
