# Quickstart: Memory Ingestion System

**Feature**: 005-memory-ingestion
**Date**: 2025-11-28

## Overview

This guide shows how to integrate and use the Memory Ingestion System in Soldier. The system automatically captures conversation turns as episodes, extracts entities and relationships, and generates hierarchical summaries.

---

## Prerequisites

Before using memory ingestion, ensure these components are available:

1. **MemoryStore** implementation (InMemory, PostgreSQL, Neo4j, etc.)
2. **LLMProvider** configured for entity extraction
3. **EmbeddingProvider** configured for episode embeddings
4. **Configuration** loaded from TOML files

---

## Basic Setup

### 1. Configuration

Add memory ingestion configuration to your TOML file:

**`config/default.toml`**:
```toml
[memory.ingestion]
enabled = true
embedding_enabled = true
entity_extraction_enabled = true
summarization_enabled = true
async_extraction = true
async_summarization = true
queue_backend = "inmemory"  # or "redis" for production
max_ingestion_latency_ms = 500

[memory.ingestion.extraction]
enabled = true
llm_provider = "anthropic"
model = "haiku"
max_tokens = 1024
temperature = 0.3
batch_size = 10
timeout_ms = 2000
min_confidence = "medium"

[memory.ingestion.deduplication]
exact_match_enabled = true
fuzzy_match_enabled = true
fuzzy_threshold = 0.85
embedding_match_enabled = true
embedding_threshold = 0.80
rule_based_enabled = true

[memory.ingestion.summarization.window]
turns_per_summary = 20
llm_provider = "anthropic"
model = "haiku"
max_tokens = 256
temperature = 0.5

[memory.ingestion.summarization.meta]
summaries_per_meta = 5
enabled_at_turn_count = 100
llm_provider = "anthropic"
model = "haiku"
max_tokens = 512
temperature = 0.5
```

---

### 2. Initialize Components

**Python code**:
```python
from soldier.config.settings import get_settings
from soldier.memory.stores.inmemory import InMemoryMemoryStore
from soldier.providers.factory import (
    create_llm_provider,
    create_embedding_provider,
)
from soldier.memory.ingestion.ingestor import MemoryIngestor
from soldier.memory.ingestion.entity_extractor import EntityExtractor
from soldier.memory.ingestion.summarizer import ConversationSummarizer
from soldier.observability.logging import get_logger

# Load configuration
settings = get_settings()
config = settings.memory.ingestion

# Initialize stores
memory_store = InMemoryMemoryStore()

# Initialize providers
llm_provider = create_llm_provider(
    settings.providers.llm[config.extraction.llm_provider]
)
embedding_provider = create_embedding_provider(
    settings.providers.embedding["default"]
)

# Initialize services
entity_extractor = EntityExtractor(
    llm_provider=llm_provider,
    config=config.extraction,
)

summarizer = ConversationSummarizer(
    llm_provider=llm_provider,
    memory_store=memory_store,
    config=config.summarization,
)

# Initialize ingestor (main entry point)
ingestor = MemoryIngestor(
    memory_store=memory_store,
    embedding_provider=embedding_provider,
    entity_extractor=entity_extractor,
    summarizer=summarizer,
    config=config,
)

logger = get_logger(__name__)
```

---

## Usage Examples

### Example 1: Ingest a Conversation Turn

```python
from soldier.conversation.models.turn import Turn
from soldier.conversation.models.session import Session
from datetime import datetime, UTC
from uuid import uuid4

# Create session
session = Session(
    id=uuid4(),
    tenant_id=uuid4(),
    agent_id=uuid4(),
    created_at=datetime.now(UTC),
)

# Create turn
turn = Turn(
    session_id=session.id,
    user_message="I ordered a laptop last week but it arrived damaged",
    agent_response="I'm sorry to hear that. Let me help you with a replacement.",
    timestamp=datetime.now(UTC),
)

# Ingest turn (synchronous - returns quickly)
episode = await ingestor.ingest_turn(turn, session)

print(f"Episode created: {episode.id}")
print(f"Embedding dimensions: {len(episode.embedding)}")
print(f"Group ID: {episode.group_id}")

# Entity extraction happens asynchronously in background
# Check logs for "entities_extracted" event
```

**Output**:
```
Episode created: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Embedding dimensions: 768
Group ID: f47ac10b-58cc-4372-a567-0e02b2c3d479:3fa85f64-5717-4562-b3fc-2c963f66afa6
```

---

### Example 2: Ingest Multiple Turns

