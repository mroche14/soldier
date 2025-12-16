# Subagent Implementation Protocol

**Version**: 1.0
**Last Updated**: 2025-12-15

This protocol governs how subagents execute implementation tasks for the Ruche platform. **Strict adherence is mandatory.**

---

## PRIME DIRECTIVE

> **NEVER GUESS. ALWAYS REFERENCE DOCUMENTATION.**
>
> If something is not documented, STOP and ask for clarification.
> Do not invent patterns, interfaces, or behaviors.

---

## Core Principles

### 1. Documentation Is The Source of Truth

```
BEFORE writing ANY code:
1. Read the relevant documentation
2. Understand the documented design
3. Implement EXACTLY what the docs describe
4. If docs are ambiguous → ASK, don't assume
```

**Documentation hierarchy**:
1. `docs/` folder - Architecture and design specs
2. `CLAUDE.md` - Development guidelines and patterns
3. Existing code patterns - Only if consistent with docs

### 2. No Invention Policy

**FORBIDDEN**:
- Inventing new interfaces not in docs
- Adding "nice to have" features
- Creating abstractions not specified
- Changing documented patterns because you think they're better
- Guessing at implementation details

**REQUIRED**:
- Implement exactly what docs specify
- Use exact names from docs
- Follow exact method signatures from docs
- Match documented data flows

### 3. When In Doubt, Search

Before implementing anything:
```bash
# Search docs for the concept
grep -r "ConceptName" docs/

# Search for related patterns
grep -r "pattern_name" ruche/

# Find existing implementations of similar things
find ruche/ -name "*similar*"
```

---

## Pre-Implementation Checklist

Before starting ANY task, complete this checklist:

```markdown
## Task: [Task Name]

### Documentation Review
- [ ] I have read the primary doc: `docs/[relevant]/[file].md`
- [ ] I have read related sections in `CLAUDE.md`
- [ ] I have searched for related docs: `grep -r "[keyword]" docs/`
- [ ] I understand the documented interface/behavior
- [ ] I have identified all documented requirements

### Existing Code Review
- [ ] I have found similar implementations in codebase
- [ ] I understand the existing patterns used
- [ ] I have identified files that will be modified
- [ ] I have identified files that will be created

### Clarification Needed
- [ ] All requirements are clear (if not, list questions below)

### Questions (if any):
1. ...
```

---

## Task Execution Protocol

### Phase 1: Understand

1. **Read the task description** completely
2. **Identify the documentation** that covers this task:
   - Which `docs/` files are relevant?
   - Which section of `CLAUDE.md` applies?
   - Which ADRs (Architectural Decision Records) are relevant?
3. **Read ALL relevant documentation** before writing any code
4. **Extract requirements** as a checklist from the docs

### Phase 2: Locate

1. **Find existing code** related to this task:
   ```bash
   # Find files by name pattern
   find ruche/ -name "*keyword*"

   # Find code by content
   grep -r "ClassName" ruche/

   # Find imports
   grep -r "from.*module.*import" ruche/
   ```

2. **Identify the exact files** to modify or create
3. **Read existing implementations** of similar patterns
4. **Note the coding style** used in those files

### Phase 3: Implement

1. **Follow documented interfaces exactly**:
   - Use the exact class/method names from docs
   - Use the exact parameter names from docs
   - Use the exact return types from docs

2. **Follow existing patterns**:
   - If similar code exists, match its style
   - Use the same error handling patterns
   - Use the same logging patterns
   - Use the same async patterns

3. **Write minimal code**:
   - Implement only what's documented
   - No extra features
   - No premature abstractions
   - No "improvements" beyond spec

### Phase 4: Verify

1. **Check against documentation**:
   - Does implementation match documented interface?
   - Does implementation match documented behavior?
   - Are all documented requirements addressed?

2. **Check against existing patterns**:
   - Does code style match existing code?
   - Are imports consistent?
   - Are error patterns consistent?

3. **Run tests**:
   ```bash
   # Run relevant tests
   uv run pytest tests/unit/[relevant]/ -v

   # Run type checking
   uv run mypy ruche/[relevant]/
   ```

---

## Documentation Reference Map

### For Each Implementation Area

#### FOCAL Brain Implementation
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| Phase 1-11 | `docs/focal_brain/spec/brain.md` | `docs/focal_brain/spec/data_models.md` |
| Models | `docs/focal_brain/spec/data_models.md` | `docs/design/domain-model.md` |
| LLM Tasks | `docs/focal_brain/spec/llm_task_configuration.md` | - |
| Configuration | `docs/focal_brain/spec/configuration.md` | `docs/architecture/configuration-overview.md` |

