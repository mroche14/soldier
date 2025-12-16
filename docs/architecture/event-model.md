# Event Model Specification

> **Date**: 2025-12-16
> **Status**: AUTHORITATIVE
> **Supersedes**: Previous FabricEvent definitions

---

## Overview

ACF uses a **flat event model** with **category-based filtering**:

- Event types use format: `{category}.{event_name}`
- Categories enable pattern-based subscription
- AG-UI mapping is handled by channel adapters (not ACF core)

---

## ACFEvent Model

```python
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class ACFEventType(str, Enum):
    """
    Event types with category prefix.

    Format: {category}.{event_name}
    Categories enable pattern-based subscription and filtering.
    """

    # ─────────────────────────────────────────────────────────────
    # Turn lifecycle
    # ─────────────────────────────────────────────────────────────
    TURN_STARTED = "turn.started"
    TURN_COMPLETED = "turn.completed"
    TURN_FAILED = "turn.failed"
    MESSAGE_ABSORBED = "turn.message_absorbed"
    TURN_SUPERSEDED = "turn.superseded"

    # ─────────────────────────────────────────────────────────────
    # Tool execution
    # ─────────────────────────────────────────────────────────────
    TOOL_AUTHORIZED = "tool.authorized"
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # ─────────────────────────────────────────────────────────────
    # Supersede coordination
    # ─────────────────────────────────────────────────────────────
    SUPERSEDE_REQUESTED = "supersede.requested"
    SUPERSEDE_DECISION = "supersede.decision"
    SUPERSEDE_EXECUTED = "supersede.executed"

    # ─────────────────────────────────────────────────────────────
    # Commit points
    # ─────────────────────────────────────────────────────────────
    COMMIT_REACHED = "commit.reached"

    # ─────────────────────────────────────────────────────────────
    # Enforcement
    # ─────────────────────────────────────────────────────────────
    ENFORCEMENT_VIOLATION = "enforcement.violation"

    # ─────────────────────────────────────────────────────────────
    # Session lifecycle
    # ─────────────────────────────────────────────────────────────
    SESSION_CREATED = "session.created"
    SESSION_RESUMED = "session.resumed"
    SESSION_CLOSED = "session.closed"

    # ─────────────────────────────────────────────────────────────
    # Internal (ACF only - not exposed to listeners)
    # ─────────────────────────────────────────────────────────────
    MUTEX_ACQUIRED = "mutex.acquired"
    MUTEX_RELEASED = "mutex.released"
    MUTEX_EXTENDED = "mutex.extended"


class ACFEvent(BaseModel):
    """
    ACF infrastructure event.

    Flat model with category-based filtering. Event types use
    format: {category}.{event_name}

    Naming: Previously called FabricEvent. Renamed to ACFEvent
    for clarity.
    """

    # ─────────────────────────────────────────────────────────────
    # Event Identity
    # ─────────────────────────────────────────────────────────────
    type: ACFEventType
    logical_turn_id: UUID
    session_key: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ─────────────────────────────────────────────────────────────
    # Event-specific payload
    # ─────────────────────────────────────────────────────────────
    payload: dict[str, Any] = Field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────
    # Optional routing context
    # ─────────────────────────────────────────────────────────────
    tenant_id: UUID | None = None
    agent_id: UUID | None = None
    interlocutor_id: UUID | None = None

    # ─────────────────────────────────────────────────────────────
    # Computed Properties
    # ─────────────────────────────────────────────────────────────
    @property
    def category(self) -> str:
        """
        Extract category from event type.

        Example: 'turn.started' → 'turn'
        """
        return self.type.value.split(".")[0]

    @property
    def event_name(self) -> str:
        """
        Extract event name from event type.

        Example: 'turn.started' → 'started'
        """
        parts = self.type.value.split(".", 1)
        return parts[1] if len(parts) > 1 else parts[0]

    def matches_pattern(self, pattern: str) -> bool:
        """
        Check if event matches a pattern.

        Patterns:
            - "*" → matches all events
            - "category.*" → matches all events in category
            - "category.name" → exact match

        Examples:
            - event.matches_pattern("*") → True (always)
            - event.matches_pattern("turn.*") → True if category is "turn"
            - event.matches_pattern("turn.started") → True if exact match
        """
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return self.category == pattern[:-2]
        return self.type.value == pattern
```

---

## Event Categories

