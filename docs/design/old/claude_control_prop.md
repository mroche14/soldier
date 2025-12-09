# Unified Control Flow Design

**Date**: 2025-12-05
**Status**: Proposal for Review
**Sources**: `state_machine.md`, `state_machine_2.md`, `enhanced-enforcement.md`

This document synthesizes three design proposals into a unified architecture for rule processing, scenario navigation, and enforcement in Soldier.

---

## Executive Summary

Three design documents propose overlapping but sometimes conflicting approaches:

| Document | Focus | Key Innovation |
|----------|-------|----------------|
| `state_machine.md` | Graph-Augmented State Machine | Rule relationships, iterative tool loop, ambiguity trap |
| `state_machine_2.md` | State-Aware Agent Engine | Intent Registry, Router with stickiness, self-evolving profile |
| `enhanced-enforcement.md` | Enhanced Enforcement | Two-lane enforcement, always-enforce GLOBAL, variable extraction |

This document identifies **8 key design decisions**, presents options for each, and provides recommendations.

---

## Current Soldier Architecture (Baseline)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT TURN PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Context Extraction   ← Embed message, optional LLM intent extraction    │
│  2. Retrieval            ← Semantic search on condition_text (GLOBAL,       │
│                            SCENARIO, STEP scoped)                           │
│  3. Rule Filtering       ← LLM decides which rules truly apply              │
│  4. Scenario Filtering   ← Navigate scenario graph                          │
│  5. Tool Execution       ← Execute attached_tool_ids from matched rules     │
│  6. Response Generation  ← action_text of matched rules in prompt           │
│  7. Enforcement          ← Check is_hard_constraint rules                   │
│  8. Persist              ← Save session, audit                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Current Rule Model:**
```python
class Rule(AgentScopedModel):
    condition_text: str           # Semantic matching
    action_text: str              # Goes into generation prompt
    scope: Scope                  # GLOBAL, SCENARIO, STEP
    scope_id: UUID | None         # scenario_id or step_id
    is_hard_constraint: bool      # Post-generation enforcement
    attached_tool_ids: list[str]  # Tools to execute when matched
    priority: int                 # Conflict resolution
    enabled: bool
    max_fires_per_session: int
    cooldown_turns: int
```

---

## Alignment Objectives Reference

Each design decision below is assessed against these core objectives:

| Objective | Definition |
|-----------|------------|
| **Alignment** | Agent behavior matches defined rules and policies |
| **Instruction Following** | Agent executes configured actions correctly |
| **Drift Prevention** | Agent stays on topic and within scenario boundaries |

Legend: ⬤⬤⬤ = Critical, ⬤⬤◯ = Important, ⬤◯◯ = Minor

---

## Design Decisions

### Decision 1: Intent Detection vs Context Extraction

**Constraint**: state_machine_2 argues these should be separate because:
- Context Extraction = "What do we know?" (fills CustomerProfile)
- Intent Detection = "Where do we go?" (navigates Scenario Graph)

**Current Soldier**: `ContextExtractor` does both (embedding + optional LLM intent).

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Keep Combined** | Single ContextExtractor handles both | Simpler, one LLM call | Harder to tune navigation vs data separately |
| **B: Separate Parallel** | ContextExtractor + IntentDetector run in parallel | Clear separation, can optimize each | Two LLM calls, more complex |
| **C: Sequential with Caching** | Context first, Intent uses context | Intent can use extracted context | Sequential latency |

#### Recommendation: **Option A with Enhancement**

Keep the combined `ContextExtractor` but enhance its output:

```python
class Context(BaseModel):
    message: str
    embedding: list[float]

    # Data extraction (for profile/variables)
    extracted_entities: dict[str, Any]

    # Navigation signals (for scenario/rules)
    detected_intent: str | None
    intent_confidence: float

    # Ambiguity detection (from state_machine.md)
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None
```

**Rationale**: One LLM call extracts all signals. The ScenarioFilter and RuleRetriever use `detected_intent` for navigation, while profile updates use `extracted_entities`.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | Better intent detection → correct rules matched |
| **Instruction Following** | ⬤⬤◯ | Extracted entities enable variable-based instructions |
| **Drift Prevention** | ⬤⬤⬤ | `detected_intent` + `intent_confidence` improve scenario routing |

**Overall Value**: HIGH - Foundation for all downstream processing. Poor extraction = wrong rules = wrong behavior.

---

### Decision 2: Rule Relationships (Graph vs Flat)

