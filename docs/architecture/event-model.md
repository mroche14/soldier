# Event Model Specification

> **Date**: 2025-12-15
> **Status**: AUTHORITATIVE
> **Scope**: AgentEvent (semantic) + ACFEvent (transport)
> **Supersedes**: Previous FabricEvent definitions in ACF_SPEC.md, ACF_ARCHITECTURE.md

---

## Executive Summary

The Ruche platform uses a **two-layer event model**:

| Layer | Name | Owner | Purpose |
|-------|------|-------|---------|
| **Semantic** | `AgentEvent` | Brains, Toolbox | What happened (business meaning) |
| **Transport** | `ACFEvent` | ACF | Routing, persistence, delivery |

**Key Principle**: ACF routes events but does NOT interpret them, except for reserved `infra.*` events needed for infrastructure invariants.

---

## 1. AgentEvent (Semantic Layer)

### 1.1 Purpose

`AgentEvent` represents **what happened** in terms that builders and observers care about:
- Scenario activated
- Tool executed
- Policy blocked an action
- Custom brain-specific events

Brains and Toolbox emit AgentEvents. ACF wraps them in ACFEvent for routing.

### 1.2 Model Definition

```python
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class AgentEventCategory(str, Enum):
    """
    Top-level event categories.

    Used for routing, filtering, and access control.
    """
    INFRA = "infra"         # Reserved for ACF/Toolbox infrastructure
    SCENARIO = "scenario"   # Scenario lifecycle events
    TOOL = "tool"           # Tool planning/execution (semantic, not infra)
    RULE = "rule"           # Rule matching events
    POLICY = "policy"       # Policy/enforcement events
    MEMORY = "memory"       # Memory operations
    CUSTOM = "custom"       # Brain-specific custom events


class AgentEvent(BaseModel):
    """
    Semantic event emitted by Brains and Toolbox.

    This is the canonical event that builders care about.
    ACF wraps this in ACFEvent for transport but does NOT
    interpret the payload (except for infra.* events).
    """

    # ─────────────────────────────────────────────────────────────
    # Event Identity
    # ─────────────────────────────────────────────────────────────
    category: AgentEventCategory
    event_type: str  # e.g., "activated", "completed", "blocked"

    # ─────────────────────────────────────────────────────────────
    # Payload (category-specific, ACF passes through)
    # ─────────────────────────────────────────────────────────────
    payload: dict[str, Any] = Field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────────
    severity: Literal["debug", "info", "warn", "error"] = "info"
    schema_version: str = "1.0"  # For client compatibility

    # ─────────────────────────────────────────────────────────────
    # Computed Properties
    # ─────────────────────────────────────────────────────────────
    @property
    def full_type(self) -> str:
        """
        Fully qualified event type.

        Examples:
            - "infra.turn.started"
            - "scenario.activated"
            - "tool.execution.completed"
            - "custom.alignment.rule_matched"
        """
        return f"{self.category.value}.{self.event_type}"

    def matches(self, pattern: str) -> bool:
        """
        Check if event matches a pattern.

        Patterns:
            - "infra.*" → matches all infra events
            - "scenario.activated" → exact match
            - "tool.*" → matches all tool events
        """
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return self.full_type.startswith(prefix + ".")
        return self.full_type == pattern
```

### 1.3 Event Categories

| Category | Emitter | Description | Example Event Types |
|----------|---------|-------------|---------------------|
| `infra` | ACF, Toolbox | Infrastructure events (reserved) | `turn.started`, `tool.completed` |
| `scenario` | Brain | Scenario lifecycle | `activated`, `step.entered`, `completed` |
| `tool` | Brain | Tool planning (semantic) | `planned`, `confirmed`, `skipped` |
| `rule` | Brain | Rule matching | `matched`, `filtered`, `applied` |
| `policy` | Brain | Policy enforcement | `checked`, `blocked`, `overridden` |
| `memory` | Brain | Memory operations | `entity.created`, `episode.stored` |
| `custom` | Brain | Brain-specific | `alignment.context_extracted`, etc. |

---

## 2. ACFEvent (Transport Layer)

