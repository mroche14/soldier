# Tasks: API Layer - Core

**Input**: Design documents from `/specs/006-api-layer-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included as they follow the existing project testing strategy.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `soldier/api/` (existing structure)
- **Tests**: `tests/unit/api/`, `tests/integration/api/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project dependencies and basic API structure

- [x] T001 Add FastAPI dependencies to pyproject.toml (fastapi, uvicorn, python-jose, sse-starlette, httpx)
- [x] T002 [P] Create soldier/api/models/context.py with TenantContext, RateLimitResult, RequestContext models
- [x] T003 [P] Create soldier/api/models/errors.py with ErrorCode enum and ErrorResponse, ErrorBody, ErrorDetail models
- [x] T004 [P] Create soldier/api/exceptions.py with SoldierAPIError, AgentNotFoundError, SessionNotFoundError, RateLimitExceededError

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement FastAPI application factory in soldier/api/app.py with create_app() function
- [x] T006 [P] Implement JWT authentication dependency in soldier/api/middleware/auth.py
- [x] T007 [P] Implement request context binding middleware in soldier/api/middleware/context.py
- [x] T008 [P] Create soldier/api/dependencies.py with dependency injection for stores and providers
- [x] T009 Implement global exception handlers in soldier/api/app.py for all SoldierAPIError types
- [x] T010 [P] Add OpenTelemetry FastAPI instrumentation in soldier/api/app.py
- [x] T011 Create soldier/api/routes/__init__.py with router registration helper

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Process Chat Message (Priority: P1) 🎯 MVP

**Goal**: Enable upstream services to send messages and receive structured responses from the alignment engine

**Independent Test**: POST /v1/chat with valid request returns response with session_id, turn_id, and response text

### Tests for User Story 1

- [x] T012 [P] [US1] Create tests/unit/api/test_chat_models.py with ChatRequest, ChatResponse validation tests
- [x] T013 [P] [US1] Create tests/unit/api/test_chat.py with mock AlignmentEngine response tests

### Implementation for User Story 1

- [x] T014 [P] [US1] Create soldier/api/models/chat.py with ChatRequest, ChatResponse, ScenarioState models
- [x] T015 [US1] Implement POST /v1/chat endpoint in soldier/api/routes/chat.py
- [x] T016 [US1] Add session creation/lookup logic in chat route (create if session_id not provided)
- [x] T017 [US1] Map AlignmentResult to ChatResponse in soldier/api/routes/chat.py
- [x] T018 [US1] Add idempotency support via Idempotency-Key header in soldier/api/middleware/idempotency.py
- [x] T019 [US1] Register chat router in soldier/api/app.py

**Checkpoint**: POST /v1/chat should be fully functional and return structured responses

---

## Phase 4: User Story 2 - Stream Chat Response (Priority: P1)

**Goal**: Enable streaming responses via Server-Sent Events for responsive UX

**Independent Test**: POST /v1/chat/stream returns SSE stream with token events followed by done event

### Tests for User Story 2

- [x] T020 [P] [US2] Create tests/unit/api/test_streaming.py with StreamEvent model tests
- [x] T021 [P] [US2] Create tests/integration/api/test_chat_stream.py with SSE stream verification

### Implementation for User Story 2

- [x] T022 [P] [US2] Add TokenEvent, DoneEvent, ErrorEvent models to soldier/api/models/chat.py
- [x] T023 [US2] Implement POST /v1/chat/stream endpoint in soldier/api/routes/chat.py using sse-starlette
- [x] T024 [US2] Create async generator for streaming AlignmentEngine responses
- [x] T025 [US2] Handle client disconnection gracefully in stream endpoint
- [x] T026 [US2] Add error event handling for streaming failures

**Checkpoint**: POST /v1/chat/stream should deliver incremental tokens via SSE

---

## Phase 5: User Story 3 - Health Check and Metrics (Priority: P2)

**Goal**: Enable operations teams to monitor service health and collect Prometheus metrics

**Independent Test**: GET /health returns status with component health, GET /metrics returns Prometheus format

### Tests for User Story 3

- [x] T027 [P] [US3] Create tests/unit/api/test_health.py with health endpoint tests

### Implementation for User Story 3

- [x] T028 [P] [US3] Create soldier/api/models/health.py with HealthResponse, ComponentHealth models
- [x] T029 [US3] Implement GET /health endpoint in soldier/api/routes/health.py with component checks
- [x] T030 [US3] Implement GET /metrics endpoint in soldier/api/routes/health.py exposing Prometheus metrics
- [x] T031 [US3] Add health checks for ConfigStore, SessionStore, AuditStore availability
- [x] T032 [US3] Register health router in soldier/api/app.py

**Checkpoint**: /health and /metrics endpoints should return appropriate responses