**Constraint**: state_machine.md proposes rules with relationships:
```json
{
  "depends_on_definitions": ["def_premium_user"],
  "entails_rules": ["rule_log_transaction"],
  "excludes_rules": ["rule_reject_all"]
}
```

**Current Soldier**: Flat rules with scope-based filtering.

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Keep Flat** | Rules are independent, only scope connects them | Simple, already implemented | Can't express "if A then B must also apply" |
| **B: Add Relationships** | Add relationship fields to Rule model | Powerful graph queries, context expansion | Complex retrieval, storage overhead |
| **C: Implicit via Tags** | Rules share tags, retriever expands by tag | Simpler than full graph | Less precise than explicit relationships |

#### Recommendation: **Option A (Keep Flat) for Now**

**Rationale**:
1. Soldier already has scope hierarchy (GLOBAL → SCENARIO → STEP) which provides structure
2. "Entails" can be handled by attached_tool_ids (rule triggers tool which triggers effect)
3. "Definitions" are better handled by the CustomerProfile schema
4. Adding relationships is a major schema change with migration complexity

**Future consideration**: If we need "rule A excludes rule B", add an `excludes_rule_ids` field later.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | Graph could ensure related rules always apply together |
| **Instruction Following** | ⬤⬤◯ | "Entails" would guarantee chained instructions |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant to drift |

**Overall Value**: LOW (deferred) - Scope hierarchy handles 90% of cases. Graph adds complexity without proportional alignment benefit. Revisit if "rule A requires rule B" becomes common.

---

### Decision 3: Iterative Tool Resolution Loop

**Constraint**: state_machine.md proposes an iterative loop:
```
1. Extract context → 2. Check missing variables → 3. Call tools to fill → 4. Re-extract → 5. If still missing, ask user
```

**Current Soldier**: Linear flow where tools execute once from matched rules.

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Keep Linear** | Tools execute once after rule matching | Simple, predictable latency | Can't auto-resolve missing data |
| **B: Pre-Generation Loop** | Loop before generation to fill variables | Better UX (fewer user questions) | Complex, unbounded latency |
| **C: Gap-Fill Service** | Dedicated service tries profile/session/tools before asking | Controlled, already exists for migrations | Needs integration into main pipeline |

#### Recommendation: **Option C (Extend Gap-Fill Service)**

Soldier already has `MissingFieldResolver` for scenario migrations. Extend it:

```python
class VariableResolver:
    """Resolve missing variables before enforcement or generation."""

    async def resolve(
        self,
        required_variables: list[str],
        session: Session,
        profile: CustomerProfile | None,
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Returns:
            resolved: Variables that were found
            still_missing: Variables that need user input
        """
        resolved = {}

        # 1. Check session variables
        for var in required_variables:
            if var in session.variables:
                resolved[var] = session.variables[var]

        # 2. Check profile fields
        if profile:
            for var in required_variables:
                if var not in resolved:
                    value = profile.get_field(var)
                    if value is not None:
                        resolved[var] = value

        # 3. Check if tools can provide (without calling yet)
        # Tool execution happens in the main pipeline

        still_missing = [v for v in required_variables if v not in resolved]
        return resolved, still_missing
```

**Rationale**: Reuses existing infrastructure. The main pipeline remains linear, but enforcement can request variable resolution before evaluating expressions.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | More variables resolved → more rules can be evaluated |
| **Instruction Following** | ⬤⬤⬤ | Auto-fetching missing data enables complete instruction execution |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant |

**Overall Value**: MEDIUM - Improves UX (fewer questions) and enables enforcement of rules that need external data. Not critical for alignment but valuable for completeness.

---

### Decision 4: Ambiguity Detection

**Constraint**: state_machine.md proposes an "Ambiguity Trap" - if the user's message is vague, exit immediately rather than guess.

**Current Soldier**: No explicit ambiguity handling.

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: No Detection** | Proceed with best guess | Faster, no extra logic | May take wrong action on vague input |
| **B: Confidence Threshold** | If intent_confidence < threshold, clarify | Simple to implement | Hard to set threshold |
| **C: Explicit Ambiguity Flag** | LLM outputs is_ambiguous + reason | Clear signal, can generate targeted question | Extra prompt engineering |

#### Recommendation: **Option C (Explicit Ambiguity Flag)**

Add to `Context` model:

```python
class Context(BaseModel):
    # ... existing fields ...

    is_ambiguous: bool = False
    ambiguity_reason: str | None = None
    confidence: float = 1.0  # 0.0-1.0
```

