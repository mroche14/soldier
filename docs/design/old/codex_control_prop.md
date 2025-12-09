# Codex Control Layer Proposal

Unified design for rule processing, scenario/journey control, and enforcement in Focal.

This document synthesizes:
- `docs/design/turn-pipeline.md`
- `docs/design/enhanced-enforcement.md`
- `docs/design/decisions/state_machine.md`
- `docs/design/decisions/state_machine_2.md`
- `docs/design/decisions/002-rule-matching-strategy.md`

It resolves overlaps and tensions between the “Graph-Augmented State Machine”, the “State-Aware Agent Engine”, and the enhanced enforcement pipeline into a single control architecture, while keeping alternative options visible for future tuning.

---

## 1. Scope and Constraints

**Goal:** Define how Focal:
- represents and retrieves **rules** and **scenarios/journeys**,
- navigates scenario state and intent,
- deterministically **enforces constraints** on every turn,
- does so **multi-tenant**, **stateless per pod**, and **auditable**.

**Key constraints:**
- Multi-tenant: every query keyed by `tenant_id` (and usually `agent_id`).
- Zero in‑memory state: all long‑lived state in ConfigStore, SessionStore, ProfileStore, MemoryStore, AuditStore.
- Deterministic control: LLMs are sensors and judges, not policy engines.
- Graph‑based flows: scenarios are directed graphs; rules can form a dependency graph.
- Hot‑swappable pipeline: all behavior controlled via TOML + Pydantic configs.

---

## 2. Control Architecture Overview

The control layer is **not** a separate pipeline; it is the way we interpret and orchestrate the existing turn pipeline:

```text
[1. RECEIVE] 
  -> [2. EXTRACT CONTEXT/INTENT]    -- "Sensor"
  -> [3. RETRIEVE]                  -- "Candidate graph"
  -> [4. RERANK]
  -> [5. RULE FILTER]               -- "Which rules apply?"
  -> [5b. SCENARIO FILTER]          -- "Where are we in the journey?"
  -> [6. EXECUTE TOOLS]
  -> [7. GENERATE RESPONSE]
  -> [8. ENFORCE]                   -- "Did we violate policy?"
  -> [9. PERSIST + MEMORY]
  -> [10. RESPOND]
```

**Codex Control** is the combination of:
- **Representation:** how rules, scenarios, intents, and profiles are modeled.
- **Navigation:** how the engine moves between states/steps.
- **Policy checking:** how we decide if an action/response is allowed.
- **Guardrails:** relevance/grounding and global constraints.

This document describes the **recommended default** and **alternative options** at each layer.

---

## 3. Data Model and Stores

### 3.1 Rules

Rules live in **ConfigStore** and are agent‑scoped.

Core fields (consolidating existing docs):
- `tenant_id`, `agent_id` (multi‑tenant, agent‑scoped).
- `id`, `name`, `enabled`.
- `condition_text`: natural language condition used for matching.
- `action_text`: natural language policy or behavior used for prompting.
- `scope`: `GLOBAL | SCENARIO | STEP`.
- `scope_id`: `None | scenario_id | step_id`.
- `is_hard_constraint`: `bool` (participates in enforcement).
- `enforcement_expression`: optional deterministic expression (lane 1).
- `attached_tool_ids`: tools to execute when the rule fires.
- `priority`, `max_fires_per_session`, `cooldown_turns`.
- Optional graph metadata:
  - `depends_on_definitions: list[node_id]`
  - `entails_rules: list[rule_id]`
  - `excludes_rules: list[rule_id]`

**Interpretation:**
- `condition_text` + embeddings drive **retrieval and RuleFilter**.
- `enforcement_expression` + `is_hard_constraint` drive **deterministic enforcement**.
- Graph metadata is used for **graph expansion** when present, but the system works without it.

**Alignment / instructions / drift:**
- Centralizes behavioral policy in structured rules, not prompts.
- Hard constraints and expressions give deterministic checks against policy.
- Scoping and cooldowns reduce rule pollution and over‑firing that lead to behavioral drift.

### 3.2 Scenarios (Journeys/Guidelines)

Scenarios live in **ConfigStore** as **directed graphs**.

