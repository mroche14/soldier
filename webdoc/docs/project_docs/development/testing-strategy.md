# Testing Strategy

This document defines Focal's overall testing approach, including the test pyramid, CI/CD pipeline, coverage requirements, and environment configurations.

---

## Test Pyramid

Focal follows a test pyramid strategy with three layers. Each layer has a specific purpose and different characteristics.

```
                    ┌───────────┐
                    │    E2E    │  Few, slow, high confidence
                    │   Tests   │  Full system validation
                    ├───────────┤
                    │           │
                    │Integration│  Medium count, medium speed
                    │   Tests   │  Component boundaries
                    │           │
                    ├───────────┤
                    │           │
                    │           │
                    │   Unit    │  Many, fast, focused
                    │   Tests   │  Single class/function
                    │           │
                    │           │
                    └───────────┘
```

### Layer Definitions

| Layer | Scope | Speed | Count | Dependencies |
|-------|-------|-------|-------|--------------|
| **Unit** | Single class/function | < 10ms each | ~80% of tests | In-memory only, mocks |
| **Integration** | Component boundaries | < 1s each | ~15% of tests | Real backends (containerized) |
| **E2E** | Full request flow | < 10s each | ~5% of tests | Full stack |

---

## Unit Tests

### Purpose

Verify that individual classes and functions work correctly in isolation.

### Characteristics

- **Fast**: Entire unit test suite runs in < 30 seconds
- **Isolated**: No external dependencies (databases, APIs, network)
- **Deterministic**: Same input always produces same output
- **Focused**: One test tests one behavior

### What to Unit Test

| Component Type | What to Test |
|----------------|--------------|
| **Domain Models** | Validation, computed properties, state transitions |
| **Store Interfaces** | All interface methods via in-memory implementation |
| **Provider Interfaces** | All interface methods via mock implementation |
| **Selection Strategies** | Score analysis, edge cases, boundary conditions |
| **Pipeline Steps** | Input/output transformation, error handling |
| **Utility Functions** | All public functions |

### What NOT to Unit Test

- Private methods (test through public interface)
- Simple data classes with no logic
- Framework code (FastAPI, Pydantic)
- Third-party library internals

### Configuration

Unit tests use `config/test.toml`:

```toml
[storage.config]
backend = "inmemory"

[storage.memory]
backend = "inmemory"

[storage.session]
backend = "inmemory"

[storage.audit]
backend = "inmemory"

[providers.llm.default]
provider = "mock"

[providers.embedding.default]
provider = "mock"
dimensions = 384

[providers.rerank.default]
provider = "mock"
```

See: [Unit Testing Guide](./unit-testing.md) for detailed patterns and examples.

---

## Integration Tests

### Purpose

Verify that components work correctly together and with real external systems.

### Characteristics

- **Realistic**: Uses actual database/cache backends
- **Containerized**: Dependencies run in Docker containers
- **Isolated per test**: Each test gets clean state
- **Slower**: Acceptable to take seconds per test

### What to Integration Test

| Component | Integration Points |
|-----------|-------------------|
| **PostgresConfigStore** | PostgreSQL with pgvector |
| **PostgresMemoryStore** | PostgreSQL with pgvector |
| **RedisSessionStore** | Redis |
| **Neo4jMemoryStore** | Neo4j |
| **AnthropicProvider** | Anthropic API (with recorded responses) |
| **OpenAIProvider** | OpenAI API (with recorded responses) |
| **API Routes** | FastAPI TestClient with real stores |

### Test Environment

Integration tests use Docker Compose to spin up dependencies:

```yaml
# docker-compose.test.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: focal_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/testpassword
    ports:
      - "7475:7474"
      - "7688:7687"
```

### Database Isolation Strategies

Each integration test must start with clean state:

```python
# Option 1: Transaction rollback (fastest)
@pytest.fixture
async def db_session(postgres_engine):
    async with postgres_engine.begin() as conn:
        yield conn
        await conn.rollback()

# Option 2: Truncate tables (for tests that need commits)
@pytest.fixture
async def clean_db(postgres_engine):
    yield postgres_engine
    async with postgres_engine.begin() as conn:
        await conn.execute(text("TRUNCATE rules, scenarios, templates CASCADE"))

# Option 3: Separate database per test (slowest, most isolated)
@pytest.fixture
async def isolated_db(postgres_engine):
    db_name = f"test_{uuid4().hex[:8]}"
    # Create database, yield, drop database
```