#### ACF Implementation
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| LogicalTurn | `docs/acf/architecture/topics/01-logical-turn.md` | `docs/acf/architecture/ACF_SPEC.md` |
| Session Mutex | `docs/acf/architecture/topics/02-session-mutex.md` | - |
| Accumulation | `docs/acf/architecture/topics/03-adaptive-accumulation.md` | - |
| Side Effects | `docs/acf/architecture/topics/04-side-effect-policy.md` | - |
| Checkpoints | `docs/acf/architecture/topics/05-checkpoint-reuse.md` | - |
| Hatchet | `docs/acf/architecture/topics/06-hatchet-integration.md` | - |
| TurnGateway | `docs/acf/architecture/topics/07-turn-gateway.md` | - |
| Config | `docs/acf/architecture/topics/08-config-hierarchy.md` | - |
| Agenda | `docs/acf/architecture/topics/09-agenda-goals.md` | - |
| Channels | `docs/acf/architecture/topics/10-channel-capabilities.md` | `docs/architecture/channel-gateway.md` |
| Abuse | `docs/acf/architecture/topics/11-abuse-detection.md` | - |
| Idempotency | `docs/acf/architecture/topics/12-idempotency.md` | - |
| ASA | `docs/acf/architecture/topics/13-asa-validator.md` | - |
| AgentRuntime | `docs/acf/architecture/AGENT_RUNTIME_SPEC.md` | - |
| Toolbox | `docs/acf/architecture/TOOLBOX_SPEC.md` | - |

#### Storage Implementation
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| Store Interfaces | `docs/design/decisions/001-storage-choice.md` | - |
| Database Selection | `docs/design/decisions/003-database-selection.md` | - |
| Memory Layer | `docs/architecture/memory-layer.md` | - |

#### Provider Implementation
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| LLM | `docs/studies/llm-executor-agno-integration.md` | - |
| Embedding | `docs/design/embedding-model-management/overview.md` | - |
| Selection | `docs/architecture/selection-strategies.md` | - |

#### API Implementation
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| REST API | `docs/architecture/api-layer.md` | `docs/design/api-crud.md` |
| Webhooks | `docs/architecture/webhook-system.md` | - |
| Channels | `docs/architecture/channel-gateway.md` | - |
| Errors | `docs/architecture/error-handling.md` | - |

#### Domain Models
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| Core Models | `docs/design/domain-model.md` | - |
| Interlocutor | `docs/design/interlocutor-data.md` | `docs/focal_brain/spec/data_models.md` |

#### Observability
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| Logging/Tracing/Metrics | `docs/architecture/observability.md` | - |

#### Configuration
| Task Area | Primary Doc | Secondary Docs |
|-----------|-------------|----------------|
| Overview | `docs/architecture/configuration-overview.md` | - |
| Models | `docs/architecture/configuration-models.md` | - |
| TOML | `docs/architecture/configuration-toml.md` | - |
| Secrets | `docs/architecture/configuration-secrets.md` | - |

---

## Code Patterns Reference

### Pattern 1: Pydantic Models

**Source**: Existing models in `ruche/domain/`, `ruche/brains/focal/models/`

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class MyModel(BaseModel):
    """Docstring describing the model."""

    id: UUID = Field(description="Unique identifier")
    tenant_id: UUID = Field(description="Tenant isolation")
    name: str = Field(description="Human-readable name")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": True}  # If immutable
```

### Pattern 2: Store Interface (ABC)

**Source**: `ruche/memory/store.py`, `ruche/conversation/store.py`

```python
from abc import ABC, abstractmethod
from uuid import UUID

class MyStore(ABC):
    """Abstract interface for MyStore."""

    @abstractmethod
    async def get(self, tenant_id: UUID, id: UUID) -> MyModel | None:
        """Get item by ID. Returns None if not found."""
        pass

    @abstractmethod
    async def save(self, item: MyModel) -> None:
        """Save item. Overwrites if exists."""
        pass
```

### Pattern 3: In-Memory Store Implementation

**Source**: `ruche/memory/stores/inmemory.py`

```python
from collections import defaultdict

class InMemoryMyStore(MyStore):
    def __init__(self) -> None:
        self._data: dict[UUID, dict[UUID, MyModel]] = defaultdict(dict)

    async def get(self, tenant_id: UUID, id: UUID) -> MyModel | None:
        return self._data[tenant_id].get(id)

    async def save(self, item: MyModel) -> None:
        self._data[item.tenant_id][item.id] = item