Concepts:
- **Scenario:** named journey with `entry_step_id`, `version`, `tenant_id`, `agent_id`.
- **Step:** node in the graph.
  - `id`, `name`, `description`.
  - `step_type`: `ACTION | INTERACTION | LOGIC` (from state_machine_2).
  - `local_rules`: scoped rules or rule references.
  - `required_profile_fields` / `required_session_fields` (scenario requirements).
- **Transition:** directed edge.
  - from_step_id, to_step_id
  - triggers:
    - **Intent** (e.g. `confirm`, `cancel`, `change_subject`).
    - **Condition** (deterministic expression on profile/session, e.g. `refund_amount > 50`).
  - optional `llm_hint`: short description to help scenario LLM adjudication.

Scenarios are consumed by:
- **ScenarioRetriever** (finding entry candidates).
- **ScenarioFilter** (step navigation).
- **AlignmentEngine** (for context in prompts and persistence).

**Alignment / instructions / drift:**
- Encodes “how the agent should proceed” as explicit graphs, not emergent chat state.
- Step‑local rules and requirements make instruction application state‑aware and repeatable.
- Terminal states, transitions, and versioning prevent flows from silently drifting over time.

### 3.3 Intent Registry

The **IntentRegistry** is a logical layer over ConfigStore:
- Stores **named intents** with example utterances and embeddings.
- Links each intent to:
  - scenario entry points (e.g. `request_refund → refund_scenario`),
  - scenario transitions (e.g. `confirm_refund` from step X to Y).

Use:
- For **intent detection** and **few‑shot classification**.
- For **analytics** (intent heatmaps, bottlenecks).

Implementation detail:
- Today, most of this is achievable via:
  - scenario entry conditions + scenario retrieval;
  - per‑transition metadata in ScenarioFilter configs.
- The IntentRegistry is a **naming and analytics layer** on top of that.

**Alignment / instructions / drift:**
- Makes “what the user can ask for” explicit, so navigation is constrained to known intents.
- Few‑shot examples improve instruction following for recurring business flows.
- Intent heatmaps help detect drift in how users and agents actually use scenarios.

### 3.4 CustomerProfile and Session

Profiles live in **ProfileStore**; sessions in **SessionStore**.

CustomerProfile (from `customer-profile.md` and state_machine_2):
- Ledger of fields with:
  - `value`, `history`, `confidence`, `source`.
- Schema is **tenant‑specific** and evolves over time.
- Setup/Builder agents register new fields when creating rules and scenarios.

Session:
- Holds **ephemeral state**:
  - `tenant_id`, `agent_id`, `session_id`.
  - `active_scenario_id`, `active_step_id`, `active_scenario_version`.
  - `variables` (turn/session variables).
  - rule tracking (fires, last fire turns).
  - `step_history`, `relocalization_count`.

The control layer treats:
- **Profile** as durable, cross‑session facts.
- **Session** as the current conversation state and working memory.

**Alignment / instructions / drift:**
- Ledger‑style profiles plus history make policy‑relevant facts auditable and correctable.
- Session fields (scenario, step, variables) bound all decisions to an explicit state.
- Versioned schemas avoid “hidden” changes in what rules mean by a field like `tier` or `age`.

### 3.5 Stores Mapping

- ConfigStore:
  - Rules, Scenarios, Templates, Intents, Variables, Tool policies.
- MemoryStore:
  - Episodes, entities, relationships, long‑term knowledge.
- SessionStore:
  - Session graph state and per‑session variables.
- ProfileStore:
  - CustomerProfile ledger and schema.
- AuditStore:
  - Turn records, enforcement decisions, scenario transitions, violations.

---

## 4. Processing Flow (Recommended Design)

This section maps the state machine concepts into the existing turn pipeline.

### 4.1 Receive & Reconcile (Steps 1, 1b)

As in `turn-pipeline.md`:
- Validate request, extract `tenant_id` from auth.
- Load or create `Session` via SessionStore.
- Load agent config (including pipeline config) via ConfigStore.
- Reconcile scenario version (migration) before processing.

Codex Control requirement:
- All later decisions must log `tenant_id`, `agent_id`, `session_id`, `turn_id`.

### 4.2 Sensor: Context + Intent Extraction (Step 2)

We combine ideas from:
- LLMContextExtractor in `turn-pipeline.md`.
- “Extractor (Sensor)” from state_machine_2.

