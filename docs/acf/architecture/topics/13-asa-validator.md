# ASA: Mechanic-Agnostic Meta-Agent

> **Topic**: Agent Setter Agent as mechanic-agnostic design-time validator and configuration assistant
> **Dependencies**: Brain interface, Side-Effect Policy (for alignment mechanic)
> **Impacts**: Tool validation, scenario safety, mechanic conformance, tenant onboarding

---

## Overview

**ASA (Agent Setter Agent)** is a **mechanic-agnostic meta-agent** that helps design, validate, and configure ANY Brain implementation. It is NOT specific to FOCAL's alignment mechanic.

### Key Capabilities

1. **Universal Conformance Testing** - Every Brain must pass ASA's conformance suite (tools via Toolbox, event emission, supersede checks, timeout handling, tenant isolation)
2. **Mechanic Discovery** - ASA can discover and work with any registered cognitive mechanic (alignment, ReAct, planner-executor, custom)
3. **Schema-Driven Configuration** - Mechanics expose their config schema; ASA generates wizards and validates against it
4. **Safety Validation** - Mechanic-specific validators ensure safety properties (e.g., checkpoints before irreversible actions in alignment)
5. **Plugin Architecture** - Custom mechanics can register with ASA and get full configuration/validation support

### Core Principle: Mechanic-Agnostic Design

ASA understands and validates **any cognitive mechanic**:

| Mechanic | ASA Helps Design | ASA Validates |
|----------|------------------|---------------|
| **Alignment (FOCAL)** | Scenarios, rules, templates, step design | Scenario completeness, rule conflicts, checkpoint placement |
| **ReAct** | Tool selection, prompt design, reasoning chains | Tool safety, prompt injection risks, loop detection |
| **Planner-Executor** | Plan templates, execution policies, rollback strategies | Plan feasibility, rollback coverage, resource limits |
| **Custom** | Whatever the mechanic needs (via plugin system) | Mechanic-specific constraints and safety invariants |

### The Reframe

| Original Proposal | New Approach |
|-------------------|--------------|
| Runtime agent with config write access | Design-time validation and assistance |
| FOCAL-specific scenario validator | Mechanic-agnostic brain configurator |
| Conversational configuration only | Wizard UI + validation API + conformance tests |
| Autonomous config changes | Suggestions requiring human approval |
| Production risk | Safe pre-deployment checks + runtime conformance |

### Why Design-Time + Conformance

A runtime agent that modifies production configurations is dangerous:
- Could create broken configurations
- Could set wrong safety policies
- Could expose security vulnerabilities
- No human review before changes go live

ASA is valuable as a **design-time assistant** that:
- Validates configurations before deployment
- Suggests improvements based on mechanic-specific best practices
- Generates edge-case handling
- Enforces mechanic-agnostic conformance requirements
- Runs conformance tests against any Brain implementation

---

## Brain Conformance Tests

**Every Brain implementation must pass ASA's conformance test suite**, regardless of which mechanic it implements.

### Universal Conformance Requirements

