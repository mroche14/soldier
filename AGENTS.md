# Focal Development Guidelines

## Project Overview

Focal is a **production-grade cognitive engine** for conversational AI. It replaces code-centric frameworks with an **API-first, multi-tenant, fully persistent** architecture designed for horizontal scaling.

**Core problem it solves**: Building reliable conversational agents without stuffing everything into prompts (unpredictable at scale) or defining behavior in code (no hot-reload, no horizontal scaling).

---

## Pre-Implementation Protocol

### 0. Follow the Implementation Plan

**CRITICAL**: Before implementing ANY feature, consult `IMPLEMENTATION_PLAN.md` at the project root.

This plan defines:
- **20 phases** of implementation in dependency order
- **Checkboxes** for tracking progress on each task
- **Document references** for each phase
- **The correct order** to build components (skeleton → config → observability → models → stores → providers → pipeline → API)

When asked to implement something:
1. Find the relevant phase in `IMPLEMENTATION_PLAN.md`
2. Check prerequisites are complete (earlier phases)
3. Follow the task list for that phase
4. **Mark checkboxes as complete when done** (change `- [ ]` to `- [x]`)
5. Reference the linked documentation for details

**Do NOT skip phases or implement out of order** - the plan is designed so each phase builds on the previous ones.

### Checkbox Tracking Reminder

**CRITICAL**: After completing ANY implementation task from `IMPLEMENTATION_PLAN.md`:
1. Immediately update the corresponding checkbox(es) from `- [ ]` to `- [x]`
2. This includes all sub-items under a task
3. Do NOT batch checkbox updates - mark each item complete as soon as it's done
4. This keeps the implementation plan accurate and helps track overall progress

### 1. Documentation is the Source of Truth

Before writing any code, you MUST:

1. **Check `IMPLEMENTATION_PLAN.md`** - Find which phase covers your task
2. **Read `docs/doc_skeleton.md`** - This is the index of all documentation
3. **Search relevant docs** using `mgrep` or `grep` for keywords related to your task
4. **Read the specific design docs** that cover your feature area

The documentation contains all architectural decisions, data models, and design rationale. Code should implement what the docs describe, not invent new patterns.

### 2. Codebase Analysis Before Changes

Before modifying existing code:

1. Use `mgrep` to find all usages of classes/functions you plan to change
2. Understand the existing patterns in the codebase
3. Check if similar functionality already exists (avoid duplication)
4. Review related test files to understand expected behavior

### 3. Key Documentation Reference

| Topic | Document |
|-------|----------|
| **Implementation Plan** | `IMPLEMENTATION_PLAN.md` |
| Project vision & goals | `docs/vision.md` |
| Architecture overview | `docs/architecture/overview.md` |
| Folder structure | `docs/architecture/folder-structure.md` |
| Domain models | `docs/design/domain-model.md` |
| Turn pipeline | `docs/design/turn-pipeline.md` |
| Alignment engine | `docs/architecture/alignment-engine.md` |
| Configuration system | `docs/architecture/configuration-overview.md` |
| Secrets management | `docs/architecture/configuration-secrets.md` |
| Storage interfaces | `docs/design/decisions/001-storage-choice.md` |
| Rule matching | `docs/design/decisions/002-rule-matching-strategy.md` |
| Observability | `docs/architecture/observability.md` |
| Memory layer | `docs/architecture/memory-layer.md` |
| Selection strategies | `docs/architecture/selection-strategies.md` |
| Scenario updates | `docs/design/scenario-update-methods.md` |
| Customer profile | `docs/design/customer-profile.md` |
| Testing strategy | `docs/development/testing-strategy.md` |
| Unit testing guide | `docs/development/unit-testing.md` |

---

## Core Architectural Principles

### 1. Zero In-Memory State

All state lives in external stores. Any pod must be able to serve any request.

**Implications**:
- No module-level caches without TTL
- No singleton patterns holding data
- Session state goes to `SessionStore`, not local variables
- Configuration loaded from TOML/Redis, not hardcoded

### 2. Multi-Tenant by Design

`tenant_id` appears on every entity, every query, every cache key.

**Implications**:
- All database queries filter by `tenant_id`
- Cache keys must include `tenant_id`
- Logs bind `tenant_id` in context
- Zero data leakage between tenants

### 3. Four Domain-Aligned Stores

