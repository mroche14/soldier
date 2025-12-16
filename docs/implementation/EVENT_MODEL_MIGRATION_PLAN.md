# Event Model Migration Plan: FabricEvent → ACFEvent

> **Date**: 2025-12-16
> **Status**: READY FOR EXECUTION
> **Estimated Total Effort**: 6-10 hours
> **Parallelizable**: Yes (by phase and by file group)

---

## Executive Summary

This plan migrates the event system from `FabricEvent`/`FabricEventType` to `ACFEvent`/`ACFEventType` with category-based filtering, while maintaining AG-UI compatibility path.

**Key Decisions:**
1. Keep **flat model** (not two-layer AgentEvent + ACFEvent)
2. Add **category prefix** to event type values (e.g., `"turn.started"`)
3. Add **computed properties** for category-based filtering
4. **Defer** full AG-UI streaming events until webchat is priority

---

## Phase 1: Rename Only

**Effort**: 1-2 hours
**Risk**: Low
**Parallelizable**: Yes (3 groups)

### Group 1A: Core Event Module

**Files:**
- `ruche/runtime/acf/events.py`

**Changes:**
```python
# Rename classes
FabricEventType → ACFEventType
FabricEvent → ACFEvent

# Add backward compatibility aliases at end of file
FabricEventType = ACFEventType  # Deprecated alias
FabricEvent = ACFEvent  # Deprecated alias
```

**Verification:**
```bash
uv run python -c "from ruche.runtime.acf.events import ACFEvent, ACFEventType, FabricEvent, FabricEventType; print('OK')"
```

---

### Group 1B: ACF Infrastructure

**Files:**
- `ruche/runtime/acf/__init__.py`
- `ruche/runtime/acf/models.py`
- `ruche/runtime/acf/event_router.py`
- `ruche/runtime/acf/workflow.py`

**Changes for `__init__.py`:**
```python
# Line 20: Update import
from ruche.runtime.acf.events import ACFEvent, ACFEventType

# Lines 69-70: Update __all__
"ACFEvent",
"ACFEventType",
```

**Changes for `models.py`:**
```python
# Line 238: Update type hint
async def emit_event(self, event: "ACFEvent") -> None:

# Line 239: Update docstring
"""Emit an ACFEvent for routing/persistence.

# Line 262: Update type hint
_route_event: Callable[["ACFEvent"], Awaitable[None]]

# Line 268: Update type hint
async def emit_event(self, event: "ACFEvent") -> None:
```

**Changes for `event_router.py`:**
```python
# Line 18: Update import
from ruche.runtime.acf.events import ACFEvent

# Line 27: Update docstring
Event listeners are async callables that receive an ACFEvent.

# Line 35: Update type hint
async def __call__(self, event: ACFEvent) -> None:

# Lines 120, 171, 218, 238: Update all ACFEvent type hints

# Line 249: Update comment
# Currently, ACFEvent uses the enum-based type system

# Line 255: Update import
from ruche.runtime.acf.events import ACFEventType
```

**Changes for `workflow.py`:**
```python
# Line 260: Update local import
from ruche.runtime.acf.events import ACFEvent, ACFEventType

# Line 329: Update local import
from ruche.runtime.acf.events import ACFEvent, ACFEventType

# Line 525: Update local import
from ruche.runtime.acf.events import ACFEvent

# Line 527: Update isinstance check
if not isinstance(event, ACFEvent):
```

**Verification:**
```bash
uv run python -c "from ruche.runtime.acf import ACFEvent, ACFEventType; print('OK')"
```

---

### Group 1C: Runtime and Toolbox

**Files:**
- `ruche/runtime/__init__.py`
- `ruche/runtime/toolbox/toolbox.py`
- `ruche/runtime/agent/context.py`

**Changes for `runtime/__init__.py`:**
```python
# Lines 43-44: Update imports
ACFEvent,
ACFEventType,

# Lines 126-127: Update __all__
"ACFEvent",
"ACFEventType",
```

**Changes for `toolbox/toolbox.py`:**
```python
# Line 27: Update TYPE_CHECKING import
from ruche.runtime.acf.events import ACFEvent, ACFEventType
```

**Changes for `agent/context.py`:**
```python
# Line 116: Update docstring
event: ACFEvent to emit (using Any to avoid forward reference issues)
```