### 2.1 Purpose

`ACFEvent` is the **transport envelope** that ACF uses to:
- Route events to appropriate listeners
- Persist events to AuditStore
- Deliver events to live UI streams
- Track events within a logical turn

ACF reads routing keys but does NOT interpret `AgentEvent` payloads (except `infra.*`).

### 2.2 Model Definition

```python
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class ACFEvent(BaseModel):
    """
    Transport envelope for AgentEvents.

    ACF routes and persists ACFEvents. It uses routing keys for
    delivery but does NOT interpret the inner AgentEvent payload
    (except for reserved infra.* events needed for invariants).

    Naming: Previously called FabricEvent. Renamed to ACFEvent for
    clarity that this is the ACF transport layer.
    """

    # ─────────────────────────────────────────────────────────────
    # Event Identity
    # ─────────────────────────────────────────────────────────────
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ─────────────────────────────────────────────────────────────
    # Routing Keys (ACF uses these for delivery)
    # ─────────────────────────────────────────────────────────────
    tenant_id: UUID
    agent_id: UUID
    session_key: str
    logical_turn_id: UUID | None = None
    channel: str | None = None
    trace_id: str

    # ─────────────────────────────────────────────────────────────
    # The Semantic Event (ACF passes through)
    # ─────────────────────────────────────────────────────────────
    event: AgentEvent

    # ─────────────────────────────────────────────────────────────
    # Computed Properties
    # ─────────────────────────────────────────────────────────────
    @property
    def is_infra_event(self) -> bool:
        """
        Check if this is an infrastructure event.

        ACF interprets infra.* events for its invariants
        (side effect tracking, commit points, etc.)
        """
        return self.event.category == AgentEventCategory.INFRA

    @property
    def full_type(self) -> str:
        """Delegate to inner AgentEvent."""
        return self.event.full_type
```

### 2.3 Routing Keys

| Key | Purpose | Used By |
|-----|---------|---------|
| `tenant_id` | Tenant isolation | All listeners |
| `agent_id` | Agent-specific routing | Agent dashboards |
| `session_key` | Session-specific delivery | Live UI |
| `logical_turn_id` | Turn correlation | TurnManager |
| `channel` | Channel-specific handling | ChannelGateway |
| `trace_id` | Distributed tracing | Observability |

---

## 3. Reserved Infrastructure Events

### 3.1 The `infra.*` Namespace

ACF reserves the `infra` category for events it needs to interpret for infrastructure invariants. **Brains MUST NOT emit arbitrary infra.* events** (only Toolbox can emit `infra.tool.*`).

### 3.2 Reserved Event Types

```python
RESERVED_INFRA_EVENTS = {
    # ─────────────────────────────────────────────────────────────
    # Turn Lifecycle (ACF emits)
    # ─────────────────────────────────────────────────────────────
    "infra.turn.started",      # Logical turn processing began
    "infra.turn.completed",    # Turn successfully completed
    "infra.turn.superseded",   # Turn cancelled by newer message
    "infra.turn.queued",       # Turn queued (GROUP_ROUND_ROBIN)
    "infra.turn.failed",       # Turn failed with error

    # ─────────────────────────────────────────────────────────────
    # Message Handling (ACF emits)
    # ─────────────────────────────────────────────────────────────
    "infra.message.received",   # Raw message received
    "infra.message.absorbed",   # Message absorbed into existing turn
    "infra.message.aggregated", # Aggregation window closed

    # ─────────────────────────────────────────────────────────────
    # Concurrency (ACF emits)
    # ─────────────────────────────────────────────────────────────
    "infra.concurrency.acquired",  # Session concurrency slot acquired
    "infra.concurrency.released",  # Session concurrency slot released
    "infra.concurrency.waiting",   # Waiting in queue

    # ─────────────────────────────────────────────────────────────
    # Tool Side Effects (Toolbox emits, ACF stores)
    # ─────────────────────────────────────────────────────────────
    "infra.tool.started",     # Tool execution started
    "infra.tool.completed",   # Tool execution completed successfully
    "infra.tool.failed",      # Tool execution failed

    # ─────────────────────────────────────────────────────────────
    # Commit Points (ACF emits)
    # ─────────────────────────────────────────────────────────────
    "infra.commit.reached",   # Irreversible side effect executed
    "infra.commit.approved",  # All mutations committed

    # ─────────────────────────────────────────────────────────────
    # Brain (Brain emits via ACF callback)
    # ─────────────────────────────────────────────────────────────
    "infra.brain.started",   # Brain execution started
    "infra.brain.completed", # Brain execution completed
    "infra.brain.error",     # Brain encountered error
}
```

