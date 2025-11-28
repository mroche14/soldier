# Research: Memory Ingestion System

**Date**: 2025-11-28
**Feature**: Phase 12 - Memory Layer (Memory Ingestion System)
**Scope**: Entity extraction, deduplication, temporal updates, async patterns, embeddings, summarization

---

## 1. Entity Extraction Approaches

### Decision: LLM-Based with Structured Output via Provider Interface

Use Claude (or configured LLM provider) with structured output to extract entities and relationships from episode content.

### Rationale

1. **Accuracy in Conversational Context**: LLMs understand natural language nuance and conversational context better than rule-based NER systems. Can distinguish between "Order #12345" as an entity vs. a reference number.

2. **Domain Flexibility**: No need to pre-define entity types or relationships. The LLM can adapt to domain-specific entities (products, orders, issues, concepts) based on provided schema.

3. **Relationship Extraction**: LLMs natively extract relationships as part of structured output. spaCy requires separate relation extraction patterns or a different model.

4. **Cost-Effective via Configuration**: Uses existing `LLMProvider` interface - configured to use cheaper models (Haiku) for extraction vs. expensive models (Sonnet) for generation. Fallback chains support cost optimization.

5. **Aligns with Architecture**: Soldier uses LLMProvider for all heavy cognitive tasks. Consistent with context extraction, filtering, and generation patterns.

6. **Extensibility**: If requirements change, just update the extraction prompt or switch providers. No code changes needed.

### Alternatives Considered

#### spaCy NER
- **Pros**: Fast (10-50ms), no API calls, works offline
- **Cons**:
  - Requires pre-defined entity types and careful training
  - Can't extract relationships natively (would need separate pipeline)
  - Doesn't understand conversational nuance or domain context
  - Performance degrades on out-of-domain text
  - For "Customer ordered a laptop", may tag both as PRODUCT instead of recognizing the ORDER relationship
  - Accuracy typically 70-75% on general text, lower on specialized domains

#### Hybrid (LLM + spaCy Fallback)
- **Pros**: Fast fallback if LLM fails, offline capability
- **Cons**:
  - Operational complexity
  - Quality inconsistency between paths
  - Double maintenance burden
  - Architecture compromise (not mentioned in design docs)

#### Rule-Based Extraction
- **Pros**: Deterministic, no cost
- **Cons**:
  - Unmaintainable for conversational text
  - Requires constant pattern updates
  - Fails on any variation

### Implementation Notes

**Entity Extraction Prompt Design**:
```
You are an entity extraction system for a knowledge graph.
Extract named entities from the following conversation turn.

Entity types to extract:
- person: People, customers, employees (must have name if known)
- order: Purchase orders, transactions
- product: Items, goods mentioned
- issue: Problems, complaints, damage
- concept: Abstract entities specific to domain (e.g., "loyalty status", "account")

For each entity:
1. Name (exact text from conversation if possible)
2. Type (choose from above)
3. Attributes (key-value pairs: {"email": "...", "status": "...", })
4. Confidence (high/medium/low - only include high/medium)

Extract relationships:
- from_name: Source entity name
- to_name: Target entity name
- relation_type: contains, ordered, has_issue, owns, related_to, etc.

Return only entities with high/medium confidence. Skip ambiguous mentions.
```

**Configuration-Driven**:
```toml
[pipeline.entity_extraction]
enabled = true
llm_provider = "haiku"  # Cheap model for extraction
max_tokens = 1024
temperature = 0.3  # Low temp for consistent extraction

[pipeline.relationship_extraction]
enabled = true
llm_provider = "haiku"
max_tokens = 512
temperature = 0.3
```

**Performance Targets**:
- Single episode extraction: 200-400ms (using Haiku)
- Batch of 10 episodes: 2-4s (parallel calls)
- Fallback to lower-confidence extraction if latency exceeds 500ms