**Verification:**
```bash
uv run python -c "from ruche.runtime import ACFEvent, ACFEventType; print('OK')"
```

---

### Group 1D: Tests

**Files:**
- `tests/unit/runtime/acf/test_event_router.py`

**Changes:**
```python
# Line 8: Update import
from ruche.runtime.acf.events import ACFEvent, ACFEventType

# All test functions: Replace FabricEvent → ACFEvent, FabricEventType → ACFEventType
# Approximately 50 occurrences
```

**Verification:**
```bash
uv run pytest tests/unit/runtime/acf/test_event_router.py -v
```

---

## Phase 2: Add Category Property

**Effort**: 2-4 hours
**Risk**: Low
**Parallelizable**: Yes (2 groups)

### Group 2A: Update Event Types

**File:** `ruche/runtime/acf/events.py`

**Changes:**

```python
class ACFEventType(str, Enum):
    """Event types with category prefix for filtering.

    Format: "{category}.{event_name}"
    Categories: turn, tool, supersede, commit, enforcement, session, mutex
    """

    # Turn lifecycle → category: turn
    TURN_STARTED = "turn.started"
    MESSAGE_ABSORBED = "turn.message_absorbed"
    TURN_COMPLETED = "turn.completed"
    TURN_FAILED = "turn.failed"

    # Supersede coordination → category: supersede
    SUPERSEDE_REQUESTED = "supersede.requested"
    SUPERSEDE_DECISION = "supersede.decision"
    SUPERSEDE_EXECUTED = "supersede.executed"

    # Commit points → category: commit
    COMMIT_POINT_REACHED = "commit.reached"

    # Tool execution → category: tool
    TOOL_AUTHORIZED = "tool.authorized"
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # Enforcement → category: enforcement
    ENFORCEMENT_VIOLATION = "enforcement.violation"

    # Session management → category: session
    SESSION_CREATED = "session.created"
    SESSION_RESUMED = "session.resumed"
    SESSION_CLOSED = "session.closed"

    # Mutex operations → category: mutex (internal, not streamed)
    MUTEX_ACQUIRED = "mutex.acquired"
    MUTEX_RELEASED = "mutex.released"
    MUTEX_EXTENDED = "mutex.extended"


class ACFEvent(BaseModel):
    """ACF event with category-based filtering support.

    The event type uses format "{category}.{event_name}" enabling:
    - Pattern matching: "turn.*" matches all turn events
    - Category filtering: event.category == "tool"
    - AG-UI mapping: category maps to AG-UI event groups
    """

    type: ACFEventType = Field(..., description="Event type in category.name format")
    logical_turn_id: UUID = Field(..., description="Associated turn")
    session_key: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )

    # Optional routing context
    tenant_id: UUID | None = Field(default=None)
    agent_id: UUID | None = Field(default=None)
    interlocutor_id: UUID | None = Field(default=None)

    @property
    def category(self) -> str:
        """Extract category from event type.

        Example: "turn.started" → "turn"
        """
        return self.type.value.split(".")[0]

    @property
    def event_name(self) -> str:
        """Extract event name without category.

        Example: "turn.started" → "started"
        """
        parts = self.type.value.split(".", 1)
        return parts[1] if len(parts) > 1 else parts[0]

    def matches_pattern(self, pattern: str) -> bool:
        """Check if event matches a pattern.

        Patterns:
        - "*" → matches all events
        - "turn.*" → matches all turn events
        - "turn.started" → exact match
        """
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return self.category == pattern[:-2]
        return self.type.value == pattern

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "type": "turn.started",
                "logical_turn_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_key": "tenant:agent:interlocutor:web",
                "timestamp": "2025-01-15T10:30:00Z",
                "payload": {"message_count": 1, "channel": "web"},
            }
        }
```

---

### Group 2B: Update Event Router

**File:** `ruche/runtime/acf/event_router.py`

**Changes to `_find_matching_listeners` method:**

```python
def _find_matching_listeners(self, event: ACFEvent) -> list[EventListener]:
    """Find all listeners matching this event.

    Supports patterns:
    - "*" → all events
    - "turn.*" → all turn category events
    - "turn.started" → exact match
    """
    matched = []
    event_type = event.type.value

    for pattern, listeners in self._listeners.items():
        if self._matches_pattern(event_type, pattern):
            matched.extend(listeners)

    return matched

def _matches_pattern(self, event_type: str, pattern: str) -> bool:
    """Check if event type matches pattern."""
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        category = pattern[:-2]
        return event_type.startswith(f"{category}.")
    return event_type == pattern
```