```python
class PipelineConformanceTests:
    """Conformance tests that EVERY Brain must pass.

    These are mechanic-agnostic safety and behavioral requirements.
    """

    async def test_tools_go_through_toolbox(self, brain: Brain, ctx: TurnContext):
        """All tool calls MUST go through the Toolbox (no direct execution)."""
        result = await brain.process_turn(ctx)

        # Verify all tool calls were logged through Toolbox
        assert all(
            call.source == "toolbox"
            for call in result.tool_calls
        ), "All tools must be executed via Toolbox"

    async def test_required_events_are_emitted(self, brain: Brain, ctx: TurnContext):
        """Brain MUST emit required lifecycle events."""
        events = []

        def capture_event(event):
            events.append(event)

        ctx.event_bus.subscribe(capture_event)
        result = await brain.process_turn(ctx)

        # Required events for all brains
        required_events = {"turn.started", "turn.completed"}
        emitted_events = {e.type for e in events}

        assert required_events.issubset(emitted_events), \
            f"Missing required events: {required_events - emitted_events}"

    async def test_supersede_checked_before_irreversible(
        self,
        brain: Brain,
        ctx: TurnContext
    ):
        """Brain MUST check for supersede BEFORE irreversible actions.

        This prevents executing irreversible tools when a newer agent version exists.
        """
        # Setup: Create superseding agent version
        await ctx.config_store.save_agent(
            ctx.agent.clone_with_version(ctx.agent.version + 1)
        )

        # Setup: Configure brain to use irreversible tool
        ctx.available_tools = [
            ToolDefinition(
                name="send_email",
                side_effect_policy=SideEffectPolicy.IRREVERSIBLE,
            )
        ]

        result = await brain.process_turn(ctx)

        # Brain should have detected supersede and NOT executed tool
        assert result.superseded, "Brain must detect supersede"
        assert len(result.tool_calls) == 0, \
            "No irreversible tools should execute when superseded"

    async def test_pipelineresult_contract(self, brain: Brain, ctx: TurnContext):
        """Brain MUST return well-formed BrainResult."""
        result = await brain.process_turn(ctx)

        # Required fields
        assert result.response is not None, "Must return response"
        assert result.session_state is not None, "Must return session state"
        assert isinstance(result.tool_calls, list), "tool_calls must be list"
        assert isinstance(result.events, list), "events must be list"

        # Metadata contract
        assert result.metadata.get("mechanic") is not None, \
            "Must declare which mechanic was used"
        assert result.metadata.get("pipeline_version") is not None, \
            "Must declare brain version"

    async def test_timeout_handling(self, brain: Brain, ctx: TurnContext):
        """Brain MUST respect timeout configuration."""
        ctx.config.pipeline_timeout_ms = 100  # Very short timeout

        # Inject slow tool
        ctx.available_tools = [
            ToolDefinition(name="slow_tool", estimated_duration_ms=5000)
        ]

        start = time.time()
        result = await brain.process_turn(ctx)
        duration_ms = (time.time() - start) * 1000

        # Should timeout gracefully
        assert duration_ms < 200, "Brain must respect timeout"
        assert result.timed_out, "Result should indicate timeout"

    async def test_tenant_isolation(self, brain: Brain, ctx: TurnContext):
        """Brain MUST NOT leak data across tenants."""
        tenant_a_ctx = ctx.clone_with_tenant("tenant-a")
        tenant_b_ctx = ctx.clone_with_tenant("tenant-b")

        # Process turn for tenant A
        result_a = await brain.process_turn(tenant_a_ctx)

        # Process turn for tenant B
        result_b = await brain.process_turn(tenant_b_ctx)

        # Verify no cross-contamination in session state
        assert result_a.session_state.tenant_id == "tenant-a"
        assert result_b.session_state.tenant_id == "tenant-b"

        # Verify no shared cache keys
        cache_keys_a = brain._get_cache_keys()
        cache_keys_b = brain._get_cache_keys()

        assert all("tenant-a" in key for key in cache_keys_a), \
            "Cache keys for tenant A must include tenant_id"
        assert all("tenant-b" in key for key in cache_keys_b), \
            "Cache keys for tenant B must include tenant_id"
```

### Mechanic-Specific Conformance Extensions

Mechanics can extend the base conformance suite:

```python
class AlignmentMechanicConformance(PipelineConformanceTests):
    """Additional tests specific to alignment mechanic."""

    async def test_checkpoint_enforcement(self, brain: AlignmentPipeline, ctx: TurnContext):
        """Alignment mechanic MUST enforce checkpoint steps before irreversible actions."""
        # ... mechanic-specific tests

    async def test_scenario_step_tracking(self, brain: AlignmentPipeline, ctx: TurnContext):
        """Alignment mechanic MUST track current scenario step."""
        # ... mechanic-specific tests


class ReactMechanicConformance(PipelineConformanceTests):
    """Additional tests specific to ReAct mechanic."""

    async def test_reasoning_trace_captured(self, brain: ReactPipeline, ctx: TurnContext):
        """ReAct mechanic MUST capture reasoning traces."""
        # ... mechanic-specific tests

    async def test_max_iterations_enforced(self, brain: ReactPipeline, ctx: TurnContext):
        """ReAct mechanic MUST enforce max reasoning iterations."""
        # ... mechanic-specific tests
```

### Running Conformance Tests

