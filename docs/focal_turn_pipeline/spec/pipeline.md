## 2. Pipeline (Phases 1–11)

### Phase 1 – Identification & context loading

**Goal:** From an inbound event, build a `TurnContext` with session, customer, config, and glossary loaded.

| ID   | Substep                                 | Goal                                                                | Inputs                                                                 | Outputs                                                                   |
| ---- | --------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| P1.1 | Extract routing identifiers             | Identify tenant/agent, channel, and channel/customer IDs            | Inbound event (`tenant_id`, `agent_id`, `channel_id` or `customer_id`) | `TurnInput`                                                               |
| P1.2 | Resolve customer from channel or create | Map `channel_id` to existing customer, or create a new one          | `tenant_id`, `channel_id`, optional `customer_id`                      | `customer_key`, `is_new_customer`                                         |
| P1.3 | Resolve / create session                | Find or allocate a session for this customer & channel              | `tenant_id`, `agent_id`, `customer_key`, `channel`                     | `session_id`                                                              |
| P1.4 | Load SessionState                       | Load scenario instances, session vars, last intent                  | `tenant_id`, `agent_id`, `session_id`                                  | `SessionState`                                                            |
| P1.5 | Load CustomerDataStore snapshot         | Get all customer variables                                          | `tenant_id`, `customer_key`                                            | `CustomerDataStore`                                                       |
| P1.6 | Load static config                      | Load pipeline config, LLM tasks, CustomerDataFields, glossary items | `tenant_id`, `agent_id`                                                | `PipelineConfig`, `LlmTaskConfig`s, `CustomerDataField`s, `GlossaryItem`s |
| P1.7 | Scenario reconciliation (if needed)     | Handle scenario version changes since last turn                     | `SessionState`, loaded Scenarios                                       | Reconciled `SessionState`                                                 |
| P1.8 | Build TurnContext                       | Aggregate all of the above                                          | P1.1–P1.7                                                              | `TurnContext`                                                             |

**Scenario Reconciliation (P1.7):**

If a session has an active scenario and the scenario's version has changed since the session started, we need to reconcile the customer's position in the scenario graph before processing the turn.

> For full details on scenario migration (gap-fill, teleportation, re-routing), see [scenario-update-methods.md](./scenario-update-methods.md).

---

### Phase 2 – LLM Situational Sensor (schema-aware + glossary-aware)

**Goal:** Ask a dedicated LLM task to “situate” the conversation:

* uses a **masked** view of CustomerDataStore (what exists, not the values),
* understands **customer data schema**,
* knows domain terms via **Glossary**,
* looks at last *K* messages.

#### 2.1 Build masked inputs

| ID   | Substep                   | Goal                                                     | Inputs                                    | Outputs               |
| ---- | ------------------------- | -------------------------------------------------------- | ----------------------------------------- | --------------------- |
| P2.1 | Build CustomerSchemaMask  | Show LLM which fields exist and whether they have values | `CustomerDataStore`, `CustomerDataField`s | `CustomerSchemaMask`  |
| P2.2 | Build Glossary view       | Provide domain terms and their meanings/usage            | `GlossaryItem`s                           | `GlossaryView` (dict) |
| P2.3 | Build conversation window | Select last *K* messages                                 | `SessionState`, `TurnInput.message`       | `conversation_window` |

`CustomerSchemaMask` is only: `field_key → {scope, type, exists}`.
No values, so no sensitive data is exposed to the LLM here.

#### 2.2 Sensor LLM call

| ID   | Substep                     | Goal                                                           | Inputs                                                                                 | Outputs                  |
| ---- | --------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------ |
| P2.4 | Call Situational Sensor LLM | Get JSON with situation, intent evolution, candidate variables | `conversation_window`, `CustomerSchemaMask`, `GlossaryView`, previous canonical intent | `situational_json` (raw) |
| P2.5 | Parse & validate snapshot   | Convert JSON into typed `SituationalSnapshot`                  | `situational_json`                                                                     | `SituationalSnapshot`    |
| P2.6 | Validate / fix language     | Confirm/fix `language`                                         | `SituationalSnapshot`, `TurnInput.message`                                             | `language_code`          |

What the LLM outputs (conceptually):

