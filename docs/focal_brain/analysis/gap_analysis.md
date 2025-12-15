# FOCAL Brain: Gap Analysis

> **Generated**: 2024-12-08
> **Status**: STALE. This file is not automatically re-generated; verify against `IMPLEMENTATION_PLAN.md`, `docs/acf/`, and the current `ruche/` code.
> **Reference**: `docs/focal_brain/README.md`
> **Purpose**: Identify implementation gaps between the focal brain specification and the current codebase.

---

## Key Architectural Notes

### Customer Data Architecture

The FOCAL brain specification uses a **two-part customer data architecture**:

> **Note:** Since this analysis was generated, naming has been consolidated in `ruche/domain/interlocutor/` (`CustomerProfile` → `InterlocutorDataStore`, `ProfileField` → `VariableEntry`, etc.). Treat legacy names below as historical references.

| Component | Purpose | Current Implementation |
|-----------|---------|------------------------|
| **InterlocutorDataField** | Schema definition (what fields exist) | `InterlocutorDataField` exists (includes `scope` and `persist`) |
| **InterlocutorDataStore** | Runtime values per customer | `InterlocutorDataStore` exists (loaded as a per-turn snapshot) |
| **VariableEntry** | Per-variable metadata with history | `VariableEntry` exists (includes `history`; no explicit `scope` field) |
| **InterlocutorSchemaMask** | Privacy-safe LLM view | Implemented (`ruche/brains/focal/context/interlocutor_schema_mask.py`) |
| **CandidateVariableInfo** | LLM extraction intermediate | Implemented (`ruche/brains/focal/context/situation_snapshot.py`) |

**Architecture Mismatch**: Customer data is stored persistently, but the brain requires a **runtime per-turn snapshot** that's loaded (P1.5), mutated in-memory (P3.3), and persisted selectively (P11.3).

**What InterlocutorDataStore HAS**:
- `VariableEntry` with value, type, source, confidence, timestamps ✓
- `InterlocutorDataField` with name, type, validation, `scope`, `persist` ✓
- `InterlocutorDataStoreInterface` with CRUD operations ✓
- `VerificationLevel`, `ItemStatus`, `SourceType` enums ✓

**What InterlocutorDataStore is MISSING**:
- Explicit `scope` on `VariableEntry` (currently scope is defined on `InterlocutorDataField` and must be derived at runtime)
- Session-end cleanup for SESSION-scoped variables (or equivalent TTL/expiry semantics)

**Critical Impact**: Phases P1.5, P2.1, P3.1-P3.4, P7.3, P11.3 all depend on this architecture.

**Migration path**:
1. Decide whether `VariableEntry` stores `scope` or derives it from `InterlocutorDataField`
2. Implement session-end cleanup for SESSION scope (if not already handled elsewhere)

---

### LLM Task Configuration Pattern

The spec (Section 5) requires each LLM task to have:
1. Config section in `config/default.toml` under `[brain.{task_name}]`
2. Jinja2 prompt template in `ruche/alignment/{domain}/prompts/{task_name}.jinja2`

| Task | Config | Template | Loader | Status |
|------|--------|----------|--------|--------|
| **Situational Sensor** | ✓ `[brain.situational_sensor]` | ✗ Uses `.txt` | ✗ None | Hardcoded fallback |
| **Rule Filter** | ✓ `[brain.rule_filtering]` | ✗ Uses `.txt` | ✗ None | Hardcoded fallback |
| **Scenario Filter** | ✓ `[brain.scenario_filtering]` | ✗ `.txt` unused | ✗ None | Deterministic only |
| **Response Generation** | ✓ `[brain.generation]` | ✗ Uses `.txt` | ✗ None | `str.format()` |
| **LLM Judge** | ✓ `[brain.enforcement]` | ✗ Missing | ✗ None | **Not implemented** |
| **Entity Extraction** | ✓ Config exists | ✗ Hardcoded | ✗ None | 192-line inline prompt |
| **Summarization** | ✓ Config exists | ✗ Hardcoded | ✗ None | Inline prompts |

**Critical Gaps**:
- **No Jinja2 templates** - all templates use `.txt` with `str.format()` or hardcoded strings
- **No template loader** - no `jinja2.Environment` or `FileSystemLoader`
- **No `LLMTaskContext`** - templates can't access config or turn context
- **Hardcoded prompts** in Python: `entity_extractor.py` (192 lines), `summarizer.py` (5 lines)
- **LLM Judge completely missing** - enforcement only does phrase matching

