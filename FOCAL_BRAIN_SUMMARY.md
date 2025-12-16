# FOCAL Brain (Alignment Engine) — Detailed Summary

**Scope**: This document explains how the **FOCAL Brain** works end-to-end (what it does per turn, what data it reads/writes, and why it is designed this way). It is written to be accurate to:

- The **canonical specs/design docs** in `docs/` (especially `docs/acf/` and `docs/focal_brain/spec/`).
- The **current implementation** in `ruche/brains/focal/` and related runtime modules.

Where the implementation is incomplete or deviates from the spec, this document calls that out explicitly.

---

## 1) What “FOCAL Brain” Is (and What It Is Not)

### 1.1 The platform layers (thin-waist architecture)

FOCAL is not the full conversational platform; it is the **Brain** (the “what to do / what to say” unit) inside a larger runtime envelope:

- **Channels / ingress**: WhatsApp, webchat, email, voice, etc.
- **ACF (Agent Conversation Fabric)**: infrastructure that decides *when* a turn is ready and enforces concurrency guarantees.
- **AgentRuntime**: loads an Agent and constructs its Brain + Toolbox.
- **Agent**: business entity that owns a **Brain** and a **Toolbox**.
- **FOCAL Brain**: the alignment-focused pipeline that processes a *LogicalTurn* and produces a response + artifacts.
- **Toolbox**: the execution boundary for tools and side effects (authorization, idempotency, audit events).
- **Stores / Providers**: persistence backends and AI capability providers (LLM, embeddings, rerank).

Implementation note: Agents can select different Brain implementations via `agent.brain_type` (default `"focal"`). AgentRuntime constructs the brain via `BrainFactory`.
- `ruche/runtime/agent/runtime.py`
- `ruche/runtime/brain/factory.py`

