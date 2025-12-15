# Subagent Execution Protocol

> **Purpose**: This document defines the execution protocol for ALL subagents implementing FOCAL 360 platform features.
> **Authority**: This document is MANDATORY. Read it COMPLETELY before starting any work.

---

## Pre-Execution Checklist

Before writing ANY code, you MUST read these files in order:

1. **This document** (`SUBAGENT_PROTOCOL.md`) - You're reading it now
2. **`CLAUDE.md`** (project root) - Project conventions and patterns
3. **`.specify/memory/constitution.md`** - Hard rules that cannot be violated
4. **`docs/acf/gap_analysis.md`** - What exists vs. what's missing (CRITICAL)
5. **Your assigned feature checklist** - `implementation/{feature}-checklist.md`
6. **Ground yourself in the turn brain** - Read `docs/focal_brain/README.md`

---

## CRITICAL: Codebase Exploration Before Implementation

**Before implementing ANYTHING**, you MUST explore the existing codebase to understand:

### 1. What Already Exists

The gap analysis identifies many partial implementations. Search before creating:

```bash
# Search for related classes/functions
mgrep "your feature name"
grep -r "RelatedClassName" ruche/

# Check if the mechanism already exists somewhere
grep -r "def method_you_plan_to_add" ruche/
```

### 2. Modify, Don't Duplicate

**CRITICAL RULE**: If something similar exists, **MODIFY IT** instead of creating a parallel implementation.

| Wrong | Right |
|-------|-------|
| Create `NewRateLimiter` alongside existing `RateLimiter` | Extend existing `RateLimiter` with debouncing |
| Add `channel_capability.py` ignoring `Channel` enum | Extend existing channel infrastructure |
| Create `IngresController` when `rate_limit.py` exists | Add ingress control to existing middleware |

### 3. Check for Obsolete Code

After your implementation:
- **Remove** old code that your new code replaces
- **Update** all imports pointing to old code
- **Delete** unused files/functions
- **Run tests** to ensure nothing still depends on removed code

### 4. Exploration Checklist

Before each implementation task, answer:

- [ ] Does similar functionality already exist? (Check gap analysis + search)
- [ ] Can I extend an existing class instead of creating a new one?
- [ ] Will my changes make any existing code obsolete?
- [ ] Have I updated all references to renamed/moved code?

---

## Documentation Structure

FOCAL 360 builds a platform layer around the existing 11-phase turn brain:

### Main Index
- **`docs/acf/README.md`** - Overview of all FOCAL 360 features

### Key References

| File | Contents |
|------|----------|
| **`gap_analysis.md`** | What exists vs. what's missing (CRITICAL - read first!) |
| **`spec/{feature}.md`** | Detailed feature specifications |
| **`implementation/{feature}-checklist.md`** | Implementation checklists |

### Reference Order for Each Feature

When implementing a feature, read in this order:

1. **Gap analysis** - What already exists that you can extend
2. **Your feature checklist** - What to implement
3. **`spec/{feature}.md`** - Detailed specifications (if available)
4. **Turn brain docs** - If your feature integrates with the brain

### Related Turn Brain Docs

| Document | Purpose |
|----------|---------|
| `docs/focal_brain/README.md` | The 11-phase brain these features wrap |
| `docs/focal_brain/spec/brain.md` | Phase-by-phase specifications |
| `docs/focal_brain/spec/data_models.md` | Existing data models |
| `docs/design/scenario-update-methods.md` | Scenario migration details |

---

## Core Principles (from Constitution)

These are HARD RULES. Violating them will cause your work to be rejected.

### 1. Technology Stack

| Requirement | Rule |
|-------------|------|
| **Python** | 3.11+ required |
| **Package Manager** | `uv` ONLY. Never use `pip` or `poetry` |
| **Web Framework** | FastAPI |
| **Logging** | `structlog` ONLY. Never `print()` or `logging` module |
| **Models** | Pydantic for ALL data models |
| **Config** | `pydantic-settings` for configuration |

