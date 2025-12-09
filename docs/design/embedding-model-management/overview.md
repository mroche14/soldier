# Embedding Model Management

## Overview

This document describes the strategy for managing embedding models across different object types (Rules, Episodes, Intents, Scenarios) in Focal, ensuring consistency between configuration, vector stores, and query-time operations.

## Problem Statement

### Current State

The `embedding_model` field is stored redundantly in **three separate locations**:

```
Entity Model (Pydantic)     →  PostgreSQL Column     →  Vector Store Metadata
Rule.embedding_model           rules.embedding_model      VectorMetadata.embedding_model
Episode.embedding_model        episodes.embedding_model   payload["embedding_model"]
```

### Issues

1. **Redundancy**: Same information stored 3 times, requiring synchronized updates
2. **No Validation**: Query embeddings can be compared against incompatible stored embeddings silently
3. **No Enforcement**: Config change to different model doesn't prevent querying old vectors
4. **Drift Risk**: Different pods with different configs can corrupt vector search quality
5. **Wasted Storage**: Per-record metadata overhead when model is constant per object type

### Failure Scenario

```
Time T1: Pod A embeds all rules with "openai/text-embedding-3-small"
Time T2: Config updated to "voyage/voyage-3"
Time T3: Pod B starts, queries with Voyage vectors against OpenAI vectors
Result:  GARBAGE RESULTS - cosine similarity across incompatible embedding spaces
         NO ERROR RAISED - silent failure
```

## Requirements

### Functional Requirements

1. **FR-1**: Support different embedding models per object type (rules, episodes, intents)
2. **FR-2**: Enable A/B testing of embedding models before full migration
3. **FR-3**: Support model changes without losing existing embeddings
4. **FR-4**: Prevent accidental mixing of incompatible embeddings
5. **FR-5**: Work with both pgvector and Qdrant (backend-agnostic)

### Non-Functional Requirements

1. **NFR-1**: Fail fast on configuration/data mismatch at startup
2. **NFR-2**: Require explicit operator approval before costly re-embedding
3. **NFR-3**: Minimize per-record storage overhead
4. **NFR-4**: Support gradual migration without downtime

## Design Options

### Option 1: Per-Record Model Tracking (Current)

**How it works**: Store `embedding_model` on each record.

```python
class Rule(BaseModel):
    embedding_model: str | None  # Stored per rule
```

| Pros | Cons |
|------|------|
| Simple implementation | 3x redundancy |
| Mixed models in same collection | No query-time validation |
| Flexible per-record | Storage overhead |
| | Silent failures on model mismatch |

**Verdict**: Current state. Informational only, no enforcement.

---

### Option 2: Collection-Per-Model (Per Object Type)

**How it works**: Each combination of object type + model gets its own collection.

```
Collection naming: {object_type}_{model_slug}

Examples:
  rules_openai_text_embedding_3_small
  rules_voyage_3
  episodes_openai_text_embedding_3_small
  intents_cohere_embed_v3
```

**Configuration**:
```toml
[embeddings]
rules = "openai/text-embedding-3-small"
episodes = "voyage/voyage-3"
intents = "openai/text-embedding-3-small"
```

| Pros | Cons |
|------|------|
| No per-record overhead | Collection proliferation |
| Implicit model from collection | Migration = new collection |
| Impossible to mix models | Requires re-embedding to change |
| Clean A/B testing | More complex collection management |
| Backend-agnostic | |

**Implementation**:
- pgvector: Separate tables or schema-based partitioning
- Qdrant: Separate collections with dimension enforcement

**Verdict**: Clean but requires explicit migration workflow.

---

### Option 3: Collection-Level Metadata

**How it works**: Store model info at collection level, not per-record.

```python
# Collection metadata (stored once)
{
    "collection": "rules",
    "embedding_model": "openai/text-embedding-3-small",
    "dimensions": 1536,
    "created_at": "2025-01-15T00:00:00Z"
}

# Individual records have NO embedding_model field
```

| Pros | Cons |
|------|------|
| Single source of truth | Requires collection metadata API |
| No per-record overhead | All records must use same model |
| Clear ownership | Migration still complex |
| Easy validation | |

**Implementation**:
- pgvector: Metadata table or table comment
- Qdrant: Collection configuration payload

**Verdict**: Good balance but requires metadata management.

---

### Option 4: Hybrid with Startup Validation (Recommended)

**How it works**: Combine collection-per-model with strict startup validation and operator-gated migration.

**Architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Configuration                             │
│  [embeddings.rules]                                              │
│  model = "openai/text-embedding-3-small"                        │
│  dimensions = 1536                                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Startup Validation                            │
│  1. Check collection exists                                      │
│  2. Verify dimensions match config                               │
│  3. Verify collection model matches config                       │
│  4. If mismatch → FAIL with migration instructions              │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            [Match: Continue]      [Mismatch: Fail Fast]
                    │                       │
                    ▼                       ▼
            Normal Operation        Migration Required
                                   (Operator Decision)