Canonical references:
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/architecture/overview.md`

### 1.2 ACF vs Brain: the responsibility boundary

**ACF provides facts + safety invariants**:
- Aggregates message bursts into a **LogicalTurn**
- Enforces a per-session **mutex** (no parallel processing per session key)
- Provides a “has pending messages?” **supersede signal** as a *fact*, not a decision
- Orchestrates durable steps (Hatchet) and routes events

**The Brain makes decisions**:
- What the user is trying to do (intent/situation)
- Which policies apply (rules)
- Which workflow step the session is in (scenario orchestration)
- Which tools to run (and when), and how to respond
- Whether to supersede current work when new messages arrive (design intent)

Canonical references:
- `docs/acf/architecture/ACF_SPEC.md`
- `ruche/runtime/brain/protocol.py`

### 1.3 “LLMs are sensors and judges, not the policy engine”

FOCAL uses LLMs in constrained roles:
- **Sensor**: extract structured situational signals (intent, tone, candidate variables) from user input.
- **Judge**: decide semantic applicability (which rules apply) or subjective compliance (enforcement lane 2).

The system’s **policy** lives in deterministic configuration:
- Rules, scenarios, templates, variables, tool bindings in ConfigStore
- State in SessionStore and InterlocutorDataStore
- Guardrails in enforcement rules that are validated post-generation

This design shifts the system away from “hope the prompt works” toward **runtime enforcement and auditability**.

Canonical references:
- `docs/focal_brain/spec/brain.md`
- `docs/design/decisions/002-rule-matching-strategy.md`
- `docs/design/decisions/001-storage-choice.md`

---

## 2) The State Model (What Lives Where, and Why)

### 2.1 The four domain-aligned stores (ADR-001)

Focal splits persistence into conceptual domains with different access patterns:

1. **ConfigStore** (“How should it behave?”)
   - Rules, Scenarios, Templates, Variables, Intents, Tool definitions/activations
   - Read-heavy, versioned, hot-reload friendly

2. **SessionStore** (“What’s happening now?”)
   - Current session state (active scenario, current step, session variables, rule fires)
   - Low-latency read/write; designed for horizontal scaling

3. **MemoryStore** (“What does it remember?”)
   - Long-term memory: episodes/entities/relationships with semantic search
   - Append-heavy, retrieval-oriented

4. **AuditStore** (“What happened?”)
   - Immutable turn records, events, compliance trail
   - Append-only, queryable

Justification:
- Each domain has different latency/durability/query requirements. Separate interfaces let each backend be optimized without coupling everything to a single database design.
- Separation reduces accidental mixing (e.g., session state leaking into config).
- Enables swapping backends independently per domain.

Canonical references:
- `docs/design/decisions/001-storage-choice.md`
- `docs/architecture/overview.md`

### 2.2 InterlocutorDataStore: structured cross-session “customer facts”

FOCAL uses a dedicated persistent store for structured, verified facts about the interlocutor (customer):

- **InterlocutorDataField**: schema definition (agent-scoped)
- **InterlocutorDataStore**: per-interlocutor values and metadata
- Values are updated incrementally from conversation (“candidate variables”), tools, or verification workflows.

Why this exists (what it allows):
- Prevents re-asking for stable facts across sessions (“email”, “account_id”, “preferences”).
- Enables scenario step skipping when required fields are already known.
- Enables validation, provenance, and retention/PII handling at the field level, rather than burying everything in unstructured memory.

Canonical references:
- `docs/design/interlocutor-data.md`
- `ruche/domain/interlocutor/models.py`

### 2.3 “Zero in-memory state” (stateless pods) — what it really means

The principle is: **no pod-local state as the system of record**. A given pod may hold transient variables during a single request, but all durable state is written to stores so that:
- Any pod can serve any request.
- Crashes/retries don’t lose the conversation state.
- Horizontal scaling doesn’t require sticky sessions.

Design tradeoff:
- More I/O and more careful store boundaries, but dramatically better correctness under concurrency and better scalability.

Canonical references:
- `docs/architecture/overview.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`

---

## 3) The Turn Unit: From Raw Messages to a LogicalTurn

FOCAL runs **once per LogicalTurn**:
- A LogicalTurn is one conversational beat (one or more raw messages) created by ACF.
- ACF guarantees per-session serialization (mutex) and provides supersede facts.

Canonical references:
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/focal_brain/spec/brain.md`

---

## 4) The FOCAL Brain Pipeline (Canonical Spec)

The canonical brain spec is an **11-phase** pipeline that executes once per LogicalTurn:
- `docs/focal_brain/spec/brain.md`

The current Ruche implementation uses a **12-step** orchestrator (`FocalCognitivePipeline`) where “persistence” is treated as a separate final step. Functionally it maps to the spec’s Phase 11 (“Persistence, audit & output”).

---

## 5) Phase-by-Phase: What Happens in One Turn

This section describes each phase in terms of:
- **Inputs** (what it reads)
- **Processing** (what it does)
- **Outputs** (what it produces for downstream phases)
- **Justification** (why this exists / what it enables)

### Phase 1 — Identification & context loading (P1.1–P1.8)

**Purpose**: Build a `TurnContext` containing all turn-scoped state required to process the LogicalTurn.

**Key inputs**
- Routing identifiers: `tenant_id`, `agent_id`, channel info, channel user id
- Session state from SessionStore
- Interlocutor data from InterlocutorDataStore
- Static config from ConfigStore (pipeline config, schema, glossary)
- (Optional) scenario migration plans if the scenario changed mid-session

**Key outputs**
- `TurnContext` (turn-scoped aggregation)