```bash
# Test a specific brain implementation
pytest tests/conformance/test_alignment_pipeline.py

# Test all registered brains
pytest tests/conformance/

# Generate conformance report
focal asa conformance-report --brain alignment --output report.json
```

---

## ASA Validator Components

The following components are **examples for the alignment mechanic**. Other mechanics would have different validators tailored to their concepts.

### 1. Tool Validator

Ensures all tools have proper side-effect declarations:

```python
class ToolValidator:
    """Validate tool definitions for safety and completeness."""

    def validate(self, tool: ToolDefinition) -> ValidationResult:
        """Validate a single tool definition."""
        issues = []
        suggestions = []

        # REQUIRED: Side-effect policy
        if not tool.side_effect_policy:
            issues.append(Issue(
                severity=Severity.ERROR,
                code="MISSING_SIDE_EFFECT_POLICY",
                message=f"Tool '{tool.name}' must declare side_effect_policy",
                fix="Add side_effect_policy field",
            ))

        # Check policy consistency with tool semantics
        policy_issues = self._check_policy_consistency(tool)
        issues.extend(policy_issues)

        # COMPENSATABLE must have compensation tool
        if tool.side_effect_policy == SideEffectPolicy.COMPENSATABLE:
            if not tool.compensation_tool:
                issues.append(Issue(
                    severity=Severity.ERROR,
                    code="MISSING_COMPENSATION",
                    message=f"COMPENSATABLE tool '{tool.name}' must specify compensation_tool",
                ))

        # IRREVERSIBLE should have confirmation
        if tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
            if not tool.confirmation_required:
                suggestions.append(Suggestion(
                    code="RECOMMEND_CONFIRMATION",
                    message=f"IRREVERSIBLE tool '{tool.name}' should require confirmation",
                    recommended_change={"confirmation_required": True},
                ))

        return ValidationResult(
            valid=len([i for i in issues if i.severity == Severity.ERROR]) == 0,
            issues=issues,
            suggestions=suggestions,
        )

    def _check_policy_consistency(self, tool: ToolDefinition) -> list[Issue]:
        """Check if declared policy matches tool semantics."""
        issues = []
        name = tool.name.lower()
        desc = (tool.description or "").lower()

        # Tools that should probably be IRREVERSIBLE
        irreversible_indicators = [
            "send", "email", "sms", "notify",
            "refund", "payment", "charge",
            "delete", "remove permanently",
            "submit", "finalize",
        ]

        if tool.side_effect_policy == SideEffectPolicy.PURE:
            for indicator in irreversible_indicators:
                if indicator in name or indicator in desc:
                    issues.append(Issue(
                        severity=Severity.WARNING,
                        code="POSSIBLE_POLICY_MISMATCH",
                        message=f"Tool '{tool.name}' marked PURE but contains '{indicator}' - verify this is correct",
                    ))

        # Tools that should probably be PURE
        pure_indicators = ["get", "fetch", "read", "list", "search", "validate", "check"]

        if tool.side_effect_policy in [SideEffectPolicy.COMPENSATABLE, SideEffectPolicy.IRREVERSIBLE]:
            for indicator in pure_indicators:
                if name.startswith(indicator):
                    issues.append(Issue(
                        severity=Severity.WARNING,
                        code="POSSIBLE_POLICY_MISMATCH",
                        message=f"Tool '{tool.name}' starts with '{indicator}' but marked {tool.side_effect_policy} - verify this is correct",
                    ))

        return issues
```

### 2. Scenario Validator

Validates scenario structure and safety:

