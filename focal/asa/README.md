# ASA: Agent Setter Agent

**ASA (Agent Setter Agent)** is a mechanic-agnostic meta-agent for design-time validation and configuration assistance for ANY CognitivePipeline implementation.

## Overview

ASA helps design, validate, and configure cognitive mechanics through:

1. **Universal Conformance Testing** - Every CognitivePipeline must pass ASA's conformance suite
2. **Mechanic Discovery** - ASA can discover and work with any registered cognitive mechanic
3. **Schema-Driven Configuration** - Mechanics expose their config schema; ASA generates wizards
4. **Safety Validation** - Mechanic-specific validators ensure safety properties
5. **Plugin Architecture** - Custom mechanics can register with ASA for full support

## Core Principle: Mechanic-Agnostic Design

ASA validates and configures ANY cognitive mechanic:

| Mechanic | ASA Helps Design | ASA Validates |
|----------|------------------|---------------|
| **Alignment (FOCAL)** | Scenarios, rules, templates | Checkpoint placement, rule conflicts |
| **ReAct** | Prompts, reasoning chains | Tool safety, loop detection |
| **Planner-Executor** | Plan templates, policies | Plan feasibility, rollback coverage |
| **Custom** | Whatever the mechanic needs | Mechanic-specific constraints |

## Module Structure

```
focal/asa/
├── models.py                    # Data models (ValidationResult, Issue, etc.)
├── validator/
│   ├── tool_validator.py        # ToolValidator class
│   ├── scenario_validator.py    # ScenarioValidator class
│   └── pipeline_conformance.py  # PipelineConformanceTests
├── suggester/
│   ├── policy_suggester.py      # PolicySuggester (side-effect policy)
│   └── edge_case_generator.py   # EdgeCaseGenerator
├── wizard/
│   └── schema_generator.py      # ConfigSchema generation
└── ci/
    └── validation.py            # CI integration (validate_deployment)
```

## Usage Examples

### 1. Tool Validation

```python
from focal.asa import ToolValidator

validator = ToolValidator()

tool = {
    "name": "send_email",
    "description": "Sends an email to a customer",
    "side_effect_policy": "irreversible",
    "confirmation_required": True,
}

result = validator.validate(tool)
if not result.valid:
    for issue in result.errors:
        print(f"ERROR: {issue.message}")
```

### 2. Policy Suggestion

```python
from focal.asa import PolicySuggester

suggester = PolicySuggester()

suggestion = suggester.suggest_policy(
    tool_name="send_refund",
    description="Processes and sends a refund to customer"
)

print(f"Suggested policy: {suggestion.suggested_policy}")
print(f"Confidence: {suggestion.confidence:.2f}")
print(f"Reasoning: {suggestion.reasoning}")
```

### 3. Scenario Validation

```python
from focal.asa import ScenarioValidator

validator = ScenarioValidator()

scenario = {
    "name": "customer_support",
    "steps": [
        {
            "name": "greeting",
            "transitions": [{"target_step": "collect_info"}],
        },
        # ... more steps
    ],
}

result = validator.validate(scenario)
for issue in result.issues:
    print(f"[{issue.severity}] {issue.message}")
```

### 4. Edge Case Generation

```python
from focal.asa import EdgeCaseGenerator

generator = EdgeCaseGenerator()

suggestions = generator.generate_edge_cases(scenario, tools)
for suggestion in suggestions:
    print(f"Rule: {suggestion.name}")
    print(f"Action: {suggestion.suggested_action}")
```

### 5. Pipeline Conformance Testing

```python
from focal.asa import PipelineConformanceTests

class MyPipelineConformance(PipelineConformanceTests):
    def get_pipeline(self):
        return MyCustomPipeline()

# Run conformance tests
conformance = MyPipelineConformance()
result = await conformance.test_tools_go_through_toolbox(ctx)
assert result.valid
```

### 6. Schema Generation for Wizard UIs

```python
from focal.asa import SchemaGenerator

generator = SchemaGenerator()

# Generate schema for alignment mechanic
schema = generator.generate_alignment_schema()

# Generate schema for ReAct mechanic
schema = generator.generate_react_schema()

# Validate config against schema
is_valid, errors = generator.validate_config_against_schema(config, schema)
```

### 7. CI Integration

```python
from pathlib import Path
from focal.asa.ci import validate_deployment

# Validate all configurations before deployment
result = await validate_deployment(Path("./config"))

if not result.can_deploy:
    print("Deployment blocked:")
    for error in result.errors:
        print(f"  - {error.message}")
    exit(1)
```

## Pipeline Conformance Requirements

Every CognitivePipeline implementation MUST pass these tests:

- ✅ `test_tools_go_through_toolbox` - All tool calls via Toolbox
- ✅ `test_required_events_are_emitted` - Emit turn.started, turn.completed
- ✅ `test_supersede_checked_before_irreversible` - Check supersede before irreversible actions
- ✅ `test_pipelineresult_contract` - Return well-formed PipelineResult
- ✅ `test_timeout_handling` - Respect timeout configuration
- ✅ `test_tenant_isolation` - No data leakage across tenants

## Models

### ValidationResult
```python
class ValidationResult(BaseModel):
    valid: bool
    issues: list[Issue]
    suggestions: list[Suggestion]
```

### Issue
```python
class Issue(BaseModel):
    severity: Severity  # ERROR, WARNING, INFO
    code: str
    message: str
    fix: str | None
    location: str | None
```

### PolicySuggestion
```python
class PolicySuggestion(BaseModel):
    suggested_policy: SideEffectPolicy
    confidence: float  # 0-1
    reasoning: str
    alternatives: list[SideEffectPolicy]
```

### SuggestedRule
```python
class SuggestedRule(BaseModel):
    name: str
    description: str
    trigger_condition: str
    trigger_scope: str | None
    suggested_action: str
    priority: int
    auto_generated: bool
```

## Configuration

```toml
[asa]
enabled = true

[asa.validation]
require_side_effect_policy = true
warn_on_policy_mismatch = true
suggest_edge_cases = true

[asa.ci]
fail_on_errors = true
fail_on_warnings = false
generate_report = true
```

## Design Philosophy

ASA is a **design-time assistant**, not a runtime agent. It:

- ✅ Validates configurations before deployment
- ✅ Suggests improvements based on best practices
- ✅ Generates edge-case handling
- ✅ Enforces mechanic-agnostic conformance requirements
- ✅ Runs conformance tests against any CognitivePipeline

ASA does NOT:

- ❌ Autonomously modify production configurations
- ❌ Make changes without human approval
- ❌ Run in production environments
- ❌ Have direct write access to configuration stores

## Related Documentation

- [13-asa-validator.md](../../docs/focal_360/architecture/topics/13-asa-validator.md) - Full ASA specification
- [12-cognitive-pipeline-interface.md](../../docs/focal_360/architecture/topics/12-cognitive-pipeline-interface.md) - Pipeline interface ASA validates
- [04-side-effect-policy.md](../../docs/focal_360/architecture/topics/04-side-effect-policy.md) - Side-effect policy system
