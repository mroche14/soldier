# Enhanced Enforcement

Extending the enforcement pipeline with deterministic rule evaluation, LLM-as-Judge for subjective rules, and optional grounding/relevance verification.

## Overview

Focal already has a rule-based system where:
1. **Rules are matched semantically** against user input (`condition_text`)
2. **Matched rules guide generation** via `action_text` in the prompt
3. **Hard constraints are enforced** post-generation (`is_hard_constraint=True`)

This document describes enhancements to the enforcement step, adding:
- **Deterministic expression evaluation** for quantitative rules (Lane 1)
- **LLM-as-Judge** for subjective rules (Lane 2)
- **Always-enforce behavior** for GLOBAL hard constraints
- **Grounding verification** (response vs context)
- **Relevance verification** (response vs query)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT TURN PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Retrieve Rules      ← Semantic match on condition_text                  │
│  2. Filter Rules        ← LLM decides which truly apply                     │
│  3. Execute Tools       ← From matched rules                                │
│  4. Generate Response   ← action_text of matched rules in prompt            │
│  5. Enforce             ← Check is_hard_constraint rules (ENHANCED)         │
│  6. Persist             ← Save session, audit                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

The enhancement focuses on **step 5 (Enforce)**, making it smarter and more comprehensive.

### Clarifications on Existing Rule Behavior

**Tool Execution**: Rules can have `attached_tool_ids` (list of tool IDs from ToolHub/ToolGateway). When a rule matches, its attached tools are executed in step 3, and the tool outputs are available to the generation step. This is orthogonal to enforcement - tools execute based on rule matching, not enforcement.

**Scope Levels**: Rules are scoped at three levels:
- `GLOBAL`: Always considered for retrieval (agent-wide)
- `SCENARIO`: Only retrieved when the session is in the specified scenario (`scope_id` = scenario ID)
- `STEP`: Only retrieved when the session is at a specific step within a scenario (`scope_id` = step ID)