**File Paths** (current incorrect format):
- `alignment/context/prompts/extract_intent.txt` (should be `.jinja2`)
- `alignment/filtering/prompts/filter_rules.txt` (should be `.jinja2`)
- `alignment/generation/prompts/system_prompt.txt` (should be `.jinja2`)

---

## Executive Summary

| Phase | Description | Status | Coverage |
|-------|-------------|--------|----------|
| **P1** | Identification & Context Loading | **IMPLEMENTED** | 85% |
| **P2** | Situational Sensor | **NOT IMPLEMENTED** | 15% |
| **P3** | Customer Data Update | **NOT IMPLEMENTED** | 15% |
| **P4** | Retrieval & Selection | **MOSTLY IMPLEMENTED** | 75% |
| **P5** | Rule Selection & Filtering | **MOSTLY IMPLEMENTED** | 70% |
| **P6** | Scenario Orchestration | **PARTIAL** | 60% |
| **P7** | Tool Execution | **PARTIAL** | 40% |
| **P8** | Response Planning | **NOT IMPLEMENTED** | 5% |
| **P9** | Generation | **PARTIAL** | 50% |
| **P10** | Enforcement & Guardrails | **PARTIAL** | 25% |
| **P11** | Persistence, Audit & Output | **IMPLEMENTED** | 95% |

**Overall Implementation: ~50%**

---

## Phase 1: Identification & Context Loading

**Goal**: Build `TurnContext` with session, customer, config, and glossary loaded.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P1.1 | Extract routing identifiers | ✅ IMPLEMENTED | `api/routes/chat.py` - ChatRequest model | — |
| P1.2 | Resolve customer from channel | ⚠️ PARTIAL | `chat.py` - Implicit in session lookup | No explicit `customer_id`, `is_new_customer` tracking |
| P1.3 | Resolve/create session | ✅ IMPLEMENTED | `conversation/stores/` - Redis & InMemory | — |
| P1.4 | Load SessionState | ✅ IMPLEMENTED | `conversation/models/session.py` | — |
| P1.5 | Load InterlocutorDataStore | ⚠️ PARTIAL | `domain/interlocutor/models.py`, `domain/interlocutor/store.py` | Has InterlocutorDataStore, needs explicit per-turn snapshot wiring (see Key Architectural Notes) |
| P1.6 | Load static config | ⚠️ PARTIAL | `config/loader.py` | **Missing**: GlossaryItem, InterlocutorDataField schema |
| P1.7 | Scenario reconciliation | ✅ IMPLEMENTED | `alignment/migration/` | Full migration system |
| P1.8 | Build TurnContext | ⚠️ PARTIAL | Engine + DI | **Missing**: Explicit `TurnContext` model |

**Key Gaps**:
- No explicit `TurnContext` aggregation model
- Glossary items not implemented
- InterlocutorDataField schema loading not explicit

---

## Phase 2: Situational Sensor (LLM)

**Goal**: Schema-aware, glossary-aware context extraction producing `SituationalSnapshot`.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P2.1 | Build InterlocutorSchemaMask | ❌ NOT FOUND | — | Model not defined, no masking logic |
| P2.2 | Build Glossary view | ❌ NOT FOUND | — | No `GlossaryItem` model, no retrieval |
| P2.3 | Build conversation window | ⚠️ PARTIAL | `extractor.py:161-171` | Hardcoded K=5, not configurable |
| P2.4 | Call Situational Sensor LLM | ⚠️ PARTIAL | `context/extractor.py:140-159` | Missing: schema mask, glossary, candidate vars |
| P2.5 | Parse SituationalSnapshot | ❌ NOT FOUND | — | No `SituationalSnapshot` model |
| P2.6 | Validate/fix language | ❌ NOT FOUND | — | No language detection/validation |

**Current vs Required Flow**:

| Current (`ContextExtractor`) | Required (`SituationalSensor`) |
|------------------------------|-------------------------------|
| Inputs: message + last 5 turns | Inputs: message + K turns + schema mask + glossary |
| Output: intent, entities, sentiment, topic, urgency | Output: `SituationalSnapshot` with candidate_variables |
| No schema awareness | Schema-aware extraction via `CustomerSchemaMask` |
| No glossary | Glossary-filtered domain terms |

