# Implementation Checklist

> **Last Updated**: 2025-12-16
> **Overall Progress**: 45/46 tasks complete (98%)
> **Remaining**: 5I (Test Coverage)

---

## Quick Status

| Wave | Complete | Total | Progress |
|------|----------|-------|----------|
| Wave 1: Foundation | 13/13 | 13 | **100%** |
| Wave 2: Infrastructure | 10/10 | 10 | **100%** |
| Wave 3: Integration | 7/7 | 7 | **100%** |
| Wave 4: API & Runtime | 7/7 | 7 | **100%** |
| Wave 5: Advanced | 8/9 | 9 | **89%** |
| **TOTAL** | **45/46** | **46** | **98%** |

---

## Wave 1: Foundation & Cleanup (13/13) ✅

- [x] **1A**: FOCAL Brain Consolidation - `engine.py` deleted, `pipeline.py` canonical
- [x] **1B**: Missing Database Tables - Migrations 013, 014, 015 created
- [x] **1C**: Logging Middleware - `middleware.py` 96 lines
- [x] **1D**: Observability Config - `default.toml` has [observability] section
- [x] **1E**: Model Consolidation - InterlocutorDataStore in domain/
- [x] **1F**: OpenAI Embedding Provider - `openai.py` 100+ lines
- [x] **1G**: Cohere Embedding Provider - `cohere.py` 80+ lines
- [x] **1H**: Cohere Rerank Provider - `cohere.py` 50+ lines
- [x] **1I**: InterlocutorChannelPresence - `channel_presence.py` created
- [x] **1J**: History Trimming - `updater.py` lines 213-215
- [x] **1K**: Remove Duplicate ABCs - MemoryStore, InterlocutorDataStore consolidated
- [x] **1L**: Clean Up Empty Stub Files - Documented in `stub-files.md`
- [x] **1M**: Document Client SDK - `client-sdk.md` 822 lines

---

## Wave 2: Core Infrastructure (10/10) ✅

- [x] **2A**: FabricTurnContext Protocol - Protocol + FabricTurnContextImpl
- [x] **2B**: AgentContext Rewrite - Has agent, brain, toolbox, channel_bindings
- [x] **2C**: AgentTurnContext - Wraps FabricTurnContext + AgentContext
- [x] **2D**: Brain Protocol - `protocol.py` 68 lines
- [x] **2E**: Toolbox Implementation - 4 files, 830+ lines
- [x] **2F**: ChannelPolicy Model - `models.py` with SupersedeMode enum
- [x] **2G**: Complete Template Model - `render()` and `variables_used`
- [x] **2H**: Type TurnContext - Session, InterlocutorDataStore types
- [x] **2I**: Turn Gateway (CRITICAL) - `gateway.py` 198 lines
- [x] **2J**: Configuration Hierarchy - Layer getters documented with tests

---

## Wave 3: Integration (7/7) ✅

- [x] **3A**: Workflow AgentRuntime Integration - brain.think() called
- [x] **3B**: Tool Execution Integration (P7.1-P7.7) - ToolExecutionOrchestrator
- [x] **3C**: Scenario Contributions (P6.4) - `extract_scenario_contributions()`
- [x] **3D**: LLM Semantic Categories (P9.4) - `GenerationResult.llm_categories`
- [x] **3E**: Relationship Expansion (P5.3) - RelationshipExpander in pipeline
- [x] **3F**: Scope/Lifecycle Pre-Filter (P5.1) - ScopePreFilter called
- [x] **3G**: Language Validation (P2.6) - `_validate_language()`

---

## Wave 4: API & Runtime (7/7) ✅

- [x] **4A**: Chat Endpoint - `POST /v1/chat` in turns.py
- [x] **4B**: Chat Streaming (SSE) - `POST /v1/chat/stream`
- [x] **4C**: Memory Endpoints - episodes, search, entities
- [x] **4D**: EventRouter - `event_router.py` with pattern matching
- [x] **4E**: IdempotencyCache - 3-tier cache (API/Beat/Tool)
- [x] **4F**: Adaptive Accumulation - Channel-aware timing
- [x] **4G**: ACF Event Emission - 17 event types