Scope affects **retrieval**, not enforcement. A STEP-scoped rule with `is_hard_constraint=True` is only enforced if it was matched (since it wouldn't be retrieved otherwise). GLOBAL hard constraints are always enforced regardless of matching.

---

## The Formalization Gap

### Why Enhancement is Needed

The current enforcement uses simple phrase matching:

```python
# Current: basic phrase matching
def _detect_violations(self, response: str, hard_rules: list[Rule]) -> list[ConstraintViolation]:
    lower_response = response.lower()
    for rule in hard_rules:
        if any(phrase in lower_response for phrase in self._extract_phrases(rule)):
            violations.append(...)
```

This has limitations:
- Can't verify quantitative constraints ("refund must be ≤ $50")
- Can't handle subjective rules ("be professional")
- Only checks rules that semantically matched the input

### The Two Lanes (from Formal Methods Theory)

Rules fall into two categories that require different verification approaches:

| Type | Example | Verification | Certainty |
|------|---------|--------------|-----------|
| **Deterministic** | `amount <= 50` | Expression evaluation (simpleeval) | 100% after extraction |
| **Probabilistic** | "be professional" | LLM-as-Judge | ~85-95% |

**Key insight**: For deterministic rules, the CHECK is 100% reliable. The only uncertainty is in variable EXTRACTION from the response. This is the "formalization gap" - converting natural language to formal variables.

---

## Enhanced Rule Model

### New Field: `enforcement_expression`

```python
# focal/alignment/models/rule.py

class Rule(AgentScopedModel):
    """Behavioral policy: when X, then Y."""

    # Existing fields
    condition_text: str           # "when user asks about refunds" (semantic match)
    action_text: str              # "limit refunds to $50" (goes into prompt)
    scope: Scope                  # GLOBAL, SCENARIO, STEP
    is_hard_constraint: bool      # Must be satisfied

    # NEW: Formal verification expression
    enforcement_expression: str | None = Field(
        default=None,
        description="Formal expression for deterministic enforcement (e.g., 'amount <= 50')"
    )
```

### How It Works Together

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RULE: Refund Policy                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  condition_text: "when user asks about refunds"                             │
│       └── Used for: Semantic matching against user input                    │
│                                                                             │
│  action_text: "explain our refund policy, limit to $50 for standard users"  │
│       └── Used for: Goes into LLM prompt, guides generation                 │
│                                                                             │
│  enforcement_expression: "amount <= 50 or user_tier == 'VIP'"               │
│       └── Used for: Post-generation verification (deterministic)            │
│                                                                             │
│  scope: GLOBAL                                                              │
│  is_hard_constraint: True                                                   │
│       └── Combined: Always enforced, even if rule didn't match input        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Enhanced Enforcement Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENHANCED ENFORCEMENT PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [Generated Response]                                                       │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 1: Collect Rules to Enforce                                        ││
│  │                                                                         ││
│  │ a) Rules that matched input AND is_hard_constraint=True                 ││
│  │ b) GLOBAL rules with is_hard_constraint=True (always, even if not       ││
│  │    matched) ← NEW BEHAVIOR                                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 2: Variable Extraction (if any rule has enforcement_expression)    ││
│  │                                                                         ││
│  │ Extract structured data from response:                                  ││
│  │ → {amount: 75, country: "US", user_tier: "standard", ...}               ││
│  │                                                                         ││
│  │ Methods: Regex patterns (fast) + LLM extraction (complex)               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         ├─── Rules WITH enforcement_expression ─────────┐                   │
│         │                                               ▼                   │
│         │    ┌─────────────────────────────────────────────────────────────┐│
│         │    │ LANE 1: DETERMINISTIC (simpleeval)                          ││
│         │    │                                                             ││
│         │    │ Evaluate: "amount <= 50 or user_tier == 'VIP'"              ││
│         │    │ With variables: {amount: 75, user_tier: "standard"}         ││
│         │    │ Result: FALSE → VIOLATION                                   ││
│         │    │                                                             ││
│         │    │ ✓ 100% deterministic (after extraction)                     ││
│         │    │ ✓ Fast, auditable                                           ││
│         │    │ ✓ No hallucination in the CHECK                             ││
│         │    └─────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         └─── Rules WITHOUT enforcement_expression ──────┐                   │
│                                                         ▼                   │
│         ┌─────────────────────────────────────────────────────────────────┐│
│         │ LANE 2: PROBABILISTIC (LLM-as-Judge)                            ││
│         │                                                                 ││
│         │ Prompt: "Does this response comply with: {action_text}?"        ││
│         │ action_text: "response must be professional and empathetic"     ││
│         │ LLM Response: "No, the tone is dismissive"                      ││
│         │                                                                 ││
│         │ ✓ Handles subjective/semantic rules                             ││
│         │ ✗ ~85-95% accuracy (LLM judgment)                               ││
│         │ ✗ Slower, costs tokens                                          ││
│         └─────────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 3: Global Checks (optional, configurable)                          ││
│  │                                                                         ││
│  │ • Relevance: Does response address the user's question?                 ││
│  │   (Query ↔ Response similarity)                                         ││
│  │                                                                         ││
│  │ • Grounding: Is response factually supported by context?                ││
│  │   (Response ↔ Retrieved Context NLI)                                    ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 4: Remediation (if violations found)                               ││
│  │                                                                         ││
│  │ 1. Regenerate with violation hints                                      ││
│  │ 2. If still failing, use fallback template                              ││
│  │ 3. Log violation for audit                                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                   │
│         ▼                                                                   │
│  [Final Response]                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Always-Enforce Behavior for GLOBAL Hard Constraints

### Current Behavior
```
User: "What's the weather?"
Rule: "Never promise >10% discount" (GLOBAL, is_hard_constraint=True)

→ Rule doesn't match "weather" semantically
→ Rule is NOT retrieved
→ Agent: "I don't know the weather, but here's 25% off!"
→ Violation NOT caught
```

### Enhanced Behavior
```
User: "What's the weather?"
Rule: "Never promise >10% discount" (GLOBAL, is_hard_constraint=True)

→ Rule doesn't match "weather" semantically
→ Rule is NOT in prompt (keeps context focused)
→ Agent: "I don't know the weather, but here's 25% off!"
→ GLOBAL hard constraints are ALWAYS enforced post-generation
→ Violation CAUGHT
```

