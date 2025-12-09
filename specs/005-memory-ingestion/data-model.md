# Data Model: Memory Ingestion System

**Feature**: 005-memory-ingestion
**Date**: 2025-11-28

## Overview

This document defines the data models and their relationships for the Memory Ingestion System. These models extend the existing Episode, Entity, and Relationship models defined in the domain model.

---

## Core Models

### Episode (Existing - Extended)

**Purpose**: Atomic unit of memory representing a conversation turn, system event, or summary.

**Fields**:
- `id`: UUID - Unique identifier
- `group_id`: string - Composite key for tenant/session isolation (`{tenant_id}:{session_id}`)
- `content`: string - Memory content (message, event text, or summary)
- `content_type`: string - Type: "message", "event", "summary", "meta_summary"
- `source`: string - Origin: "user", "agent", "system", "external"
- `source_metadata`: dict - Additional context (e.g., summary metadata)
- `occurred_at`: datetime - When the event happened in real world
- `recorded_at`: datetime - When Focal learned about it (ingestion time)
- `embedding`: list[float] | None - Semantic vector representation
- `embedding_model`: string | None - Model that generated the embedding
- `entity_ids`: list[UUID] - References to extracted entities

**Validations**:
- `group_id` must follow pattern `{uuid}:{uuid}`
- `content` must not be empty
- `content_type` must be one of: "message", "event", "summary", "meta_summary"
- `source` must be one of: "user", "agent", "system", "external"
- `embedding` dimensions must match `embedding_model` specification (768 or 1536)

**Indexes**:
- Primary: `id`
- Query: `group_id` + `recorded_at` (for chronological retrieval)
- Vector: `embedding` (for semantic search)
- Content type: `group_id` + `content_type` (for summary queries)

---

### Entity (Existing - Extended)

**Purpose**: Named thing extracted from episodes (person, product, order, issue, concept).

**Fields**:
- `id`: UUID - Unique identifier
- `group_id`: string - Tenant/session isolation
- `name`: string - Entity name (as mentioned in conversation)
- `entity_type`: string - Classification: "person", "product", "order", "issue", "concept", "other"
- `attributes`: dict[string, any] - Key-value metadata (e.g., `{"email": "...", "status": "..."}`)
- `valid_from`: datetime - When this entity became valid in real world
- `valid_to`: datetime | None - When it stopped being valid (None = still valid)
- `recorded_at`: datetime - When Focal extracted this entity
- `embedding`: list[float] | None - Semantic vector for deduplication
- `confidence`: string | None - Extraction confidence: "high", "medium", "low"

**Validations**:
- `name` must not be empty
- `entity_type` must be one of predefined types
- `valid_from` must be <= `valid_to` (if set)
- `recorded_at` must be >= `valid_from`

**Indexes**:
- Primary: `id`
- Uniqueness: `group_id` + normalized(`name`) + `entity_type` (for exact match deduplication)
- Temporal: `group_id` + `valid_from` + `valid_to` (for point-in-time queries)
- Vector: `embedding` (for similarity deduplication)

**State Transitions**:
```
[Created] → valid_from=now, valid_to=None
    ↓
[Updated] → attributes merged, timestamps preserved
    ↓
[Invalidated] → valid_to=now (for temporal updates)
```

---

### Relationship (Existing - Extended)

**Purpose**: Directed edge between two entities representing their connection.

**Fields**:
- `id`: UUID - Unique identifier
- `group_id`: string - Tenant/session isolation
- `from_entity_id`: UUID - Source entity reference
- `to_entity_id`: UUID - Target entity reference
- `relation_type`: string - Type of relationship (e.g., "ordered", "contains", "has_issue", "lives_at")
- `attributes`: dict[string, any] - Optional relationship metadata
- `valid_from`: datetime - When this relationship became valid
- `valid_to`: datetime | None - When it stopped being valid (None = still valid)
- `recorded_at`: datetime - When Focal extracted this relationship
- `confidence`: string | None - Extraction confidence: "high", "medium", "low"

**Validations**:
- `from_entity_id` and `to_entity_id` must reference existing entities
- `relation_type` must not be empty
- `valid_from` must be <= `valid_to` (if set)
- Cannot create self-referencing relationship (`from_entity_id` == `to_entity_id`)

**Indexes**:
- Primary: `id`
- Navigation: `group_id` + `from_entity_id` + `relation_type` (for graph traversal)
- Reverse navigation: `group_id` + `to_entity_id` + `relation_type`
- Temporal: `group_id` + `valid_from` + `valid_to` (for point-in-time queries)

