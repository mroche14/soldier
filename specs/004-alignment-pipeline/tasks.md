# Tasks: Alignment Pipeline

**Input**: Design documents from `/specs/004-alignment-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests ARE requested (85% coverage per constitution). Test tasks included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `soldier/` package at repository root
- **Tests**: `tests/` at repository root
- All paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Add new dependencies and create directory structure

- [x] T001 Add numpy, scipy, scikit-learn dependencies via `uv add numpy scipy scikit-learn`
- [x] T002 [P] Create test directory structure: `tests/unit/alignment/retrieval/`, `tests/unit/alignment/context/`, `tests/unit/alignment/filtering/`, `tests/unit/alignment/execution/`, `tests/unit/alignment/generation/`, `tests/unit/alignment/enforcement/`
- [x] T003 [P] Create prompt template directories: `soldier/alignment/context/prompts/`, `soldier/alignment/filtering/prompts/`, `soldier/alignment/generation/prompts/`
- [x] T004 [P] Create `tests/integration/alignment/` directory for integration tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and interfaces that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models (from data-model.md)

- [x] T005 [P] Implement ScoredItem and SelectionResult dataclasses in `soldier/alignment/retrieval/selection.py`
- [x] T006 [P] Implement SelectionStrategy ABC interface in `soldier/alignment/retrieval/selection.py`
- [x] T007 [P] Extend Context model with intent, entities, sentiment, scenario_signal in `soldier/alignment/context/models.py`
- [x] T008 [P] Implement ExtractedEntity, Sentiment, Urgency, ScenarioSignal enums in `soldier/alignment/context/models.py`
- [x] T009 [P] Implement ScoredRule, RuleSource, RetrievalResult in `soldier/alignment/retrieval/models.py`
- [x] T010 [P] Implement MatchedRule, RuleFilterResult in `soldier/alignment/filtering/models.py`
- [x] T011 [P] Implement ScenarioAction, ScenarioFilterResult in `soldier/alignment/filtering/models.py`
- [x] T012 [P] Implement ToolResult, VariableResolution in `soldier/alignment/execution/models.py`
- [x] T013 [P] Implement TemplateMode, GenerationResult in `soldier/alignment/generation/models.py`
- [x] T014 [P] Implement ConstraintViolation, EnforcementResult in `soldier/alignment/enforcement/models.py`
- [x] T015 [P] Implement PipelineStepTiming, AlignmentResult in `soldier/alignment/result.py`

### Configuration Models

- [x] T016 [P] Extend SelectionConfig with strategy-specific params in `soldier/config/models/selection.py`
- [x] T017 [P] Implement PipelineStepConfig, PipelineConfig in `soldier/config/models/pipeline.py`

### Test Factories

- [x] T018 [P] Create ContextFactory, RuleFactory test fixtures in `tests/factories/alignment.py`

**Checkpoint**: Foundation ready - all models defined, user story implementation can begin

---

## Phase 3: User Story 4 - Dynamic Selection (Priority: P3 but foundational) 🎯 First

**Goal**: Implement selection strategies that all retrieval steps depend on (FR-001 to FR-004)

**Why first**: Selection strategies are used by US1, US2, US3 - building them first enables parallel work

**Independent Test**: Run selection strategy tests with various score distributions

### Tests for User Story 4

- [x] T019 [P] [US4] Unit test for FixedKSelectionStrategy in `tests/unit/alignment/retrieval/test_selection.py`
- [x] T020 [P] [US4] Unit test for ElbowSelectionStrategy in `tests/unit/alignment/retrieval/test_selection.py`
- [x] T021 [P] [US4] Unit test for AdaptiveKSelectionStrategy in `tests/unit/alignment/retrieval/test_selection.py`
- [x] T022 [P] [US4] Unit test for EntropySelectionStrategy in `tests/unit/alignment/retrieval/test_selection.py`
- [x] T023 [P] [US4] Unit test for ClusterSelectionStrategy in `tests/unit/alignment/retrieval/test_selection.py`
- [x] T024 [P] [US4] Contract tests for SelectionStrategy interface in `tests/unit/alignment/retrieval/test_selection_contract.py`

### Implementation for User Story 4

- [x] T025 [US4] Implement FixedKSelectionStrategy in `soldier/alignment/retrieval/selection.py`
- [x] T026 [US4] Implement ElbowSelectionStrategy in `soldier/alignment/retrieval/selection.py`
- [x] T027 [US4] Implement AdaptiveKSelectionStrategy in `soldier/alignment/retrieval/selection.py`
- [x] T028 [US4] Implement EntropySelectionStrategy in `soldier/alignment/retrieval/selection.py`
- [x] T029 [US4] Implement ClusterSelectionStrategy in `soldier/alignment/retrieval/selection.py`
- [x] T030 [US4] Implement create_selection_strategy factory in `soldier/alignment/retrieval/selection.py`
- [x] T031 [US4] Export selection strategies in `soldier/alignment/retrieval/__init__.py`

**Checkpoint**: Selection strategies complete - can be used by retrieval components

---

## Phase 4: User Story 1 - Process Simple Message (Priority: P1) 🎯 MVP

**Goal**: End-to-end processing of a user message with rule matching and response generation (FR-005 to FR-027, FR-028 to FR-032)

**Independent Test**: Send a message to an agent with pre-configured rules and verify the response follows those rules

### Tests for User Story 1

- [x] T032 [P] [US1] Unit test for ContextExtractor in `tests/unit/alignment/context/test_extractor.py`
- [x] T033 [P] [US1] Unit test for RuleRetriever in `tests/unit/alignment/retrieval/test_rule_retriever.py`
- [x] T034 [P] [US1] Unit test for RuleFilter in `tests/unit/alignment/filtering/test_rule_filter.py`
- [x] T035 [P] [US1] Unit test for PromptBuilder in `tests/unit/alignment/generation/test_prompt_builder.py`
- [x] T036 [P] [US1] Unit test for ResponseGenerator in `tests/unit/alignment/generation/test_generator.py`
- [x] T037 [P] [US1] Unit test for AlignmentEngine basic flow in `tests/unit/alignment/test_engine.py`
- [x] T038 [US1] Integration test for full pipeline flow in `tests/integration/alignment/test_engine.py`

### Context Extraction (Phase 7)

- [x] T039 [US1] Create intent extraction prompt template in `soldier/alignment/context/prompts/extract_intent.txt`
- [x] T040 [US1] Implement ContextExtractor with LLM, embedding_only, and disabled modes in `soldier/alignment/context/extractor.py`
- [x] T041 [US1] Export ContextExtractor in `soldier/alignment/context/__init__.py`

### Retrieval (Phase 8)

- [x] T042 [US1] Implement RuleRetriever with scope hierarchy (global, scenario, step) in `soldier/alignment/retrieval/rule_retriever.py`
- [x] T043 [US1] Implement business filters (enabled, max_fires, cooldown) in `soldier/alignment/retrieval/rule_retriever.py`
- [x] T044 [US1] Implement Reranker wrapper for RerankProvider in `soldier/alignment/retrieval/reranker.py`
- [x] T045 [US1] Export retrieval components in `soldier/alignment/retrieval/__init__.py`

### Filtering (Phase 9)

- [x] T046 [US1] Create rule filtering prompt template in `soldier/alignment/filtering/prompts/filter_rules.txt`
- [x] T047 [US1] Implement RuleFilter with LLM-based judgment in `soldier/alignment/filtering/rule_filter.py`
- [x] T048 [US1] Export filtering components in `soldier/alignment/filtering/__init__.py`

### Generation (Phase 10)

- [x] T049 [US1] Create system prompt template in `soldier/alignment/generation/prompts/system_prompt.txt`
- [x] T050 [US1] Implement PromptBuilder for assembling context, rules, memory, tools in `soldier/alignment/generation/prompt_builder.py`
- [x] T051 [US1] Implement ResponseGenerator with template mode handling in `soldier/alignment/generation/generator.py`
- [x] T052 [US1] Export generation components in `soldier/alignment/generation/__init__.py`

### Engine Integration (Phase 11)

- [x] T053 [US1] Implement AlignmentEngine orchestrator with step enable/disable in `soldier/alignment/engine.py`
- [x] T054 [US1] Implement pipeline step timing and logging in `soldier/alignment/engine.py`
- [x] T055 [US1] Implement graceful error handling per step in `soldier/alignment/engine.py`
- [x] T056 [US1] Export AlignmentEngine and AlignmentResult in `soldier/alignment/__init__.py`

**Checkpoint**: MVP complete - simple message processing works end-to-end

---

## Phase 5: User Story 2 - Multi-Step Scenarios (Priority: P2)

**Goal**: Navigate multi-step conversational flows with step transitions (FR-016 to FR-019)

**Independent Test**: Simulate a complete scenario flow (e.g., return process) verifying correct transitions

### Tests for User Story 2

- [x] T057 [P] [US2] Unit test for ScenarioRetriever in `tests/unit/alignment/retrieval/test_scenario_retriever.py`
- [x] T058 [P] [US2] Unit test for ScenarioFilter in `tests/unit/alignment/filtering/test_scenario_filter.py`
- [x] T059 [US2] Integration test for scenario flow in `tests/integration/alignment/test_scenario_flow.py`

### Implementation for User Story 2

- [x] T060 [US2] Implement ScenarioRetriever with selection strategy in `soldier/alignment/retrieval/scenario_retriever.py`
- [x] T061 [US2] Create scenario evaluation prompt in `soldier/alignment/filtering/prompts/evaluate_scenario.txt`
- [x] T062 [US2] Implement ScenarioFilter with graph navigation in `soldier/alignment/filtering/scenario_filter.py`
- [x] T063 [US2] Implement transition evaluation with LLM adjudication in `soldier/alignment/filtering/scenario_filter.py`
- [x] T064 [US2] Implement loop detection in scenario transitions in `soldier/alignment/filtering/scenario_filter.py`
- [x] T065 [US2] Implement re-localization for inconsistent state recovery in `soldier/alignment/filtering/scenario_filter.py`
- [x] T066 [US2] Integrate ScenarioFilter into AlignmentEngine in `soldier/alignment/engine.py`

**Checkpoint**: Scenario navigation works - multi-step flows complete

---

## Phase 6: User Story 3 - Tool Execution (Priority: P2)

**Goal**: Execute tools from matched rules and incorporate results (FR-020 to FR-022)

**Independent Test**: Configure a rule with attached tool, send matching message, verify tool executed

### Tests for User Story 3

- [x] T067 [P] [US3] Unit test for ToolExecutor in `tests/unit/alignment/execution/test_tool_executor.py`
- [x] T068 [P] [US3] Unit test for VariableResolver in `tests/unit/alignment/execution/test_variable_resolver.py`
- [x] T069 [US3] Integration test for tool execution flow in `tests/integration/alignment/test_tool_execution.py`

### Implementation for User Story 3

- [x] T070 [US3] Implement VariableResolver with session, profile, tool sources in `soldier/alignment/execution/variable_resolver.py`
- [x] T071 [US3] Implement ToolExecutor with timeout handling in `soldier/alignment/execution/tool_executor.py`
- [x] T072 [US3] Implement parallel tool execution for multiple matched rules in `soldier/alignment/execution/tool_executor.py`
- [x] T073 [US3] Integrate tool results into PromptBuilder in `soldier/alignment/generation/prompt_builder.py`
- [x] T074 [US3] Integrate ToolExecutor into AlignmentEngine in `soldier/alignment/engine.py`
- [x] T075 [US3] Export execution components in `soldier/alignment/execution/__init__.py`

**Checkpoint**: Tool execution works - tools run and results incorporated

---

## Phase 7: User Story 5 - Hard Constraint Enforcement (Priority: P3)

**Goal**: Validate responses against hard constraints with regeneration (FR-025 to FR-027)

**Independent Test**: Configure a hard constraint, generate violating response, verify correction

### Tests for User Story 5

- [x] T076 [P] [US5] Unit test for EnforcementValidator in `tests/unit/alignment/enforcement/test_validator.py`
- [x] T077 [P] [US5] Unit test for FallbackHandler in `tests/unit/alignment/enforcement/test_fallback.py`
- [x] T078 [US5] Integration test for constraint enforcement in `tests/integration/alignment/test_enforcement.py`

### Implementation for User Story 5

- [x] T079 [US5] Implement EnforcementValidator with constraint checking in `soldier/alignment/enforcement/validator.py`
- [x] T080 [US5] Implement regeneration logic with stronger prompt in `soldier/alignment/enforcement/validator.py`
- [x] T081 [US5] Implement FallbackHandler with template fallback chain in `soldier/alignment/enforcement/fallback.py`
- [x] T082 [US5] Integrate EnforcementValidator into AlignmentEngine in `soldier/alignment/engine.py`
- [x] T083 [US5] Export enforcement components in `soldier/alignment/enforcement/__init__.py`

**Checkpoint**: Hard constraints work - violations detected and corrected

---

## Phase 8: User Story 6 - Template Responses (Priority: P3)

**Goal**: Use pre-written templates for critical responses (FR-023)

**Independent Test**: Trigger rule with exclusive template, verify exact text returned

### Tests for User Story 6

- [x] T084 [P] [US6] Unit test for template modes (exclusive, suggest, fallback) in `tests/unit/alignment/generation/test_generator.py`
- [x] T085 [US6] Integration test for template flow in `tests/integration/alignment/test_templates.py`

### Implementation for User Story 6

- [x] T086 [US6] Implement EXCLUSIVE template mode in ResponseGenerator (skip LLM) in `soldier/alignment/generation/generator.py`
- [x] T087 [US6] Implement SUGGEST template mode in PromptBuilder in `soldier/alignment/generation/prompt_builder.py`
- [x] T088 [US6] Implement variable placeholder resolution in templates in `soldier/alignment/generation/generator.py`

**Checkpoint**: Template modes work - exact text returned when configured

---

## Phase 9: Memory Integration

**Goal**: Retrieve relevant memory episodes (FR-013)

**Independent Test**: Configure memory retrieval, verify episodes included in prompt

### Tests for Memory Integration

- [x] T089 [P] [MEM] Unit test for MemoryRetriever in `tests/unit/memory/retrieval/test_retriever.py`

### Implementation for Memory Integration

- [x] T090 [MEM] Implement MemoryRetriever with selection strategy in `soldier/memory/retrieval/retriever.py`
- [x] T091 [MEM] Integrate memory context into PromptBuilder in `soldier/alignment/generation/prompt_builder.py`
- [x] T092 [MEM] Integrate MemoryRetriever into AlignmentEngine in `soldier/alignment/engine.py`

**Checkpoint**: Memory retrieval works - past context incorporated

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, performance testing, and documentation

 - [x] T093 [P] Add comprehensive docstrings to all public classes/methods
 - [x] T094 [P] Update `soldier/alignment/__init__.py` with all public exports
 - [x] T095 Run full test suite and verify 85% coverage in `soldier/alignment/`
 - [x] T096 Run quickstart.md examples and verify they work
 - [x] T097 Run mypy type checking and fix any errors
 - [x] T098 Run ruff linting and formatting
 - [x] T099 [PERF] Create performance test for pipeline latency (P50 < 1000ms) and concurrency (SC-006) in `tests/performance/test_pipeline_latency.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US4 Selection (Phase 3)**: Depends on Foundational - enables parallel retrieval work
