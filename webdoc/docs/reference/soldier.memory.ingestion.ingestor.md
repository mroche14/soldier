<a id="focal.memory.ingestion.ingestor"></a>

# focal.memory.ingestion.ingestor

Memory ingestion orchestrator.

<a id="focal.memory.ingestion.ingestor.MemoryIngestor"></a>

## MemoryIngestor Objects

```python
class MemoryIngestor()
```

Main orchestrator for episode creation and async task dispatching.

<a id="focal.memory.ingestion.ingestor.MemoryIngestor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(memory_store: MemoryStore,
             embedding_provider: EmbeddingProvider,
             entity_extractor: Any | None,
             summarizer: Any | None,
             task_queue: TaskQueue,
             config: MemoryIngestionConfig | None = None,
             fallback_embedding_provider: EmbeddingProvider | None = None)
```

Initialize memory ingestor.

**Arguments**:

- `memory_store` - Store for episodes and entities
- `embedding_provider` - Primary provider for embeddings
- `entity_extractor` - Service for entity extraction (optional)
- `summarizer` - Service for summarization (optional)
- `task_queue` - Queue for async tasks
- `config` - Configuration for ingestion
- `fallback_embedding_provider` - Fallback provider for embeddings

<a id="focal.memory.ingestion.ingestor.MemoryIngestor.ingest_turn"></a>

#### ingest\_turn

```python
async def ingest_turn(turn: Turn, session: Session) -> Episode
```

Ingest a conversation turn into memory.

Synchronous operations (<500ms):
- Create Episode model from turn
- Generate embedding via EmbeddingProvider
- Store episode in MemoryStore
- Queue async extraction tasks

Asynchronous operations (queued):
- Extract entities and relationships
- Check if summarization threshold reached

**Arguments**:

- `turn` - Conversation turn with user message and agent response
- `session` - Current session context (for group_id)
  

**Returns**:

- `Episode` - Stored episode with generated embedding
  

**Raises**:

- `IngestionError` - If episode creation or storage fails

<a id="focal.memory.ingestion.ingestor.MemoryIngestor.ingest_event"></a>

#### ingest\_event

```python
async def ingest_event(event_type: str,
                       content: str,
                       group_id: str,
                       metadata: dict[str, Any] | None = None) -> Episode
```

Ingest a system event into memory.

Similar to ingest_turn but for non-conversation events
(e.g., tool execution, scenario transitions, errors).

**Arguments**:

- `event_type` - Type of event (for source_metadata)
- `content` - Event description
- `group_id` - Tenant:session identifier
- `metadata` - Optional additional context
  

**Returns**:

- `Episode` - Stored episode
  

**Raises**:

- `IngestionError` - If episode creation or storage fails

