## 3. Data models & contracts

### 3.0 Class vs lightweight summary

To integrate your “not everything must be a class” constraint:

* **Core Pydantic models (now)** – strong contracts you'll depend on a lot:

  * `TurnInput`
  * `TurnContext`
  * `CustomerDataField`
  * `VariableEntry`
  * `CustomerDataStore`
  * `CustomerSchemaMaskEntry`
  * `CustomerSchemaMask`
  * `GlossaryItem`
  * `CandidateVariableInfo`
  * `SituationalSnapshot`
  * `Rule`
  * `Relationship`
  * `Scenario`
  * `ScenarioStep`
  * `ScenarioTransition`
  * `ScenarioInstance`
  * `SessionState`
  * `ResponsePlan`
  * `ConstraintViolation`
  * `EnforcementResult`
  * `OutcomeCategory`
  * `TurnOutcome`
  * `TurnRecord`

* **Lightweight structs for v1 (dict/tuple/TypedDict)** – can be upgraded later:

  * `IntentCandidate`
  * `RuleCandidate`
  * `ScenarioCandidate`
  * `RuleRetrievalQuery` / `ScenarioRetrievalQuery`
  * `CustomerDataUpdate`
  * `ScenarioSelectionContext`
  * `ScenarioContribution`
  * `ScenarioContributionPlan`
  * `SelectionConfig`
  * `SelectionStrategiesConfig`
  * `ScoredItem` / `SelectionResult`
  * Any per-scenario contribution items used inside ResponsePlan.

I’ll mark them accordingly.

---

### 3.1 Core runtime inputs

#### 3.1.1 TurnInput **[Core Pydantic]**

```python
class TurnInput(BaseModel):
    tenant_id: str
    agent_id: str

    channel: Literal["phone", "whatsapp", "webchat", "email", "api"]
    channel_id: str                # phone number, webchat session ID, email, etc.

    customer_id: str | None = None # optional if upstream already knows the customer

    message: str
    metadata: dict[str, Any] = {}
```

#### 3.1.2 TurnContext **[Core Pydantic]**

```python
class TurnContext(BaseModel):
    input: TurnInput

    session: SessionState
    customer_data: CustomerDataStore

    pipeline_config: "PipelineConfig"              # can be a Pydantic model or dict
    customer_data_fields: dict[str, CustomerDataField]
    llm_tasks: dict[str, "LlmTaskConfig"]          # lightweight, per-task configs
    glossary: dict[str, GlossaryItem]
```

---

### 3.2 Customer Data Architecture

This section describes the **two-part architecture** for customer data:

| Component | Purpose | Scope |
|-----------|---------|-------|
| **CustomerDataField** | Schema definition | Tenant + Agent |
| **CustomerDataStore** | Runtime values per customer | Customer |
| **CustomerSchemaMask** | Privacy-safe view for LLM | Turn |

**Key distinction:**
- **CustomerDataField** = "What fields exist?" (schema, defined at agent configuration time)
- **CustomerDataStore** = "What values does this customer have?" (runtime, per-customer)
- **CustomerSchemaMask** = "What does the LLM see?" (turn-scoped, no actual values)

The LLM never sees raw customer values during situational sensing. Instead, it receives a **CustomerSchemaMask** showing:
- Which fields exist for this agent
- Whether each field has a value (boolean `exists`)
- The field's type and scope

This allows schema-aware extraction without data leakage.

#### 3.2.1 CustomerDataField **[Core Pydantic]**

**Schema definition** - defines what customer data fields exist for an agent.

```python
class CustomerDataField(BaseModel):
    key: str                           # "first_name", "email", "subscription_plan", ...
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
    type: Literal["string", "number", "boolean", "datetime", "json"]

    persist: bool = True
    description: str | None = None
```

#### 3.2.2 VariableEntry & CustomerDataStore **[Core Pydantic]**

**Runtime storage** - holds actual customer values with history and confidence tracking.

