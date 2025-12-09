# Memory Layer

The memory layer gives Focal agents long-term context and factual grounding. It combines a **temporal knowledge graph** with **hybrid retrieval** to provide both precise facts and semantic recall.

## Core Concepts

### Episodes

An **Episode** is the atomic unit of memory—a single piece of experience:

- User message
- Agent response
- System event
- External data ingestion

Each Episode contains:
- Raw text or structured data
- Timestamp (when it occurred)
- Ingestion timestamp (when Focal learned it)
- Source metadata
- `group_id` for tenant/session isolation

### Entities and Relationships

When an Episode is ingested, Focal extracts:

- **Entities**: Named things (people, products, orders, concepts)
- **Relationships**: Connections between entities (ordered, owns, related_to)

Example: "I ordered a laptop last week but it arrived damaged"

```
Extracted:
  Entities: [Order, Laptop, DamageIssue]
  Relationships: [Order -contains-> Laptop, Order -has_issue-> DamageIssue]
```

### Temporal Modeling

All nodes and edges carry **bi-temporal attributes**:

| Attribute | Meaning |
|-----------|---------|
| `valid_from` | When the fact became true in the real world |
| `valid_to` | When the fact stopped being true (null if still valid) |
| `recorded_at` | When Focal learned this fact |

This enables:
- **Point-in-time queries**: "What did we know about this customer last Tuesday?"
- **Contradiction handling**: New facts invalidate old edges rather than deleting them
- **Audit trails**: Complete history preserved for compliance

## Storage Backend (MemoryStore Interface)

The memory layer uses the `MemoryStore` interface, allowing pluggable backends. Implementations are selected via configuration.

| Backend | Graph Traversal | Vector Search | Best For |
|---------|-----------------|---------------|----------|
| **Neo4j** | Native Cypher | HNSW indexes | Production, complex traversals |
| **FalkorDB** | Native GraphQL | Built-in vectors | Low-latency, unified queries |
| **PostgreSQL + pgvector** | CTEs/recursive | pgvector HNSW | Simple deployments, familiarity |
| **MongoDB + Atlas Vector** | $graphLookup | Atlas Vector Search | Document-centric, flexible schema |
| **ArangoDB** | AQL traversals | Built-in | Multi-model workloads |
| **InMemory** | Dict-based | Linear scan | Testing/development |

See [ADR-001: Storage and Cache Architecture](../design/decisions/001-storage-choice.md) for full interface definitions.

### MemoryStore Interface

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

class MemoryStore(ABC):
    """Interface for knowledge graph storage."""

    @abstractmethod
    async def add_episode(self, episode: Episode) -> UUID:
        """Store an episode in the knowledge graph."""
        pass

    @abstractmethod
    async def vector_search(
        self, query_embedding: List[float], group_id: str, limit: int = 10
    ) -> List[Episode]:
        """Find episodes by vector similarity."""
        pass

    @abstractmethod
    async def text_search(
        self, query: str, group_id: str, limit: int = 10
    ) -> List[Episode]:
        """Find episodes by full-text search (BM25 or similar)."""
        pass

    @abstractmethod
    async def add_entity(self, entity: Entity) -> UUID:
        """Store an entity node."""
        pass

    @abstractmethod
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Store a relationship edge between entities."""
        pass

    @abstractmethod
    async def traverse_from_entities(
        self, entity_ids: List[UUID], group_id: str, depth: int = 2
    ) -> List[Dict[str, Any]]:
        """Traverse graph from given entities to find related context."""
        pass

    @abstractmethod
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all data for a group (tenant:session)."""
        pass
```

## Hybrid Retrieval

Focal combines three search strategies to find relevant context:

### 1. Semantic Vector Search

Find Episodes/Entities similar to the query by meaning.

```
Query: "broken product refund"
Matches: Episode about "damaged laptop" (embeddings are close)
```

- Uses embeddings from OpenAI, SentenceTransformers, or local models
- Stored via MemoryStore implementation (each backend handles vectors differently)
- Sub-100ms retrieval via HNSW or similar indexes

### 2. Keyword/BM25 Search

Exact term matching for precision.

```
Query: "Order #12345"
Matches: Exact Episode mentioning that order ID
```

- Full-text indexes on Episode content
- Catches cases where semantic search misses exact terms
- Useful for IDs, names, codes

### 3. Graph Traversal

Follow relationships from known-relevant nodes.

```
Starting point: Entity "Order #12345" (from BM25 match)
Traverse: Order -> Customer -> Previous Orders -> Issues
Result: Related context the user didn't explicitly mention
```

- Leverages graph structure for contextual expansion
- Weighted by recency and relevance
- Bounded depth to control result size

### Retrieval Pipeline

```
User Query
     │
     ├──► Embed query ──► Vector search ──► Top-K Episodes
     │
     ├──► BM25 search ──► Top-K Episodes
     │
     └──► Known entities ──► Graph traversal ──► Related nodes
                │
                ▼
         Merge + Re-rank
                │
                ▼
         Final context set
```

**Key property**: No LLM calls during retrieval. All heavy lifting (extraction, summarization) happens at ingestion time.

## Ingestion Pipeline

When new data arrives:

```
Raw Input (message, event, document)
     │
     ▼
┌─────────────────────────────────┐
│     Entity Extraction           │
│  (LLM or spaCy for NER)         │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│   Relationship Extraction       │
│  (LLM structured output)        │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│      Embedding Generation       │
│  (Episode text → vector)        │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│       Graph Update              │
│  - Merge/create entities        │
│  - Insert relationships         │
│  - Update temporal validity     │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│    Summarization (async)        │
│  - Trigger if session long      │
│  - Create summary Episodes      │
└─────────────────────────────────┘
```

### Continuous Updates

Episodes integrate incrementally—no batch reprocessing:

- New Episode triggers entity extraction
- Entities merge with existing nodes or create new ones
- Relationships added with current timestamp
- Embeddings indexed immediately
- Summaries generated asynchronously (don't block response)

## Summarization

For long conversations, Focal compresses older turns:

- After N turns (configurable), generate summary Episode
- Summary linked to conversation/user node
- Retrieval prefers summaries for distant history, raw Episodes for recent
- Hierarchical: summary of summaries for very long sessions

## Multi-Tenancy

Memory isolation via `group_id` (all MemoryStore implementations must enforce this):

```python
# Adding an Episode via MemoryStore interface
await memory_store.add_episode(Episode(
    content="User asked about refund",
    group_id=f"{tenant_id}:{session_id}",
    occurred_at=now(),
    source="user"
))

# Querying via MemoryStore interface
results = await memory_store.vector_search(
    query_embedding=embedding,
    group_id=f"{tenant_id}:{session_id}",  # Only sees this tenant's data
    limit=10
)
```

- All MemoryStore implementations filter by `group_id`
- No cross-tenant data leakage possible at interface level
- Performance benefit: queries scope to smaller subgraph/partition

## Performance Targets

| Operation | Target Latency |
|-----------|----------------|
| Vector search (top-10) | < 50ms |
| BM25 search | < 30ms |
| Graph traversal (depth 2) | < 100ms |
| Full hybrid retrieval | < 200ms |
| Episode ingestion | < 500ms (sync), < 2s (with extraction) |
