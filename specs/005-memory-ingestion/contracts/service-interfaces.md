# Service Interfaces: Memory Ingestion System

**Feature**: 005-memory-ingestion
**Date**: 2025-11-28
**Type**: Internal Service Contracts

## Overview

This document defines the Python service interfaces (contracts) for the Memory Ingestion System. These are internal interfaces used by the alignment engine, not external HTTP APIs.

---

## MemoryIngestor Interface

**Module**: `focal.memory.ingestion.ingestor`
**Purpose**: Main orchestrator for episode creation and async task dispatching

### Methods

#### `ingest_turn`

```python
async def ingest_turn(
    self,
    turn: Turn,
    session: Session
) -> Episode:
    """
    Ingest a conversation turn into memory.

    Synchronous operations (<500ms):
    - Create Episode model from turn
    - Generate embedding via EmbeddingProvider
    - Store episode in MemoryStore
    - Queue async extraction tasks

    Asynchronous operations (queued):
    - Extract entities and relationships
    - Check if summarization threshold reached

    Args:
        turn: Conversation turn with user message and agent response
        session: Current session context (for group_id)

    Returns:
        Episode: Stored episode with generated embedding

    Raises:
        IngestionError: If episode creation or storage fails
        EmbeddingError: If embedding generation fails (will use fallback)
    """
```

**Contract**:
- MUST complete in <500ms (p95)
- MUST store episode even if embedding fails (graceful degradation)
- MUST NOT block on entity extraction (async only)
- MUST bind `group_id` as `{session.tenant_id}:{session.id}`

---

#### `ingest_event`

```python
async def ingest_event(
    self,
    event_type: str,
    content: str,
    group_id: str,
    metadata: dict[str, Any] | None = None
) -> Episode:
    """
    Ingest a system event into memory.

    Similar to ingest_turn but for non-conversation events
    (e.g., tool execution, scenario transitions, errors).

    Args:
        event_type: Type of event (for source_metadata)
        content: Event description
        group_id: Tenant:session identifier
        metadata: Optional additional context

    Returns:
        Episode: Stored episode

    Raises:
        IngestionError: If episode creation or storage fails
    """
```

**Contract**:
- MUST complete in <500ms
- Events get `source="system"` and `content_type="event"`
- Entity extraction is OPTIONAL for events (configurable)

---

## EntityExtractor Interface

**Module**: `focal.memory.ingestion.entity_extractor`
**Purpose**: Extract entities and relationships from episode content using LLM

### Methods

#### `extract`

```python
async def extract(
    self,
    episode: Episode
) -> EntityExtractionResult:
    """
    Extract entities and relationships from episode content.

    Uses LLMProvider with structured output to identify:
    - Named entities (people, products, orders, issues, concepts)
    - Relationships between those entities
    - Confidence scores for each extraction

    Args:
        episode: Episode to extract from

    Returns:
        EntityExtractionResult: Contains lists of ExtractedEntity
        and ExtractedRelationship objects

    Raises:
        ExtractionError: If LLM call fails or returns invalid structure
        TimeoutError: If extraction exceeds configured timeout
    """
```

**Contract**:
- MUST use configured LLMProvider (from `config.entity_extraction.llm_provider`)
- MUST return structured output (Pydantic model validation)
- MUST filter by `min_confidence` from config
- SHOULD complete in <2s (p95)
- MUST handle LLM provider failures gracefully (return empty result, log error)

---

#### `extract_batch`

```python
async def extract_batch(
    self,
    episodes: list[Episode]
) -> list[EntityExtractionResult]:
    """
    Extract from multiple episodes in parallel.

    More efficient than sequential extraction when processing
    backlog or batch ingestion.

    Args:
        episodes: List of episodes to extract from

    Returns:
        List of EntityExtractionResult in same order as input

    Raises:
        ExtractionError: If batch processing fails
    """
```

**Contract**:
- MUST process in parallel (up to `config.entity_extraction.batch_size`)
- MUST maintain order (result[i] corresponds to episodes[i])
- MUST continue on individual failures (partial success allowed)

---

## EntityDeduplicator Interface

**Module**: `focal.memory.ingestion.entity_extractor` (helper class)
**Purpose**: Find and merge duplicate entities

### Methods

#### `find_duplicate`