### API Response Recording

For external API integration tests, use response recording to avoid hitting real APIs in CI:

```python
# tests/integration/providers/test_anthropic.py
import pytest
from pytest_recording import use_cassette

@use_cassette("anthropic_generate_simple.yaml")
async def test_anthropic_generate():
    provider = AnthropicProvider(api_key="test-key")
    response = await provider.generate("Hello")
    assert response.text
    assert response.usage.input_tokens > 0
```

Cassettes are stored in `tests/integration/cassettes/` and committed to git.

---

## End-to-End Tests

### Purpose

Verify that the entire system works correctly from API request to response.

### Characteristics

- **Full stack**: All components running together
- **User perspective**: Tests what users actually experience
- **Scenario-based**: Tests complete conversation flows
- **Slow**: Minutes per test acceptable

### What to E2E Test

| Scenario | Description |
|----------|-------------|
| **Simple chat** | Message in, response out |
| **Rule matching** | Message triggers correct rule |
| **Scenario flow** | Multi-turn conversation through scenario steps |
| **Scenario migration** | User mid-scenario when scenario updates |
| **Memory retrieval** | Agent recalls information from previous session |
| **Error recovery** | System degrades gracefully on provider failure |
| **Multi-tenant isolation** | Tenant A cannot see Tenant B's data |

### E2E Test Structure

```python
# tests/e2e/test_scenario_flow.py

@pytest.mark.e2e
async def test_complete_returns_scenario(e2e_client, seeded_agent):
    """
    Test: User completes a full returns scenario.

    Flow:
    1. User: "I want to return my order"
    2. Agent: Asks for order number (enters returns scenario)
    3. User: "Order 12345"
    4. Agent: Confirms return initiated (completes scenario)
    """
    # Turn 1: Entry
    response = await e2e_client.chat(
        agent_id=seeded_agent.id,
        message="I want to return my order",
    )
    assert "order number" in response.text.lower()
    assert response.scenario_id == seeded_agent.returns_scenario_id
    assert response.step_id == "ask_order_number"

    # Turn 2: Provide info
    response = await e2e_client.chat(
        agent_id=seeded_agent.id,
        session_id=response.session_id,
        message="Order 12345",
    )
    assert "return" in response.text.lower()
    assert "initiated" in response.text.lower() or "processed" in response.text.lower()
    assert response.scenario_completed is True
```

### E2E Environment

E2E tests run against a fully deployed stack (local or staging):

```bash
# Start full stack
docker-compose -f docker-compose.yml up -d

# Run E2E tests
pytest tests/e2e/ --e2e-base-url=http://localhost:8000

# Or against staging
pytest tests/e2e/ --e2e-base-url=https://staging.focal.example.com
```

---

## Coverage Requirements

### Minimum Coverage Targets

| Module | Line Coverage | Branch Coverage |
|--------|---------------|-----------------|
| `focal/alignment/` | 85% | 80% |
| `focal/memory/` | 85% | 80% |
| `focal/conversation/` | 80% | 75% |
| `focal/audit/` | 80% | 75% |
| `focal/providers/` | 80% | 75% |
| `focal/config/` | 90% | 85% |
| `focal/api/` | 80% | 75% |
| **Overall** | **85%** | **80%** |

### Coverage Enforcement

Coverage is enforced in CI:

```toml
# pyproject.toml
[tool.coverage.run]
source = ["focal"]
branch = true
omit = [
    "focal/__main__.py",
    "focal/api/grpc/protos/*",
]

[tool.coverage.report]
fail_under = 85
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

### Coverage Reports

```bash
# Generate coverage report
pytest --cov=focal --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

---

## CI/CD Pipeline

