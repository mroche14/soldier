# Work Packages

> **Status**: CONFIRMED - User decisions applied
> **Purpose**: Define independent work units for parallel execution
> **Last Updated**: 2025-12-15

## User Decisions Applied

| Question | Decision | Impact |
|----------|----------|--------|
| Q1 | Put both files in `brains/focal/` for user review | WP-001: Keep both, move alignment/ to brains/focal/ |
| Q2 | (A) Full restructure | WP-004: Execute all restructuring tasks |
| Q3 | Pending (details provided) | — |
| Q4 | (A) Rename customer → interlocutor NOW | WP-005: Execute terminology rename |
| Q5 | (A) Move IMPLEMENTATION_PLAN.md to docs/focal_brain/ | WP-007: Move file, create new subagent plan |

---

## Work Package Summary

| ID | Name | Priority | Effort | Dependencies | Status |
|----|------|----------|--------|--------------|--------|
| WP-000 | Planning & Questions | P0 | 1 day | — | 🟡 IN PROGRESS |
| WP-001 | FOCAL Consolidation | P1 | 2-3 days | WP-000 | ⚪ PENDING |
| WP-002 | ACF Verification & Completion | P1 | 3-5 days | WP-000 | ⚪ PENDING |
| WP-003 | Enforcement Wiring | P1 | 1-2 days | WP-001 | ⚪ PENDING |
| WP-004 | Folder Restructuring | P2 | 3-5 days | WP-001, WP-002 | ⚪ PENDING |
| WP-005 | Terminology Standardization | P2 | 2-3 days | WP-004 | ⚪ PENDING |
| WP-006 | Provider Deduplication | P2 | 1 day | WP-004 | ⚪ PENDING |
| WP-007 | Documentation Alignment | P3 | 2 days | WP-001 to WP-006 | ⚪ PENDING |
| WP-008 | Test Coverage Expansion | P3 | 2-3 days | WP-001 to WP-006 | ⚪ PENDING |

---

## Dependency Graph

```
WP-000 (Planning)
    │
    ├──► WP-001 (FOCAL Consolidation)
    │        │
    │        ├──► WP-003 (Enforcement)
    │        │
    │        └──► WP-004 (Folder Restructure) ◄── WP-002
    │                    │
    │                    ├──► WP-005 (Terminology)
    │                    │
    │                    └──► WP-006 (Providers)
    │
    └──► WP-002 (ACF Verification)

All ──► WP-007 (Docs) + WP-008 (Tests)
```

---

## WP-000: Planning & Questions Resolution

**Priority**: P0 (Blocking)
**Effort**: 1 day
**Dependencies**: None

### Scope

```yaml
owns:
  - docs/implementation/**
reads:
  - "**/*"  # Full codebase read access
forbidden:
  - ruche/**  # No code changes yet
```

### Tasks

- [x] Create implementation planning folder structure
- [x] Complete gap analysis
- [x] Document all ambiguities as questions
- [x] Create subagent protocol
- [x] Create work packages (this document)
- [ ] Get user answers to blocking questions
- [ ] Finalize work package specifications
- [ ] Create tracking files

### Success Criteria

- All blocking questions answered
- All WP specifications approved
- Tracking infrastructure ready

---

## WP-001: FOCAL Consolidation

**Priority**: P1 (Critical)
**Effort**: 2-3 days
**Dependencies**: WP-000
**Blocks**: WP-003, WP-004

### Problem

Two large files contain FOCAL brain logic:
- `ruche/brains/focal/pipeline.py` (2097 lines)
- `ruche/alignment/engine.py` (2078 lines)

### User Decision (Q1)

**"Put them in Brain/focal for now I will review them."**

This means: Move BOTH files to `brains/focal/`, preserve both for user review, don't delete either until user confirms which to keep.

### Scope

```yaml
owns:
  - ruche/brains/focal/**
  - ruche/alignment/**
  - tests/unit/alignment/**
  - tests/unit/brains/**
reads:
  - ruche/domain/**
  - ruche/config/**
  - ruche/infrastructure/**
forbidden:
  - ruche/runtime/**
  - ruche/api/**
```