```python
class VariableEntry(BaseModel):
    value: Any
    type: Literal["string", "number", "boolean", "datetime", "json"]

    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
    last_updated_at: datetime
    source: Literal["USER", "TOOL", "INFERENCE", "SYSTEM"]
    confidence: float = 1.0
    history: list[dict[str, Any]] = []  # [{value, timestamp, source}, ...]
```

```python
class CustomerDataStore(BaseModel):
    tenant_id: str
    customer_key: str

    variables: dict[str, VariableEntry]
```

#### 3.2.3 CustomerSchemaMask **[Core Pydantic]**

**Privacy-safe view for LLM** - shows schema structure without exposing actual values.

The `CustomerSchemaMask` is built from `CustomerDataField` definitions + `CustomerDataStore` state:
- Keys come from `CustomerDataField.key`
- `scope` and `type` come from `CustomerDataField`
- `exists` = whether `CustomerDataStore.variables` has a value for this key

```python
class CustomerSchemaMaskEntry(BaseModel):
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
    type: Literal["string", "number", "boolean", "datetime", "json"]
    exists: bool                      # True if value currently stored
```

```python
class CustomerSchemaMask(BaseModel):
    variables: dict[str, CustomerSchemaMaskEntry]
```

---

### 3.3 Glossary **[Core Pydantic]**

```python
class GlossaryItem(BaseModel):
    id: str
    tenant_id: str
    agent_id: str

    term: str                         # e.g. "VIP"
    description: str                  # what it means for this business
    usage_notes: str | None = None    # how the agent should talk about it

    related_variable_keys: list[str] = []   # optional
    example_phrases: list[str] = []        # optional, for recognition
```

👉 Opinion: GlossaryItem is **semantic + UX**, not logic.
The logic (“VIP if spend > 1000”) should live in expressions (rules/steps/transitions) using CustomerDataStore variables.

---

### 3.4 Situational Sensor

#### 3.4.1 CandidateVariableInfo **[Core Pydantic]**

```python
class CandidateVariableInfo(BaseModel):
    value: Any
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
    is_update: bool = False
```

#### 3.4.2 SituationalSnapshot **[Core Pydantic]**

```python
class SituationalSnapshot(BaseModel):
    language: str

    previous_intent_label: str | None
    intent_changed: bool
    new_intent_label: str | None
    new_intent_text: str | None

    topic_changed: bool
    tone: str
    frustration_level: Literal["low", "medium", "high"] | None = None

    situation_facts: list[str] = []   # mini rule-like statements

    candidate_variables: dict[str, CandidateVariableInfo] = {}
```

---

### 3.5 Object Selection Pipeline

Every retrievable object type in Focal goes through a **unified selection pipeline** after initial vector/hybrid retrieval. This pipeline is configurable per object type and consists of two stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OBJECT SELECTION PIPELINE                             │
│                    (Applied per object type: rules, scenarios, intents)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Candidates from vector/hybrid retrieval                                    │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STAGE 1: RERANKING (optional)                                      │   │
│   │  ┌───────────────────────────────────────────────────────────────┐  │   │
│   │  │ • Cross-encoder model rescores query-document pairs           │  │   │
│   │  │ • More accurate than embedding similarity alone               │  │   │
│   │  │ • Providers: Cohere, Jina, Voyage, local CrossEncoder         │  │   │
│   │  │ • Can be disabled per object type                             │  │   │
│   │  └───────────────────────────────────────────────────────────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  STAGE 2: SELECTION STRATEGY                                        │   │
│   │  ┌───────────────────────────────────────────────────────────────┐  │   │
│   │  │ • Analyzes score distribution to decide how many to keep      │  │   │
│   │  │ • Strategies: fixed_k, elbow, adaptive_k, entropy, clustering │  │   │
│   │  │ • Respects min_k / max_k bounds                               │  │   │
│   │  │ • Applies min_score threshold                                 │  │   │
│   │  └───────────────────────────────────────────────────────────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│   Selected objects (ready for filtering/orchestration)                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.5.1 Object Types Using This Pipeline