```

### Pattern 4: Provider Interface

**Source**: `ruche/infrastructure/providers/embedding/base.py`

```python
from abc import ABC, abstractmethod

class MyProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def execute(self, input: Input) -> Output:
        """Execute the provider operation."""
        pass
```

### Pattern 5: API Route

**Source**: `ruche/api/routes/agents.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

router = APIRouter(prefix="/v1/myresource", tags=["myresource"])

@router.get("/{id}", response_model=MyResponse)
async def get_item(
    id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    store: MyStore = Depends(get_store),
) -> MyResponse:
    """Get item by ID."""
    item = await store.get(tenant_id, id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return MyResponse.from_model(item)
```

### Pattern 6: Structured Logging

**Source**: `CLAUDE.md`, existing code

```python
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

# Good: Structured with context
logger.info(
    "operation_completed",
    item_id=item.id,
    tenant_id=tenant_id,
    duration_ms=duration,
)

# Bad: Unstructured string
logger.info(f"Completed operation for {item.id}")
```

### Pattern 7: Error Handling

**Source**: `docs/architecture/error-handling.md`

```python
from ruche.api.exceptions import NotFoundError, ValidationError

# Raise domain-specific errors
if not item:
    raise NotFoundError(f"Item {id} not found")

if not valid:
    raise ValidationError("Invalid input", details={"field": "reason"})
```

---

## Task Completion Checklist

Before marking a task complete, verify:

```markdown
## Completion Checklist for: [Task Name]

### Documentation Compliance
- [ ] Implementation matches documented interface exactly
- [ ] Implementation matches documented behavior exactly
- [ ] All documented requirements are addressed
- [ ] No undocumented features were added

### Code Quality
- [ ] Code follows existing patterns in codebase
- [ ] Structured logging is used (no f-strings in logs)
- [ ] Error handling follows documented patterns
- [ ] Type hints are complete
- [ ] Docstrings are present

### Testing
- [ ] Unit tests pass: `uv run pytest tests/unit/[relevant]/ -v`
- [ ] Type checking passes: `uv run mypy ruche/[relevant]/`
- [ ] No new warnings introduced

### Integration
- [ ] Imports work correctly
- [ ] No circular dependencies introduced
- [ ] Related code still works

### Report
- [ ] List files created
- [ ] List files modified
- [ ] List any deviations from docs (should be NONE)
- [ ] List any questions/concerns discovered
```

---

## Handling Ambiguity

When documentation is unclear or incomplete:

### Step 1: Search More

```bash
# Search for the term in all docs
grep -ri "ambiguous_term" docs/

# Search for related concepts
grep -ri "related_concept" docs/

# Check if there's a decision record
ls docs/design/decisions/
```

### Step 2: Check Existing Code

```bash
# Find similar implementations
grep -r "SimilarClass" ruche/

# Check how similar problems were solved
find ruche/ -name "*similar*" -exec head -50 {} \;
```

### Step 3: ASK, Don't Guess

If still unclear after searching:

```markdown
## Clarification Request

**Task**: [Task name]
**Ambiguity**: [What is unclear]
**Searched**:
- docs/[files searched]
- ruche/[code searched]

**Options I see**:
1. Option A: [description]
2. Option B: [description]

**My recommendation**: [if any]

**Waiting for clarification before proceeding.**
```

**NEVER proceed with guessing. ALWAYS wait for clarification.**

---

## Anti-Patterns (NEVER DO THESE)

### 1. Inventing Interfaces
```python
# BAD: Interface not in docs
class MyNewAbstraction(ABC):
    @abstractmethod
    async def my_invented_method(self): pass

# GOOD: Use documented interface
class DocumentedInterface(ABC):
    @abstractmethod
    async def documented_method(self): pass
```

### 2. Adding Undocumented Features
```python
# BAD: Feature not in docs
async def process(self, input, extra_feature=True):
    if extra_feature:
        self._do_extra_thing()  # Not documented!

# GOOD: Only documented behavior
async def process(self, input):
    # Exactly what docs specify
```

### 3. Changing Documented Names
```python
# BAD: Renamed from docs
class BetterNamedClass:  # Docs say "DocumentedName"
    pass

# GOOD: Exact name from docs
class DocumentedName:
    pass
```

### 4. Guessing at Behavior
```python
# BAD: Guessing what to return
async def get_items(self):
    # Docs don't specify sort order, I'll guess...
    return sorted(items, key=lambda x: x.created_at)

# GOOD: Ask for clarification
async def get_items(self):
    # QUESTION: Docs don't specify sort order.
    # Stopping to ask before implementing.
    raise NotImplementedError("Need clarification on sort order")
```

### 5. Over-Engineering
```python
# BAD: Adding abstractions not in docs
class ItemFactory:
    def create_item(self): ...

class ItemBuilder:
    def build(self): ...

# GOOD: Simple implementation per docs
def create_item(data: dict) -> Item:
    return Item(**data)
```

---

## Reporting Format

After completing a task, report in this format:

```markdown
## Task Completion Report: [Task Name]

### Summary
[1-2 sentence summary of what was done]

### Documentation Referenced
- `docs/[file1].md` - [what was learned]
- `docs/[file2].md` - [what was learned]

### Files Changed
| File | Action | Lines Changed |
|------|--------|---------------|
| `ruche/path/file.py` | Created | +150 |
| `ruche/path/other.py` | Modified | +20, -5 |

### Implementation Notes
- [Note about implementation choice, referencing docs]
- [Note about pattern followed]

### Tests
- `tests/unit/path/test_file.py` - [Created/Modified]
- Test results: [Pass/Fail]

### Deviations from Documentation
[SHOULD BE EMPTY - If not empty, explain why and get approval]

### Open Questions
[Any questions discovered during implementation]

### Verification
- [ ] Documentation compliance verified
- [ ] Code quality verified
- [ ] Tests pass
- [ ] Ready for review
```

---

## Quick Reference Card

```
╔══════════════════════════════════════════════════════════════╗
║                    SUBAGENT QUICK REFERENCE                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  BEFORE CODING:                                              ║
║  1. Read docs: docs/[relevant]/*.md                          ║
║  2. Read CLAUDE.md section                                   ║
║  3. Search: grep -r "keyword" docs/                          ║
║  4. Find patterns: grep -r "Similar" ruche/                  ║
║                                                              ║
║  WHILE CODING:                                               ║
║  • Use EXACT names from docs                                 ║
║  • Follow EXACT interfaces from docs                         ║
║  • Match EXISTING patterns in codebase                       ║
║  • NO invented features                                      ║
║  • NO guessing                                               ║
║                                                              ║
║  IF UNCLEAR:                                                 ║
║  • Search more docs                                          ║
║  • Check existing code                                       ║
║  • ASK - never guess                                         ║
║                                                              ║
║  AFTER CODING:                                               ║
║  • Verify against docs                                       ║
║  • Run tests: uv run pytest tests/unit/[relevant]/ -v        ║
║  • Type check: uv run mypy ruche/[relevant]/                 ║
║  • Report using standard format                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Appendix A: Common Documentation Locations

| Looking for... | Check here |
|----------------|------------|
| Brain phase behavior | `docs/focal_brain/spec/brain.md` |
| Data model fields | `docs/focal_brain/spec/data_models.md` |
| ACF behavior | `docs/acf/architecture/ACF_SPEC.md` |
| Store interfaces | `docs/design/decisions/001-storage-choice.md` |
| API endpoints | `docs/design/api-crud.md` |
| Error codes | `docs/architecture/error-handling.md` |
| Config structure | `docs/architecture/configuration-overview.md` |
| Logging patterns | `docs/architecture/observability.md` |
| Terminology | `CLAUDE.md` (Core Terminology section) |
| Coding standards | `CLAUDE.md` (Coding Standards section) |

---

## Appendix B: Exhaustive Implementation Checklists

These checklists ensure NOTHING is missed during implementation. Complete EVERY item.

### B.1 Checklist: Implementing a New Model

```markdown
## Model Implementation Checklist: [ModelName]

### Pre-Implementation
- [ ] Found model definition in docs: `docs/[file].md` line [X]
- [ ] Listed ALL fields from documentation
- [ ] Identified field types from documentation
- [ ] Identified required vs optional fields
- [ ] Identified default values from documentation
- [ ] Identified validators/constraints from documentation
- [ ] Found related models that this model references
- [ ] Found models that reference this model

### Implementation
- [ ] Created file: `ruche/[module]/models/[name].py`
- [ ] Added imports (Pydantic, UUID, datetime, etc.)
- [ ] Defined class with EXACT name from docs
- [ ] Added docstring describing the model
- [ ] Added ALL fields from docs (not one less, not one more):
  - [ ] Field 1: `name: type = Field(...)`
  - [ ] Field 2: `name: type = Field(...)`
  - [ ] [Continue for ALL fields]
- [ ] Added all validators from docs
- [ ] Added all computed properties from docs
- [ ] Added all methods from docs
- [ ] Set `model_config` appropriately (frozen, etc.)

### Verification
- [ ] Compare field-by-field with documentation
- [ ] Verified field types match docs exactly
- [ ] Verified field names match docs exactly
- [ ] Verified default values match docs exactly
- [ ] No extra fields added (not in docs)
- [ ] No fields missing (all from docs present)
- [ ] Import works: `from ruche.[module].models import ModelName`
- [ ] Can instantiate with valid data
- [ ] Validation rejects invalid data

### Testing
- [ ] Created test file: `tests/unit/[module]/test_[name].py`
- [ ] Test: Valid instantiation
- [ ] Test: Each validator
- [ ] Test: Each computed property
- [ ] Test: Serialization/deserialization
- [ ] Tests pass: `uv run pytest tests/unit/[module]/test_[name].py -v`
```

### B.2 Checklist: Implementing a Store Interface

```markdown
## Store Interface Checklist: [StoreName]

### Pre-Implementation
- [ ] Found interface definition in docs: `docs/design/decisions/001-storage-choice.md`
- [ ] Listed ALL methods from documentation
- [ ] For each method, documented:
  - [ ] Method signature (params, return type)
  - [ ] Expected behavior
  - [ ] Error conditions
- [ ] Identified which models this store handles
- [ ] Identified tenant isolation requirements

### Interface Implementation
- [ ] Created file: `ruche/[module]/store.py`
- [ ] Defined ABC class with EXACT name from docs
- [ ] Added docstring describing the store's purpose
- [ ] Defined ALL abstract methods from docs:
  - [ ] Method 1: signature matches docs exactly
  - [ ] Method 2: signature matches docs exactly
  - [ ] [Continue for ALL methods]
- [ ] Each method has docstring explaining behavior

### In-Memory Implementation
- [ ] Created file: `ruche/[module]/stores/inmemory.py`
- [ ] Class inherits from interface ABC
- [ ] Implemented ALL abstract methods
- [ ] Used appropriate data structures (dict, defaultdict)
- [ ] Implemented tenant isolation (all lookups by tenant_id)
- [ ] Handles not-found cases (returns None, not raises)

### PostgreSQL Implementation (if applicable)
- [ ] Created file: `ruche/[module]/stores/postgres.py`
- [ ] Class inherits from interface ABC
- [ ] Implemented ALL abstract methods
- [ ] All queries filter by `tenant_id`
- [ ] Uses soft deletes where documented (`deleted_at IS NULL`)
- [ ] Uses parameterized queries (no SQL injection)
- [ ] Proper async/await usage

### Contract Tests
- [ ] Created: `tests/contract/test_[store]_contract.py`
- [ ] Tests ALL interface methods
- [ ] Tests run against InMemory implementation
- [ ] Tests can run against Postgres implementation
- [ ] Tenant isolation tested
- [ ] Not-found behavior tested

### Verification
- [ ] ALL methods from docs implemented
- [ ] No extra methods added
- [ ] All signatures match docs
- [ ] Tests pass for all implementations
```

### B.3 Checklist: Implementing a Provider

```markdown
## Provider Implementation Checklist: [ProviderName]

### Pre-Implementation
- [ ] Found provider spec in docs: `docs/[file].md`
- [ ] Identified provider interface/ABC
- [ ] Listed ALL required methods
- [ ] Identified configuration requirements
- [ ] Identified API key/credential requirements
- [ ] Found example usage patterns

### Interface Review
- [ ] Located ABC: `ruche/infrastructure/providers/[type]/base.py`
- [ ] Listed all abstract methods to implement
- [ ] Listed all properties to implement
- [ ] Understood expected inputs/outputs

### Implementation
- [ ] Created file: `ruche/infrastructure/providers/[type]/[provider].py`
- [ ] Added imports
- [ ] Class inherits from ABC
- [ ] Implemented `provider_name` property
- [ ] Implemented ALL abstract methods:
  - [ ] Method 1: handles all documented cases
  - [ ] Method 2: handles all documented cases
  - [ ] [Continue for ALL methods]
- [ ] API key resolution from env var (documented var name)
- [ ] Error handling for API failures
- [ ] Proper async/await
- [ ] Structured logging for operations

### Configuration
- [ ] Provider can be configured via TOML
- [ ] Config model exists or created
- [ ] Default values are sensible
- [ ] API key uses SecretStr

### Testing
- [ ] Created: `tests/unit/providers/test_[provider].py`
- [ ] Test with mock responses
- [ ] Test error handling
- [ ] Test configuration
- [ ] Created: `tests/integration/providers/test_[provider].py` (optional)

### Registration
- [ ] Added to `__init__.py` exports
- [ ] Added to provider factory (if exists)
- [ ] Documented in README or provider docs
```

### B.4 Checklist: Implementing an API Endpoint

```markdown
## API Endpoint Checklist: [METHOD] [PATH]

### Pre-Implementation
- [ ] Found endpoint spec in docs: `docs/design/api-crud.md` or `docs/architecture/api-layer.md`
- [ ] Documented request format (params, body, headers)
- [ ] Documented response format (status codes, body)
- [ ] Documented error responses
- [ ] Identified required middleware (auth, rate limit, idempotency)
- [ ] Identified dependencies (stores, services)

### Request Model
- [ ] Created/found request model in `ruche/api/models/`
- [ ] All fields from docs present
- [ ] Validation rules match docs
- [ ] Field names match docs exactly

### Response Model
- [ ] Created/found response model in `ruche/api/models/`
- [ ] All fields from docs present
- [ ] Field names match docs exactly
- [ ] Status codes documented

### Route Implementation
- [ ] Located/created router file: `ruche/api/routes/[resource].py`
- [ ] Added route decorator with correct method and path
- [ ] Added response_model
- [ ] Added dependencies (Depends):
  - [ ] Authentication/tenant extraction
  - [ ] Store injection
  - [ ] Other services
- [ ] Implemented handler:
  - [ ] Input validation
  - [ ] Business logic
  - [ ] Error handling (correct HTTP codes)
  - [ ] Response construction
- [ ] Added docstring for OpenAPI

### Error Handling
- [ ] 400 for validation errors
- [ ] 401 for auth errors
- [ ] 403 for permission errors
- [ ] 404 for not found
- [ ] 409 for conflicts
- [ ] 429 for rate limit
- [ ] Error response format matches docs

### Testing
- [ ] Created: `tests/unit/api/test_[resource].py`
- [ ] Test happy path
- [ ] Test validation errors
- [ ] Test not found
- [ ] Test auth errors
- [ ] Test all documented error cases
- [ ] Test response format matches docs

### Registration
- [ ] Router included in `ruche/api/app.py`
- [ ] Endpoint appears in OpenAPI docs
```

### B.5 Checklist: Implementing a Brain Phase

```markdown
## Brain Phase Checklist: Phase [N] - [Name]

### Pre-Implementation
- [ ] Read phase spec in `docs/focal_brain/spec/brain.md` lines [X-Y]
- [ ] Listed ALL substeps (P[N].1, P[N].2, etc.)
- [ ] For each substep documented:
  - [ ] Input data
  - [ ] Processing logic
  - [ ] Output data
  - [ ] Error conditions
- [ ] Identified required models from `docs/focal_brain/spec/data_models.md`
- [ ] Identified dependencies (stores, providers, other phases)

### Phase Implementation

#### Substep P[N].1: [Name]
- [ ] Found/created implementation file
- [ ] Input matches docs: [describe]
- [ ] Processing matches docs: [describe]
- [ ] Output matches docs: [describe]
- [ ] Error handling per docs

#### Substep P[N].2: [Name]
- [ ] Found/created implementation file
- [ ] Input matches docs
- [ ] Processing matches docs
- [ ] Output matches docs
- [ ] Error handling per docs

[Continue for ALL substeps]

### Integration with Pipeline
- [ ] Phase called from correct location in `pipeline.py`
- [ ] Called in correct order (after P[N-1], before P[N+1])
- [ ] Input from previous phase correct
- [ ] Output to next phase correct
- [ ] Phase can be disabled via config

### Configuration
- [ ] Phase config exists in `ruche/config/models/pipeline.py`
- [ ] `enabled` flag
- [ ] All configurable parameters from docs
- [ ] Defaults match docs

### Logging & Tracing
- [ ] Phase start logged
- [ ] Phase completion logged
- [ ] Errors logged with context
- [ ] Span created for phase
- [ ] Metrics recorded

### Testing
- [ ] Unit tests for each substep
- [ ] Integration test for full phase
- [ ] Tests verify outputs match docs
- [ ] Edge cases tested

### Verification
- [ ] Re-read docs and compare implementation
- [ ] ALL substeps implemented (not one missing)
- [ ] NO extra substeps added (not in docs)
- [ ] Data flow matches docs exactly
```

### B.6 Checklist: Implementing ACF Component

```markdown
## ACF Component Checklist: [ComponentName]

### Pre-Implementation
- [ ] Found primary doc: `docs/acf/architecture/[file].md`
- [ ] Found topic doc (if any): `docs/acf/architecture/topics/[topic].md`
- [ ] Listed ALL requirements from docs
- [ ] Identified interfaces/protocols to implement
- [ ] Identified integration points with other ACF components
- [ ] Identified integration with Agent/Brain

### Interface/Protocol Definition
- [ ] Created/found protocol in `ruche/runtime/[location]/`
- [ ] ALL methods from docs defined
- [ ] Method signatures match docs exactly
- [ ] Documented non-serializability (if applicable)

### Implementation
- [ ] Created implementation class
- [ ] Implements ALL protocol methods
- [ ] Behavior matches docs for each method:
  - [ ] Method 1: behavior verified against docs
  - [ ] Method 2: behavior verified against docs
  - [ ] [Continue for ALL methods]
- [ ] Integrates with documented dependencies
- [ ] No invented behavior

### Hatchet Integration (if applicable)
- [ ] Workflow step defined
- [ ] Step behavior matches docs
- [ ] Failure handling matches docs
- [ ] Retry logic matches docs

### Redis/External Dependencies (if applicable)
- [ ] Key format matches docs
- [ ] TTL values match docs
- [ ] Error handling for connection failures

### Testing
- [ ] Unit tests for component
- [ ] Integration tests with Hatchet (if applicable)
- [ ] Tests verify all documented behaviors

### Verification
- [ ] Re-read ALL relevant docs
- [ ] Compare implementation line-by-line with docs
- [ ] No missing behaviors
- [ ] No invented behaviors
```

### B.7 Master Implementation Verification Checklist

Run this checklist AFTER completing any implementation:

```markdown
## Final Verification Checklist

### Documentation Compliance
- [ ] Re-read primary documentation for this task
- [ ] Every documented requirement has corresponding code
- [ ] No code exists without documentation backing
- [ ] Names match docs exactly (classes, methods, fields)
- [ ] Signatures match docs exactly (params, returns)
- [ ] Behavior matches docs exactly

### Code Quality
- [ ] No linting errors: `uv run ruff check ruche/[path]/`
- [ ] No type errors: `uv run mypy ruche/[path]/`
- [ ] Consistent with existing code style
- [ ] Structured logging (no f-strings in logs)
- [ ] Proper error handling
- [ ] Complete docstrings

### Testing
- [ ] Unit tests exist and pass
- [ ] Contract tests (if store/provider)
- [ ] Integration tests (if applicable)
- [ ] Coverage acceptable

### Integration
- [ ] Imports work from expected locations
- [ ] No circular imports
- [ ] Related components still work
- [ ] No breaking changes to existing code

### Configuration
- [ ] Config model exists (if needed)
- [ ] TOML section exists (if needed)
- [ ] Defaults are sensible
- [ ] Can be overridden via env vars

### Observability
- [ ] Logging at appropriate points
- [ ] Tracing spans (if applicable)
- [ ] Metrics (if applicable)

### Security
- [ ] No hardcoded secrets
- [ ] Tenant isolation maintained
- [ ] Input validation complete
- [ ] No SQL injection possible

### Documentation
- [ ] Code docstrings complete
- [ ] Any new patterns documented
- [ ] README updated (if significant change)

### Sign-off
- [ ] I verify this implementation matches documentation exactly
- [ ] I have not added any undocumented features
- [ ] I have not guessed at any behaviors
- [ ] All checklist items above are genuinely complete
```

---

## Appendix C: Task-Specific Checklists by Wave

### Wave 1 Task Checklists

<details>
<summary>1A: FOCAL Brain Consolidation</summary>

```markdown
## Task 1A: FOCAL Brain Consolidation

### Pre-Work
- [ ] Read both implementations:
  - [ ] `ruche/brains/focal/engine.py` (2076 lines)
  - [ ] `ruche/brains/focal/pipeline.py` (2098 lines)
- [ ] Identified all differences between them
- [ ] Verified `pipeline.py` is the canonical one to keep

### Execution
- [ ] Found all imports of `AlignmentEngine`:
  ```bash
  grep -r "from.*engine import AlignmentEngine" ruche/
  grep -r "AlignmentEngine" ruche/
  ```
- [ ] List of files to update: [list]
- [ ] Updated each import to use `FocalCognitivePipeline`
- [ ] Deleted `ruche/brains/focal/engine.py`
- [ ] Updated `ruche/brains/focal/__init__.py` exports

### Verification
- [ ] No remaining references to `AlignmentEngine`
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] No import errors
- [ ] Application starts successfully

### Completion
- [ ] Files deleted: `ruche/brains/focal/engine.py`
- [ ] Files modified: [list with changes]
```

</details>

<details>
<summary>1B: Missing Database Tables</summary>

```markdown
## Task 1B: Missing Database Tables

### Pre-Work
- [ ] Read docs for each table:
  - [ ] GlossaryItem: `docs/focal_brain/spec/data_models.md` lines [X]
  - [ ] Intent: `docs/[file].md` lines [X]
  - [ ] RuleRelationship: `docs/[file].md` lines [X]
- [ ] Documented ALL fields for each table
- [ ] Found existing migration patterns in `ruche/infrastructure/db/migrations/versions/`

### Migration 013: Glossary
- [ ] Created file: `013_glossary.py`
- [ ] Table name matches docs: `glossary_items`
- [ ] All columns from docs:
  - [ ] `id UUID PRIMARY KEY`
  - [ ] `tenant_id UUID NOT NULL`
  - [ ] `agent_id UUID NOT NULL`
  - [ ] `term VARCHAR(255) NOT NULL`
  - [ ] `definition TEXT NOT NULL`
  - [ ] `usage_hint TEXT`
  - [ ] `aliases TEXT[]`
  - [ ] `category VARCHAR(100)`
  - [ ] `priority INTEGER DEFAULT 0`
  - [ ] `enabled BOOLEAN DEFAULT true`
  - [ ] `created_at TIMESTAMPTZ`
  - [ ] `updated_at TIMESTAMPTZ`
- [ ] Indexes: `(tenant_id, agent_id)`
- [ ] Foreign keys (if any)

### Migration 014: Intents
- [ ] Created file: `014_intents.py`
- [ ] All columns from docs present
- [ ] Indexes appropriate
- [ ] Soft delete column: `deleted_at`

### Migration 015: Rule Relationships
- [ ] Created file: `015_rule_relationships.py`
- [ ] All columns from docs present
- [ ] Foreign keys to `rules` table
- [ ] Relationship type enum/check

### Store Updates
- [ ] Updated `PostgresAgentConfigStore`:
  - [ ] Removed `NotImplementedError` from glossary methods
  - [ ] Removed `NotImplementedError` from intent methods
  - [ ] Removed `NotImplementedError` from rule_relationship methods
- [ ] Implemented actual database queries

### Testing
- [ ] Migration runs successfully: `alembic upgrade head`
- [ ] Migration rollback works: `alembic downgrade -1`
- [ ] Store methods work with new tables
- [ ] Tests pass

### Completion
- [ ] Migrations created and tested
- [ ] Store implementation complete
- [ ] No more NotImplementedError for these methods
```

</details>

<details>
<summary>1F: OpenAI Embedding Provider</summary>

```markdown
## Task 1F: OpenAI Embedding Provider

### Pre-Work
- [ ] Read ABC: `ruche/infrastructure/providers/embedding/base.py`
- [ ] Read existing impl: `ruche/infrastructure/providers/embedding/jina.py`
- [ ] Read docs: `docs/design/embedding-model-management/overview.md`
- [ ] Listed all abstract methods to implement:
  - [ ] `provider_name` property
  - [ ] `dimensions` property
  - [ ] `embed(texts, model, **kwargs)`
  - [ ] `embed_single(text, model, **kwargs)`

### Implementation
- [ ] Created: `ruche/infrastructure/providers/embedding/openai.py`
- [ ] Class: `OpenAIEmbeddingProvider(EmbeddingProvider)`
- [ ] Implemented `provider_name` → `"openai"`
- [ ] Implemented `dimensions`:
  - [ ] `text-embedding-3-small` → 1536
  - [ ] `text-embedding-3-large` → 3072
- [ ] Implemented `embed`:
  - [ ] Uses `openai` SDK
  - [ ] Batches appropriately
  - [ ] Returns list of embeddings
- [ ] Implemented `embed_single`:
  - [ ] Calls `embed` with single item
- [ ] API key from `OPENAI_API_KEY` env var
- [ ] Error handling for API errors
- [ ] Structured logging

### Configuration
- [ ] Can be selected via config
- [ ] Model is configurable
- [ ] API key via SecretStr (if in config)

### Testing
- [ ] Created: `tests/unit/providers/embedding/test_openai.py`
- [ ] Test with mocked OpenAI client
- [ ] Test error handling
- [ ] Test different models

### Registration
- [ ] Added to `ruche/infrastructure/providers/embedding/__init__.py`
- [ ] Can be instantiated from factory

### Completion
- [ ] All abstract methods implemented
- [ ] Pattern matches existing providers
- [ ] Tests pass
```

</details>

[Additional task checklists would continue for each task in each wave...]