The storage layer is split by conceptual domain:

| Store | Question | Contains |
|-------|----------|----------|
| `ConfigStore` | "How should it behave?" | Rules, Scenarios, Templates, Variables |
| `MemoryStore` | "What does it remember?" | Episodes, Entities, Relationships |
| `SessionStore` | "What's happening now?" | Session state, active step, variables |
| `AuditStore` | "What happened?" | Turn records, events (immutable) |

**Implications**:
- Don't mix concerns (e.g., no session data in ConfigStore)
- Each store has its own interface - implement against the interface
- In-memory implementations exist for testing

### 4. Provider Interfaces for AI Capabilities

All AI capabilities are accessed through abstract interfaces:

| Provider | Purpose |
|----------|---------|
| `LLMProvider` | Text generation (context extraction, filtering, generation) |
| `EmbeddingProvider` | Vector embeddings for semantic search |
| `RerankProvider` | Re-ordering search results by relevance |

**Implications**:
- Never hardcode to a specific AI provider
- Each pipeline step can use different providers
- Fallback chains are configured, not coded

### 5. Configuration Lives in Files, Not Code

> **Full documentation**: See `docs/architecture/configuration-overview.md` and `docs/architecture/configuration-secrets.md`

```
config/default.toml      → Base defaults (committed)
config/{env}.toml        → Environment overrides (committed)
.env                     → Secrets (gitignored, never committed)
FOCAL_* env vars       → Runtime overrides
```

**Configuration Loading Order** (later overrides earlier):
1. Pydantic model defaults
2. `config/default.toml`
3. `config/{FOCAL_ENV}.toml` (development, staging, production)
4. Environment variables (`FOCAL_*`)

**Implications**:
- No magic numbers in code
- All configurable values have Pydantic model defaults
- Use `get_settings()` to access configuration
- Secrets go in `.env`, never in TOML files

### 6. Secrets Management

**NEVER commit secrets to TOML files or code.**

**Secret Resolution Order**:
1. Secret Manager (production) - AWS Secrets Manager, HashiCorp Vault
2. Standard env vars - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
3. Focal-prefixed env vars - `FOCAL_PIPELINE__GENERATION__MODELS`
4. `.env` file (development only, gitignored)

**Common Provider Env Vars**:
| Provider | Variable |
|----------|----------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Cohere | `COHERE_API_KEY` |
| Voyage | `VOYAGE_API_KEY` |

**Development Setup**:
```bash
# Copy template and fill in your keys
cp .env.example .env

# .env is gitignored - never commit it
```

**In Code** - Use `SecretStr` for sensitive values:
```python
from pydantic import SecretStr

class ProviderConfig(BaseModel):
    api_key: SecretStr | None = None  # Never logged accidentally

    def get_api_key(self) -> str:
        if self.api_key:
            return self.api_key.get_secret_value()
        # Fallback to env var
        return os.environ["ANTHROPIC_API_KEY"]
```

---

## Coding Standards

### Naming Conventions

**Principle**: Names should be self-explanatory without being verbose. A reader should understand what something does from its name alone, without needing to read the implementation.

**Classes**: Use domain-specific nouns that describe *what it is* or *what it does*:

| Bad | Good | Why |
|-----|------|-----|
| `KGManager` | `MemoryStore` | What it stores is clear |
| `ProcessorV2` | `ContextExtractor` | What it does is clear |
| `Handler` | `RuleFilter` | Specific about the domain |
| `Utils` | `SelectionStrategy` | Describes the pattern |
| `Core` | `AlignmentEngine` | Describes the purpose |

**Methods**: Use verb phrases that describe the action. Be specific but concise:

| Bad | Good | Why |
|-----|------|-----|
| `process()` | `extract_intent()` | Says what it extracts |
| `do()` | `filter_by_scope()` | Clear action and target |
| `run()` | `generate_response()` | Specific outcome |
| `handle()` | `apply_migration()` | Domain-specific action |
| `get_data()` | `get_rules_for_agent()` | Says what data |

**Variables**: Use nouns that describe the content. Avoid abbreviations except well-known ones (`id`, `url`, `config`):

| Bad | Good |
|-----|------|
| `d` | `document` |
| `tmp` | `cached_result` |
| `res` | `response` or `matched_rules` |
| `cb` | `on_complete` or `callback` |
| `lst` | `rules` or `candidates` |

