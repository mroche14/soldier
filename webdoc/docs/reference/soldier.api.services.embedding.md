<a id="soldier.api.services.embedding"></a>

# soldier.api.services.embedding

Async embedding service for rule embedding computation.

<a id="soldier.api.services.embedding.EmbeddingService"></a>

## EmbeddingService Objects

```python
class EmbeddingService()
```

Service for async embedding computation.

Handles background computation of embeddings for rules
without blocking API responses.

<a id="soldier.api.services.embedding.EmbeddingService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore,
             embedding_provider: EmbeddingProvider,
             max_retries: int = 3) -> None
```

Initialize embedding service.

**Arguments**:

- `config_store` - Store for persisting updated embeddings
- `embedding_provider` - Provider for computing embeddings
- `max_retries` - Maximum retry attempts on failure

<a id="soldier.api.services.embedding.EmbeddingService.compute_rule_embedding"></a>

#### compute\_rule\_embedding

```python
async def compute_rule_embedding(tenant_id: UUID, rule_id: UUID) -> bool
```

Compute and persist embedding for a rule.

This method is designed to be called as a background task.
It fetches the rule, computes embedding, and saves the updated rule.

**Arguments**:

- `tenant_id` - Tenant owning the rule
- `rule_id` - Rule to compute embedding for
  

**Returns**:

  True if embedding was successfully computed and saved

<a id="soldier.api.services.embedding.EmbeddingService.compute_rule_embeddings_batch"></a>

#### compute\_rule\_embeddings\_batch

```python
async def compute_rule_embeddings_batch(
        tenant_id: UUID, rule_ids: list[UUID]) -> dict[UUID, bool]
```

Compute embeddings for multiple rules.

**Arguments**:

- `tenant_id` - Tenant owning the rules
- `rule_ids` - List of rule IDs to process
  

**Returns**:

  Dict mapping rule_id to success status

<a id="soldier.api.services.embedding.schedule_embedding_computation"></a>

#### schedule\_embedding\_computation

```python
async def schedule_embedding_computation(embedding_service: EmbeddingService,
                                         tenant_id: UUID,
                                         rule_id: UUID) -> None
```

Background task for embedding computation.

This function is designed to be passed to FastAPI's BackgroundTasks.

**Arguments**:

- `embedding_service` - Service to use for computation
- `tenant_id` - Tenant owning the rule
- `rule_id` - Rule to compute embedding for