### 3.3 Why ACF Interprets `infra.*` Events

| Event | ACF Action |
|-------|------------|
| `infra.tool.completed` | Store in `LogicalTurn.side_effects` |
| `infra.commit.reached` | Mark turn as non-supersedable |
| `infra.turn.superseded` | Cancel current workflow |
| `infra.concurrency.*` | Metrics, debugging |

---

## 4. Event Emission API

### 4.1 Brain Context Interface

```python
class BrainTurnContext(Protocol):
    """Context passed to Brain.process_turn()"""

    async def emit_event(self, event: AgentEvent) -> None:
        """
        Emit a semantic event.

        ACF wraps this in ACFEvent and routes it.

        Args:
            event: The semantic event to emit

        Example:
            await ctx.emit_event(AgentEvent(
                category=AgentEventCategory.SCENARIO,
                event_type="activated",
                payload={"scenario_id": str(scenario.id)}
            ))
        """
        ...
```

### 4.2 Emission Examples

```python
# ─────────────────────────────────────────────────────────────────
# Brain: Scenario activated
# ─────────────────────────────────────────────────────────────────
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.SCENARIO,
    event_type="activated",
    payload={
        "scenario_id": str(scenario.id),
        "scenario_name": scenario.name,
        "entry_step": "greeting",
    }
))
# → full_type: "scenario.activated"


# ─────────────────────────────────────────────────────────────────
# Brain: Rule matched
# ─────────────────────────────────────────────────────────────────
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.RULE,
    event_type="matched",
    payload={
        "rule_id": str(rule.id),
        "rule_name": rule.name,
        "confidence": 0.92,
        "trigger_text": "I want a refund",
    }
))
# → full_type: "rule.matched"


# ─────────────────────────────────────────────────────────────────
# Brain: Policy blocked action
# ─────────────────────────────────────────────────────────────────
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.POLICY,
    event_type="blocked",
    severity="warn",
    payload={
        "policy_name": "max_refund_amount",
        "blocked_action": "approve_refund",
        "reason": "Amount exceeds $500 limit",
    }
))
# → full_type: "policy.blocked"


# ─────────────────────────────────────────────────────────────────
# Toolbox: Tool execution completed (infra event)
# ─────────────────────────────────────────────────────────────────
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.INFRA,
    event_type="tool.completed",
    payload={
        "tool_name": "create_order",
        "tool_id": str(tool_binding.tool_id),
        "side_effect_policy": "irreversible",
        "idempotency_key": "order:tenant:12345",
        "execution_time_ms": 234,
        "result_summary": "Order #12345 created",
    }
))
# → full_type: "infra.tool.completed"
# → ACF stores in LogicalTurn.side_effects


# ─────────────────────────────────────────────────────────────────
# Brain: Custom alignment-specific event
# ─────────────────────────────────────────────────────────────────
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.CUSTOM,
    event_type="alignment.context_extracted",
    payload={
        "intent": "request_refund",
        "entities": ["order_id", "reason"],
        "confidence": 0.88,
    }
))
# → full_type: "custom.alignment.context_extracted"
```

---

## 5. Event Routing Architecture