**Implementation mapping**
- Customer resolution: `ruche/brains/focal/pipeline.py::_resolve_customer()`
- Session load: `ruche/brains/focal/pipeline.py::process_turn()` → `SessionStore.get()`
- History load: `ruche/brains/focal/pipeline.py::_load_history()` → `AuditStore.list_turns_by_session()`
- Scenario reconciliation (version changes): `ruche/brains/focal/pipeline.py::_pre_turn_reconciliation()` → `ruche/brains/focal/migration/executor.py`
- Turn context build: `ruche/brains/focal/pipeline.py::_build_turn_context()` → `ruche/brains/focal/models/turn_context.py`
- Static config loaders: `ruche/brains/focal/phases/loaders/static_config_loader.py`
- Interlocutor snapshot loader: `ruche/brains/focal/phases/loaders/interlocutor_data_loader.py`

**Justification (what this enables)**
- **Multi-tenant safety**: all subsequent operations are scoped by resolved IDs.
- **Correctness under concurrency**: run in the ACF session mutex boundary.
- **Hot-reload & version safety**: reconciliation prevents corrupting sessions when scenarios change.
- **Privacy + token discipline**: loads schemas and glossary selectively and can cap what goes into prompts.

**Important implementation note**
- The Brain protocol wrapper `FocalCognitivePipeline.think()` currently uses a placeholder combined message (see `ruche/brains/focal/pipeline.py::think()`). The canonical design is that it should process the real LogicalTurn messages from ACF.

---

### Phase 2 — Situational Sensor (LLM) (P2.1–P2.6)

**Purpose**: Produce a structured `SituationSnapshot` from user input (intent, topic, tone, urgency, and candidate field values).

**Key inputs**
- Current user message + last K conversation turns
- **Customer schema mask** (fields exist / has value, but not the values)
- Glossary items (domain terms)

**Key processing**
- Build `CustomerSchemaMask` (privacy-safe)
- Render prompt (`ruche/brains/focal/phases/context/prompts/situation_sensor.jinja2`)
- Call LLM with deterministic settings (temperature often `0.0` for extraction)
- Parse JSON output into `SituationSnapshot`
- Validate language (ISO 639-1) and fall back if invalid

**Key outputs**
- `SituationSnapshot` (primary per-turn “understanding” object)
- Candidate variables (`candidate_variables`) for Phase 3

**Implementation mapping**
- Sensor orchestrator: `ruche/brains/focal/phases/context/situation_sensor.py`
- Schema mask model: `ruche/brains/focal/phases/context/customer_schema_mask.py`
- Snapshot model: `ruche/brains/focal/phases/context/situation_snapshot.py`

**Justification (what this enables)**
- **Separation of concerns**: extraction is isolated from generation, so you can tune models/cost separately.
- **Reduced PII leakage**: the LLM sees only schema existence, not stored values, during sensing.
- **Typed downstream processing**: later phases can rely on structured fields rather than re-prompting.
- **Auditability**: the snapshot is stored in `AlignmentResult` and can be recorded in `TurnRecord`.

---

### Phase 3 — Interlocutor data update (schema-driven) (P3.1–P3.4)

**Purpose**: Update the in-memory InterlocutorDataStore snapshot with new facts extracted from the user message, and compute a list of updates that should be persisted.

**Key inputs**
- `SituationSnapshot.candidate_variables`
- InterlocutorDataField schema definitions
- Current InterlocutorDataStore snapshot

**Key processing**
- Match candidates to schema fields
- Validate and coerce values (type/regex/allowed values)
- Update InterlocutorDataStore in-memory (track history)
- Mark which updates should be persisted (scope and `persist` rules)

**Key outputs**
- Updated InterlocutorDataStore (in-memory, for this turn)
- `persistent_customer_updates` to be written in the persistence phase

**Implementation mapping**
- Updater: `ruche/brains/focal/phases/interlocutor/updater.py`
- Field schema: `ruche/domain/interlocutor/models.py::InterlocutorDataField`
- Persistence filtering: `ruche/brains/focal/pipeline.py::_persist_customer_data()`

**Justification (what this enables)**
- **Cross-session continuity**: stable facts persist across sessions without bloating prompts.
- **Data quality**: typed validation and provenance reduce silent corruption.
- **Scenario efficiency**: step skipping and requirement checks can use structured fields.
- **Privacy policy hooks**: PII flags, retention, and encryption requirements attach to the schema.

