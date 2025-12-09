# Subagent Execution Protocol

> **Purpose**: This document defines the execution protocol for ALL subagents implementing the focal turn pipeline phases.
> **Authority**: This document is MANDATORY. Read it COMPLETELY before starting any work.

---

## Pre-Execution Checklist

Before writing ANY code, you MUST read these files in order:

1. **This document** (`SUBAGENT_PROTOCOL.md`) - You're reading it now
2. **`CLAUDE.md`** (project root) - Project conventions and patterns
3. **`.specify/memory/constitution.md`** - Hard rules that cannot be violated
4. **`docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md`** - Naming consolidation (CRITICAL)
5. **Your assigned phase checklist** - `phase-{N}-{name}-checklist.md`
6. **Ground yourself in the focal turn pipeline specs** - Read the design docs in `docs/focal_turn_pipeline/spec/`

---

## CRITICAL: Codebase Exploration Before Implementation

**Before implementing ANYTHING**, you MUST explore the existing codebase to understand:

### 1. What Already Exists

Search for similar implementations before creating new code:

```bash
# Search for related classes/functions
mgrep "your feature name"
grep -r "RelatedClassName" focal/

# Check if the mechanism already exists somewhere
grep -r "def method_you_plan_to_add" focal/
```

### 2. Modify, Don't Duplicate

**CRITICAL RULE**: If something similar exists, **MODIFY IT** instead of creating a parallel implementation.

| Wrong ❌ | Right ✅ |
|----------|----------|
| Create `NewProfileStore` alongside existing `ProfileStore` | Rename/extend existing `ProfileStore` |
| Add `my_validator.py` when `validation.py` exists | Add your validation to existing `validation.py` |
| Create `CustomerDataUpdater` when `ProfileUpdater` does similar | Rename/extend `ProfileUpdater` |

### 3. Check for Obsolete Code

After your implementation:
- **Remove** old code that your new code replaces
- **Update** all imports pointing to old code
- **Delete** unused files/functions
- **Run tests** to ensure nothing still depends on removed code

### 4. Exploration Checklist

Before each implementation task, answer:

- [ ] Does similar functionality already exist? (Search the codebase)
- [ ] Can I extend an existing class instead of creating new one?
- [ ] Will my changes make any existing code obsolete?
- [ ] Have I updated all references to renamed/moved code?

---

## Documentation Structure

The focal turn pipeline specification is split across multiple files for easier navigation:

### Main Index
- **`docs/focal_turn_pipeline/README.md`** - Overview, diagrams, phase summary

### Detailed Specifications (in `docs/focal_turn_pipeline/spec/`)

| File | Contents |
|------|----------|
| **`pipeline.md`** | Detailed Phase 1-11 specifications with substeps, inputs/outputs |
| **`data_models.md`** | All data model definitions (TurnContext, SituationalSnapshot, etc.) |
| **`configuration.md`** | Pipeline configuration patterns |
| **`llm_task_configuration.md`** | LLM task configuration pattern (Jinja2 templates, config sections) |
| **`execution_model.md`** | Parallelization rules, async patterns, performance |

### Reference Order for Each Phase

When implementing a phase, read in this order:

1. **Your phase checklist** - What to implement
2. **`pipeline.md`** - Detailed substeps for your phase
3. **`data_models.md`** - Model definitions your phase creates/uses
4. **`llm_task_configuration.md`** - If your phase has an LLM task
5. **`execution_model.md`** - If your phase involves parallelization

### Related Documents

| Document | Purpose |
|----------|---------|
| `docs/focal_turn_pipeline/analysis/gap_analysis.md` | What's implemented vs. missing |
| `docs/design/scenario-update-methods.md` | Scenario migration details (Phase 1.7) |
| `docs/design/customer-profile.md` | CustomerProfile/CustomerDataStore context |

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