**Recommended design (Parallel extraction within one step):**
- A single **Extractor** step performs:
  - **Context extraction:** fill `Context` model (intent text, entities, sentiment, scenario hints).
  - **Intent detection:** map the user message to one or more named intents.
  - **Profile updates:** extract profile fields based on schema and update ProfileStore.

Implementation note:
- Today, `ContextExtractor` already outputs `user_intent`, `entities`, `sentiment`, `scenario_signal`.
- We extend it conceptually to:
  - use **IntentRegistry** entries as retrieval examples;
  - produce `detected_intents` as structured output;
  - optionally generate field updates for CustomerProfile.

**Option A – Single LLM call (current default):**
- One LLM prompt (as in `extract_intent.txt`) returns both context and coarse scenario signal.
- Pros: Simple, one request; good default.
- Cons: Less explicit control over intent definitions; weaker analytics.

**Option B – Split Context + Intent with IntentRegistry:**
- Use:
  - LLMContextExtractor for context (entities, sentiment, hints).
  - Embedding/IntentRegistry for intent classification (vector search + optional LLM).
- Pros: Better reuse of intents across agents; more explainable; high observability.
- Cons: More moving parts; slightly higher latency.

**Recommendation:** Start with **Option A** plus **lightweight IntentRegistry usage** (few‑shot examples inside context extraction). Move to **Option B** for tenants needing fine‑grained analytics and explicit intent control.

**Alignment / instructions / drift:**
- Separating “what is happening” (context/profile) from “what user wants” (intent) keeps routing logic clean.
- Using the schema and intent catalog ensures the sensor fills the exact variables policies depend on.
- Ambiguity/confidence signals can block or clarify instead of letting the agent guess and drift.

### 4.3 Candidate Retrieval (Step 3)

This step is already defined in `turn-pipeline.md` and `002-rule-matching-strategy.md`.

**Recommended algorithm:**
- For rules:
  - Use **hybrid retrieval** (Option B in `002-rule-matching-strategy.md`):
    - vector search on `condition_text + action_text`,
    - optional BM25 scoring on textual content,
    - apply scope filters: `GLOBAL`, then active `SCENARIO`, then active `STEP`.
  - Over‑fetch (e.g. 20–30 rules) for re‑ranking and filtering.
- For scenarios:
  - Vector search scenario entry conditions (as in `ScenarioRetriever`).
  - Use **active scenario continuation** logic when in a scenario.
- For memory:
  - Use existing MemoryRetriever (vector now, hybrid later).

**Option 1 – Vector-only (current implementation):**
- Simpler, already in place.
- Acceptable for smaller rule sets.

**Option 2 – Hybrid vector + BM25 (recommended):**
- As in `002-rule-matching-strategy.md`.
- Better recall + precision, especially for long/structured conditions.

**Option 3 – LLM-on-candidates:**
- LLM does semantic filtering directly on candidate rules (slowest).
- Use only for high‑risk domains.

**Recommendation:** Default to **Option 2** for rules (hybrid) and **vector-only** for scenarios/memory initially; keep Option 3 as an opt‑in enforcement‑grade matching mode.

**Alignment / instructions / drift:**
- Scope‑aware retrieval prevents unrelated rules or scenarios from influencing decisions.
- Hybrid search improves recall/precision so the “right” instructions are available for the turn.
- Over‑fetch + later filters provide robustness against embedding model noise without over‑trusting LLMs.

### 4.4 Rerank (Step 4)

Use `ResultReranker` to:
- take top‑K candidate rules/scenarios/memory chunks,
- rerank by dedicated reranker (Cohere/Voyage/CrossEncoder),
- keep top‑K for filters.

No structural changes required; Codex Control relies on this to improve ordering before decisions.

### 4.5 Rule Filter (Step 5)

RuleFilter is the **probabilistic judge** of which retrieved rules apply; it sits **before deterministic enforcement**.

Behavior:
- Input: `Context`, candidate rules.
- Output: `matched_rules` (subset), optional coarse `scenario_signal`.
- Mechanism: LLM prompt that decides YES/NO per candidate.

Control implications:
- RuleFilter is allowed to be “slightly conservative” (favor false negatives over false positives).
- Deterministic enforcement later can still catch **violations of hard constraints**, even when a rule was not matched.