### 2. Architectural Patterns

| Pattern | Implementation |
|---------|----------------|
| **Zero In-Memory State** | No module-level caches, no singletons holding data |
| **Multi-Tenant** | `tenant_id` on EVERY entity, query, cache key |
| **Interface-First** | ABC first → InMemory impl → Production impl |
| **Dependency Injection** | Classes receive dependencies in `__init__`, never create them |
| **Async Everywhere** | ALL I/O operations must be `async` |

### 3. The Four Stores

Do NOT mix concerns between stores:

| Store | Question It Answers | Use For FOCAL 360 |
|-------|---------------------|-------------------|
| `ConfigStore` | "How should it behave?" | ChannelCapability, ToolSideEffectPolicy, AgentConfig |
| `MemoryStore` | "What does it remember?" | (Existing - don't extend for FOCAL 360) |
| `SessionStore` | "What's happening now?" | AgendaTask, Goal, in-flight turn state |
| `AuditStore` | "What happened?" | Abuse flags, ingress events, turn cancellations |

### 4. Banned Practices

**NEVER DO THESE:**

```python
# BANNED: try/except for imports
try:
    import anthropic
except ImportError:
    anthropic = None  # WRONG!

# CORRECT: Let it fail at import time
import anthropic

# BANNED: print for logging
print(f"Processing {user_id}")  # WRONG!

# CORRECT: structlog
from ruche.observability.logging import get_logger
logger = get_logger(__name__)
logger.info("processing_user", user_id=str(user_id))

# BANNED: blocking I/O
def get_rules():  # WRONG!
    return db.query(...)

# CORRECT: async
async def get_rules():
    return await db.query(...)

# BANNED: hardcoded config
MAX_RETRIES = 3  # WRONG!

# CORRECT: config file
# In config/default.toml: max_retries = 3
# In code: self._config.max_retries
```

---

## Gap Analysis Reference (CRITICAL)

The gap analysis (`docs/acf/gap_analysis.md`) identifies what already exists. **ALWAYS check it first.**

### Vocabulary Mapping

| FOCAL 360 Term | Existing Focal Term | Status |
|----------------|----------------------|--------|
| Ingress Control | `RateLimitMiddleware` | Extend (add debouncing) |
| Debouncing | `burst_size` config | Implement (field unused) |
| Side-Effect Registry | `ScenarioStep.is_checkpoint` | Extend (add tool-level) |
| ChannelCapability | `Channel` enum | Extend (add metadata) |
| AgentConfig | `AgentConfig` model | Wire (exists but unused) |
| AgendaTask | — | Create new |
| ASA/Reporter | — | Create new |

### Feature Categories

| Category | Description | Example Files |
|----------|-------------|---------------|
| **Category A: Pre-Brain** | Wraps the turn brain | `ruche/api/middleware/` |
| **Category B: Brain Extensions** | Extends existing phases | `ruche/alignment/`, `ruche/config/` |
| **Category C: New Systems** | Entirely new subsystems | `ruche/agenda/`, `ruche/meta_agents/` |

---

## Implementation Patterns

### Adding Middleware (Category A)

```python
# ruche/api/middleware/ingress.py
from starlette.middleware.base import BaseHTTPMiddleware
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

class IngressControlMiddleware(BaseHTTPMiddleware):
    """Pre-turn ingress control with debouncing and abuse detection."""

    def __init__(self, app, config: IngressConfig):
        super().__init__(app)
        self._config = config

    async def dispatch(self, request: Request, call_next):
        # ... implementation
        pass
```

### Adding Configuration

```toml
# config/default.toml
[api.ingress]
enabled = true
debounce_window_ms = 2000
coalesce_enabled = true
abuse_threshold = 5
```

```python
# ruche/config/models/api.py
class IngressConfig(BaseModel):
    """Configuration for ingress control."""
    enabled: bool = True
    debounce_window_ms: int = 2000
    coalesce_enabled: bool = True
    abuse_threshold: int = 5

# Add to APIConfig
class APIConfig(BaseModel):
    # ... existing fields ...
    ingress: IngressConfig = Field(default_factory=IngressConfig)
```

### Adding Structured Logging

```python
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

# Good: structured with context
logger.info(
    "turn_coalesced",
    tenant_id=str(tenant_id),
    customer_id=str(customer_id),
    messages_merged=count,
    window_ms=elapsed,
)

# Bad: unstructured string
logger.info(f"Coalesced {count} messages in {elapsed}ms")  # WRONG!
```

### Adding Metrics

```python
# ruche/observability/metrics.py
from prometheus_client import Counter, Histogram

ingress_coalesced_total = Counter(
    "focal_ingress_coalesced_total",
    "Total coalesced message bursts",
    ["tenant_id", "channel"],
)

ingress_debounce_duration = Histogram(
    "focal_ingress_debounce_duration_seconds",
    "Duration of debounce window",
    ["tenant_id"],
)
```

### Adding a Store Interface (Category C)

```python
# ruche/agenda/store.py
from abc import ABC, abstractmethod
from uuid import UUID

class AgendaStore(ABC):
    """Interface for agenda task storage."""

    @abstractmethod
    async def get_pending_tasks(
        self, tenant_id: UUID, customer_id: UUID
    ) -> list[AgendaTask]:
        """Get pending tasks for a customer."""
        pass

    @abstractmethod
    async def save_task(self, task: AgendaTask) -> None:
        """Save an agenda task."""
        pass

# ruche/agenda/stores/inmemory.py
class InMemoryAgendaStore(AgendaStore):
    """In-memory implementation for testing."""

    def __init__(self):
        self._tasks: dict[tuple[UUID, UUID], list[AgendaTask]] = {}

    async def get_pending_tasks(
        self, tenant_id: UUID, customer_id: UUID
    ) -> list[AgendaTask]:
        return self._tasks.get((tenant_id, customer_id), [])

    async def save_task(self, task: AgendaTask) -> None:
        key = (task.tenant_id, task.customer_id)
        if key not in self._tasks:
            self._tasks[key] = []
        self._tasks[key].append(task)
```

---

## Uncertainty Protocol

When you encounter something unclear or blocking:

### DO NOT:
- Guess or improvise
- Make architectural decisions without asking
- Skip items silently
- Create workarounds

### DO:
1. **Mark the item** in the checklist with:
   ```markdown
   - [ ] ⏸️ BLOCKED: [Clear reason why this is blocked]
   ```

2. **Continue with next item** - Don't stop working

3. **Document in your final report**:
   ```markdown
   ## Blocked Items

   ### Item 3.2: Implement X
   **Blocked because**: The interface for Y doesn't exist yet. This is created in Feature Z.
   **Suggested resolution**: Complete Feature Z first, or provide Y interface stub.
   ```

### Common Blockers and Resolutions

| Blocker | Resolution |
|---------|------------|
| "Model X doesn't exist" | Check gap analysis - might exist under different name |
| "Import fails" | Run `uv sync` to install dependencies |
| "Store interface missing method" | Check if method should be added as part of your feature |
| "Config section missing" | Add it as part of your implementation |
| "Test fails due to missing fixture" | Create the fixture in `conftest.py` |

---

## Checklist Update Protocol

### CRITICAL: Update Checkboxes AS YOU WORK

**DO NOT** wait until the end to update checkboxes. **DO NOT** just write a summary.

You MUST edit the checklist file and change `- [ ]` to `- [x]` **immediately after completing each item**.

### Marking Items Complete

When you complete an item, **immediately edit the checklist file**:

```markdown
# Before (in the checklist file)
- [ ] **Create IngressConfig model**
  - File: `ruche/config/models/api.py`
  - Action: Add config model

# After (edit the checklist file to show)
- [x] **Create IngressConfig model**
  - File: `ruche/config/models/api.py`
  - Action: Added config model
  - **Implemented**: Created with `debounce_window_ms`, `coalesce_enabled`, `abuse_threshold`. Added to APIConfig.
```

### The Process

1. Read checklist item
2. Implement the item
3. **IMMEDIATELY** use the Edit tool to change `- [ ]` to `- [x]` in the checklist file
4. Add implementation notes under the item
5. Move to next item

**DO NOT:**
- Batch checkbox updates at the end
- Only write a summary section
- Leave checkboxes unchecked after completing work
- Create a separate "results" section instead of checking boxes

### Marking Items Blocked

```markdown
# Before
- [ ] **Integrate with SideEffectRegistry**
  - File: `ruche/api/middleware/ingress.py`

# After
- [ ] ⏸️ BLOCKED: SideEffectRegistry not yet created (Wave 4 prerequisite)
  - File: `ruche/api/middleware/ingress.py`
```

### Adding Implementation Notes

Always add a brief note about:
- What you actually implemented
- Any deviations from the spec
- Important decisions made
- File paths created/modified

---

## Testing Requirements

### Minimum Coverage

| Module | Required Coverage |
|--------|-------------------|
| Overall | 85% line, 80% branch |
| New FOCAL 360 modules | 85% minimum |

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific feature tests
uv run pytest tests/unit/api/middleware/test_ingress.py -v

# Run with coverage
uv run pytest --cov=ruche/api/middleware --cov-report=term-missing

# Run only your feature's tests
uv run pytest tests/unit/agenda/ -v --cov=ruche/agenda
```

### Test Patterns

```python
# tests/unit/api/middleware/test_ingress.py
import pytest
from ruche.api.middleware.ingress import IngressControlMiddleware

class TestIngressControlMiddleware:
    """Test suite for IngressControlMiddleware."""

    async def test_debounce_coalesces_rapid_messages(self):
        """Test that rapid messages are coalesced."""
        # Arrange
        middleware = IngressControlMiddleware(app, config)

        # Act
        # ... send rapid messages

        # Assert
        assert coalesced_count == 2

    async def test_bypass_when_disabled(self):
        """Test that middleware passes through when disabled."""
        config = IngressConfig(enabled=False)
        # ...
```

### Using Test Factories

```python
# tests/factories/acf.py
from ruche.agenda.models import AgendaTask

class AgendaTaskFactory:
    @staticmethod
    def create(**overrides) -> AgendaTask:
        defaults = {
            "tenant_id": uuid4(),
            "customer_id": uuid4(),
            "task_type": "follow_up",
            "scheduled_at": datetime.now(UTC) + timedelta(hours=24),
            "created_at": datetime.now(UTC),
        }
        return AgendaTask(**{**defaults, **overrides})
```

---

## Final Report Template

At the end of your work, provide this report:

```markdown
# {Feature} Implementation Report

## Summary
- **Items Completed**: X of Y
- **Items Blocked**: Z
- **Tests**: PASSING / FAILING
- **Coverage**: XX%

## Completed Items
1. Created `IngressControlMiddleware` in `ruche/api/middleware/ingress.py`
2. Added config section `[api.ingress]` to `config/default.toml`
3. Extended `RateLimiter` with debouncing capability
4. ... (list all)

## Blocked Items

### Item 3.2: Integrate with SideEffectRegistry
- **Reason**: SideEffectRegistry not yet implemented
- **Dependency**: Wave 4
- **Suggested Resolution**: Complete Wave 4 first

## Deviations from Checklist
- Used existing `RateLimiter` instead of creating new class per gap analysis
- Added Redis backend since existing infra supports it

## Tests Created
- `tests/unit/api/middleware/test_ingress.py` (8 tests)
- `tests/unit/api/middleware/test_debounce.py` (5 tests)

## Files Created/Modified
### Created
- `ruche/api/middleware/ingress.py`
- `ruche/config/models/ingress.py`
- `tests/unit/api/middleware/test_ingress.py`

### Modified
- `ruche/api/app.py` (added middleware registration)
- `ruche/api/middleware/rate_limit.py` (added debounce support)
- `config/default.toml` (added [api.ingress] section)
- `ruche/config/models/api.py` (added IngressConfig)

## Notes for Next Wave
- The IngressControl is ready for SideEffectRegistry integration
- Consider adding distributed debouncing via Redis for multi-pod deployment
```

---

## Quick Reference

### Import Patterns

```python
# Logging
from ruche.observability.logging import get_logger
logger = get_logger(__name__)

# Metrics
from ruche.observability.metrics import my_metric

# Models
from ruche.alignment.models import Rule, MatchedRule
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, UTC

# Stores
from ruche.alignment.stores.config_store import ConfigStore
from ruche.alignment.stores.inmemory import InMemoryConfigStore

# Config
from ruche.config.loader import get_settings
settings = get_settings()

# Existing middleware
from ruche.api.middleware.rate_limit import RateLimiter
```

### File Locations

| Type | Location Pattern |
|------|------------------|
| Middleware | `ruche/api/middleware/{name}.py` |
| Models (alignment) | `ruche/alignment/models/{name}.py` |
| Models (new system) | `ruche/{system}/models.py` |
| Stores | `ruche/{system}/store.py` + `ruche/{system}/stores/` |
| Config Models | `ruche/config/models/{domain}.py` |
| Unit Tests | `tests/unit/{mirror_of_src}/test_{name}.py` |
| Integration Tests | `tests/integration/{feature}/test_{name}.py` |

---

## Code Quality Checks (MANDATORY)

**Run these checks at the end of EVERY feature**:

### 1. Ruff (Linting & Formatting)

```bash
# Check for linting issues
uv run ruff check ruche/

# Auto-fix what can be fixed
uv run ruff check --fix ruche/

# Format code
uv run ruff format ruche/
```

**All ruff errors MUST be fixed** before marking feature complete.

### 2. Mypy (Type Checking)

```bash
# Run type checking on your changes
uv run mypy ruche/ --ignore-missing-imports

# Or check specific files you modified
uv run mypy ruche/api/middleware/ingress.py
```

**Target**: No new type errors introduced. Pre-existing errors are acceptable but don't add more.

### 3. Quick Quality Check Script

Run this at the end of each feature:

```bash
# Full quality check
echo "=== RUFF CHECK ===" && uv run ruff check ruche/ && \
echo "=== RUFF FORMAT CHECK ===" && uv run ruff format --check ruche/ && \
echo "=== MYPY ===" && uv run mypy ruche/ --ignore-missing-imports && \
echo "=== TESTS ===" && uv run pytest tests/unit/ -v --tb=short && \
echo "=== ALL CHECKS PASSED ==="
```

### Common Issues and Fixes

| Issue | Fix |
|-------|-----|
| `F401: imported but unused` | Remove unused import |
| `E501: line too long` | Break line or ruff format |
| `Missing type annotation` | Add type hints to function |
| `Incompatible types` | Fix the type mismatch |

---

## Checklist Before Submitting

Before marking your feature complete:

- [ ] All implemented items marked `[x]` with notes
- [ ] All blocked items marked `⏸️ BLOCKED:` with reasons
- [ ] All tests pass: `uv run pytest`
- [ ] Coverage meets threshold: `uv run pytest --cov`
- [ ] **Code quality checks pass** (see above)
- [ ] No `print()` statements in code
- [ ] No hardcoded config values
- [ ] All new models have `tenant_id`
- [ ] All I/O functions are `async`
- [ ] **No duplicate/parallel implementations** (checked gap analysis)
- [ ] **Extended existing code where possible** (per gap analysis)
- [ ] Final report written

---

## Questions?

If you have questions this document doesn't answer:
1. Check `CLAUDE.md` for project patterns
2. Check `docs/acf/gap_analysis.md` for existing implementations
3. Check existing code for examples
4. Mark item as ⏸️ BLOCKED and continue
5. Document the question in your final report