**Balance clarity and brevity**:
- `get_active_rules_for_agent_in_scenario()` → Too long, break into steps
- `get_rules()` → Too vague if context isn't obvious
- `get_scenario_rules(agent_id, scenario_id)` → Right balance

**When in doubt**: Optimize for reading, not writing. Code is read 10x more than it's written.

### Minimal Implementation Principle

**Write the least amount of code necessary** to fulfill the request. Do not anticipate future needs.

**Do NOT**:
- Add features, refactor code, or make "improvements" beyond what was explicitly requested
- Create abstractions, helpers, or utilities for single use cases
- Add error handling for scenarios that cannot happen
- Write "nice to have" code alongside the main task
- Add docstrings, comments, or type annotations to code you didn't change
- Design for hypothetical future requirements

**Do**:
- Solve the current problem only
- Prefer simple, readable code over clever solutions
- Accept three similar lines of code over a premature abstraction
- Trust internal code and framework guarantees
- Only validate at system boundaries (user input, external APIs)

**Examples**:

| Request | Wrong | Right |
|---------|-------|-------|
| "Add a `get_user` method" | Add `get_user`, `get_users`, `find_user`, `search_users` | Add only `get_user` |
| "Fix the null check bug" | Fix bug + refactor surrounding code + add logging | Fix only the null check |
| "Create Rule model" | Create Rule + RuleBuilder + RuleValidator + RuleFactory | Create only Rule |

**The right amount of complexity is the minimum needed for the current task.**

### Object-Oriented Patterns

This project follows OOP principles:

```python
# Good: Clear class with single responsibility
class RuleRetriever:
    """Retrieves candidate rules using vector similarity."""

    def __init__(self, config_store: ConfigStore, embedding_provider: EmbeddingProvider):
        self._config_store = config_store
        self._embedding_provider = embedding_provider

    async def retrieve(self, context: Context, session: Session) -> list[Rule]:
        ...

# Bad: God class doing everything
class Engine:
    def do_everything(self, message, session, config, ...):
        ...
```

### Dependency Injection

Classes receive their dependencies, they don't create them:

```python
# Good: Dependencies injected
class AlignmentEngine:
    def __init__(
        self,
        context_extractor: ContextExtractor,
        rule_retriever: RuleRetriever,
        response_generator: ResponseGenerator,
    ):
        ...

# Bad: Creating dependencies inside
class AlignmentEngine:
    def __init__(self):
        self.extractor = ContextExtractor()  # Tight coupling
```

### Async Everything

Focal is async-first. All I/O operations are async:

```python
# Good
async def get_rules(self, tenant_id: UUID) -> list[Rule]:
    ...

# Bad: Blocking call in async context
def get_rules(self, tenant_id: UUID) -> list[Rule]:
    ...
```

### Package Management (uv)

This project uses **uv** for Python package and environment management.

**Adding dependencies**:
```bash
# Add a package (latest version)
uv add pydantic

# Add a dev dependency
uv add --dev pytest

# NEVER pin specific versions unless absolutely necessary
# uv will resolve and lock the latest compatible versions
```

**Do NOT**:
- Specify version numbers when adding packages (`uv add pydantic==2.5.0`)
- Manually edit `pyproject.toml` to add version constraints
- Use pip, poetry, or other package managers

**Do**:
- Let uv resolve latest compatible versions
- Use `uv.lock` for reproducible builds (committed to git)
- Run `uv sync` to install dependencies from lock file

**Running commands**:
```bash
# Run Python scripts
uv run python script.py

# Run pytest
uv run pytest

# Run the application
uv run focal
```

### Import Rules

**Never wrap imports in try/except blocks**:

```python
# BAD - Masks missing dependencies, fails silently later
try:
    import anthropic
except ImportError:
    anthropic = None  # Will cause cryptic errors later

# BAD - Same problem with conditional behavior
try:
    from focal.memory.stores.neo4j import Neo4jMemoryStore
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

# GOOD - Let it crash immediately with clear error
import anthropic
from focal.memory.stores.neo4j import Neo4jMemoryStore
```

**Why**: Missing dependencies should crash immediately at import time with a clear `ModuleNotFoundError`, not fail unpredictably later when the code tries to use the missing module.

**Exception**: Only acceptable for optional runtime plugins loaded dynamically via configuration, and even then prefer explicit checks over try/except.