**Pipeline integration:**
```python
# In AlignmentEngine.process_turn()

context = await self._extract_context(message, history)

if context.is_ambiguous:
    return AlignmentResult(
        response=f"I want to make sure I understand. {context.ambiguity_reason}",
        # ... early exit
    )
```

**Rationale**: Explicit is better than implicit. The LLM can reason about ambiguity better than a simple confidence score.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤⬤ | Prevents wrong action based on misunderstood intent |
| **Instruction Following** | ⬤⬤◯ | Ensures instructions match actual user intent |
| **Drift Prevention** | ⬤⬤⬤ | Stops agent from going down wrong path on vague input |

**Overall Value**: HIGH - Critical for alignment. Without it, agent may approve refund when user was asking hypothetically ("what if I wanted a refund?"). Ambiguity trap prevents costly mistakes.

**Risk mitigated**: Agent acts on "maybe" as "yes", commits to action user didn't intend.

---

### Decision 5: Scenario Navigation Stickiness

**Constraint**: state_machine_2 proposes "stickiness" - bias heavily toward current scenario transitions over global intents to prevent ping-ponging.

**Current Soldier**: ScenarioFilter evaluates candidates but doesn't have explicit stickiness.

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: No Stickiness** | Equal weight to all matching scenarios | User can easily switch | May switch on minor tangents |
| **B: Score Boost** | Add bonus score to current scenario transitions | Soft preference | May ignore legitimate exits |
| **C: Confidence Threshold** | Only exit current scenario if new intent > 0.85 | Hard boundary | May trap user in wrong scenario |
| **D: Explicit Exit Intents** | Define specific intents that trigger exit | Controlled, predictable | More configuration burden |

#### Recommendation: **Option B + D (Score Boost + Exit Intents)**

```python
class ScenarioFilterConfig(BaseModel):
    stickiness_boost: float = Field(
        default=0.15,
        description="Score bonus for transitions within current scenario"
    )
    exit_intent_threshold: float = Field(
        default=0.85,
        description="Minimum confidence to exit current scenario for new one"
    )
```

**Implementation in ScenarioFilter:**
```python
async def evaluate(self, ..., active_scenario_id: UUID | None):
    scored_candidates = []

    for candidate in candidates:
        score = candidate.similarity_score

        # Stickiness: boost current scenario
        if active_scenario_id and candidate.scenario_id == active_scenario_id:
            score += self._config.stickiness_boost

        scored_candidates.append((candidate, score))

    # Sort and decide
    best = max(scored_candidates, key=lambda x: x[1])

    # If switching scenarios, require high confidence
    if active_scenario_id and best.scenario_id != active_scenario_id:
        if best.score < self._config.exit_intent_threshold:
            # Stay in current scenario
            return self._stay_in_current(active_scenario_id)

    return best
```

**Rationale**: Combines soft preference (score boost) with hard boundary for exits, addressing the "ping-pong" problem.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤◯◯ | Indirectly helps by keeping correct rules in scope |
| **Instruction Following** | ⬤⬤◯ | Ensures scenario-specific instructions stay active |
| **Drift Prevention** | ⬤⬤⬤ | PRIMARY mechanism to prevent topic-hopping |

**Overall Value**: HIGH - Essential for drift prevention. Without stickiness, mentioning "price" while in refund flow causes jump to pricing scenario. User loses context, agent loses track.

**Risk mitigated**: Agent ping-pongs between scenarios on tangential mentions, confusing user and losing conversation state.

---

### Decision 6: Intent Registry

**Constraint**: state_machine_2 proposes an IntentRegistry for:
1. Few-shot classification (better than zero-shot)
2. Business observability (intent heatmaps)

**Current Soldier**: No explicit intent registry. Intents are implicit in rule condition_text.

#### Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: No Registry** | Intents are implicit in rules/scenarios | Simpler | No observability, no few-shot |
| **B: Separate Intent Entity** | New `Intent` model with examples | Full control, observability | Another entity to manage |
| **C: Intent Examples on Scenario** | Scenarios have `entry_examples` field | Tied to navigation, simpler than B | Less flexible |

#### Recommendation: **Option C (Intent Examples on Scenario)**

Extend the Scenario model:

```python
class Scenario(AgentScopedModel):
    # ... existing fields ...

    # For better intent matching
    entry_examples: list[str] = Field(
        default_factory=list,
        description="Example phrases that trigger this scenario (few-shot)"
    )

    # For observability
    intent_label: str = Field(
        default="",
        description="Business-friendly label for analytics (e.g., 'refund_request')"
    )
```