**State Transitions**:
```
[Created] → valid_from=now, valid_to=None, confidence=high
    ↓
[Updated] → Old relationship invalidated (valid_to=now), new one created
    ↓
[Queried] → Active relationships have valid_to=None
```

---

## Ingestion Service Models

### MemoryIngestorConfig

**Purpose**: Configuration for the memory ingestion orchestrator.

**Fields**:
- `enabled`: bool - Master switch for ingestion system
- `embedding_enabled`: bool - Generate embeddings during ingestion
- `entity_extraction_enabled`: bool - Extract entities asynchronously
- `summarization_enabled`: bool - Trigger summarization at thresholds
- `async_extraction`: bool - Run extraction in background tasks
- `async_summarization`: bool - Run summarization in background tasks
- `queue_backend`: string - "redis" or "inmemory"
- `max_ingestion_latency_ms`: int - Target latency for episode creation (500ms)

**Defaults**:
```toml
enabled = true
embedding_enabled = true
entity_extraction_enabled = true
summarization_enabled = true
async_extraction = true
async_summarization = true
queue_backend = "inmemory"
max_ingestion_latency_ms = 500
```

---

### EntityExtractionConfig

**Purpose**: Configuration for LLM-based entity and relationship extraction.

**Fields**:
- `enabled`: bool - Enable entity extraction
- `llm_provider`: string - Provider name (e.g., "anthropic", "openai")
- `model`: string - Model to use (e.g., "haiku", "gpt-4")
- `max_tokens`: int - Maximum tokens for extraction response
- `temperature`: float - LLM temperature (0.3 for consistent extraction)
- `batch_size`: int - Number of episodes to extract in parallel
- `timeout_ms`: int - Timeout for extraction operation
- `min_confidence`: string - Minimum confidence to keep ("medium" or "high")

**Defaults**:
```toml
enabled = true
llm_provider = "anthropic"
model = "haiku"
max_tokens = 1024
temperature = 0.3
batch_size = 10
timeout_ms = 2000
min_confidence = "medium"
```

---

### EntityDeduplicationConfig

**Purpose**: Configuration for multi-stage entity deduplication.

**Fields**:
- `exact_match_enabled`: bool - Stage 1: Exact normalized name match
- `fuzzy_match_enabled`: bool - Stage 2: Levenshtein similarity
- `fuzzy_threshold`: float - Similarity threshold for fuzzy match (0.85)
- `embedding_match_enabled`: bool - Stage 3: Vector similarity
- `embedding_threshold`: float - Cosine similarity threshold (0.80)
- `rule_based_enabled`: bool - Stage 4: Domain-specific rules

**Defaults**:
```toml
exact_match_enabled = true
fuzzy_match_enabled = true
fuzzy_threshold = 0.85
embedding_match_enabled = true
embedding_threshold = 0.80
rule_based_enabled = true
```

---

### SummarizationConfig

**Purpose**: Configuration for hierarchical conversation summarization.

**Fields**:

**Window Configuration**:
- `turns_per_summary`: int - Number of turns before creating window summary (20)
- `llm_provider`: string - Provider for summarization
- `model`: string - Model to use
- `max_tokens`: int - Maximum tokens for summary (256)
- `temperature`: float - LLM temperature (0.5)

**Meta-Summary Configuration**:
- `summaries_per_meta`: int - Number of summaries before meta-summary (5)
- `enabled_at_turn_count`: int - Start meta-summaries at N turns (100)
- `meta_max_tokens`: int - Maximum tokens for meta-summary (512)

**Defaults**:
```toml
[memory.summarization.window]
turns_per_summary = 20
llm_provider = "anthropic"
model = "haiku"
max_tokens = 256
temperature = 0.5

[memory.summarization.meta]
summaries_per_meta = 5
enabled_at_turn_count = 100
meta_max_tokens = 512
```

---

## Structured Output Models

### ExtractedEntity

**Purpose**: Pydantic model for LLM structured output during entity extraction.

**Fields**:
- `name`: string - Entity name as mentioned in text
- `type`: string - Entity type classification
- `attributes`: dict[string, string] - Extracted key-value attributes
- `confidence`: string - Extraction confidence ("high", "medium", "low")

**Example**:
```json
{
  "name": "Order #12345",
  "type": "order",
  "attributes": {
    "order_id": "12345",
    "status": "processing"
  },
  "confidence": "high"
}
```

---

### ExtractedRelationship

**Purpose**: Pydantic model for LLM structured output during relationship extraction.