**Alignment / instructions / drift:**
- Explicitly deciding which rules apply per turn keeps prompts small and focused on relevant policy.
- Conservative filtering avoids over‑applying instructions where they don’t clearly fit.
- Combined with enforcement, this reduces both instruction overreach and policy gaps over time.

### 4.6 Scenario Filter / Router (Step 5b)

ScenarioFilter implements the **Router + Scenario Engine** from state_machine_2:
- **Router responsibilities:**
  - Decide if we:
    - stay in the current scenario,
    - transition to a new step,
    - exit the scenario,
    - start a new scenario.
  - Resolve conflicts between local step transitions and global intents.
- **Scenario Engine responsibilities:**
  - Evaluate transitions based on:
    - detected intents,
    - deterministic conditions (expressions),
    - LLM adjudication when ambiguous.
  - Update `session.active_scenario_id`, `active_step_id`, and step history.

Existing `ScenarioFilter` already covers:
- step transitions,
- entry checking,
- re‑localization,
- loop detection.

We integrate the state_machine_2 ideas as **behavioral policies**:
- **Stickiness:** prefer local transitions from the active scenario unless a global intent has significantly higher confidence.
- **Fallback transitions:** each step can define a “fallback/clarification” transition if no intent matches.
- **Scenario exit on terminal steps:** if in a terminal step and no transitions match, exit scenario.

**Option 1 – LLM‑heavy navigation:**
- ScenarioFilter delegates most decisions to an LLM; conditions and intents are soft signals.
- Pros: Very flexible; easy to author.
- Cons: Harder to reason about; less deterministic.

**Option 2 – Hybrid deterministic + LLM (recommended):**
- Use deterministic conditions and intent matches as primary signals.
- Use LLM only for:
  - tie‑breaking between multiple candidate transitions,
  - re‑localization when the state appears inconsistent.
- Pros: Matches the “deterministic core + probabilistic sensing” philosophy.

**Option 3 – Deterministic only:**
- All transitions are expressions over profile + session; no LLM.
- Pros: Max determinism; suitable for regulated tenants.
- Cons: Higher authoring burden; less adaptive.

**Recommendation:** Implement **Option 2** as the default ScenarioFilter behavior; keep Option 1/3 as configuration modes for specific tenants.

**Alignment / instructions / drift:**
- Sticky routing ensures users stay in a coherent journey unless they clearly change goals.
- Fallback transitions give deterministic behavior when intents don’t match cleanly, instead of undefined loops.
- Deterministic conditions on transitions anchor process adherence to explicit rules over profile/session state.

### 4.7 Tool Execution (Step 6)

Tool execution follows `turn-pipeline.md`:
- Only tools from **matched rules** are executed.
- Tool outputs are fed into:
  - session variables,
  - potentially the CustomerProfile (via extraction/ingestion),
  - generation prompts.

Link to state_machine.md:
- The “Auto-Resolution Loop” (resolving missing variables via tools before asking the user) can be layered in as:
  - a policy in the **ToolExecutor + VariableResolver**:
    - if a step requires variables and they are missing,
    - try configured resolvers/tools,
    - only ask the user if resolvers fail.

This iterative behavior is an **internal loop inside a single turn** (up to `max_loops`) and can be implemented without changing the main pipeline shape.

**Alignment / instructions / drift:**
- Mapping variables to tools makes “where information comes from” explicit and repeatable.
- Iterative resolution lets the system satisfy policy preconditions automatically instead of improvising.
- Tool failures surface as explicit outcomes, not silent misbehavior, which helps detect drift.

### 4.8 Response Generation (Step 7)

No major changes, but Codex Control enforces:
- **Prompt composition discipline:**
  - Rules: only `action_text` of **matched rules** (plus optional always‑enforced GLOBAL constraints as “silent guardrails” if desired).
  - Scenario context: only active scenario + step.
  - Memory: limited, most relevant episodes.
  - Tool results: successful results only.
- **Template shortcut path:** exclusive templates can bypass LLM when allowed by policy.

**Alignment / instructions / drift:**
- Strict prompt composition (rules, scenario, memory, tools) ensures the LLM sees an aligned, curated context.
- Exclusive templates give fully deterministic paths for high‑risk or highly standardized responses.
- Limiting how much historic state enters the prompt reduces slow prompt‑based drift in behavior.