```python
class ScenarioValidator:
    """Validate scenario definitions."""

    def validate(self, scenario: Scenario) -> ValidationResult:
        """Validate a scenario definition."""
        issues = []
        suggestions = []

        # Check for unreachable steps
        unreachable = self._find_unreachable_steps(scenario)
        for step in unreachable:
            issues.append(Issue(
                severity=Severity.WARNING,
                code="UNREACHABLE_STEP",
                message=f"Step '{step.name}' is not reachable from any other step",
            ))

        # Check for infinite loops
        loops = self._detect_loops(scenario)
        for loop in loops:
            issues.append(Issue(
                severity=Severity.WARNING,
                code="POTENTIAL_LOOP",
                message=f"Potential infinite loop: {' -> '.join(loop)}",
            ))

        # Check checkpoint placement
        checkpoint_issues = self._validate_checkpoints(scenario)
        issues.extend(checkpoint_issues)

        # Check tool bindings
        for step in scenario.steps:
            for binding in step.tool_bindings:
                tool_issues = self._validate_step_tool(step, binding)
                issues.extend(tool_issues)

        return ValidationResult(
            valid=len([i for i in issues if i.severity == Severity.ERROR]) == 0,
            issues=issues,
            suggestions=suggestions,
        )

    def _validate_checkpoints(self, scenario: Scenario) -> list[Issue]:
        """Validate checkpoint placement makes sense."""
        issues = []

        checkpoint_steps = [s for s in scenario.steps if s.is_checkpoint]

        if not checkpoint_steps:
            # No checkpoints - might be fine for simple scenarios
            has_irreversible = any(
                any(tb.tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE
                    for tb in step.tool_bindings)
                for step in scenario.steps
            )
            if has_irreversible:
                issues.append(Issue(
                    severity=Severity.WARNING,
                    code="MISSING_CHECKPOINT",
                    message="Scenario has IRREVERSIBLE tools but no checkpoint steps",
                ))

        return issues

    def _validate_step_tool(
        self,
        step: ScenarioStep,
        binding: ToolBinding,
    ) -> list[Issue]:
        """Validate tool binding on a step."""
        issues = []

        # IRREVERSIBLE tool on non-checkpoint step
        if binding.tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
            if not step.is_checkpoint:
                issues.append(Issue(
                    severity=Severity.WARNING,
                    code="IRREVERSIBLE_NO_CHECKPOINT",
                    message=f"Step '{step.name}' has IRREVERSIBLE tool but is_checkpoint=False",
                    fix="Set is_checkpoint=True on this step",
                ))

        return issues
```

### 3. Edge Case Generator

Suggests additional rules for edge cases:

```python
class EdgeCaseGenerator:
    """Generate edge-case rules and scenarios."""

    def generate_edge_cases(
        self,
        scenario: Scenario,
        tools: list[ToolDefinition],
    ) -> list[SuggestedRule]:
        """Generate edge-case rules for a scenario."""
        suggestions = []

        # For each IRREVERSIBLE tool, suggest cancellation handling
        for step in scenario.steps:
            for binding in step.tool_bindings:
                if binding.tool.side_effect_policy == SideEffectPolicy.IRREVERSIBLE:
                    suggestions.append(SuggestedRule(
                        name=f"handle_cancel_before_{step.name}",
                        description=f"Handle user cancellation before {binding.tool.name}",
                        trigger_condition="User says 'cancel', 'stop', 'wait', or 'nevermind'",
                        trigger_scope=f"Before reaching step '{step.name}'",
                        suggested_action="Confirm cancellation, don't proceed to irreversible action",
                        priority=100,  # High priority to catch cancellations
                    ))

        # For scenarios with data collection, suggest validation rules
        data_steps = [s for s in scenario.steps if self._is_data_collection_step(s)]
        for step in data_steps:
            suggestions.append(SuggestedRule(
                name=f"validate_{step.name}_input",
                description=f"Validate user input at step '{step.name}'",
                trigger_condition="User provides invalid or incomplete data",
                suggested_action="Re-prompt with specific guidance",
            ))

        # Suggest timeout handling
        if len(scenario.steps) > 3:
            suggestions.append(SuggestedRule(
                name=f"handle_{scenario.name}_timeout",
                description="Handle session timeout mid-scenario",
                trigger_condition="No user response for configured timeout period",
                suggested_action="Send reminder or gracefully close scenario",
            ))

        return suggestions

    def _is_data_collection_step(self, step: ScenarioStep) -> bool:
        """Check if step collects user data."""
        # Heuristic: step prompts user for specific information
        return any(
            keyword in (step.prompt or "").lower()
            for keyword in ["enter", "provide", "what is your", "please tell"]
        )


class SuggestedRule(BaseModel):
    """A suggested rule generated by edge case analysis."""
    name: str
    description: str
    trigger_condition: str
    trigger_scope: str | None = None
    suggested_action: str
    priority: int = 50
    auto_generated: bool = True
```

