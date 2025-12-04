<a id="soldier.api.routes.templates"></a>

# soldier.api.routes.templates

Template management endpoints.

<a id="soldier.api.routes.templates.list_templates"></a>

#### list\_templates

```python
@router.get("", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: ConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mode: TemplateMode | None = Query(default=None,
                                      description="Filter by mode"),
    scope: Scope | None = Query(default=None, description="Filter by scope"),
    sort_by: Literal["name", "created_at",
                     "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc")
) -> PaginatedResponse[TemplateResponse]
```

List templates for an agent.

<a id="soldier.api.routes.templates.create_template"></a>

#### create\_template

```python
@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(agent_id: UUID, request: TemplateCreate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> TemplateResponse
```

Create a new template.

<a id="soldier.api.routes.templates.get_template"></a>

#### get\_template

```python
@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(agent_id: UUID, template_id: UUID,
                       tenant_context: TenantContextDep,
                       config_store: ConfigStoreDep) -> TemplateResponse
```

Get a template by ID.

<a id="soldier.api.routes.templates.update_template"></a>

#### update\_template

```python
@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(agent_id: UUID, template_id: UUID,
                          request: TemplateUpdate,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> TemplateResponse
```

Update a template.

<a id="soldier.api.routes.templates.delete_template"></a>

#### delete\_template

```python
@router.delete("/{template_id}", status_code=204)
async def delete_template(agent_id: UUID, template_id: UUID,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> None
```

Delete a template (soft delete).

<a id="soldier.api.routes.templates.preview_template"></a>

#### preview\_template

```python
@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
        agent_id: UUID, template_id: UUID, request: TemplatePreviewRequest,
        tenant_context: TenantContextDep,
        config_store: ConfigStoreDep) -> TemplatePreviewResponse
```

Preview a template with variable substitution.

