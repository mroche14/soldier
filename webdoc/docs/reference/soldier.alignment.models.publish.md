<a id="soldier.alignment.models.publish"></a>

# soldier.alignment.models.publish

Publish job models for configuration versioning.

<a id="soldier.alignment.models.publish.PublishStage"></a>

## PublishStage Objects

```python
class PublishStage(BaseModel)
```

Progress tracking for a single publish stage.

Each publish job goes through multiple stages:
- validate: Check configuration consistency
- compile: Compute embeddings, validate references
- write_bundles: Serialize configuration
- swap_pointer: Atomic version switch
- invalidate_cache: Clear cached config

<a id="soldier.alignment.models.publish.PublishJob"></a>

## PublishJob Objects

```python
class PublishJob(TenantScopedModel)
```

Tracks publish operation progress.

A publish job represents the process of making configuration
changes live for an agent. It progresses through multiple
stages and tracks success/failure for each.

<a id="soldier.alignment.models.publish.PublishJob.create_with_stages"></a>

#### create\_with\_stages

```python
@classmethod
def create_with_stages(cls,
                       tenant_id: UUID,
                       agent_id: UUID,
                       version: int,
                       started_at: datetime,
                       description: str | None = None) -> "PublishJob"
```

Create a new publish job with all stages initialized.