```python
# Simulate a conversation
turns = [
    ("Hi, I need help with my order", "Hello! I'd be happy to help. What's your order number?"),
    ("It's order #12345", "Thank you. Let me look that up for you."),
    ("It hasn't arrived yet", "I see it's still in transit. Expected delivery is tomorrow."),
    ("Can you expedite it?", "Certainly, I've upgraded to next-day shipping at no charge."),
]

for user_msg, agent_msg in turns:
    turn = Turn(
        session_id=session.id,
        user_message=user_msg,
        agent_response=agent_msg,
        timestamp=datetime.now(UTC),
    )

    episode = await ingestor.ingest_turn(turn, session)
    print(f"Ingested turn {episode.id}")

# Wait a moment for async extraction
await asyncio.sleep(2)

# Query extracted entities
entities = await memory_store.get_entities(
    group_id=f"{session.tenant_id}:{session.id}"
)

print(f"Extracted {len(entities)} entities:")
for entity in entities:
    print(f"  - {entity.name} ({entity.entity_type})")
```

**Output**:
```
Ingested turn 7c9e6679-7425-40de-944b-e07fc1f90ae7
Ingested turn 8d0e7780-8536-41ef-a55c-1f13c3d4e48b
Ingested turn 9e1e8891-9647-42f0-b66d-2024d4e5f59c
Ingested turn 0f2f9902-a758-43f1-c77e-3135e5f6g60d

Extracted 3 entities:
  - Order #12345 (order)
  - Customer (person)
  - Shipping upgrade (concept)
```

---

### Example 3: Trigger Summarization

```python
# Ingest 20 turns to hit summarization threshold
for i in range(20):
    turn = Turn(
        session_id=session.id,
        user_message=f"User message {i+1}",
        agent_response=f"Agent response {i+1}",
        timestamp=datetime.now(UTC),
    )
    await ingestor.ingest_turn(turn, session)

# Wait for async summarization
await asyncio.sleep(3)

# Query summaries
summaries = await memory_store.get_episodes(
    group_id=f"{session.tenant_id}:{session.id}",
    content_type="summary",
)

if summaries:
    print(f"Summary created: {summaries[0].content[:200]}...")
else:
    print("No summary created yet (still processing)")
```

**Output**:
```
Summary created: The customer inquired about order #12345 which had not arrived.
Agent confirmed it was in transit with expected delivery tomorrow. Customer requested
expedited shipping which was upgraded to next-day at no charge. Additional questions
about delivery address and...
```

---

### Example 4: Manually Trigger Entity Extraction

```python
# Create episode without using ingestor
from soldier.memory.models.episode import Episode

episode = Episode(
    group_id=f"{session.tenant_id}:{session.id}",
    content="Customer John Smith called about his laptop order. It was damaged during shipping.",
    source="agent",
    content_type="event",
    occurred_at=datetime.now(UTC),
)

# Store episode
await memory_store.add_episode(episode)

# Manually extract entities
result = await entity_extractor.extract(episode)

print(f"Extracted {len(result.entities)} entities:")
for entity in result.entities:
    print(f"  - {entity.name} ({entity.type}) - confidence: {entity.confidence}")

print(f"\nExtracted {len(result.relationships)} relationships:")
for rel in result.relationships:
    print(f"  - {rel.from_name} --{rel.relation_type}--> {rel.to_name}")
```

**Output**:
```
Extracted 3 entities:
  - John Smith (person) - confidence: high
  - laptop order (order) - confidence: high
  - damaged (issue) - confidence: high

Extracted 2 relationships:
  - John Smith --placed--> laptop order
  - laptop order --has_issue--> damaged
```

---

### Example 5: Query Memory with Temporal Context

```python
# Query current active entities
active_entities = await memory_store.get_entities(
    group_id=f"{session.tenant_id}:{session.id}"
)
print(f"Active entities: {len(active_entities)}")

# Query relationships as of specific date
from datetime import datetime, UTC, timedelta

past_date = datetime.now(UTC) - timedelta(days=7)

# Note: This requires MemoryStore implementation to support temporal queries
# Example with hypothetical interface extension:
# relationships_then = await memory_store.get_relationships(
#     group_id=f"{session.tenant_id}:{session.id}",
#     valid_as_of=past_date
# )
```

---

### Example 6: Disable Features Selectively