### 4.9 Enforcement and Guardrails (Step 8)

This is where `enhanced-enforcement.md` is fully integrated.

Core elements:

1. **Rule selection for enforcement:**
   - All **hard constraints** from matched rules (`is_hard_constraint=True`).
   - All **GLOBAL hard constraints**, even if not matched by retrieval.
     - Retrieved via ConfigStore using `scope=GLOBAL`, `hard_constraints_only=True`.
   - Result: `rules_to_enforce`.

2. **Variable extraction:**
   - From:
     - the generated response text (regex + optional LLM extraction),
     - session variables,
     - CustomerProfile fields.
   - Produces a dictionary of variables used by deterministic expressions.

3. **Lane 1 – Deterministic enforcement:**
   - Uses `enforcement_expression` with a safe evaluator (e.g. `simpleeval`).
   - Returns `True` when the rule is satisfied; `False` on violation.
   - 100% deterministic once variables are known.

4. **Lane 2 – LLM-as-Judge for subjective rules:**
   - For rules without `enforcement_expression`.
   - LLM evaluates whether the response complies with `action_text`.
   - Returns `(passed: bool, explanation: str)`.

5. **Global checks (optional):**
   - **Relevance:** does the response address the user’s query?
     - Embedding similarity or cross‑encoder.
     - Refusal bypass for “I don’t know” answers.
   - **Grounding:** is the response supported by retrieved context?
     - LLM NLI or cross‑encoder; outputs `ENTAILMENT | NEUTRAL | CONTRADICTION`.

6. **Remediation:**
   - If violations exist:
     - Optionally regenerate with hints about violated constraints (self‑critique).
     - Or fall back to a safe template.
   - All violations are recorded in AuditStore.

**Option A – Minimal enforcement:**
- Only deterministic lane; no LLM-as-Judge, no global checks.
- Suitable for low‑risk tenants or CPU‑only environments.

**Option B – Deterministic + LLM-as-Judge (recommended baseline):**
- Lane 1 for quantitative/structured policies.
- Lane 2 for tone, style, and subjective policies.
- No global relevance/grounding by default.

**Option C – Full enhanced enforcement:**
- Deterministic + LLM-as-Judge + relevance + grounding.
- For safety‑critical tenants (compliance/finance/health).

**Recommendation:** Expose these options via `EnforcementConfig`, with **Option B** as the default and **Option C** as an opt‑in preset.

### 4.10 Persist, Memory, and Audit (Steps 9–10)

Persist step:
- Saves:
  - updated session state,
  - turn record with:
    - matched rules,
    - tools called,
    - scenario before/after,
    - enforcement result (pass/fail, violations),
    - latency + token usage.
- Optionally sends content to MemoryIngestor for long‑term memory.

Codex Control requirement:
- All key decisions (rule matches, scenario transitions, enforcement evaluations) must be **audit‑logged** for debugging and analytics.

**Alignment / instructions / drift:**
- Persisted turns plus enforcement results create an explicit trace of when and how policies were applied or violated.
- Memory ingestion can be constrained to aligned, post‑enforcement content, preventing hallucinations from seeding future behavior.
- Audit logs make it possible to detect slow drift (e.g., rules that never fire, scenarios users abandon) and correct them.

---

## 5. Design Axes and Options

This section summarizes the main axes where multiple designs exist, with pros/cons and recommendations.

### 5.1 Intent and Scenario Navigation

**Axis:** How do we decide where the user is in the scenario graph?

- **Option 1 – Context-only (monolithic LLM):**
  - Use only LLMContextExtractor + ScenarioFilter with LLM reasoning.
  - Pros: simplest authoring; minimal infra.
  - Cons: harder to debug; intent taxonomy is implicit.

- **Option 2 – State-Aware Engine (recommended):**
  - Use:
    - Extractor as sensor (context + intents + profile updates).
    - ScenarioFilter as router/engine with:
      - stickiness rules,
      - fallback transitions,
      - deterministic conditions.
  - Pros: clear separation of sensing vs. decision; matches state_machine_2.
  - Cons: requires more care in scenario design.

