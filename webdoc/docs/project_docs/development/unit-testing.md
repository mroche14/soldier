# Unit Testing Guide

This document provides concrete guidance for writing unit tests in the Soldier codebase. It covers naming conventions, patterns, fixture composition, async testing, and provides templates for testing different component types.

---

## Core Principles

1. **One test, one behavior**: Each test verifies exactly one thing
2. **Fast**: Individual tests run in milliseconds
3. **Isolated**: No shared state between tests
4. **Deterministic**: Same input always produces same output
5. **Readable**: Test name describes the scenario and expectation

---

## Test Structure

### File Organization

Test files mirror the source structure:

```
soldier/alignment/retrieval/rule_retriever.py
    → tests/unit/alignment/retrieval/test_rule_retriever.py

soldier/memory/stores/inmemory.py
    → tests/unit/memory/stores/test_inmemory.py

soldier/providers/llm/base.py
    → tests/unit/providers/llm/test_base.py
```

### File Layout

```python
# tests/unit/alignment/retrieval/test_rule_retriever.py
"""Unit tests for RuleRetriever."""

import pytest
from uuid import uuid4

from soldier.alignment.retrieval.rule_retriever import RuleRetriever
from soldier.alignment.models import Rule, Context
from tests.factories import RuleFactory, ContextFactory


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def config_store():
    """In-memory config store for testing."""
    return InMemoryConfigStore()


@pytest.fixture
def embedding_provider():
    """Mock embedding provider."""
    return MockEmbeddingProvider(dimensions=384)


@pytest.fixture
def retriever(config_store, embedding_provider):
    """RuleRetriever instance under test."""
    return RuleRetriever(
        config_store=config_store,
        embedding_provider=embedding_provider,
    )


# ============================================================
# Tests: retrieve()
# ============================================================

class TestRetrieve:
    """Tests for RuleRetriever.retrieve()"""

    async def test_returns_empty_list_when_no_rules_exist(
        self, retriever, sample_context
    ):
        """When no rules exist, retrieve returns empty list."""
        results = await retriever.retrieve(sample_context)
        assert results == []

    async def test_returns_matching_rules_sorted_by_score(
        self, retriever, config_store, sample_context
    ):
        """Matching rules are returned sorted by similarity score."""
        # Arrange
        rules = RuleFactory.create_batch(3, agent_id=sample_context.agent_id)
        for rule in rules:
            await config_store.save_rule(rule)

        # Act
        results = await retriever.retrieve(sample_context)

        # Assert
        assert len(results) == 3
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    async def test_filters_by_tenant_id(
        self, retriever, config_store, sample_context
    ):
        """Only rules from the same tenant are returned."""
        # Arrange
        same_tenant_rule = RuleFactory.create(
            tenant_id=sample_context.tenant_id,
            agent_id=sample_context.agent_id,
        )
        other_tenant_rule = RuleFactory.create(
            tenant_id=uuid4(),  # Different tenant
            agent_id=sample_context.agent_id,
        )
        await config_store.save_rule(same_tenant_rule)
        await config_store.save_rule(other_tenant_rule)

        # Act
        results = await retriever.retrieve(sample_context)

        # Assert
        assert len(results) == 1
        assert results[0].rule.id == same_tenant_rule.id


# ============================================================
# Tests: _apply_scope_filter()
# ============================================================

class TestApplyScopeFilter:
    """Tests for RuleRetriever._apply_scope_filter()"""

    async def test_global_rules_always_included(self, retriever):
        """Global scope rules are included regardless of scenario."""
        # ...

    async def test_scenario_rules_included_when_in_scenario(self, retriever):
        """Scenario scope rules included when session is in that scenario."""
        # ...
```

---

## Naming Conventions

### Test Functions

Use the pattern: `test_<method>_<scenario>_<expected_behavior>`

```python
# Good
def test_retrieve_when_no_rules_exist_returns_empty_list():
def test_save_rule_with_duplicate_id_raises_conflict_error():
def test_generate_with_empty_prompt_raises_validation_error():

# Bad
def test_retrieve():  # Too vague
def test_it_works():  # Meaningless
def test_rule_retriever():  # Not specific
```

### Test Classes

Group related tests in classes named `Test<MethodOrBehavior>`:

```python
class TestRetrieve:
    """Tests for the retrieve() method."""

class TestSaveRule:
    """Tests for the save_rule() method."""

class TestTenantIsolation:
    """Tests verifying tenant isolation across methods."""
```

### Fixture Names

Use descriptive names that indicate what the fixture provides:

```python
# Good
@pytest.fixture
def sample_rule():
    """A valid Rule instance for testing."""

@pytest.fixture
def expired_session():
    """A Session that has exceeded its TTL."""

@pytest.fixture
def config_store_with_rules():
    """ConfigStore pre-populated with test rules."""

# Bad
@pytest.fixture
def data():  # Too vague

@pytest.fixture
def x():  # Meaningless
```

---

## Arrange-Act-Assert Pattern

Every test follows the AAA pattern:

```python
async def test_save_rule_persists_rule_to_store(self, config_store, sample_rule):
    """Saved rules can be retrieved by ID."""

    # Arrange - Set up preconditions
    # (sample_rule is provided by fixture)

    # Act - Execute the behavior under test
    await config_store.save_rule(sample_rule)
    retrieved = await config_store.get_rule(
        sample_rule.tenant_id,
        sample_rule.id,
    )

    # Assert - Verify the outcome
    assert retrieved is not None
    assert retrieved.id == sample_rule.id
    assert retrieved.condition_text == sample_rule.condition_text
```

For simple tests, comments are optional but the structure remains:

```python
async def test_get_nonexistent_rule_returns_none(self, config_store):
    result = await config_store.get_rule(uuid4(), uuid4())
    assert result is None
```

---

## Async Testing

### Configuration

Soldier uses `pytest-asyncio` in auto mode:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

### Writing Async Tests

All async tests and fixtures use `async def`:

```python
# Async test
async def test_retrieve_returns_rules(self, retriever, sample_context):
    results = await retriever.retrieve(sample_context)
    assert isinstance(results, list)


# Async fixture
@pytest.fixture
async def session_with_history(session_store, sample_session):
    """Session with pre-existing turn history."""
    await session_store.save(sample_session)
    # Add some turns...
    return sample_session
```

### Testing Async Generators

```python
async def test_stream_generates_chunks(self, generator):
    """Streaming generation yields chunks."""
    chunks = []
    async for chunk in generator.stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert all(isinstance(c, str) for c in chunks)
```

### Testing Timeouts

```python
async def test_generate_respects_timeout(self, slow_provider):
    """Generation times out after configured duration."""
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            slow_provider.generate("Hello"),
            timeout=0.1,
        )
```

---

## Fixture Composition

### Building Complex Test Objects

Use fixture composition to build objects with dependencies:

```python
# Base fixtures
@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


# Composed fixtures
@pytest.fixture
def sample_rule(tenant_id, agent_id):
    """Rule belonging to the test tenant/agent."""
    return RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
    )


@pytest.fixture
def sample_scenario(tenant_id, agent_id):
    """Scenario belonging to the test tenant/agent."""
    return ScenarioFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
    )


@pytest.fixture
def sample_session(tenant_id, agent_id, sample_scenario):
    """Active session in the test scenario."""
    return SessionFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        active_scenario_id=sample_scenario.id,
    )


@pytest.fixture
def sample_context(tenant_id, agent_id, sample_session):
    """Context for a turn in the test session."""
    return ContextFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session=sample_session,
        user_message="I want to return my order",
    )
```

### Parameterized Fixtures

Use `pytest.fixture(params=...)` for testing multiple variants:

```python
@pytest.fixture(params=["inmemory", "postgres", "mongodb"])
def config_store(request):
    """ConfigStore implementation to test."""
    if request.param == "inmemory":
        return InMemoryConfigStore()
    elif request.param == "postgres":
        pytest.skip("Postgres tests run in integration")
    elif request.param == "mongodb":
        pytest.skip("MongoDB tests run in integration")
```

---

## Factories

### Factory Pattern

Use factories to create test objects with sensible defaults:

```python
# tests/factories.py
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime

from soldier.alignment.models import Rule, RuleScope


@dataclass
class RuleFactory:
    """Factory for creating test Rule instances."""

    tenant_id: UUID = field(default_factory=uuid4)
    agent_id: UUID = field(default_factory=uuid4)
    condition_text: str = "User asks about returns"
    action_text: str = "Explain the return policy"
    scope: RuleScope = RuleScope.GLOBAL
    priority: int = 1
    enabled: bool = True

    def build(self, **overrides) -> Rule:
        """Build a Rule with optional overrides."""
        attrs = {
            "id": uuid4(),
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "condition_text": self.condition_text,
            "action_text": self.action_text,
            "scope": self.scope,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        attrs.update(overrides)
        return Rule(**attrs)

    @classmethod
    def create(cls, **kwargs) -> Rule:
        """Shorthand for RuleFactory().build(**kwargs)."""
        factory = cls()
        return factory.build(**kwargs)

    @classmethod
    def create_batch(cls, count: int, **shared_kwargs) -> list[Rule]:
        """Create multiple rules with shared attributes."""
        factory = cls(**{k: v for k, v in shared_kwargs.items()
                        if k in cls.__dataclass_fields__})
        overrides = {k: v for k, v in shared_kwargs.items()
                    if k not in cls.__dataclass_fields__}
        return [factory.build(**overrides) for _ in range(count)]
```

### Using Factories

```python
# Simple creation
rule = RuleFactory.create()

# With overrides
high_priority_rule = RuleFactory.create(priority=100)

# Batch with shared attributes
tenant_rules = RuleFactory.create_batch(
    count=5,
    tenant_id=my_tenant_id,
    agent_id=my_agent_id,
)

# Using factory instance for related objects
factory = RuleFactory(tenant_id=tenant_id, agent_id=agent_id)
rule1 = factory.build(condition_text="condition 1")
rule2 = factory.build(condition_text="condition 2")
# Both rules belong to same tenant/agent
```

---

## Mocking

### When to Mock

| Situation | Mock? | Use Instead |
|-----------|-------|-------------|
| External API (Anthropic, OpenAI) | Yes | MockLLMProvider |
| Database | No | InMemoryStore |
| Time/dates | Yes | `freezegun` |
| Random values | Yes | Fixed seed or patch |
| Other internal classes | Rarely | Real implementation |

### Mock Providers

Use the built-in mock providers for AI capabilities:

```python
@pytest.fixture
def llm_provider():
    """Mock LLM that returns predictable responses."""
    return MockLLMProvider(
        default_response="This is a test response",
        structured_responses={
            "UserIntent": UserIntent(intent="return_product", confidence=0.95),
        },
    )


@pytest.fixture
def embedding_provider():
    """Mock embeddings with deterministic vectors."""
    return MockEmbeddingProvider(
        dimensions=384,
        # Optionally configure specific embeddings
        embeddings={
            "return policy": [0.1, 0.2, ...],
        },
    )
```

### Patching

When mocking is necessary, use `pytest-mock`:

```python
async def test_handles_provider_timeout(self, mocker, retriever):
    """Retriever handles provider timeout gracefully."""
    mocker.patch.object(
        retriever._embedding_provider,
        "embed",
        side_effect=TimeoutError("Provider timeout"),
    )

    # Should not raise, should return empty or use fallback
    results = await retriever.retrieve(sample_context)
    assert results == []
```

### Time Mocking

Use `freezegun` for time-dependent tests:

```python
from freezegun import freeze_time

@freeze_time("2025-01-15 10:00:00")
async def test_session_expires_after_ttl(self, session_store):
    """Sessions are marked expired after TTL."""
    session = SessionFactory.create(ttl_seconds=3600)
    await session_store.save(session)

    # Fast forward 2 hours
    with freeze_time("2025-01-15 12:00:00"):
        retrieved = await session_store.get(session.id)
        assert retrieved.is_expired is True
```

---

## Testing Specific Components

### Testing Store Implementations