---

## Code Organization

### Folder Structure Philosophy

```
Code follows concepts, not technical layers.

Ask: "Where would I look for X?"
Answer: In the folder named after X.
```

| Looking for... | Location |
|----------------|----------|
| Rule matching logic | `focal/alignment/retrieval/` |
| Memory storage | `focal/memory/stores/` |
| Session management | `focal/conversation/` |
| API endpoints | `focal/api/routes/` |
| Configuration models | `focal/config/models/` |
| Logging setup | `focal/observability/` |

### No Duplication

Before creating a new class/function:

1. Search if it already exists
2. Check if extending an existing class makes sense
3. Consider if this belongs in an existing module

### Interface-First Design

When adding new capabilities:

1. Define the abstract interface (ABC) first
2. Create an in-memory implementation for testing
3. Then implement the production backend

```python
# 1. Interface
class NewStore(ABC):
    @abstractmethod
    async def operation(self) -> Result:
        pass

# 2. Test implementation
class InMemoryNewStore(NewStore):
    async def operation(self) -> Result:
        ...

# 3. Production implementation
class PostgresNewStore(NewStore):
    async def operation(self) -> Result:
        ...
```

---

## Observability Requirements

### Structured Logging

All logging uses `structlog` with JSON output. Every log entry includes context:

```python
from focal.observability.logging import get_logger

logger = get_logger(__name__)

# Good: Structured with context
logger.info(
    "rule_matched",
    rule_id=rule.id,
    score=score,
    tenant_id=tenant_id,
)

# Bad: Unstructured string
logger.info(f"Matched rule {rule.id} with score {score}")
```

### Required Context Fields

Every log must be traceable. These are bound automatically by middleware:
- `tenant_id`
- `agent_id`
- `session_id`
- `turn_id`
- `trace_id`

### Never Log Secrets or PII

```python
# Bad: Logging secrets
logger.info("api_key", key=api_key)

# Bad: Logging user message at INFO
logger.info("user_message", message=user_input)

# Good: Sensitive data only at DEBUG
logger.debug("user_message", message=user_input)
```

---

## Testing Standards

> **Full documentation**: See `docs/development/testing-strategy.md` and `docs/development/unit-testing.md`

### Test Pyramid

| Layer | Purpose | Speed | Dependencies |
|-------|---------|-------|--------------|
| **Unit** (80%) | Single class/function | < 10ms each | In-memory, mocks |
| **Integration** (15%) | Component boundaries | < 1s each | Real backends (Docker) |
| **E2E** (5%) | Full request flow | < 10s each | Full stack |

### Coverage Requirements

- **Overall**: 85% line coverage, 80% branch coverage
- **Alignment/Memory modules**: 85% minimum
- Coverage enforced in CI - PRs fail below threshold

### Unit Test Quick Reference

**Naming**: `test_<method>_<scenario>_<expected_behavior>`

```python
# Good
def test_retrieve_when_no_rules_exist_returns_empty_list():
def test_save_rule_with_duplicate_id_raises_conflict_error():
```

**Structure**: Arrange-Act-Assert

```python
async def test_save_rule_persists_to_store(self, store, sample_rule):
    # Arrange (fixtures provide setup)

    # Act
    await store.save_rule(sample_rule)
    retrieved = await store.get_rule(sample_rule.tenant_id, sample_rule.id)

    # Assert
    assert retrieved == sample_rule
```

**Fixtures**: Use in-memory implementations for stores, mocks for providers

```python
@pytest.fixture
def config_store():
    return InMemoryConfigStore()

@pytest.fixture
def llm_provider():
    return MockLLMProvider(default_response="Test response")
```

**Factories**: Create test data with sensible defaults

```python
rule = RuleFactory.create(priority=100, tenant_id=my_tenant_id)
rules = RuleFactory.create_batch(5, agent_id=my_agent_id)
```

### What to Test

| Component | Test Focus |
|-----------|------------|
| **Store implementations** | CRUD, queries, tenant isolation, vector search |
| **Selection strategies** | Score analysis, edge cases, boundary conditions |
| **Pipeline steps** | Input/output transformation, error handling |
| **Domain models** | Validation, computed properties, state transitions |

### Contract Tests

Every Store/Provider implementation must pass the same contract tests:

```python
class TestInMemoryConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()

class TestPostgresConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self, postgres_connection):
        return PostgresConfigStore(postgres_connection)
```

---

## Pipeline Development

### Turn Pipeline Steps

The alignment engine processes turns through these steps:

1. **Context Extraction** - Understand user intent
2. **Retrieval** - Find candidate rules/scenarios/memory
3. **Reranking** - Improve candidate ordering
4. **LLM Filtering** - Judge which rules apply
5. **Tool Execution** - Run tools from matched rules
6. **Response Generation** - Generate response
7. **Enforcement** - Validate against constraints

### Adding Pipeline Steps

Each step should be:
- Independently configurable via TOML
- Optional (can be disabled)
- Logged with timing
- Traceable (span per step)

```toml
[pipeline.new_step]
enabled = true
provider = "some_provider"
```

### Separation of Concerns

**RuleFilter** and **ScenarioFilter** are separate:

| Filter | Responsibility |
|--------|----------------|
| `RuleFilter` | Which rules apply to this turn? |
| `ScenarioFilter` | Which step should we be in? |

Don't conflate these responsibilities.

---

## Data Model Principles

### Tenant Scoping

```python
class TenantScopedModel(BaseModel):
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

class AgentScopedModel(TenantScopedModel):
    agent_id: UUID
```

### Soft Deletes

Use `deleted_at` instead of hard deletes for audit trail:

```python
deleted_at: Optional[datetime] = None  # None = not deleted
```

### Precomputed Embeddings

Store embeddings alongside text to avoid recomputation:

```python
condition_text: str
condition_embedding: Optional[list[float]] = None
embedding_model: Optional[str] = None  # Track which model generated it
```

---

## Error Handling

### Graceful Degradation

The system should degrade gracefully:

```python
# Good: Fallback chain
try:
    response = await primary_llm.generate(prompt)
except ProviderError:
    response = await fallback_llm.generate(prompt)
```

### Never Swallow Errors Silently

```python
# Bad
try:
    ...
except Exception:
    pass  # Silent failure

# Good
try:
    ...
except SpecificError as e:
    logger.error("operation_failed", error=str(e))
    raise
```

---

## Speckit Integration

This project uses speckit for feature implementation. When implementing features:

1. Run `/speckit.specify` to create the feature spec
2. Run `/speckit.clarify` if requirements are ambiguous
3. Run `/speckit.plan` to generate implementation plan
4. Run `/speckit.tasks` to generate actionable tasks
5. Run `/speckit.analyze` to check consistency
6. Run `/speckit.implement` to execute tasks

---

## Quick Reference: Don't Do This

| Don't | Do Instead |
|-------|------------|
| Hardcode configuration values | Put in TOML with Pydantic defaults |
| Create singletons holding state | Use dependency injection |
| Mix storage concerns | Use the appropriate Store interface |
| Log secrets or PII at INFO | Use DEBUG level for sensitive data |
| Create vague class names | Use domain-specific descriptive names |
| Skip reading docs | Read `docs/doc_skeleton.md` first |
| Duplicate existing functionality | Search codebase with mgrep |
| Tight-couple to specific providers | Code against interfaces |
| Use blocking I/O | Use async throughout |
| Skip tenant_id in queries | Always filter by tenant |

---

## Version Information

- **Last Updated**: 2025-01-15
- **Based on Documentation Version**: Initial architecture

## Active Technologies
- Python 3.11+ (required for `tomllib` built-in) + pydantic, pydantic-settings, structlog (001-project-foundation)
- N/A (configuration phase - no database yet) (001-project-foundation)
- Python 3.11+ (required for built-in `tomllib`) + pydantic, pydantic-settings, structlog, prometheus_client, opentelemetry-sdk, opentelemetry-exporter-otlp (003-core-abstractions)
- In-memory only (dict-based implementations for testing/development) (003-core-abstractions)
- Python 3.11+ + pydantic, pydantic-settings, structlog, prometheus-client, opentelemetry-sdk (existing); numpy, scipy, scikit-learn (new for selection strategies) (004-alignment-pipeline)
- In-memory stores (existing); ConfigStore, MemoryStore, SessionStore, AuditStore interfaces already defined (004-alignment-pipeline)

## Recent Changes
- 001-project-foundation: Added Python 3.11+ (required for `tomllib` built-in) + pydantic, pydantic-settings, structlog
