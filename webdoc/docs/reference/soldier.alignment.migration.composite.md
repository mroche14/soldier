<a id="focal.alignment.migration.composite"></a>

# focal.alignment.migration.composite

Composite migration for multi-version gaps.

Handles scenarios where customers missed multiple versions (e.g., V1→V5).
Computes net effect across plan chain to avoid asking for obsolete data.

<a id="focal.alignment.migration.composite.CompositeMapper"></a>

## CompositeMapper Objects

```python
class CompositeMapper()
```

Map multi-version migrations to a single composite migration.

When a customer skipped multiple versions (V1→V5), this class:
1. Loads the chain of migration plans (V1→V2, V2→V3, V3→V4, V4→V5)
2. Accumulates all data collection requirements
3. Prunes requirements to only those needed in final version
4. Executes a single composite migration

<a id="focal.alignment.migration.composite.CompositeMapper.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: "ConfigStore") -> None
```

Initialize the composite mapper.

**Arguments**:

- `config_store` - Store for migration plans

<a id="focal.alignment.migration.composite.CompositeMapper.get_plan_chain"></a>

#### get\_plan\_chain

```python
async def get_plan_chain(tenant_id: UUID, scenario_id: UUID,
                         start_version: int,
                         end_version: int) -> list[MigrationPlan]
```

Load the chain of migration plans between versions.

**Arguments**:

- `tenant_id` - Tenant ID
- `scenario_id` - Scenario ID
- `start_version` - Customer's current version
- `end_version` - Target version
  

**Returns**:

  List of MigrationPlans in order (V1→V2, V2→V3, etc.)

<a id="focal.alignment.migration.composite.CompositeMapper.accumulate_requirements"></a>

#### accumulate\_requirements

```python
def accumulate_requirements(plan_chain: list[MigrationPlan],
                            anchor_hash: str) -> set[str]
```

Accumulate all data collection requirements across plan chain.

**Arguments**:

- `plan_chain` - Chain of migration plans
- `anchor_hash` - Content hash of customer's current anchor
  

**Returns**:

  Set of all field names collected across chain

<a id="focal.alignment.migration.composite.CompositeMapper.prune_requirements"></a>

#### prune\_requirements

```python
def prune_requirements(accumulated_fields: set[str], final_plan: MigrationPlan,
                       anchor_hash: str) -> set[str]
```

Prune requirements to only those needed in final version.

Removes fields that were needed in intermediate versions but
were later removed from the flow.

**Arguments**:

- `accumulated_fields` - All fields collected across chain
- `final_plan` - The final migration plan (to target version)
- `anchor_hash` - Content hash of anchor
  

**Returns**:

  Set of fields actually needed in final version

<a id="focal.alignment.migration.composite.CompositeMapper.execute_composite_migration"></a>

#### execute\_composite\_migration

```python
async def execute_composite_migration(
        session: "Session", plan_chain: list[MigrationPlan],
        _final_scenario: "Scenario", anchor_hash: str) -> ReconciliationResult
```

Execute a composite migration across multiple versions.

Instead of applying V1→V2→V3→V4 migrations sequentially,
we compute the net effect and apply it in one step.

**Arguments**:

- `session` - Current session
- `plan_chain` - Chain of migration plans
- `final_scenario` - Final scenario version
- `anchor_hash` - Content hash of customer's current anchor
  

**Returns**:

  ReconciliationResult with composite migration outcome

<a id="focal.alignment.migration.composite.CompositeMapper.build_composite_transformation"></a>

#### build\_composite\_transformation

```python
async def build_composite_transformation(
        plan_chain: list[MigrationPlan],
        anchor_hash: str) -> AnchorTransformation | None
```

Build a synthetic transformation representing net effect.

Useful for representing the composite migration in a single
transformation object.

**Arguments**:

- `plan_chain` - Chain of migration plans
- `anchor_hash` - Content hash of anchor
  

**Returns**:

  Synthetic AnchorTransformation or None