---

## Phase 6: User Story 4 - Session Management (Priority: P2)

**Goal**: Enable upstream services to retrieve session state, view history, and end sessions

**Independent Test**: GET /v1/sessions/{id} returns session state, DELETE ends session

### Tests for User Story 4

- [x] T033 [P] [US4] Create tests/unit/api/test_sessions.py with session endpoint tests
- [x] T034 [P] [US4] Create tests/unit/api/test_session_models.py with SessionResponse, TurnResponse tests

### Implementation for User Story 4

- [x] T035 [P] [US4] Create soldier/api/models/session.py with SessionResponse, TurnResponse, TurnListResponse models
- [x] T036 [US4] Implement GET /v1/sessions/{session_id} in soldier/api/routes/sessions.py
- [x] T037 [US4] Implement DELETE /v1/sessions/{session_id} in soldier/api/routes/sessions.py
- [x] T038 [US4] Implement GET /v1/sessions/{session_id}/turns with pagination in soldier/api/routes/sessions.py
- [x] T039 [US4] Map Session model to SessionResponse, TurnRecord to TurnResponse
- [x] T040 [US4] Register sessions router in soldier/api/app.py

**Checkpoint**: Session management endpoints should be fully functional

---

## Phase 7: User Story 5 - Rate Limiting (Priority: P3)

**Goal**: Enforce per-tenant rate limits to prevent abuse and ensure fair resource allocation

**Independent Test**: Requests exceeding rate limit return 429 with X-RateLimit-* headers

### Tests for User Story 5

- [x] T041 [P] [US5] Create tests/unit/api/test_rate_limit.py with rate limiter logic tests
- [x] T042 [P] [US5] Create tests/integration/api/test_rate_limiting.py with limit enforcement tests

### Implementation for User Story 5

- [x] T043 [US5] Implement SlidingWindowRateLimiter in soldier/api/middleware/rate_limit.py
- [x] T044 [US5] Add Redis-backed rate limit storage with in-memory fallback
- [x] T045 [US5] Implement tier-based limits (Free: 60/min, Pro: 600/min, Enterprise: custom)
- [x] T046 [US5] Add X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset response headers
- [x] T047 [US5] Integrate rate limiting middleware in soldier/api/app.py
- [x] T048 [US5] Handle RateLimitExceededError with 429 response and retry-after header

**Checkpoint**: Rate limiting should enforce per-tenant limits with appropriate headers

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T049 [P] Create tests/integration/api/test_chat_flow.py with full end-to-end chat flow test
- [x] T050 [P] Create tests/unit/api/test_context.py to verify context binding (tenant_id, trace_id in logs)
- [x] T051 [P] Create tests/unit/api/test_tracing.py to verify OpenTelemetry trace propagation
- [x] T052 [P] Update soldier/api/models/__init__.py to export all models
- [x] T053 [P] Update soldier/api/routes/__init__.py to export all routers
- [x] T054 [P] Update soldier/api/middleware/__init__.py to export all middleware
- [x] T055 Run quickstart.md validation - verify all documented commands work
- [x] T056 Validate OpenAPI spec matches implementation at /docs endpoint

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority but US2 depends on US1 chat route structure
  - US3 and US4 are P2 and can run in parallel
  - US5 is P3 and can start after Foundational
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Depends on US1 chat models and route structure being in place
- **User Story 3 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 5 (P3)**: Can start after Foundational - No dependencies on other stories

### Within Each User Story

- Tests should be written first to understand expected behavior
- Models before routes
- Core implementation before edge case handling
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational completes:
  - US1 can start immediately
  - US3, US4, US5 can all start in parallel (if team capacity allows)
- Within each story, tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create tests/unit/api/test_chat_models.py with ChatRequest, ChatResponse validation tests"
Task: "Create tests/unit/api/test_chat.py with mock AlignmentEngine response tests"

# Then launch model creation:
Task: "Create soldier/api/models/chat.py with ChatRequest, ChatResponse, ScenarioState models"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Process Chat Message)
4. **STOP and VALIDATE**: Test POST /v1/chat independently
5. Deploy/demo if ready - basic chat functionality is usable

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy (MVP! - basic chat works)
3. Add User Story 2 → Test independently → Deploy (streaming added)
4. Add User Story 3 → Test independently → Deploy (health/metrics added)
5. Add User Story 4 → Test independently → Deploy (session management added)
6. Add User Story 5 → Test independently → Deploy (rate limiting added)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Foundational phase:
- Developer A: User Story 1 → User Story 2 (has dependency)
- Developer B: User Story 3 (health/metrics)
- Developer C: User Story 4 (sessions)
- Developer D: User Story 5 (rate limiting)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Existing stub files in soldier/api/ should be replaced with implementations