| Category | Events | Emitter | Description |
|----------|--------|---------|-------------|
| `turn` | started, completed, failed, message_absorbed, superseded | ACF | Turn lifecycle |
| `tool` | authorized, executed, failed | Toolbox | Tool execution |
| `supersede` | requested, decision, executed | ACF | Supersede coordination |
| `commit` | reached | ACF | Commit point tracking |
| `enforcement` | violation | Brain | Policy violations |
| `session` | created, resumed, closed | ACF | Session lifecycle |
| `mutex` | acquired, released, extended | ACF | Internal only |

---

## Pattern-Based Subscription

```python
# Subscribe to all turn events
router.register_listener("turn.*", my_listener)

# Subscribe to specific event
router.register_listener("tool.executed", tool_listener)

# Subscribe to all events
router.register_listener("*", audit_listener)
```

**Implementation:**

```python
class EventRouter:
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}

    def register_listener(self, pattern: str, listener: Callable):
        """Register a listener for events matching pattern."""
        if pattern not in self._listeners:
            self._listeners[pattern] = []
        self._listeners[pattern].append(listener)

    async def emit(self, event: ACFEvent):
        """Emit event to all matching listeners."""
        for pattern, listeners in self._listeners.items():
            if event.matches_pattern(pattern):
                for listener in listeners:
                    await listener(event)
```

---

## Event Payloads

### Turn Events

**turn.started**
```python
{
    "message": str,           # User message
    "channel": str,           # Channel identifier
    "metadata": dict          # Channel-specific metadata
}
```

**turn.completed**
```python
{
    "response_segments": list[dict],  # Response parts
    "artifacts": dict,                # Brain artifacts
    "duration_ms": int                # Total duration
}
```

**turn.failed**
```python
{
    "error": str,             # Error message
    "error_type": str,        # Error class name
    "traceback": str | None   # Stack trace (debug only)
}
```

**turn.message_absorbed**
```python
{
    "message": str,           # Absorbed message
    "aggregation_count": int  # Total messages in turn
}
```

**turn.superseded**
```python
{
    "superseded_by": str,     # Newer logical_turn_id
    "reason": str             # Why superseded
}
```

### Tool Events

**tool.authorized**
```python
{
    "tool_name": str,
    "tool_id": str,
    "side_effect_policy": str,  # "none", "reversible", "irreversible"
    "parameters": dict
}
```

**tool.executed**
```python
{
    "tool_name": str,
    "tool_id": str,
    "result": Any,
    "duration_ms": int,
    "idempotency_key": str | None
}
```

**tool.failed**
```python
{
    "tool_name": str,
    "tool_id": str,
    "error": str,
    "error_type": str
}
```

### Supersede Events

**supersede.requested**
```python
{
    "current_turn_id": str,
    "new_message": str,
    "time_since_start_ms": int
}
```

**supersede.decision**
```python
{
    "decision": str,          # "allow", "deny", "queued"
    "reason": str,
    "has_irreversible": bool
}
```

**supersede.executed**
```python
{
    "superseded_turn_id": str,
    "new_turn_id": str
}
```

### Commit Events

**commit.reached**
```python
{
    "tool_name": str,
    "tool_id": str,
    "side_effect_policy": str,
    "commit_point": str       # Description of commit
}
```

### Enforcement Events

**enforcement.violation**
```python
{
    "policy_name": str,
    "violation_type": str,
    "blocked_action": str,
    "reason": str
}
```

### Session Events

**session.created**
```python
{
    "session_key": str,
    "channel": str,
    "interlocutor_id": str | None
}
```

**session.resumed**
```python
{
    "session_key": str,
    "last_turn_at": str,      # ISO timestamp
    "turn_count": int
}
```

**session.closed**
```python
{
    "session_key": str,
    "reason": str,            # "timeout", "explicit", "error"
    "total_turns": int
}
```

---

## AG-UI Mapping

AG-UI compatibility is handled by channel adapters, not ACF core.

| ACFEvent | AG-UI Event | Notes |
|----------|-------------|-------|
| turn.started | RUN_STARTED | Turn begins |
| turn.completed | RUN_FINISHED | Turn ends successfully |
| turn.failed | RUN_ERROR | Turn ends with error |
| tool.authorized | TOOL_CALL_START | Tool execution begins |
| tool.executed | TOOL_CALL_END | Tool succeeds |
| tool.failed | TOOL_CALL_END | Tool fails (with error) |

**See**: `docs/acf/analysis/ag_ui_considerations.md` for full AG-UI integration details.

---

## Event Persistence

### AuditStore Schema