| Store | Question It Answers | Contains |
|-------|---------------------|----------|
| `ConfigStore` | "How should it behave?" | Rules, Scenarios, Templates, GlossaryItems |
| `MemoryStore` | "What does it remember?" | Episodes, Entities, Relationships |
| `SessionStore` | "What's happening now?" | Session state, active step, variables |
| `AuditStore` | "What happened?" | Turn records, events (immutable) |

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
from focal.observability.logging import get_logger
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

## Naming Corrections (CRITICAL)

The existing `focal/profile/` module IS the CustomerDataStore. Do NOT create duplicate models.

### Rename Map (from CHECKLIST_CORRECTIONS.md)

| Old Name (profile/) | New Name | Action |
|---------------------|----------|--------|
| `ProfileFieldDefinition` | `CustomerDataField` | RENAME + add `scope`, `persist` |
| `ProfileField` | `VariableEntry` | RENAME + add `history` |
| `CustomerProfile` | `CustomerDataStore` | RENAME |
| `ProfileStore` | `CustomerDataStore` (interface) | RENAME |
| `ProfileFieldSource` | `VariableSource` | RENAME |

### New Models to CREATE (these don't exist yet)

| Model | Location |
|-------|----------|
| `CustomerSchemaMask` | `focal/alignment/context/customer_schema_mask.py` |
| `CandidateVariableInfo` | `focal/alignment/context/situational_snapshot.py` |
| `SituationalSnapshot` | `focal/alignment/context/situational_snapshot.py` |
| `GlossaryItem` | `focal/alignment/models/glossary.py` |
| `TurnContext` | `focal/alignment/models/turn_context.py` |
| `ResponsePlan` | `focal/alignment/planning/models.py` |
| `TurnOutcome` | `focal/alignment/models/outcome.py` |

---

## Implementation Patterns

### Adding a New Model

```python
# focal/alignment/models/my_model.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class MyModel(BaseModel):
    """Docstring explaining purpose."""

    # Always include tenant scoping
    tenant_id: UUID
    id: UUID

    # Required fields
    name: str

    # Optional fields with defaults
    enabled: bool = Field(default=True)

    # Timestamps
    created_at: datetime
    updated_at: datetime

# Export in __init__.py
# focal/alignment/models/__init__.py
from .my_model import MyModel
```

### Adding Configuration

```toml
# config/default.toml
[pipeline.my_feature]
enabled = true
max_items = 50
timeout_seconds = 30
```

```python
# focal/config/models/pipeline.py
class MyFeatureConfig(BaseModel):
    """Configuration for my feature."""
    enabled: bool = True
    max_items: int = 50
    timeout_seconds: int = 30

# Add to PipelineConfig
class PipelineConfig(BaseModel):
    # ... existing fields ...
    my_feature: MyFeatureConfig = Field(default_factory=MyFeatureConfig)
```

### Adding Structured Logging

```python
from focal.observability.logging import get_logger

logger = get_logger(__name__)

# Good: structured with context
logger.info(
    "operation_completed",
    tenant_id=str(tenant_id),
    rule_id=str(rule.id),
    duration_ms=elapsed,
    items_processed=count,
)

# Bad: unstructured string
logger.info(f"Completed processing {count} items in {elapsed}ms")  # WRONG!
```

### Adding Metrics

```python
# focal/observability/metrics.py
from prometheus_client import Counter, Histogram

my_operation_total = Counter(
    "focal_my_operation_total",
    "Total my operations",
    ["tenant_id", "status"],
)

my_operation_duration = Histogram(
    "focal_my_operation_duration_seconds",
    "Duration of my operation",
    ["tenant_id"],
)
```

### Adding a Store Interface

```python
# focal/alignment/stores/my_store.py
from abc import ABC, abstractmethod

class MyStore(ABC):
    """Interface for my store."""

    @abstractmethod
    async def get(self, tenant_id: UUID, id: UUID) -> MyModel | None:
        """Get item by ID."""
        pass

    @abstractmethod
    async def save(self, item: MyModel) -> None:
        """Save item."""
        pass

# focal/alignment/stores/inmemory.py
class InMemoryMyStore(MyStore):
    """In-memory implementation for testing."""

    def __init__(self):
        self._items: dict[tuple[UUID, UUID], MyModel] = {}

    async def get(self, tenant_id: UUID, id: UUID) -> MyModel | None:
        return self._items.get((tenant_id, id))

    async def save(self, item: MyModel) -> None:
        self._items[(item.tenant_id, item.id)] = item
```

