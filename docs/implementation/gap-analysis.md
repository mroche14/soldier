# Gap Analysis: Codebase vs. Architecture Documentation

> **Generated**: 2025-12-15
> **Purpose**: Exhaustive comparison of what EXISTS in code vs. what SHOULD exist per documentation

---

## Executive Summary

| Dimension | Current State | Target State | Gap Level |
|-----------|---------------|--------------|-----------|
| **Folder Structure** | Partially aligned | `docs/architecture/folder-structure.md` | MEDIUM |
| **ACF (Turn Infrastructure)** | Partial/Scattered | `docs/acf/` | HIGH |
| **FOCAL Brain** | Mostly complete | `docs/focal_brain/` | LOW |
| **Stores** | Complete | `docs/design/decisions/001-storage-choice.md` | LOW |
| **Providers** | Complete | Provider docs | LOW |
| **API Layer** | Complete | `docs/architecture/api-layer.md` | LOW |
| **Terminology** | Mixed old/new | Standardized per V6 | MEDIUM |

---

## 1. Folder Structure Gap Analysis

### Current Structure (Actual)

```
ruche/                           # ✓ Renamed from focal/
├── alignment/                   # ✗ Should be brains/focal/ per docs
│   ├── context/                 # → brains/focal/phases/
│   ├── customer/                # → brains/focal/phases/
│   ├── enforcement/             # → brains/focal/phases/
│   ├── execution/               # → brains/focal/phases/
│   ├── filtering/               # → brains/focal/phases/
│   ├── generation/              # → brains/focal/phases/
│   ├── loaders/                 # → brains/focal/loaders/
│   ├── migration/               # → brains/focal/migration/
│   ├── models/                  # → brains/focal/models/
│   ├── orchestration/           # → brains/focal/orchestration/
│   ├── planning/                # → brains/focal/planning/
│   ├── retrieval/               # → brains/focal/retrieval/
│   ├── stores/                  # → infrastructure/stores/config/
│   └── engine.py                # → brains/focal/engine.py
├── api/                         # ✓ Correct location
├── asa/                         # ✓ Correct location
├── audit/                       # → infrastructure/stores/audit/
├── brains/                      # ✓ Exists but incomplete
│   ├── focal/                   # Has pipeline.py but duplicates alignment/
│   └── protocol.py              # ✓ Brain ABC
├── client/                      # ✓ Correct location
├── config/                      # ✓ Correct location
├── conversation/                # → infrastructure/stores/session/
├── customer_data/               # → domain/interlocutor/ + infrastructure/stores/interlocutor/
├── db/                          # → infrastructure/db/
├── domain/                      # ✓ Exists but incomplete
├── infrastructure/              # ✓ Exists, needs consolidation
├── jobs/                        # → infrastructure/jobs/
├── memory/                      # Split: domain/memory/ + infrastructure/stores/memory/
├── observability/               # ✓ Correct location
├── providers/                   # → infrastructure/providers/ (duplicate exists)
├── runtime/                     # ✓ Correct - ACF, AgentRuntime, Agenda
├── utils/                       # ✓ Correct location
└── vector/                      # → infrastructure/stores/vector/
```

### Target Structure (Per Documentation)

