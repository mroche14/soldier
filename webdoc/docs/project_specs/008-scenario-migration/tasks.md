# Tasks: Scenario Migration System

**Input**: Design documents from `/specs/008-scenario-migration/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the migration module structure and configuration

- [X] T001 Create migration module structure at `focal/alignment/migration/` with `__init__.py`
- [X] T002 [P] Create migration config models in `focal/config/models/migration.py`
- [X] T003 [P] Add migration config section to `focal/config/settings.py` and `config/default.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and store extensions that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Core Models

- [X] T004 [P] Create `MigrationPlanStatus` and `MigrationScenario` enums in `focal/alignment/migration/models.py`
- [X] T005 [P] Create `ScopeFilter` model in `focal/alignment/migration/models.py`
- [X] T006 [P] Create `AnchorMigrationPolicy` model in `focal/alignment/migration/models.py`
- [X] T007 [P] Create `InsertedNode`, `NewFork`, `ForkBranch`, `DeletedNode` models in `focal/alignment/migration/models.py`
- [X] T008 [P] Create `UpstreamChanges`, `DownstreamChanges`, `TransitionChange` models in `focal/alignment/migration/models.py`
- [X] T009 [P] Create `AnchorTransformation` model in `focal/alignment/migration/models.py`
- [X] T010 Create `TransformationMap` model in `focal/alignment/migration/models.py` (depends on T007-T009)
- [X] T011 [P] Create `MigrationSummary`, `MigrationWarning`, `FieldCollectionInfo` models in `focal/alignment/migration/models.py`
- [X] T012 Create `MigrationPlan` model in `focal/alignment/migration/models.py` (depends on T010, T011)

### Session Store Extensions

- [X] T013 Create `PendingMigration` model in `focal/conversation/models.py`
- [X] T014 Extend `StepVisit` model with `is_checkpoint`, `checkpoint_description`, `step_name` fields in `focal/conversation/models.py`
- [X] T015 Extend `Session` model with `pending_migration` and `scenario_checksum` fields in `focal/conversation/models.py`
- [X] T016 Add `find_sessions_by_step_hash()` method to `SessionStore` interface in `focal/conversation/stores/session_store.py`
- [X] T017 Implement `find_sessions_by_step_hash()` in `InMemorySessionStore` in `focal/conversation/stores/in_memory/session_store.py`

### Config Store Extensions

- [X] T018 Add migration plan methods to `ConfigStore` interface: `get_migration_plan()`, `save_migration_plan()`, `list_migration_plans()`, `get_migration_plan_for_versions()` in `focal/alignment/stores/config_store.py`
- [X] T019 Add scenario archiving methods to `ConfigStore` interface: `archive_scenario_version()`, `get_archived_scenario()` in `focal/alignment/stores/config_store.py`
- [X] T020 Implement migration plan methods in `InMemoryConfigStore` in `focal/alignment/stores/in_memory/config_store.py`
- [X] T021 Implement scenario archiving methods in `InMemoryConfigStore` in `focal/alignment/stores/in_memory/config_store.py`

### Content Hashing

