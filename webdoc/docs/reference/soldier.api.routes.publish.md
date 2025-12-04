<a id="soldier.api.routes.publish"></a>

# soldier.api.routes.publish

Publishing and versioning endpoints.

<a id="soldier.api.routes.publish.get_publish_status"></a>

#### get\_publish\_status

```python
@router.get("", response_model=PublishStatusResponse)
async def get_publish_status(
        agent_id: UUID, tenant_context: TenantContextDep,
        config_store: ConfigStoreDep) -> PublishStatusResponse
```

Get current publish status for an agent.

<a id="soldier.api.routes.publish.initiate_publish"></a>

#### initiate\_publish

```python
@router.post("", response_model=PublishJobResponse, status_code=202)
async def initiate_publish(
        agent_id: UUID, request: PublishRequest,
        tenant_context: TenantContextDep, config_store: ConfigStoreDep,
        background_tasks: BackgroundTasks) -> PublishJobResponse
```

Initiate a publish operation.

Returns immediately with job ID. Use GET /publish/{publish_id}
to check progress.

<a id="soldier.api.routes.publish.get_publish_job"></a>

#### get\_publish\_job

```python
@router.get("/{publish_id}", response_model=PublishJobResponse)
async def get_publish_job(agent_id: UUID, publish_id: UUID,
                          tenant_context: TenantContextDep,
                          config_store: ConfigStoreDep) -> PublishJobResponse
```

Get the status of a publish job.

<a id="soldier.api.routes.publish.rollback_to_version"></a>

#### rollback\_to\_version

```python
@router.post("/rollback", response_model=PublishJobResponse)
async def rollback_to_version(
        agent_id: UUID, request: RollbackRequest,
        tenant_context: TenantContextDep,
        config_store: ConfigStoreDep) -> PublishJobResponse
```

Rollback agent configuration to a previous version.