| Object Type | Retriever Class | Reranking | Strategy |
|-------------|-----------------|-----------|----------|
| **Rules** | `RuleRetriever` | ✅ Recommended | `adaptive_k` |
| **Scenarios** | `ScenarioRetriever` | ❌ Optional | `entropy` |
| **Memory** | `MemoryRetriever` | ✅ Recommended | `clustering` |
| **Intents** | `IntentRetriever` | ✅ Recommended | `elbow` |
| **Templates** *(future)* | `TemplateRetriever` | ❌ Rarely | `fixed_k` |

Each object type has its own reranking + selection configuration under `[pipeline.retrieval.*_selection]`.

#### 3.5.2 Stage 1: Reranking

Reranking uses a **cross-encoder model** to rescore candidates. Unlike embedding similarity (which compares vectors independently), cross-encoders process the query and document together, enabling more accurate relevance judgments.

**When to enable reranking:**
- High-stakes retrieval where precision matters (rules, intents)
- When embedding similarity alone produces false positives
- When you have budget for the additional latency (~50-100ms)

**When to disable reranking:**
- Low-latency requirements
- Object types with small candidate pools
- When embedding quality is already high

**Supported providers:**

| Provider | Model Examples | Notes |
|----------|---------------|-------|
| Cohere | `rerank-english-v3.0`, `rerank-multilingual-v3.0` | Best general-purpose |
| Jina | `jina-reranker-v2-base-multilingual` | Good multilingual support |
| Voyage | `rerank-2` | Optimized for code/technical |
| Local | `cross-encoder/ms-marco-MiniLM-L-6-v2` | No API cost, higher latency |

#### 3.5.3 Stage 2: Selection Strategies

Selection strategies analyze the **score distribution** to dynamically determine how many results to keep, rather than using a fixed top-k.

**Available strategies:**

| Strategy | Algorithm | Best For |
|----------|-----------|----------|
| `fixed_k` | Always return exactly k items | Baseline, predictable behavior |
| `elbow` | Find significant score drop | Clear relevant/irrelevant separation |
| `adaptive_k` | Curvature analysis of score curve | General-purpose retrieval |
| `entropy` | Shannon entropy of score distribution | Ambiguous queries (flat scores → keep more) |
| `clustering` | DBSCAN on scores, top per cluster | Multi-topic queries |

**Strategy selection guidance:**

```
Is there usually a clear "relevant" vs "irrelevant" boundary?
├─ Yes → Use `elbow` or `adaptive_k`
└─ No, scores are often flat
   ├─ Query might match multiple distinct topics → Use `clustering`
   └─ Uncertainty is normal → Use `entropy` (keeps more when unsure)
```

#### 3.5.4 ScoredItem & SelectionResult **[Lightweight]**

For v1, you can use simple tuples/lists:

```python
# v1 suggestion:
ScoredItem = tuple[Any, float]  # (item, score)

SelectionResult = dict[str, Any]  # {"items": list[ScoredItem], "strategy_used": str}
```

If you later want stricter typing:

```python
# optional Pydantic later
class ScoredItem(Generic[T], BaseModel):
    item: T
    score: float

class SelectionResult(Generic[T], BaseModel):
    items: list[ScoredItem[T]]
    strategy_used: str
```

#### 3.5.5 SelectionConfig **[Lightweight]**

Per-object-type configuration combining reranking + selection strategy (matches `[pipeline.retrieval.*_selection]`):

```python
# v1: Can be a simple dict loaded from TOML
SelectionConfig = dict[str, Any]
# {
#     # Reranking stage (optional)
#     "reranking_enabled": bool,
#     "rerank_provider": str | None,   # References [providers.rerank.*]
#     "rerank_top_k": int | None,
#
#     # Selection strategy stage
#     "strategy": str,              # "fixed_k" | "elbow" | "adaptive_k" | "entropy" | "clustering"
#     "min_score": float,
#     "max_k": int,
#     "min_k": int,                 # Optional, defaults to 1
# }
```

Later, if stricter typing is needed:

```python
class SelectionConfig(BaseModel):
    # Reranking stage
    reranking_enabled: bool = False
    rerank_provider: str | None = None
    rerank_top_k: int | None = None

    # Selection strategy stage
    strategy: Literal["fixed_k", "elbow", "adaptive_k", "entropy", "clustering"] = "adaptive_k"
    min_score: float = 0.5
    max_k: int = 20
    min_k: int = 1
```

---

### 3.6 Rules, Relationships, Scenarios & Steps

#### 3.6.1 ToolBinding **[Core Pydantic]**

```python
class ToolBinding(BaseModel):
    tool_id: str                                      # e.g. "order_lookup"
    when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"]
    required_variables: list[str] = []                # variable names this tool can fill
```

#### 3.6.2 Rule **[Core Pydantic]**

```python
class Rule(BaseModel):
    id: str
    tenant_id: str
    agent_id: str

    name: str
    description: str | None = None

    # Retrieval target
    condition_text: str        # used for hybrid retrieval (semantic + lexical)
    action_text: str           # guidance for planner/LLM

    # Scope
    scope: Literal["GLOBAL", "SCENARIO", "STEP"]
    scope_id: str | None       # None, scenario_id, or "scenario_id#step_id"

    # Enforcement
    is_hard_constraint: bool = False
    enforcement_expression: str | None = None

    # Tools
    tool_bindings: list[ToolBinding] = []

    # Lifecycle
    priority: int = 0
    max_fires_per_session: int | None = None
    cooldown_turns: int = 0

    enabled: bool = True
```

#### 3.6.3 Relationship **[Core Pydantic]**

```python
class Relationship(BaseModel):
    id: str
    tenant_id: str
    agent_id: str

    source_type: Literal["RULE", "SCENARIO", "STEP"]
    source_id: str

    target_type: Literal["RULE", "SCENARIO", "STEP"]
    target_id: str

    kind: Literal["depends_on", "implies", "excludes", "specializes", "related"]

    weight: float | None = None
    metadata: dict[str, Any] = {}
```

#### 3.6.4 Scenario, ScenarioStep, ScenarioTransition **[Core Pydantic]**

```python
class Scenario(BaseModel):
    id: str
    tenant_id: str
    agent_id: str

    name: str
    description: str

    version: int = 1
    entry_step_id: str

    entry_examples: list[str] = []
    tags: list[str] = []
```

```python
class ScenarioStep(BaseModel):
    id: str
    tenant_id: str
    agent_id: str
    scenario_id: str

    name: str
    description: str

    step_type: Literal["QUESTION", "ACTION", "LOGIC"]

    template_id: str | None = None

    rule_ids: list[str] = []
    tool_bindings: list[ToolBinding] = []

    completion_expression: str | None = None
```

```python
class ScenarioTransition(BaseModel):
    id: str
    tenant_id: str
    agent_id: str
    scenario_id: str

    from_step_id: str
    to_step_id: str

    intent_label: str | None = None
    condition_expression: str | None = None
    priority: int = 0

    description: str | None = None
```

> **🔄 Config Versioning Note:**
> All agent configuration (Rules, Scenarios, Steps, Transitions, CustomerDataFields, Glossary) should be versioned at the **agent level**. When configuration changes:
> * Bump the agent's `config_version`
> * Store old versions for rollback and audit
> * Active sessions continue with their loaded config until the next turn
> * Scenario migration handles customers mid-journey when scenarios change (see migration module)
>
> This ensures reproducibility, rollback capability, and clean migration paths.

---

### 3.7 Scenario state & orchestration

#### 3.7.1 ScenarioInstance & SessionState **[Core Pydantic]**

```python
class ScenarioInstance(BaseModel):
    scenario_id: str
    current_step_id: str
    status: Literal["ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"]
    started_at_turn: int
    updated_at_turn: int
```

```python
class SessionState(BaseModel):
    tenant_id: str
    agent_id: str
    session_id: str

    scenarios: list[ScenarioInstance] = []

    last_intent_label: str | None = None

    variables: dict[str, Any] = {}          # session-scoped scratchpad

    rule_fire_counts: dict[str, int] = {}
    rule_last_turn: dict[str, int] = {}

    turn_index: int = 0
```