**Implementation:**
```python
async def get_rules_to_enforce(
    self,
    matched_rules: list[MatchedRule],
    tenant_id: UUID,
    agent_id: UUID,
) -> list[Rule]:
    """Get all rules that need enforcement."""

    # 1. Hard constraints from matched rules
    rules_to_enforce = [
        mr.rule for mr in matched_rules
        if mr.rule.is_hard_constraint
    ]
    matched_ids = {r.id for r in rules_to_enforce}

    # 2. GLOBAL hard constraints (always enforce, even if not matched)
    global_hard_constraints = await self._config_store.get_rules(
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=Scope.GLOBAL,
        hard_constraints_only=True,
    )

    # Add GLOBAL rules not already in the list
    for rule in global_hard_constraints:
        if rule.id not in matched_ids:
            rules_to_enforce.append(rule)

    return rules_to_enforce
```

---

## Variable Extraction

Before evaluating expressions, we need to extract variables from the response.

### Extraction Methods

**Method 1: Regex Patterns (Fast)**
```python
def _extract_common_patterns(self, text: str) -> dict[str, Any]:
    """Extract common patterns using regex."""
    variables = {}

    # Amounts: $50, 50.00, USD 50
    amount_match = re.search(r'(?:\$|USD|EUR)?\s*(\d+(?:\.\d{2})?)', text)
    if amount_match:
        variables['amount'] = float(amount_match.group(1))

    # Percentages: 10%, 10 percent
    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', text)
    if percent_match:
        variables['discount_percent'] = float(percent_match.group(1))

    # Boolean flags
    variables['contains_refund'] = bool(re.search(r'\brefund\b', text, re.I))
    variables['contains_promise'] = bool(re.search(r'\b(guarantee|promise)\b', text, re.I))

    return variables
```

**Method 2: LLM Extraction (Complex)**
```python
async def _extract_with_llm(self, response: str, fields: list[str]) -> dict[str, Any]:
    """Use LLM to extract structured variables."""
    prompt = f"""Extract these variables from the text. Return JSON only.

Text: "{response}"
Variables to extract: {fields}

Rules:
- Return null for variables not found
- Return numbers as numbers, not strings
"""
    return await self._llm.generate_structured(prompt=prompt, temperature=0.0)
```

### Combining with Session/Profile Variables

```python
async def extract_variables(
    self,
    response: str,
    session_variables: dict[str, Any],
    profile: CustomerProfile | None,
) -> dict[str, Any]:
    """Extract and merge all available variables."""

    # 1. Regex extraction (fast)
    variables = self._extract_common_patterns(response)

    # 2. LLM extraction if needed
    if self._needs_complex_extraction(rules_to_enforce):
        llm_vars = await self._extract_with_llm(response, required_fields)
        variables.update(llm_vars)

    # 3. Add session variables (user_tier, etc.)
    variables.update(session_variables)

    # 4. Add profile fields
    if profile:
        variables['user_tier'] = profile.get_field('tier')
        variables['is_vip'] = profile.get_field('tier') == 'VIP'

    return variables
```

---

## Deterministic Expression Evaluation (Lane 1)

Uses `simpleeval` for safe expression evaluation - no arbitrary code execution.

```python
from simpleeval import EvalWithCompoundTypes

class DeterministicEnforcer:
    """Evaluate enforcement expressions safely."""

    SAFE_FUNCTIONS = {
        'len': len, 'abs': abs, 'min': min, 'max': max,
        'lower': lambda s: s.lower() if isinstance(s, str) else s,
    }

    def evaluate(self, expression: str, variables: dict[str, Any]) -> bool:
        """Evaluate expression against variables.

        Returns True if rule is satisfied, False if violated.
        """
        evaluator = EvalWithCompoundTypes(
            names=variables,
            functions=self.SAFE_FUNCTIONS,
        )
        return bool(evaluator.eval(expression))
```

### Expression Syntax

| Expression | Meaning |
|------------|---------|
| `amount <= 50` | Amount must be ≤ 50 |
| `amount <= 50 or user_tier == 'VIP'` | VIPs can have any amount |
| `country in ['US', 'CA', 'UK']` | Must be in allowed countries |
| `discount_percent <= 10` | Max 10% discount |
| `not contains_competitor_mention` | No competitor mentions |
| `len(items) <= 5` | Max 5 items |

### Security: What's Blocked

```python
# These all raise errors - no code execution possible
"import os"                          # No imports
"__import__('os').system('rm -rf')"  # No builtins
"open('/etc/passwd').read()"         # No file access
"lambda x: x * 2"                    # No lambdas
"exec('print(1)')"                   # No exec
```