```
ruche/
├── api/                         # HTTP/gRPC/MCP interfaces
│   ├── routes/
│   ├── models/
│   ├── middleware/
│   ├── grpc/
│   └── mcp/
├── brains/                      # Brain implementations
│   ├── protocol.py              # Brain ABC
│   └── focal/                   # FOCAL alignment brain
│       ├── engine.py            # AlignmentEngine
│       ├── phases/              # P1-P11 implementations
│       ├── models/              # FOCAL-specific models
│       ├── migration/           # Scenario migration
│       ├── prompts/             # Jinja2 templates
│       └── stores/              # FOCAL-specific stores (ConfigStore)
├── runtime/                     # Conversation infrastructure (ACF)
│   ├── acf/                     # Agent Conversation Fabric
│   ├── agent/                   # AgentRuntime
│   └── agenda/                  # Proactive follow-up
├── domain/                      # Pure domain models (no infrastructure)
│   ├── interlocutor/            # InterlocutorDataField, VariableEntry
│   ├── rules/                   # Rule, MatchedRule
│   ├── scenarios/               # Scenario, ScenarioStep
│   ├── memory/                  # Episode, Entity, Relationship
│   └── glossary.py
├── infrastructure/              # All external dependencies
│   ├── stores/                  # Storage implementations
│   │   ├── config/              # ConfigStore (Postgres, InMemory)
│   │   ├── session/             # SessionStore (Redis, InMemory)
│   │   ├── memory/              # MemoryStore (Postgres+pgvector, Neo4j)
│   │   ├── audit/               # AuditStore (Postgres, TimescaleDB)
│   │   ├── interlocutor/        # InterlocutorDataStore (Postgres, cached)
│   │   └── vector/              # VectorStore (PGVector, Qdrant)
│   ├── providers/               # AI providers
│   │   ├── llm/                 # LLMExecutor (Agno-backed)
│   │   ├── embedding/           # EmbeddingProvider implementations
│   │   └── rerank/              # RerankProvider implementations
│   ├── toolbox/                 # Tool execution
│   ├── channels/                # Channel adapters
│   ├── db/                      # Database migrations, pooling
│   └── jobs/                    # Background workflows (Hatchet)
├── asa/                         # Agent Setter Agent (validation)
├── config/                      # Configuration loading
│   ├── loader.py
│   ├── settings.py
│   └── models/
├── observability/               # Logging, tracing, metrics
├── client/                      # SDK client
└── utils/                       # Utilities
```

### Structural Changes Required

| Current Path | Target Path | Change Type |
|--------------|-------------|-------------|
| `alignment/` | `brains/focal/` | MOVE + REORGANIZE |
| `alignment/stores/` | `brains/focal/stores/` OR `infrastructure/stores/config/` | DECISION NEEDED |
| `audit/` | `infrastructure/stores/audit/` | MOVE |
| `conversation/` | `infrastructure/stores/session/` | MOVE |
| `customer_data/` | Split to `domain/interlocutor/` + `infrastructure/stores/interlocutor/` | SPLIT |
| `memory/` | Split to `domain/memory/` + `infrastructure/stores/memory/` | SPLIT |
| `providers/` (root) | `infrastructure/providers/` | MOVE (dedupe with existing) |
| `db/` | `infrastructure/db/` | MOVE |
| `jobs/` | `infrastructure/jobs/` | MOVE |
| `vector/` | `infrastructure/stores/vector/` | MOVE |
| `brains/focal/pipeline.py` | Merge with `alignment/engine.py` | MERGE (see duplication) |

---

## 2. Module Duplication Analysis

### Critical Duplications Found

| Module | Location 1 | Location 2 | Resolution |
|--------|------------|------------|------------|
| **FOCAL Pipeline** | `brains/focal/pipeline.py` (2097 lines) | `alignment/engine.py` (2078 lines) | CONSOLIDATE - They appear to be the same code |
| **Providers** | `providers/` | `infrastructure/providers/` | CONSOLIDATE to infrastructure/ |
| **Memory Models** | `memory/models/` | `domain/memory/` | CONSOLIDATE to domain/ |
| **Interlocutor Models** | `customer_data/models.py` | `domain/interlocutor/` | CONSOLIDATE to domain/ |

### Duplication Details

#### FOCAL Pipeline vs Alignment Engine
- `brains/focal/pipeline.py`: 2097 lines
- `alignment/engine.py`: 2078 lines
- **Status**: Need to verify if these are the same or different implementations
- **Risk**: HIGH - Could be maintaining two versions of the same logic

#### Providers Duplication
- `ruche/providers/` - Appears to be backward compatibility layer
- `ruche/infrastructure/providers/` - Actual implementations
- **Resolution**: Keep infrastructure/, deprecate root providers/