#### 3.7.2 Lifecycle & step decisions **[Core Pydantic]**

```python
class ScenarioLifecycleDecision(BaseModel):
    scenario_id: str
    action: Literal["START", "CONTINUE", "PAUSE", "COMPLETE", "CANCEL"]
    reason: str | None = None
```

```python
class ScenarioStepTransitionDecision(BaseModel):
    scenario_id: str
    from_step_id: str
    to_step_id: str | None    # None = stay
    reason: str | None = None
```

#### 3.7.3 ScenarioContribution & Plan **[Lightweight]**

For v1, this can be simple dicts:

```python
# v1 suggestion
ScenarioContribution = dict[str, Any]
# {
#   "scenario_id": str,
#   "step_id": str,
#   "contribution_type": "ASK" | "INFORM" | "CONFIRM" | "ACTION_HINT",
#   "description": str,
# }

ScenarioContributionPlan = dict[str, Any]
# {"contributions": list[ScenarioContribution]}
```

Later you can turn them into Pydantic if you want:

```python
class ScenarioContribution(BaseModel):
    scenario_id: str
    step_id: str
    contribution_type: Literal["ASK", "INFORM", "CONFIRM", "ACTION_HINT"]
    description: str

class ScenarioContributionPlan(BaseModel):
    contributions: list[ScenarioContribution]
```

---

### 3.8 Retrieval & planning structs

These are good candidates for **lightweight v1 types**.

#### 3.8.1 Candidates

```python
# v1 suggestions:
RuleCandidate = tuple[Rule, float]      # (rule, score)
ScenarioCandidate = tuple[Scenario, float]  # (scenario, score)

IntentCandidate = dict[str, Any]
# {"intent": IntentObjOrId, "score": float}
```

If you want Pydantic later:

```python
class RuleCandidate(BaseModel):
    rule: Rule
    score: float

class ScenarioCandidate(BaseModel):
    scenario: Scenario
    score: float
```

#### 3.8.2 ResponsePlan **[Core Pydantic]**

```python
class ResponsePlan(BaseModel):
    global_response_type: Literal["ASK", "ANSWER", "MIXED", "CONFIRM", "REFUSE", "ESCALATE"]

    template_ids: list[str] = []    # from multiple steps, can be empty
    bullet_points: list[str] = []   # high-level items in the answer
    must_include: list[str] = []    # constraints from rules/scenarios
    must_avoid: list[str] = []      # things not to mention

    # optional: scenario-specific notes, can embed lightweight plan
    scenario_contributions: dict[str, Any] = {}
```

You can embed the lightweight `ScenarioContributionPlan` there (`scenario_contributions`).

---

### 3.9 Enforcement & audit

#### 3.9.1 ConstraintViolation & EnforcementResult **[Core Pydantic]**

```python
class ConstraintViolation(BaseModel):
    rule_id: str | None
    violation_type: str          # "expression_failed", "judge_failed", "relevance_failed", ...
    details: str
    lane: Literal["deterministic", "subjective", "global"]
```

```python
class EnforcementResult(BaseModel):
    passed: bool
    violations: list[ConstraintViolation] = []

    can_retry: bool = False
    hints_for_regeneration: list[str] = []
```

#### 3.9.2 OutcomeCategory & TurnOutcome **[Core Pydantic]**

Captures how well the agent addressed the user's need. Supports **multiple categories per turn** to handle multi-scenario and multi-intent messages.

**Key design decisions:**
- **Turn-level resolution**: One `resolution` per turn (RESOLVED/PARTIAL/UNRESOLVED/REDIRECTED)
- **Multiple categories**: A turn can have 0..N `OutcomeCategory` entries (e.g., knowledge gap for one question, out-of-scope for another)
- **Scenario resolution is separate**: Track scenario completion via `ScenarioInstance.status`, not `TurnOutcome`