### 5.1 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Event Sources                                │
├──────────────────┬──────────────────┬───────────────────────────────┤
│      ACF         │      Brain       │         Toolbox               │
│ (infra.turn.*)   │ (scenario.*)     │ (infra.tool.*)                │
│ (infra.message.*)│ (rule.*)         │                               │
│ (infra.commit.*) │ (policy.*)       │                               │
│                  │ (memory.*)       │                               │
│                  │ (custom.*)       │                               │
└────────┬─────────┴────────┬─────────┴──────────────┬────────────────┘
         │                  │                        │
         │      ┌───────────┴───────────┐            │
         │      │  ctx.emit_event()     │            │
         │      │  (AgentEvent)         │            │
         │      └───────────┬───────────┘            │
         │                  │                        │
         └──────────────────┼────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │     ACF EventRouter         │
              │                             │
              │  1. Wrap in ACFEvent        │
              │  2. Add routing keys        │
              │  3. Route to listeners      │
              │  4. Interpret infra.* only  │
              └─────────────┬───────────────┘
                            │
        ┌───────────────────┼───────────────────┬──────────────────┐
        │                   │                   │                  │
        ▼                   ▼                   ▼                  ▼
┌───────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐
│  AuditStore   │  │  TurnManager   │  │ Live Listeners │  │   Metrics    │
│  (all events) │  │ (infra.tool.*) │  │ (UI streams)   │  │ (counters)   │
└───────────────┘  └────────────────┘  └────────────────┘  └──────────────┘
```

### 5.2 Routing Rules

| Event Pattern | AuditStore | TurnManager | Live UI | Metrics |
|---------------|------------|-------------|---------|---------|
| `infra.turn.*` | ✅ | ❌ | ✅ | ✅ |
| `infra.tool.*` | ✅ | ✅ (side effects) | ✅ | ✅ |
| `infra.commit.*` | ✅ | ✅ (commit flag) | ❌ | ✅ |
| `scenario.*` | ✅ | ❌ | ✅ | ✅ |
| `rule.*` | ✅ | ❌ | ✅ (debug) | ✅ |
| `policy.*` | ✅ | ❌ | ✅ | ✅ |
| `custom.*` | ✅ | ❌ | ✅ (filtered) | ❌ |

### 5.3 Event Filtering for Live UI

```python
class EventFilter(BaseModel):
    """Filter for live event subscriptions."""

    categories: list[AgentEventCategory] | None = None  # None = all
    patterns: list[str] | None = None  # e.g., ["scenario.*", "policy.blocked"]
    min_severity: Literal["debug", "info", "warn", "error"] = "info"

    def matches(self, event: AgentEvent) -> bool:
        # Severity check
        severity_order = ["debug", "info", "warn", "error"]
        if severity_order.index(event.severity) < severity_order.index(self.min_severity):
            return False

        # Category check
        if self.categories and event.category not in self.categories:
            return False

        # Pattern check
        if self.patterns:
            return any(event.matches(p) for p in self.patterns)

        return True
```

---

## 6. Event Persistence

### 6.1 AuditStore Schema

```python
class PersistedEvent(BaseModel):
    """Event record in AuditStore."""

    # From ACFEvent
    event_id: UUID
    timestamp: datetime
    tenant_id: UUID
    agent_id: UUID
    session_key: str
    logical_turn_id: UUID | None
    trace_id: str

    # From AgentEvent
    category: str
    event_type: str
    full_type: str  # Denormalized for queries
    severity: str
    payload: dict[str, Any]

    # Indexing
    # CREATE INDEX idx_events_tenant_turn ON events(tenant_id, logical_turn_id);
    # CREATE INDEX idx_events_full_type ON events(full_type);
    # CREATE INDEX idx_events_timestamp ON events(timestamp);
```

### 6.2 Retention Policy

| Category | Retention | Rationale |
|----------|-----------|-----------|
| `infra.*` | 90 days | Debugging, compliance |
| `scenario.*` | 90 days | Business analytics |
| `tool.*` | 90 days | Audit trail |
| `rule.*` | 30 days | Debugging only |
| `policy.*` | 90 days | Compliance |
| `custom.*` | 30 days | Brain-specific |

---

## 7. Versioning Strategy

### 7.1 Schema Version

Each `AgentEvent` carries a `schema_version` field:

```python
await ctx.emit_event(AgentEvent(
    category=AgentEventCategory.SCENARIO,
    event_type="activated",
    schema_version="1.1",  # Payload schema version
    payload={...}
))
```

### 7.2 Compatibility Rules

| Change Type | Version Bump | Client Impact |
|-------------|--------------|---------------|
| Add optional field | Patch (1.0.1) | None |
| Add required field | Minor (1.1.0) | Must handle missing |
| Remove field | Major (2.0.0) | Breaking |
| Change field type | Major (2.0.0) | Breaking |

### 7.3 Client Handling

```python
def handle_scenario_event(event: AgentEvent):
    if event.schema_version.startswith("1."):
        # v1.x handling
        scenario_id = event.payload.get("scenario_id")
    elif event.schema_version.startswith("2."):
        # v2.x handling (hypothetical)
        scenario_id = event.payload.get("scenario", {}).get("id")