---

## 3. ACF Implementation Gap

### Documentation Says (docs/acf/)

The ACF layer should provide:

| Component | Documented | Exists in Code? | Status |
|-----------|------------|-----------------|--------|
| **LogicalTurn model** | Yes | Partial | `runtime/acf/` has some |
| **Session Mutex** | Yes | Partial | Hatchet-based? |
| **TurnManager** | Yes | Yes | `runtime/acf/turn_manager.py` |
| **Adaptive Accumulation** | Yes | ? | Need to verify |
| **Supersede Coordination** | Yes | ? | Need to verify |
| **Hatchet Workflow** | Yes | Partial | `jobs/workflows/` |
| **FabricTurnContext** | Yes | ? | Need to verify |
| **AgentRuntime** | Yes | Yes | `runtime/agent/` |
| **Toolbox** | Yes | Yes | `infrastructure/toolbox/` |

### ACF Files Found

```
ruche/runtime/
├── acf/                         # 8 files
│   ├── __init__.py
│   ├── turn_manager.py
│   ├── accumulator.py
│   ├── mutex.py
│   └── ...
├── agent/                       # 4 files
│   ├── __init__.py
│   ├── runtime.py
│   └── context.py
└── agenda/                      # 3 files
    ├── __init__.py
    ├── scheduler.py
    └── workflow.py
```

### ACF Gap Assessment

**IMPLEMENTATION_PLAN.md Phase 6.5 Status**:
- [x] Core models exist
- [ ] LogicalTurnWorkflow (Hatchet) - UNCLEAR
- [ ] Three-layer idempotency - PARTIAL
- [ ] Unit tests - NEED VERIFICATION

---

## 4. FOCAL Brain Implementation Status

### Phase Completion (from IMPLEMENTATION_PLAN.md)

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| P1 | Identification & Context Loading | ✅ DONE | `alignment/loaders/` |
| P2 | Situational Sensor | ✅ DONE | `alignment/context/` |
| P3 | Interlocutor Data Update | ✅ DONE | `customer_data/` |
| P4 | Retrieval & Selection | ✅ DONE | `alignment/retrieval/` |
| P5 | Rule Selection & Filtering | ✅ DONE | `alignment/filtering/` |
| P6 | Scenario Orchestration | ✅ DONE | `alignment/orchestration/` |
| P7 | Tool Execution | ✅ DONE | `alignment/execution/` |
| P8 | Response Planning | ✅ DONE | `alignment/planning/` |
| P9 | Generation | ✅ DONE | `alignment/generation/` |
| P10 | Enforcement & Guardrails | 🔶 PARTIAL | Two-lane not wired |
| P11 | Persistence, Audit & Output | ✅ DONE | `audit/` |

### Enforcement Gap (P10)

Per `docs/focal_brain/implementation/phase-10-enforcement-checklist.md`:

- [x] `DeterministicEnforcer` exists
- [x] `SubjectiveEnforcer` exists
- [x] `simpleeval` integrated
- [ ] Two-lane dispatch NOT WIRED in `EnforcementValidator.validate()`
- [ ] GLOBAL hard constraints always-enforce NOT IMPLEMENTED

---

## 5. Store Implementation Status

### Per ADR-001 + ADR-003

| Store | Interface | InMemory | Postgres | Redis | Other |
|-------|-----------|----------|----------|-------|-------|
| **ConfigStore** | ✅ | ✅ | ✅ | — | — |
| **SessionStore** | ✅ | ✅ | — | ✅ | MongoDB, DynamoDB |
| **MemoryStore** | ✅ | ✅ | ✅ (pgvector) | — | Neo4j, MongoDB |
| **AuditStore** | ✅ | ✅ | ✅ | — | MongoDB, ClickHouse, TimescaleDB |
| **InterlocutorDataStore** | ✅ | ✅ | ✅ | ✅ (cache) | — |
| **VectorStore** | ✅ | ✅ | ✅ (PGVector) | — | Qdrant |

