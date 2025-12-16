# Parallel Work Tasks

**Generated**: 2025-12-16
**Purpose**: Tasks that can be executed in parallel by subagents

This document lists remaining implementation tasks from the IMPLEMENTATION_WAVES.md that can be worked on in parallel.

---

## Current Status

**Test Suite Status** (as of 2025-12-16):
- Unit tests: 1667 passed, 10 skipped
- Integration tests: 14 Redis-related failures (need Redis running)
- Coverage: 59.1% (target: 85%)

---

## Parallelizable Tasks

### Task 1: Regeneration Retry Loop (5F)
**Priority**: Medium
**Estimated Effort**: 2-4 hours
**Location**: `ruche/brains/focal/pipeline.py`

**Problem**: When enforcement validation fails, the system goes directly to fallback template. There's no retry logic to regenerate with feedback about the violation.

**Current Flow** (lines 1860-1915):
```python
async def _enforce_response(...):
    result = await self._enforcement_validator.validate(...)
    # If failed, goes directly to fallback - NO RETRY
    if not result.passed and self._fallback_handler:
        fallback_template = self._fallback_handler.select_fallback(templates or [])
        result = self._fallback_handler.apply_fallback(fallback_template, result)
    return result
```

**Target Flow**:
1. If validation fails, attempt regeneration with violation feedback
2. Retry up to N times (configurable, default 2)
3. Only fall back to template if all regeneration attempts fail
4. Track `regeneration_attempts` count in result

**Implementation Notes**:
- Add retry loop before fallback
- Include violation details in regeneration prompt
- Add config option: `enforcement.max_regeneration_attempts`
- Update `EnforcementResult.regeneration_attempts` counter

---

### Task 2: ConfigResolver Layer Getters (2J)
**Priority**: Medium
**Estimated Effort**: 3-4 hours
**Location**: `ruche/runtime/config/resolver.py`

**Problem**: The framework is done but `_get_tenant_config`, `_get_channel_config`, `_get_scenario_config`, and `_get_step_config` return `None`.

**Current State**:
- `_get_agent_config()` works (extracts from agent settings)
- Other layer getters are stubs returning None

**Required Implementation**:

1. **`_get_tenant_config(tenant_id)`**:
   - Requires new `tenant_configs` table or JSONB column
   - For now, can read from TOML config fallback

2. **`_get_channel_config(tenant_id, agent_id, channel)`**:
   - Read from `channel_bindings` table if config_overrides column exists
   - Or use channel-specific TOML sections

3. **`_get_scenario_config(tenant_id, scenario_id)`**:
   - Extract from scenario's `config_overrides` field if it exists
   - Or return None until schema supports it

4. **`_get_step_config(tenant_id, scenario_id, step_id)`**:
   - Extract from step's config if it exists in `ScenarioStep` model

**Notes**: Document which config layers are "future" vs "now" in docstrings

---

### Task 3: InterlocutorDataStore Consolidation (1E/1K)
**Priority**: Medium
**Estimated Effort**: 4-6 hours
**Locations**:
- `ruche/domain/interlocutor/models.py` (KEEP)
- `ruche/interlocutor_data/models.py` (CONSOLIDATE)
- `ruche/interlocutor_data/store.py` (CONSOLIDATE)

**Problem**: Duplicate `InterlocutorDataField` and `InterlocutorDataStore` definitions exist.

**Steps**:
1. Compare both implementations to ensure feature parity
2. Keep `ruche/domain/interlocutor/models.py` as canonical
3. Update all imports throughout codebase:
   - Use `mgrep` to find all usages
   - Update imports in tests and source
4. Deprecate or remove `ruche/interlocutor_data/models.py` duplicates
5. Update `field_resolver.py` to use correct types

**Files to Update**:
- `ruche/brains/focal/phases/loaders/interlocutor_data_loader.py`
- `ruche/brains/focal/migration/field_resolver.py`
- `tests/unit/brains/focal/migration/test_field_resolver.py`
- Any file importing from `ruche.interlocutor_data.models`