```python
class TestInMemoryConfigStore:
    """Unit tests for InMemoryConfigStore."""

    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()

    # CRUD operations
    async def test_save_rule_creates_new_rule(self, store, sample_rule):
        await store.save_rule(sample_rule)
        retrieved = await store.get_rule(sample_rule.tenant_id, sample_rule.id)
        assert retrieved == sample_rule

    async def test_save_rule_updates_existing_rule(self, store, sample_rule):
        await store.save_rule(sample_rule)
        sample_rule.priority = 999
        await store.save_rule(sample_rule)
        retrieved = await store.get_rule(sample_rule.tenant_id, sample_rule.id)
        assert retrieved.priority == 999

    async def test_delete_rule_removes_rule(self, store, sample_rule):
        await store.save_rule(sample_rule)
        await store.delete_rule(sample_rule.tenant_id, sample_rule.id)
        retrieved = await store.get_rule(sample_rule.tenant_id, sample_rule.id)
        assert retrieved is None

    # Queries
    async def test_get_rules_returns_all_for_agent(self, store, tenant_id, agent_id):
        rules = RuleFactory.create_batch(5, tenant_id=tenant_id, agent_id=agent_id)
        for rule in rules:
            await store.save_rule(rule)

        results = await store.get_rules(tenant_id, agent_id)
        assert len(results) == 5

    # Tenant isolation
    async def test_get_rules_isolates_tenants(self, store):
        tenant_a = uuid4()
        tenant_b = uuid4()
        agent_id = uuid4()

        rule_a = RuleFactory.create(tenant_id=tenant_a, agent_id=agent_id)
        rule_b = RuleFactory.create(tenant_id=tenant_b, agent_id=agent_id)
        await store.save_rule(rule_a)
        await store.save_rule(rule_b)

        results = await store.get_rules(tenant_a, agent_id)
        assert len(results) == 1
        assert results[0].id == rule_a.id

    # Vector search
    async def test_vector_search_returns_similar_rules(self, store, embedding_provider):
        # Create rules with embeddings
        rule = RuleFactory.create()
        rule.condition_embedding = await embedding_provider.embed(rule.condition_text)
        await store.save_rule(rule)

        # Search with same embedding
        results = await store.vector_search_rules(
            tenant_id=rule.tenant_id,
            agent_id=rule.agent_id,
            embedding=rule.condition_embedding,
            limit=10,
        )
        assert len(results) >= 1
        assert results[0].id == rule.id
```

### Testing Selection Strategies

```python
class TestElbowSelectionStrategy:
    """Unit tests for ElbowSelectionStrategy."""

    @pytest.fixture
    def strategy(self):
        return ElbowSelectionStrategy(
            drop_threshold=0.2,
            min_items=1,
            max_items=10,
        )

    def test_selects_items_before_score_drop(self, strategy):
        """Items before significant score drop are selected."""
        items = [
            ScoredItem(id="a", score=0.95),
            ScoredItem(id="b", score=0.90),
            ScoredItem(id="c", score=0.85),
            ScoredItem(id="d", score=0.50),  # Big drop here
            ScoredItem(id="e", score=0.45),
        ]

        result = strategy.select(items)

        assert len(result.selected) == 3
        assert [i.id for i in result.selected] == ["a", "b", "c"]

    def test_respects_min_items(self, strategy):
        """At least min_items are returned even with early drop."""
        items = [
            ScoredItem(id="a", score=0.95),
            ScoredItem(id="b", score=0.50),  # Immediate drop
        ]

        result = strategy.select(items)

        assert len(result.selected) >= 1

    def test_respects_max_items(self, strategy):
        """No more than max_items are returned."""
        items = [ScoredItem(id=str(i), score=0.99 - i*0.001) for i in range(20)]

        result = strategy.select(items)

        assert len(result.selected) <= 10

    def test_handles_empty_input(self, strategy):
        """Empty input returns empty selection."""
        result = strategy.select([])

        assert result.selected == []

    def test_handles_single_item(self, strategy):
        """Single item is returned."""
        items = [ScoredItem(id="a", score=0.95)]

        result = strategy.select(items)

        assert len(result.selected) == 1

    def test_handles_identical_scores(self, strategy):
        """All items with identical scores are selected up to max."""
        items = [ScoredItem(id=str(i), score=0.80) for i in range(5)]

        result = strategy.select(items)

        # No drop, so all should be selected (up to max)
        assert len(result.selected) == 5
```

### Testing Pipeline Steps

