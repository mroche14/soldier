# Implementation Plan: Alignment Pipeline

**Branch**: `004-alignment-pipeline` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-alignment-pipeline/spec.md`

## Summary

Implement the core alignment pipeline (Phases 6-11) that processes user messages through a multi-step orchestration: context extraction, rule/scenario/memory retrieval with dynamic selection strategies, LLM-based filtering, tool execution, response generation with template support, and enforcement validation. This is the "brain" of the Focal cognitive engine.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pydantic, pydantic-settings, structlog, prometheus-client, opentelemetry-sdk (existing); numpy, scipy, scikit-learn (new for selection strategies)
**Storage**: In-memory stores (existing); ConfigStore, MemoryStore, SessionStore, AuditStore interfaces already defined
**Testing**: pytest, pytest-asyncio, pytest-cov (existing)
**Target Platform**: Linux server (containerized)
**Project Type**: Single Python package (focal/)
**Performance Goals**: <1s simple message processing, <2s with tools (per SC-001, SC-002)
**Constraints**: 100 concurrent requests (SC-006), zero in-memory state, multi-tenant isolation
**Scale/Scope**: All 6 pipeline phases, 32 functional requirements, 5 selection strategies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **API-first** | PASS | Pipeline is internal; API layer (Phase 13-14) exposes it externally |
| **Zero In-Memory State** | PASS | All state via SessionStore/ConfigStore; no module-level caches |
| **Multi-Tenant Native** | PASS | All operations filter by tenant_id (FR-011, FR-012) |
| **Hot-Reload** | PASS | Config from TOML/stores, not hardcoded (FR-029) |
| **Full Auditability** | PASS | Step timing and metadata logged (FR-030); AuditStore integration (FR-032) |
| **Python 3.11+** | PASS | Already configured in pyproject.toml |
| **uv Package Management** | PASS | Dependencies added via uv add |
| **Pydantic for Models** | PASS | All domain models use Pydantic (existing) |
| **structlog for Logging** | PASS | Observability infrastructure exists |
| **No try/except imports** | PASS | Direct imports only |
| **Four Stores Pattern** | PASS | Using existing ConfigStore, MemoryStore, SessionStore, AuditStore |
| **Interface-First Design** | PASS | ABC interfaces exist; adding SelectionStrategy interface |
| **Provider Model** | PASS | Using existing LLMProvider, EmbeddingProvider, RerankProvider |
| **Dependency Injection** | PASS | Pipeline components receive dependencies via __init__ |
| **Async Everywhere** | PASS | All I/O operations are async |
| **85% Code Coverage** | PENDING | Enforced by CI |
| **Contract Tests** | PASS | Will add SelectionStrategyContract tests |

**Gate Result**: PASS - No constitution violations

## Project Structure

### Documentation (this feature)

```text
specs/004-alignment-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
focal/
├── alignment/
│   ├── retrieval/
│   │   ├── __init__.py              # Exports
│   │   ├── selection.py             # Selection strategies (Phase 6) [NEW]
│   │   ├── rule_retriever.py        # Rule retrieval (Phase 8) [EXPAND]
│   │   ├── scenario_retriever.py    # Scenario retrieval (Phase 8) [EXPAND]
│   │   └── reranker.py              # Reranking (Phase 8) [EXPAND]
│   ├── context/
│   │   ├── __init__.py              # Exports
│   │   ├── extractor.py             # Context extraction (Phase 7) [EXPAND]
│   │   ├── models.py                # Context, UserIntent models [EXPAND]
│   │   └── prompts/                 # Prompt templates [NEW]
│   │       └── extract_intent.txt
│   ├── filtering/
│   │   ├── __init__.py              # Exports
│   │   ├── rule_filter.py           # Rule filtering (Phase 9) [EXPAND]
│   │   ├── scenario_filter.py       # Scenario filtering (Phase 9) [EXPAND]
│   │   └── prompts/
│   │       ├── filter_rules.txt     # [NEW]
│   │       └── evaluate_scenario.txt # [NEW]
│   ├── execution/
│   │   ├── __init__.py              # Exports
│   │   ├── tool_executor.py         # Tool execution (Phase 10) [EXPAND]
│   │   └── variable_resolver.py     # Variable resolution [EXPAND]
│   ├── generation/
│   │   ├── __init__.py              # Exports
│   │   ├── prompt_builder.py        # Prompt assembly (Phase 10) [EXPAND]
│   │   ├── generator.py             # Response generation [EXPAND]
│   │   └── prompts/
│   │       └── system_prompt.txt    # [NEW]
│   ├── enforcement/
│   │   ├── __init__.py              # Exports
│   │   ├── validator.py             # Constraint validation (Phase 10) [EXPAND]
│   │   └── fallback.py              # Fallback handling [EXPAND]
│   ├── engine.py                    # AlignmentEngine orchestrator (Phase 11) [EXPAND]
│   └── result.py                    # AlignmentResult model [NEW]
├── memory/
│   └── retrieval/
│       └── retriever.py             # Memory retrieval (Phase 8) [EXPAND]
└── config/
    └── models/
        └── selection.py             # Selection config (exists) [EXPAND]

tests/
├── unit/
│   └── alignment/
│       ├── retrieval/
│       │   └── test_selection.py    # Selection strategy tests [NEW]
│       ├── context/
│       │   └── test_extractor.py    # Context extraction tests [NEW]
│       ├── filtering/
│       │   ├── test_rule_filter.py  # Rule filter tests [NEW]
│       │   └── test_scenario_filter.py # Scenario filter tests [NEW]
│       ├── execution/
│       │   └── test_tool_executor.py # Tool executor tests [NEW]
│       ├── generation/
│       │   └── test_generator.py    # Generator tests [NEW]
│       └── enforcement/
│           └── test_validator.py    # Validator tests [NEW]
└── integration/
    └── alignment/
        └── test_engine.py           # Full pipeline integration tests [NEW]
```

**Structure Decision**: Follows existing `focal/` package structure with domain-aligned folders. Each pipeline phase maps to a subdirectory under `alignment/`. Test structure mirrors source.

## Task Ordering Rationale

**US4 (Selection Strategies) executes before US1 (MVP)**

Despite US4 being listed as Priority P3 in the spec, it is implemented in Phase 3 (before US1's Phase 4) because:

1. **Dependency**: Selection strategies are a foundational component used by rule retrieval, scenario retrieval, and memory retrieval
2. **No Blocking**: US4 has no external dependencies beyond the foundational models
3. **Enables Parallelism**: Completing US4 first allows US2 (Scenarios), US3 (Tools), and Memory to proceed in parallel with US1 without waiting for selection implementation
4. **Minimal Scope**: US4 is self-contained (13 tasks vs 25 for US1), making it quick to complete

This ordering reflects implementation dependencies, not business priority. US1 remains the MVP for stakeholder demonstration.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