```python
# Create ingestor with entity extraction disabled
config_no_extraction = config.model_copy(deep=True)
config_no_extraction.entity_extraction_enabled = False

ingestor_no_extraction = MemoryIngestor(
    memory_store=memory_store,
    embedding_provider=embedding_provider,
    entity_extractor=entity_extractor,
    summarizer=summarizer,
    config=config_no_extraction,
)

# This will create episodes but NOT extract entities
episode = await ingestor_no_extraction.ingest_turn(turn, session)

# Episodes still get embeddings (if embedding_enabled=True)
assert episode.embedding is not None
assert len(episode.entity_ids) == 0  # No entities extracted
```

---

## Advanced Usage

### Custom Entity Types

Configure entity extraction to recognize domain-specific entities:

```python
# Modify extraction prompt to include custom entity types
# This requires editing the EntityExtractor prompt template

custom_prompt = """
Extract entities from the conversation:

Entity types to extract:
- person: People, customers
- product: Items, goods
- order: Purchase orders
- issue: Problems, complaints
- ticket: Support tickets (custom)
- subscription: Subscription plans (custom)
- feature_request: Feature requests (custom)

For each entity, provide name, type, attributes, and confidence.
"""

# Use custom prompt in EntityExtractor
entity_extractor.set_extraction_prompt(custom_prompt)
```

---

### Batch Extraction for Backfill

```python
# Extract entities from existing episodes (backfill scenario)
existing_episodes = await memory_store.get_episodes(
    group_id=f"{session.tenant_id}:{session.id}",
    limit=100
)

# Batch extract (more efficient)
results = await entity_extractor.extract_batch(existing_episodes)

# Process results
for episode, result in zip(existing_episodes, results):
    for entity in result.entities:
        # Deduplicate and store
        existing = await entity_deduplicator.find_duplicate(entity, episode.group_id)
        if existing:
            merged = await entity_deduplicator.merge_entities(existing, entity)
            await memory_store.update_entity(merged)
        else:
            entity.group_id = episode.group_id
            await memory_store.add_entity(entity)

    for rel in result.relationships:
        # Store relationships
        rel.group_id = episode.group_id
        await memory_store.add_relationship(rel)
```

---

### Per-Agent Configuration

Override memory ingestion settings per agent:

**`config/default.toml`**:
```toml
# Global default
[memory.ingestion.summarization.window]
turns_per_summary = 20

# Agent-specific override (customer support - more granular)
[agents.customer_support.memory.ingestion.summarization.window]
turns_per_summary = 10

# Agent-specific override (sales - less frequent)
[agents.sales.memory.ingestion.summarization.window]
turns_per_summary = 50
```

---

## Integration with Alignment Engine

### Hook into Turn Processing

```python
# In AlignmentEngine.process_turn()

async def process_turn(
    self,
    user_message: str,
    session: Session,
) -> AlignmentResult:
    # ... existing pipeline steps (context extraction, retrieval, etc.)

    # After generation completes
    turn = Turn(
        session_id=session.id,
        user_message=user_message,
        agent_response=result.response,
        timestamp=datetime.now(UTC),
    )

    # Ingest into memory (async)
    episode = await self.memory_ingestor.ingest_turn(turn, session)

    # Add episode_id to result metadata
    result.metadata["episode_id"] = str(episode.id)

    return result
```

---

## Monitoring & Debugging

### Check Ingestion Metrics

```python
from soldier.observability.metrics import (
    EPISODES_CREATED,
    ENTITIES_EXTRACTED,
    SUMMARIES_CREATED,
)

# View counters (requires Prometheus scraping)
print(f"Episodes created: {EPISODES_CREATED._value.get()}")
print(f"Entities extracted: {ENTITIES_EXTRACTED._value.get()}")
print(f"Summaries created: {SUMMARIES_CREATED._value.get()}")
```

---

### Enable Debug Logging

```python
import logging
from soldier.observability.logging import setup_logging

# Set log level to DEBUG for memory ingestion
logging.getLogger("soldier.memory.ingestion").setLevel(logging.DEBUG)

# Re-run ingestion
episode = await ingestor.ingest_turn(turn, session)

# Check logs for detailed extraction steps:
# - "entity_extraction_started"
# - "deduplication_stage" (exact, fuzzy, embedding, rule)
# - "entity_merged" or "entity_created"
# - "relationship_created"
```

---

### Query Background Task Status

```python
# If using Redis Queue
from rq import Queue
from redis import Redis

redis_conn = Redis(host='localhost', port=6379)
queue = Queue('memory_ingestion', connection=redis_conn)

# Check queue status
print(f"Pending jobs: {len(queue)}")
print(f"Failed jobs: {queue.failed_job_registry.count}")

# Get specific job status
job = queue.fetch_job(job_id)
if job:
    print(f"Job status: {job.get_status()}")
    print(f"Job result: {job.result}")
```