### 4. Policy Suggester

Suggests side-effect policies for new tools:

```python
class PolicySuggester:
    """Suggest side-effect policies for tools."""

    # Keyword mappings
    POLICY_KEYWORDS = {
        SideEffectPolicy.IRREVERSIBLE: [
            "send", "email", "sms", "notification",
            "refund", "payment", "charge", "bill",
            "delete", "remove", "cancel",
            "submit", "finalize", "complete",
            "transfer", "withdraw",
        ],
        SideEffectPolicy.COMPENSATABLE: [
            "add", "create", "reserve", "book",
            "update", "modify", "change",
            "enable", "disable",
        ],
        SideEffectPolicy.IDEMPOTENT: [
            "set", "assign", "configure",
            "sync", "refresh",
        ],
        SideEffectPolicy.PURE: [
            "get", "fetch", "read", "list",
            "search", "find", "lookup",
            "validate", "check", "verify",
            "calculate", "compute",
        ],
    }

    def suggest_policy(
        self,
        tool_name: str,
        description: str | None = None,
    ) -> PolicySuggestion:
        """Suggest appropriate policy for a tool."""

        name_lower = tool_name.lower()
        desc_lower = (description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Score each policy based on keyword matches
        scores = {policy: 0 for policy in SideEffectPolicy}

        for policy, keywords in self.POLICY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    scores[policy] += 1
                    # Extra weight for name matches
                    if keyword in name_lower:
                        scores[policy] += 2

        # Get best match
        best_policy = max(scores, key=scores.get)
        confidence = scores[best_policy] / (sum(scores.values()) + 1)

        # Default to PURE if no matches (conservative for reads)
        if scores[best_policy] == 0:
            best_policy = SideEffectPolicy.PURE
            confidence = 0.3

        return PolicySuggestion(
            suggested_policy=best_policy,
            confidence=confidence,
            reasoning=self._build_reasoning(tool_name, best_policy, scores),
            alternatives=[
                p for p in SideEffectPolicy
                if p != best_policy and scores[p] > 0
            ],
        )

    def _build_reasoning(
        self,
        tool_name: str,
        policy: SideEffectPolicy,
        scores: dict,
    ) -> str:
        """Build human-readable reasoning."""
        matched_keywords = [
            kw for kw in self.POLICY_KEYWORDS.get(policy, [])
            if kw in tool_name.lower()
        ]

        if matched_keywords:
            return f"Tool name contains '{', '.join(matched_keywords)}' suggesting {policy.value} behavior"
        return f"Default suggestion based on analysis (verify manually)"


class PolicySuggestion(BaseModel):
    suggested_policy: SideEffectPolicy
    confidence: float  # 0-1
    reasoning: str
    alternatives: list[SideEffectPolicy]
```

---

## Validation API

Expose validation as an API for UI/CI integration:

```python
@router.post("/validate/tool")
async def validate_tool(
    request: ValidateToolRequest,
    validator: ToolValidator = Depends(get_tool_validator),
) -> ValidationResult:
    """Validate a tool definition."""
    tool = ToolDefinition(**request.tool)
    return validator.validate(tool)


@router.post("/validate/scenario")
async def validate_scenario(
    request: ValidateScenarioRequest,
    validator: ScenarioValidator = Depends(get_scenario_validator),
) -> ValidationResult:
    """Validate a scenario definition."""
    scenario = Scenario(**request.scenario)
    return validator.validate(scenario)


@router.post("/suggest/policy")
async def suggest_policy(
    request: SuggestPolicyRequest,
    suggester: PolicySuggester = Depends(get_policy_suggester),
) -> PolicySuggestion:
    """Suggest side-effect policy for a tool."""
    return suggester.suggest_policy(
        tool_name=request.tool_name,
        description=request.description,
    )


@router.post("/generate/edge-cases")
async def generate_edge_cases(
    request: GenerateEdgeCasesRequest,
    generator: EdgeCaseGenerator = Depends(get_edge_case_generator),
) -> list[SuggestedRule]:
    """Generate edge-case rules for a scenario."""
    scenario = Scenario(**request.scenario)
    tools = [ToolDefinition(**t) for t in request.tools]
    return generator.generate_edge_cases(scenario, tools)
```

