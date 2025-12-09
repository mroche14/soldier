<a id="focal.alignment.migration.executor"></a>

# focal.alignment.migration.executor

Migration executor for JIT session migration.

Applies migration scenarios (clean graft, gap fill, re-route) when
customers return after a scenario version change.

<a id="focal.alignment.migration.executor.MigrationExecutor"></a>

## MigrationExecutor Objects

```python
class MigrationExecutor()
```

Execute JIT migrations for sessions with pending migrations.

Handles three migration scenarios:
- Clean Graft: Silent teleport to equivalent V2 step
- Gap Fill: Collect missing data before teleport
- Re-Route: Evaluate upstream fork and potentially block at checkpoint

<a id="focal.alignment.migration.executor.MigrationExecutor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: "ConfigStore",
             session_store: "SessionStore",
             config: ScenarioMigrationConfig | None = None,
             profile_store: "ProfileStore | None" = None,
             llm_provider: "LLMProvider | None" = None) -> None
```

Initialize the migration executor.

**Arguments**:

- `config_store` - Store for scenarios and migration plans
- `session_store` - Store for sessions
- `config` - Migration configuration
- `profile_store` - Optional profile store for gap fill
- `llm_provider` - Optional LLM for conversation extraction

<a id="focal.alignment.migration.executor.MigrationExecutor.reconcile"></a>

#### reconcile

```python
async def reconcile(session: Session,
                    current_scenario: "Scenario") -> ReconciliationResult
```

Perform pre-turn reconciliation for a session.

Checks for pending migrations or version mismatches and applies
the appropriate migration scenario.

**Arguments**:

- `session` - Current session
- `current_scenario` - Current version of the scenario
  

**Returns**:

  ReconciliationResult indicating what action to take

