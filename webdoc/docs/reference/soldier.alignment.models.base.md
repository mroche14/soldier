<a id="focal.alignment.models.base"></a>

# focal.alignment.models.base

Base models for alignment domain entities.

<a id="focal.alignment.models.base.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="focal.alignment.models.base.TenantScopedModel"></a>

## TenantScopedModel Objects

```python
class TenantScopedModel(BaseModel)
```

Base for all tenant-scoped entities.

All entities in the system must be scoped to a tenant for
multi-tenant isolation. This base class provides:
- tenant_id: Required tenant identifier
- created_at/updated_at: Automatic timestamps
- deleted_at: Soft delete marker

<a id="focal.alignment.models.base.TenantScopedModel.is_deleted"></a>

#### is\_deleted

```python
@property
def is_deleted() -> bool
```

Check if entity is soft-deleted.

<a id="focal.alignment.models.base.TenantScopedModel.touch"></a>

#### touch

```python
def touch() -> None
```

Update the updated_at timestamp to current time.

<a id="focal.alignment.models.base.TenantScopedModel.soft_delete"></a>

#### soft\_delete

```python
def soft_delete() -> None
```

Mark entity as soft-deleted.

<a id="focal.alignment.models.base.AgentScopedModel"></a>

## AgentScopedModel Objects

```python
class AgentScopedModel(TenantScopedModel)
```

Base for entities scoped to a specific agent.

Extends TenantScopedModel with agent_id for entities that
belong to a specific agent within a tenant.