```

**Configuration**:
```toml
[embeddings.rules]
model = "openai/text-embedding-3-small"
dimensions = 1536
collection = "rules"  # Optional override, defaults to object type

[embeddings.episodes]
model = "voyage/voyage-3"
dimensions = 1024

[embeddings.intents]
model = "openai/text-embedding-3-small"
dimensions = 1536

[embeddings.migration]
# Safety: require explicit approval for re-embedding
auto_migrate = false
cost_warning_threshold = 10000  # vectors
```

**Startup Behavior**:

```python
async def validate_embedding_config():
    """Run at pod startup. Fail fast on mismatch."""

    for object_type in ["rules", "episodes", "intents"]:
        config = settings.embeddings[object_type]
        collection = await vector_store.get_collection(object_type)

        if collection is None:
            # New collection - create with config
            await vector_store.create_collection(
                name=object_type,
                dimensions=config.dimensions,
                metadata={"embedding_model": config.model}
            )
            continue

        # Validate existing collection
        if collection.dimensions != config.dimensions:
            raise StartupError(
                f"Dimension mismatch for '{object_type}': "
                f"collection={collection.dimensions}, config={config.dimensions}. "
                f"Run migration or fix config."
            )

        if collection.metadata.get("embedding_model") != config.model:
            raise StartupError(
                f"Model mismatch for '{object_type}': "
                f"collection={collection.metadata['embedding_model']}, "
                f"config={config.model}. "
                f"Run: focal migrate embeddings {object_type}"
            )
```

**Migration Workflow** (Operator-Gated):

```
Step 1: Operator changes config
        embeddings.rules.model = "voyage/voyage-3"

Step 2: Pod startup FAILS with clear message
        "Model mismatch for 'rules': collection=openai/text-embedding-3-small,
         config=voyage/voyage-3. Run: focal migrate embeddings rules"

Step 3: Operator runs migration command
        $ focal migrate embeddings rules --dry-run

        Migration Plan:
        - Source: rules (openai/text-embedding-3-small)
        - Target: rules_new (voyage/voyage-3)
        - Records: 15,432
        - Estimated cost: $2.31 (Voyage API)
        - Estimated time: 12 minutes

        Proceed? [y/N]

Step 4: Operator approves, migration runs
        - Creates rules_new collection
        - Re-embeds all rules with new model
        - Updates collection metadata
        - Swaps collection pointers
        - Archives old collection (configurable retention)

Step 5: Pods can now start successfully
```

| Pros | Cons |
|------|------|
| Fail-fast prevents silent corruption | More complex startup |
| Operator approval prevents cost surprises | Requires migration tooling |
| Clear migration workflow | Downtime during validation |
| Cost estimation before commit | |
| Backend-agnostic | |
| Audit trail of model changes | |

**Verdict**: Recommended. Balances safety with operational control.

---

## Comparison Matrix

| Aspect | Option 1 (Current) | Option 2 (Collection-per-model) | Option 3 (Collection metadata) | Option 4 (Hybrid) |
|--------|-------------------|--------------------------------|-------------------------------|-------------------|
| Per-record overhead | High (3x) | None | None | None |
| Query-time validation | None | Implicit | Explicit | Explicit |
| Mixed models | Allowed (dangerous) | Impossible | Impossible | Impossible |
| A/B testing | Manual | Easy | Medium | Easy |
| Migration complexity | None | New collection | Metadata update | Gated workflow |
| Cost control | None | None | None | Built-in |
| Failure mode | Silent | Fast | Fast | Fast + Actionable |
| Backend support | All | All | Varies | All |

## Recommended Solution: Option 4

### Rationale

1. **Safety First**: Fail-fast startup prevents silent embedding space corruption
2. **Cost Control**: Operator must approve re-embedding costs before execution
3. **Clear Workflow**: Migration command with dry-run, estimates, and confirmation
4. **Audit Trail**: Collection metadata tracks model history
5. **Backend Agnostic**: Works with pgvector, Qdrant, or any vector store
6. **Minimal Overhead**: No per-record model field needed

### Changes from Current State

| Component | Current | Proposed |
|-----------|---------|----------|
| `Rule.embedding_model` | Per-record field | Remove |
| `Episode.embedding_model` | Per-record field | Remove |
| `VectorMetadata.embedding_model` | Per-record metadata | Keep (for migration traceability) |
| Database columns | `embedding_model VARCHAR(100)` | Remove in migration |
| Collection creation | Static | Dynamic with metadata |
| Startup | No validation | Strict validation |
| Model change | Silent | Fail + migration workflow |

## Impact Analysis

### Files Affected: 45+

| Category | Count | Severity | Notes |
|----------|-------|----------|-------|
| Domain Models | 3 | HIGH | Remove field definitions |
| Database Migrations | 3 | HIGH | New migration to drop columns |
| Postgres Stores | 2 | HIGH | Rewrite 6+ SQL methods |
| Vector Stores | 3 | MEDIUM | Update metadata handling |
| Embedding Manager | 1 | HIGH | Core logic refactoring |
| Configuration | 1 | MEDIUM | Add embedding config section |
| Tests | 6+ | MEDIUM | Update fixtures |

### Detailed File List

**Models to modify**:
- `focal/alignment/models/rule.py` - Remove `embedding_model` field
- `focal/alignment/models/intent.py` - Remove `embedding_model` field
- `focal/memory/models/episode.py` - Remove `embedding_model` field

**Stores to modify**:
- `focal/alignment/stores/postgres.py` - Remove from all queries
- `focal/memory/stores/postgres.py` - Remove from episode queries

**New components**:
- `focal/vector/validation.py` - Startup validation
- `focal/cli/migrate.py` - Migration command
- `focal/config/models/embedding.py` - Embedding config models

## Migration Strategy

### Phase 1: Add Configuration (Non-Breaking)

1. Add new `[embeddings]` config section
2. Add startup validation (warning mode, not blocking)
3. Add collection metadata support to vector stores

### Phase 2: Dual-Write Mode

1. Continue writing `embedding_model` to records
2. Also write to collection metadata
3. Log warnings on mismatches

### Phase 3: Migration Tooling

1. Implement `focal migrate embeddings` command
2. Add dry-run with cost estimation
3. Add rollback capability

### Phase 4: Remove Redundancy

1. Create migration to drop `embedding_model` columns
2. Remove field from domain models
3. Update all tests

### Phase 5: Strict Enforcement

1. Enable fail-fast startup validation
2. Remove dual-write code
3. Document operational procedures

## Appendix A: Vector Store Specifics

### pgvector

**Collection = Table**

```sql
-- Collection metadata stored in table comment or separate metadata table
CREATE TABLE rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    embedding vector(1536),
    -- NO embedding_model column
    ...
);