* `language`
* `intent_changed` (bool) + `new_intent_label`, `new_intent_text`
* `topic_changed`, `tone`, optional `frustration_level`
* `situation_facts`: bullet-like statements (“User wants refund because…”)
* `candidate_variables`:
  `{ <field_key>: {value, scope, is_update} }`, where keys are taken from `CustomerSchemaMask.variables` (so it uses **correct field names**).

---

### Phase 3 – CustomerDataStore update (schema-driven)

**Goal:** map `candidate_variables` into `CustomerDataStore` using `CustomerDataField` definitions.

| ID   | Substep                                | Goal                                               | Inputs                                                            | Outputs                                             |
| ---- | -------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------- |
| P3.1 | Match candidates to CustomerDataFields | Align candidate keys to known fields               | `SituationalSnapshot.candidate_variables`, `customer_data_fields` | list of `(CustomerDataField, raw_value, is_update)` |
| P3.2 | Validate & coerce types                | Check/coerce value types                           | mapping from P3.1                                                 | `CustomerDataUpdate` list (lightweight)             |
| P3.3 | Apply updates in memory                | Mutate in-memory `CustomerDataStore` for this turn | `CustomerDataStore`, `CustomerDataUpdate`, `is_update` flags      | updated `CustomerDataStore`                         |
| P3.4 | Mark updates for persistence           | Decide what will be persisted later                | updated `CustomerDataStore`, `CustomerDataField.persist` flags    | list of `persistent_updates` (lightweight)          |

DB writes happen in Phase 11, but logically we know the deltas here.

---

### Phase 4 – Representations, retrieval & selection strategies

**Goal:** get embeddings and run **hybrid retrieval + adaptive selection** for:

* intents,
* rules,
* scenarios.

#### 4.1 Embeddings & lexical features

| ID   | Substep                              | Goal                 | Inputs                                                                   | Outputs                                 |
| ---- | ------------------------------------ | -------------------- | ------------------------------------------------------------------------ | --------------------------------------- |
| P4.1 | Compute embedding & lexical features | Enable hybrid search | `TurnInput.message` or `SituationalSnapshot.new_intent_text`, `language` | `message_embedding`, `lexical_features` |

#### 4.2 Intent retrieval

| ID   | Substep                 | Goal                                              | Inputs                                                  | Outputs                                  |
| ---- | ----------------------- | ------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------- |
| P4.2 | Hybrid intent retrieval | Get scored candidate intents                      | `message_embedding`, `lexical_features`, Intent catalog | list of `IntentCandidate` (lightweight)  |
| P4.3 | Decide canonical intent | Merge sensor’s `new_intent` with hybrid retrieval | `SituationalSnapshot`, list of `IntentCandidate`        | `canonical_intent_label`, `intent_score` |

You can keep `IntentCandidate` as `dict` or `tuple[Intent, float]` at first.

#### 4.3 Rule retrieval + selection strategy

| ID   | Substep                       | Goal                                             | Inputs                                                             | Outputs                               |
| ---- | ----------------------------- | ------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------- |
| P4.4 | Build rule retrieval query    | Capture situation for rule matching              | `SituationalSnapshot`, `canonical_intent_label`, `situation_facts` | `RuleRetrievalQuery` (str or dict)    |
| P4.5 | Hybrid rule retrieval         | Get scored rule candidates **by condition_text** | `RuleRetrievalQuery`, rule index, `message_embedding`              | list of `RuleCandidate` (lightweight) |
| P4.6 | Apply rule selection strategy | Dynamically choose how many rules to keep        | `RuleCandidate` list, `SelectionStrategiesConfig.rule`             | `selected_rule_candidates` (list)     |

* Retrieval is **only** on `Rule.condition_text` (your preference).
* `RuleCandidate` can start as `tuple[Rule, float]`.
* `SelectionStrategiesConfig.rule` defines which strategy to use (e.g. `adaptive_k`).

#### 4.4 Scenario retrieval + selection strategy

| ID   | Substep                           | Goal                                                    | Inputs                                                         | Outputs                                   |
| ---- | --------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------- |
| P4.7 | Build scenario retrieval query    | Text for scenario matching                              | `SituationalSnapshot`, `canonical_intent_label`                | `ScenarioRetrievalQuery`                  |
| P4.8 | Hybrid scenario retrieval         | Get scored scenarios                                    | `ScenarioRetrievalQuery`, scenario index                       | list of `ScenarioCandidate` (lightweight) |
| P4.9 | Apply scenario selection strategy | Dynamically choose how many scenario candidates to keep | `ScenarioCandidate` list, `SelectionStrategiesConfig.scenario` | `selected_scenario_candidates`            |