---

## Wave 5: Advanced Features (8/9) 🔶

- [x] **5A**: Webhook System - 4 files, HMAC signing
- [x] **5B**: gRPC Services - Proto files + 3 implementations
- [x] **5C**: ChannelGateway - Gateway + Adapter pattern
- [x] **5D**: Row Level Security - Migration 016
- [x] **5E**: PostgreSQL Session Persistence - Migration 017
- [x] **5F**: Regeneration Loop (P10.8) - Retry with violation feedback
- [x] **5G**: Memory Ingestion (P11.5) - `_ingest_memory()` in pipeline
- [x] **5H**: Migration Module Tests - 2,193 lines, 64 test functions
- [ ] **5I**: Test Coverage to 85% - **Currently 59.2%, target 85%**

---

## Remaining Work

### 5I: Test Coverage Improvement

**Current**: 59.2% | **Target**: 85% | **Gap**: 25.8%

**Priority Areas** (production code, not test fixtures):
1. **ACF Workflow** (19.1% coverage) - Stateless pod orchestration
2. **PostgreSQL Stores** (12-13% coverage) - Production backends
3. **FOCAL Brain Phases** (33-70% coverage) - Core business logic

**Sub-tasks**:
- [x] ACF Workflow tests (`ruche/runtime/acf/workflow.py`) - 73.2% coverage
- [x] ACF Commit Point tests (`ruche/runtime/acf/commit_point.py`) - 100% coverage
- [x] ACF Supersede tests (`ruche/runtime/acf/supersede.py`) - 95.7% coverage
- [x] ACF Mutex tests (`ruche/runtime/acf/mutex.py`) - 95.1% coverage
- [x] FOCAL tool_execution_orchestrator tests - 21 tests
- [x] FOCAL deterministic_enforcer tests - 48 tests
- [x] FOCAL scenario_filter tests - 28 tests
- [x] PostgreSQL ConfigStore tests - 8 integration tests (existing)
- [x] PostgreSQL InterlocutorDataStore tests - 14 integration tests (existing)
- [x] PostgreSQL MemoryStore tests - 15 integration tests (existing)

---

## Test Status

| Metric | Value |
|--------|-------|
| Unit Tests Passing | 1894 |
| Integration Tests Passing | 37 (PostgreSQL) |
| Total Tests | 2092 |
| Coverage | ~55% (improving) |
| Target Coverage | 85% |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `IMPLEMENTATION_WAVES.md` | Detailed task descriptions |
| `PARALLEL_WORK_TASKS.md` | Parallelizable task breakdown |
| `stub-files.md` | Documentation of intentional stub files |
| `tracking/overview.md` | Architecture refactoring WP tracking |

---

## Additional Completions (Beyond Waves)

### Goal System Removal ✅
Removed all Goal/GoalStore references (2025-12-16):
- Renamed `09-agenda-goals.md` → `09-agenda.md`
- Removed Goal, GoalStatus, GoalType, GoalStore, GoalChecker
- Updated all doc references
- Agenda/Task system preserved

### Hatchet Worker Entrypoint ✅
Created ACF worker for self-hosted Hatchet (2025-12-16):
- New: `ruche/runtime/acf/worker.py` (~200 lines)
- New: `ruche/runtime/acf/README.md` (usage docs)
- Added CLI: `ruche-worker` in pyproject.toml
- Added JobsConfig to Settings
- Start with: `uv run ruche-worker`

### Template Model Fix ✅
Fixed model-database field mismatch (2025-12-16):
- Changed Template.text → Template.content (matches DB schema)
- Updated 4 source files, 5 test files
- PostgreSQL template methods were already implemented

### Expression Evaluator ✅
Implemented domain-level expression evaluation (2025-12-16):
- New: `ruche/domain/rules/expressions.py` (full implementation)
- New: `tests/unit/domain/test_expressions.py` (25 tests)
- DeterministicEnforcer now delegates to domain layer
- 85 total expression tests passing