```python
class OutcomeCategory(BaseModel):
    """A single categorized outcome within a turn."""

    source: Literal["PIPELINE", "GENERATION"]

    category: Literal[
        # Pipeline-determined (set by code, deterministic)
        "AWAITING_USER_INPUT",   # Phase 8: response_type == ASK
        "SYSTEM_ERROR",          # Phase 7: tool/API failure
        "POLICY_RESTRICTION",    # Phase 10: enforcement blocked

        # LLM-determined (semantic interpretation)
        "KNOWLEDGE_GAP",         # "I should know this but don't"
        "CAPABILITY_GAP",        # "I can't perform this action"
        "OUT_OF_SCOPE",          # "Not what this business handles"
        "SAFETY_REFUSAL",        # "Refusing for safety reasons"
    ]

    scenario_id: str | None = None   # Which scenario (if scoped)
    step_id: str | None = None       # Which step (if scoped)
    details: str | None = None       # Explanation for debugging/analytics


class TurnOutcome(BaseModel):
    """Overall turn outcome with granular categories."""

    resolution: Literal[
        "RESOLVED",      # User need fully addressed
        "PARTIAL",       # Partially addressed, more needed
        "UNRESOLVED",    # Could not address
        "REDIRECTED",    # Sent elsewhere (escalation, different channel)
    ]

    categories: list[OutcomeCategory] = []
```

**Category ownership:**

| Category | Source | Set By | Example |
|----------|--------|--------|---------|
| `AWAITING_USER_INPUT` | `PIPELINE` | Phase 8 (planning) | Need order ID to proceed |
| `SYSTEM_ERROR` | `PIPELINE` | Phase 7 (tool execution) | Tool 'order_lookup' timed out |
| `POLICY_RESTRICTION` | `PIPELINE` | Phase 10 (enforcement) | Rule 'refund_limit' blocked |
| `KNOWLEDGE_GAP` | `GENERATION` | Phase 9 (LLM) | "I don't know if we have parking" |
| `CAPABILITY_GAP` | `GENERATION` | Phase 9 (LLM) | "I can't book flights" |
| `OUT_OF_SCOPE` | `GENERATION` | Phase 9 (LLM) | "We don't offer insurance" |
| `SAFETY_REFUSAL` | `GENERATION` | Phase 9 (LLM) | "I can't help with that request" |

**Business actions by category:**

| Category | Business Action |
|----------|-----------------|
| `AWAITING_USER_INPUT` | Normal flow - not a problem |
| `SYSTEM_ERROR` | Fix reliability, add retries |
| `POLICY_RESTRICTION` | Review if policy too strict |
| `KNOWLEDGE_GAP` | Add to knowledge base |
| `CAPABILITY_GAP` | Add tool/integration |
| `OUT_OF_SCOPE` | Expected, maybe add redirect |
| `SAFETY_REFUSAL` | Expected, good behavior |

**How categories accumulate during pipeline:**

```
Phase 7 (Tool Execution):
    │   Tool failed? → categories.append(OutcomeCategory(
    │       source="PIPELINE", category="SYSTEM_ERROR",
    │       details="Tool 'order_lookup' timed out after 5000ms"
    │   ))
    ▼
Phase 8 (Planning):
    │   response_type == ASK? → categories.append(OutcomeCategory(
    │       source="PIPELINE", category="AWAITING_USER_INPUT",
    │       scenario_id="kyc_flow", step_id="collect_id"
    │   ))
    ▼
Phase 9 (Generation):
    │   LLM appends semantic categories (cannot override PIPELINE ones):
    │   → OutcomeCategory(source="GENERATION", category="KNOWLEDGE_GAP",
    │       details="parking availability not in knowledge base")
    │   → OutcomeCategory(source="GENERATION", category="OUT_OF_SCOPE",
    │       details="flight booking not offered")
    ▼
Phase 10 (Enforcement):
    │   Enforcement blocked? → categories.append(OutcomeCategory(
    │       source="PIPELINE", category="POLICY_RESTRICTION",
    │       details="Rule 'refund_limit' failed: amount 75 > max 50"
    │   ))
    ▼
Final TurnOutcome:
    resolution: PARTIAL
    categories: [
        {source: PIPELINE, category: AWAITING_USER_INPUT, scenario_id: "kyc_flow"},
        {source: GENERATION, category: KNOWLEDGE_GAP, details: "parking availability"},
        {source: GENERATION, category: OUT_OF_SCOPE, details: "flight booking"},
    ]
```