Selection strategies:

* run **after retrieval**,
* before LLM rule filtering or scenario orchestration.

Examples:

* `adaptive_k` for rules (general purpose),
* `entropy` for scenarios (keep more when scores are flat).

> **📊 Observability Note – Intent Registry:**
> The intent retrieval mechanism (P4.2–P4.3) can feed into a business-facing **Intent Registry** for analytics purposes. This registry enables:
> * **Intent heatmaps**: "60% of users trigger 'refund_request' intent"
> * **Bottleneck detection**: "Users abandon at step 3 of refund flow"
> * **Few-shot improvement**: Store example phrases per intent for better retrieval accuracy
>
> The Intent Registry is an **observability layer**, not a runtime enforcement mechanism. It's documented separately from the core pipeline.

---

### Phase 5 – Rule selection (filtering + relationships)

**Goal:** from `selected_rule_candidates`, get final `applied_rules` using:

* scope & lifecycle filters,
* optional LLM rule filter,
* rule relationships.

| ID   | Substep                               | Goal                                             | Inputs                                          | Outputs                                |
| ---- | ------------------------------------- | ------------------------------------------------ | ----------------------------------------------- | -------------------------------------- |
| P5.1 | Pre-filter rules by scope & lifecycle | Remove disabled, cooled-down, out-of-scope rules | `selected_rule_candidates`, `SessionState`      | `scoped_rule_candidates` (lightweight) |
| P5.2 | Optional LLM rule filter              | Ask LLM which rules truly apply                  | `scoped_rule_candidates`, `SituationalSnapshot` | `MatchedRule` list (lightweight)       |
| P5.3 | Relationship expansion for rules      | Apply rule→rule relationships                    | `MatchedRule` list, `Relationship` model        | `applied_rules: list[Rule]`            |

Notice:

* We **first** do retrieval + selection strategy → `selected_rule_candidates`.
* Then use optional LLM to say “APPLIES / NOT_RELATED / UNSURE”.
* **Only after we’re confident** in chosen rules do we expand via relationships (your requirement: “relationship expansion should be made only after rules to be applied are finally chosen with maximal certainty”).

---

### Phase 6 – Scenario orchestration & next-state decisions

**Goal:** decide what to do with scenarios, independent of rules:

* start / continue / pause / complete / cancel,
* step transitions,
* which scenarios **contribute** to this turn’s response.

A customer can be in **several scenarios at once**, and a single answer can mix contributions from multiple scenarios (questions, tool results, etc.).

| ID   | Substep                                 | Goal                                                                       | Inputs                                                                                                                  | Outputs                                  |
| ---- | --------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| P6.1 | Build scenario selection context        | Combine candidates, existing instances, relationships, rules               | `selected_scenario_candidates`, `SessionState`, `applied_rules`, `Relationship`s                                        | `ScenarioSelectionContext` (lightweight) |
| P6.2 | Scenario lifecycle decisions            | For each candidate + active scenario: START/CONTINUE/PAUSE/COMPLETE/CANCEL | `ScenarioSelectionContext`, `SituationalSnapshot`, `canonical_intent_label`                                             | list of `ScenarioLifecycleDecision`      |
| P6.3 | Step transition evaluation per scenario | For each ACTIVE scenario: stay or move to next step                        | ACTIVE `ScenarioInstance`s, `ScenarioTransition`s, `SituationalSnapshot`, `CustomerDataStore`, `canonical_intent_label` | list of `ScenarioStepTransitionDecision` |
| P6.4 | Determine scenario contributions        | Decide how each scenario wants to participate in this turn                 | lifecycle & step decisions, step metadata, `applied_rules`                                                              | `ScenarioContributionPlan`               |

Key points:

* We **don't force** a single "focus scenario" per turn.
* `ScenarioContributionPlan` says, for each ACTIVE scenario:

  * does it want to **ask** something this turn?
  * does it want to **inform** something?
  * does it need to **confirm** something?
  * is there an **action hint** (like "we must now call `order_lookup`")?

These contributions feed into response planning.

**Step skipping / Re-localization (P6.3):**