---

## Common Patterns

### Pattern 1: Graceful Degradation

```python
try:
    episode = await ingestor.ingest_turn(turn, session)
except IngestionError as e:
    logger.error("ingestion_failed", error=str(e))
    # Continue - conversation can proceed without memory
    # (episode creation failed but conversation flow continues)
```

**Rationale**: Memory ingestion should NEVER block the conversation flow.

---

### Pattern 2: Async Task Monitoring

```python
# Queue entity extraction
task_id = await ingestor._queue_entity_extraction(episode.id, episode.group_id)

# Poll for completion (in background monitoring job)
async def monitor_extraction(task_id):
    while True:
        status = await task_queue.get_status(task_id)
        if status == "completed":
            logger.info("extraction_complete", task_id=task_id)
            break
        elif status == "failed":
            logger.error("extraction_failed", task_id=task_id)
            break
        await asyncio.sleep(1)
```

---

### Pattern 3: Conditional Extraction

```python
# Only extract entities if message contains potential entities
if has_potential_entities(turn.user_message):
    episode = await ingestor.ingest_turn(turn, session)
else:
    # Skip extraction, just store episode
    config_no_extraction = config.model_copy(deep=True)
    config_no_extraction.entity_extraction_enabled = False
    episode = await ingestor.ingest_turn(turn, session)
```

---

## Troubleshooting

### Issue: Episodes created but no entities extracted

**Symptoms**:
- Episodes appear in MemoryStore
- `entity_ids` field is empty
- No log events with "entities_extracted"

**Possible causes**:
1. Entity extraction disabled in config
2. LLM provider timeout
3. Async task queue not processing

**Solution**:
```python
# Check config
print(f"Extraction enabled: {config.entity_extraction_enabled}")

# Check if queue is processing
# (If using in-memory queue, check asyncio tasks)

# Check LLM provider
try:
    result = await entity_extractor.extract(episode)
    print(f"Extracted {len(result.entities)} entities")
except Exception as e:
    print(f"Extraction error: {e}")
```

---

### Issue: Embedding generation fails

**Symptoms**:
- `episode.embedding` is `None`
- Log events with "embedding_failed"

**Possible causes**:
1. Embedding provider not configured
2. Model not available
3. Episode content too long

**Solution**:
```python
# Test embedding provider directly
test_text = "Test embedding generation"
embedding = await embedding_provider.embed([test_text])
print(f"Embedding dimensions: {len(embedding.embeddings[0])}")

# Check episode content length
print(f"Episode content length: {len(episode.content)} characters")

# If too long, truncate
if len(episode.content) > 8000:
    episode.content = episode.content[:8000] + "..."
```

---

### Issue: Summaries not being created

**Symptoms**:
- Episode count > threshold
- No summary episodes in MemoryStore
- No log events with "summary_created"

**Possible causes**:
1. Summarization disabled in config
2. Threshold calculation incorrect
3. LLM provider timeout

**Solution**:
```python
# Manually trigger summarization
summary = await summarizer.check_and_summarize_if_needed(
    f"{session.tenant_id}:{session.id}"
)

if summary:
    print(f"Summary created: {summary.id}")
else:
    print("Threshold not reached or summarization disabled")

# Check episode count
count = await memory_store.count_episodes(
    group_id=f"{session.tenant_id}:{session.id}"
)
print(f"Episode count: {count}, Threshold: {config.summarization.window.turns_per_summary}")
```

---

## Performance Tips

1. **Use batch extraction** when processing multiple episodes
2. **Enable async extraction** for real-time conversations
3. **Tune deduplication thresholds** based on your domain (stricter for exact matches, looser for concepts)
4. **Adjust summarization windows** per agent type (customer support: 10 turns, sales: 20 turns)
5. **Monitor queue depth** and scale workers if backlog grows

---

## Next Steps

- **Production deployment**: Switch to Redis queue (`queue_backend = "redis"`)
- **Observability**: Set up Prometheus + Grafana dashboards for memory metrics
- **Fine-tuning**: Adjust extraction prompts for domain-specific entities
- **Testing**: Run integration tests with real conversation data

---

## References

- **Architecture**: `docs/architecture/memory-layer.md`
- **Research**: `specs/005-memory-ingestion/research.md`
- **Data Model**: `specs/005-memory-ingestion/data-model.md`
- **Service Interfaces**: `specs/005-memory-ingestion/contracts/service-interfaces.md`