### Tasks

1. **Move alignment/engine.py → brains/focal/**
   - Rename to `brains/focal/engine.py` (keep `pipeline.py` as-is)
   - User will review both and decide which to keep
   - Document differences between them

2. **Restructure alignment/ → brains/focal/**
   - Move `alignment/context/` → `brains/focal/phases/`
   - Move `alignment/filtering/` → `brains/focal/phases/`
   - Move `alignment/generation/` → `brains/focal/phases/`
   - Move `alignment/execution/` → `brains/focal/phases/`
   - Move `alignment/enforcement/` → `brains/focal/phases/`
   - Move `alignment/retrieval/` → `brains/focal/retrieval/`
   - Move `alignment/migration/` → `brains/focal/migration/`
   - Move `alignment/models/` → `brains/focal/models/`
   - Move `alignment/stores/` → `brains/focal/stores/` (pending Q3 confirmation)

3. **Update all imports**
   - Search and replace import paths
   - Verify no broken imports

4. **Delete empty alignment/ folder**
   - After all content moved
   - Verify no remaining references

### Success Criteria

- All FOCAL code consolidated in `brains/focal/`
- Both `pipeline.py` and `engine.py` preserved for user review
- All existing tests pass
- No `ruche.alignment` imports in codebase

---

## WP-002: ACF Verification & Completion

**Priority**: P1 (Critical)
**Effort**: 3-5 days
**Dependencies**: WP-000
**Blocks**: WP-004

### Problem

Phase 6.5 in IMPLEMENTATION_PLAN is mostly unchecked, but `ruche/runtime/acf/` has files.

### Scope

```yaml
owns:
  - ruche/runtime/acf/**
  - ruche/runtime/agent/**
  - ruche/jobs/workflows/**
  - tests/unit/runtime/**
  - tests/integration/runtime/**
reads:
  - ruche/domain/**
  - ruche/config/**
  - ruche/infrastructure/**
  - docs/acf/**
forbidden:
  - ruche/brains/**
  - ruche/api/**
```

### Tasks

1. **Audit existing ACF code**
   - Read all 8 files in `runtime/acf/`
   - Compare against `docs/acf/architecture/ACF_SPEC.md`
   - Document what exists vs. what's missing

2. **Verify LogicalTurn model**
   - Check against `docs/acf/architecture/topics/01-logical-turn.md`
   - Add missing fields if needed

3. **Verify session mutex**
   - Check Hatchet integration
   - Verify `{tenant}:{agent}:{interlocutor}:{channel}` key format

4. **Verify/implement accumulation**
   - Check `docs/acf/architecture/topics/03-adaptive-accumulation.md`
   - Implement if missing

5. **Verify/implement supersede**
   - Check supersede signals and coordination
   - Implement if missing

6. **Wire Hatchet LogicalTurnWorkflow**
   - Check `ruche/jobs/workflows/`
   - Implement if missing

7. **Add comprehensive tests**
   - Unit tests for each ACF component
   - Integration test for workflow

### Success Criteria

- All Phase 6.5 checkboxes can be marked complete
- ACF tests coverage > 80%
- Hatchet workflow runs successfully

---

## WP-003: Enforcement Wiring

**Priority**: P1 (Critical)
**Effort**: 1-2 days
**Dependencies**: WP-001
**Blocks**: None

### Problem

Per `phase-10-enforcement-checklist.md`:
- `DeterministicEnforcer` exists
- `SubjectiveEnforcer` exists
- Two-lane dispatch NOT WIRED

### Scope

```yaml
owns:
  - ruche/brains/focal/phases/enforcement/**  # After WP-001 moves
  - tests/unit/brains/focal/enforcement/**
reads:
  - ruche/domain/**
  - ruche/config/**
forbidden:
  - ruche/runtime/**
  - ruche/api/**
```

### Tasks

1. **Wire two-lane dispatch in validator**
   - Modify `EnforcementValidator.validate()`
   - Route rules WITH `enforcement_expression` to DeterministicEnforcer
   - Route rules WITHOUT to SubjectiveEnforcer

2. **Implement GLOBAL always-enforce**
   - Add `get_global_hard_constraints()` to ConfigStore
   - Call in validator for every turn

3. **Add variable extraction**
   - Integrate `VariableExtractor` with session/profile data
   - Pass to DeterministicEnforcer

4. **Update configuration**
   - Add `[brain.enforcement]` TOML section
   - Wire config to validator

5. **Add tests**
   - Test deterministic lane
   - Test LLM-as-Judge lane
   - Test GLOBAL always-enforce

### Success Criteria

- `enforcement_expression` rules use deterministic evaluation
- Subjective rules use LLM judgment
- GLOBAL hard constraints checked on every response

---

## WP-004: Folder Restructuring

**Priority**: P2 (Important)
**Effort**: 3-5 days
**Dependencies**: WP-001, WP-002
**Blocks**: WP-005, WP-006

### Problem

Current folder structure doesn't match documented target.

### Scope

```yaml
owns:
  - ruche/**
  - tests/**
reads:
  - docs/architecture/folder-structure.md
forbidden:
  - docs/**  # Except updating if needed
```

### Tasks

Depends on Q2 answer. If full restructure:

1. **Move domain models**
   - `customer_data/models.py` → `domain/interlocutor/`
   - `memory/models/` → `domain/memory/`
   - Consolidate rule/scenario models

2. **Move stores under infrastructure/**
   - `audit/` → `infrastructure/stores/audit/`
   - `conversation/` → `infrastructure/stores/session/`
   - `vector/` → `infrastructure/stores/vector/`

3. **Move supporting modules**
   - `db/` → `infrastructure/db/`
   - `jobs/` → `infrastructure/jobs/`

4. **Update all imports**
   - Automated search/replace
   - Manual verification

5. **Update documentation**
   - `folder-structure.md` if structure differs
   - CLAUDE.md import examples

### Success Criteria

- Folder structure matches documentation
- All tests pass
- No broken imports

---

## WP-005: Terminology Standardization

**Priority**: P2 (Important)
**Effort**: 2-3 days
**Dependencies**: WP-004
**Blocks**: None

### Problem

Mixed old/new terminology in code.

### User Decision (Q4)

**"Now (A)"** - Execute full rename immediately.

### Scope

```yaml
owns:
  - ruche/**
  - tests/**
reads:
  - docs/ARCHITECTURE_READINESS_REPORT_V6.md
forbidden:
  - docs/**
```

### Tasks

1. **Rename customer → interlocutor** ✅ CONFIRMED
   - `customer_data/` → `interlocutor_data/`
   - `CustomerDataStore` → `InterlocutorDataStore`
   - `CustomerDataField` → `InterlocutorDataField`
   - `customer_id` → `interlocutor_id` in all code
   - Update all references (~50+ files)

2. **Standardize method names**
   - `brain.run()` → `brain.think()` (if still present)
   - Verify `run_agent` in Hatchet steps

3. **Standardize session key format**
   - Verify `interlocutor_id` not `customer_id`

4. **Update tests**
   - Rename test files/classes
   - `test_customer_*` → `test_interlocutor_*`

### Success Criteria

- No `customer` terminology in code (except where semantically correct)
- All class names use `Interlocutor*`
- Consistent with V6 report definitions

---

## WP-006: Provider Deduplication

**Priority**: P2 (Important)
**Effort**: 1 day
**Dependencies**: WP-004
**Blocks**: None

### Problem

Providers exist in two locations:
- `ruche/providers/` (18 files)
- `ruche/infrastructure/providers/` (16 files)

### Scope

```yaml
owns:
  - ruche/providers/**
  - ruche/infrastructure/providers/**
reads:
  - All files importing from providers
forbidden:
  - ruche/brains/**
  - ruche/runtime/**
```

### Tasks

1. **Identify canonical location**
   - `infrastructure/providers/` is target per docs

2. **Convert root providers to re-exports**
   - Keep `ruche/providers/__init__.py`
   - Re-export from `infrastructure/providers/`

3. **Or merge if unique code exists**
   - Migrate any unique implementations
   - Update imports

4. **Update documentation**
   - CLAUDE.md import examples

### Success Criteria

- Single source of truth for providers
- Backward-compatible imports from `ruche/providers/`

---

## WP-007: Documentation Alignment

**Priority**: P3 (Polish)
**Effort**: 2 days
**Dependencies**: WP-001 to WP-006
**Blocks**: None

### User Decision (Q5)

**"A then create new implementation plan"** - Move IMPLEMENTATION_PLAN.md to docs/focal_brain/, then create new subagent implementation plan.

### Scope

```yaml
owns:
  - docs/**
  - CLAUDE.md
  - IMPLEMENTATION_PLAN.md
reads:
  - ruche/**
forbidden:
  - ruche/**
  - tests/**
```

### Tasks

1. **Move IMPLEMENTATION_PLAN.md → docs/focal_brain/** ✅ CONFIRMED
   - Move file to `docs/focal_brain/IMPLEMENTATION_PLAN.md`
   - Fix `focal/` → `ruche/` paths within the file
   - Update Phase 6.5 checkboxes per WP-002
   - Update all internal doc path references

2. **Create new master implementation plan**
   - Create `docs/implementation/master-plan.md`
   - Covers all work packages for subagents
   - Links to individual WP tracking files
   - Defines execution waves

3. **Update folder-structure.md**
   - Reflect actual post-refactor structure

4. **Update CLAUDE.md**
   - Import path examples
   - New folder locations
   - Reference new implementation plan

5. **Archive old docs**
   - Move superseded docs to `docs/archive/`

6. **Update doc_skeleton.md**
   - Reflect current doc state

### Success Criteria

- IMPLEMENTATION_PLAN.md moved to docs/focal_brain/
- New master-plan.md created for subagents
- All documentation matches codebase
- No stale path references

---

## WP-008: Test Coverage Expansion

**Priority**: P3 (Polish)
**Effort**: 2-3 days
**Dependencies**: WP-001 to WP-006
**Blocks**: None

### Scope

```yaml
owns:
  - tests/**
reads:
  - ruche/**
  - docs/development/testing-strategy.md
forbidden:
  - ruche/**
```

### Tasks

1. **Add missing ACF tests** (from WP-002)
   - Comprehensive unit tests
   - Integration tests

2. **Add enforcement tests** (from WP-003)
   - Two-lane tests
   - GLOBAL constraint tests

3. **Add E2E tests**
   - Full chat flow
   - Scenario navigation
   - Per `testing-strategy.md`

4. **Verify coverage targets**
   - 80% overall
   - 85% for brains/focal/

### Success Criteria

- All testing gaps from gap-analysis.md closed
- Coverage meets targets

---

## Parallel Execution Plan

### Wave 1 (Sequential - Must Complete First)
- WP-000: Planning

### Wave 2 (Parallel)
- WP-001: FOCAL Consolidation
- WP-002: ACF Verification

### Wave 3 (Sequential after Wave 2)
- WP-003: Enforcement Wiring (needs WP-001)
- WP-004: Folder Restructuring (needs WP-001 + WP-002)

### Wave 4 (Parallel after Wave 3)
- WP-005: Terminology
- WP-006: Providers

### Wave 5 (Parallel - Final)
- WP-007: Documentation
- WP-008: Tests

---

## Effort Summary

| Wave | Work Packages | Total Effort | Calendar Days |
|------|---------------|--------------|---------------|
| 1 | WP-000 | 1 day | 1 day |
| 2 | WP-001 + WP-002 | 5-8 days | 3-4 days (parallel) |
| 3 | WP-003 + WP-004 | 4-7 days | 4-5 days (sequential) |
| 4 | WP-005 + WP-006 | 3-4 days | 2-3 days (parallel) |
| 5 | WP-007 + WP-008 | 4-5 days | 2-3 days (parallel) |

**Total**: ~12-16 calendar days with parallel execution

---

*This document will be finalized after user answers questions.md*
