<a id="soldier.api.routes.agents"></a>

# soldier.api.routes.agents

Agent management endpoints.

<a id="soldier.api.routes.agents.list_agents"></a>

#### list\_agents

```python
@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    enabled: bool | None = Query(default=None,
                                 description="Filter by enabled status"),
    sort_by: Literal["name", "created_at",
                     "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc")
) -> PaginatedResponse[AgentResponse]
```

List agents for the tenant.

Retrieve a paginated list of agents with optional filtering and sorting.

**Arguments**:

- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
- `limit` - Maximum number of agents to return (1-100)
- `offset` - Number of agents to skip
- `enabled` - Filter by enabled status
- `sort_by` - Field to sort by
- `sort_order` - Sort direction
  

**Returns**:

  Paginated list of agents

<a id="soldier.api.routes.agents.create_agent"></a>

#### create\_agent

```python
@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(request: AgentCreate, tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> AgentResponse
```

Create a new agent.

**Arguments**:

- `request` - Agent creation request
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Returns**:

  Created agent

<a id="soldier.api.routes.agents.get_agent"></a>

#### get\_agent

```python
@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    include_stats: bool = Query(default=False,
                                description="Include usage statistics")
) -> AgentResponse
```

Get an agent by ID.

**Arguments**:

- `agent_id` - Agent identifier
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
- `include_stats` - Whether to include usage statistics
  

**Returns**:

  Agent details
  

**Raises**:

- `AgentNotFoundError` - If agent doesn't exist or belongs to different tenant

<a id="soldier.api.routes.agents.update_agent"></a>

#### update\_agent

```python
@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: UUID, request: AgentUpdate,
                       tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> AgentResponse
```

Update an agent.

**Arguments**:

- `agent_id` - Agent identifier
- `request` - Agent update request
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Returns**:

  Updated agent
  

**Raises**:

- `AgentNotFoundError` - If agent doesn't exist or belongs to different tenant

<a id="soldier.api.routes.agents.delete_agent"></a>

#### delete\_agent

```python
@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> None
```

Delete an agent (soft delete).

This performs a soft delete by setting deleted_at timestamp.
The agent will no longer respond to requests.

**Arguments**:

- `agent_id` - Agent identifier
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Raises**:

- `AgentNotFoundError` - If agent doesn't exist or belongs to different tenant