### Pipeline Stages

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Lint     │───▶│    Unit     │───▶│ Integration │───▶│    E2E      │
│   & Type    │    │   Tests     │    │    Tests    │    │   Tests     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     < 1min             < 1min            < 5min            < 10min
```

### What Runs When

| Trigger | Lint | Unit | Integration | E2E | Deploy |
|---------|------|------|-------------|-----|--------|
| PR opened | Yes | Yes | Yes | No | No |
| PR updated | Yes | Yes | Yes | No | No |
| Merge to main | Yes | Yes | Yes | Yes | Staging |
| Release tag | Yes | Yes | Yes | Yes | Production |
| Nightly | Yes | Yes | Yes | Yes | No |

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check focal/ tests/
      - run: ruff format --check focal/ tests/
      - run: mypy focal/

  unit:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/ -v --cov=focal --cov-fail-under=85
      - uses: codecov/codecov-action@v4

  integration:
    runs-on: ubuntu-latest
    needs: unit
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: focal_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/focal_test
          REDIS_URL: redis://localhost:6379

  e2e:
    runs-on: ubuntu-latest
    needs: integration
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: docker-compose up -d
      - run: pip install -e ".[dev]"
      - run: pytest tests/e2e/ -v --e2e-base-url=http://localhost:8000
      - run: docker-compose down
```

---

## Performance Testing

### Latency Targets

From the architecture docs, these are the latency targets to validate:

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Context extraction | 100ms | 200ms | 500ms |
| Rule retrieval | 50ms | 100ms | 200ms |
| Reranking | 100ms | 200ms | 300ms |
| LLM filtering | 200ms | 400ms | 800ms |
| Response generation | 500ms | 1000ms | 2000ms |
| **Full turn (no tools)** | **1000ms** | **2000ms** | **3000ms** |

### Performance Test Structure

```python
# tests/performance/test_pipeline_latency.py
import pytest
from focal.testing.performance import measure_latency, LatencyReport

@pytest.mark.performance
async def test_context_extraction_latency(context_extractor, benchmark_messages):
    """Context extraction should complete within latency targets."""

    report = await measure_latency(
        func=context_extractor.extract,
        args_list=[(msg,) for msg in benchmark_messages],
        iterations=100,
    )

    assert report.p50 < 100, f"P50 {report.p50}ms exceeds 100ms target"
    assert report.p95 < 200, f"P95 {report.p95}ms exceeds 200ms target"
    assert report.p99 < 500, f"P99 {report.p99}ms exceeds 500ms target"


@pytest.mark.performance
async def test_full_turn_latency(alignment_engine, benchmark_conversations):
    """Full turn processing should complete within latency targets."""

    report = await measure_latency(
        func=alignment_engine.process_turn,
        args_list=benchmark_conversations,
        iterations=50,
    )

    assert report.p50 < 1000, f"P50 {report.p50}ms exceeds 1000ms target"
    assert report.p95 < 2000, f"P95 {report.p95}ms exceeds 2000ms target"
```

### Running Performance Tests

Performance tests are not run in regular CI due to variability. They run:

1. **Nightly**: Against staging environment
2. **Pre-release**: Before any production deployment
3. **On-demand**: When optimizing specific components

```bash
# Run performance tests locally
pytest tests/performance/ -v --benchmark-json=benchmark.json

# Compare with baseline
pytest tests/performance/ -v --benchmark-compare=baseline.json
```

---

## Contract Testing

### Purpose

Verify that implementations of abstract interfaces (ABCs) fulfill the contract.

### Store Contracts

Every `Store` implementation must pass the same contract tests:

```python
# tests/contracts/test_config_store_contract.py
import pytest
from abc import ABC
from focal.alignment.stores import ConfigStore

class ConfigStoreContract(ABC):
    """Contract tests that all ConfigStore implementations must pass."""

    @pytest.fixture
    def store(self) -> ConfigStore:
        """Subclasses must provide a store instance."""
        raise NotImplementedError

    async def test_save_and_get_rule(self, store, sample_rule):
        """Saved rules can be retrieved by ID."""
        await store.save_rule(sample_rule)
        retrieved = await store.get_rule(sample_rule.tenant_id, sample_rule.id)
        assert retrieved == sample_rule

    async def test_get_nonexistent_rule_returns_none(self, store, random_uuid):
        """Getting a non-existent rule returns None, not an error."""
        result = await store.get_rule(random_uuid, random_uuid)
        assert result is None

    async def test_rules_are_tenant_isolated(self, store, sample_rule, other_tenant_id):
        """Rules from one tenant are not visible to another."""
        await store.save_rule(sample_rule)
        result = await store.get_rule(other_tenant_id, sample_rule.id)
        assert result is None

    async def test_vector_search_returns_similar_rules(self, store, embedded_rules):
        """Vector search returns semantically similar rules."""
        results = await store.vector_search_rules(
            tenant_id=embedded_rules[0].tenant_id,
            agent_id=embedded_rules[0].agent_id,
            embedding=embedded_rules[0].condition_embedding,
            limit=5,
        )
        assert len(results) > 0
        assert results[0].id == embedded_rules[0].id  # Most similar is itself

    # ... more contract tests


# tests/unit/alignment/stores/test_inmemory_config.py
class TestInMemoryConfigStore(ConfigStoreContract):
    """InMemoryConfigStore must fulfill the ConfigStore contract."""

    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()


# tests/integration/stores/test_postgres_config.py
class TestPostgresConfigStore(ConfigStoreContract):
    """PostgresConfigStore must fulfill the ConfigStore contract."""

    @pytest.fixture
    async def store(self, postgres_connection):
        return PostgresConfigStore(postgres_connection)
```

### Provider Contracts

Same pattern for providers:

```python
# tests/contracts/test_llm_provider_contract.py
class LLMProviderContract(ABC):
    """Contract tests for LLM providers."""

    async def test_generate_returns_text(self, provider):
        """Generate returns non-empty text."""
        response = await provider.generate("Say hello")
        assert isinstance(response.text, str)
        assert len(response.text) > 0

    async def test_generate_respects_max_tokens(self, provider):
        """Generate respects max_tokens parameter."""
        response = await provider.generate(
            "Write a very long story",
            max_tokens=10,
        )
        assert response.usage.output_tokens <= 15  # Allow small buffer

    async def test_generate_structured_returns_model(self, provider):
        """Generate structured returns valid Pydantic model."""
        class Output(BaseModel):
            greeting: str

        result = await provider.generate_structured(
            "Say hello",
            schema=Output,
        )
        assert isinstance(result, Output)
        assert isinstance(result.greeting, str)
```

---

## Test Data Management

### Fixture Factories

Use factories to create test data with sensible defaults:

```python
# tests/factories.py
from focal.alignment.models import Rule, Scenario, ScenarioStep
from focal.conversation.models import Session
from uuid import uuid4

class RuleFactory:
    """Factory for creating test Rule instances."""

    @staticmethod
    def create(
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        condition_text: str = "default condition",
        action_text: str = "default action",
        **overrides,
    ) -> Rule:
        return Rule(
            id=uuid4(),
            tenant_id=tenant_id or uuid4(),
            agent_id=agent_id or uuid4(),
            condition_text=condition_text,
            action_text=action_text,
            priority=1,
            enabled=True,
            **overrides,
        )

    @staticmethod
    def create_batch(count: int, **shared_attrs) -> list[Rule]:
        return [RuleFactory.create(**shared_attrs) for _ in range(count)]
```

### Seed Data

For integration and E2E tests, use seed data that represents realistic scenarios:

```python
# tests/seed_data/returns_scenario.py
RETURNS_SCENARIO = {
    "name": "Product Returns",
    "description": "Handle product return requests",
    "steps": [
        {
            "id": "entry",
            "name": "Identify Intent",
            "transitions": [
                {"to": "ask_order", "condition": "user wants to return"}
            ],
        },
        {
            "id": "ask_order",
            "name": "Ask for Order Number",
            "prompt": "What is your order number?",
            "collects": ["order_number"],
            "transitions": [
                {"to": "confirm", "condition": "order_number provided"}
            ],
        },
        {
            "id": "confirm",
            "name": "Confirm Return",
            "prompt": "I've initiated the return for order {order_number}.",
            "is_terminal": True,
        },
    ],
}
```

---

## See Also

- [Unit Testing Guide](./unit-testing.md) - Detailed patterns for writing unit tests
- [Folder Structure](../architecture/folder-structure.md) - Test directory organization
- [Configuration TOML](../architecture/configuration-toml.md) - Test environment configuration
