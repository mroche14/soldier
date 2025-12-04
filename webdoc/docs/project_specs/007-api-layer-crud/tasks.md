# Tasks: API CRUD Operations

**Input**: Design documents from `/specs/001-api-crud/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: API layer shared models and utilities needed by all CRUD routes

- [x] T001 Extend ErrorCode enum with CRUD-specific error codes in soldier/api/models/errors.py
- [x] T002 [P] Create pagination models (PaginatedResponse, pagination params) in soldier/api/models/pagination.py
- [x] T003 [P] Create bulk operation models (BulkOperation, BulkResult, BulkRequest, BulkResponse) in soldier/api/models/bulk.py
- [x] T004 Register new routes in soldier/api/routes/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models and services that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Agent model with AgentSettings embedded model in soldier/alignment/models/agent.py
- [x] T006 [P] Create ToolActivation model in soldier/alignment/models/tool_activation.py
- [x] T007 [P] Create PublishJob and PublishStage models in soldier/alignment/models/publish.py
- [x] T008 Export new models from soldier/alignment/models/__init__.py
- [x] T009 Add Agent and ToolActivation CRUD methods to ConfigStore interface in soldier/alignment/stores/config_store.py
- [x] T010 Implement Agent and ToolActivation methods in InMemoryConfigStore in soldier/alignment/stores/inmemory.py
- [x] T011 [P] Create async embedding service using BackgroundTasks in soldier/api/services/embedding.py
- [x] T012 [P] Create publish job orchestration service in soldier/api/services/publish.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Agent Management (Priority: P1) 🎯 MVP

**Goal**: Enable administrators to create, configure, and manage AI agents via RESTful API

**Independent Test**: Create agent via POST, retrieve it, update settings, list with pagination, delete it

### Implementation for User Story 1

- [x] T013 [P] [US1] Create AgentCreate and AgentUpdate request models in soldier/api/models/crud.py
- [x] T014 [P] [US1] Create AgentResponse model with stats in soldier/api/models/crud.py
- [x] T015 [US1] Implement GET /agents list endpoint with pagination, sorting, and filters in soldier/api/routes/agents.py
- [x] T016 [US1] Implement POST /agents create endpoint in soldier/api/routes/agents.py
- [x] T017 [US1] Implement GET /agents/{agent_id} get single endpoint in soldier/api/routes/agents.py
- [x] T018 [US1] Implement PUT /agents/{agent_id} update endpoint in soldier/api/routes/agents.py
- [x] T019 [US1] Implement DELETE /agents/{agent_id} soft-delete endpoint in soldier/api/routes/agents.py
- [x] T020 [US1] Add tenant_id extraction from JWT and scoping to all agent endpoints in soldier/api/routes/agents.py

**Checkpoint**: User Story 1 should be fully functional - agents can be created, read, updated, deleted, and listed

---

## Phase 4: User Story 2 - Rule Management (Priority: P1)

**Goal**: Enable content authors to define behavioral rules that guide agent responses with async embedding computation

**Independent Test**: Create rules for an agent, list with scope/priority filters, update condition text (triggers embedding recomputation), bulk operations, delete

### Implementation for User Story 2

- [x] T021 [P] [US2] Create RuleCreate and RuleUpdate request models in soldier/api/models/crud.py
- [x] T022 [P] [US2] Create RuleResponse model in soldier/api/models/crud.py
- [x] T023 [US2] Implement GET /agents/{agent_id}/rules list endpoint with scope, priority range, enabled filters, and sorting in soldier/api/routes/rules.py
- [x] T024 [US2] Implement POST /agents/{agent_id}/rules create endpoint with async embedding trigger in soldier/api/routes/rules.py
- [x] T025 [US2] Implement GET /agents/{agent_id}/rules/{rule_id} get single endpoint in soldier/api/routes/rules.py
- [x] T026 [US2] Implement PUT /agents/{agent_id}/rules/{rule_id} update endpoint with async embedding trigger on text change in soldier/api/routes/rules.py
- [x] T027 [US2] Implement DELETE /agents/{agent_id}/rules/{rule_id} soft-delete endpoint in soldier/api/routes/rules.py
- [x] T028 [US2] Implement POST /agents/{agent_id}/rules/bulk bulk operations endpoint in soldier/api/routes/rules.py
- [x] T029 [US2] Add tenant_id scoping to all rule endpoints in soldier/api/routes/rules.py

**Checkpoint**: User Story 2 should be fully functional - rules can be CRUD'd with filtering and bulk ops, embeddings compute async

---

## Phase 5: User Story 3 - Scenario Management (Priority: P2)

**Goal**: Enable conversation designers to create multi-step conversational flows with steps and transitions

**Independent Test**: Create scenario with steps, add steps, update transitions, delete non-entry step, verify entry step deletion blocked

### Implementation for User Story 3

- [x] T030 [P] [US3] Create ScenarioCreate, ScenarioUpdate, StepCreate, StepUpdate request models in soldier/api/models/crud.py
- [x] T031 [P] [US3] Create ScenarioResponse, StepResponse models in soldier/api/models/crud.py
- [x] T032 [US3] Implement scenario graph validation (detect unreachable steps) helper in soldier/api/services/scenario_validation.py
- [x] T033 [US3] Implement GET /agents/{agent_id}/scenarios list endpoint with tag, enabled filters, and sorting in soldier/api/routes/scenarios.py
- [x] T034 [US3] Implement POST /agents/{agent_id}/scenarios create endpoint with step ID auto-generation in soldier/api/routes/scenarios.py
- [x] T035 [US3] Implement GET /agents/{agent_id}/scenarios/{scenario_id} get single endpoint in soldier/api/routes/scenarios.py
- [x] T036 [US3] Implement PUT /agents/{agent_id}/scenarios/{scenario_id} update endpoint in soldier/api/routes/scenarios.py
- [x] T037 [US3] Implement DELETE /agents/{agent_id}/scenarios/{scenario_id} soft-delete endpoint in soldier/api/routes/scenarios.py
- [x] T038 [US3] Implement POST /agents/{agent_id}/scenarios/{scenario_id}/steps add step endpoint in soldier/api/routes/scenarios.py
- [x] T039 [US3] Implement PUT /agents/{agent_id}/scenarios/{scenario_id}/steps/{step_id} update step endpoint in soldier/api/routes/scenarios.py
- [x] T040 [US3] Implement DELETE /agents/{agent_id}/scenarios/{scenario_id}/steps/{step_id} delete step with entry step protection in soldier/api/routes/scenarios.py
- [x] T041 [US3] Add tenant_id scoping to all scenario endpoints in soldier/api/routes/scenarios.py

**Checkpoint**: User Story 3 should be fully functional - scenarios with steps and transitions can be managed

---

## Phase 6: User Story 4 - Template Management (Priority: P2)

**Goal**: Enable content authors to create response templates with variable placeholders and preview functionality

**Independent Test**: Create template with variables, preview with sample values, filter by mode, update scope

### Implementation for User Story 4

- [x] T042 [P] [US4] Create TemplateCreate, TemplateUpdate request models in soldier/api/models/crud.py
- [x] T043 [P] [US4] Create TemplateResponse, TemplatePreviewRequest, TemplatePreviewResponse models in soldier/api/models/crud.py
- [x] T044 [P] [US4] Implement template variable extraction helper (regex for {variable_name}) in soldier/api/services/template_utils.py
- [x] T045 [US4] Implement GET /agents/{agent_id}/templates list endpoint with mode, scope filters, and sorting in soldier/api/routes/templates.py
- [x] T046 [US4] Implement POST /agents/{agent_id}/templates create endpoint with variable extraction in soldier/api/routes/templates.py
- [x] T047 [US4] Implement GET /agents/{agent_id}/templates/{template_id} get single endpoint in soldier/api/routes/templates.py
- [x] T048 [US4] Implement PUT /agents/{agent_id}/templates/{template_id} update endpoint in soldier/api/routes/templates.py
- [x] T049 [US4] Implement DELETE /agents/{agent_id}/templates/{template_id} soft-delete endpoint in soldier/api/routes/templates.py
- [x] T050 [US4] Implement POST /agents/{agent_id}/templates/{template_id}/preview preview endpoint in soldier/api/routes/templates.py
- [x] T051 [US4] Add tenant_id scoping to all template endpoints in soldier/api/routes/templates.py

**Checkpoint**: User Story 4 should be fully functional - templates with variables can be managed and previewed

---

## Phase 7: User Story 5 - Variable Management (Priority: P3)

**Goal**: Enable system integrators to define dynamic context variables with resolver tools and caching policies

**Independent Test**: Create variable with resolver tool, update cache TTL, list all variables

### Implementation for User Story 5

- [x] T052 [P] [US5] Create VariableCreate, VariableUpdate request models in soldier/api/models/crud.py
- [x] T053 [P] [US5] Create VariableResponse model in soldier/api/models/crud.py
- [x] T054 [US5] Implement GET /agents/{agent_id}/variables list endpoint in soldier/api/routes/variables.py
- [x] T055 [US5] Implement POST /agents/{agent_id}/variables create endpoint in soldier/api/routes/variables.py
- [x] T056 [US5] Implement GET /agents/{agent_id}/variables/{variable_id} get single endpoint in soldier/api/routes/variables.py
- [x] T057 [US5] Implement PUT /agents/{agent_id}/variables/{variable_id} update endpoint in soldier/api/routes/variables.py
- [x] T058 [US5] Implement DELETE /agents/{agent_id}/variables/{variable_id} soft-delete endpoint in soldier/api/routes/variables.py
- [x] T059 [US5] Add tenant_id scoping to all variable endpoints in soldier/api/routes/variables.py

**Checkpoint**: User Story 5 should be fully functional - variables can be CRUD'd with resolver tool references

---

## Phase 8: User Story 6 - Tool Activation Management (Priority: P3)

**Goal**: Enable administrators to enable/disable tools for specific agents with policy overrides

**Independent Test**: Enable tool for agent, verify enabled, disable tool, verify disabled, add policy override

### Implementation for User Story 6

- [x] T060 [P] [US6] Create ToolActivationCreate, ToolActivationUpdate request models in soldier/api/models/crud.py
- [x] T061 [P] [US6] Create ToolActivationResponse model in soldier/api/models/crud.py
- [x] T062 [US6] Implement GET /agents/{agent_id}/tools list endpoint in soldier/api/routes/tools.py
- [x] T063 [US6] Implement POST /agents/{agent_id}/tools enable tool endpoint in soldier/api/routes/tools.py
- [x] T064 [US6] Implement PUT /agents/{agent_id}/tools/{tool_id} update activation with policy override in soldier/api/routes/tools.py
- [x] T065 [US6] Implement DELETE /agents/{agent_id}/tools/{tool_id} disable tool endpoint in soldier/api/routes/tools.py
- [x] T066 [US6] Add tenant_id scoping to all tool endpoints in soldier/api/routes/tools.py

**Checkpoint**: User Story 6 should be fully functional - tools can be enabled/disabled per agent with overrides

---

## Phase 9: User Story 7 - Publishing and Versioning (Priority: P2)

**Goal**: Enable platform operators to publish configuration changes and rollback to previous versions

**Independent Test**: Check publish status, publish changes, verify version increment, check job progress, rollback

### Implementation for User Story 7

- [x] T067 [P] [US7] Create PublishStatusResponse, PublishRequest, PublishJobResponse, RollbackRequest models in soldier/api/models/crud.py
- [x] T068 [US7] Implement GET /agents/{agent_id}/publish status endpoint with change summary in soldier/api/routes/publish.py
- [x] T069 [US7] Implement POST /agents/{agent_id}/publish initiate publish endpoint in soldier/api/routes/publish.py
- [x] T070 [US7] Implement GET /agents/{agent_id}/publish/{publish_id} get job status endpoint in soldier/api/routes/publish.py
- [x] T071 [US7] Implement POST /agents/{agent_id}/rollback rollback to version endpoint in soldier/api/routes/publish.py
- [x] T072 [US7] Wire publish service to execute stages (validate, compile, write_bundles, swap_pointer, invalidate_cache) in soldier/api/services/publish.py
- [x] T073 [US7] Add tenant_id scoping to all publish endpoints in soldier/api/routes/publish.py

**Checkpoint**: User Story 7 should be fully functional - configuration can be published and rolled back

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T074 [P] Add structured logging for all CRUD operations across all route modules
- [x] T075 [P] Validate all endpoints return consistent error responses per ErrorCode enum
- [x] T076 Verify tenant isolation across all endpoints (no cross-tenant data leakage)
- [x] T077 Run quickstart.md validation against running API

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1) - Agents**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1) - Rules**: Can start after Foundational (Phase 2) - Requires agents to exist but independently testable
- **User Story 3 (P2) - Scenarios**: Can start after Foundational (Phase 2) - Requires agents to exist but independently testable
- **User Story 4 (P2) - Templates**: Can start after Foundational (Phase 2) - Requires agents to exist but independently testable
- **User Story 5 (P3) - Variables**: Can start after Foundational (Phase 2) - Requires agents to exist but independently testable
- **User Story 6 (P3) - Tools**: Can start after Foundational (Phase 2) - Requires agents to exist but independently testable
- **User Story 7 (P2) - Publishing**: Depends on US1 (Agents) - publishing requires an agent with configuration

### Within Each User Story

- Models before services (where applicable)
- Services before endpoints
- List endpoint before single-item endpoints
- Create before update/delete
- Core implementation before tenant scoping verification
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Request/response models marked [P] within a story can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: Foundational Phase

```bash
# Launch all parallelizable foundational tasks together:
Task: "Create ToolActivation model in soldier/alignment/models/tool_activation.py"
Task: "Create PublishJob and PublishStage models in soldier/alignment/models/publish.py"
Task: "Create async embedding service using BackgroundTasks in soldier/api/services/embedding.py"
Task: "Create publish job orchestration service in soldier/api/services/publish.py"
```

## Parallel Example: User Story 2 (Rules)

```bash
# Launch all request/response models together:
Task: "Create RuleCreate and RuleUpdate request models in soldier/api/models/crud.py"
Task: "Create RuleResponse model in soldier/api/models/crud.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 - Agent Management
4. Complete Phase 4: User Story 2 - Rule Management
5. **STOP and VALIDATE**: Test agents and rules independently
6. Deploy/demo if ready - this is a functional MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (Agents) → Test independently → Deploy/Demo
3. Add User Story 2 (Rules) → Test independently → Deploy/Demo (MVP!)
4. Add User Story 7 (Publishing) → Test independently → Deploy/Demo
5. Add User Story 3 (Scenarios) → Test independently → Deploy/Demo
6. Add User Story 4 (Templates) → Test independently → Deploy/Demo
7. Add User Story 5 (Variables) → Test independently → Deploy/Demo
8. Add User Story 6 (Tools) → Test independently → Deploy/Demo
9. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Agents) + User Story 2 (Rules)
   - Developer B: User Story 3 (Scenarios) + User Story 4 (Templates)
   - Developer C: User Story 5 (Variables) + User Story 6 (Tools)
   - Developer D: User Story 7 (Publishing) after US1 complete
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All endpoints require tenant_id from JWT - never allow cross-tenant access
- Embeddings are computed asynchronously - don't block API response
