<a id="soldier.api.routes.variables"></a>

# soldier.api.routes.variables

Variable management endpoints.

<a id="soldier.api.routes.variables.list_variables"></a>

#### list\_variables

```python
@router.get("", response_model=PaginatedResponse[VariableResponse])
async def list_variables(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["name", "created_at",
                     "updated_at"] = Query(default="name"),
    sort_order: Literal["asc", "desc"] = Query(default="asc")
) -> PaginatedResponse[VariableResponse]
```

List variables for an agent.

<a id="soldier.api.routes.variables.create_variable"></a>

#### create\_variable

```python
@router.post("", response_model=VariableResponse, status_code=201)
async def create_variable(agent_id: UUID, request: VariableCreate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> VariableResponse
```

Create a new variable.

<a id="soldier.api.routes.variables.get_variable"></a>

#### get\_variable

```python
@router.get("/{variable_id}", response_model=VariableResponse)
async def get_variable(agent_id: UUID, variable_id: UUID,
                       tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> VariableResponse
```

Get a variable by ID.

<a id="soldier.api.routes.variables.update_variable"></a>

#### update\_variable

```python
@router.put("/{variable_id}", response_model=VariableResponse)
async def update_variable(agent_id: UUID, variable_id: UUID,
                          request: VariableUpdate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> VariableResponse
```

Update a variable.

<a id="soldier.api.routes.variables.delete_variable"></a>

#### delete\_variable

```python
@router.delete("/{variable_id}", status_code=204)
async def delete_variable(agent_id: UUID, variable_id: UUID,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> None
```

Delete a variable (soft delete).

