# Phase 10: Enforcement & Guardrails - Implementation Checklist

> **Reference Documents**:
> - `docs/focal_turn_pipeline/README.md` (Phase 10, P10.1-P10.10)
> - `docs/focal_turn_pipeline/analysis/gap_analysis.md` (Phase 10 gaps)
> - `docs/design/old/enhanced-enforcement.md` (Two-lane enforcement design)
> - `CLAUDE.md` (Enforcement section)

---

## Phase Overview

**Goal**: Implement two-lane enforcement (deterministic + LLM-as-Judge) with GLOBAL constraint enforcement and optional relevance/grounding checks.

**Current State**: ~25% implemented - only basic phrase matching exists.

**Critical Gap**: GLOBAL hard constraints are NOT always enforced (production blocker).

**Key Components**:
- **Lane 1**: Deterministic expression evaluation via `simpleeval` for quantitative rules
- **Lane 2**: LLM-as-Judge for subjective rules without expressions
- **Always-enforce**: GLOBAL hard constraints must be checked on EVERY response
- **Variable extraction**: Extract amounts, percentages, flags from response text
- **Relevance/Grounding**: Optional quality checks (bypass for valid refusals)

---

## CRITICAL: GLOBAL Hard Constraints (PRODUCTION BLOCKER)

### Why This Matters

**Current Problem** (`engine.py:976`):
```python
hard_rules = [m.rule for m in matched_rules if m.rule.is_hard_constraint]
# ONLY checks MATCHED rules!
```

**Example Failure Scenario**:
```
User: "What's the weather?"
GLOBAL Rule: "Never promise >10% discount" (is_hard_constraint=True)

→ Rule doesn't match "weather" semantically
→ Rule NOT retrieved, NOT in hard_rules
→ Response: "Weather unavailable. Here's 25% off!"
→ GLOBAL constraint NOT enforced ❌
```

**Required Behavior**:
- GLOBAL rules with `is_hard_constraint=True` must ALWAYS be enforced
- These are safety guardrails, not retrieval targets
- They don't bloat the prompt (only checked post-generation)

---

## 1. Rule Model Enhancement

### 1.1 Add enforcement_expression Field

- [ ] **Add enforcement_expression field to Rule model**
  - File: `soldier/alignment/models/rule.py`
  - Action: Add field after `is_hard_constraint`
  - Details:
    ```python
    enforcement_expression: str | None = Field(
        default=None,
        description="Formal expression for deterministic enforcement (e.g., 'amount <= 50')"
    )
    ```
  - Why: Enables deterministic evaluation (Lane 1) for quantitative constraints
  - Example: `"amount <= 50 or user_tier == 'VIP'"`

### 1.2 Update Database Schema

- [ ] **Create Alembic migration for enforcement_expression**
  - File: `alembic/versions/012_add_enforcement_expression.py`
  - Action: Create migration
  - Details: Add nullable `TEXT` column `enforcement_expression` to `rules` table
  - Why: Persist the new field

### 1.3 Update ConfigStore Interface

- [ ] **Add enforcement_expression to ConfigStore queries**
  - File: `soldier/alignment/stores/config_store.py`
  - Action: Verify interface supports new field
  - Details: No changes needed - ConfigStore already loads full Rule models
  - Why: Ensure stores handle the new field

---

## 2. GLOBAL Constraint Always-Enforce

### 2.1 Add get_global_hard_constraints to ConfigStore

- [x] **Add method to fetch GLOBAL hard constraints**
  - File: `soldier/alignment/stores/agent_config_store.py`
  - Action: Method already exists - get_rules() with scope=GLOBAL parameter
  - **Implemented**: Can use get_rules(scope=Scope.GLOBAL, enabled_only=True) to fetch GLOBAL hard constraints
  - Details:
    ```python
    @abstractmethod
    async def get_global_hard_constraints(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Rule]:
        """Fetch all GLOBAL hard constraints for always-enforce behavior."""
        pass
    ```