- **Option 3 – Deterministic only:**
  - All transitions by expressions and explicit user inputs.
  - Pros: maximal determinism.
  - Cons: lowest flexibility and UX.

**Recommendation:** Adopt **Option 2** as the canonical design, with configuration toggles allowing tenants to slide towards Option 1 or 3.

### 5.2 Rule Representation and Retrieval

**Axis:** Flat vs. graph‑augmented rules; retrieval strategy.

- **Option 1 – Flat rules + vector search:**
  - Each rule is independent; retrieval is embedding‑only.
  - Pros: simple; already implemented.
  - Cons: poorer handling of shared definitions and dependencies.

- **Option 2 – Graph-augmented rules (recommended structurally):**
  - Rules can reference:
    - shared definitions,
    - entailments and exclusions.
  - Retrieval uses:
    - vector search to find seed rules,
    - graph expansion to pull linked nodes (definitions, entailed rules).
  - Pros: better context integrity; supports complex policies.
  - Cons: requires extra modeling; not all tenants need it.

- **Option 3 – LLM‑centric rule reasoning:**
  - LLM reads large blocks of policy text instead of structured rules.
  - Pros: simplest authoring; reduces structure needs.
  - Cons: harder to enforce deterministically; poor auditability.

**Recommendation:** Model rules with optional graph metadata (Option 2), but keep retrieval **functional without it**. Use hybrid vector+BM25 for seeds; add graph expansion where relationships exist.

### 5.3 Enforcement Strength

**Axis:** How strong and expensive should enforcement be?

Options mapping to Section 4.9:
- **Minimal:** deterministic only.
- **Baseline (recommended):** deterministic + LLM-as-Judge.
- **Maximal:** baseline + relevance + grounding.

These correspond to different `EnforcementConfig` presets and can be exposed as:
- `mode = "minimal" | "baseline" | "maximal"` in TOML, mapping to booleans.

### 5.4 Iterative Resolution vs. Single Pass

**Axis:** Resolve missing variables via tools vs. ask user immediately.

- **Option 1 – Single pass (current behavior):**
  - One pass: extract → retrieve → filter → tools → generate → enforce.

- **Option 2 – Iterative resolution (from state_machine.md, recommended where needed):**
  - For each turn:
    - extract → retrieve → try to resolve missing variables via tools,
    - loop up to `max_loops` before giving up and asking user.
  - Pros: fewer unnecessary user questions; better automation.
  - Cons: more complexity; risk of extra latency if loops are long.

**Recommendation:** Keep the **single pass** as the default; implement the **iterative resolution loop** as an optional configuration for steps or scenarios that declare required variables and tool resolvers.

---

## 6. Configuration and Modes

The control layer is driven by existing pipeline configs:
- `pipeline.context_extraction`
- `pipeline.retrieval` / `pipeline.reranking`
- `pipeline.rule_filter`
- `pipeline.scenario_filter`
- `pipeline.enforcement`

We propose adding **high‑level presets**:

```toml
[pipeline.codex_control]
mode = "baseline"  # "minimal" | "baseline" | "maximal"
```

The engine maps `mode` to:
- context extraction mode (llm vs embedding_only),
- rule_filter and scenario_filter aggressiveness and LLM usage,
- enforcement config (which lanes/global checks are enabled).

Implementation can be incremental; the important part is that **control policies are explicit in configuration**, not hardcoded.

---

## 7. Recommendations and Next Steps

### 7.1 Recommended Baseline for Focal

For the default, multi‑tenant SaaS deployment:
- **Architecture:**
  - Use the **State-Aware Agent Engine** view:
    - Extractor as sensor.
    - ScenarioFilter as router/engine.
    - Enforcement as deterministic + LLM-as-Judge.
- **Retrieval:**
  - Implement hybrid vector + BM25 for rule retrieval (Option 2).
  - Keep scenarios and memory on vector-only for now.
- **Rules:**
  - Support `enforcement_expression` and `is_hard_constraint` as in enhanced enforcement.
  - Begin storing graph metadata where available; treat it as optional.
- **Scenarios:**
  - Treat scenarios as graphs with typed steps and transitions.
  - Use stickiness and fallback transitions in ScenarioFilter.