> **Important:** Scenario completion rate is tracked via `ScenarioInstance.status == COMPLETED`, **not** via `TurnOutcome`. These are separate concerns: turn success ≠ scenario success.

#### 3.9.3 TurnRecord **[Core Pydantic]**

```python
class TurnRecord(BaseModel):
    tenant_id: str
    agent_id: str
    session_id: str
    turn_index: int
    timestamp: datetime

    channel: str
    user_message: str
    model_response: str

    situational_snapshot: SituationalSnapshot

    matched_rule_ids: list[str]
    enforced_rule_ids: list[str]

    scenario_lifecycle: list[ScenarioLifecycleDecision]
    scenario_step_transition: list[ScenarioStepTransitionDecision]

    enforcement_result: EnforcementResult

    # Turn outcome for observability (categories accumulate through pipeline)
    outcome: TurnOutcome

    timings_ms: dict[str, float]
    token_usage: dict[str, int]
```

**Outcome tracking:**

The `outcome` field contains:
- `resolution`: Overall turn resolution (RESOLVED/PARTIAL/UNRESOLVED/REDIRECTED)
- `categories`: List of `OutcomeCategory` entries accumulated during the pipeline

Categories are appended by different phases:
- **Phase 7**: `SYSTEM_ERROR` (tool failures)
- **Phase 8**: `AWAITING_USER_INPUT` (planning decides to ask)
- **Phase 9**: `KNOWLEDGE_GAP`, `CAPABILITY_GAP`, `OUT_OF_SCOPE`, `SAFETY_REFUSAL` (LLM semantic)
- **Phase 10**: `POLICY_RESTRICTION` (enforcement blocked)

**Analytics enabled by TurnOutcome:**

```sql
-- Turn resolution rate (overall)
SELECT resolution, COUNT(*), COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as pct
FROM turn_records
GROUP BY 1;

-- Scenario completion rate (separate from turn outcome!)
SELECT scenario_id,
       COUNT(*) FILTER (WHERE status = 'COMPLETED') * 100.0 / COUNT(*) as completion_rate
FROM scenario_instances
GROUP BY 1;

-- Knowledge gaps: what should we add to knowledge base?
SELECT oc.details, COUNT(*)
FROM turn_records tr,
     unnest(tr.outcome.categories) as oc
WHERE oc.category = 'KNOWLEDGE_GAP'
GROUP BY 1 ORDER BY 2 DESC;

-- Capability gaps: what tools should we build?
SELECT oc.details, COUNT(*)
FROM turn_records tr,
     unnest(tr.outcome.categories) as oc
WHERE oc.category = 'CAPABILITY_GAP'
GROUP BY 1 ORDER BY 2 DESC;

-- System errors: reliability issues
SELECT oc.details, COUNT(*)
FROM turn_records tr,
     unnest(tr.outcome.categories) as oc
WHERE oc.category = 'SYSTEM_ERROR' AND oc.source = 'PIPELINE'
GROUP BY 1 ORDER BY 2 DESC;

-- Categories by scenario (which scenarios have issues?)
SELECT oc.scenario_id, oc.category, COUNT(*)
FROM turn_records tr,
     unnest(tr.outcome.categories) as oc
WHERE oc.scenario_id IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 3 DESC;

-- Pipeline vs Generation category distribution
SELECT oc.source, oc.category, COUNT(*)
FROM turn_records tr,
     unnest(tr.outcome.categories) as oc
GROUP BY 1, 2 ORDER BY 1, 3 DESC;
```

---