---

### Phase 4 — Retrieval & selection strategies (P4.*)

**Purpose**: Retrieve candidates (rules/scenarios/intents/memory) relevant to the current turn and dynamically select an appropriate number of results.

**Key inputs**
- Message embedding (computed or provided)
- ConfigStore indices (rules/scenarios/intents)
- MemoryStore semantic index (episodes)
- Selection strategy config per object type (dynamic k selection)
- Optional reranking providers (cross-encoder)
- Optional hybrid scoring (vector + BM25)

**Key processing**
- Run retrieval tasks in parallel where possible:
  - Rules
  - Scenarios
  - Intents
  - Memory episodes
- Rerank per object type (optional)
- Apply selection strategy per object type (adaptive cutoff instead of fixed top-k)
- Merge sensor intent with intent retrieval to decide canonical intent

**Key outputs**
- `RetrievalResult` (scored rules, scenarios, memory episodes; plus selection metadata)
- `snapshot.canonical_intent_label` / `snapshot.canonical_intent_score`

**Implementation mapping**
- Orchestration: `ruche/brains/focal/pipeline.py::_retrieve_rules()` (name is historical; it retrieves more than rules)
- Rule retrieval: `ruche/brains/focal/retrieval/rule_retriever.py`
- Scenario retrieval: `ruche/brains/focal/retrieval/scenario_retriever.py`
- Intent retrieval + canonical intent merge: `ruche/brains/focal/retrieval/intent_retriever.py`
- Memory retrieval: `ruche/memory/retrieval/retriever.py`
- Selection strategies: `ruche/brains/focal/retrieval/selection.py` and `docs/architecture/selection-strategies.md`

**Justification (what this enables)**
- **Latency control**: retrieval is designed to be fast and mostly non-LLM, keeping LLM calls focused.
- **Prompt bloat prevention**: selection strategies cut off noisy tails dynamically.
- **Precision and robustness**: reranking and hybrid scoring improve accuracy when embeddings alone are insufficient.
- **Analytics**: canonical intents can feed an “intent registry” without becoming policy engines.

**Important implementation note**
- `RuleRetriever.retrieve()` supports scope-aware retrieval (GLOBAL/SCENARIO/STEP), but the current pipeline call does not pass active scenario/step context into retrieval. Scope filtering is still applied in Phase 5 prefilter, but scope-aware retrieval itself is not yet fully utilized.

---

### Phase 5 — Rule selection (filtering + relationships) (P5.1–P5.3)

**Purpose**: Convert retrieved rule candidates into the final applied rule set for the turn.

**Key inputs**
- Candidate rules from retrieval
- Session state (rule fires, cooldowns, active scenario/step)
- `SituationSnapshot` (canonical intent, topic, etc.)
- Rule relationships (depends_on / implies / excludes)

**Key processing**
1. **Deterministic prefilter** (P5.1)
   - Remove disabled rules
   - Remove scope mismatches (scenario/step scoped)
   - Apply cooldown and max-fires-per-session

2. **LLM filter** (P5.2)
   - Batch-evaluate candidate rules against the snapshot
   - Return ternary outputs: APPLIES / NOT_RELATED / UNSURE with confidence

3. **Relationship expansion** (P5.3)
   - Add implied/required rules
   - Remove excluded rules

**Key outputs**
- `matched_rules: list[MatchedRule]` used for tool execution, planning, generation, enforcement

**Implementation mapping**
- Prefilter: `ruche/brains/focal/phases/filtering/scope_filter.py`
- LLM filter: `ruche/brains/focal/phases/filtering/rule_filter.py`
- Relationship expansion: `ruche/brains/focal/phases/filtering/relationship_expander.py`