### 2.2 Implement in InMemoryConfigStore

- [ ] **Implement get_global_hard_constraints**
  - File: `soldier/alignment/stores/inmemory.py`
  - Action: Add implementation
  - Details: Filter rules by `scope=GLOBAL` and `is_hard_constraint=True` and `enabled=True`

### 2.3 Implement in PostgresConfigStore

- [ ] **Implement get_global_hard_constraints**
  - File: `soldier/alignment/stores/postgres.py`
  - Action: Add implementation
  - Details: SQL query with WHERE clause for scope, is_hard_constraint, enabled

---

## 3. Variable Extraction from Response

### 3.1 Create VariableExtractor Class

- [ ] **Create variable extraction service**
  - File: `soldier/alignment/enforcement/variable_extractor.py`
  - Action: Create new file
  - Details:
    - Class: `VariableExtractor`
    - Method: `extract_variables(response: str, session: Session, profile: CustomerProfile | None) -> dict[str, Any]`
    - Implements regex extraction for common patterns (amounts, percentages, flags)
    - Optional: LLM extraction for complex cases
  - Dependencies:
    - `re` (stdlib)
    - `soldier.conversation.models.session.Session`
    - `soldier.profile.models.CustomerProfile`

### 3.2 Implement Regex Pattern Extraction

- [ ] **Add regex extraction methods**
  - File: `soldier/alignment/enforcement/variable_extractor.py`
  - Action: Add to VariableExtractor class
  - Details:
    - `_extract_amounts(text: str) -> dict`: Match `$50`, `USD 50`, `50.00`
    - `_extract_percentages(text: str) -> dict`: Match `10%`, `10 percent`
    - `_extract_boolean_flags(text: str) -> dict`: Match presence of keywords (refund, promise, guarantee)
    - Return merged dict of extracted variables

### 3.3 Implement LLM Extraction (Optional)

- [ ] **Add LLM-based extraction for complex cases**
  - File: `soldier/alignment/enforcement/variable_extractor.py`
  - Action: Add method
  - Details:
    - Method: `_extract_with_llm(response: str, required_fields: list[str]) -> dict[str, Any]`
    - Uses `LLMExecutor` with structured output
    - Temperature: 0.0 (deterministic)
    - Prompt: Extract specific fields from text as JSON
  - Why: Handles complex extractions regex can't catch

### 3.4 Merge with Session and Profile Variables

- [ ] **Merge extracted variables with context**
  - File: `soldier/alignment/enforcement/variable_extractor.py`
  - Action: Implement in extract_variables method
  - Details:
    - Priority: response vars > session vars > profile vars
    - Add `user_tier`, `is_vip`, `country`, etc. from profile
    - Add session variables (custom vars set during conversation)
  - Why: Enforcement expressions need full variable context

---

## 4. Deterministic Expression Evaluation (Lane 1)

### 4.1 Add simpleeval Dependency

- [ ] **Add simpleeval to project dependencies**
  - File: `pyproject.toml`
  - Action: Add dependency
  - Details: Add `simpleeval = "*"` to `[project.dependencies]`
  - Command: `uv add simpleeval`
  - Why: Safe expression evaluation without arbitrary code execution

### 4.2 Create DeterministicEnforcer Class

- [ ] **Create deterministic enforcement service**
  - File: `soldier/alignment/enforcement/deterministic_enforcer.py`
  - Action: Create new file
  - Details:
    - Class: `DeterministicEnforcer`
    - Method: `evaluate(expression: str, variables: dict[str, Any]) -> tuple[bool, str | None]`
    - Uses `simpleeval.EvalWithCompoundTypes`
    - Returns: (passed: bool, error_message: str | None)
  - Why: 100% deterministic constraint checking for quantitative rules

### 4.3 Define Safe Functions Whitelist

