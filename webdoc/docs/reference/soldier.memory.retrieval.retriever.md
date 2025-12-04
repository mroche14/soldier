<a id="soldier.memory.retrieval.retriever"></a>

# soldier.memory.retrieval.retriever

Memory retrieval with selection strategies.

<a id="soldier.memory.retrieval.retriever.MemoryRetriever"></a>

## MemoryRetriever Objects

```python
class MemoryRetriever()
```

Retrieve relevant memory episodes using embeddings and selection.

<a id="soldier.memory.retrieval.retriever.MemoryRetriever.retrieve"></a>

#### retrieve

```python
async def retrieve(tenant_id: UUID, agent_id: UUID,
                   context: Context) -> list[ScoredEpisode]
```

Retrieve episodes for the tenant/agent.