**Justification (what this enables)**
- **Cost control**: deterministic prefilter reduces LLM calls and token usage.
- **Higher precision**: LLM filtering resolves semantic ambiguity beyond vector similarity.
- **Explainability**: rules include “reasoning” in `MatchedRule` and appear in audit artifacts.
- **Composable policy**: relationships allow reusable policy blocks without duplicating rule text.

---

### Phase 6 — Scenario orchestration & next-state decisions (P6.*)

**Purpose**: Determine the session’s workflow state (“scenario”) and which step(s) are active or should change.

**Key inputs**
- Scenario candidates from retrieval
- Active scenario and step from SessionStore
- Step history (for loop detection)
- InterlocutorDataStore + session variables (for skipping and requirements)
- Canonical intent label

**Spec intent (canonical design)**
- Decide scenario lifecycle actions (START/CONTINUE/PAUSE/COMPLETE/CANCEL)
- Evaluate step transitions using scenario graph edges (conditions, priorities)
- Support step skipping and relocalization (“recovery step”)
- Produce a `ScenarioContributionPlan` describing what scenarios want to contribute this turn

Canonical reference:
- `docs/focal_brain/spec/brain.md` (Phase 6)
- `docs/design/scenario-update-methods.md` (scenario version changes)

**Current implementation status (in this repo)**
- The pipeline uses `ScenarioFilter` but its navigation logic is currently limited:
  - Starts the top retrieved scenario if none active
  - Continues the active scenario
  - Detects loops and can “relocalize”
  - Supports step skipping based on known required fields
  - Does **not** yet evaluate step transitions based on transition conditions

Implementation mapping:
- Scenario filter: `ruche/brains/focal/phases/filtering/scenario_filter.py`
- Step skipping helpers are embedded in the same file.

**Requirements / gap-fill**
- After scenario filtering, the pipeline optionally runs a requirement resolution pass which can attempt “gap fill”:
  - `ruche/brains/focal/pipeline.py::_check_scenario_requirements()`
  - `ruche/brains/focal/migration/field_resolver.py::MissingFieldResolver`

**Justification (what this enables)**
- **Workflow reliability**: scenarios are explicit state machines, not implicit prompt behavior.
- **Long-lived sessions**: scenario state survives days/weeks and remains consistent across pods.
- **Safe mid-flight updates**: migration planning avoids corrupting active sessions when graphs change.
- **Better UX**: step skipping avoids redundant questions when the user provides multiple fields at once.

---

### Phase 7 — Tenant tool scheduling & execution (P7.1–P7.7)

**Purpose**: Execute tools deterministically when needed, respecting timing and dependencies, and produce variables for response generation and future turns.

**Spec intent (canonical design)**
- Collect tool bindings from contributing scenarios and matched rules
- Compute required variables for this turn
- Resolve known variables from InterlocutorDataStore and Session
- Schedule tools by `when` phase (BEFORE/DURING/AFTER) and dependency graph
- Execute tools via Toolbox (policy + idempotency + audit boundary)
- Merge tool outputs into `engine_variables`
- Queue future tools for later phases

Canonical references:
- `docs/focal_brain/spec/brain.md` (Phase 7)
- `docs/acf/architecture/TOOLBOX_SPEC.md`

**Current implementation status (in this repo)**
- A Phase 7 orchestration scaffold exists:
  - `ruche/brains/focal/phases/execution/tool_execution_orchestrator.py`
  - `ruche/brains/focal/phases/execution/tool_scheduler.py`
  - `ruche/brains/focal/phases/execution/variable_requirement_analyzer.py`
  - `ruche/brains/focal/phases/execution/variable_resolver.py`
  - `ruche/brains/focal/phases/execution/variable_merger.py`
- However, actual execution currently falls back to legacy “attached_tool_ids” execution:
  - `ruche/brains/focal/phases/execution/tool_executor.py`
  - Tool scheduling output is not yet wired into concrete tool calls.