**Current Output Fields** (`Context` model):
```python
intent: str | None
entities: list[ExtractedEntity]
sentiment: Sentiment | None
topic: str | None
urgency: Urgency
scenario_signal: ScenarioSignal | None
```

**Required Output Fields** (`SituationalSnapshot` model):
```python
canonical_intent_label: str
confidence: float
candidate_variables: dict[str, CandidateVariableInfo]  # ← CRITICAL FOR P3
topic: str
tone: str
detected_language: str
intent_changed: bool
situation_facts: list[str]
```

**Key Gaps**:
- **`SituationalSnapshot`** model completely missing
- **`CandidateVariableInfo`** model completely missing (blocks Phase 3)
- **`InterlocutorSchemaMask`** not built or passed to LLM
- **`GlossaryItem`** and `GlossaryView` not implemented
- Conversation window hardcoded to K=5 (line 167 of `extractor.py`)
- No candidate variable extraction from user message
- **Blocks Phase 3**: Without `candidate_variables`, P3 cannot update InterlocutorDataStore

---

## Phase 3: Customer Data Update

**Goal**: Map `candidate_variables` into `InterlocutorDataStore` using schema definitions.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P3.1 | Match candidates to fields | ❌ NOT FOUND | — | Depends on P2 (SituationalSnapshot) |
| P3.2 | Validate & coerce types | ⚠️ PARTIAL | `domain/interlocutor/validation.py` | Exists but not integrated |
| P3.3 | Apply updates in memory | ❌ NOT FOUND | — | Has `InterlocutorDataStore`, needs in-memory update flow with history/confidence |
| P3.4 | Mark updates for persistence | ❌ NOT FOUND | — | No `persistent_updates` tracking |

**Key Gaps**:
- Blocked by Phase 2 gaps (no `SituationalSnapshot`)
- `InterlocutorDataStore` architecture not implemented (see Key Architectural Notes)
  - Has `InterlocutorDataStore` but needs: `InterlocutorDataField` schema, `VariableEntry` with history/confidence
- `InterlocutorDataUpdate` model not defined
- Validation exists but not connected to brain

---

## Phase 4: Retrieval & Selection

**Goal**: Hybrid retrieval with adaptive selection for intents, rules, scenarios.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P4.1 | Compute embedding + lexical | ⚠️ PARTIAL | `vector/embedding_manager.py` | **Missing**: BM25/lexical features |
| P4.2 | Hybrid intent retrieval | ❌ NOT FOUND | — | No intent catalog or retrieval |
| P4.3 | Decide canonical intent | ❌ NOT FOUND | — | No intent merging logic |
| P4.4 | Build rule retrieval query | ✅ IMPLEMENTED | `retrieval/rule_retriever.py` | — |
| P4.5 | Hybrid rule retrieval | ⚠️ PARTIAL | Vector similarity only | **Missing**: BM25 hybrid |
| P4.6 | Apply rule selection strategy | ✅ IMPLEMENTED | `retrieval/selection.py` | 5 strategies implemented |
| P4.7 | Build scenario retrieval query | ✅ IMPLEMENTED | `retrieval/scenario_retriever.py` | — |
| P4.8 | Hybrid scenario retrieval | ⚠️ PARTIAL | Vector similarity only | **Missing**: BM25 hybrid |
| P4.9 | Apply scenario selection strategy | ✅ IMPLEMENTED | `retrieval/scenario_retriever.py` | — |

**Key Gaps**:
- Intent retrieval (P4.2-P4.3) not implemented
- BM25/lexical search not implemented (vector-only)
- Hybrid combining not implemented

**Strengths**:
- Selection strategies fully implemented (fixed_k, elbow, adaptive_k, entropy, clustering)
- Reranking fully implemented (Cohere, Jina, CrossEncoder)
- Memory retrieval follows same patterns

---

## Phase 5: Rule Selection & Filtering

**Goal**: Pre-filter, LLM filter, and relationship expansion for rules.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P5.1 | Pre-filter by scope & lifecycle | ✅ IMPLEMENTED | `retrieval/rule_retriever.py` | enabled, max_fires, cooldown |
| P5.2 | Optional LLM rule filter | ✅ IMPLEMENTED | `filtering/rule_filter.py` | Binary applies/not (not ternary) |
| P5.3 | Relationship expansion | ❌ NOT FOUND | — | No rule→rule relationship model |