```python
class PersistedEvent(BaseModel):
    """Event record in AuditStore."""

    # Event identity
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str           # e.g., "turn.started"
    timestamp: datetime

    # Routing context
    tenant_id: UUID | None
    agent_id: UUID | None
    session_key: str
    logical_turn_id: UUID
    interlocutor_id: UUID | None

    # Event data
    payload: dict[str, Any]

    # Derived for querying
    category: str             # "turn", "tool", etc.
    event_name: str           # "started", "executed", etc.
```

### Indexing Strategy

```sql
-- Primary access pattern: query by turn
CREATE INDEX idx_events_turn ON events(logical_turn_id, timestamp);

-- Query by tenant and category
CREATE INDEX idx_events_tenant_category ON events(tenant_id, category, timestamp);

-- Query by session
CREATE INDEX idx_events_session ON events(session_key, timestamp);

-- Time-based cleanup
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

### Retention Policy

| Category | Retention | Rationale |
|----------|-----------|-----------|
| `turn` | 90 days | Business analytics, debugging |
| `tool` | 90 days | Audit trail, compliance |
| `supersede` | 30 days | Debugging only |
| `commit` | 90 days | Audit trail |
| `enforcement` | 90 days | Compliance |
| `session` | 90 days | Analytics |
| `mutex` | 7 days | Debugging only |

---

## Configuration

```toml
[acf.events]
# Event routing
enabled = true
audit_store_enabled = true
live_ui_enabled = true
metrics_enabled = true

# Filtering
max_payload_size_bytes = 65536    # 64KB

# Rate limiting (per tenant per minute)
max_events_per_minute = 10000

# Retention
default_retention_days = 90
debug_event_retention_days = 30   # mutex, supersede
```

---

## Migration from FabricEvent

`FabricEvent` and `FabricEventType` are deprecated aliases for backward compatibility.
Use `ACFEvent` and `ACFEventType` in new code.

### Name Changes

| Old | New |
|-----|-----|
| FabricEvent | ACFEvent |
| FabricEventType | ACFEventType |

### Event Type Changes

| Old FabricEventType | New ACFEventType | Value |
|---------------------|------------------|-------|
| TURN_STARTED | TURN_STARTED | "turn.started" |
| TURN_COMPLETED | TURN_COMPLETED | "turn.completed" |
| TURN_FAILED | TURN_FAILED | "turn.failed" |
| MESSAGE_ABSORBED | MESSAGE_ABSORBED | "turn.message_absorbed" |
| TURN_SUPERSEDED | TURN_SUPERSEDED | "turn.superseded" |
| TOOL_AUTHORIZED | TOOL_AUTHORIZED | "tool.authorized" |
| TOOL_EXECUTED | TOOL_EXECUTED | "tool.executed" |
| TOOL_FAILED | TOOL_FAILED | "tool.failed" |
| SUPERSEDE_REQUESTED | SUPERSEDE_REQUESTED | "supersede.requested" |
| SUPERSEDE_DECISION | SUPERSEDE_DECISION | "supersede.decision" |
| SUPERSEDE_EXECUTED | SUPERSEDE_EXECUTED | "supersede.executed" |
| COMMIT_REACHED | COMMIT_REACHED | "commit.reached" |
| ENFORCEMENT_VIOLATION | ENFORCEMENT_VIOLATION | "enforcement.violation" |

### Code Migration

**Before:**
```python
from ruche.runtime.acf.events import FabricEvent, FabricEventType

event = FabricEvent(
    type=FabricEventType.TURN_STARTED,
    logical_turn_id=turn_id,
    session_key=session_key,
    payload={"message": "Hello"}
)
```

**After:**
```python
from ruche.runtime.acf.events import ACFEvent, ACFEventType

event = ACFEvent(
    type=ACFEventType.TURN_STARTED,
    logical_turn_id=turn_id,
    session_key=session_key,
    payload={"message": "Hello"}
)
```

---

## Summary

**Key Design Decisions:**

1. **Flat model** - No two-layer abstraction, single ACFEvent type
2. **Category-based** - Event types use `{category}.{event_name}` format
3. **Pattern matching** - Subscribe to `category.*` or specific events
4. **Channel adapters** - AG-UI mapping handled outside ACF core
5. **Simple payloads** - Event-specific dictionaries, no rigid schemas

**Benefits:**

- Simpler mental model (one event type, not two)
- Flexible subscription with pattern matching
- Easy to extend with new categories
- Clear separation between ACF events and channel-specific protocols

---

*Document updated: 2025-12-16*
*Supersedes: Previous FabricEvent and AgentEvent/ACFEvent two-layer model*
