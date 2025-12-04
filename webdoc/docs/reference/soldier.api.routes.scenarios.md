<a id="soldier.api.routes.scenarios"></a>

# soldier.api.routes.scenarios

Scenario management endpoints.

<a id="soldier.api.routes.scenarios.list_scenarios"></a>

#### list\_scenarios

```python
@router.get("", response_model=PaginatedResponse[ScenarioResponse])
async def list_scenarios(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tag: str | None = Query(default=None, description="Filter by tag"),
    enabled: bool | None = Query(default=None),
    sort_by: Literal["name", "created_at",
                     "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc")
) -> PaginatedResponse[ScenarioResponse]
```

List scenarios for an agent.

<a id="soldier.api.routes.scenarios.create_scenario"></a>

#### create\_scenario

```python
@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_scenario(agent_id: UUID, request: ScenarioCreate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> ScenarioResponse
```

Create a new scenario with steps.

<a id="soldier.api.routes.scenarios.get_scenario"></a>

#### get\_scenario

```python
@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(agent_id: UUID, scenario_id: UUID,
                       tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> ScenarioResponse
```

Get a scenario by ID.

<a id="soldier.api.routes.scenarios.update_scenario"></a>

#### update\_scenario

```python
@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(agent_id: UUID, scenario_id: UUID,
                          request: ScenarioUpdate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> ScenarioResponse
```

Update a scenario.

<a id="soldier.api.routes.scenarios.delete_scenario"></a>

#### delete\_scenario

```python
@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(agent_id: UUID, scenario_id: UUID,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> None
```

Delete a scenario (soft delete).

<a id="soldier.api.routes.scenarios.add_step"></a>

#### add\_step

```python
@router.post("/{scenario_id}/steps",
             response_model=StepResponse,
             status_code=201)
async def add_step(agent_id: UUID, scenario_id: UUID, request: StepCreate,
                   tenant_context: TenantContextDep,
                   config_store: ConfigStoreDep) -> StepResponse
```

Add a step to a scenario.

<a id="soldier.api.routes.scenarios.update_step"></a>

#### update\_step

```python
@router.put("/{scenario_id}/steps/{step_id}", response_model=StepResponse)
async def update_step(agent_id: UUID, scenario_id: UUID, step_id: UUID,
                      request: StepUpdate, tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep) -> StepResponse
```

Update a scenario step.

<a id="soldier.api.routes.scenarios.delete_step"></a>

#### delete\_step

```python
@router.delete("/{scenario_id}/steps/{step_id}", status_code=204)
async def delete_step(agent_id: UUID, scenario_id: UUID, step_id: UUID,
                      tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep) -> None
```

Delete a scenario step.

Cannot delete the entry step.