---

### Task 4: Fix Field Resolver Tests
**Priority**: Medium
**Estimated Effort**: 2-3 hours
**Location**: `tests/unit/brains/focal/migration/test_field_resolver.py`

**Problem**: Tests are skipped because:
1. Session model doesn't have `interlocutor_id` attribute (uses `customer_profile_id`)
2. MockProfileStore and MockLLMExecutor need API updates

**Steps**:
1. Update test fixtures to not set `sample_session.interlocutor_id`
2. Update MockProfileStore to match `InterlocutorDataStore` interface
3. Update tests to work with current Session model
4. Remove skip markers after fixes
5. Run tests to verify

---

### Task 5: Test Coverage Improvement (5I)
**Priority**: High
**Estimated Effort**: 8-16 hours (can be parallelized further)
**Current**: 59.1%
**Target**: 85%

**Priority Areas** (by uncovered lines):
1. `ruche/vector/` - ~80% uncovered (embedding_manager, pgvector, qdrant)
2. `ruche/infrastructure/stores/` - many backends with stubs
3. `ruche/brains/focal/phases/` - several phases with gaps
4. `ruche/runtime/` - acf, channels, toolbox need more coverage

**Strategy**:
- Focus on high-impact modules first
- Add contract tests for store interfaces
- Add unit tests for all phase classes

**Sub-tasks (can parallelize)**:
- Task 5A: Vector module tests
- Task 5B: Store contract tests
- Task 5C: FOCAL phase tests
- Task 5D: Runtime module tests

---

### Task 6: Update IMPLEMENTATION_WAVES.md Tracking
**Priority**: Low
**Estimated Effort**: 30 minutes
**Location**: `docs/implementation/IMPLEMENTATION_WAVES.md`

**Updates Needed**:
1. Mark 2G (Template model) as ✅ COMPLETE (has `render()` and `variables_used`)
2. Update test failure counts
3. Update coverage percentage
4. Add notes about skipped tests

---

## Dependencies Between Tasks

```
Task 3 (InterlocutorDataStore) ──┬──> Task 4 (Field Resolver Tests)
                                 │
                                 └──> Task 5 (Coverage)

Task 1 (Regeneration Loop)  ──────> Independent

Task 2 (ConfigResolver)     ──────> Independent

Task 6 (Update Tracking)    ──────> Can do anytime
```

---

## Execution Notes

1. **Task 1 and Task 2** are independent and can run in parallel
2. **Task 3** should complete before **Task 4** (since tests depend on model consolidation)
3. **Task 5** can run partially in parallel with subsets (5A, 5B, 5C, 5D)
4. **Task 6** should run last to capture all updates

---

## Agent Assignment Guidelines

When assigning to subagents:

1. **For Task 1 (Regeneration Loop)**:
   - Read `ruche/brains/focal/pipeline.py` lines 1860-1915
   - Understand enforcement flow
   - Implement retry loop with configurable attempts

2. **For Task 2 (ConfigResolver)**:
   - Read `ruche/runtime/config/resolver.py`
   - Check database schema for config storage options
   - Implement or document each layer getter

3. **For Task 3 (Model Consolidation)**:
   - Use `mgrep` to find all usages
   - Be careful with import changes
   - Run tests after each major change

4. **For Task 4 (Fix Tests)**:
   - Depends on Task 3 completion
   - Update mocks to match current interfaces
   - Remove skip markers after verification

5. **For Task 5 (Coverage)**:
   - Can split by module
   - Focus on critical paths first
   - Use existing test patterns as reference

---

## Verification Commands

```bash
# Run unit tests
uv run pytest tests/unit/ -q

# Run with coverage
uv run pytest --cov=ruche --cov-report=term-missing -q --tb=no

# Run specific test file
uv run pytest tests/unit/brains/focal/migration/test_field_resolver.py -v

# Check test count
uv run pytest --collect-only -q 2>&1 | wc -l
```