- [ ] **Add safe function whitelist**
  - File: `soldier/alignment/enforcement/deterministic_enforcer.py`
  - Action: Add class constant
  - Details:
    ```python
    SAFE_FUNCTIONS = {
        'len': len,
        'abs': abs,
        'min': min,
        'max': max,
        'lower': lambda s: s.lower() if isinstance(s, str) else s,
        'upper': lambda s: s.upper() if isinstance(s, str) else s,
    }
    ```
  - Why: Limit expression capabilities to safe operations only

### 4.4 Implement Expression Evaluation

- [ ] **Implement safe expression evaluation**
  - File: `soldier/alignment/enforcement/deterministic_enforcer.py`
  - Action: Implement evaluate method
  - Details:
    - Create `EvalWithCompoundTypes` with variables and safe functions
    - Catch `simpleeval` exceptions (syntax errors, undefined variables)
    - Return tuple: (True, None) if passed, (False, error_msg) if failed/error
  - Example expressions:
    - `amount <= 50`
    - `amount <= 50 or user_tier == 'VIP'`
    - `discount_percent <= 10`
    - `not contains_competitor_mention`
    - `country in ['US', 'CA', 'UK']`

### 4.5 Add Expression Validation Utility

- [ ] **Add expression syntax validator**
  - File: `soldier/alignment/enforcement/deterministic_enforcer.py`
  - Action: Add static method
  - Details:
    - Method: `validate_syntax(expression: str) -> tuple[bool, str | None]`
    - Attempts to parse expression with empty variables
    - Returns validation result (for API/UI feedback)
  - Why: Catch syntax errors when creating rules, not at runtime

---

## 5. LLM-as-Judge (Lane 2)

### 5.1 Create SubjectiveEnforcer Class

- [ ] **Create LLM-based enforcement service**
  - File: `soldier/alignment/enforcement/subjective_enforcer.py`
  - Action: Create new file
  - Details:
    - Class: `SubjectiveEnforcer`
    - Constructor: Takes `LLMExecutor` and `EnforcementConfig`
    - Method: `evaluate(response: str, rule: Rule) -> tuple[bool, str]`
    - Returns: (passed: bool, explanation: str)
  - Why: Handle subjective constraints that can't be expressed as code

### 5.2 Create LLM Judge Prompt Template

- [ ] **Create Jinja2 prompt template**
  - File: `soldier/alignment/enforcement/prompts/judge_rule_compliance.jinja2`
  - Action: Create new file
  - Details:
    ```jinja2
    You are a compliance judge. Evaluate if this response follows the rule.

    Rule: {{ rule.action_text }}

    Response to evaluate:
    "{{ response }}"

    Does the response comply with the rule? Answer with:
    - "PASS" if it complies
    - "FAIL: <reason>" if it violates

    Be strict but fair.
    ```
  - Why: Configurable prompts, not hardcoded strings

### 5.3 Implement LLM Judgment

- [ ] **Implement subjective rule evaluation**
  - File: `soldier/alignment/enforcement/subjective_enforcer.py`
  - Action: Implement evaluate method
  - Details:
    - Load template, render with rule and response
    - Call LLM with temperature=0.0 (deterministic)
    - Parse result: "PASS" → (True, ""), "FAIL: reason" → (False, reason)
    - Use model from config (`llm_judge_models[0]`)
  - Example rules:
    - "Maintain professional and empathetic tone"
    - "Acknowledge customer frustration"
    - "Never sound dismissive or robotic"

---

## 6. Enhanced EnforcementValidator

### 6.1 Update EnforcementValidator Constructor

- [ ] **Add new dependencies to constructor**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Modify `__init__`
  - Details:
    - Add: `config_store: ConfigStore`
    - Add: `variable_extractor: VariableExtractor`
    - Add: `deterministic_enforcer: DeterministicEnforcer`
    - Add: `subjective_enforcer: SubjectiveEnforcer`
    - Add: `session: Session` (pass to validate method instead)
    - Add: `profile: CustomerProfile | None` (pass to validate method)
    - Add: `config: EnforcementConfig`

