<a id="focal.alignment.migration.planner"></a>

# focal.alignment.migration.planner

Migration planner and deployer for scenario version transitions.

Implements MigrationPlanner for plan generation and MigrationDeployer
for session marking during deployment.

<a id="focal.alignment.migration.planner.MigrationPlanner"></a>

## MigrationPlanner Objects

```python
class MigrationPlanner()
```

Generates migration plans for scenario version transitions.

<a id="focal.alignment.migration.planner.MigrationPlanner.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: "ConfigStore",
             session_store: "SessionStore",
             config: ScenarioMigrationConfig | None = None) -> None
```

Initialize planner.

**Arguments**:

- `config_store` - Store for scenarios and migration plans
- `session_store` - Store for session queries (affected count)
- `config` - Migration configuration

<a id="focal.alignment.migration.planner.MigrationPlanner.generate_plan"></a>

#### generate\_plan

```python
async def generate_plan(tenant_id: UUID,
                        scenario_id: UUID,
                        new_scenario: "Scenario",
                        created_by: str | None = None) -> MigrationPlan
```

Generate a migration plan for a scenario update.

**Arguments**:

- `tenant_id` - Tenant identifier
- `scenario_id` - Scenario being updated
- `new_scenario` - New scenario version
- `created_by` - Operator creating the plan
  

**Returns**:

  Generated MigrationPlan
  

**Raises**:

- `ValueError` - If current scenario not found or versions invalid

<a id="focal.alignment.migration.planner.MigrationPlanner.approve_plan"></a>

#### approve\_plan

```python
async def approve_plan(tenant_id: UUID,
                       plan_id: UUID,
                       approved_by: str | None = None) -> MigrationPlan
```

Approve a migration plan for deployment.

**Arguments**:

- `tenant_id` - Tenant identifier
- `plan_id` - Plan to approve
- `approved_by` - Approver identifier
  

**Returns**:

  Updated plan
  

**Raises**:

- `ValueError` - If plan not found or not in PENDING status

<a id="focal.alignment.migration.planner.MigrationPlanner.reject_plan"></a>

#### reject\_plan

```python
async def reject_plan(tenant_id: UUID,
                      plan_id: UUID,
                      rejected_by: str | None = None,
                      reason: str | None = None) -> MigrationPlan
```

Reject a migration plan.

**Arguments**:

- `tenant_id` - Tenant identifier
- `plan_id` - Plan to reject
- `rejected_by` - Rejector identifier
- `reason` - Rejection reason
  

**Returns**:

  Updated plan
  

**Raises**:

- `ValueError` - If plan not found or not in PENDING status

<a id="focal.alignment.migration.planner.MigrationPlanner.update_policies"></a>

#### update\_policies

```python
async def update_policies(
        tenant_id: UUID, plan_id: UUID,
        policies: dict[str, AnchorMigrationPolicy]) -> MigrationPlan
```

Update per-anchor policies for a migration plan.

**Arguments**:

- `tenant_id` - Tenant identifier
- `plan_id` - Plan to update
- `policies` - New policies by anchor hash
  

**Returns**:

  Updated plan
  

**Raises**:

- `ValueError` - If plan not found or not in PENDING status

<a id="focal.alignment.migration.planner.MigrationDeployer"></a>

## MigrationDeployer Objects

```python
class MigrationDeployer()
```

Deploys migration plans by marking eligible sessions.

<a id="focal.alignment.migration.planner.MigrationDeployer.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: "ConfigStore",
             session_store: "SessionStore",
             config: ScenarioMigrationConfig | None = None) -> None
```

Initialize deployer.

**Arguments**:

- `config_store` - Store for migration plans
- `session_store` - Store for session marking
- `config` - Migration configuration

<a id="focal.alignment.migration.planner.MigrationDeployer.deploy"></a>

#### deploy

```python
async def deploy(tenant_id: UUID, plan_id: UUID) -> dict[str, Any]
```

Deploy a migration plan by marking eligible sessions.

Phase 1 of two-phase deployment: marks sessions with pending_migration.
Actual migration happens at JIT when customer returns.

**Arguments**:

- `tenant_id` - Tenant identifier
- `plan_id` - Plan to deploy
  

**Returns**:

  Deployment result with counts
  

**Raises**:

- `ValueError` - If plan not found or not in APPROVED status

<a id="focal.alignment.migration.planner.MigrationDeployer.get_deployment_status"></a>

#### get\_deployment\_status

```python
async def get_deployment_status(tenant_id: UUID,
                                plan_id: UUID) -> dict[str, Any]
```

Get deployment status for a migration plan.

**Arguments**:

- `tenant_id` - Tenant identifier
- `plan_id` - Plan to check
  

**Returns**:

  Status dict with counts
  

**Raises**:

- `ValueError` - If plan not found

<a id="focal.alignment.migration.planner.MigrationDeployer.cleanup_old_plans"></a>

#### cleanup\_old\_plans

```python
async def cleanup_old_plans(tenant_id: UUID, retention_days: int = 30) -> int
```

Clean up old migration plans.

Removes migration plans that have been deployed for longer
than the retention period.

**Arguments**:

- `tenant_id` - Tenant to clean up
- `retention_days` - Days to retain deployed plans (default 30)
  

**Returns**:

  Number of plans deleted