**Usage in retrieval:**
```python
# In ScenarioRetriever
# Use entry_examples for few-shot embedding comparison
```

**Rationale**:
- Keeps intents tied to what they trigger (scenarios)
- Enables few-shot matching via examples
- Provides intent_label for observability dashboards
- No new entity to manage

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤◯◯ | Indirectly helps via better scenario matching |
| **Instruction Following** | ⬤⬤◯ | Correct scenario = correct instructions activated |
| **Drift Prevention** | ⬤⬤⬤ | Better matching = less wrong-scenario drift |

**Overall Value**: MEDIUM - Improves accuracy of scenario routing. Few-shot examples help distinguish "refund request" from "complaint about refund". Not critical but valuable for complex multi-scenario agents.

**Risk mitigated**: "I want my money back" incorrectly routes to complaints instead of refunds.

---

### Decision 7: Variable Extraction Timing

**Constraint**: enhanced-enforcement.md proposes extracting variables from the response for enforcement. But state_machine.md and state_machine_2.md suggest extraction from user input into CustomerProfile.

**Question**: When do we extract? From what?

#### Analysis

| Extraction Point | What | Why |
|------------------|------|-----|
| **From User Input** | Facts about user (country, tier, order ID) | Build CustomerProfile |
| **From Tool Outputs** | Results from API calls (order_status, balance) | Session variables |
| **From Agent Response** | Commitments agent made (refund amount, discount) | Enforcement |

These are **three different extractions** at different points:

```
User: "I'm in France and want a refund for order 123"
      ↓
[Extract from Input] → {country: "France", order_id: "123"} → Profile
      ↓
[Tool: lookup_order] → {order_status: "delivered", amount: 75} → Session
      ↓
[Generate Response] → "I'll process a $75 refund for you"
      ↓
[Extract from Response] → {promised_refund: 75} → Enforcement
      ↓
[Enforce] → "amount <= 50" with {amount: 75} → VIOLATION
```

#### Recommendation: **Three-Stage Extraction**

1. **Context Extraction** (existing): Extract from user input → update Profile
2. **Tool Execution** (existing): Tool outputs → update Session variables
3. **Response Extraction** (new, for enforcement): Extract from response → enforcement variables

```python
# Enforcement uses merged variables from all sources:
async def extract_enforcement_variables(
    self,
    response: str,
    session: Session,
    profile: CustomerProfile | None,
) -> dict[str, Any]:
    """Merge variables from all sources for enforcement."""

    variables = {}

    # 1. Profile fields (known facts about user)
    if profile:
        variables.update(profile.to_variables())

    # 2. Session variables (from tools, previous turns)
    variables.update(session.variables)

    # 3. Response extraction (what agent committed to)
    response_vars = await self._extract_from_response(response)
    variables.update(response_vars)

    return variables
```

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤⬤ | CRITICAL - Enables enforcement of quantitative rules |
| **Instruction Following** | ⬤⬤◯ | Variables enable conditional instruction execution |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant |

**Overall Value**: HIGH - Response extraction is essential for Lane 1 enforcement. Without extracting "I'll give you $75" → {amount: 75}, we cannot evaluate "amount <= 50". This is the bridge between natural language and deterministic checking.

**Risk mitigated**: Agent promises $100 refund, enforcement has no way to detect violation.

---

### Decision 8: Enforcement Scope for Non-GLOBAL Rules

**Constraint**: enhanced-enforcement.md proposes always enforcing GLOBAL hard constraints. But what about SCENARIO/STEP hard constraints?

**Question**: If a SCENARIO-scoped rule with `is_hard_constraint=True` matched, should it be enforced? What if it didn't match but we're in that scenario?

#### Options

| Option | Scope | Matched? | Enforce? |
|--------|-------|----------|----------|
| **A: Match-Based** | Any | Yes | Yes |
| **A: Match-Based** | Any | No | No |
| **B: Scope-Based** | GLOBAL | Any | Always |
| **B: Scope-Based** | SCENARIO/STEP | Only if matched | Yes |
| **C: Full Scope-Based** | GLOBAL | Any | Always |
| **C: Full Scope-Based** | SCENARIO | In scenario | Always |
| **C: Full Scope-Based** | STEP | In step | Always |

#### Recommendation: **Option B (GLOBAL always, others match-based)**