### 6.2 Implement get_rules_to_enforce

- [x] **Add method to collect all rules for enforcement**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Add private method
  - **Implemented**: Added _get_rules_to_enforce() that fetches GLOBAL hard constraints and merges with matched rules
  - Details:
    ```python
    async def _get_rules_to_enforce(
        self,
        matched_rules: list[MatchedRule],
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Rule]:
        # 1. Hard constraints from matched rules
        rules = [mr.rule for mr in matched_rules if mr.rule.is_hard_constraint]
        matched_ids = {r.id for r in rules}

        # 2. GLOBAL hard constraints (always enforce)
        if self._config.always_enforce_global:
            global_hard = await self._config_store.get_global_hard_constraints(
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            for rule in global_hard:
                if rule.id not in matched_ids:
                    rules.append(rule)

        return rules
    ```
  - Why: **CRITICAL** - This fixes the production blocker

### 6.3 Update validate Method - Add Variable Extraction

- [ ] **Extract variables before enforcement**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Update validate method
  - Details:
    - Call `_get_rules_to_enforce()` instead of using `hard_rules` parameter
    - Check if any rule has `enforcement_expression`
    - If yes, call `variable_extractor.extract_variables(response, session, profile)`
    - Store extracted variables for Lane 1 evaluation

### 6.4 Update validate Method - Two-Lane Evaluation

- [ ] **Implement two-lane enforcement logic**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Replace `_detect_violations` with two-lane logic
  - Details:
    ```python
    for rule in rules_to_enforce:
        if rule.enforcement_expression:
            # Lane 1: Deterministic
            if self._config.deterministic_enabled:
                passed, error = self._deterministic.evaluate(
                    rule.enforcement_expression, variables
                )
                if not passed:
                    violations.append(ConstraintViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        violation_type="expression_failed",
                        details=error or f"Expression '{rule.enforcement_expression}' evaluated to False",
                    ))
        else:
            # Lane 2: LLM-as-Judge
            if self._config.llm_judge_enabled:
                passed, reason = await self._subjective.evaluate(response, rule)
                if not passed:
                    violations.append(ConstraintViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        violation_type="llm_judge_failed",
                        details=reason,
                    ))
    ```

### 6.5 Keep Existing Regeneration Logic

- [ ] **Preserve regeneration and fallback behavior**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Keep existing `_regenerate` method
  - Details:
    - Regeneration already works correctly
    - Re-run two-lane evaluation on regenerated response
    - Fallback handling done by `FallbackHandler` (unchanged)

---

## 7. Optional: Relevance & Grounding Checks

### 7.1 Create RelevanceVerifier Class (Optional)

- [ ] **Create relevance checking service**
  - File: `soldier/alignment/enforcement/relevance_verifier.py`
  - Action: Create new file (optional feature)
  - Details:
    - Class: `RelevanceVerifier`
    - Method: `verify(user_query: str, response: str) -> tuple[float, bool]`
    - Uses embedding similarity (query ↔ response)
    - Bypass check if response contains refusal phrases
  - Why: Detect when response doesn't address the question

### 7.2 Implement Refusal Detection

- [ ] **Add refusal phrase detection**
  - File: `soldier/alignment/enforcement/relevance_verifier.py`
  - Action: Add method
  - Details:
    ```python
    REFUSAL_PHRASES = [
        "i don't know", "i cannot answer", "i'm not able to",
        "no information", "outside my capabilities",
        "out of scope", "knowledge gap"
    ]

    def _is_refusal_response(self, response: str) -> bool:
        return any(phrase in response.lower() for phrase in REFUSAL_PHRASES)
    ```
  - Why: Valid "I don't know" responses have low similarity but are correct

### 7.3 Create GroundingVerifier Class (Optional)