**Status**: All stores COMPLETE

---

## 6. Provider Implementation Status

### Per Documentation

| Provider | Interface | Mock | OpenAI | Cohere | Other |
|----------|-----------|------|--------|--------|-------|
| **LLMExecutor** | ✅ (Agno) | ✅ | Via Agno | Via Agno | Anthropic, OpenRouter |
| **EmbeddingProvider** | ✅ | ✅ | ✅ | ✅ | Jina, Voyage, SentenceTransformers |
| **RerankProvider** | ✅ | ✅ | — | ✅ | Voyage, Jina, CrossEncoder |

**Status**: All providers COMPLETE

---

## 7. API Implementation Status

| Endpoint Category | Status | Notes |
|-------------------|--------|-------|
| `/v1/chat` | ✅ | Chat processing |
| `/v1/chat/stream` | ✅ | SSE streaming |
| `/v1/sessions` | ✅ | Session management |
| `/v1/agents` | ✅ | CRUD |
| `/v1/rules` | ✅ | CRUD |
| `/v1/scenarios` | ✅ | CRUD |
| `/v1/templates` | ✅ | CRUD |
| `/v1/variables` | ✅ | CRUD |
| `/v1/tools` | ✅ | Tool management |
| `/v1/migrations` | ✅ | Scenario migration |
| `/health` | ✅ | Health check |
| `/metrics` | ✅ | Prometheus |

**Status**: REST API COMPLETE

---

## 8. Terminology Alignment

### Current vs. Target (per V6)

| Term | Old (in code) | New (target) | Files Affected |
|------|---------------|--------------|----------------|
| `brain.run()` | Some files | `brain.think()` | ~20 files |
| `run_pipeline` | Some files | `run_agent` | Hatchet workflows |
| `customer_id` | Some files | `interlocutor_id` | Session keys |
| `CustomerDataStore` | Many files | `InterlocutorDataStore` | 50+ files |
| `CognitivePipeline` | Old docs | `Brain` | Docs only |
| `focal/` | IMPLEMENTATION_PLAN | `ruche/` | 1 file |

---

## 9. Test Coverage Analysis

### Current Test Structure

```
tests/
├── unit/                        # 80 files
│   ├── alignment/               # 22 files
│   ├── api/                     # 11 files
│   ├── config/                  # 3 files
│   ├── conversation/            # 3 files
│   ├── customer_data/           # 5 files
│   ├── memory/                  # 5 files
│   ├── audit/                   # 2 files
│   ├── observability/           # 3 files
│   ├── providers/               # 3 files
│   ├── vector/                  # 1 file
│   └── jobs/                    # 1 file
├── integration/                 # 25 files
├── contract/                    # 2 files
├── e2e/                         # 2 files
└── performance/                 # 2 files
```

### Test Coverage Gaps

| Area | Current | Target | Gap |
|------|---------|--------|-----|
| Unit tests | 80 files | — | GOOD |
| ACF unit tests | ? | Per Phase 6.5 | VERIFY |
| Enforcement wiring tests | MISSING | Per P10 checklist | ADD |
| Integration tests | 25 files | — | GOOD |
| E2E tests | 2 files | 5+ per docs | ADD |

---

## 10. Priority Ranking

### HIGH Priority (Blocking Production)

1. **Consolidate FOCAL code duplication** - `brains/focal/` vs `alignment/`
2. **Wire enforcement two-lane** - P10 completion
3. **Verify ACF implementation** - Phase 6.5 completeness

### MEDIUM Priority (Structural Health)

4. **Folder restructure** - Align with target structure
5. **Providers deduplication** - Single location
6. **Terminology standardization** - Interlocutor naming

### LOW Priority (Polish)

7. **Move stores under infrastructure/**
8. **Domain model consolidation**
9. **Test coverage expansion**

---

## Questions Requiring Human Decision

See `questions.md` for detailed questions that need resolution before implementation planning can proceed.