---

## CI Integration

Run validation in CI before deployment:

```python
# ci_validation.py

async def validate_deployment(
    config_path: Path,
) -> DeploymentValidationResult:
    """Validate all configurations before deployment."""

    # Load configurations
    tools = load_tools(config_path / "tools")
    scenarios = load_scenarios(config_path / "scenarios")
    rules = load_rules(config_path / "rules")

    all_issues = []
    all_suggestions = []

    # Validate tools
    tool_validator = ToolValidator()
    for tool in tools:
        result = tool_validator.validate(tool)
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)

    # Validate scenarios
    scenario_validator = ScenarioValidator()
    for scenario in scenarios:
        result = scenario_validator.validate(scenario)
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)

    # Check for missing edge cases
    edge_generator = EdgeCaseGenerator()
    for scenario in scenarios:
        suggested = edge_generator.generate_edge_cases(scenario, tools)
        # Check if suggested rules already exist
        for suggestion in suggested:
            if not rule_exists(suggestion.name, rules):
                all_suggestions.append(Suggestion(
                    code="MISSING_EDGE_CASE",
                    message=f"Consider adding rule: {suggestion.name}",
                    details=suggestion.model_dump(),
                ))

    # Determine if deployment should proceed
    errors = [i for i in all_issues if i.severity == Severity.ERROR]

    return DeploymentValidationResult(
        can_deploy=len(errors) == 0,
        errors=errors,
        warnings=[i for i in all_issues if i.severity == Severity.WARNING],
        suggestions=all_suggestions,
    )


# In CI brain:
# python -m soldier.asa.ci_validation --config-path ./config
# Exit code 1 if validation fails
```

---

## Wizard UI Integration

Provide validation feedback in configuration UI:

```typescript
// Frontend: Real-time validation as user configures tools

async function validateTool(toolConfig: ToolConfig): Promise<ValidationResult> {
  const response = await fetch('/api/validate/tool', {
    method: 'POST',
    body: JSON.stringify({ tool: toolConfig }),
  });
  return response.json();
}

// Show validation in UI
function ToolConfigForm({ tool, onSave }) {
  const [validation, setValidation] = useState(null);

  useEffect(() => {
    validateTool(tool).then(setValidation);
  }, [tool]);

  return (
    <form>
      {/* Tool fields */}

      {validation?.issues.map(issue => (
        <ValidationMessage
          key={issue.code}
          severity={issue.severity}
          message={issue.message}
          fix={issue.fix}
        />
      ))}

      {validation?.suggestions.map(suggestion => (
        <SuggestionMessage
          key={suggestion.code}
          message={suggestion.message}
          onApply={() => applyRecommendation(suggestion)}
        />
      ))}

      <button
        disabled={!validation?.valid}
        onClick={onSave}
      >
        Save Tool
      </button>
    </form>
  );
}
```

---

## Configuration

```toml
[asa]
# Enable/disable ASA validation
enabled = true

# Validation strictness
[asa.validation]
require_side_effect_policy = true
warn_on_policy_mismatch = true
suggest_edge_cases = true

# CI integration
[asa.ci]
fail_on_errors = true
fail_on_warnings = false
generate_report = true
```

---

## ASA as Brain Configurator

ASA can configure **any Brain implementation**, not just alignment-based ones.

### Configuration Abstraction

Every mechanic exposes its configuration schema:

```python
class Brain(ABC):
    """Base interface for all cognitive mechanics."""

    @classmethod
    @abstractmethod
    def get_config_schema(cls) -> ConfigSchema:
        """Return configuration schema for this mechanic.

        ASA uses this to understand what can be configured.
        """
        pass

    @abstractmethod
    async def validate_config(self, config: dict) -> ValidationResult:
        """Validate a configuration for this mechanic.

        ASA calls this to check if configuration is valid.
        """
        pass

    @abstractmethod
    async def process_turn(self, ctx: TurnContext) -> BrainResult:
        """Execute one turn of conversation."""
        pass
```

### Mechanic-Specific Configuration Examples