- [ ] **Create grounding checking service**
  - File: `soldier/alignment/enforcement/grounding_verifier.py`
  - Action: Create new file (optional feature)
  - Details:
    - Class: `GroundingVerifier`
    - Method: `verify(response: str, context_chunks: list[str]) -> tuple[float, str, bool]`
    - Uses LLM-based NLI (Natural Language Inference)
    - Returns: (score, classification, passed)
    - Classifications: ENTAILMENT, NEUTRAL, CONTRADICTION
  - Why: Detect hallucinations (response not supported by context)

### 7.4 Integrate Optional Checks into Validator

- [ ] **Add optional checks to validate method**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Add after two-lane evaluation
  - Details:
    ```python
    # Optional: Relevance check
    if self._config.relevance_check_enabled and self._relevance:
        score, passed = await self._relevance.verify(user_query, response)
        if not passed:
            violations.append(ConstraintViolation(
                rule_id=None,
                rule_name="Relevance Check",
                violation_type="relevance_failed",
                details=f"Relevance score {score:.2f} below threshold {self._config.relevance_threshold}",
            ))

    # Optional: Grounding check
    if self._config.grounding_check_enabled and self._grounding:
        score, classification, passed = await self._grounding.verify(response, context_chunks or [])
        if not passed:
            violations.append(ConstraintViolation(
                rule_id=None,
                rule_name="Grounding Check",
                violation_type="grounding_failed",
                details=f"Classification: {classification}, score: {score:.2f}",
            ))
    ```

---

## 8. Configuration

### 8.1 Extend EnforcementConfig Model

- [ ] **Add enforcement configuration fields**
  - File: `soldier/config/models/pipeline.py`
  - Action: Extend `EnforcementConfig` class
  - Details:
    ```python
    class EnforcementConfig(BaseModel):
        """Configuration for enforcement step."""

        enabled: bool = True
        max_retries: int = Field(default=1, ge=0, le=3)

        # Lane 1: Deterministic
        deterministic_enabled: bool = Field(
            default=True,
            description="Enable expression-based enforcement"
        )

        # Lane 2: LLM-as-Judge
        llm_judge_enabled: bool = Field(
            default=True,
            description="Enable LLM judgment for subjective rules"
        )
        llm_judge_models: list[str] = Field(
            default=["openrouter/anthropic/claude-3-haiku"],
        )

        # Always-enforce GLOBAL
        always_enforce_global: bool = Field(
            default=True,
            description="Always enforce GLOBAL hard constraints"
        )

        # Optional: Relevance
        relevance_check_enabled: bool = Field(default=False)
        relevance_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        relevance_refusal_bypass: bool = Field(default=True)

        # Optional: Grounding
        grounding_check_enabled: bool = Field(default=False)
        grounding_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    ```

### 8.2 Update TOML Configuration

- [ ] **Add enforcement configuration to TOML**
  - File: `config/default.toml`
  - Action: Update `[pipeline.enforcement]` section
  - Details:
    ```toml
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

    # Optional: Relevance verification
    relevance_check_enabled = false
    relevance_threshold = 0.5
    relevance_refusal_bypass = true

    # Optional: Grounding verification
    grounding_check_enabled = false
    grounding_threshold = 0.75
    ```

---

## 9. AlignmentEngine Integration

### 9.1 Update Engine Constructor

- [ ] **Add enforcement components to engine DI**
  - File: `soldier/alignment/engine.py`
  - Action: Update `__init__` or factory
  - Details:
    - Instantiate `VariableExtractor`
    - Instantiate `DeterministicEnforcer`
    - Instantiate `SubjectiveEnforcer` with LLM executor
    - Instantiate optional `RelevanceVerifier` and `GroundingVerifier`
    - Pass all to `EnforcementValidator` constructor

### 9.2 Update Engine process_turn - Pass Session and Profile