**Changes to `_record_side_effect` method (line ~238):**

```python
# Update to use new event type format
if event.type != ACFEventType.TOOL_EXECUTED:
    return

# Or use category check
if event.category != "tool" or event.event_name != "executed":
    return
```

---

### Group 2C: Update Tests

**File:** `tests/unit/runtime/acf/test_event_router.py`

**Changes:**
- Update all event type references to new format
- Add tests for category-based filtering
- Add tests for pattern matching

```python
# Example test updates
def sample_event() -> ACFEvent:
    return ACFEvent(
        type=ACFEventType.TURN_STARTED,  # Now "turn.started"
        logical_turn_id=uuid4(),
        session_key="test:agent:interlocutor:web",
    )

class TestPatternMatching:
    async def test_wildcard_category_match(self, router: EventRouter):
        """Test that 'turn.*' matches all turn events."""
        events_received = []

        async def listener(event: ACFEvent) -> None:
            events_received.append(event)

        await router.register_listener("turn.*", listener)

        # Should match
        await router.route(ACFEvent(type=ACFEventType.TURN_STARTED, ...))
        await router.route(ACFEvent(type=ACFEventType.TURN_COMPLETED, ...))

        # Should not match
        await router.route(ACFEvent(type=ACFEventType.TOOL_EXECUTED, ...))

        assert len(events_received) == 2

    async def test_category_property(self):
        """Test category extraction."""
        event = ACFEvent(type=ACFEventType.TOOL_EXECUTED, ...)
        assert event.category == "tool"
        assert event.event_name == "executed"
```

---

## Phase 3: Documentation Sync

**Effort**: 3-4 hours
**Risk**: Low
**Parallelizable**: Yes (3 groups)

### Group 3A: Authoritative Docs

**Files:**
- `docs/architecture/event-model.md` (REWRITE)

**New Content:**

```markdown
# Event Model Specification

> **Date**: 2025-12-16
> **Status**: AUTHORITATIVE

## Overview

ACF uses a **flat event model** with **category-based filtering**:

- Events have type format: `{category}.{event_name}`
- Categories enable pattern-based subscription
- AG-UI mapping handled by channel adapters

## Event Types

| Category | Events | Emitter | Streamable |
|----------|--------|---------|------------|
| `turn` | started, completed, failed, message_absorbed | ACF | Yes |
| `tool` | authorized, executed, failed | Toolbox | Yes |
| `supersede` | requested, decision, executed | ACF | Debug only |
| `commit` | reached | ACF | No |
| `enforcement` | violation | Brain | Yes |
| `session` | created, resumed, closed | ACF | Optional |
| `mutex` | acquired, released, extended | ACF | No (internal) |

## ACFEvent Model

\`\`\`python
class ACFEvent(BaseModel):
    type: ACFEventType          # e.g., "turn.started"
    logical_turn_id: UUID
    session_key: str
    timestamp: datetime
    payload: dict
    tenant_id: UUID | None
    agent_id: UUID | None

    @property
    def category(self) -> str:
        return self.type.value.split(".")[0]
\`\`\`

## Pattern Matching

\`\`\`python
# Subscribe to all turn events
router.register_listener("turn.*", my_listener)

# Subscribe to specific event
router.register_listener("tool.executed", tool_listener)

# Subscribe to everything
router.register_listener("*", audit_listener)
\`\`\`

## AG-UI Mapping

AG-UI compatibility is handled by `AGUIWebchatAdapter`:

| ACFEvent | AG-UI Event |
|----------|-------------|
| turn.started | RUN_STARTED |
| turn.completed | RUN_FINISHED |
| turn.failed | RUN_ERROR |
| tool.authorized | TOOL_CALL_START |
| tool.executed | TOOL_CALL_END |

## Migration from FabricEvent

`FabricEvent` and `FabricEventType` are deprecated aliases.
Use `ACFEvent` and `ACFEventType` in new code.
```

---

### Group 3B: ACF Architecture Docs

