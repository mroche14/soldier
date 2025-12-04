<a id="soldier.api.services.publish"></a>

# soldier.api.services.publish

Publish job orchestration service.

<a id="soldier.api.services.publish.PublishService"></a>

## PublishService Objects

```python
class PublishService()
```

Service for orchestrating publish operations.

Manages the lifecycle of publish jobs and executes
the multi-stage publish process.

<a id="soldier.api.services.publish.PublishService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore) -> None
```

Initialize publish service.

**Arguments**:

- `config_store` - Store for configuration data

<a id="soldier.api.services.publish.PublishService.get_publish_status"></a>

#### get\_publish\_status

```python
async def get_publish_status(tenant_id: UUID,
                             agent_id: UUID) -> dict[str, Any]
```

Get current publish status for an agent.

**Returns**:

  Dict with current_version, draft_version, has_unpublished_changes, etc.

<a id="soldier.api.services.publish.PublishService.create_publish_job"></a>

#### create\_publish\_job

```python
async def create_publish_job(tenant_id: UUID,
                             agent_id: UUID,
                             description: str | None = None) -> PublishJob
```

Create a new publish job.

**Arguments**:

- `tenant_id` - Tenant owning the agent
- `agent_id` - Agent to publish
- `description` - Optional description for this publish
  

**Returns**:

  Created publish job

<a id="soldier.api.services.publish.PublishService.get_job"></a>

#### get\_job

```python
async def get_job(tenant_id: UUID, job_id: UUID) -> PublishJob | None
```

Get a publish job by ID.

**Arguments**:

- `tenant_id` - Tenant owning the job
- `job_id` - Job identifier
  

**Returns**:

  Publish job if found and owned by tenant

<a id="soldier.api.services.publish.PublishService.execute_publish"></a>

#### execute\_publish

```python
async def execute_publish(job_id: UUID) -> PublishJob
```

Execute a publish job through all stages.

This is a simplified implementation for MVP.
Production would run stages asynchronously with proper
error handling and rollback.

**Arguments**:

- `job_id` - Job to execute
  

**Returns**:

  Updated job with final status

<a id="soldier.api.services.publish.PublishService.rollback_to_version"></a>

#### rollback\_to\_version

```python
async def rollback_to_version(tenant_id: UUID,
                              agent_id: UUID,
                              target_version: int,
                              reason: str | None = None) -> PublishJob
```

Rollback an agent to a previous version.

For MVP, this creates a rollback job that sets the
agent version. Production would restore configuration
from version history.

**Arguments**:

- `tenant_id` - Tenant owning the agent
- `agent_id` - Agent to rollback
- `target_version` - Version to rollback to
- `reason` - Optional reason for rollback
  

**Returns**:

  Created rollback job