```

---

## 8. Configuration

```toml
[acf.events]
# Event routing
enabled = true
audit_store_enabled = true
live_ui_enabled = true
metrics_enabled = true

# Filtering
default_severity_filter = "info"  # debug, info, warn, error
max_payload_size_bytes = 65536    # 64KB

# Rate limiting (per tenant per minute)
max_events_per_minute = 10000
max_custom_events_per_minute = 1000

# Retention
default_retention_days = 90
custom_event_retention_days = 30
```

---

## 9. Migration from FabricEvent

### 9.1 Rename Mapping

| Old Name | New Name |
|----------|----------|
| `FabricEvent` | `ACFEvent` |
| `FabricEventType` | Removed (use `AgentEvent.full_type`) |
| `FabricTurnContext.emit_event()` | `BrainTurnContext.emit_event()` |

### 9.2 Event Type Mapping

| Old FabricEventType | New AgentEvent |
|---------------------|----------------|
| `TURN_STARTED` | `infra.turn.started` |
| `TURN_COMPLETED` | `infra.turn.completed` |
| `TURN_SUPERSEDED` | `infra.turn.superseded` |
| `MESSAGE_RECEIVED` | `infra.message.received` |
| `MESSAGE_ABSORBED` | `infra.message.absorbed` |
| `TOOL_SIDE_EFFECT_STARTED` | `infra.tool.started` |
| `TOOL_SIDE_EFFECT_COMPLETED` | `infra.tool.completed` |
| `TOOL_SIDE_EFFECT_FAILED` | `infra.tool.failed` |
| `COMMIT_APPROVED` | `infra.commit.approved` |
| `PIPELINE_STARTED` | `infra.brain.started` |
| `PIPELINE_COMPLETED` | `infra.brain.completed` |
| `PIPELINE_ERROR` | `infra.brain.error` |
| `STATUS_UPDATE` | `custom.{brain}.status_update` |

### 9.3 Files Requiring Update

The following files reference `FabricEvent` and need updating to `ACFEvent`:

- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/acf/architecture/TOOLBOX_SPEC.md`
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- `docs/acf/architecture/topics/01-logical-turn.md`
- `docs/acf/architecture/topics/02-session-mutex.md`
- `docs/acf/architecture/topics/04-side-effect-policy.md`
- `docs/acf/architecture/topics/06-hatchet-integration.md`
- `docs/acf/README.md`
- `docs/acf/architecture/README.md`

---

## 10. Summary

| Aspect | AgentEvent | ACFEvent |
|--------|------------|----------|
| **Layer** | Semantic | Transport |
| **Owner** | Brains, Toolbox | ACF |
| **Contains** | Business meaning | Routing keys + AgentEvent |
| **Interpreted by** | Observers, UI | ACF (routing only) |
| **Extensible** | Yes (custom.*) | No (fixed schema) |
| **Versioned** | Yes (schema_version) | No |

**Key Decisions:**
1. `AgentEvent` is canonical (what builders care about)
2. `ACFEvent` is transport (routing envelope)
3. `infra.*` namespace reserved for ACF/Toolbox infrastructure events
4. ACF routes all events but only interprets `infra.*`
5. Brains can emit custom events freely via `custom.*` category

---

*Document created: 2025-12-15*
*Supersedes: FabricEvent definitions in ACF_SPEC.md, ACF_ARCHITECTURE.md*
