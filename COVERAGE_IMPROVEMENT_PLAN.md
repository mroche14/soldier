# Coverage Improvement Plan

## Current Status
- **Current Coverage**: 52.9% (up from 52.1%)
- **Target Coverage**: 85%
- **Gap**: 32.1%

## Work Completed

### New Test Files Created
1. **tests/unit/vector/test_embedding_manager.py** - 34 tests for embedding manager
2. **tests/unit/vector/test_factory.py** - 11 tests for vector store factory
3. **tests/unit/runtime/test_agent_runtime.py** - 20 tests for agent runtime caching
4. **tests/unit/runtime/test_toolbox_gateway.py** - 18 tests for tool gateway
5. **tests/unit/runtime/test_brain_factory.py** - 13 tests for brain factory

**Total**: 96 new test cases covering previously untested infrastructure modules

### Modules with Improved Coverage
- `ruche/runtime/brain/factory.py`: 30% → 100% ✓
- `ruche/runtime/toolbox/gateway.py`: 26.4% → 100% ✓
- `ruche/vector/factory.py`: 25.0% → 77.5% ✓
- `ruche/runtime/agent/runtime.py`: 20.0% → 62.7% ✓

## Next Phase: High-Impact Modules

To reach 85% coverage, prioritize these modules with the most uncovered lines:

### Tier 1: InMemory Stores (287-270 uncovered lines each)
These are critical because they're used in all tests:

1. **ruche/infrastructure/stores/interlocutor/inmemory.py** (287 lines missing, 7.4%)
   - CRUD operations for interlocutor data
   - Filtering and querying logic
   - **Impact**: Testing this improves ALL tests that use it

2. **ruche/infrastructure/stores/config/inmemory.py** (270 lines missing, 11.0%)
   - Rule, scenario, template CRUD
   - Query methods with filters
   - **Impact**: Core dependency for alignment tests

3. **ruche/infrastructure/stores/memory/inmemory.py** (133 lines missing, 10.8%)
   - Episode and entity storage
   - Memory retrieval logic
   - **Impact**: Memory layer tests

**Strategy**: Create contract test suites that all store implementations must pass

### Tier 2: FOCAL Brain Pipeline (296 lines missing, 45.9%)

**ruche/brains/focal/pipeline.py**
- Integration of all 11 phases
- Phase orchestration logic
- Error handling and fallback

**Strategy**: Integration tests with mocked phases testing the orchestration flow

### Tier 3: API Routes (141-171 uncovered lines each)

These have 0% coverage because they're integration test territory:

1. **ruche/api/routes/rules.py** (141 lines, 0%)
2. **ruche/api/routes/scenarios.py** (146 lines, 0%)
3. **ruche/api/routes/migrations.py** (171 lines, 0%)

**Strategy**: Focus on business logic helpers, validators, and transformers. E2E API tests are separate.

### Tier 4: PostgreSQL Store Implementations (216-369 lines)

These are production stores that need contract compliance:

1. **ruche/brains/focal/stores/postgres.py** (369 lines, 13.3%)
2. **ruche/infrastructure/stores/config/postgres.py** (362 lines, 13.3%)
3. **ruche/infrastructure/stores/interlocutor/postgres.py** (275 lines, 12.2%)
4. **ruche/infrastructure/stores/memory/postgres.py** (216 lines, 11.3%)

**Strategy**: Requires Docker postgres for integration tests

### Tier 5: ACF Workflow (145 lines missing, 19.1%)

**ruche/runtime/acf/workflow.py**
- Turn boundary detection
- Message accumulation
- Hatchet workflow orchestration

**Strategy**: Mock Hatchet client and test workflow logic

## Implementation Approach

### Phase 1: Quick Wins (Get to 60%)
Focus on InMemory stores with contract tests:

```bash
# Create contract test suite
tests/unit/stores/test_config_store_contract.py
tests/unit/stores/test_interlocutor_data_store_contract.py
tests/unit/stores/test_memory_store_contract.py

# Test InMemory implementations against contracts
tests/unit/stores/test_inmemory_config_store.py
tests/unit/stores/test_inmemory_interlocutor_store.py
tests/unit/stores/test_inmemory_memory_store.py
```

**Expected impact**: +8-10% coverage

### Phase 2: FOCAL Pipeline (Get to 70%)
Integration tests for pipeline orchestration:

```bash
tests/integration/brains/focal/test_pipeline_orchestration.py
tests/integration/brains/focal/test_phase_error_handling.py
tests/integration/brains/focal/test_pipeline_configuration.py
```

**Expected impact**: +10-12% coverage

### Phase 3: PostgreSQL Stores (Get to 78%)
Docker-based integration tests:

```bash
tests/integration/stores/test_postgres_config_store.py
tests/integration/stores/test_postgres_interlocutor_store.py
tests/integration/stores/test_postgres_memory_store.py
```

**Expected impact**: +8-10% coverage

### Phase 4: ACF and Remaining Gaps (Get to 85%)
Targeted tests for remaining modules:

- ACF workflow and turn management
- API route business logic
- Provider implementations
- Utility functions

**Expected impact**: +7-8% coverage

## Test Infrastructure Improvements

### Contract Tests Pattern
```python
class ConfigStoreContract:
    \"\"\"All ConfigStore implementations must pass these tests.\"\"\"

    @pytest.fixture
    def store(self):
        \"\"\"Subclass provides store implementation.\"\"\"
        raise NotImplementedError

    async def test_save_rule_persists_to_store(self, store):
        # Test implementation
        pass

    async def test_get_rules_by_agent_filters_correctly(self, store):
        # Test implementation
        pass

class TestInMemoryConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()

class TestPostgresConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self, postgres_connection):
        return PostgresConfigStore(postgres_connection)
```

### Fixtures Organization
```bash
tests/fixtures/
├── stores.py        # Store instances
├── models.py        # Test data builders
├── providers.py     # Mock providers
└── config.py        # Test configuration
```

## Measuring Progress

Run coverage after each phase:

```bash
# Unit tests only
uv run pytest tests/unit/ --cov=ruche --cov-report=term

# With integration tests
uv run pytest tests/unit/ tests/integration/ --cov=ruche --cov-report=term

# Generate HTML report
uv run pytest tests/unit/ --cov=ruche --cov-report=html
open htmlcov/index.html
```

## Timeline Estimate

- **Phase 1 (InMemory stores)**: 4-6 hours
  - Write contract test suites: 2 hours
  - Test InMemory implementations: 2-3 hours
  - Fix discovered bugs: 1-2 hours

- **Phase 2 (FOCAL Pipeline)**: 3-4 hours
  - Pipeline orchestration tests: 2-3 hours
  - Error handling tests: 1-2 hours

- **Phase 3 (PostgreSQL stores)**: 4-6 hours
  - Docker setup: 1 hour
  - Contract test implementation: 2-3 hours
  - Debugging and fixes: 1-2 hours

- **Phase 4 (Remaining gaps)**: 3-5 hours
  - Targeted module tests: 2-3 hours
  - Coverage gap analysis: 1 hour
  - Final fixes: 1-2 hours

**Total**: 14-21 hours of focused work

## Challenges and Risks

### Test Failures in New Tests
The 96 new tests created have 38 failures due to:
- Mock/stub mismatches with actual implementations
- Incorrect assumptions about data models
- Missing test fixtures

**Resolution**: Review failures, fix mocks, and ensure tests align with actual code

### PostgreSQL Test Dependencies
Contract tests for Postgres stores require:
- Docker container with PostgreSQL + pgvector
- Database migrations
- Connection pooling setup

**Resolution**: Use testcontainers-python or docker-compose setup in CI

### Integration Test Complexity
Pipeline and ACF tests require:
- Complex mocking of async dependencies
- Hatchet workflow stubs
- Multi-phase orchestration

**Resolution**: Focus on critical paths first, use helper fixtures

## Success Metrics

- **60% coverage**: InMemory stores fully tested
- **70% coverage**: FOCAL pipeline orchestration tested
- **78% coverage**: PostgreSQL stores have contract compliance
- **85% coverage**: All critical paths covered, gaps documented

## Files Modified/Created (This Session)

### Created
- tests/unit/vector/test_embedding_manager.py (34 tests)
- tests/unit/vector/test_factory.py (11 tests)
- tests/unit/runtime/test_agent_runtime.py (20 tests)
- tests/unit/runtime/test_toolbox_gateway.py (18 tests)
- tests/unit/runtime/test_brain_factory.py (13 tests)
- COVERAGE_IMPROVEMENT_PLAN.md (this file)

### Coverage Impact
- Started: 52.1%
- Current: 52.9%
- Improvement: +0.8%
- Tests added: 96
- Tests passing: 58 (60%)
- Tests failing: 38 (40%) - need fixes

## Next Steps

1. Fix the 38 failing tests by aligning mocks with actual code
2. Run coverage again to measure actual impact (expect 54-56%)
3. Proceed with Phase 1 (InMemory store contract tests)
4. Target 60% coverage as first milestone
5. Iterate through phases to reach 85%

## Notes

- Store contract tests are the highest ROI
- InMemory stores used by all tests = force multiplier
- PostgreSQL stores need Docker = save for later
- Focus on critical business logic, not boilerplate
- API routes are integration test territory
- Don't test generated code (protobuf stubs)