---

## LLM-as-Judge for Subjective Rules (Lane 2)

For rules without `enforcement_expression`, use LLM judgment on `action_text`.

```python
class SubjectiveEnforcer:
    """Use LLM to judge compliance with subjective rules."""

    async def evaluate(
        self,
        response: str,
        rule: Rule,
    ) -> tuple[bool, str]:
        """Judge if response complies with rule.

        Returns (passed, explanation).
        """
        prompt = f"""You are a compliance judge. Evaluate if this response follows the rule.

Rule: {rule.action_text}

Response to evaluate:
"{response}"

Does the response comply with the rule? Answer with:
- "PASS" if it complies
- "FAIL: <reason>" if it violates

Be strict but fair."""

        result = await self._llm.generate(prompt=prompt, temperature=0.0)

        if result.startswith("PASS"):
            return True, ""
        else:
            reason = result.replace("FAIL:", "").strip()
            return False, reason
```

### When to Use Each Lane

| Rule has `enforcement_expression`? | Lane | Method |
|-----------------------------------|------|--------|
| Yes | Lane 1 | simpleeval (deterministic) |
| No | Lane 2 | LLM-as-Judge (probabilistic) |

---

## Relevance Verification

Checks if response actually addresses the user's question.

**The Problem:**
```
User: "What is your refund policy?"
Agent: "Our office hours are 9 AM to 5 PM."  ← Irrelevant!
```

**The Check:** Compare User Query ↔ Agent Response

### Two Strategies

| Strategy | Speed | Accuracy | Model |
|----------|-------|----------|-------|
| Embedding Similarity | < 5ms | Good | all-MiniLM-L6-v2 |
| Cross-Encoder | 40-100ms | Better | ms-marco-MiniLM-L-6-v2 |

```python
class RelevanceVerifier:
    """Verify response addresses the user's question."""

    async def verify(
        self,
        user_query: str,
        response: str,
    ) -> tuple[float, bool]:
        """Returns (score, passed)."""

        # Check for valid refusal first
        if self._is_refusal_response(response):
            return 1.0, True  # Refusals are valid

        # Calculate relevance
        query_emb = await self._embed(user_query)
        response_emb = await self._embed(response)
        score = cosine_similarity(query_emb, response_emb)

        return score, score >= self._threshold
```

### ⚠️ The "I Don't Know" Trap

**Problem:** Refusal responses have low semantic similarity to questions.

```
User: "What is the airspeed velocity of an unladen swallow?"
Agent: "I'm sorry, I don't have that information."

Naive check: FAIL (score ~0.1) ← Wrong! This is a valid response.
```

**Solution:** Refusal bypass - detect refusal phrases before scoring.

```python
REFUSAL_PHRASES = [
    "i don't know", "i cannot answer", "i'm not able to",
    "no information", "outside my capabilities",
]

def _is_refusal_response(self, response: str) -> bool:
    """Detect valid refusal/uncertainty responses."""
    return any(phrase in response.lower() for phrase in REFUSAL_PHRASES)
```

---

## Grounding Verification

Checks if response is factually supported by the retrieved context.

**The Problem:**
```
Context: "We offer refunds up to $50 for US customers."
Agent: "I've processed your $200 refund with free shipping!"  ← Hallucination!
```

**The Check:** Compare Agent Response ↔ Source Context (NLI)

### Classification

| Result | Meaning | Score |
|--------|---------|-------|
| ENTAILMENT | Response supported by context | 1.0 |
| NEUTRAL | Response mentions things not in context | 0.5 |
| CONTRADICTION | Response contradicts context | 0.0 |

```python
class GroundingVerifier:
    """Verify response is grounded in provided context."""

    async def verify(
        self,
        response: str,
        context_chunks: list[str],
    ) -> tuple[float, str, bool]:
        """Returns (score, classification, passed)."""

        prompt = f"""Evaluate if the Response is supported by the Context.

Context: {' '.join(context_chunks)}

Response: {response}

Output ONE word: ENTAILMENT, NEUTRAL, or CONTRADICTION"""

        result = await self._llm.generate(prompt=prompt, temperature=0.0)

        if "ENTAILMENT" in result.upper():
            return 1.0, "entailment", True
        elif "NEUTRAL" in result.upper():
            return 0.5, "neutral", 0.5 >= self._threshold
        else:
            return 0.0, "contradiction", False
```