```python
async def get_rules_to_enforce(
    self,
    matched_rules: list[MatchedRule],
    tenant_id: UUID,
    agent_id: UUID,
) -> list[Rule]:
    """Get all rules that need enforcement."""

    # 1. All matched hard constraints (any scope)
    rules = [mr.rule for mr in matched_rules if mr.rule.is_hard_constraint]
    matched_ids = {r.id for r in rules}

    # 2. ALL GLOBAL hard constraints (even if not matched)
    global_hard = await self._config_store.get_rules(
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=Scope.GLOBAL,
        hard_constraints_only=True,
    )

    for rule in global_hard:
        if rule.id not in matched_ids:
            rules.append(rule)

    # Note: SCENARIO/STEP hard constraints only if they matched
    # (they were retrieved based on current scenario/step, so if they
    # matched semantically, they apply; if not, they don't)

    return rules
```

**Rationale**:
- GLOBAL = guardrails that must never be violated (competitor mentions, PII, etc.)
- SCENARIO/STEP = contextual rules that only apply when semantically relevant
- A STEP rule "validate IBAN format" shouldn't enforce if user is asking about weather, even if we're at the IBAN step

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤⬤ | CRITICAL - Guardrails enforced regardless of conversation topic |
| **Instruction Following** | ⬤⬤⬤ | Business-critical rules (competitor bans, max discounts) always checked |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant |

**Overall Value**: CRITICAL - This is the most important alignment mechanism. "Never mention competitor X" must be enforced even when discussing weather. Without always-enforce GLOBAL, off-topic conversations bypass all safety rules.

**Risk mitigated**: User asks about weather, agent mentions competitor in joke. Without always-enforce, no rule catches this because "competitor" rule didn't match "weather" query.

---

## Unified Pipeline (Proposed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROPOSED TURN PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [User Message]                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 1. CONTEXT EXTRACTION (Enhanced)                                        ││
│  │                                                                         ││
│  │ Outputs:                                                                ││
│  │ • embedding (for retrieval)                                             ││
│  │ • extracted_entities (for profile update)                               ││
│  │ • detected_intent + confidence (for navigation)                         ││
│  │ • is_ambiguous + reason (for early exit)                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ├── if is_ambiguous ──→ [Return clarification question]               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 2. RETRIEVAL                                                            ││
│  │                                                                         ││
│  │ Rules: GLOBAL + SCENARIO (if in scenario) + STEP (if at step)           ││
│  │ Scenarios: Use entry_examples for few-shot matching                     ││
│  │ Memory: Episodes relevant to query                                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 3. FILTERING                                                            ││
│  │                                                                         ││
│  │ Rule Filter: LLM judges which rules apply                               ││
│  │ Scenario Filter: Navigate with stickiness boost                         ││
│  │   • +0.15 score for current scenario transitions                        ││
│  │   • Require >0.85 confidence to exit for new scenario                   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 4. TOOL EXECUTION                                                       ││
│  │                                                                         ││
│  │ Execute attached_tool_ids from matched rules                            ││
│  │ Tool outputs → session.variables                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 5. RESPONSE GENERATION                                                  ││
│  │                                                                         ││
│  │ Prompt includes:                                                        ││
│  │ • action_text from matched rules                                        ││
│  │ • tool outputs                                                          ││
│  │ • memory context                                                        ││
│  │ • conversation history                                                  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 6. ENFORCEMENT (Enhanced)                                               ││
│  │                                                                         ││
│  │ Collect rules to enforce:                                               ││
│  │ • Matched rules with is_hard_constraint=True                            ││
│  │ • ALL GLOBAL rules with is_hard_constraint=True                         ││
│  │                                                                         ││
│  │ Variable sources (merged):                                              ││
│  │ • CustomerProfile fields                                                ││
│  │ • Session variables (from tools)                                        ││
│  │ • Extracted from response                                               ││
│  │                                                                         ││
│  │ Two lanes:                                                              ││
│  │ • Lane 1: Deterministic (simpleeval for enforcement_expression)         ││
│  │ • Lane 2: Probabilistic (LLM-as-Judge for action_text)                  ││
│  │                                                                         ││
│  │ Optional global checks:                                                 ││
│  │ • Relevance (query ↔ response)                                          ││
│  │ • Grounding (response ↔ context)                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ├── if violations ──→ [Regenerate or Fallback]                        │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 7. PERSIST                                                              ││
│  │                                                                         ││
│  │ • Update session (rule fires, scenario step, variables)                 ││
│  │ • Update profile (extracted entities)                                   ││
│  │ • Create turn record (audit)                                            ││
│  │ • Log intent for observability (intent_label from scenario)             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│       │                                                                     │
│       ▼                                                                     │
│  [Final Response]                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary of Recommendations