- [ ] **Pass session and profile to validator**
  - File: `soldier/alignment/engine.py`
  - Action: Update enforcement call in `process_turn`
  - Details:
    - Add `session` parameter to `validator.validate()`
    - Add `profile` parameter (load from ProfileStore if needed)
    - Remove `hard_rules` parameter (validator fetches itself now)

---

## 10. Tests

### 10.1 Unit Tests - VariableExtractor

- [ ] **Test variable extraction from response**
  - File: `tests/unit/alignment/enforcement/test_variable_extractor.py`
  - Action: Create new file
  - Tests:
    - `test_extract_amount_dollar_format()`
    - `test_extract_percentage()`
    - `test_extract_boolean_flags()`
    - `test_merge_with_session_variables()`
    - `test_merge_with_profile_fields()`
    - `test_profile_takes_precedence_over_session()`

### 10.2 Unit Tests - DeterministicEnforcer

- [ ] **Test expression evaluation**
  - File: `tests/unit/alignment/enforcement/test_deterministic_enforcer.py`
  - Action: Create new file
  - Tests:
    - `test_evaluate_simple_comparison()` - `amount <= 50`
    - `test_evaluate_with_or_condition()` - `amount <= 50 or user_tier == 'VIP'`
    - `test_evaluate_list_membership()` - `country in ['US', 'CA']`
    - `test_evaluate_boolean_flag()` - `not contains_competitor`
    - `test_evaluate_with_functions()` - `len(items) <= 5`
    - `test_undefined_variable_returns_false()`
    - `test_syntax_error_returns_false()`
    - `test_validate_syntax_utility()`

### 10.3 Unit Tests - SubjectiveEnforcer

- [ ] **Test LLM-as-Judge evaluation**
  - File: `tests/unit/alignment/enforcement/test_subjective_enforcer.py`
  - Action: Create new file
  - Tests:
    - `test_evaluate_professional_tone_pass()`
    - `test_evaluate_professional_tone_fail()`
    - `test_evaluate_empathy_rule()`
    - `test_llm_returns_pass()`
    - `test_llm_returns_fail_with_reason()`

### 10.4 Unit Tests - EnforcementValidator (Enhanced)

- [ ] **Test GLOBAL constraint always-enforce**
  - File: `tests/unit/alignment/enforcement/test_validator.py`
  - Action: Update existing tests
  - Tests:
    - `test_get_rules_to_enforce_includes_matched_hard_rules()`
    - `test_get_rules_to_enforce_includes_global_hard_rules()` - **CRITICAL**
    - `test_global_rule_not_matched_but_still_enforced()` - **CRITICAL**
    - `test_global_rule_not_duplicated_if_also_matched()`
    - `test_lane1_deterministic_evaluation()`
    - `test_lane2_llm_judge_evaluation()`
    - `test_rule_with_expression_uses_lane1()`
    - `test_rule_without_expression_uses_lane2()`
    - `test_extraction_only_runs_if_needed()`

### 10.5 Unit Tests - RelevanceVerifier (Optional)

- [ ] **Test relevance checking**
  - File: `tests/unit/alignment/enforcement/test_relevance_verifier.py`
  - Action: Create new file (if implementing)
  - Tests:
    - `test_relevant_response_passes()`
    - `test_irrelevant_response_fails()`
    - `test_refusal_response_bypasses_check()` - **CRITICAL**
    - `test_i_dont_know_passes()`

### 10.6 Unit Tests - GroundingVerifier (Optional)

- [ ] **Test grounding checking**
  - File: `tests/unit/alignment/enforcement/test_grounding_verifier.py`
  - Action: Create new file (if implementing)
  - Tests:
    - `test_grounded_response_passes()`
    - `test_hallucinated_response_fails()`
    - `test_entailment_classification()`
    - `test_contradiction_classification()`

### 10.7 Integration Tests - Full Enforcement Flow