---

## Configuration

### Pipeline Configuration (Extended)

```python
# focal/config/models/pipeline.py

class EnforcementConfig(BaseModel):
    """Configuration for enforcement step."""

    enabled: bool = True
    max_retries: int = Field(default=1, ge=0, le=3)

    # Lane 1: Deterministic enforcement
    deterministic_enabled: bool = Field(
        default=True,
        description="Enable expression-based enforcement for rules with enforcement_expression"
    )

    # Lane 2: LLM-as-Judge
    llm_judge_enabled: bool = Field(
        default=True,
        description="Enable LLM judgment for subjective rules without expressions"
    )
    llm_judge_models: list[str] = Field(
        default=["openrouter/anthropic/claude-3-haiku"],
    )

    # Always-enforce GLOBAL hard constraints
    always_enforce_global: bool = Field(
        default=True,
        description="Always enforce GLOBAL hard constraints, even if not matched"
    )

    # Relevance verification
    relevance_check_enabled: bool = Field(default=False)
    relevance_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_strategy: Literal["embedding", "cross_encoder"] = "embedding"
    relevance_refusal_bypass: bool = Field(default=True)

    # Grounding verification
    grounding_check_enabled: bool = Field(default=False)
    grounding_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    grounding_strategy: Literal["llm_judge", "cross_encoder"] = "llm_judge"
```

### TOML Configuration

```toml
# config/default.toml

[pipeline.enforcement]
enabled = true
max_retries = 1

# Lane 1: Deterministic (for rules with enforcement_expression)
deterministic_enabled = true

# Lane 2: LLM-as-Judge (for subjective rules)
llm_judge_enabled = true
llm_judge_models = [
    "openrouter/anthropic/claude-3-haiku",
    "openai/gpt-4o-mini",
]

# Always enforce GLOBAL hard constraints
always_enforce_global = true

# Relevance verification (optional)
relevance_check_enabled = false
relevance_threshold = 0.5
relevance_strategy = "embedding"
relevance_refusal_bypass = true

# Grounding verification (optional)
grounding_check_enabled = false
grounding_threshold = 0.75
grounding_strategy = "llm_judge"
```

```toml
# config/production.toml

[pipeline.enforcement]
max_retries = 2
relevance_check_enabled = true
grounding_check_enabled = true
grounding_threshold = 0.8
```

---

## Example Rules

### Deterministic Rule (Lane 1)

```python
Rule(
    name="Refund Limit",
    condition_text="when response commits to a refund amount",
    action_text="limit refunds to $50 for standard customers, VIPs unlimited",
    enforcement_expression="amount <= 50 or user_tier == 'VIP'",
    scope=Scope.GLOBAL,
    is_hard_constraint=True,
)
```

### Subjective Rule (Lane 2)

```python
Rule(
    name="Professional Tone",
    condition_text="when responding to customer complaints",
    action_text="maintain professional and empathetic tone, acknowledge frustration",
    enforcement_expression=None,  # No expression = LLM-as-Judge
    scope=Scope.SCENARIO,
    scope_id=complaint_scenario_id,
    is_hard_constraint=False,  # Soft constraint
)
```

### Silent Guardrail (Always Enforced)

```python
Rule(
    name="Competitor Mention Ban",
    condition_text="any response",  # Broad - but won't bloat prompt
    action_text="never mention competitor products by name",
    enforcement_expression="not contains_competitor_mention",
    scope=Scope.GLOBAL,  # + is_hard_constraint = always enforced
    is_hard_constraint=True,
)
```

---

## Integration with Existing Code

### Extended EnforcementValidator