- [X] T022 Implement `compute_node_content_hash()` function using SHA-256 in `focal/alignment/migration/diff.py`
- [X] T023 Implement `compute_scenario_checksum()` function for version validation in `focal/alignment/migration/diff.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Operator Updates Scenario Without Breaking Active Sessions (Priority: P1) 🎯 MVP

**Goal**: Operators can modify scenarios and generate migration plans with transformation maps

**Independent Test**: Modify a scenario with active sessions and verify the transformation map correctly identifies anchors and upstream/downstream changes

### Implementation for User Story 1

- [X] T024 Implement `find_anchor_nodes()` function using content hash matching in `focal/alignment/migration/diff.py`
- [X] T025 Implement `compute_upstream_changes()` function using reverse BFS in `focal/alignment/migration/diff.py`
- [X] T026 Implement `compute_downstream_changes()` function using forward BFS in `focal/alignment/migration/diff.py`
- [X] T027 Implement `compute_transformation_map()` function that builds complete diff in `focal/alignment/migration/diff.py`
- [X] T028 Implement `determine_migration_scenario()` function (clean_graft, gap_fill, re_route) in `focal/alignment/migration/diff.py`
- [X] T029 Implement `MigrationPlanner` class with `generate_plan()` method in `focal/alignment/migration/planner.py`
- [X] T030 Implement `build_migration_summary()` function (counts, warnings, affected sessions) in `focal/alignment/migration/planner.py`
- [X] T031 Create migration routes file `focal/api/routes/migrations.py`
- [X] T032 Implement `POST /scenarios/{scenario_id}/migration-plan` endpoint in `focal/api/routes/migrations.py`
- [X] T033 Implement `GET /migration-plans` endpoint (list with filters) in `focal/api/routes/migrations.py`
- [X] T034 Implement `GET /migration-plans/{plan_id}` endpoint in `focal/api/routes/migrations.py`
- [X] T035 Implement `GET /migration-plans/{plan_id}/summary` endpoint in `focal/api/routes/migrations.py`
- [X] T036 Implement `PUT /migration-plans/{plan_id}/policies` endpoint in `focal/api/routes/migrations.py`
- [X] T037 Implement `POST /migration-plans/{plan_id}/approve` endpoint in `focal/api/routes/migrations.py`
- [X] T038 Implement `POST /migration-plans/{plan_id}/reject` endpoint in `focal/api/routes/migrations.py`
- [X] T039 Implement `MigrationDeployer` class with Phase 1 `mark_sessions()` method in `focal/alignment/migration/planner.py`
- [X] T040 Implement `POST /migration-plans/{plan_id}/deploy` endpoint in `focal/api/routes/migrations.py`
- [X] T041 Implement `GET /migration-plans/{plan_id}/deployment-status` endpoint in `focal/api/routes/migrations.py`
- [X] T042 Register migration routes in `focal/api/routes/__init__.py`
- [X] T043 Add unit tests for `diff.py` functions in `tests/unit/alignment/migration/test_diff.py`
- [X] T044 Add unit tests for `planner.py` in `tests/unit/alignment/migration/test_planner.py`

**Checkpoint**: Operators can generate, configure, and deploy migration plans

---

## Phase 4: User Story 2 - Customer Continues Conversation After Scenario Update (Priority: P1) 🎯 MVP ✅

**Goal**: Returning customers are migrated at JIT when they send their next message

**Independent Test**: Simulate a customer return after scenario version change and verify the correct migration scenario is executed

### Implementation for User Story 2

- [X] T045 Create `ReconciliationResult` model (action, target_step_id, collect_fields, blocked_by_checkpoint) in `focal/alignment/migration/models.py`
- [X] T046 Implement `MigrationExecutor` class in `focal/alignment/migration/executor.py`
- [X] T047 Implement `execute_clean_graft()` method (silent teleport to V2 anchor) in `focal/alignment/migration/executor.py`
- [X] T048 Implement `execute_gap_fill()` method (backfill then teleport) in `focal/alignment/migration/executor.py`
- [X] T049 Implement `execute_re_route()` method (evaluate fork, check checkpoint, teleport) in `focal/alignment/migration/executor.py`
- [X] T050 Implement `_pre_turn_reconciliation()` method in `focal/alignment/engine.py` (AlignmentEngine) - must detect both `pending_migration` flag AND `scenario_checksum` mismatch as triggers for reconciliation
- [X] T051 Integrate reconciliation at start of `process_turn()` in `focal/alignment/engine.py` - update `scenario_checksum` on session after successful migration
- [X] T052 Implement fallback reconciliation for missing plans (anchor-based relocation) in `focal/alignment/migration/executor.py`
- [X] T053 Clear `pending_migration` flag and set new `scenario_checksum` after successful migration in `focal/alignment/migration/executor.py`
- [X] T054 Add unit tests for `executor.py` in `tests/unit/alignment/migration/test_executor.py`
- [X] T055 Add integration test for JIT migration flow in `tests/integration/alignment/migration/test_migration_flow.py`

**Checkpoint**: Customers are correctly migrated at JIT based on their migration scenario ✅

---

## Phase 5: User Story 3 - Operator Configures Per-Anchor Migration Policies (Priority: P2)

**Goal**: Granular control over migration behavior per anchor (scope filters, update_downstream)

**Independent Test**: Configure different policies for different anchors and verify sessions are filtered and migrated according to their anchor's policy

### Implementation for User Story 3

- [X] T056 Implement scope filter matching in `MigrationDeployer.mark_sessions()` in `focal/alignment/migration/planner.py`
- [X] T057 Implement channel filtering (include/exclude) in scope filter logic in `focal/alignment/migration/planner.py`
- [X] T058 Implement session age filtering (min/max days) in scope filter logic in `focal/alignment/migration/planner.py`
- [X] T059 Implement current_node filtering in scope filter logic in `focal/alignment/migration/planner.py`
- [X] T060 Implement `update_downstream=false` behavior (skip teleport, update version only) in `focal/alignment/migration/executor.py`
- [X] T061 Implement `force_scenario` policy override in `focal/alignment/migration/executor.py`
- [X] T062 Add unit tests for scope filter matching in `tests/unit/alignment/migration/test_planner.py`

**Checkpoint**: Per-anchor policies correctly filter sessions and control migration behavior

---

## Phase 6: User Story 4 - Re-Routing with Checkpoint Blocking (Priority: P2)

**Goal**: Prevent teleportation past irreversible checkpoints

**Independent Test**: Add an upstream fork and verify checkpoint blocking when customer has passed an irreversible step

### Implementation for User Story 4

- [X] T063 Implement `find_last_checkpoint()` function (walk backwards through step_history) in `focal/alignment/migration/executor.py`
- [X] T064 Implement `is_upstream_of_checkpoint()` function (BFS from target to checkpoint) in `focal/alignment/migration/executor.py`
- [X] T065 Implement `evaluate_fork_condition()` method for re-route scenario in `focal/alignment/migration/executor.py`
- [X] T066 Integrate checkpoint blocking into `execute_re_route()` in `focal/alignment/migration/executor.py`
- [X] T067 Add `checkpoint_warning` field to `ReconciliationResult` for operator visibility in `focal/alignment/migration/models.py`
- [X] T068 Add structured logging for checkpoint blocks in `focal/alignment/migration/executor.py`
- [X] T069 Add unit tests for checkpoint blocking in `tests/unit/alignment/migration/test_executor.py`

**Checkpoint**: Re-routing respects checkpoints and logs blocks for operator visibility

---

## Phase 7: User Story 5 - Multi-Version Gaps Without Thrashing (Priority: P2)

**Goal**: Composite migration for customers who missed multiple versions

**Independent Test**: Create multiple sequential scenario updates and verify a dormant customer only sees the net requirements of the final version

### Implementation for User Story 5

- [X] T070 Create `CompositeMapper` class in `focal/alignment/migration/composite.py`
- [X] T071 Implement `get_plan_chain()` method to load V1→V2→V3→...→Vn plans in `focal/alignment/migration/composite.py`
- [X] T072 Implement `accumulate_requirements()` method (collect all fields across chain) in `focal/alignment/migration/composite.py`
- [X] T073 Implement `prune_requirements()` method (keep only fields needed in final version) in `focal/alignment/migration/composite.py`
- [X] T074 Implement `execute_composite_migration()` method in `focal/alignment/migration/composite.py`
- [X] T075 Implement fallback for broken plan chain (intermediate plan expired) in `focal/alignment/migration/composite.py`
- [X] T076 Integrate composite migration into `MigrationExecutor` for multi-version gaps in `focal/alignment/migration/executor.py`
- [X] T077 Add unit tests for composite migration in `tests/unit/alignment/migration/test_composite.py`

**Checkpoint**: Multi-version migrations correctly prune obsolete requirements

---

## Phase 8: User Story 6 - Gap Fill Without Re-Asking Customer (Priority: P3)

**Goal**: Retrieve data from profile/session/conversation before asking customer

**Independent Test**: Require a field during migration and verify each gap fill source is checked in order

### Implementation for User Story 6

- [X] T078 Create `GapFillService` class in `focal/alignment/migration/gap_fill.py`
- [X] T079 Create `GapFillResult` model (filled, value, source, confidence, needs_confirmation) in `focal/alignment/migration/models.py`
- [X] T080 Implement `try_profile_fill()` method in `focal/alignment/migration/gap_fill.py`
- [X] T081 Implement `try_session_fill()` method in `focal/alignment/migration/gap_fill.py`
- [X] T082 Implement `try_conversation_extraction()` method using LLMProvider in `focal/alignment/migration/gap_fill.py`
- [X] T083 Implement extraction prompt template with JSON output format in `focal/alignment/migration/gap_fill.py`
- [X] T084 Implement confidence threshold logic (0.85 for use, 0.95 for no confirmation) in `focal/alignment/migration/gap_fill.py`
- [X] T085 Implement `persist_extracted_values()` to save to profile in `focal/alignment/migration/gap_fill.py`
- [X] T086 Integrate `GapFillService` into `execute_gap_fill()` in `focal/alignment/migration/executor.py`
- [X] T087 Add unit tests for gap fill in `tests/unit/alignment/migration/test_gap_fill.py`
- [X] T088 Add LLM recording tests for extraction in `tests/unit/alignment/migration/test_gap_fill.py`

**Checkpoint**: Gap fill retrieves data without re-asking customers in most cases

---

## Phase 9: Polish & Cross-Cutting Concerns ✅

**Purpose**: Improvements that affect multiple user stories

- [X] T089 [P] Add structured logging for all migration operations in `focal/alignment/migration/`
- [X] T090 [P] Add metrics for migration counts by scenario type (clean_graft, gap_fill, re_route) in `focal/alignment/migration/executor.py`
- [X] T091 [P] Add audit log entries for migration applications in `focal/alignment/migration/executor.py`
- [X] T092 [P] Implement version retention cleanup (default 7 days for archived scenarios) in `focal/alignment/migration/planner.py`
- [X] T093 [P] Implement plan retention cleanup (default 30 days) in `focal/alignment/migration/planner.py`
- [X] T094 Add ConfigStore contract tests for migration plan methods in `tests/contract/test_config_store_migration.py`
- [X] T095 Run quickstart.md validation end-to-end
- [X] T096 Update CLAUDE.md with migration module context

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can then proceed in priority order (P1 → P2 → P3)
  - Note: US1 and US2 are both P1 but US2 depends on US1's executor integration point
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Depends on US1 (needs MigrationPlanner, transformation map) but implements separate executor
- **User Story 3 (P2)**: Depends on US1 (extends policy behavior during marking)
- **User Story 4 (P2)**: Depends on US2 (extends re-route execution with checkpoint blocking)
- **User Story 5 (P2)**: Depends on US2 (extends executor with composite migration)
- **User Story 6 (P3)**: Depends on US2 (extends gap_fill execution with data retrieval)

### Within Each User Story

- Models before services
- Services before API endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Foundational model tasks (T004-T012) can run in parallel
- Session store extensions (T013-T017) can run in parallel with Config store extensions (T018-T021)
- All API endpoint tasks within US1 (T032-T042) can be batched after MigrationPlanner is complete
- All test tasks can run in parallel with their corresponding implementation tasks
- Polish tasks (T089-T096) can all run in parallel

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (migration plan generation + deployment)
4. Complete Phase 4: User Story 2 (JIT execution)
5. **STOP and VALIDATE**: Test operator workflow and customer migration end-to-end
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Operators can create migration plans → Demo
3. Add User Story 2 → Customers migrate at JIT → MVP!
4. Add User Story 3 → Per-anchor policies → Enhanced control
5. Add User Story 4 → Checkpoint blocking → Safety for payments/irreversible actions
6. Add User Story 5 → Composite migration → Handle dormant customers
7. Add User Story 6 → Gap fill optimization → Better customer experience

---

## Summary

| Phase | Tasks | Parallel Opportunities | Story |
|-------|-------|------------------------|-------|
| Setup | 3 | 2 | - |
| Foundational | 20 | 15 | - |
| US1 (P1) | 21 | 8 | Operator Updates Scenario |
| US2 (P1) | 11 | 2 | Customer Continues Conversation |
| US3 (P2) | 7 | 0 | Per-Anchor Policies |
| US4 (P2) | 7 | 0 | Checkpoint Blocking |
| US5 (P2) | 8 | 0 | Multi-Version Gaps |
| US6 (P3) | 11 | 0 | Gap Fill |
| Polish | 8 | 5 | - |
| **Total** | **96** | **32** | |

**MVP Scope**: Phases 1-4 (US1 + US2) = 55 tasks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