### Core Design Decisions

| Decision | Recommendation | Rationale |
|----------|----------------|-----------|
| **1. Intent vs Context** | Keep combined with enhanced output | One LLM call, clear separation in output fields |
| **2. Rule Relationships** | Keep flat for now | Scope hierarchy sufficient, avoids schema complexity |
| **3. Iterative Tool Loop** | Extend Gap-Fill Service | Reuse existing infrastructure, keep pipeline linear |
| **4. Ambiguity Detection** | Add explicit flag to Context | Better than confidence threshold |
| **5. Scenario Stickiness** | Score boost + exit threshold | Prevents ping-pong without trapping users |
| **6. Intent Registry** | Add entry_examples to Scenario | Enables few-shot without new entity |
| **7. Variable Extraction** | Three-stage (input, tools, response) | Different sources for different purposes |
| **8. Enforcement Scope** | GLOBAL always, others match-based | Guardrails vs contextual rules |

### Additional Considerations

| Topic | Recommendation | Source |
|-------|----------------|--------|
| **A. Definition Nodes** | Use existing ProfileFieldDefinition | state_machine.md |
| **B. Setup Agent/Builder** | Out of scope (future tooling) | state_machine_2.md |
| **C. Stuck User/Fallback** | Add fallback_behavior to ScenarioFilterConfig | state_machine_2.md |
| **D. Profile Schema Versioning** | Add schema_version to Agent config | state_machine_2.md |
| **E. Refusal Bypass** | Add refusal detection before relevance scoring | enhanced-enforcement.md |
| **F. Tool Execution** | Confirm existing attached_tool_ids behavior | all |

---

## Implementation Priority

1. **Phase 1: Context Enhancement**
   - Add `is_ambiguous`, `ambiguity_reason`, `confidence` to Context
   - Update ContextExtractor prompt to output these
   - Add early exit in pipeline

2. **Phase 2: Scenario Navigation**
   - Add `entry_examples`, `intent_label` to Scenario
   - Implement stickiness in ScenarioFilter
   - Add intent logging for observability

3. **Phase 3: Enhanced Enforcement**
   - Add `enforcement_expression` to Rule
   - Implement DeterministicEnforcer (simpleeval)
   - Implement SubjectiveEnforcer (LLM-as-Judge)
   - Implement always-enforce for GLOBAL

4. **Phase 4: Variable Resolution**
   - Implement three-stage extraction
   - Extend VariableResolver for enforcement

5. **Phase 5: Output Verification**
   - Implement RelevanceVerifier
   - Implement GroundingVerifier

---

## Additional Considerations

### A. Definition Nodes (from state_machine.md)

**Constraint**: state_machine.md proposes "DEFINITION" nodes (e.g., "What is a Premium User?") that get expanded into context so the LLM understands terms.

**Current Soldier**: No explicit definition nodes. Terms are implicit in rule condition_text/action_text.

**Recommendation**: Use **CustomerProfile Field Definitions** instead.

Soldier already has `ProfileFieldDefinition` in the profile system:

```python
class ProfileFieldDefinition(BaseModel):
    field_name: str                    # "is_vip"
    display_name: str                  # "VIP Status"
    description: str                   # "User is VIP if lifetime spend > $1000"
    field_type: ProfileFieldType       # BOOLEAN
    validation_rules: list[str]        # ["value in [True, False]"]
    extraction_hints: list[str]        # ["Look for 'premium', 'VIP', 'gold member'"]
```

The `description` and `extraction_hints` serve as definitions. When building the extraction prompt, include relevant field definitions so the LLM knows what "VIP" means.

**No new entity needed** - extend usage of existing ProfileFieldDefinition.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | Definitions help LLM extract correct values |
| **Instruction Following** | ⬤⬤◯ | Clear definitions → accurate variable extraction |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant |

**Overall Value**: MEDIUM - Important for accuracy of extraction but already exists. No new work needed beyond using existing ProfileFieldDefinition more extensively.

---

### B. Setup Agent / Builder (from state_machine_2.md)

**Constraint**: state_machine_2 proposes a "Setup Agent" that:
1. Ingests natural language configuration ("I want an agent that handles returns")
2. Detects ambiguity ("How do we define VIP?")
3. Detects incoherence ("You said instant refunds but also manual approval - which wins?")
4. Generates Profile Schema, Scenarios, Rules

**Recommendation**: **Out of scope for runtime engine, but valuable for tooling.**