```python
# focal/alignment/enforcement/validator.py

class EnforcementValidator:
    """Validate responses against hard constraint rules."""

    def __init__(
        self,
        config_store: AgentConfigStore,
        response_generator: ResponseGenerator,
        deterministic_enforcer: DeterministicEnforcer,
        subjective_enforcer: SubjectiveEnforcer,
        relevance_verifier: RelevanceVerifier | None,
        grounding_verifier: GroundingVerifier | None,
        config: EnforcementConfig,
    ) -> None:
        self._config_store = config_store
        self._response_generator = response_generator
        self._deterministic = deterministic_enforcer
        self._subjective = subjective_enforcer
        self._relevance = relevance_verifier
        self._grounding = grounding_verifier
        self._config = config

    async def validate(
        self,
        response: str,
        context: Context,
        matched_rules: list[MatchedRule],
        session: Session,
        context_chunks: list[str] | None = None,
    ) -> EnforcementResult:
        """Validate response against all applicable rules."""

        violations = []

        # 1. Collect rules to enforce
        rules = await self._get_rules_to_enforce(
            matched_rules=matched_rules,
            tenant_id=session.tenant_id,
            agent_id=session.agent_id,
        )

        # 2. Extract variables (if any rule has enforcement_expression)
        variables = {}
        if any(r.enforcement_expression for r in rules):
            variables = await self._extract_variables(
                response=response,
                session=session,
            )

        # 3. Evaluate each rule
        for rule in rules:
            if rule.enforcement_expression:
                # Lane 1: Deterministic
                passed = self._deterministic.evaluate(
                    rule.enforcement_expression, variables
                )
                if not passed:
                    violations.append(ConstraintViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        violation_type="expression_failed",
                        details=f"Expression '{rule.enforcement_expression}' evaluated to False",
                    ))
            else:
                # Lane 2: LLM-as-Judge
                passed, reason = await self._subjective.evaluate(response, rule)
                if not passed:
                    violations.append(ConstraintViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        violation_type="llm_judge_failed",
                        details=reason,
                    ))

        # 4. Global checks
        if self._config.relevance_check_enabled and self._relevance:
            score, passed = await self._relevance.verify(
                context.user_message, response
            )
            if not passed:
                violations.append(ConstraintViolation(
                    rule_id=None,
                    rule_name="Relevance Check",
                    violation_type="relevance_failed",
                    details=f"Relevance score {score:.2f} below threshold",
                ))

        if self._config.grounding_check_enabled and self._grounding:
            score, classification, passed = await self._grounding.verify(
                response, context_chunks or []
            )
            if not passed:
                violations.append(ConstraintViolation(
                    rule_id=None,
                    rule_name="Grounding Check",
                    violation_type="grounding_failed",
                    details=f"Classification: {classification}, score: {score:.2f}",
                ))

        # 5. Handle violations
        if violations and self._config.max_retries > 0:
            # Attempt regeneration
            ...

        return EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
            ...
        )
```

---

## Future: Tool Call Verification

Currently, verification runs after final response generation. A future enhancement will apply grounding and relevance checks after tool/retrieval calls:

```
[Tool Call (e.g., RAG retrieval)] → [Relevance Check] → [Continue with verified context]
```

This will be implemented when integrating with the Tool Gateway.

---

## Model Recommendations for CPU Deployment

When self-hosting on CPU, use optimized ONNX models:

| Check | Model | Size | Latency |
|-------|-------|------|---------|
| Grounding (NLI) | `cross-encoder/nli-deberta-v3-base` | ~300MB | ~80ms |
| Relevance (Ranking) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~90MB | ~50ms |

**Total**: < 1GB RAM, ~130ms latency (or ~80ms parallel)

### Why Two Separate Models?

- **Grounding (NLI)**: Trained on entailment datasets. Answers "Does A support B?"
- **Relevance (MS-MARCO)**: Trained on query-passage ranking. Answers "Is this a good answer?"

Using the wrong model type gives poor results.

---

## Dependencies

Add to `pyproject.toml`:

```toml
[project.dependencies]
simpleeval = "*"  # Safe expression evaluation
```

Optional for CPU deployment with local models:
```toml
[project.optional-dependencies]
local-models = [
    "optimum[onnxruntime]",
]
```

---

## Summary

| Enhancement | What It Does | Uses |
|-------------|--------------|------|
| `enforcement_expression` on Rule | Formal expression for deterministic checks | simpleeval |
| Lane 1 (Deterministic) | 100% reliable verification of quantitative rules | Expression evaluation |
| Lane 2 (LLM-as-Judge) | ~90% reliable verification of subjective rules | LLM judgment |
| Always-enforce GLOBAL | GLOBAL + is_hard_constraint rules enforced on every response | Existing scope system |
| Relevance verification | Check response addresses the question | Embedding similarity |
| Grounding verification | Check response is factually grounded | NLI classification |