**Key Gaps**:
- Rule relationship expansion not implemented
- No `depends_on`, `entails`, `excludes` relationships

---

## Phase 6: Scenario Orchestration

**Goal**: Lifecycle decisions, step transitions, multi-scenario contributions.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P6.1 | Build scenario selection context | ⚠️ PARTIAL | `filtering/scenario_filter.py` | No formal `ScenarioSelectionContext` model |
| P6.2 | Scenario lifecycle decisions | ⚠️ PARTIAL | `ScenarioAction` enum | **Missing**: PAUSE, COMPLETE, CANCEL |
| P6.3 | Step transition evaluation | ⚠️ PARTIAL | Basic transitions work | **Missing**: Step skipping logic |
| P6.4 | Determine contributions | ❌ NOT FOUND | — | No `ScenarioContributionPlan` |

**Key Gaps**:
- Missing lifecycle actions: PAUSE, COMPLETE, CANCEL
- Step skipping not implemented (jump to furthest reachable step)
- `ScenarioContribution` / `ScenarioContributionPlan` not implemented
- Multi-scenario coordination not implemented

---

## Phase 7: Tool Execution

**Goal**: Execute tenant tools with proper scheduling and variable resolution.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P7.1 | Collect tool bindings | ⚠️ PARTIAL | `Rule.attached_tool_ids` exists | No `ToolBinding` model, no collection logic |
| P7.2 | Compute required variables | ❌ NOT FOUND | — | No variable requirement analysis |
| P7.3 | Resolve from interlocutor/session | ⚠️ PARTIAL | Models exist | Resolution logic not implemented |
| P7.4 | Determine allowed tool calls | ❌ NOT FOUND | — | No BEFORE/DURING/AFTER scheduling |
| P7.5 | Execute tenant tools | ✅ IMPLEMENTED | `execution/tool_executor.py` | Parallel, timeout, fail-fast |
| P7.6 | Merge tool results | ⚠️ PARTIAL | `session.variables` update | No formal `engine_variables` phase |
| P7.7 | Keep future-scheduled tools | ❌ NOT FOUND | — | No future tool queue |

**Key Gaps**:
- Tool scheduling (BEFORE_STEP, DURING_STEP, AFTER_STEP) not implemented
- `ToolBinding` model not defined
- Variable resolution from profile/session not implemented
- No future tool queue for AFTER_STEP tools

**Strengths**:
- Tool execution (P7.5) fully implemented with concurrency, timeouts, fail-fast

---

## Phase 8: Response Planning

**Goal**: Build `ResponsePlan` combining scenario contributions and rule constraints.

**STATUS: PHASE 8 IS ENTIRELY SKIPPED** - Brain jumps from P6 (Scenario Orchestration) directly to P9 (Generation).

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P8.1 | Determine global response type | ❌ NOT FOUND | — | No `ResponseType` enum (ASK/ANSWER/MIXED/ESCALATE/HANDOFF) |
| P8.2 | Prioritize scenario contributions | ❌ NOT FOUND | — | No `ScenarioContributionPlan` model |
| P8.3 | Merge contribution plans | ❌ NOT FOUND | — | No merging logic |
| P8.4 | Inject constraints | ❌ NOT FOUND | — | Constraints only in Phase 10 (post-generation) |

**Current Brain Flow** (from `engine.py`):
```
Context Extraction → Retrieval → Rule Filtering → Scenario Filtering → Tool Execution
                                                                         ↓
                                                           [MISSING: Response Planning]
                                                                         ↓
                                                                    Generation
```

**What Generation Currently Receives**:
- `Context`, `matched_rules`, `history`, `tool_results`, `memory_context`, `templates`
- **Missing**: `ResponsePlan`, scenario contributions, response type guidance, pre-computed constraints

**What Phase 8 Should Provide**:
```python
class ResponsePlan(BaseModel):
    response_type: ResponseType  # ASK / ANSWER / MIXED / ESCALATE / HANDOFF
    contributions: list[ScenarioContributionPlan]  # What each scenario wants to say
    must_include: list[str]  # Pre-extracted from rules
    must_avoid: list[str]    # Pre-extracted from rules
    constraints_from_rules: list[RuleConstraint]
```

