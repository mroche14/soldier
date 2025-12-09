<a id="focal.api.routes.rules"></a>

# focal.api.routes.rules

Rule management endpoints.

<a id="focal.api.routes.rules.list_rules"></a>

#### list\_rules

```python
@router.get("", response_model=PaginatedResponse[RuleResponse])
async def list_rules(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    scope: Scope | None = Query(default=None, description="Filter by scope"),
    enabled: bool | None = Query(default=None,
                                 description="Filter by enabled status"),
    priority_min: int | None = Query(default=None, ge=-100, le=100),
    priority_max: int | None = Query(default=None, ge=-100, le=100),
    sort_by: Literal["name", "priority", "created_at",
                     "updated_at"] = Query(default="priority"),
    sort_order: Literal["asc", "desc"] = Query(default="desc")
) -> PaginatedResponse[RuleResponse]
```

List rules for an agent.

Retrieve a paginated list of rules with optional filtering and sorting.

**Arguments**:

- `agent_id` - Agent identifier
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
- `limit` - Maximum number of rules to return
- `offset` - Number of rules to skip
- `scope` - Filter by scope level
- `enabled` - Filter by enabled status
- `priority_min` - Minimum priority filter
- `priority_max` - Maximum priority filter
- `sort_by` - Field to sort by
- `sort_order` - Sort direction
  

**Returns**:

  Paginated list of rules

<a id="focal.api.routes.rules.create_rule"></a>

#### create\_rule

```python
@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(agent_id: UUID, request: RuleCreate,
                      tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep,
                      _background_tasks: BackgroundTasks) -> RuleResponse
```

Create a new rule.

Creates a rule for the specified agent. Embedding computation is
triggered asynchronously in the background.

**Arguments**:

- `agent_id` - Agent identifier
- `request` - Rule creation request
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
- `_background_tasks` - FastAPI background tasks (for future embedding)
  

**Returns**:

  Created rule

<a id="focal.api.routes.rules.get_rule"></a>

#### get\_rule

```python
@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(agent_id: UUID, rule_id: UUID,
                   tenant_context: TenantContextDep,
                   config_store: ConfigStoreDep) -> RuleResponse
```

Get a rule by ID.

**Arguments**:

- `agent_id` - Agent identifier
- `rule_id` - Rule identifier
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Returns**:

  Rule details
  

**Raises**:

- `RuleNotFoundError` - If rule doesn't exist

<a id="focal.api.routes.rules.update_rule"></a>

#### update\_rule

```python
@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(agent_id: UUID, rule_id: UUID, request: RuleUpdate,
                      tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep,
                      _background_tasks: BackgroundTasks) -> RuleResponse
```

Update a rule.

If condition_text or action_text changes, embedding recomputation
is triggered asynchronously.

**Arguments**:

- `agent_id` - Agent identifier
- `rule_id` - Rule identifier
- `request` - Rule update request
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
- `_background_tasks` - FastAPI background tasks (for future embedding)
  

**Returns**:

  Updated rule
  

**Raises**:

- `RuleNotFoundError` - If rule doesn't exist

<a id="focal.api.routes.rules.delete_rule"></a>

#### delete\_rule

```python
@router.delete("/{rule_id}", status_code=204)
async def delete_rule(agent_id: UUID, rule_id: UUID,
                      tenant_context: TenantContextDep,
                      config_store: ConfigStoreDep) -> None
```

Delete a rule (soft delete).

**Arguments**:

- `agent_id` - Agent identifier
- `rule_id` - Rule identifier
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Raises**:

- `RuleNotFoundError` - If rule doesn't exist

<a id="focal.api.routes.rules.bulk_rule_operations"></a>

#### bulk\_rule\_operations

```python
@router.post("/bulk", response_model=BulkResponse[RuleResponse])
async def bulk_rule_operations(
        agent_id: UUID, request: BulkRequest[RuleCreate],
        tenant_context: TenantContextDep,
        config_store: ConfigStoreDep) -> BulkResponse[RuleResponse]
```

Execute bulk rule operations.

Supports create, update, and delete operations in a single request.
Operations are processed in order, with partial success handling.

**Arguments**:

- `agent_id` - Agent identifier
- `request` - Bulk operation request
- `tenant_context` - Authenticated tenant context
- `config_store` - Configuration store
  

**Returns**:

  Bulk operation results