- **Enforcement:**
  - Adopt **baseline** enforcement (deterministic + LLM-as-Judge) globally.
  - Always enforce GLOBAL hard constraints regardless of retrieval.
  - Keep relevance/grounding disabled by default but available.
- **Profiles:**
  - Continue evolving CustomerProfile as a ledger.
  - Use extraction to keep profiles up to date when rules introduce new fields.

### 7.2 Roadmap by Complexity

1. **Short term:**
   - Align code with enhanced enforcement spec (deterministic + LLM-as-Judge + global hard constraints).
   - Add optional hybrid retrieval for rules.
   - Harden ScenarioFilter with stickiness and fallback semantics.

2. **Medium term:**
   - Introduce IntentRegistry as a first‑class concept (naming + analytics).
   - Add optional graph metadata to rules and basic graph expansion.
   - Implement iterative resolution loops for scenarios that declare required variables and resolvers.

3. **Long term:**
   - Full graph‑augmented retrieval for rules and definitions.
   - Rich enforcement policies with local models (ONNX) for grounding/relevance.
   - Pre‑trained, reusable control presets per vertical (e.g., “Strict Compliance”, “Conversational Support”, “Sales Assist”).

---

## 8. How This Unifies the Existing Docs

- **state_machine.md (“Graph-Augmented State Machine”):**
  - Contributes:
    - graph‑based rule relationships and expansion,
    - iterative resolution loop,
    - explicit guardrail checks (relevance, grounding).
  - Incorporated as optional enhancements on top of the baseline pipeline.

- **state_machine_2.md (“State-Aware Agent Engine”):**
  - Contributes:
    - Extractor/Router/Scenario Engine decomposition,
    - CustomerProfile ledger and schema evolution,
    - intent vs. context separation and stickiness.
  - Forms the conceptual backbone of the ScenarioFilter and profile integration.

- **enhanced-enforcement.md:**
  - Contributes:
    - deterministic vs. probabilistic enforcement lanes,
    - variable extraction and expression evaluation,
    - always‑enforce GLOBAL hard constraints,
    - relevance and grounding verification.
  - Becomes the canonical design for Step 8 (Enforce) in the turn pipeline.

- **002-rule-matching-strategy.md:**
  - Contributes:
    - hybrid retrieval strategy,
    - score composition and cutoffs,
    - future LLM‑derived patterns.
  - Defines the recommended rule retrieval behavior.

- **turn-pipeline.md:**
  - Provides the **skeleton** into which all of the above plug.
  - Codex Control does not change the pipeline shape; it clarifies responsibilities and options at key control points.

Together, these yield a single, coherent **Codex Control Layer**: deterministic at its core, LLM‑assisted at the boundaries, multi‑tenant, and fully configurable via TOML.

---

## 9. Alignment, Instruction Following, and Drift

This control design is explicitly tuned for:

- **Alignment to explicit policy:**
  - Policies live in **rules, scenarios, and profile/schema** stored in ConfigStore/ProfileStore, not hidden in prompts.
  - Deterministic **enforcement expressions** and scenario transition conditions ensure that once policy is expressed, its application is code‑level deterministic.

- **Instruction following:**
  - Scoped rules (GLOBAL / SCENARIO / STEP) and **rule retrieval** prevent unrelated instructions from polluting a turn.
  - Scenario graphs and **stickiness** ensure that once a journey is entered, the agent prefers following that path unless a clear, higher‑confidence global intent overrides it.
  - Tool execution and iterative resolution (when enabled) help satisfy required preconditions before generating responses, instead of asking the user arbitrarily or guessing.

- **Drift resistance (over turns and time):**
  - **GLOBAL hard constraints** are always enforced, even when the matching stack fails, so safety and compliance policies do not drift with retrieval or prompting quality.
  - Optional **relevance and grounding** checks catch semantic drift (answering the wrong question, hallucinating policy/facts) on each response.
  - CustomerProfile as a **ledger** with schema evolution and history avoids silent state drift; updates are explicit and auditable.
  - Scenario navigation, step history, and AuditStore logging provide a trace of how and why the engine moved between states, making drift detectable and correctable.

Overall, Codex Control makes the “what should the agent do?” layer explicit, testable, and configurable, and then uses LLMs only to sense inputs and judge ambiguous or subjective aspects, which is the core requirement for robust alignment and drift control in Focal.