**Impact of Missing Phase 8**:
1. Generation has no guidance on response mode (ask vs answer vs escalate)
2. Scenarios don't contribute content/guidance to response
3. Constraints aren't pre-computed (enforcement is reactive, not proactive)
4. Scenario-step templates (line 36 of `scenario.py`) are **never loaded or used**

**Key Missing Models**:
- `ResponseType` enum
- `ResponsePlan` model
- `ScenarioContributionPlan` model
- `ScenarioContribution` model
- `RuleConstraint` model

---

## Phase 9: Generation

**Goal**: Build prompt, call LLM, format for channel, set resolution.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P9.1 | Build generation prompt | ✅ IMPLEMENTED | `generation/prompt_builder.py` | **Missing**: ResponsePlan, glossary |
| P9.2 | Call answer LLM | ⚠️ PARTIAL | `generation/generator.py` | **Missing**: Semantic categories output |
| P9.3 | Post-format for channel | ❌ NOT FOUND | — | No channel formatting |
| P9.4 | Append LLM categories | ❌ NOT FOUND | — | No `OutcomeCategory` model |
| P9.5 | Set resolution | ❌ NOT FOUND | — | No `TurnOutcome` model |

**Key Gaps**:
- LLM doesn't output semantic categories (KNOWLEDGE_GAP, OUT_OF_SCOPE, etc.)
- Channel formatting not implemented (WhatsApp, email, SMS, etc.)
- `TurnOutcome` / `OutcomeCategory` models not defined
- Resolution determination not implemented

**Strengths**:
- Prompt building works (rules, context, memory, tool results)
- LLM execution works (token tracking, timing, fallbacks)

---

## Phase 10: Enforcement & Guardrails

**Goal**: Two-lane enforcement (deterministic + LLM-as-Judge) with remediation.

**STATUS: ~25% IMPLEMENTED** - Only basic phrase matching exists.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P10.1a | Collect matched hard constraints | ✅ IMPLEMENTED | `engine.py:976` | — |
| P10.1b | Always add GLOBAL constraints | ❌ **CRITICAL** | — | GLOBAL rules not fetched if not matched |
| P10.2 | Extract variables from response | ❌ NOT FOUND | — | No regex or LLM extraction |
| P10.3 | Build enforcement var view | ❌ NOT FOUND | — | No profile+session+response merge |
| P10.4 | Deterministic (Lane 1, simpleeval) | ❌ NOT FOUND | — | No `simpleeval`, no expressions |
| P10.5 | LLM-as-Judge (Lane 2) | ❌ NOT FOUND | — | No LLM judgment for subjective rules |
| P10.6 | Relevance check | ❌ NOT FOUND | — | No query↔response similarity |
| P10.7 | Grounding check | ❌ NOT FOUND | — | No response↔context entailment |
| P10.8 | Aggregate violations | ⚠️ PARTIAL | `validator.py:117-143` | Basic phrase matching only |
| P10.9 | Regeneration with hints | ⚠️ PARTIAL | `validator.py:95-115` | Retry works, but no constraint hints |
| P10.10 | Fallback | ✅ IMPLEMENTED | `fallback.py` | Works correctly |

**⚠️ CRITICAL SAFETY GAP: GLOBAL Hard Constraints**

Current code (`engine.py:976`):
```python
hard_rules = [m.rule for m in matched_rules if m.rule.is_hard_constraint]
# PROBLEM: Only checks MATCHED rules!
```

**Example Failure**:
```
User: "What's the weather?"
GLOBAL Rule: "Never promise >10% discount" (hard_constraint=True)

→ Rule doesn't match "weather" semantically
→ Rule NOT retrieved
→ Response: "Weather unavailable. Here's 25% off!"
→ GLOBAL constraint NOT enforced ❌
```

**Two-Lane Architecture (Not Implemented)**:

| Lane | Purpose | How | Status |
|------|---------|-----|--------|
| **Lane 1: Deterministic** | Rules with `enforcement_expression` | `simpleeval` library | ❌ Missing |
| **Lane 2: Probabilistic** | Subjective rules (no expression) | LLM-as-Judge | ❌ Missing |

**Lane 1 Example** (not implemented):
```python
Rule(
    name="Refund Limit",
    action_text="limit refunds to $50 for standard customers",
    enforcement_expression="amount <= 50 or user_tier == 'VIP'",  # ← MISSING FIELD
)
# Would evaluate: extract "amount" from response → check expression
```