### Adding Jinja2 Templates

```jinja2
{# focal/alignment/context/prompts/my_task.jinja2 #}
You are analyzing a customer conversation.

{% if context %}
# Context
{{ context }}
{% endif %}

# Task
{{ task_description }}

Respond with JSON:
{
  "result": "..."
}
```

```python
# Loading templates
from focal.alignment.context.template_loader import TemplateLoader
from pathlib import Path

loader = TemplateLoader(Path(__file__).parent / "prompts")
prompt = loader.render("my_task.jinja2", context=ctx, task_description=desc)
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
   **Blocked because**: The interface for Y doesn't exist yet. This is created in Phase N.
   **Suggested resolution**: Complete Phase N first, or provide Y interface stub.
   ```

### Common Blockers and Resolutions

| Blocker | Resolution |
|---------|------------|
| "Model X doesn't exist" | Check if it's in previous phase checklist |
| "Import fails" | Run `uv sync` to install dependencies |
| "Store interface missing method" | Check if method should be added as part of your phase |
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
- [ ] **Create MyModel model**
  - File: `focal/alignment/models/my_model.py`
  - Action: Create new file

# After (edit the checklist file to show)
- [x] **Create MyModel model**
  - File: `focal/alignment/models/my_model.py`
  - Action: Created new file
  - **Implemented**: Created with fields `tenant_id`, `id`, `name`, `enabled`. Added export to `__init__.py`.
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
- [ ] **Integrate with SituationalSnapshot**
  - File: `focal/alignment/engine.py`

# After
- [ ] ⏸️ BLOCKED: SituationalSnapshot model not yet created (Phase 2 prerequisite)
  - File: `focal/alignment/engine.py`
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
| `focal/alignment/` | 85% minimum |
| `focal/memory/` | 85% minimum |

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific phase tests
uv run pytest tests/unit/alignment/models/ -v

# Run with coverage
uv run pytest --cov=focal/alignment --cov-report=term-missing

# Run only your phase's tests
uv run pytest tests/unit/alignment/context/ -v --cov=focal/alignment/context
```

### Test Patterns

```python
# tests/unit/alignment/models/test_my_model.py
import pytest
from focal.alignment.models.my_model import MyModel