**Justification (what this enables)**
- **Deterministic side effects**: tools run because a rule/step demanded them, not because the model guessed.
- **Safer production behavior**: tool semantics (irreversible, idempotent, compensatable) live at the Toolbox boundary.
- **Latency/cost control**: run only the tools needed to fill required variables; parallelize safe tools.
- **Supersede safety**: the canonical design checks ACF supersede facts before irreversible tools.

---

### Phase 8 — Response planning (P8.*)

**Purpose**: Produce a structured `ResponsePlan` that guides generation (what to ask/inform/confirm, in what priority, with what constraints).

**Key inputs**
- Scenario contributions (ASK / INFORM / CONFIRM / ACTION_HINT)
- Matched rules (constraints and priorities)
- Tool results (facts and errors)

**Key outputs**
- `ResponsePlan` consumed by generation

**Implementation mapping**
- Planning models: `ruche/brains/focal/phases/planning/models.py`
- Planner: `ruche/brains/focal/phases/planning/planner.py`
- Scenario contribution extraction (currently simplified): `ruche/brains/focal/pipeline_contribution_extractor.py`

**Justification (what this enables)**
- **Prompt structure**: keeps generation from being an unstructured “dump everything” prompt.
- **Multi-scenario handling**: merges multiple scenario contributions deterministically (by priority).
- **Explicit response typing**: enables consistent behavior like ASK vs ANSWER vs CONFIRM.

---

### Phase 9 — Generation (main LLM)

**Purpose**: Produce the natural language response (or deterministic template output).

**Key inputs**
- `SituationSnapshot`
- Matched rules (action_text instructions; constraints)
- Memory context (optional)
- Tool results (optional)
- ResponsePlan (optional)
- Templates (exclusive/suggest/fallback)
- Glossary (optional)

**Key processing**
- If an **EXCLUSIVE** template is attached to a matched rule, bypass the LLM.
- Otherwise build a system prompt that includes:
  - active rules + hard constraint markings
  - user context (intent/tone/urgency)
  - memory episodes (if any)
  - tool outputs (if any)
  - response plan and constraints (if enabled)
  - output schema requirement (JSON envelope with categories)
- Call the generation model; parse structured output; format for channel.

**Key outputs**
- `GenerationResult.response` (text)
- Optional `OutcomeCategory` signals emitted by the model (e.g., KNOWLEDGE_GAP)

**Implementation mapping**
- Generator: `ruche/brains/focal/phases/generation/generator.py`
- Prompt builder: `ruche/brains/focal/phases/generation/prompt_builder.py`
- System prompt template: `ruche/brains/focal/phases/generation/prompts/system_prompt.txt`
- LLM output parser: `ruche/brains/focal/phases/generation/parser.py`

**Justification (what this enables)**
- **Template bypass**: deterministic, low-latency responses for high-risk or fully scripted behaviors.
- **Per-step model selection**: the generation model can be higher quality than sensor/filter models.
- **Structured outcomes**: “categories” allow downstream guardrails (e.g., relevance checks) to behave correctly.

---

### Phase 10 — Enforcement & guardrails

**Purpose**: Validate that the response complies with hard constraints and apply remediation if not.

**Key design points**
- Two-lane enforcement:
  - **Lane 1 (Deterministic)**: evaluate `enforcement_expression` with extracted variables
  - **Lane 2 (Subjective)**: LLM-as-judge checks compliance for non-expressible constraints
- **Always enforce GLOBAL hard constraints** even if they did not match retrieval (critical safety property).
- If violations occur: attempt regeneration (bounded retries), then fallback.

**Implementation mapping**
- Validator: `ruche/brains/focal/phases/enforcement/validator.py`
- Deterministic evaluation: `ruche/brains/focal/phases/enforcement/deterministic_enforcer.py`
- Variable extraction: `ruche/brains/focal/phases/enforcement/variable_extractor.py`
- LLM judge: `ruche/brains/focal/phases/enforcement/subjective_enforcer.py`
- Fallback handler: `ruche/brains/focal/phases/enforcement/fallback.py`