```python
class TestContextExtractor:
    """Unit tests for ContextExtractor."""

    @pytest.fixture
    def extractor(self, llm_provider):
        return LLMContextExtractor(
            llm_provider=llm_provider,
            history_turns=5,
        )

    async def test_extracts_intent_from_message(self, extractor):
        """User intent is extracted from message."""
        context = await extractor.extract(
            message="I want to return my order",
            history=[],
        )

        assert context.intent is not None
        assert context.intent.primary_intent == "return_product"

    async def test_includes_conversation_history(self, extractor, sample_history):
        """Extraction considers conversation history."""
        context = await extractor.extract(
            message="Yes, that one",  # Ambiguous without history
            history=sample_history,
        )

        # Should understand "that one" from history
        assert context.resolved_references is not None

    async def test_extracts_entities(self, extractor):
        """Named entities are extracted from message."""
        context = await extractor.extract(
            message="I ordered product SKU-12345 last Tuesday",
            history=[],
        )

        assert "SKU-12345" in [e.value for e in context.entities]
        assert any(e.type == "product_sku" for e in context.entities)

    async def test_handles_empty_message(self, extractor):
        """Empty message returns minimal context."""
        context = await extractor.extract(message="", history=[])

        assert context is not None
        assert context.intent is None or context.intent.confidence < 0.5
```

### Testing Domain Models

```python
class TestRule:
    """Unit tests for Rule model."""

    def test_validates_required_fields(self):
        """Rule requires tenant_id, agent_id, condition_text."""
        with pytest.raises(ValidationError) as exc_info:
            Rule(
                id=uuid4(),
                # Missing tenant_id, agent_id, condition_text
            )

        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "tenant_id" in missing_fields
        assert "agent_id" in missing_fields
        assert "condition_text" in missing_fields

    def test_priority_must_be_positive(self):
        """Rule priority must be >= 0."""
        with pytest.raises(ValidationError):
            RuleFactory.create(priority=-1)

    def test_is_active_checks_enabled_and_not_deleted(self):
        """is_active property checks enabled flag and deleted_at."""
        rule = RuleFactory.create(enabled=True, deleted_at=None)
        assert rule.is_active is True

        rule.enabled = False
        assert rule.is_active is False

        rule.enabled = True
        rule.deleted_at = datetime.utcnow()
        assert rule.is_active is False

    def test_matches_scope_global(self):
        """Global scope rules match any context."""
        rule = RuleFactory.create(scope=RuleScope.GLOBAL)

        assert rule.matches_scope(scenario_id=None, step_id=None) is True
        assert rule.matches_scope(scenario_id=uuid4(), step_id=None) is True
        assert rule.matches_scope(scenario_id=uuid4(), step_id=uuid4()) is True

    def test_matches_scope_scenario(self):
        """Scenario scope rules only match their scenario."""
        scenario_id = uuid4()
        rule = RuleFactory.create(
            scope=RuleScope.SCENARIO,
            scenario_id=scenario_id,
        )

        assert rule.matches_scope(scenario_id=scenario_id, step_id=None) is True
        assert rule.matches_scope(scenario_id=uuid4(), step_id=None) is False
        assert rule.matches_scope(scenario_id=None, step_id=None) is False
```

---

## Parametrized Tests

Use `@pytest.mark.parametrize` for testing multiple inputs:

```python
class TestVariableResolver:
    """Tests for VariableResolver."""

    @pytest.mark.parametrize("template,variables,expected", [
        # Simple substitution
        ("Hello {name}", {"name": "Alice"}, "Hello Alice"),
        # Multiple variables
        ("{greeting} {name}", {"greeting": "Hi", "name": "Bob"}, "Hi Bob"),
        # Missing variable unchanged
        ("Hello {name}", {}, "Hello {name}"),
        # Nested braces
        ("Code: {{literal}}", {}, "Code: {literal}"),
        # Empty template
        ("", {"name": "Alice"}, ""),
        # No variables in template
        ("Hello world", {"name": "Alice"}, "Hello world"),
    ])
    def test_resolve_template(self, resolver, template, variables, expected):
        """Variable resolution handles various cases correctly."""
        result = resolver.resolve(template, variables)
        assert result == expected

    @pytest.mark.parametrize("invalid_input", [
        None,
        123,
        ["list"],
        {"dict": "value"},
    ])
    def test_resolve_rejects_invalid_template_type(self, resolver, invalid_input):
        """Only string templates are accepted."""
        with pytest.raises(TypeError):
            resolver.resolve(invalid_input, {})
```