**Files:**
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/acf/architecture/TOOLBOX_SPEC.md`

**Changes:**
- Replace `FabricEvent` → `ACFEvent`
- Replace `FabricEventType` → `ACFEventType`
- Update example event type values to new format
- Update any flat enum definitions to show category.name format

---

### Group 3C: Topic and Analysis Docs

**Files:**
- `docs/acf/architecture/topics/01-logical-turn.md`
- `docs/acf/architecture/topics/04-side-effect-policy.md`
- `docs/acf/architecture/topics/06-hatchet-integration.md`
- `docs/acf/analysis/ag_ui_considerations.md`
- `docs/acf/architecture/README.md`
- `docs/acf/README.md`

**Changes:**
- Replace all `FabricEvent` references with `ACFEvent`
- Update code examples to use new event type format

---

## Verification Commands

```bash
# After Phase 1: Run all tests
uv run pytest tests/unit/runtime/acf/ -v

# After Phase 2: Run all tests
uv run pytest tests/unit/runtime/acf/ -v

# Check no FabricEvent in non-alias code
grep -r "FabricEvent" ruche/ --include="*.py" | grep -v "= ACF"

# Check documentation consistency
grep -r "FabricEvent" docs/ --include="*.md" | grep -v "deprecated\|alias\|migration"
```

---

## Subagent Task Distribution

### For Parallel Execution

**Subagent 1: Phase 1 Code (Groups 1A-1C)**
```
Task: Rename FabricEvent to ACFEvent in all code files
Files:
- ruche/runtime/acf/events.py
- ruche/runtime/acf/__init__.py
- ruche/runtime/acf/models.py
- ruche/runtime/acf/event_router.py
- ruche/runtime/acf/workflow.py
- ruche/runtime/__init__.py
- ruche/runtime/toolbox/toolbox.py
- ruche/runtime/agent/context.py

Instructions:
1. Rename FabricEventType → ACFEventType
2. Rename FabricEvent → ACFEvent
3. Add backward compat aliases in events.py
4. Update all imports, type hints, docstrings
5. DO NOT change event type values yet
```

**Subagent 2: Phase 1 Tests (Group 1D)**
```
Task: Update test file for ACFEvent rename
Files:
- tests/unit/runtime/acf/test_event_router.py

Instructions:
1. Replace all FabricEvent → ACFEvent
2. Replace all FabricEventType → ACFEventType
3. Run tests to verify: uv run pytest tests/unit/runtime/acf/test_event_router.py -v
```

**Subagent 3: Phase 2 Events (Group 2A)**
```
Task: Add category to event types
Files:
- ruche/runtime/acf/events.py

Instructions:
1. Change enum values to category.name format
2. Add category, event_name properties
3. Add matches_pattern method
4. Update JSON schema example
```

**Subagent 4: Phase 2 Router (Group 2B)**
```
Task: Update event router for category patterns
Files:
- ruche/runtime/acf/event_router.py

Instructions:
1. Update _find_matching_listeners for category patterns
2. Add _matches_pattern helper method
3. Update side effect recording to use new event type
```

**Subagent 5: Phase 3 Docs (Groups 3A-3C)**
```
Task: Update all documentation
Files:
- docs/architecture/event-model.md (rewrite)
- docs/acf/architecture/ACF_SPEC.md
- docs/acf/architecture/ACF_ARCHITECTURE.md
- docs/acf/architecture/TOOLBOX_SPEC.md
- docs/acf/architecture/topics/*.md
- docs/acf/analysis/ag_ui_considerations.md

Instructions:
1. Rewrite event-model.md with simplified flat model
2. Replace FabricEvent → ACFEvent everywhere
3. Update event type examples to category.name format
4. Remove references to two-layer AgentEvent model
```

---

## Rollback Plan

If issues arise:

1. **Phase 1 rollback**: Backward compat aliases ensure old imports work
2. **Phase 2 rollback**: Can revert enum values to old format
3. **Phase 3 rollback**: Docs are independent, can revert git commits

---

## Success Criteria

- [ ] All existing tests pass
- [ ] `from ruche.runtime.acf import ACFEvent, ACFEventType` works
- [ ] `from ruche.runtime.acf import FabricEvent, FabricEventType` works (deprecated)
- [ ] Event router supports `category.*` patterns
- [ ] `event.category` returns correct category
- [ ] Documentation is internally consistent
- [ ] No grep hits for `FabricEvent` except alias definitions