COMMENT ON TABLE rules IS '{"embedding_model": "openai/text-embedding-3-small", "dimensions": 1536}';

-- Or metadata table
CREATE TABLE vector_collection_metadata (
    collection_name VARCHAR(100) PRIMARY KEY,
    embedding_model VARCHAR(200) NOT NULL,
    dimensions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Qdrant

**Collection = Collection**

```python
# Create collection with metadata
client.create_collection(
    collection_name="rules",
    vectors_config=VectorParams(
        size=1536,
        distance=Distance.COSINE,
    ),
)

# Store metadata in collection info (custom payload on a sentinel point)
# Or use collection aliases for model versioning
```

## Appendix B: Cost Estimation

### Embedding API Costs (Approximate, 2025)

| Provider | Model | Cost per 1M tokens |
|----------|-------|-------------------|
| OpenAI | text-embedding-3-small | $0.02 |
| OpenAI | text-embedding-3-large | $0.13 |
| Voyage | voyage-3 | $0.06 |
| Cohere | embed-v3 | $0.10 |

### Example Migration Cost

```
Rules: 10,000 records
Average text: 200 tokens
Total tokens: 2,000,000

OpenAI small: $0.04
Voyage-3: $0.12
```

The migration command should display these estimates before execution.

## Appendix C: Configuration Schema

```toml
[embeddings]
# Default model for new object types
default_model = "openai/text-embedding-3-small"

[embeddings.rules]
model = "openai/text-embedding-3-small"
dimensions = 1536
# collection = "rules"  # Optional, defaults to object type

[embeddings.episodes]
model = "voyage/voyage-3"
dimensions = 1024

[embeddings.intents]
model = "openai/text-embedding-3-small"
dimensions = 1536

[embeddings.scenarios]
model = "openai/text-embedding-3-small"
dimensions = 1536

[embeddings.migration]
# Require explicit approval for re-embedding
auto_migrate = false

# Warn before migrating more than N vectors
cost_warning_threshold = 10000

# Keep old collection for N days after migration
retention_days = 7
```

## References

- [Qdrant: How to choose an embedding model](https://qdrant.tech/articles/how-to-choose-an-embedding-model/)
- [Qdrant: Collection management](https://qdrant.tech/documentation/concepts/collections/)
- [Milvus: Embedding model versioning](https://milvus.io/ai-quick-reference/how-do-you-version-and-manage-changes-in-embedding-models)
- [Zilliz: Embedding model versioning in production](https://zilliz.com/ai-faq/how-do-i-handle-versioning-of-embedding-models-in-production)
- [LanceDB: Versioning & Reproducibility](https://lancedb.com/docs/tables/versioning/)