**Fields**:
- `from_name`: string - Source entity name (matches ExtractedEntity.name)
- `to_name`: string - Target entity name
- `relation_type`: string - Relationship type (e.g., "ordered", "contains")
- `attributes`: dict[string, string] - Optional relationship metadata
- `confidence`: string - Extraction confidence

**Example**:
```json
{
  "from_name": "Customer John",
  "to_name": "Order #12345",
  "relation_type": "placed",
  "attributes": {},
  "confidence": "high"
}
```

---

### EntityExtractionResult

**Purpose**: Complete extraction result from LLM containing all entities and relationships.

**Fields**:
- `entities`: list[ExtractedEntity] - All extracted entities
- `relationships`: list[ExtractedRelationship] - All extracted relationships

**Example**:
```json
{
  "entities": [
    {"name": "Customer John", "type": "person", "attributes": {}, "confidence": "high"},
    {"name": "Order #12345", "type": "order", "attributes": {"order_id": "12345"}, "confidence": "high"},
    {"name": "Laptop", "type": "product", "attributes": {}, "confidence": "high"}
  ],
  "relationships": [
    {"from_name": "Customer John", "to_name": "Order #12345", "relation_type": "placed", "confidence": "high"},
    {"from_name": "Order #12345", "to_name": "Laptop", "relation_type": "contains", "confidence": "high"}
  ]
}
```

---

## Service Interfaces

### MemoryIngestor

**Purpose**: Orchestrates episode creation, embedding generation, and async tasks.

**Methods**:

```python
async def ingest_turn(
    turn: Turn,
    session: Session
) -> Episode:
    """
    Create episode from conversation turn.

    Synchronous operations (<500ms):
    - Create Episode model
    - Generate embedding
    - Store in MemoryStore

    Asynchronous operations (queued):
    - Extract entities and relationships
    - Check summarization threshold

    Returns: Stored episode with embedding
    """

async def ingest_event(
    event: SystemEvent,
    group_id: str
) -> Episode:
    """
    Create episode from system event.
    Similar to ingest_turn but for non-conversation events.
    """
```

---

### EntityExtractor

**Purpose**: Extract entities and relationships from episode content using LLM.

**Methods**:

```python
async def extract(
    episode: Episode
) -> EntityExtractionResult:
    """
    Extract entities and relationships from episode content.

    Uses LLM with structured output to identify:
    - Named entities (people, products, orders, concepts)
    - Relationships between entities
    - Confidence scores

    Returns: EntityExtractionResult with all extracted data
    Raises: ExtractionError if LLM call fails
    """

async def extract_batch(
    episodes: list[Episode]
) -> list[EntityExtractionResult]:
    """
    Extract from multiple episodes in parallel.
    More efficient than sequential extraction.
    """
```

---

### EntityDeduplicator

**Purpose**: Find and merge duplicate entities using multi-stage matching.

**Methods**:

```python
async def find_duplicate(
    entity: Entity,
    group_id: str
) -> Entity | None:
    """
    Find duplicate entity using multi-stage pipeline.

    Stages (in order, stops at first match):
    1. Exact match (normalized name)
    2. Fuzzy string matching (Levenshtein)
    3. Embedding similarity (cosine)
    4. Rule-based (domain-specific)

    Returns: Existing entity if duplicate found, None otherwise
    """

async def merge_entities(
    existing: Entity,
    new: Entity
) -> Entity:
    """
    Merge new entity data into existing entity.
    Combines attributes, preserves timestamps.
    """
```

---

### ConversationSummarizer

**Purpose**: Generate hierarchical summaries of conversation windows.

**Methods**:

```python
async def summarize_window(
    episodes: list[Episode],
    group_id: str
) -> Episode:
    """
    Create summary of conversation window.

    Uses LLM to generate concise summary of N turns.
    Returns summary as Episode with content_type="summary".
    """

async def create_meta_summary(
    summaries: list[Episode],
    group_id: str
) -> Episode:
    """
    Create meta-summary (summary of summaries).

    For very long conversations, combines multiple
    window summaries into higher-level overview.
    """

async def check_and_summarize_if_needed(
    group_id: str
) -> Episode | None:
    """
    Check if summarization threshold reached.
    Automatically triggers window or meta-summary.
    Returns created summary or None.
    """
```

---

## Data Flow