class TestMyModel:
    """Test suite for MyModel."""

    def test_create_with_required_fields(self):
        """Test model creation with required fields."""
        model = MyModel(
            tenant_id=uuid4(),
            id=uuid4(),
            name="test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert model.name == "test"
        assert model.enabled is True  # default

    def test_validation_rejects_empty_name(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError):
            MyModel(name="", ...)
```

### Using Test Factories

```python
# tests/factories.py
from focal.alignment.models.my_model import MyModel

class MyModelFactory:
    @staticmethod
    def create(**overrides) -> MyModel:
        defaults = {
            "tenant_id": uuid4(),
            "id": uuid4(),
            "name": "test_name",
            "enabled": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        return MyModel(**{**defaults, **overrides})
```

---

## Final Report Template

At the end of your work, provide this report:

```markdown
# Phase {N} Implementation Report

## Summary
- **Items Completed**: X of Y
- **Items Blocked**: Z
- **Tests**: PASSING / FAILING
- **Coverage**: XX%

## Completed Items
1. Created `MyModel` in `focal/alignment/models/my_model.py`
2. Added config section `[pipeline.my_feature]` to `config/default.toml`
3. Implemented `MyStore` interface and `InMemoryMyStore`
4. ... (list all)

## Blocked Items

### Item 3.2: Integrate with SituationalSnapshot
- **Reason**: SituationalSnapshot model not yet created
- **Dependency**: Phase 2
- **Suggested Resolution**: Complete Phase 2 first

## Deviations from Checklist
- Item 2.1 specified `key` field, but used `name` per CHECKLIST_CORRECTIONS.md
- Added extra validation for X because Y

## Tests Created
- `tests/unit/alignment/models/test_my_model.py` (8 tests)
- `tests/unit/alignment/stores/test_my_store.py` (5 tests)

## Files Created/Modified
### Created
- `focal/alignment/models/my_model.py`
- `focal/alignment/stores/my_store.py`
- `tests/unit/alignment/models/test_my_model.py`

### Modified
- `focal/alignment/models/__init__.py` (added export)
- `config/default.toml` (added section)
- `focal/config/models/pipeline.py` (added config model)

## Notes for Next Phase
- The `MyStore` interface is ready for Phase N+1 to use
- Consider adding caching for performance (future enhancement)
```

---

## Quick Reference

### Import Patterns

```python
# Logging
from focal.observability.logging import get_logger
logger = get_logger(__name__)

# Metrics
from focal.observability.metrics import my_metric

# Models
from focal.alignment.models import MyModel
from focal.alignment.models.rule import Rule, MatchedRule

# Stores
from focal.alignment.stores.config_store import ConfigStore
from focal.alignment.stores.inmemory import InMemoryConfigStore

# Config
from focal.config.loader import get_settings
settings = get_settings()

# Pydantic
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, UTC
```

### File Locations

| Type | Location Pattern |
|------|------------------|
| Models | `focal/alignment/models/{name}.py` |
| Stores | `focal/alignment/stores/{name}.py` |
| Config Models | `focal/config/models/{domain}.py` |
| Templates | `focal/alignment/{domain}/prompts/{name}.jinja2` |
| Unit Tests | `tests/unit/alignment/{mirror_of_src}/test_{name}.py` |
| Integration Tests | `tests/integration/alignment/test_{feature}.py` |

---

## Checklist Before Submitting

Before marking your phase complete:

- [ ] All implemented items marked `[x]` with notes
- [ ] All blocked items marked `⏸️ BLOCKED:` with reasons
- [ ] All tests pass: `uv run pytest`
- [ ] Coverage meets threshold: `uv run pytest --cov`
- [ ] **Code quality checks pass** (see below)
- [ ] No `print()` statements in code
- [ ] No hardcoded config values
- [ ] All new models have `tenant_id`
- [ ] All I/O functions are `async`
- [ ] **No duplicate/parallel implementations** (searched codebase)
- [ ] **Obsolete code removed** (if you renamed/replaced something)
- [ ] Final report written

---

## Code Quality Checks (MANDATORY)

**Run these checks at the end of EVERY phase**:

### 1. Ruff (Linting & Formatting)

```bash
# Check for linting issues
uv run ruff check focal/alignment/

# Auto-fix what can be fixed
uv run ruff check --fix focal/alignment/

# Format code
uv run ruff format focal/alignment/
```

**All ruff errors MUST be fixed** before marking phase complete.

### 2. Mypy (Type Checking)

```bash
# Run type checking on your changes
uv run mypy focal/alignment/ --ignore-missing-imports

# Or check specific files you modified
uv run mypy focal/alignment/models/my_new_model.py
```

**Target**: No new type errors introduced. Pre-existing errors are acceptable but don't add more.

### 3. Quick Quality Check Script

Run this at the end of each phase:

```bash
# Full quality check
echo "=== RUFF CHECK ===" && uv run ruff check focal/alignment/ && \
echo "=== RUFF FORMAT CHECK ===" && uv run ruff format --check focal/alignment/ && \
echo "=== MYPY ===" && uv run mypy focal/alignment/ --ignore-missing-imports && \
echo "=== TESTS ===" && uv run pytest tests/unit/alignment/ -v --tb=short && \
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

## Questions?

If you have questions this document doesn't answer:
1. Check `CLAUDE.md` for project patterns
2. Check existing code for examples
3. Mark item as ⏸️ BLOCKED and continue
4. Document the question in your final report
