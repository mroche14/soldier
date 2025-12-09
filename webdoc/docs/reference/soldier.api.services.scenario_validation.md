<a id="focal.api.services.scenario_validation"></a>

# focal.api.services.scenario\_validation

Scenario validation service.

<a id="focal.api.services.scenario_validation.detect_unreachable_steps"></a>

#### detect\_unreachable\_steps

```python
def detect_unreachable_steps(scenario: Scenario) -> list[UUID]
```

Detect steps that cannot be reached from the entry point.

Uses BFS from entry step to find all reachable steps,
then returns any steps that weren't visited.

**Arguments**:

- `scenario` - Scenario to analyze
  

**Returns**:

  List of unreachable step IDs

<a id="focal.api.services.scenario_validation.validate_scenario_graph"></a>

#### validate\_scenario\_graph

```python
def validate_scenario_graph(scenario: Scenario) -> list[str]
```

Validate scenario graph structure.

Checks for:
- Entry step exists in steps list
- All transition targets exist
- No orphaned steps (unreachable from entry)
- At least one terminal step

**Arguments**:

- `scenario` - Scenario to validate
  

**Returns**:

  List of validation error messages (empty if valid)