This is a design-time tool, not runtime. Consider as future work:
- A CLI or UI wizard that uses LLM to generate Soldier configuration
- Validates rules for conflicts before deployment
- Auto-suggests ProfileFieldDefinitions based on rule expressions

**For now**: Manual rule/scenario creation via API. Validation at save time (existing).

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤◯◯ | Design-time, doesn't affect runtime alignment |
| **Instruction Following** | ⬤◯◯ | Helps create better rules, but not runtime |
| **Drift Prevention** | ⬤◯◯ | Not relevant |

**Overall Value**: LOW (out of scope) - Valuable for configuration quality but doesn't affect runtime alignment. Design-time tooling is a separate concern.

---

### C. Stuck User Problem / Fallback Transitions (from state_machine_2.md)

**Constraint**: User is at a step expecting "Yes/No", they say "Maybe". Intent doesn't match any transition. Bot loops.

**Recommendation**: Add **fallback behavior** to ScenarioFilter.

```python
class ScenarioFilterConfig(BaseModel):
    # ... existing ...

    # Fallback when no transition matches
    fallback_behavior: Literal["clarify", "stay", "escalate"] = "clarify"
    max_clarifications_per_step: int = 2
```

**Implementation:**
```python
async def evaluate(self, ...):
    # ... existing logic ...

    # No valid transition found
    if best_transition_score < self._config.min_transition_score:
        clarification_count = session.step_clarification_count.get(current_step_id, 0)

        if clarification_count >= self._config.max_clarifications_per_step:
            if self._config.fallback_behavior == "escalate":
                return ScenarioFilterResult(action="escalate", ...)
            else:
                return ScenarioFilterResult(action="stay", ...)

        # Generate clarification
        return ScenarioFilterResult(
            action="clarify",
            clarification_prompt=f"I didn't quite understand. {step.clarification_hint}",
        )
```

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤◯◯ | Prevents wrong action when stuck, but indirect |
| **Instruction Following** | ⬤⬤◯ | Ensures step instructions are completed before moving on |
| **Drift Prevention** | ⬤⬤⬤ | Prevents infinite loops and graceful degradation |

**Overall Value**: MEDIUM - Important for robustness. Without fallback handling, bot loops forever on unexpected input. Escalation option provides human backup.

**Risk mitigated**: User says "maybe" when bot expects "yes/no", bot repeats question indefinitely.

---

### D. Profile Schema Versioning (from state_machine_2.md)

**Constraint**: When new fields are added to CustomerProfile schema, how do we version?

**Current Soldier**: ProfileFieldDefinition exists but no explicit versioning.

**Recommendation**: Add `schema_version` to agent configuration.

```python
class Agent(TenantScopedModel):
    # ... existing ...

    profile_schema_version: int = Field(default=1)
    profile_field_definitions: list[ProfileFieldDefinition] = Field(default_factory=list)
```

When ContextExtractor runs, it uses the field definitions from the current agent config. If definitions change, bump version. Migration handles old profiles.

**Note**: This ties into existing scenario migration infrastructure.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤◯◯ | Operational concern, not runtime alignment |
| **Instruction Following** | ⬤◯◯ | Affects migrations, not instruction execution |
| **Drift Prevention** | ⬤◯◯ | Not relevant |

**Overall Value**: LOW - Operational infrastructure. Important for smooth deployments but doesn't affect how the agent follows rules or stays on topic.

---

### E. Refusal Bypass in Relevance Check (from enhanced-enforcement.md)

**Constraint**: Relevance check compares query ↔ response similarity. But valid refusals ("I don't know") have low similarity and would fail.

**Recommendation**: Add **refusal detection** before relevance scoring.

```python
class RelevanceVerifier:
    REFUSAL_PHRASES = [
        "i don't know", "i cannot answer", "i'm not able to",
        "outside my capabilities", "i don't have that information",
    ]

    async def verify(self, query: str, response: str) -> tuple[float, bool]:
        # Bypass for valid refusals
        if self._is_refusal_response(response):
            return 1.0, True  # Pass

        # Normal relevance check
        score = await self._compute_similarity(query, response)
        return score, score >= self._threshold

    def _is_refusal_response(self, response: str) -> bool:
        return any(phrase in response.lower() for phrase in self.REFUSAL_PHRASES)
```

Add to config:
```python
class EnforcementConfig(BaseModel):
    # ... existing ...
    relevance_refusal_bypass: bool = True
```

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | Prevents false-positive blocks on valid refusals |
| **Instruction Following** | ⬤◯◯ | Not directly relevant |
| **Drift Prevention** | ⬤⬤◯ | Allows valid "I can't help with that" responses |

