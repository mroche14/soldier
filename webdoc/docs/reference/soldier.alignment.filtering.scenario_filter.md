<a id="focal.alignment.filtering.scenario_filter"></a>

# focal.alignment.filtering.scenario\_filter

Scenario filtering and navigation decisions.

<a id="focal.alignment.filtering.scenario_filter.ScenarioFilter"></a>

## ScenarioFilter Objects

```python
class ScenarioFilter()
```

Determine scenario navigation actions for a turn.

Handles scenario lifecycle including:
- Starting new scenarios when entry conditions match
- Continuing within active scenarios
- Detecting and handling loops via relocalization
- Exiting scenarios when requested

<a id="focal.alignment.filtering.scenario_filter.ScenarioFilter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore, max_loop_count: int = 3) -> None
```

Initialize the scenario filter.

**Arguments**:

- `config_store` - Store for scenario definitions
- `max_loop_count` - Maximum visits to a step before triggering relocalization

<a id="focal.alignment.filtering.scenario_filter.ScenarioFilter.evaluate"></a>

#### evaluate

```python
async def evaluate(
        tenant_id: UUID,
        context: Context,
        *,
        candidates: list[ScoredScenario],
        active_scenario_id: UUID | None = None,
        current_step_id: UUID | None = None,
        visited_steps: dict[UUID, int] | None = None) -> ScenarioFilterResult
```

Evaluate scenario navigation for the current turn.

**Arguments**:

- `tenant_id` - Tenant identifier
- `context` - Extracted context from user message
- `candidates` - Candidate scenarios from retrieval
- `active_scenario_id` - Currently active scenario (if any)
- `current_step_id` - Current step within active scenario
- `visited_steps` - Map of step_id -> visit count for loop detection
  

**Returns**:

  ScenarioFilterResult with navigation action and target