**Justification (what this enables)**
- **Reliability**: moves constraints from “prompt suggestion” to “validated requirement”.
- **Compliance**: supports formal constraints like `amount <= 50` with deterministic evaluation.
- **Safety-by-default**: global guardrails can’t be bypassed by retrieval misses.
- **Auditable failures**: violations are recorded in the enforcement result and can be stored in TurnRecord.

---

### Phase 11 — Persistence, audit & output

**Purpose**: Make the turn durable and observable: update the session state, persist relevant updates, and record an immutable audit entry.

**Key outputs**
- Updated SessionStore state (turn count, active scenario/step, rule fires, variables)
- Updated InterlocutorDataStore fields (persisted subset of Phase 3 updates)
- TurnRecord in AuditStore
- Optional memory ingestion of the turn into MemoryStore

**Implementation mapping**
- Session update + persist: `ruche/brains/focal/pipeline.py::_update_and_persist_session()`
- Customer data persist: `ruche/brains/focal/pipeline.py::_persist_customer_data()`
- TurnRecord persist: `ruche/brains/focal/pipeline.py::_persist_turn_record()`
- TurnRecord model: `ruche/audit/models/turn_record.py`
- Parallel persistence orchestrator: `ruche/brains/focal/pipeline.py` (see “Parallel persistence” in `_process_turn_impl`)

**Justification (what this enables)**
- **Stateless execution**: next turn can run on any pod with correct state.
- **Debuggability**: TurnRecord provides a stable forensic trail.
- **Compliance**: audit separation from operational logs.
- **Performance**: persistence can be parallelized because stores are domain-separated.

---

## 6) Configuration: How Behavior Is Tuned Without Code Changes

### 6.1 Configuration loading

Configuration is TOML-driven with Pydantic models:
- Base defaults in `config/default.toml`
- Environment overrides in `config/{RUCHE_ENV}.toml` (e.g. `config/development.toml`, `config/staging.toml`, `config/production.toml`, `config/test.toml`)
- Runtime overrides via `RUCHE_*` environment variables (nested delimiter `__`)

**Naming note (spec vs code)**:
- Some older/spec docs (e.g. `docs/focal_brain/spec/configuration.md`) describe configuration under `[brain.*]`.
- The current Ruche implementation uses `[pipeline.*]` and the `PipelineConfig` model (`ruche/config/models/pipeline.py`), surfaced as `Settings.pipeline` (`ruche/config/settings.py`).

Canonical reference:
- `docs/architecture/configuration-overview.md`

### 6.2 Per-step model selection and OpenRouter routing

Each LLM-invoking step can choose:
- Primary model and fallback models
- OpenRouter provider routing preferences

Model strings are parsed by provider prefix (examples): `openrouter/...`, `anthropic/...`, `openai/...`, `groq/...`, `mock/...` (see `ruche/infrastructure/providers/llm/executor.py`).

Implementation:
- `ruche/infrastructure/providers/llm/executor.py::create_executors_from_pipeline_config()`
- `ruche/config/models/pipeline.py` (step configs)

### 6.3 Retrieval tuning (selection, reranking, hybrid)

The retrieval stage has per-object-type knobs:
- selection strategy (`adaptive_k`, `entropy`, etc.)
- reranking enablement and top_k
- hybrid scoring weights (vector + BM25)

See:
- `config/default.toml` (`[pipeline.retrieval.*]`)
- `docs/architecture/selection-strategies.md`

---

## 7) Observability & Audit: How You Debug a Brain in Production

FOCAL is designed so every turn is traceable at multiple levels:

1. **Structured logs** (operational)
   - JSON logs with bound context (tenant/agent/session/turn IDs)
   - No PII at INFO by default

2. **Traces** (performance + causal debugging)
   - Spans per step (conceptually)

3. **Metrics** (service health)
   - Counters and histograms per stage