- [ ] **Test end-to-end enforcement**
  - File: `tests/integration/alignment/test_enforcement_flow.py`
  - Action: Create new file
  - Tests:
    - `test_deterministic_rule_blocks_violation()`
    - `test_subjective_rule_llm_judge_blocks()`
    - `test_global_rule_enforced_without_matching()` - **CRITICAL**
    - `test_regeneration_fixes_violation()`
    - `test_fallback_after_failed_regeneration()`
    - `test_both_lanes_run_in_same_turn()`

### 10.8 Contract Tests - ConfigStore

- [ ] **Test get_global_hard_constraints**
  - File: `tests/contract/test_config_store_contract.py`
  - Action: Add test
  - Details:
    - `test_get_global_hard_constraints_returns_only_global()`
    - `test_get_global_hard_constraints_returns_only_hard()`
    - `test_get_global_hard_constraints_returns_only_enabled()`
    - `test_get_global_hard_constraints_filters_by_tenant_agent()`

---

## 11. Documentation Updates

### 11.1 Update CLAUDE.md

- [ ] **Document enforcement architecture**
  - File: `CLAUDE.md`
  - Action: Update enforcement section
  - Details:
    - Two-lane enforcement (deterministic + LLM-as-Judge)
    - `enforcement_expression` field usage
    - GLOBAL always-enforce behavior
    - Variable extraction approach
    - When to use each lane

### 11.2 Update API Documentation

- [ ] **Document enforcement_expression in Rule API**
  - File: API docs (OpenAPI/Swagger)
  - Action: Add field to Rule schema
  - Details:
    - Field description and examples
    - Expression syntax guide
    - Validation endpoint for testing expressions

---

## 12. Observability

### 12.1 Add Enforcement Metrics

- [ ] **Add two-lane enforcement metrics**
  - File: `soldier/observability/metrics.py`
  - Action: Add metrics
  - Details:
    ```python
    # Lane 1
    enforcement_deterministic_total = Counter(
        "enforcement_deterministic_total",
        "Total deterministic expression evaluations",
        ["tenant_id", "agent_id", "result"]  # result: pass/fail/error
    )

    # Lane 2
    enforcement_llm_judge_total = Counter(
        "enforcement_llm_judge_total",
        "Total LLM-as-Judge evaluations",
        ["tenant_id", "agent_id", "result"]
    )

    # GLOBAL enforcement
    enforcement_global_rules_checked = Counter(
        "enforcement_global_rules_checked",
        "GLOBAL hard constraints checked",
        ["tenant_id", "agent_id"]
    )

    # Variable extraction
    enforcement_variable_extraction_time = Histogram(
        "enforcement_variable_extraction_time_ms",
        "Time to extract variables from response",
        ["tenant_id", "agent_id", "method"]  # method: regex/llm
    )
    ```

### 12.2 Add Structured Logging

- [ ] **Log enforcement decisions**
  - File: `soldier/alignment/enforcement/validator.py`
  - Action: Add log statements
  - Details:
    ```python
    logger.info(
        "enforcement_lane1_evaluated",
        rule_id=str(rule.id),
        rule_name=rule.name,
        expression=rule.enforcement_expression,
        variables=variables,
        result=passed,
    )

    logger.warning(
        "enforcement_violation_detected",
        rule_id=str(rule.id),
        rule_name=rule.name,
        lane="deterministic" or "llm_judge",
        violation_type=violation.violation_type,
        details=violation.details,
    )

    logger.info(
        "enforcement_global_rules_enforced",
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        global_rule_count=len(global_rules),
        matched_rule_count=len(matched_rules),
    )
    ```

---

## Priority Order

### Tier 1: Production Blockers (Complete First)

1. **GLOBAL always-enforce** (Items 2.1-2.3, 6.2)
   - Why: Fixes critical safety gap
2. **Rule model enhancement** (Items 1.1-1.2)
   - Why: Enables deterministic enforcement
3. **Variable extraction** (Items 3.1-3.4)
   - Why: Required for Lane 1