**Alignment Mechanic:**
```python
class AlignmentPipeline(Brain):
    @classmethod
    def get_config_schema(cls) -> ConfigSchema:
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(name="scenario", type="graph", required=True),
                ArtifactSchema(name="rules", type="list", required=False),
                ArtifactSchema(name="templates", type="dict", required=False),
            ],
            parameters=[
                ParameterSchema(name="checkpoint_mode", type="enum", values=["strict", "warn"]),
                ParameterSchema(name="rule_priority_threshold", type="int", min=0, max=100),
            ],
        )
```

**ReAct Mechanic:**
```python
class ReactPipeline(Brain):
    @classmethod
    def get_config_schema(cls) -> ConfigSchema:
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(name="system_prompt", type="string", required=True),
                ArtifactSchema(name="reasoning_examples", type="list", required=False),
            ],
            parameters=[
                ParameterSchema(name="max_iterations", type="int", min=1, max=20),
                ParameterSchema(name="temperature", type="float", min=0.0, max=2.0),
                ParameterSchema(name="allow_parallel_tools", type="bool"),
            ],
        )
```

**Planner-Executor Mechanic:**
```python
class PlannerExecutorPipeline(Brain):
    @classmethod
    def get_config_schema(cls) -> ConfigSchema:
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(name="plan_templates", type="list", required=True),
                ArtifactSchema(name="execution_policies", type="dict", required=True),
            ],
            parameters=[
                ParameterSchema(name="replan_on_failure", type="bool"),
                ParameterSchema(name="max_plan_depth", type="int", min=1, max=10),
                ParameterSchema(name="rollback_strategy", type="enum", values=["full", "partial", "none"]),
            ],
        )
```

### ASA Configuration Workflow

```python
# 1. ASA discovers available mechanics
mechanics = await asa.discover_mechanics()
# Returns: ["alignment", "react", "planner-executor", "custom-qa-bot"]

# 2. User selects mechanic for their agent
selected_mechanic = "react"

# 3. ASA loads mechanic's config schema
schema = await asa.get_mechanic_schema(selected_mechanic)

# 4. ASA generates configuration wizard UI
wizard = asa.generate_wizard(schema)

# 5. User fills configuration through wizard
config = {
    "system_prompt": "You are a helpful customer service agent...",
    "max_iterations": 5,
    "temperature": 0.7,
    "tools": ["search_orders", "create_ticket", "send_email"],
}

# 6. ASA validates configuration
validation = await asa.validate_configuration(selected_mechanic, config)

# 7. ASA runs conformance tests
conformance = await asa.run_conformance_tests(selected_mechanic, config)

# 8. If valid, configuration is deployed
if validation.valid and conformance.passed:
    await deploy_agent_config(agent_id, selected_mechanic, config)
```

### Plugin System for Custom Mechanics

ASA supports custom mechanics via plugins:

```python
# Custom mechanic registration
class CustomQAMechanic(Brain):
    """Custom Q&A mechanic with RAG."""

    @classmethod
    def get_config_schema(cls) -> ConfigSchema:
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(name="knowledge_base", type="vector_store", required=True),
                ArtifactSchema(name="answer_templates", type="dict", required=False),
            ],
            parameters=[
                ParameterSchema(name="retrieval_k", type="int", min=1, max=20),
                ParameterSchema(name="confidence_threshold", type="float", min=0.0, max=1.0),
            ],
        )

    async def validate_config(self, config: dict) -> ValidationResult:
        # Custom validation logic
        issues = []
        if config.get("confidence_threshold", 0) < 0.5:
            issues.append(Issue(
                severity=Severity.WARNING,
                message="Low confidence threshold may produce unreliable answers",
            ))
        return ValidationResult(valid=True, issues=issues)

# Register with ASA
asa.register_mechanic("custom-qa-bot", CustomQAMechanic)
```

---

## Related Topics

- [04-side-effect-policy.md](04-side-effect-policy.md) - Side-effect policy validation (for mechanics that use tools)
- [08-config-hierarchy.md](08-config-hierarchy.md) - How configurations are organized
- [12-cognitive-brain-interface.md](12-cognitive-brain-interface.md) - Base interface ASA validates against