```python
async def find_duplicate(
    self,
    entity: Entity,
    group_id: str
) -> Entity | None:
    """
    Find duplicate entity using multi-stage matching pipeline.

    Stages (stops at first match):
    1. Exact match on normalized name
    2. Fuzzy string matching (Levenshtein)
    3. Embedding similarity (cosine)
    4. Rule-based domain-specific matching

    Args:
        entity: Candidate entity to check
        group_id: Scope for searching existing entities

    Returns:
        Entity: Existing duplicate if found, None otherwise
    """
```

**Contract**:
- MUST search only within `group_id` (tenant isolation)
- MUST try stages in order, stopping at first match
- MUST respect config flags (e.g., `fuzzy_match_enabled`)
- SHOULD complete in <100ms (p95)

---

#### `merge_entities`

```python
async def merge_entities(
    self,
    existing: Entity,
    new: Entity
) -> Entity:
    """
    Merge new entity data into existing entity.

    Combines attributes (new takes precedence for conflicts),
    preserves temporal timestamps.

    Args:
        existing: Entity already in MemoryStore
        new: Newly extracted entity with updated data

    Returns:
        Entity: Merged entity (NOT automatically persisted)
    """
```

**Contract**:
- MUST preserve `existing.id` and `existing.valid_from`
- MUST merge `attributes` (new overwrites existing keys)
- MUST NOT automatically persist (caller's responsibility)

---

## ConversationSummarizer Interface

**Module**: `focal.memory.ingestion.summarizer`
**Purpose**: Generate hierarchical conversation summaries

### Methods

#### `summarize_window`

```python
async def summarize_window(
    self,
    episodes: list[Episode],
    group_id: str
) -> Episode:
    """
    Create summary of conversation window.

    Uses LLM to generate concise summary of N turns.
    Summary is returned as Episode with content_type="summary".

    Args:
        episodes: Window of episodes to summarize (typically 10-50)
        group_id: Tenant:session for the summary

    Returns:
        Episode: Summary episode (NOT persisted, caller stores it)

    Raises:
        SummarizationError: If LLM call fails
    """
```

**Contract**:
- MUST use configured LLM model (`config.summarization.window.llm_provider`)
- MUST set `content_type="summary"` and `source="system"`
- MUST include metadata: `{"summary_type": "window", "episodes_covered": N, "episode_ids": [...]}`
- SHOULD complete in <2s (p95)
- Summary length SHOULD be 30-50% of original episode content

---

#### `create_meta_summary`

```python
async def create_meta_summary(
    self,
    summaries: list[Episode],
    group_id: str
) -> Episode:
    """
    Create meta-summary (summary of summaries).

    For very long conversations, combines multiple window
    summaries into higher-level overview.

    Args:
        summaries: Window summaries to combine (typically 5-10)
        group_id: Tenant:session for the meta-summary

    Returns:
        Episode: Meta-summary episode (NOT persisted)

    Raises:
        SummarizationError: If LLM call fails
    """
```

**Contract**:
- MUST set `content_type="meta_summary"` and `source="system"`
- MUST include metadata: `{"summary_type": "meta", "summaries_covered": N, "summary_ids": [...]}`
- Meta-summary length SHOULD be 50-70% of combined summary length

---

#### `check_and_summarize_if_needed`

```python
async def check_and_summarize_if_needed(
    self,
    group_id: str
) -> Episode | None:
    """
    Check if summarization threshold reached and summarize if needed.

    Queries MemoryStore to count episodes, compares against thresholds,
    and triggers window or meta-summary generation.

    Args:
        group_id: Tenant:session to check

    Returns:
        Episode: Created summary if threshold was reached, None otherwise
        (Summary is automatically persisted by this method)

    Raises:
        SummarizationError: If summary generation or storage fails
    """
```

**Contract**:
- MUST query MemoryStore for episode count
- MUST check both window threshold (`turns_per_summary`) and meta threshold
- MUST persist summary before returning (unlike other methods)
- MUST handle case where no summarization needed (return None)

---

## Configuration Interfaces

### MemoryIngestionConfig

**Module**: `focal.config.models.pipeline`

```python
class MemoryIngestionConfig(BaseModel):
    """Configuration for memory ingestion system."""

    enabled: bool = True
    embedding_enabled: bool = True
    entity_extraction_enabled: bool = True
    summarization_enabled: bool = True
    async_extraction: bool = True
    async_summarization: bool = True
    queue_backend: Literal["redis", "inmemory"] = "inmemory"
    max_ingestion_latency_ms: int = 500

    entity_extraction: EntityExtractionConfig
    deduplication: EntityDeduplicationConfig
    summarization: SummarizationConfig
```

---

### EntityExtractionConfig

```python
class EntityExtractionConfig(BaseModel):
    """Configuration for entity extraction."""

    enabled: bool = True
    llm_provider: str = "anthropic"
    model: str = "haiku"
    max_tokens: int = 1024
    temperature: float = 0.3
    batch_size: int = 10
    timeout_ms: int = 2000
    min_confidence: Literal["high", "medium", "low"] = "medium"
```

---

### EntityDeduplicationConfig

```python
class EntityDeduplicationConfig(BaseModel):
    """Configuration for entity deduplication."""

    exact_match_enabled: bool = True
    fuzzy_match_enabled: bool = True
    fuzzy_threshold: float = 0.85
    embedding_match_enabled: bool = True
    embedding_threshold: float = 0.80
    rule_based_enabled: bool = True
```

---

### SummarizationConfig

```python
class SummarizationConfig(BaseModel):
    """Configuration for conversation summarization."""

    enabled: bool = True

    class WindowConfig(BaseModel):
        turns_per_summary: int = 20
        llm_provider: str = "anthropic"
        model: str = "haiku"
        max_tokens: int = 256
        temperature: float = 0.5

    class MetaConfig(BaseModel):
        summaries_per_meta: int = 5
        enabled_at_turn_count: int = 100
        llm_provider: str = "anthropic"
        model: str = "haiku"
        max_tokens: int = 512
        temperature: float = 0.5

    window: WindowConfig = Field(default_factory=WindowConfig)
    meta: MetaConfig = Field(default_factory=MetaConfig)
```

---

## Error Handling Contracts

### IngestionError

```python
class IngestionError(Exception):
    """Raised when episode ingestion fails."""

    def __init__(
        self,
        message: str,
        episode_id: UUID | None = None,
        group_id: str | None = None,
        cause: Exception | None = None
    ):
        self.episode_id = episode_id
        self.group_id = group_id
        self.cause = cause
        super().__init__(message)
```

**Usage**: Raised by `MemoryIngestor` when critical failure occurs

---

### ExtractionError

```python
class ExtractionError(Exception):
    """Raised when entity/relationship extraction fails."""

    def __init__(
        self,
        message: str,
        episode_id: UUID | None = None,
        provider_error: str | None = None,
        cause: Exception | None = None
    ):
        self.episode_id = episode_id
        self.provider_error = provider_error
        self.cause = cause
        super().__init__(message)
```

**Usage**: Raised by `EntityExtractor` when LLM call fails

---

### SummarizationError

```python
class SummarizationError(Exception):
    """Raised when summarization fails."""

    def __init__(
        self,
        message: str,
        group_id: str | None = None,
        summary_type: Literal["window", "meta"] | None = None,
        cause: Exception | None = None
    ):
        self.group_id = group_id
        self.summary_type = summary_type
        self.cause = cause
        super().__init__(message)
```

**Usage**: Raised by `ConversationSummarizer` when summary generation fails

---

## Observability Contracts

### Structured Logging

All components MUST log key events with structured fields:

**MemoryIngestor**:
```python
logger.info(
    "episode_created",
    episode_id=episode.id,
    group_id=episode.group_id,
    content_type=episode.content_type,
    embedding_model=episode.embedding_model,
    latency_ms=duration_ms,
)

logger.error(
    "ingestion_failed",
    group_id=group_id,
    error=str(e),
    cause=type(e).__name__,
)
```

**EntityExtractor**:
```python
logger.info(
    "entities_extracted",
    episode_id=episode.id,
    entity_count=len(result.entities),
    relationship_count=len(result.relationships),
    latency_ms=duration_ms,
)

logger.warning(
    "extraction_timeout",
    episode_id=episode.id,
    timeout_ms=config.timeout_ms,
)
```

**ConversationSummarizer**:
```python
logger.info(
    "summary_created",
    group_id=group_id,
    summary_type="window",
    episodes_covered=len(episodes),
    summary_id=summary.id,
    compression_ratio=compression,
)
```

---

### OpenTelemetry Spans

All async operations MUST create spans:

```python
with start_span("memory.ingest_turn") as span:
    span.set_attribute("group_id", session.group_id)
    span.set_attribute("embedding_enabled", config.embedding_enabled)

    episode = await self._create_episode(turn, session)
    span.set_attribute("episode_id", str(episode.id))

    # ... ingestion logic

    span.set_attribute("latency_ms", duration_ms)
    span.set_status(Status(StatusCode.OK))
```

**Required span names**:
- `memory.ingest_turn`
- `memory.extract_entities`
- `memory.deduplicate_entity`
- `memory.summarize_window`
- `memory.summarize_meta`

---

### Prometheus Metrics

All components MUST increment counters and record histograms:

```python
# Counters
EPISODES_CREATED.labels(content_type="message", source="user").inc()
ENTITIES_EXTRACTED.labels(entity_type="person").inc()
SUMMARIES_CREATED.labels(summary_type="window").inc()

# Histograms
INGESTION_LATENCY.labels(operation="episode_create").observe(duration_ms)
EXTRACTION_LATENCY.labels(operation="entity_extract").observe(duration_ms)

# Gauges
ACTIVE_SESSIONS.set(count)
```

**Required metrics**:
- `focal_episodes_created_total{content_type, source}`
- `focal_entities_extracted_total{entity_type}`
- `focal_relationships_created_total{relation_type}`
- `focal_summaries_created_total{summary_type}`
- `focal_ingestion_latency_milliseconds{operation}`
- `focal_extraction_latency_milliseconds{operation}`
- `focal_deduplication_matches_total{stage}` (exact, fuzzy, embedding, rule)

---

## Testing Contracts

### Unit Test Requirements

Each service MUST have unit tests covering:

1. **MemoryIngestor**:
   - Episode creation from turn
   - Embedding generation and fallback
   - Async task queuing
   - Error handling (storage failure, embedding failure)

2. **EntityExtractor**:
   - LLM structured output parsing
   - Confidence filtering
   - Batch extraction
   - LLM provider timeout/error handling

3. **EntityDeduplicator**:
   - Each deduplication stage independently
   - Multi-stage pipeline (early exit)
   - Entity merging logic

4. **ConversationSummarizer**:
   - Window summarization
   - Meta-summarization
   - Threshold checking logic
   - Summary storage

### Integration Test Requirements

Integration tests MUST verify:

1. **End-to-End Ingestion**:
   - Turn → Episode → Entities → Relationships → Summary
   - Verify all components work together
   - Use mock LLM/Embedding providers for deterministic results

2. **Temporal Updates**:
   - Relationship invalidation (valid_to setting)
   - New relationship creation (valid_from setting)
   - Point-in-time queries

3. **Deduplication Accuracy**:
   - Known duplicate entities correctly merged
   - Non-duplicates remain separate
   - Measure precision/recall on test dataset

4. **Summarization Quality**:
   - Summaries contain key facts from episodes
   - Compression ratio meets target (70%+)
   - Meta-summaries cover all window summaries

---

## Performance Contracts

### Latency Targets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Episode creation | 200ms | 500ms | 800ms |
| Entity extraction | 1s | 2s | 3s |
| Entity deduplication | 50ms | 100ms | 200ms |
| Window summarization | 1s | 2s | 4s |
| Meta-summarization | 2s | 4s | 6s |

### Throughput Targets

- **Episode ingestion**: 100 episodes/second per instance
- **Entity extraction**: 50 episodes/second (async workers)
- **Summarization**: 20 summaries/second (async workers)

### Resource Constraints

- **Memory**: <100MB per 1000 episodes (excluding embeddings)
- **CPU**: <10% utilization during steady-state ingestion
- **Storage**: Vector index size <50% of episode data size

---

## Backward Compatibility

### Breaking Changes

None - This is a new feature, no existing APIs affected.

### Deprecations

None.

### Migration Path

N/A - New feature.

---

## Security Contracts

### Tenant Isolation

ALL methods MUST:
- Filter by `group_id` when querying MemoryStore
- Never return data from different `group_id`
- Validate `group_id` format: `{tenant_id}:{session_id}`

### Data Validation

ALL inputs MUST:
- Validate required fields are present
- Sanitize user content before LLM extraction (no prompt injection)
- Validate UUIDs before database queries
- Reject malformed embeddings (wrong dimensions, NaN values)

### Error Messages

MUST NOT expose:
- Internal implementation details
- Other tenant's data
- LLM provider API keys or credentials
- Database connection strings

MUST include:
- Error type (for client retry logic)
- Request ID (for support debugging)
- Safe error message (for user display)