When evaluating step transitions, the system should detect if the user already has all required data to **skip intermediate steps**. This commonly happens when:
- User provides multiple pieces of information in one message
- Data from previous conversations is already in `CustomerDataStore`
- Tool results from Phase 7 (previous turn) already filled required variables

Example:
```
Scenario: "Refund Flow"
Steps: [collect_order_id] → [collect_reason] → [confirm_refund] → [process]

User message: "I want a refund for order #123 because the item was damaged"

Without step skipping: Start at [collect_order_id], ask for order ID (redundant)
With step skipping:    Jump directly to [confirm_refund] (we have order_id + reason)
```

The transition evaluation (P6.3) checks:
1. What variables does each downstream step require?
2. Which of those are already in `CustomerDataStore` or extractable from current message?
3. What's the furthest valid step we can reach?

> **Note:** This is NOT the same as scenario migration (handling version changes). For migration when scenario structure changes between turns, see [scenario-update-methods.md](./scenario-update-methods.md).

---

### Phase 7 – Tenant tool scheduling & execution

**Goal:** run tenant tools **only** when:

* they’re bound to **rules** or **scenario steps**,
* they’re in the right `when` (BEFORE/DURING/AFTER),
* they’re needed to fill variables for this turn.

| ID   | Substep                                                   | Goal                                       | Inputs                                                      | Outputs                                |
| ---- | --------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------- | -------------------------------------- |
| P7.1 | Collect tool bindings from contributing scenarios + rules | Know which tools are eligible now          | `ScenarioContributionPlan`, scenario steps, `applied_rules` | list of `ToolBinding`                  |
| P7.2 | Compute required variables for this turn                  | Which vars should be filled via tools      | `ToolBinding`, `applied_rules`, step metadata               | set of `required_var_names` (set[str]) |
| P7.3 | Resolve from CustomerDataStore / Session                  | Use already-known data first               | updated `CustomerDataStore`, `SessionState`                 | `known_vars`, `missing_vars` (dicts)   |
| P7.4 | Determine tool calls allowed now                          | Respect scenario scheduling for tools      | `ToolBinding`, `missing_vars`, scenario steps               | list of `(tool_id, var_names_to_fill)` |
| P7.5 | Execute tenant tools                                      | Fetch domain data                          | list of tool calls                                          | tool results (var_name → value)        |
| P7.6 | Merge tool results into engine variables                  | Build `engine_variables`                   | `known_vars`, tool results                                  | `engine_variables` (dict[str, Any])    |
| P7.7 | Keep future-scheduled tools for later                     | Do not execute tools meant for later steps | scenario graphs & bindings                                  | –                                      |

We keep **one pass** per turn here; if later you want a multi-iteration silent loop (try more tools if still missing data), you can add it around P7.2-P7.6.

---

### Phase 8 – Response planning (multi-scenario, templates optional)

**Goal:** build a `ResponsePlan` that:

* combines contributions from multiple scenarios,
* respects `applied_rules`,
* optionally uses step-level templates.

| ID   | Substep                                 | Goal                                             | Inputs                                                                                 | Outputs                                               |
| ---- | --------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| P8.1 | Determine global response type          | Overall type: ASK / ANSWER / MIXED / ESCALATE    | `ScenarioContributionPlan`, `applied_rules`, `SituationalSnapshot`, `engine_variables` | `global_response_type`                                |
| P8.2 | Collect step-level templates (optional) | Resolve templates tied to contributing steps     | contributing scenario steps                                                            | list of `TemplateRef` (some may be `None`)            |
| P8.3 | Build per-scenario contribution plan    | Clarify what each scenario wants in this message | `ScenarioContributionPlan`, templates, `engine_variables`, `applied_rules`             | list of per-scenario contribution items (lightweight) |
| P8.4 | Synthesize global ResponsePlan          | Merge scenario contributions into one plan       | per-scenario contribution items, `global_response_type`                                | `ResponsePlan`                                        |
| P8.5 | Inject explicit constraints into plan   | Inject “must/do not” from rules and step logic   | `ResponsePlan`, `applied_rules`, scenario metadata                                     | refined `ResponsePlan`                                |

* A step **may or may not** have a template:

  * **if yes**: that template shapes the structure of that scenario's portion.
  * **if no**: we rely on `ResponsePlan.bullet_points`, `must_include`, `must_avoid`.

