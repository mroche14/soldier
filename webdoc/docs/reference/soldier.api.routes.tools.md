<a id="soldier.api.routes.tools"></a>

# soldier.api.routes.tools

Tool activation management endpoints.

<a id="soldier.api.routes.tools.list_tool_activations"></a>

#### list\_tool\_activations

```python
@router.get("", response_model=PaginatedResponse[ToolActivationResponse])
async def list_tool_activations(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Literal["enabled", "disabled"] | None = Query(default=None)
) -> PaginatedResponse[ToolActivationResponse]
```

List tool activations for an agent.

<a id="soldier.api.routes.tools.enable_tool"></a>

#### enable\_tool

```python
@router.post("", response_model=ToolActivationResponse, status_code=201)
async def enable_tool(agent_id: UUID, request: ToolActivationCreate,
                      tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep) -> ToolActivationResponse
```

Enable a tool for an agent.

<a id="soldier.api.routes.tools.update_tool_activation"></a>

#### update\_tool\_activation

```python
@router.put("/{tool_id}", response_model=ToolActivationResponse)
async def update_tool_activation(
        agent_id: UUID, tool_id: str, request: ToolActivationUpdate,
        tenant_context: TenantContextDep,
        config_store: ConfigStoreDep) -> ToolActivationResponse
```

Update a tool activation (policy override).

<a id="soldier.api.routes.tools.disable_tool"></a>

#### disable\_tool

```python
@router.delete("/{tool_id}", status_code=204)
async def disable_tool(agent_id: UUID, tool_id: str,
                       tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> None
```

Disable a tool for an agent.

