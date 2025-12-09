<a id="focal.api.routes.migrations"></a>

# focal.api.routes.migrations

Migration API routes.

Provides endpoints for managing scenario migrations:
- Generate migration plans
- Review and configure policies
- Approve/reject plans
- Deploy migrations
- Monitor deployment status

<a id="focal.api.routes.migrations.TransitionInput"></a>

## TransitionInput Objects

```python
class TransitionInput(BaseModel)
```

Input for a step transition.

<a id="focal.api.routes.migrations.ScenarioStepInput"></a>

## ScenarioStepInput Objects

```python
class ScenarioStepInput(BaseModel)
```

Input for a scenario step.

<a id="focal.api.routes.migrations.ScenarioInput"></a>

## ScenarioInput Objects

```python
class ScenarioInput(BaseModel)
```

Input for a new scenario version.

<a id="focal.api.routes.migrations.GenerateMigrationPlanRequest"></a>

## GenerateMigrationPlanRequest Objects

```python
class GenerateMigrationPlanRequest(BaseModel)
```

Request to generate a migration plan.

<a id="focal.api.routes.migrations.ApprovePlanRequest"></a>

## ApprovePlanRequest Objects

```python
class ApprovePlanRequest(BaseModel)
```

Request to approve a plan.

<a id="focal.api.routes.migrations.RejectPlanRequest"></a>

## RejectPlanRequest Objects

```python
class RejectPlanRequest(BaseModel)
```

Request to reject a plan.

<a id="focal.api.routes.migrations.UpdatePoliciesRequest"></a>

## UpdatePoliciesRequest Objects

```python
class UpdatePoliciesRequest(BaseModel)
```

Request to update anchor policies.

<a id="focal.api.routes.migrations.MigrationPlanSummaryItem"></a>

## MigrationPlanSummaryItem Objects

```python
class MigrationPlanSummaryItem(BaseModel)
```

Summary item for list view.

<a id="focal.api.routes.migrations.DeploymentResult"></a>

## DeploymentResult Objects

```python
class DeploymentResult(BaseModel)
```

Result of deployment operation.

<a id="focal.api.routes.migrations.DeploymentStatus"></a>

## DeploymentStatus Objects

```python
class DeploymentStatus(BaseModel)
```

Current deployment status.

<a id="focal.api.routes.migrations.generate_migration_plan"></a>

#### generate\_migration\_plan

```python
@router.post(
    "/scenarios/{scenario_id}/migration-plan",
    response_model=MigrationPlan,
    status_code=status.HTTP_201_CREATED,
)
async def generate_migration_plan(
    scenario_id: UUID,
    request: GenerateMigrationPlanRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> MigrationPlan
```

Generate a migration plan for a scenario update.

Computes the graph diff, identifies anchors, and determines
migration scenarios (Clean Graft, Gap Fill, Re-Route) for each anchor.

<a id="focal.api.routes.migrations.list_migration_plans"></a>

#### list\_migration\_plans

```python
@router.get("/migration-plans", response_model=dict)
async def list_migration_plans(
    scenario_id: UUID | None = None,
    plan_status: MigrationPlanStatus | None = None,
    limit: int = 50,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store)
) -> dict[str, Any]
```

List migration plans for a tenant.

<a id="focal.api.routes.migrations.get_migration_plan"></a>

#### get\_migration\_plan

```python
@router.get("/migration-plans/{plan_id}", response_model=MigrationPlan)
async def get_migration_plan(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store)
) -> MigrationPlan
```

Get full details of a migration plan.

<a id="focal.api.routes.migrations.get_migration_summary"></a>

#### get\_migration\_summary

```python
@router.get("/migration-plans/{plan_id}/summary",
            response_model=MigrationSummary)
async def get_migration_summary(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store)
) -> MigrationSummary
```

Get operator-friendly summary of a migration plan.

<a id="focal.api.routes.migrations.update_anchor_policies"></a>

#### update\_anchor\_policies

```python
@router.put("/migration-plans/{plan_id}/policies",
            response_model=MigrationPlan)
async def update_anchor_policies(
    plan_id: UUID,
    request: UpdatePoliciesRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> MigrationPlan
```

Update per-anchor migration policies.

<a id="focal.api.routes.migrations.approve_migration_plan"></a>

#### approve\_migration\_plan

```python
@router.post("/migration-plans/{plan_id}/approve",
             response_model=MigrationPlan)
async def approve_migration_plan(
    plan_id: UUID,
    request: ApprovePlanRequest | None = None,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> MigrationPlan
```

Approve a migration plan for deployment.

<a id="focal.api.routes.migrations.reject_migration_plan"></a>

#### reject\_migration\_plan

```python
@router.post("/migration-plans/{plan_id}/reject", response_model=MigrationPlan)
async def reject_migration_plan(
    plan_id: UUID,
    request: RejectPlanRequest | None = None,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> MigrationPlan
```

Reject a migration plan.

<a id="focal.api.routes.migrations.deploy_migration_plan"></a>

#### deploy\_migration\_plan

```python
@router.post("/migration-plans/{plan_id}/deploy",
             response_model=DeploymentResult)
async def deploy_migration_plan(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> DeploymentResult
```

Deploy an approved migration plan.

Marks eligible sessions with pending_migration flag.
Migrations are applied JIT at next customer message.

<a id="focal.api.routes.migrations.get_deployment_status"></a>

#### get\_deployment\_status

```python
@router.get(
    "/migration-plans/{plan_id}/deployment-status",
    response_model=DeploymentStatus,
)
async def get_deployment_status(
    plan_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    config_store: ConfigStore = Depends(get_config_store),
    session_store: SessionStore = Depends(get_session_store)
) -> DeploymentStatus
```

Get current deployment status.