4. **Deterministic enforcer** (Items 4.1-4.5)
   - Why: Core Lane 1 implementation

### Tier 2: Core Two-Lane System

5. **LLM-as-Judge** (Items 5.1-5.3)
   - Why: Core Lane 2 implementation
6. **Enhanced validator** (Items 6.1-6.5)
   - Why: Integrates both lanes
7. **Configuration** (Items 8.1-8.2)
   - Why: Makes system configurable
8. **Engine integration** (Items 9.1-9.2)
   - Why: Wires it all together

### Tier 3: Testing & Observability

9. **Unit tests** (Items 10.1-10.6)
   - Why: Verify correctness
10. **Integration tests** (Items 10.7-10.8)
    - Why: End-to-end validation
11. **Metrics & logging** (Items 12.1-12.2)
    - Why: Production observability

### Tier 4: Optional Enhancements

12. **Relevance/Grounding checks** (Items 7.1-7.4)
    - Why: Nice-to-have quality checks
13. **Documentation** (Items 11.1-11.2)
    - Why: Always last

---

## Success Criteria

Phase 10 is complete when:

- [ ] `enforcement_expression` field exists on Rule model and in database
- [ ] GLOBAL hard constraints are ALWAYS enforced, even when not matched
- [ ] Variable extraction works for amounts, percentages, and flags
- [ ] Lane 1 (deterministic) evaluates expressions safely via simpleeval
- [ ] Lane 2 (LLM-as-Judge) evaluates subjective rules
- [ ] Both lanes can run in the same turn
- [ ] Configuration allows enabling/disabling each lane
- [ ] All unit tests pass (especially GLOBAL enforcement tests)
- [ ] Integration test validates full enforcement flow
- [ ] Metrics track both lanes and GLOBAL checks
- [ ] Production blocker is fixed (GLOBAL rules always enforced)

---

## Dependencies

### New Python Dependencies

- `simpleeval` - Safe expression evaluation (Lane 1)

### Existing Dependencies

- `soldier.providers.llm.base.LLMExecutor` - For LLM-as-Judge (Lane 2)
- `soldier.alignment.stores.config_store.ConfigStore` - Fetch GLOBAL rules
- `soldier.conversation.models.session.Session` - Session variables
- `soldier.profile.models.CustomerProfile` - Profile fields

### Optional Dependencies (for Relevance/Grounding)

- Embedding provider (already exists)
- Cross-encoder models (optional, for better accuracy)

---

## Notes

- **CRITICAL**: The GLOBAL always-enforce behavior fixes a production safety gap
- **Lane 1 is deterministic**: After variable extraction, expression evaluation is 100% reliable
- **Lane 2 is probabilistic**: LLM judgment is ~85-95% accurate
- **No prompt pollution**: GLOBAL rules only enforced post-generation, not added to prompt
- **Async everything**: All enforcement operations are async
- **Observability**: Log and track enforcement decisions for audit trail
- **Security**: `simpleeval` prevents arbitrary code execution
- **Graceful degradation**: If Lane 1 fails (syntax error), log and skip (don't crash)
- **Optional checks**: Relevance and grounding are optional features, can be added later

---

## Reference Materials

| Document | Section | What It Covers |
|----------|---------|----------------|
| `focal_turn_pipeline.md` | Phase 10 | P10.1-P10.10 step breakdown |
| `focal_pipeline_gap_analysis.md` | Phase 10 | Current gaps and critical issues |
| `old/enhanced-enforcement.md` | Full doc | Two-lane design, expression syntax, examples |
| `CLAUDE.md` | Enforcement section | Development guidelines |

---

**Last Updated**: 2025-01-15
**Phase Dependencies**: Phase 7 (Context Extraction), Phase 8 (Retrieval), Phase 10 (Generation)
**Estimated Effort**: 3-5 days for Tier 1-2, 2-3 days for Tier 3-4