**Current Violation Detection** (`validator.py:117-143`):
```python
# Only does simple phrase matching:
if any(phrase in lower_response for phrase in self._extract_phrases(rule)):
    violations.append(...)
```

**Missing Dependencies**: `simpleeval` not in `pyproject.toml`

**Missing on Rule Model**: `enforcement_expression: str | None` field

**Key Gaps**:
1. **GLOBAL constraints not always enforced** (production blocker)
2. **No variable extraction** from response (can't check "amount <= 50")
3. **No `simpleeval`** for deterministic expression evaluation
4. **No LLM-as-Judge** for subjective constraint evaluation
5. **No relevance/grounding checks** (optional but valuable)

**What Works**:
- Basic phrase matching against `action_text`
- Regeneration retry (max 2 attempts)
- Fallback template selection and application
- `EnforcementResult` model with metrics

---

## Phase 11: Persistence, Audit & Output

**Goal**: Persist session/customer data, record audit trail, emit metrics.

| ID | Sub-phase | Status | Implementation | Gap |
|----|-----------|--------|----------------|-----|
| P11.1 | Update SessionState | ✅ IMPLEMENTED | `engine.py` | — |
| P11.2 | Persist SessionState | ✅ IMPLEMENTED | `conversation/stores/` | Redis, PostgreSQL |
| P11.3 | Persist InterlocutorDataStore | ⚠️ PARTIAL | `domain/interlocutor/store.py` | No explicit `persistent_updates` batch |
| P11.4 | Record TurnRecord | ✅ IMPLEMENTED | `audit/stores/` | PostgreSQL, InMemory |
| P11.5 | Memory ingestion | ✅ IMPLEMENTED | `memory/ingestion/` | Async queue, summarization |
| P11.6 | Build final API response | ✅ IMPLEMENTED | `api/routes/chat.py` | — |
| P11.7 | Emit metrics/traces | ✅ IMPLEMENTED | `observability/` | Prometheus, OpenTelemetry |

**Key Gaps**:
- No explicit `persistent_updates` batching (direct to InterlocutorDataStoreInterface)

**Strengths**:
- Session persistence fully implemented (Redis two-tier)
- Audit trail fully implemented (PostgreSQL)
- Memory ingestion fully implemented (async, entity extraction, summarization)
- Observability fully implemented (metrics, tracing, structured logging)

---

## Priority Implementation Order

Based on dependencies and impact:

### Tier 1: Foundation Models (Blockers)
1. **SituationalSnapshot** model (unblocks Phase 2-3)
2. **TurnOutcome** / **OutcomeCategory** models (unblocks Phase 9-10)
3. **ResponsePlan** model (unblocks Phase 8-9)
4. **ScenarioContributionPlan** model (unblocks Phase 6, 8)

### Tier 2: Critical Safety
5. **P10.1b**: Always enforce GLOBAL hard constraints
6. **P10.4**: Deterministic enforcement (simpleeval)
7. **P10.5**: LLM-as-Judge for subjective constraints

### Tier 3: Core Brain
8. **Phase 2**: Full situational sensor with schema masking
9. **Phase 3**: Customer data update flow
10. **Phase 8**: Response planning (currently skipped entirely)

### Tier 4: Enhancements
11. **P4.2-P4.3**: Intent retrieval
12. **P4.5/P4.8**: BM25 hybrid search
13. **P6.3**: Step skipping logic
14. **P7.4**: Tool scheduling (BEFORE/DURING/AFTER)
15. **P9.3**: Channel formatting

---

## Missing Models Summary

| Model | Phase | Priority |
|-------|-------|----------|
| `SituationalSnapshot` | P2 | High |
| `CandidateVariableInfo` | P2 | High |
| `InterlocutorSchemaMask` | P2 | High |
| `GlossaryItem` / `GlossaryView` | P1, P2 | Medium |
| `InterlocutorDataStore` + `InterlocutorDataField` + `VariableEntry` | P1, P3 | High |
| `InterlocutorDataUpdate` | P3 | High |
| `TurnContext` | P1 | Medium |
| `ScenarioContribution` | P6 | High |
| `ScenarioContributionPlan` | P6 | High |
| `ScenarioLifecycleDecision` | P6 | Medium |
| `ToolBinding` | P7 | Medium |
| `ResponsePlan` | P8 | High |
| `ResponseType` enum | P8 | High |
| `OutcomeCategory` | P9 | High |
| `TurnOutcome` | P9 | High |
| `enforcement_expression` (Rule field) | P10 | High |

---

## Files to Create

```
ruche/brains/focal/
├── context/
│   └── situational_snapshot.py    # SituationalSnapshot, CandidateVariableInfo
├── planning/
│   ├── response_planner.py        # ResponsePlan synthesis
│   └── models.py                  # ResponsePlan, ResponseType
├── enforcement/
│   ├── variable_extractor.py      # Extract vars from response
│   ├── deterministic_enforcer.py  # simpleeval evaluation
│   ├── subjective_enforcer.py     # LLM-as-Judge
│   ├── relevance_verifier.py      # Relevance check
│   └── grounding_verifier.py      # Grounding check
└── models/
    └── outcome.py                 # TurnOutcome, OutcomeCategory

ruche/domain/interlocutor/
└── data_store.py                  # InterlocutorDataStore, InterlocutorDataUpdate
```

---

## FOCAL Brain Parallelism

See `focal_brain.md` Section 6 for the full FOCAL Brain Execution Model.

**Current State**: Most operations execute **sequentially**, creating performance bottlenecks.

| Phase | Parallel Operations | Spec | Current | Gap |
|-------|---------------------|------|---------|-----|
| **P1** | InterlocutorDataStore ‖ Config/Glossary | ✓ Parallel | Sequential | `engine.py:293-300` - sequential awaits |
| **P4** | Rule ‖ Scenario ‖ Memory ‖ Intent retrieval | ✓ Parallel | Sequential | `engine.py:746-778` - sequential awaits |
| **P4** | Reranking per object type | ✓ Parallel | Sequential | Only rules reranked, no gather |
| **P11** | Session ‖ InterlocutorData ‖ TurnRecord ‖ Memory | ✓ Parallel | Sequential | `engine.py:446-460` - sequential awaits |
| **P11** | Memory ingestion (background) | ✓ Async | Not integrated | Task queue exists but unused |

**Current Code Analysis** (from `engine.py`):

```python
# P1: Sequential loading (lines 293-300)
session = await self._session_store.get(session_id)        # await 1
history = await self._load_history(session_id)             # await 2

# P4: Sequential retrieval (lines 746-778)
retrieval_result = await self._rule_retriever.retrieve(...)    # await 1
scenarios = await self._scenario_retriever.retrieve(...)       # await 2
memories = await self._memory_retriever.retrieve(...)          # await 3

# P11: Sequential persistence (lines 446-460)
await self._update_and_persist_session(...)    # await 1
await self._persist_turn_record(...)           # await 2
```

**Should Be** (per spec Section 6.5):
```python
# P4: Parallel retrieval
rules, scenarios, memories, intents = await asyncio.gather(
    rule_task, scenario_task, memory_task, intent_task
)
```

**Performance Impact**:
- Sequential P4 with 80ms per retrieval: **240ms** (3 × 80ms)
- Parallel P4: **80ms** (max of three)
- **Savings: 160ms per turn**

**Infrastructure That Exists But Is Unused**:
- `InMemoryTaskQueue` with background worker (`memory/ingestion/queue.py`)
- `EntityExtractor.extract_batch` uses `asyncio.gather()` (line 142)
- BUT: No `task_queue.enqueue()` call in `engine.py`

**Critical Sequential Dependencies** (must remain sequential):
- **P2 → P4.1**: Embedding needs SituationalSnapshot context
- **P3 → P4**: Customer data updates affect retrieval
- **P9 → P10**: Enforcement needs generated response

---

## Conclusion

The codebase has strong foundations in:
- **Retrieval & Selection** (Phase 4): Selection strategies, reranking
- **Persistence & Observability** (Phase 11): Session, audit, memory, metrics
- **Tool Execution** (Phase 7.5): Parallel execution with timeouts

Major gaps exist in:
- **Situational Sensing** (Phase 2): Schema-aware extraction
- **Response Planning** (Phase 8): Entirely missing
- **Enforcement** (Phase 10): Two-lane enforcement not implemented

The brain currently skips from Phase 6 → Phase 9, missing the Response Planning phase entirely. This means:
- No formal response type determination
- No scenario contribution coordination
- No pre-generation constraint injection

Priority should be given to foundation models (`SituationalSnapshot`, `ResponsePlan`, `TurnOutcome`) that unblock multiple phases.