> **🔮 FUTURE – Template Associations:**
> Currently, templates are optionally attached to scenario steps. A future enhancement would allow **templates to be associated with rules** as well, enabling:
> * Rule-specific response formatting (e.g., a "refund_policy" rule could have a structured template)
> * Consistent phrasing across different scenarios when the same rule fires
> * Template inheritance (step template → rule template → default)
>
> This is not implemented yet.

---

### Phase 9 – Generation (main LLM)

| ID   | Substep                         | Goal                                                      | Inputs                                                                                                    | Outputs                                |
| ---- | ------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| P9.1 | Build generation prompt         | Final prompt: scenarios, rules, variables, plan, glossary | `ResponsePlan`, scenario steps, `engine_variables`, `applied_rules`, conversation history, `GlossaryView` | `prompt`                               |
| P9.2 | Call answer LLM                 | Produce answer + semantic outcome categories              | `prompt`, answer `LlmTaskConfig`                                                                          | `raw_answer`, `llm_categories`         |
| P9.3 | Post-format for channel         | Adapt for WhatsApp/email/webchat/SMS/etc.                 | `raw_answer`, `TurnInput.channel`                                                                         | `channel_answer`                       |
| P9.4 | Append LLM categories           | Add LLM's semantic categories to TurnOutcome              | `llm_categories`, `TurnOutcome` (in progress)                                                             | Updated `TurnOutcome.categories`       |
| P9.5 | Set resolution from state       | Determine overall turn resolution                         | `global_response_type`, `TurnOutcome.categories`                                                          | `TurnOutcome.resolution`               |

**LLM semantic category output (P9.2):**

The generation LLM outputs **both** the response text **and** any semantic categories it identifies:

```json
{
  "response": "I'm sorry, I don't have information about parking. Also, we don't offer flight booking services.",
  "categories": [
    {
      "category": "KNOWLEDGE_GAP",
      "details": "parking availability not in knowledge base"
    },
    {
      "category": "OUT_OF_SCOPE",
      "details": "flight booking not offered by this business"
    }
  ]
}
```

The LLM only outputs from these 4 semantic categories:
- `KNOWLEDGE_GAP` - "I should know this but don't"
- `CAPABILITY_GAP` - "I can't perform this action"
- `OUT_OF_SCOPE` - "Not what this business handles"
- `SAFETY_REFUSAL` - "Refusing for safety reasons"

**Pipeline categories already set before Phase 9:**

By the time we reach generation, the pipeline has already appended:
- **Phase 7**: `SYSTEM_ERROR` (if tool failed)
- **Phase 8**: `AWAITING_USER_INPUT` (if `global_response_type == ASK`)

**Resolution determination (P9.5):**

| State | Resolution |
|-------|------------|
| `global_response_type == ESCALATE` | `REDIRECTED` |
| `global_response_type == ASK` | `PARTIAL` |
| Any category present | `PARTIAL` or `UNRESOLVED` (based on severity) |
| No categories, answer delivered | `RESOLVED` |

---

### Phase 10 – Enforcement & guardrails

**Goal:** enforce **hard constraints** and policy after generation.

| ID     | Substep                                       | Goal                                                           | Inputs                                                               | Outputs                               |
| ------ | --------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------- |
| P10.1a | Collect matched hard constraints              | Hard constraints from rules that matched this turn             | `applied_rules`                                                      | `matched_hard_rules` (list[Rule])     |
| P10.1b | Always add GLOBAL hard constraints            | **All** GLOBAL `is_hard_constraint=True` rules, even unmatched | ConfigStore query: `scope=GLOBAL, is_hard_constraint=True`           | `rules_to_enforce` (list[Rule])       |
| P10.2  | Extract variables from answer                 | Understand what the answer committed to                        | `channel_answer`                                                     | `response_variables` (dict)           |
| P10.3  | Build enforcement variable view               | Merge profile + session + response                             | `CustomerDataStore`, `SessionState`, `response_variables`            | `enforcement_vars` (dict)             |
| P10.4  | Evaluate deterministic constraints (Lane 1)   | Evaluate `enforcement_expression` per rule                     | `rules_to_enforce` with `enforcement_expression`, `enforcement_vars` | deterministic violations (list)       |
| P10.5  | Evaluate subjective constraints (Lane 2)      | LLM-as-Judge for rules without expressions                     | `rules_to_enforce` without expressions, `channel_answer`             | subjective violations (list)          |
| P10.6  | Optional relevance/grounding checks           | Check relevant & grounded answers                              | user message, retrieved docs, answer, `TurnOutcome.categories`       | extra violations or pass              |
| P10.7  | Aggregate violations & decide remediation     | Decide pass/fail & retry/fallback                              | all violations, enforcement mode                                     | `EnforcementResult`                   |
| P10.8  | Optional regeneration                         | Ask LLM to fix answer                                          | `EnforcementResult`, `prompt`, `channel_answer`                      | repaired `channel_answer` or fallback |
| P10.9  | Append POLICY_RESTRICTION if blocked          | Add category if enforcement blocked & used fallback            | `EnforcementResult`, fallback used?                                  | Updated `TurnOutcome.categories`      |
| P10.10 | Adjust resolution if needed                   | Update resolution based on final state                         | `TurnOutcome`, fallback used?                                        | Final `TurnOutcome.resolution`        |