**Overall Value**: MEDIUM - Important for avoiding false positives. Without refusal bypass, "I don't know" responses get blocked by relevance check (low similarity to question). This would force agent to hallucinate an answer instead of admitting uncertainty.

**Risk mitigated**: Agent blocked for saying "I don't know", forced to make something up instead.

---

### F. Tool Execution Clarification

**Existing behavior** (confirm in proposal): Rules can have `attached_tool_ids`. When a rule matches, its tools execute. Tool outputs go to `session.variables` and are available to generation.

```python
class Rule(AgentScopedModel):
    # ... existing ...
    attached_tool_ids: list[str]  # Tool IDs from ToolHub/ToolGateway
```

**Flow:**
```
Rule matched → Execute attached_tool_ids → Outputs to session.variables → Available in generation prompt
```

This is orthogonal to enforcement. Tools execute based on rule matching, not enforcement evaluation.

#### Alignment Impact

| Objective | Impact | Notes |
|-----------|:------:|-------|
| **Alignment** | ⬤⬤◯ | Tools can fetch data needed for alignment decisions |
| **Instruction Following** | ⬤⬤⬤ | Rules can trigger actions (API calls, lookups) as part of instructions |
| **Drift Prevention** | ⬤◯◯ | Not directly relevant |

**Overall Value**: HIGH - Core mechanism for action execution. A rule saying "look up order status" triggers the lookup tool. Without tool execution, agent can only generate text, not take actions.

**Risk mitigated**: Agent promises to check something but has no mechanism to actually check it.

---

## Open Questions for Review

1. **Ambiguity Response**: Should ambiguous queries trigger a specific scenario ("clarification flow") or just a generic response?

2. **Stickiness Override**: Should there be explicit "exit intents" that always break stickiness (e.g., "cancel", "start over")?

3. **Profile vs Session Variables**: What's the boundary? Profile = persistent facts, Session = conversation state?

4. **Enforcement Regeneration**: How many times should we retry before falling back to template?

5. **Tool Loop Iteration**: If we add iterative tool resolution, what's the max loop count? (state_machine.md suggests 3)

6. **Fallback Escalation**: When stuck user exhausts clarifications, should we escalate to human or exit scenario?

7. **Definition Scope**: Should ProfileFieldDefinitions be agent-scoped or tenant-scoped?

---

## Appendix: Key Model Changes

### Context (Enhanced)

```python
class Context(BaseModel):
    message: str
    embedding: list[float]

    # Existing
    intent: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)

    # New: Navigation signals
    detected_intent: str | None = None
    intent_confidence: float = 1.0

    # New: Ambiguity detection
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None
```

### Scenario (Enhanced)

```python
class Scenario(AgentScopedModel):
    # ... existing fields ...

    # New: Few-shot matching
    entry_examples: list[str] = Field(default_factory=list)

    # New: Observability
    intent_label: str = ""
```

### Rule (Enhanced)

```python
class Rule(AgentScopedModel):
    # ... existing fields ...

    # New: Deterministic enforcement
    enforcement_expression: str | None = None
```

### ScenarioFilterConfig (New)

```python
class ScenarioFilterConfig(BaseModel):
    enabled: bool = True
    stickiness_boost: float = 0.15
    exit_intent_threshold: float = 0.85
    max_loop_count: int = 10

    # Fallback handling (from Additional Consideration C)
    fallback_behavior: Literal["clarify", "stay", "escalate"] = "clarify"
    max_clarifications_per_step: int = 2
    min_transition_score: float = 0.3
```

### Agent Config (Enhanced)

```python
class Agent(TenantScopedModel):
    # ... existing fields ...

    # Profile schema versioning (from Additional Consideration D)
    profile_schema_version: int = Field(default=1)
    profile_field_definitions: list[ProfileFieldDefinition] = Field(default_factory=list)
```

### EnforcementConfig (Enhanced)

```python
class EnforcementConfig(BaseModel):
    enabled: bool = True
    max_retries: int = 1

    # Lane 1
    deterministic_enabled: bool = True

    # Lane 2
    llm_judge_enabled: bool = True
    llm_judge_models: list[str] = ["openrouter/anthropic/claude-3-haiku"]

    # Always-enforce
    always_enforce_global: bool = True

    # Optional checks
    relevance_check_enabled: bool = False
    relevance_threshold: float = 0.5
    relevance_refusal_bypass: bool = True  # (from Additional Consideration E)

    grounding_check_enabled: bool = False
    grounding_threshold: float = 0.75
```