4. **Audit records** (compliance and replayability)
   - Immutable `TurnRecord` with matched rules, scenario state, tool calls, enforcement violations

Canonical reference:
- `docs/architecture/observability.md`

---

## 8) What This Design Allows (and the Key Tradeoffs)

### 8.1 Allows

- **Horizontal scaling without sticky sessions** (stateless pods + durable stores)
- **Hot-reload of behavior** (config in stores; per-step model choices in config)
- **Multi-brain platform** (FOCAL, LangGraph, Agno) behind the same ACF envelope
- **Deterministic tool execution** with side-effect policy enforcement at the Toolbox boundary
- **Safe long-lived workflows** via explicit scenario graphs + migration strategies
- **Operational clarity** via turn-level audit records and per-step telemetry
- **Cost/performance tuning** by splitting sensor/filter/judge/generation into separate model tiers

### 8.2 Costs / tradeoffs

- More moving parts than prompt-only systems (stores, retrieval, multiple steps)
- Requires disciplined config and schema management
- Added latency from extra LLM calls (sensor + rule filter + judge) in exchange for reliability
- Needs careful UX design around supersede, confirmation, and long-lived scenario flows

---

## 9) Spec vs Implementation: Notable Deltas in This Repo

This repository contains both a detailed spec and an evolving implementation. The most important current deltas:

1. **Brain protocol integration**: `FocalCognitivePipeline.think()` currently constructs a placeholder message instead of using real LogicalTurn content (`ruche/brains/focal/pipeline.py::think()`).
2. **Scenario orchestration depth**: scenario transition evaluation by graph edges is not yet implemented; the current `ScenarioFilter` mostly STARTs top candidate and CONTINUEs active (`ruche/brains/focal/phases/filtering/scenario_filter.py`).
3. **Scope-aware rule retrieval**: `RuleRetriever` supports scenario/step scope retrieval, but the orchestrator does not pass active scenario/step into retrieval yet (`ruche/brains/focal/pipeline.py::_retrieve_rules()`).
4. **Tool scheduling wiring**: Phase 7 scheduling exists, but execution currently falls back to legacy `attached_tool_ids` and does not fully use the scheduled tool plan (`ruche/brains/focal/phases/execution/tool_execution_orchestrator.py`).
5. **Enforcement regeneration hints**: enforcement calls regeneration, but the current generation path does not explicitly incorporate violation summaries into the generation prompt (see `ruche/brains/focal/phases/enforcement/validator.py::_regenerate()` and `ruche/brains/focal/phases/generation/prompt_builder.py`).

These are implementation gaps, not design contradictions; they reflect staged build-out.

---

## 10) Primary References (Docs + Code)

**Canonical docs**
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/focal_brain/spec/brain.md`
- `docs/focal_brain/spec/data_models.md`
- `docs/focal_brain/spec/execution_model.md`
- `docs/design/decisions/001-storage-choice.md`
- `docs/design/decisions/002-rule-matching-strategy.md`
- `docs/design/scenario-update-methods.md`
- `docs/architecture/selection-strategies.md`
- `docs/architecture/observability.md`
- `docs/design/interlocutor-data.md`

**Core implementation**
- `ruche/brains/focal/pipeline.py` (main orchestrator)
- `ruche/brains/focal/phases/context/situation_sensor.py`
- `ruche/brains/focal/retrieval/` (rules/scenarios/intents + selection)
- `ruche/memory/retrieval/retriever.py`
- `ruche/brains/focal/phases/filtering/` (scope prefilter, LLM rule filter, scenario filter)
- `ruche/brains/focal/phases/planning/` (response planning)
- `ruche/brains/focal/phases/generation/` (prompt building + response generation)
- `ruche/brains/focal/phases/enforcement/` (two-lane enforcement)
- `ruche/brains/focal/migration/` (scenario version reconciliation)
- `ruche/audit/models/turn_record.py`
- `ruche/runtime/brain/protocol.py`
- `ruche/runtime/brain/factory.py`