**Error Handling**:
- If LLM extraction fails (timeout, provider error), skip extraction and log
- Episode still stored successfully (extraction is async, doesn't block)
- Implement retry logic for transient failures

---

## 2. Entity Deduplication Strategies

### Decision: Multi-Stage Hybrid Approach

Combine exact matching, fuzzy string matching, and embedding similarity for robust entity deduplication.

### Rationale

1. **High Accuracy**: Different matching techniques catch different types of duplicates (typos, variations, concept similarity).

2. **Performance**: Stages are ordered from fastest to slowest, stopping at first match.

3. **Domain Alignment**: Handles conversational variations:
   - Exact: "Order #12345" → "Order #12345"
   - Typo: "John Smith" → "Jon Smith"
   - Variation: "Customer John" → "John Smith"
   - Concept: "Product ordered" → "Item purchased"

4. **Configurable Thresholds**: Each stage has tunable confidence threshold for different tolerance levels.

### Deduplication Pipeline

#### Stage 1: Exact Match (Index Lookup) - 0ms

```python
# Check group_id + entity_type + normalized name
# Exact match if found
def exact_match_candidate(entity: Entity) -> Entity | None:
    normalized = normalize_entity_name(entity.name)
    return index.get((entity.group_id, entity.entity_type, normalized))
```

**Normalization**: Lowercase, trim whitespace, remove punctuation
- "Order #12345" → "order 12345"
- "John Smith" → "john smith"

#### Stage 2: Fuzzy String Matching (Levenshtein Distance) - 5-20ms

If no exact match, check similar names for same entity type:

```python
# Levenshtein distance on normalized names
# Match if similarity > 85%
def fuzzy_match_candidate(
    entity: Entity,
    existing_entities: list[Entity],
    threshold: float = 0.85
) -> Entity | None:
    normalized = normalize_entity_name(entity.name)
    for existing in existing_entities:
        if existing.entity_type != entity.entity_type:
            continue
        similarity = levenshtein_similarity(
            normalized,
            normalize_entity_name(existing.name)
        )
        if similarity >= threshold:
            return existing
    return None
```

**Configuration**:
```toml
[memory.entity_deduplication]
exact_match_enabled = true
fuzzy_match_enabled = true
fuzzy_threshold = 0.85  # 85% string similarity
embedding_similarity_enabled = true
embedding_threshold = 0.80  # 80% vector similarity
```

#### Stage 3: Embedding Similarity - 50-100ms

If fuzzy match fails, use entity embeddings:

```python
# Generate embedding for candidate entity name
# Search existing entities by embedding
# Match if cosine_similarity > 0.80
async def embedding_match_candidate(
    entity: Entity,
    embedding_provider: EmbeddingProvider,
    existing_entities: list[Entity],
    threshold: float = 0.80
) -> Entity | None:
    if not entity.embedding:
        embedding = await embedding_provider.embed_single(entity.name)
    else:
        embedding = entity.embedding

    for existing in existing_entities:
        if existing.entity_type != entity.entity_type:
            continue
        if not existing.embedding:
            continue
        similarity = cosine_similarity(embedding, existing.embedding)
        if similarity >= threshold:
            return existing
    return None
```

**Use Case**: "Customer John" (new) matches "john smith" (existing) because semantically similar

#### Stage 4: Rule-Based (Relationship Context) - 10-50ms

For special cases where semantic matching isn't enough:

```python
# Example: Same address + same phone = same person
# Example: Same order_id + same timestamp = same order
def rule_based_match_candidate(
    entity: Entity,
    existing_entities: list[Entity]
) -> Entity | None:
    if entity.entity_type == "person":
        # Match if email or phone matches
        for existing in existing_entities:
            if existing.entity_type != "person":
                continue
            if entity.attributes.get("email") == existing.attributes.get("email"):
                return existing
            if entity.attributes.get("phone") == existing.attributes.get("phone"):
                return existing

    if entity.entity_type == "order":
        # Match if order_id is same
        for existing in existing_entities:
            if existing.entity_type != "order":
                continue
            if entity.attributes.get("order_id") == existing.attributes.get("order_id"):
                return existing
    return None
```

### Handling Duplicates

When duplicate found:

```python
async def deduplicate_entity(
    new_entity: Entity,
    existing_entity: Entity,
    memory_store: MemoryStore
) -> Entity:
    """Merge new entity into existing."""
    # Merge attributes (new takes precedence for updated values)
    merged_attrs = existing_entity.attributes.copy()
    merged_attrs.update(new_entity.attributes)

    # Update entity with merged data
    updated = Entity(
        id=existing_entity.id,
        group_id=existing_entity.group_id,
        name=existing_entity.name,  # Keep original name
        entity_type=existing_entity.entity_type,
        attributes=merged_attrs,
        valid_from=existing_entity.valid_from,
        valid_to=None,  # Still valid
        recorded_at=existing_entity.recorded_at,
        embedding=existing_entity.embedding,  # Keep original
    )

    await memory_store.update_entity(updated)
    return updated
```

### Accuracy & Trade-offs

| Stage | Speed | Accuracy | False Positives | Use Cases |
|-------|-------|----------|-----------------|-----------|
| Exact | <1ms | 100% | 0% | Common case |
| Fuzzy | 5-20ms | 85-90% | 2-5% | Typos, minor variations |
| Embedding | 50-100ms | 80-85% | 5-10% | Synonym/concept matches |
| Rule | 10-50ms | 95%+ | <1% | Domain-specific matches |

**Target**: 95% correct deduplication on test data (matched with F1-score evaluation)

---

## 3. Temporal Graph Update Patterns

### Decision: Bi-Temporal Versioning with Immutable History

When facts change, invalidate old relationships with `valid_to` timestamp and create new relationships with `valid_from` timestamp. Never delete.

### Rationale

1. **Audit Trail**: Complete history preserved for compliance ("What did we know on 2025-11-15?")

2. **Contradiction Handling**: Can represent that an order status changed from "processing" to "delivered"

3. **Graph Consistency**: Old relationships remain for historical queries; new ones active for current queries

4. **No Data Loss**: Can recover from incorrect extractions by invalidating them rather than deleting

### Pattern

**Scenario: Address Update**

```
Conversation Turn 1:
  "My address is 123 Main St"
  → Extract: Entity(John Smith) -lives_at-> Address(123 Main St)
  → Relationship(valid_from=T1, valid_to=None)

Conversation Turn 5:
  "I moved to 456 Oak Ave"
  → Extract: Entity(John Smith) -lives_at-> Address(456 Oak Ave)
  → Before storing:
    1. Find existing: John Smith -lives_at-> Address(123 Main St)
    2. Invalidate old: Set valid_to=now() on the 123 Main St relationship
    3. Create new: John Smith -lives_at-> Address(456 Oak Ave) with valid_from=now()

Result in graph:
  ✓ John Smith -lives_at-> Address(123 Main St) [valid_from=T1, valid_to=T5]
  ✓ John Smith -lives_at-> Address(456 Oak Ave) [valid_from=T5, valid_to=None]
```

### Implementation

```python
async def update_relationship_temporal(
    from_entity_id: UUID,
    to_entity_id: UUID,
    relation_type: str,
    new_attributes: dict[str, Any],
    group_id: str,
    memory_store: MemoryStore,
) -> Relationship:
    """Update a relationship by invalidating old and creating new."""

    # Find existing active relationships
    existing = await memory_store.get_relationships(
        group_id=group_id,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_type,
    )

    # Invalidate all active relationships
    now = datetime.now(UTC)
    for rel in existing:
        if rel.valid_to is None:  # Only if currently active
            rel.valid_to = now
            await memory_store.update_relationship(rel)

    # Create new relationship with current timestamp
    new_rel = Relationship(
        group_id=group_id,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_type,
        attributes=new_attributes,
        valid_from=now,
        valid_to=None,  # Currently active
    )

    new_id = await memory_store.add_relationship(new_rel)
    return new_rel
```

### Query Patterns

**Current State** (default):
```python
# Get current relationships (active)
rels = await memory_store.get_relationships(
    group_id=group_id,
    from_entity_id=entity_id,
    relation_type="lives_at"
    # Implicitly filters: valid_to IS NULL
)
```

**Point-in-Time Query**:
```python
# What was the relationship on 2025-11-15?
query_time = datetime(2025, 11, 15, tzinfo=UTC)
rels = await memory_store.get_relationships(
    group_id=group_id,
    from_entity_id=entity_id,
    relation_type="lives_at",
    valid_as_of=query_time  # (added to interface)
    # Filters: valid_from <= query_time AND (valid_to IS NULL OR valid_to > query_time)
)
```

**History**:
```python
# Get all versions (including invalidated)
rels_all = await memory_store.get_relationships(
    group_id=group_id,
    from_entity_id=entity_id,
    relation_type="lives_at",
    include_history=True  # (added to interface)
)
```

### Duplicate Relationship Prevention

When extracting relationships, check for existing before creating:

```python
async def extract_and_store_relationships(
    from_entity: Entity,
    to_entity: Entity,
    relation_type: str,
    attributes: dict[str, Any],
    group_id: str,
    memory_store: MemoryStore,
) -> Relationship:
    """Extract relationship, handling temporal updates."""

    # Check for existing active relationship
    existing = await memory_store.get_relationships(
        group_id=group_id,
        from_entity_id=from_entity.id,
        to_entity_id=to_entity.id,
        relation_type=relation_type,
    )

    active = [r for r in existing if r.valid_to is None]

    if active:
        # Relationship exists - check if attributes changed
        active_rel = active[0]
        if active_rel.attributes == attributes:
            # No change - return existing
            return active_rel
        else:
            # Attributes changed - invalidate and create new
            return await update_relationship_temporal(
                from_entity.id, to_entity.id, relation_type,
                attributes, group_id, memory_store
            )
    else:
        # New relationship
        new_rel = Relationship(
            group_id=group_id,
            from_entity_id=from_entity.id,
            to_entity_id=to_entity.id,
            relation_type=relation_type,
            attributes=attributes,
            valid_from=datetime.now(UTC),
            valid_to=None,
        )
        await memory_store.add_relationship(new_rel)
        return new_rel
```

### Configuration

```toml
[memory.temporal_updates]
enabled = true
invalidate_on_change = true
keep_history = true
point_in_time_query_enabled = true
```

---

## 4. Async Task Patterns for Summarization

### Decision: Async Fire-and-Forget with Fallback Queue

Trigger summarization asynchronously after episode creation. Use task queue (Redis Queue or Celery) with fallback to in-process async task.

### Rationale

1. **Non-Blocking**: Episode creation completes within 500ms (no summarization latency)

2. **Reliable Retry**: Message queue persists tasks and retries on failure

3. **Observable**: Task execution logged and traced via observability layer

4. **Decoupled**: Summarization logic independent from episode ingestion

5. **Horizontal Scalability**: Separate worker pool can process summaries

### Pattern

```python
async def ingest_episode(
    episode: Episode,
    memory_store: MemoryStore,
    embedding_provider: EmbeddingProvider,
    entity_extractor: EntityExtractor,
    task_queue: TaskQueue,  # Redis or in-memory
    config: MemoryIngestionConfig,
) -> UUID:
    """Ingest episode synchronously, queue summarization asynchronously."""

    # 1. Store episode (fast)
    episode_id = await memory_store.add_episode(episode)

    # 2. Generate embedding (fast - parallel)
    if config.embedding_enabled:
        embedding = await embedding_provider.embed_single(episode.content)
        episode.embedding = embedding
        episode.embedding_model = embedding_provider.provider_name
        await memory_store.update_episode(episode)

    # 3. Extract entities (medium - can be async)
    if config.entity_extraction_enabled:
        task_queue.enqueue(
            "extract_entities",
            episode_id=episode_id,
            group_id=episode.group_id,
        )

    # 4. Check if summarization needed (fast - query count)
    episode_count = await memory_store.count_episodes(episode.group_id)
    threshold = config.summarization_turn_threshold

    if episode_count % threshold == 0 and config.summarization_enabled:
        # Queue summarization task
        task_queue.enqueue(
            "summarize_conversation",
            group_id=episode.group_id,
            turn_threshold=threshold,
        )

    return episode_id
```

### Task Queue Implementation

#### Option A: Redis Queue (Recommended for Production)

```python
from redis import Redis
from rq import Queue

class RedisTaskQueue:
    def __init__(self, redis_client: Redis):
        self.queue = Queue(connection=redis_client)

    def enqueue(
        self,
        job_type: str,
        **kwargs
    ) -> str:
        """Enqueue a task."""
        job = self.queue.enqueue(
            f"soldier.memory.tasks.{job_type}",
            **kwargs,
            job_timeout=600,  # 10 min timeout
            result_ttl=3600,  # Keep result for 1 hour
            failure_ttl=86400,  # Keep failure for 1 day
        )
        return job.id
```

**Pros**: Persistent, retries, monitoring, separate workers
**Cons**: Redis dependency, operational overhead

#### Option B: In-Process Async Queue (Development)

```python
import asyncio
from typing import Callable

class InMemoryTaskQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.tasks: dict[str, Callable] = {}

    def register(self, job_type: str, handler: Callable):
        """Register a task handler."""
        self.tasks[job_type] = handler

    def enqueue(self, job_type: str, **kwargs) -> str:
        """Enqueue a task."""
        job_id = str(uuid4())
        asyncio.create_task(
            self._run_task(job_id, job_type, kwargs)
        )
        return job_id

    async def _run_task(
        self,
        job_id: str,
        job_type: str,
        kwargs: dict
    ):
        """Run task with error handling."""
        try:
            handler = self.tasks[job_type]
            await handler(**kwargs)
        except Exception as e:
            logger.error(
                "task_failed",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
            )
```

**Pros**: Simple, no dependencies, fast for dev
**Cons**: Not persistent, no retries, in-process

### Task Handlers

```python
# soldier/memory/tasks.py

async def extract_entities(
    episode_id: UUID,
    group_id: str,
    memory_store: MemoryStore,
    entity_extractor: EntityExtractor,
) -> None:
    """Extract entities from an episode asynchronously."""
    try:
        episode = await memory_store.get_episode(group_id, episode_id)
        if not episode:
            logger.warning("episode_not_found", episode_id=episode_id)
            return

        # Extract entities and relationships
        entities, relationships = await entity_extractor.extract(
            episode.content,
            context_type=episode.source,
        )

        # Store entities and relationships (with deduplication)
        for entity in entities:
            entity.group_id = group_id
            existing = await find_duplicate_entity(entity, memory_store)
            if existing:
                # Merge and update
                await memory_store.update_entity(existing)
            else:
                await memory_store.add_entity(entity)

        for rel in relationships:
            rel.group_id = group_id
            await memory_store.add_relationship(rel)

        logger.info(
            "entities_extracted",
            episode_id=episode_id,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

    except Exception as e:
        logger.error(
            "entity_extraction_failed",
            episode_id=episode_id,
            error=str(e),
        )
        raise


async def summarize_conversation(
    group_id: str,
    turn_threshold: int,
    memory_store: MemoryStore,
    summarizer: ConversationSummarizer,
) -> None:
    """Summarize conversation after turn threshold.

    Called when episode_count % turn_threshold == 0
    """
    try:
        # Get episodes since last summary
        episodes = await memory_store.get_episodes(
            group_id,
            limit=turn_threshold + 10,  # Extra buffer
        )

        if len(episodes) < turn_threshold:
            return  # Not ready yet

        # Generate summary
        summary_text = await summarizer.summarize(episodes)

        # Store as episode
        summary_episode = Episode(
            group_id=group_id,
            content=summary_text,
            source="system",
            content_type="summary",
            occurred_at=datetime.now(UTC),
        )

        await memory_store.add_episode(summary_episode)

        logger.info(
            "conversation_summarized",
            group_id=group_id,
            summary_id=summary_episode.id,
            episode_count=len(episodes),
        )

    except Exception as e:
        logger.error(
            "summarization_failed",
            group_id=group_id,
            error=str(e),
        )
        raise
```

### Configuration

```toml
[memory.async_tasks]
enabled = true
queue_type = "redis"  # or "inmemory" for dev

[memory.async_tasks.redis]
url = "redis://localhost:6379/0"
max_retries = 3
timeout_seconds = 600

[memory.async_tasks.handlers]
entity_extraction_timeout = 120
summarization_timeout = 300
```

### Error Handling & Observability

```python
# Task execution with tracing
async def execute_task_with_trace(
    job_id: str,
    job_type: str,
    handler: Callable,
    kwargs: dict,
):
    """Execute task with observability."""
    with start_span(f"task_{job_type}") as span:
        span.set_attribute("job_id", job_id)
        span.set_attribute("job_type", job_type)

        try:
            await handler(**kwargs)
            span.set_attribute("status", "success")
        except Exception as e:
            span.set_attribute("status", "error")
            span.record_exception(e)
            logger.error(
                "task_error",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
            )
            # Re-raise for queue retry logic
            raise
```

---

## 5. Embedding Model Selection

### Decision: Sentence-Transformers (Open Source) with Optional OpenAI Fallback

Use `all-mpnet-base-v2` (sentence-transformers) as primary embedding model. Configure optional OpenAI fallback for production.

### Rationale

1. **Conversational Domain**: Sentence-Transformers fine-tuned on semantic similarity, designed for short texts and sentence-level embeddings (perfect for conversation episodes)

2. **Performance**: 100-200ms for episode batch (vs 500ms+ for API calls)

3. **Cost**: Zero API cost - runs locally or on GPU. Scales horizontally

4. **Privacy**: No external data transmission (important for sensitive conversations)

5. **Multi-Model Support**: Configured via EmbeddingProvider interface - can use different models for different content types

### Comparison Matrix

| Model | Speed | Cost | Accuracy | Multi-lingual | Best For |
|-------|-------|------|----------|---------------|----------|
| **all-mpnet-base-v2** | 100-200ms | $0 | 85-90% | No (English) | Short text, episodes |
| **OpenAI text-embedding-3-small** | 500ms + API | $0.02/1M tokens | 90-95% | Yes | High accuracy, fallback |
| **sentence-transformers/paraphrase-multilingual-mpnet-base-v2** | 150-250ms | $0 | 80-85% | Yes (98 langs) | Multi-lingual conversations |
| **Cohere embed** | 400ms + API | $0.10/1M tokens | 85-90% | Yes | High-concurrency fallback |

### Implementation Decision Tree

```
Input: Episode to embed

├─ Length > 8192 tokens?
│  └─ YES: Chunk into sentences, embed separately, average
│  └─ NO: Continue
│
├─ Multi-lingual content?
│  └─ YES: Use paraphrase-multilingual-mpnet-base-v2
│  └─ NO: Use all-mpnet-base-v2
│
├─ Embedding generation latency > 500ms?
│  └─ YES: Fallback to OpenAI embed (if configured)
│  └─ NO: Use result
│
└─ Store embedding + model name with episode
```

### Configuration

```toml
[providers.embedding.default]
provider = "sentence_transformers"
model = "all-mpnet-base-v2"
dimensions = 768
batch_size = 32
max_length = 512

# Fallback for when primary is slow/fails
[providers.embedding.fallback]
provider = "openai"
model = "text-embedding-3-small"
dimensions = 1536

# Multi-lingual alternative
[providers.embedding.multilingual]
provider = "sentence_transformers"
model = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
dimensions = 768

[memory.embedding]
enabled = true
primary_provider = "default"
fallback_enabled = true
fallback_timeout_ms = 500
batch_embedding = true
```

### Implementation Pattern

```python
class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers models."""

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self.model.get_sentence_embedding_dimension()

    async def embed(
        self,
        texts: list[str],
        **kwargs
    ) -> EmbeddingResponse:
        """Generate embeddings using sentence-transformers."""
        # Handle long texts by chunking
        embeddings = []
        for text in texts:
            if len(text.split()) > 500:
                # Chunk long texts
                chunks = self._chunk_text(text)
                chunk_embeddings = self.model.encode(
                    chunks,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                )
                # Average embeddings
                avg_embedding = chunk_embeddings.mean(dim=0).tolist()
                embeddings.append(avg_embedding)
            else:
                embedding = self.model.encode(
                    text,
                    convert_to_tensor=False,
                )
                embeddings.append(embedding.tolist())

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self._model_name,
            dimensions=self.dimensions,
            usage={"total_tokens": sum(len(t.split()) for t in texts)},
        )
```

### Fallback Chain Pattern

```python
async def embed_with_fallback(
    episode: Episode,
    primary_provider: EmbeddingProvider,
    fallback_provider: EmbeddingProvider,
    timeout_ms: int = 500,
) -> tuple[list[float], str]:
    """Embed with fallback to secondary provider."""
    try:
        # Try primary provider with timeout
        embedding = await asyncio.wait_for(
            primary_provider.embed_single(episode.content),
            timeout=timeout_ms / 1000,
        )
        return embedding, primary_provider.provider_name
    except asyncio.TimeoutError:
        logger.warning(
            "embedding_timeout",
            provider=primary_provider.provider_name,
            episode_id=episode.id,
        )
        # Fallback to secondary
        embedding = await fallback_provider.embed_single(episode.content)
        return embedding, fallback_provider.provider_name
    except Exception as e:
        logger.error(
            "embedding_failed",
            provider=primary_provider.provider_name,
            error=str(e),
        )
        # Fallback
        embedding = await fallback_provider.embed_single(episode.content)
        return embedding, fallback_provider.provider_name
```

### Accuracy Targets

- Semantic match accuracy: 85%+ (test set comparison with gold embeddings)
- Latency p95: < 200ms for typical episode (500 tokens)
- Dimensional consistency: Always 768 or 1536 (configured)

---

## 6. Summarization Strategies

### Decision: Sliding Window Abstractive Summarization with Hierarchical Rollup

Generate summaries every N turns using LLM-based abstractive summarization. Chain summaries into meta-summaries for very long conversations.

### Rationale

1. **Information Density**: Abstractive (generates new text) better than extractive (copies original) for compression

2. **Conversational Context**: LLM understands dialog flow, can extract key decisions and facts

3. **Hierarchical Approach**: Scales to arbitrarily long conversations without token explosion

4. **Configurable Windows**: Tune window size based on domain (customer support: 10 turns, voice calls: 5 turns)

5. **Async Processing**: Summarization runs after turns are stored, doesn't impact latency

### Summarization Tiers

```
Individual Turns: [Turn 1, 2, 3, ..., 50]
         ↓
Window Summaries: [Summary(1-10), Summary(11-20), Summary(21-30), Summary(31-40), Summary(41-50)]
         ↓
Meta-Summary: Summary of summaries (1-50)
         ↓
For 100 turns: Summary(51-100), then meta-summary of both meta-summaries
```

### Configuration

```toml
[memory.summarization]
enabled = true

# First tier: individual conversation windows
[memory.summarization.window]
turns_per_summary = 20  # Every 20 turns, create summary
llm_provider = "haiku"  # Fast, cheap model
max_tokens = 256
temperature = 0.5

# Second tier: meta-summaries
[memory.summarization.meta]
summaries_per_meta = 5  # Every 5 summaries, create meta-summary
enabled_at_turn_count = 100  # Start meta-summaries at 100 turns
llm_provider = "haiku"
max_tokens = 512
temperature = 0.5
```

### Implementation

```python
class ConversationSummarizer:
    """Generate hierarchical conversation summaries."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        memory_store: MemoryStore,
        config: SummarizationConfig,
    ):
        self.llm = llm_provider
        self.store = memory_store
        self.config = config

    async def summarize_window(
        self,
        episodes: list[Episode],
        group_id: str,
    ) -> Episode:
        """Summarize a window of episodes."""
        # Build window context
        context = self._format_episodes_for_summary(episodes)

        # Generate summary
        messages = [
            LLMMessage(
                role="system",
                content="""You are a concise summarizer of customer conversations.
Extract the key information: what the customer wanted, what happened,
and what was resolved. Be brief (1-2 paragraphs max).""",
            ),
            LLMMessage(
                role="user",
                content=f"Summarize this conversation:\n\n{context}",
            ),
        ]

        response = await self.llm.generate(
            messages,
            model=self.config.window.llm_provider,
            max_tokens=self.config.window.max_tokens,
            temperature=self.config.window.temperature,
        )

        # Store as summary episode
        summary_episode = Episode(
            group_id=group_id,
            content=response.content,
            source="system",
            content_type="summary",
            occurred_at=episodes[-1].occurred_at,  # Use last turn time
            source_metadata={
                "summary_type": "window",
                "episodes_covered": len(episodes),
                "episode_ids": [str(e.id) for e in episodes],
            },
        )

        return summary_episode

    async def check_and_summarize_if_needed(
        self,
        group_id: str,
    ) -> Episode | None:
        """Check if summarization threshold reached, summarize if needed."""
        # Count total episodes (including existing summaries)
        episodes = await self.store.get_episodes(group_id)
        turn_count = len([e for e in episodes if e.content_type == "message"])

        if turn_count % self.config.window.turns_per_summary != 0:
            return None  # Not time to summarize

        # Get unsummarized episodes
        recent = await self.store.get_episodes(
            group_id,
            limit=self.config.window.turns_per_summary + 5,
        )

        # Exclude recent summaries from summarization
        to_summarize = [
            e for e in recent
            if e.content_type in ("message", "event")
        ]

        if len(to_summarize) < self.config.window.turns_per_summary:
            return None

        # Generate summary
        summary = await self.summarize_window(
            to_summarize[-self.config.window.turns_per_summary:],
            group_id,
        )

        # Store summary
        summary.id = await self.store.add_episode(summary)

        # Check if meta-summary needed
        summary_count = len([
            e for e in episodes
            if e.content_type == "summary"
        ])

        if (turn_count > self.config.meta.enabled_at_turn_count and
            summary_count % self.config.meta.summaries_per_meta == 0):
            # Generate meta-summary
            meta = await self.create_meta_summary(group_id)
            if meta:
                meta.id = await self.store.add_episode(meta)
                return meta

        return summary

    async def create_meta_summary(
        self,
        group_id: str,
    ) -> Episode | None:
        """Create summary of summaries."""
        # Get all window summaries
        episodes = await self.store.get_episodes(group_id)
        summaries = [
            e for e in episodes
            if e.content_type == "summary"
        ]

        if len(summaries) < 2:
            return None

        # Get most recent N summaries
        summaries_to_meta = summaries[-self.config.meta.summaries_per_meta:]
        context = self._format_episodes_for_summary(summaries_to_meta)

        # Generate meta-summary
        messages = [
            LLMMessage(
                role="system",
                content="""You are summarizing previously generated conversation
summaries into a high-level overview. Focus on major themes and outcomes.""",
            ),
            LLMMessage(
                role="user",
                content=f"Create a meta-summary from these summaries:\n\n{context}",
            ),
        ]

        response = await self.llm.generate(
            messages,
            model=self.config.meta.llm_provider,
            max_tokens=self.config.meta.max_tokens,
            temperature=self.config.meta.temperature,
        )

        meta_episode = Episode(
            group_id=group_id,
            content=response.content,
            source="system",
            content_type="meta_summary",
            occurred_at=summaries_to_meta[-1].occurred_at,
            source_metadata={
                "summary_type": "meta",
                "summaries_covered": len(summaries_to_meta),
                "summary_ids": [str(s.id) for s in summaries_to_meta],
            },
        )

        return meta_episode

    def _format_episodes_for_summary(self, episodes: list[Episode]) -> str:
        """Format episodes for LLM consumption."""
        lines = []
        for episode in episodes:
            if episode.source == "user":
                lines.append(f"Customer: {episode.content}")
            elif episode.source == "agent":
                lines.append(f"Agent: {episode.content}")
            elif episode.source == "system":
                lines.append(f"[System: {episode.content}]")
        return "\n".join(lines)
```

### Retrieval Preference

When retrieving context, prefer summaries for old turns:

```python
async def retrieve_contextual_episodes(
    group_id: str,
    query_embedding: list[float],
    memory_store: MemoryStore,
    config: SummarizationConfig,
) -> list[Episode]:
    """Retrieve episodes, preferring summaries for old turns."""

    # Get all episodes
    all_episodes = await memory_store.get_episodes(group_id)

    # Split into recent (raw episodes) and old (use summaries if available)
    recent = all_episodes[-config.window.turns_per_summary:]  # Last N turns

    # For older turns, prefer summaries
    old = all_episodes[:-config.window.turns_per_summary]
    summaries = [e for e in old if e.content_type in ("summary", "meta_summary")]
    raw = [e for e in old if e.content_type in ("message", "event") and e not in summaries]

    # Combine: recent raw + old summaries + old raw (fallback)
    to_search = recent + summaries + raw[:20]

    # Vector search
    results = await memory_store.vector_search_episodes(
        query_embedding,
        group_id,
        limit=10,
    )

    return results
```

### Window Size Tuning

Different domains benefit from different window sizes:

```toml
# Customer support: shorter windows (more detail)
[agents.customer_support.memory.summarization.window]
turns_per_summary = 10
llm_provider = "haiku"

# Sales calls: medium windows
[agents.sales.memory.summarization.window]
turns_per_summary = 20
llm_provider = "haiku"

# Long-form interviews: larger windows (compression)
[agents.interview.memory.summarization.window]
turns_per_summary = 50
llm_provider = "haiku"
```

### Quality Metrics

- **Summary retention**: 80%+ of key facts preserved in summary
- **Compression ratio**: 70%+ reduction in token count
- **Retrieval accuracy**: Summaries rank in top-5 for relevant queries
- **Processing time**: < 2s per window summary (Haiku API)

---

## Summary Table

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **Entity Extraction** | LLM with structured output (Claude/Haiku) | Conversational understanding, domain flexibility, provider consistency |
| **Entity Deduplication** | Multi-stage hybrid (exact → fuzzy → embedding → rule) | High accuracy, staged performance, handles typos and synonyms |
| **Temporal Updates** | Bi-temporal versioning (valid_from/valid_to) | Audit trail, contradiction handling, no data loss |
| **Async Tasks** | Redis Queue with fallback to in-process | Non-blocking, reliable, scalable, observable |
| **Embeddings** | Sentence-Transformers (open source) with OpenAI fallback | Fast, local, cost-effective, conversational domain expertise |
| **Summarization** | Hierarchical abstractive (LLM-based windows + meta) | Information density, scales to long conversations, configurable |

---

## Integration Points

All components integrate via existing Soldier abstractions:

- **LLMProvider**: For entity extraction, summarization
- **EmbeddingProvider**: For embeddings, deduplication similarity
- **MemoryStore**: For storage with temporal support
- **Configuration**: TOML-driven, configurable per agent
- **Observability**: Structured logging, OpenTelemetry spans, metrics
- **Error Handling**: Graceful degradation, no blocking failures

This design ensures the Memory Ingestion System fits naturally into the Soldier ecosystem while following the architectural principles of API-first, provider-based, configuration-driven processing.