- **US1 MVP (Phase 4)**: Depends on Foundational + US4 Selection
- **US2 Scenarios (Phase 5)**: Depends on US1 (extends engine)
- **US3 Tools (Phase 6)**: Depends on US1 (extends engine)
- **US5 Enforcement (Phase 7)**: Depends on US1 (extends generation)
- **US6 Templates (Phase 8)**: Depends on US1 (extends generation)
- **Memory (Phase 9)**: Depends on US1 (extends retrieval)
- **Polish (Phase 10)**: Depends on all user stories

### User Story Dependencies

```
                    ┌─────────────┐
                    │   Setup     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Foundational│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │US4 Selection│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  US1 MVP    │ ◄── Main pipeline
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────▼─────┐    ┌─────▼─────┐    ┌──────▼─────┐
   │US2 Scenario│   │ US3 Tools │    │US5 Enforce │
   └───────────┘    └───────────┘    └──────┬─────┘
                                            │
                                     ┌──────▼─────┐
                                     │US6 Template│
                                     └────────────┘
```

### Parallel Opportunities

**Within Phase 2 (Foundational)**: All T005-T018 can run in parallel (different files)

**Within Phase 3 (US4 Selection)**: All T019-T024 tests can run in parallel

**Within Phase 4 (US1 MVP)**:
- T032-T036 tests can run in parallel
- T039, T046, T049 prompt templates can run in parallel