**Important notes:**

* **P10.1b (Always-enforce GLOBAL):** GLOBAL hard constraints are safety guardrails that must be checked on **every** response, regardless of whether they matched the retrieval. Example: "Never mention competitor X" must be enforced even on off-topic conversations.

* **P10.5 (Lane 2 - LLM-as-Judge):** For rules that have `is_hard_constraint=True` but no `enforcement_expression`, the LLM is asked to judge whether the response complies with the rule's `action_text`. Example: A rule with `action_text="Maintain professional and empathetic tone"` cannot be expressed as code, so the LLM evaluates compliance.

* **P10.6 (Relevance bypass):** If `TurnOutcome.categories` contains `KNOWLEDGE_GAP`, `OUT_OF_SCOPE`, `CAPABILITY_GAP`, or `SAFETY_REFUSAL`, skip the relevance check. These are valid responses that have low embedding similarity to the query but are semantically appropriate (legitimate refusals/limitations).

* **P10.9 (POLICY_RESTRICTION):** If enforcement fails after retries and we use a fallback template, append:
  ```python
  OutcomeCategory(
      source="PIPELINE",
      category="POLICY_RESTRICTION",
      details=f"Rule '{violated_rule.name}' blocked: {violation_details}"
  )
  ```

---

### Phase 11 – Persistence, audit & output

| ID    | Substep                             | Goal                                                  | Inputs                                                                                                                        | Outputs                 |
| ----- | ----------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| P11.1 | Update SessionState                 | Apply lifecycle & transitions, store canonical intent | `SessionState`, `ScenarioLifecycleDecision`s, `ScenarioStepTransitionDecision`s, `engine_variables`, `canonical_intent_label` | new `SessionState`      |
| P11.2 | Persist SessionState                | Save to session store                                 | new `SessionState`                                                                                                            | durable session row     |
| P11.3 | Persist CustomerDataStore           | Commit `persistent_updates`                           | updated `CustomerDataStore`                                                                                                   | durable customer record |
| P11.4 | Record TurnRecord                   | Full trace of the turn                                | `TurnContext`, `SituationalSnapshot`, `applied_rules`, scenario decisions, `EnforcementResult`, timings, token usage          | `TurnRecord`            |
| P11.5 | Optional long-term memory ingestion | Store summaries/facts for RAG                         | user message, answer, scenario info                                                                                           | memory entries          |
| P11.6 | Build final API response            | Return to caller                                      | `channel_answer`, metadata (session info, etc.)                                                                               | HTTP/RPC response       |
| P11.7 | Emit metrics / traces               | Observability                                         | timings, token usage, error flags                                                                                             | metrics/traces          |

> **🔮 FUTURE – Memory Layer Integration (Zep, Graphiti):**
> P11.5 currently supports basic memory ingestion. A future enhancement would integrate dedicated memory layers like **Zep** or **Graphiti** to enable:
> * **Long-term personalization**: "User mentioned they're not available on weekends" → remembered months later when scheduling a call
> * **Fact extraction and graph storage**: Build knowledge graphs from conversations
> * **Temporal memory**: "User was frustrated last week about shipping delays" → proactive acknowledgment
> * **Cross-session context**: Information flows across sessions without explicit session variables
>
> This would enhance Phase 4 (Retrieval) with memory retrieval alongside rules/scenarios, and Phase 9 (Generation) with personalized context injection.
>
> This is not implemented yet – an area to explore.

---
