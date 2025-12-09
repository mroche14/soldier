<a id="focal.memory.ingestion.tasks"></a>

# focal.memory.ingestion.tasks

Background task handlers for memory ingestion.

<a id="focal.memory.ingestion.tasks.extract_entities"></a>

#### extract\_entities

```python
async def extract_entities(episode_id: UUID, group_id: str,
                           memory_store: MemoryStore,
                           entity_extractor: EntityExtractor,
                           entity_deduplicator: EntityDeduplicator) -> None
```

Extract entities from an episode asynchronously.

**Arguments**:

- `episode_id` - Episode to process
- `group_id` - Tenant:session identifier
- `memory_store` - Memory store
- `entity_extractor` - Entity extractor service
- `entity_deduplicator` - Entity deduplicator service

<a id="focal.memory.ingestion.tasks.check_summarization"></a>

#### check\_summarization

```python
async def check_summarization(group_id: str, _memory_store: MemoryStore,
                              summarizer: ConversationSummarizer) -> None
```

Check if summarization threshold reached and summarize if needed.

**Arguments**:

- `group_id` - Tenant:session identifier
- `_memory_store` - Memory store (not directly used, summarizer has its own)
- `summarizer` - Conversation summarizer service