---

## Error Testing

### Testing Expected Exceptions

```python
async def test_get_rule_with_invalid_uuid_raises_validation_error(self, store):
    """Invalid UUID format raises ValidationError."""
    with pytest.raises(ValidationError):
        await store.get_rule("not-a-uuid", uuid4())


async def test_save_rule_with_conflict_raises_conflict_error(self, store):
    """Saving rule with existing ID raises ConflictError."""
    rule = RuleFactory.create()
    await store.save_rule(rule)

    # Try to save different rule with same ID
    duplicate = RuleFactory.create(id=rule.id)
    with pytest.raises(ConflictError) as exc_info:
        await store.save_rule(duplicate)

    assert exc_info.value.resource_id == rule.id
```

### Testing Error Messages

```python
async def test_provider_error_includes_details(self, provider, mocker):
    """Provider errors include helpful debugging info."""
    mocker.patch.object(
        provider._client,
        "complete",
        side_effect=APIError("Rate limited", status_code=429),
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.generate("Hello")

    error = exc_info.value
    assert "rate" in error.message.lower()
    assert error.provider_name == "anthropic"
    assert error.is_retryable is True
```

---

## Test Markers

Use markers to categorize tests:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests requiring external services",
    "e2e: marks end-to-end tests",
    "performance: marks performance benchmark tests",
]
```

Usage:

```python
@pytest.mark.slow
async def test_large_batch_processing(self, store):
    """Processing 10000 rules completes in reasonable time."""
    rules = RuleFactory.create_batch(10000)
    # ...


@pytest.mark.skip(reason="Pending implementation of feature X")
async def test_future_feature(self):
    pass


@pytest.mark.xfail(reason="Known bug #123")
async def test_known_failing_case(self):
    pass
```

Running specific markers:

```bash
# Run only fast tests
pytest -m "not slow"

# Run only unit tests (exclude integration)
pytest tests/unit/

# Run specific test class
pytest tests/unit/alignment/retrieval/test_rule_retriever.py::TestRetrieve
```

---

## Coverage

### Viewing Coverage

```bash
# Run with coverage
pytest tests/unit/ --cov=soldier --cov-report=term-missing

# Generate HTML report
pytest tests/unit/ --cov=soldier --cov-report=html
open htmlcov/index.html
```

### What to Cover

| Must Cover | May Skip |
|------------|----------|
| Public methods | Private helpers (test via public) |
| Error paths | `if TYPE_CHECKING` blocks |
| Edge cases | Abstract method definitions |
| Business logic | Simple property getters |

### Coverage Exclusions

```python
# Exclude from coverage with pragma
def __repr__(self) -> str:  # pragma: no cover
    return f"Rule({self.id})"


# Or for type checking blocks
if TYPE_CHECKING:  # Automatically excluded
    from soldier.types import SomeType
```

---

## Common Patterns

### Testing Async Context Managers

```python
async def test_transaction_rollback_on_error(self, store):
    """Failed operations rollback the transaction."""
    async with store.transaction() as tx:
        await tx.save_rule(sample_rule)
        raise ValueError("Simulated error")

    # Rule should not be persisted
    result = await store.get_rule(sample_rule.tenant_id, sample_rule.id)
    assert result is None
```

### Testing Event Emission

```python
async def test_rule_matched_emits_event(self, engine, event_collector):
    """Matching a rule emits a rule_matched event."""
    await engine.process_turn(message="return my order", session=session)

    events = event_collector.get_events("rule_matched")
    assert len(events) == 1
    assert events[0].rule_id == expected_rule.id
```

### Testing Logging

```python
async def test_logs_warning_on_fallback(self, retriever, caplog):
    """Warning is logged when falling back to secondary provider."""
    with caplog.at_level(logging.WARNING):
        await retriever.retrieve(context)

    assert "fallback" in caplog.text.lower()
    assert "primary provider failed" in caplog.text.lower()
```

---

## See Also

- [Testing Strategy](./testing-strategy.md) - Overall testing approach
- [Folder Structure](../architecture/folder-structure.md) - Test directory organization
- [Domain Model](../design/domain-model.md) - Models to test
- [Storage ADR](../design/decisions/001-storage-choice.md) - Store interfaces