### Brain Terminology Fix ✅
Renamed PipelineFactory → BrainFactory (2025-12-16):
- `ruche/runtime/brain/factory.py` - Class rename
- `ruche/runtime/agent/runtime.py` - Attribute rename
- `pipeline_type` → `brain_type` everywhere
- 5 source files, 6 docs updated

### PostgreSQL Store Methods ✅
Implemented 11 NotImplementedError methods (2025-12-16):
- Intents: get_intent, get_intents, save_intent, delete_intent
- Rule relationships: get/save/delete_rule_relationship
- Glossary: get_glossary_items, save_glossary_item
- Interlocutor fields: get/save_interlocutor_data_fields

### Agenda System ✅
Made scheduler + workflow real (2025-12-16):
- `ruche/runtime/agenda/scheduler.py` - Background polling, task execution
- `ruche/runtime/agenda/workflow.py` - Task type routing, brain integration
- `ruche/runtime/agenda/store.py` - TaskStore interface
- `ruche/runtime/agenda/stores/inmemory.py` - InMemory implementation
- 14 tests passing

### Domain Layer Cleanup ✅
Moved Task models to domain/ (2025-12-16):
- New: `ruche/domain/agenda/models.py`
- Deleted: `ruche/runtime/agenda/models.py`
- Backward compatibility via re-exports

### Channel Bindings/Policies ✅
Implemented in AgentRuntime (2025-12-16):
- `ChannelPolicy` model expanded (SupersedeMode, capabilities)
- `DEFAULT_CHANNEL_POLICIES` for 5 channels
- ConfigStore interface: get_channel_bindings, get_channel_policies
- AgentRuntime placeholders → real implementations

### Worker Bootstrap Wiring ✅
Connected stores to worker (2025-12-16):
- SessionStore: Redis with InMemory fallback
- AuditStore: InMemory (PostgreSQL has circular import)
- AgentRuntime: Full wiring with BrainFactory
- `uv run ruche-worker` now creates real components

---

## Activity Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2025-12-15 | Waves 1-4 | Complete | Initial implementation |
| 2025-12-15 | 5A-5H | Complete | Advanced features |
| 2025-12-16 | Field resolver tests | Fixed | Added interlocutor_id to Session |
| 2025-12-16 | Model consolidation | Complete | 502 lines removed |
| 2025-12-16 | Stub files documentation | Complete | stub-files.md created |
| 2025-12-16 | 5I: ACF tests | **Complete** | 94 tests: workflow, mutex, commit_point, supersede |
| 2025-12-16 | Tracking system | **Created** | IMPLEMENTATION_CHECKLIST.md |
| 2025-12-16 | 5I: FOCAL tests | **Complete** | 97 tests: orchestrator, enforcer, scenario_filter |
| 2025-12-16 | 5I: PostgreSQL tests | **Verified** | 37 integration tests already exist and pass |
| 2025-12-16 | Goal system removal | **Complete** | Removed Goal/GoalStore, kept Agenda/Task |
| 2025-12-16 | Hatchet worker | **Complete** | worker.py + CLI entrypoint |
| 2025-12-16 | Template model fix | **Complete** | text→content field alignment |
| 2025-12-16 | Expression evaluator | **Complete** | Domain-level implementation + 25 tests |
| 2025-12-16 | Brain terminology | **Complete** | PipelineFactory → BrainFactory |
| 2025-12-16 | PostgreSQL stores | **Complete** | 11 methods implemented |
| 2025-12-16 | Agenda system | **Complete** | Scheduler + workflow real |
| 2025-12-16 | Domain cleanup | **Complete** | Task models → domain/agenda/ |
| 2025-12-16 | Channel policies | **Complete** | AgentRuntime now loads real policies |
| 2025-12-16 | Worker wiring | **Complete** | Real stores connected |

---

*This checklist is the quick-reference for implementation status. See IMPLEMENTATION_WAVES.md for detailed descriptions.*