### Ingestion Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Conversation Turn Completes                              │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. MemoryIngestor.ingest_turn()                             │
│    - Create Episode model                                   │
│    - Generate embedding (100-200ms)                         │
│    - Store in MemoryStore (<500ms total)                    │
└───────────────┬─────────────────────────────────────────────┘
                │
                ├──────────────────────────────────────────────┐
                │                                              │
                ▼ (async queue)                                ▼ (async queue)
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│ 3. EntityExtractor.extract()    │       │ 4. Check Summarization Threshold│
│    - LLM extraction (200-400ms) │       │    - Count episodes              │
│    - Returns entities + rels     │       │    - If threshold % == 0:        │
└───────────────┬─────────────────┘       │      trigger summarize_window()  │
                │                          └──────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. EntityDeduplicator.find_duplicate()                      │
│    - For each extracted entity:                             │
│      Stage 1: Exact match                                   │
│      Stage 2: Fuzzy match (if no exact)                     │
│      Stage 3: Embedding match (if no fuzzy)                 │
│      Stage 4: Rule-based (if no embedding)                  │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Store Entities and Relationships                         │
│    - If duplicate: merge_entities()                         │
│    - If new: add_entity()                                   │
│    - For relationships: check temporal updates              │
│      - Invalidate old (valid_to=now)                        │
│      - Create new (valid_from=now)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Relationships Between Models

```
Episode (1) ──has many──> (N) Entity
   │                          │
   │                          │
   └──references──> (N) Relationship <──connects── (2) Entity
                         │
                         │
                    has temporal
                    attributes
                    (valid_from,
                     valid_to)
```

**Cardinality**:
- One Episode can reference multiple Entities (via `entity_ids`)
- One Entity can appear in multiple Episodes
- One Relationship connects exactly two Entities
- Relationships have temporal versioning (same pair can have multiple versions)

---

## Storage Considerations

### Indexes Required

**Episodes**:
1. Primary key: `id`
2. Composite: `(group_id, recorded_at)` - For chronological queries
3. Vector index: `embedding` - For semantic search (HNSW or similar)
4. Filter: `(group_id, content_type)` - For summary retrieval

**Entities**:
1. Primary key: `id`
2. Unique: `(group_id, normalized(name), entity_type)` - For exact match deduplication
3. Temporal: `(group_id, valid_from, valid_to)` - For point-in-time queries
4. Vector index: `embedding` - For similarity deduplication

**Relationships**:
1. Primary key: `id`
2. Navigation: `(group_id, from_entity_id, relation_type, valid_to)` - For active relationship queries
3. Reverse: `(group_id, to_entity_id, relation_type, valid_to)` - For reverse traversal
4. Temporal: `(group_id, valid_from, valid_to)` - For point-in-time queries

### Performance Targets

| Operation | Target | Strategy |
|-----------|--------|----------|
| Episode creation | <500ms | In-memory model creation, fast embedding, indexed insert |
| Entity deduplication | <100ms | Staged matching (exact → fuzzy → embedding), early exit |
| Relationship temporal update | <50ms | Index lookup, two writes (invalidate + create) |
| Vector search | <50ms | HNSW index, limited to group_id partition |
| Summarization | <2s | Async task, batched LLM call |

---

## Validation Rules

### Episode Validation

1. `group_id` must match pattern `{uuid}:{uuid}`
2. `content` must not be empty
3. `embedding` dimensions must match model (768 or 1536)
4. `occurred_at` <= `recorded_at` (can't record before it happened)

### Entity Validation

1. `name` must not be empty
2. `valid_from` <= `valid_to` (if `valid_to` is set)
3. `recorded_at` >= `valid_from` (can't record before it became valid)
4. `entity_type` must be in allowed set
5. `confidence` must be "high", "medium", or "low"

### Relationship Validation

1. `from_entity_id` and `to_entity_id` must reference existing entities in same `group_id`
2. `from_entity_id` != `to_entity_id` (no self-references)
3. `valid_from` <= `valid_to` (if `valid_to` is set)
4. `relation_type` must not be empty

---

## Migration Considerations

### Adding to Existing Codebase

**No schema changes required** - All models already exist in `focal/memory/models/`.

**New implementations**:
- `MemoryIngestor` - New service class
- `EntityExtractor` - New service class
- `EntityDeduplicator` - New utility class
- `ConversationSummarizer` - New service class

**Configuration additions**:
- `MemoryIngestionConfig` in `focal/config/models/pipeline.py`
- TOML sections in `config/default.toml`

**Backward compatibility**:
- Existing Episode/Entity/Relationship queries continue working
- New fields (`embedding_model`, `confidence`) are optional
- Ingestion can be enabled/disabled per agent via configuration