**After US1 complete**: US2, US3, US5 can run in parallel (different components)

---

## Parallel Example: Foundational Phase

```bash
# Launch all model implementations in parallel:
Task: "T005 Implement ScoredItem and SelectionResult in soldier/alignment/retrieval/selection.py"
Task: "T007 Extend Context model in soldier/alignment/context/models.py"
Task: "T010 Implement MatchedRule, RuleFilterResult in soldier/alignment/filtering/models.py"
Task: "T012 Implement ToolResult in soldier/alignment/execution/models.py"
Task: "T013 Implement GenerationResult in soldier/alignment/generation/models.py"
Task: "T014 Implement EnforcementResult in soldier/alignment/enforcement/models.py"
Task: "T015 Implement AlignmentResult in soldier/alignment/result.py"
```

---

## Implementation Strategy

### MVP First (US4 + US1 Only)

1. Complete Phase 1: Setup (dependencies, directories)
2. Complete Phase 2: Foundational (all models)
3. Complete Phase 3: US4 Selection Strategies
4. Complete Phase 4: US1 Simple Message Processing
5. **STOP and VALIDATE**: Test with quickstart.md examples
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational + US4 → Selection strategies usable
2. Add US1 → MVP: Simple message processing works
3. Add US2 → Scenario flows work
4. Add US3 → Tool execution works
5. Add US5 + US6 → Enforcement and templates work
6. Add Memory → Full context retrieval works

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Setup | 4 | Dependencies, directories |
| Foundational | 14 | All data models |
| US4 Selection | 13 | Selection strategies |
| US1 MVP | 25 | Core pipeline |
| US2 Scenarios | 10 | Scenario navigation |
| US3 Tools | 9 | Tool execution |
| US5 Enforcement | 8 | Constraint validation |
| US6 Templates | 5 | Template modes |
| Memory | 4 | Memory retrieval |
| Polish | 7 | Testing, performance, docs |

**Total Tasks**: 99
**Parallel Opportunities**: 50+ tasks marked [P]
**MVP Scope**: Phases 1-4 (56 tasks)
