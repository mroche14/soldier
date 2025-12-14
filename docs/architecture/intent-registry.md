# Intent Registry

> **Purpose**: Intent catalog for canonical intent matching and analytics
> **Phase**: 4 (Retrieval & Selection)
> **Status**: Implemented

---

## Overview

The Intent Registry provides a centralized catalog of canonical intents that can be matched against user messages using hybrid retrieval (vector + BM25). This enables consistent intent classification across the system and supports intent-based analytics.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│                  Intent Registry                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────┐        ┌──────────────────┐   │
│  │ Intent Catalog │        │ Intent Retriever │   │
│  │ (ConfigStore)  │◄───────│ (Hybrid Search)  │   │
│  └────────────────┘        └──────────────────┘   │
│                                     │              │
│                                     ▼              │
│                         ┌───────────────────────┐  │
│                         │ Canonical Decision    │  │
│                         │ (LLM + Hybrid Merge) │  │
│                         └───────────────────────┘  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Data Models

#### Intent

```python
class Intent(BaseModel):
    """Canonical intent definition."""

    id: UUID
    tenant_id: UUID
    agent_id: UUID

    # Intent identification
    label: str  # e.g., "order_cancellation", "refund_request"
    description: str | None

    # Retrieval
    example_phrases: list[str]
    embedding: list[float] | None  # Precomputed from examples
    embedding_model: str | None

    # Metadata
    created_at: datetime
    updated_at: datetime
    enabled: bool = True
```

#### IntentCandidate

```python
class IntentCandidate(BaseModel):
    """Scored intent candidate from retrieval."""

    intent_id: UUID
    intent_label: str
    score: float
    source: Literal["hybrid", "llm_sensor"]  # How it was matched
```

---

## Retrieval Process

### Phase 4.2: Hybrid Intent Retrieval

```python
# In IntentRetriever.retrieve()

1. Load all enabled intents for agent
2. Compute query embedding (if not cached in context)
3. Score each intent:
   - Vector similarity: cosine(query_embedding, intent.embedding)
   - BM25 score: match query against example_phrases
   - Combined: weighted average (configurable)
4. Apply selection strategy (top-k, threshold, etc.)
5. Return scored candidates
```

### Phase 4.3: Canonical Intent Decision

```python
# In decide_canonical_intent()

def decide_canonical_intent(
    sensor_intent: str | None,          # From Situational Sensor (Phase 2)
    sensor_confidence: float | None,    # LLM confidence
    hybrid_candidates: list[IntentCandidate],  # From retrieval
    threshold: float = 0.7,
) -> tuple[str | None, float | None]:
    """Merge LLM sensor and hybrid retrieval."""

    # Strategy:
    # 1. If sensor confidence >= threshold, trust it
    # 2. Else if top hybrid score >= threshold, use hybrid
    # 3. Else fallback to sensor (even if low confidence)
```

---

## Configuration

### Intent Catalog Config

```toml
[pipeline.retrieval.intent_selection]
strategy = "top_k"
max_k = 5
min_k = 1
min_score = 0.0

[pipeline.retrieval.intent_hybrid]
enabled = true
vector_weight = 0.5
bm25_weight = 0.5
normalization = "softmax"

[pipeline.retrieval.intent_reranking]
enabled = false  # Simple matching usually sufficient
```

---

## Storage

### ConfigStore Interface

```python
class AgentConfigStore(ABC):
    @abstractmethod
    async def get_intents(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        enabled_only: bool = True,
    ) -> list[Intent]:
        """Get all intents for an agent."""

    @abstractmethod
    async def get_intent(
        self,
        tenant_id: UUID,
        intent_id: UUID,
    ) -> Intent | None:
        """Get a specific intent."""

    @abstractmethod
    async def save_intent(self, intent: Intent) -> None:
        """Save or update an intent."""

    @abstractmethod
    async def delete_intent(
        self,
        tenant_id: UUID,
        intent_id: UUID,
    ) -> None:
        """Delete an intent."""
```

### PostgreSQL Schema

```sql
CREATE TABLE intents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    label VARCHAR(255) NOT NULL,
    description TEXT,
    example_phrases TEXT[] NOT NULL DEFAULT '{}',
    embedding FLOAT[] NULL,
    embedding_model VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX ix_intents_tenant_agent ON intents (tenant_id, agent_id);
CREATE INDEX ix_intents_label ON intents (label);
CREATE INDEX ix_intents_tenant_agent_enabled ON intents (tenant_id, agent_id, enabled);
```

---

## Usage Examples

### Creating Intents

```python
from ruche.mechanics.focal.models.intent import Intent
from datetime import datetime, UTC
from uuid import uuid4

# Create an intent
intent = Intent(
    id=uuid4(),
    tenant_id=my_tenant_id,
    agent_id=my_agent_id,
    label="order_cancellation",
    description="User wants to cancel their order",
    example_phrases=[
        "cancel my order",
        "I want to cancel",
        "cancel order please",
        "stop my order",
    ],
    embedding=None,  # Will be computed on save
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
    enabled=True,
)

# Save to store
await config_store.save_intent(intent)
```

### Retrieving Intents

```python
from ruche.mechanics.focal.retrieval.intent_retriever import IntentRetriever

retriever = IntentRetriever(
    config_store=config_store,
    embedding_provider=embedding_provider,
    selection_config=SelectionConfig(max_k=5, min_score=0.7),
)

# Retrieve candidates
candidates = await retriever.retrieve(
    tenant_id=my_tenant_id,
    agent_id=my_agent_id,
    context=context,
)

# candidates = [
#     IntentCandidate(intent_label="order_cancellation", score=0.85, source="hybrid"),
#     IntentCandidate(intent_label="refund_request", score=0.72, source="hybrid"),
# ]
```

### Canonical Intent Decision

```python
from ruche.mechanics.focal.retrieval.intent_retriever import decide_canonical_intent

# Merge LLM sensor with hybrid retrieval
canonical, confidence = decide_canonical_intent(
    sensor_intent="order_cancellation",  # From Phase 2 sensor
    sensor_confidence=0.6,  # Low confidence
    hybrid_candidates=candidates,
    threshold=0.7,
)

# Result: ("order_cancellation", 0.85)
# Used hybrid candidate since it had higher confidence
```

---

## Analytics

### Intent Distribution

Track which intents are matched most frequently:

```python
from ruche.observability.metrics import Counter

intent_matched = Counter(
    "focal_intent_matched_total",
    "Total intent matches",
    ["tenant_id", "intent_label"],
)

# Track match
intent_matched.labels(
    tenant_id=str(tenant_id),
    intent_label=canonical_intent,
).inc()
```

### Intent Confidence

Track confidence distribution:

```python
intent_confidence = Histogram(
    "focal_intent_confidence",
    "Intent match confidence scores",
    ["tenant_id", "source"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Track confidence
intent_confidence.labels(
    tenant_id=str(tenant_id),
    source="hybrid",  # or "llm_sensor"
).observe(confidence)
```

---

## Best Practices

### Intent Design

1. **Granularity**: Not too broad ("customer_inquiry") or too narrow ("cancel_order_placed_yesterday")
2. **Coverage**: 5-20 intents per agent is typical
3. **Example Phrases**: 3-10 diverse examples per intent
4. **Mutual Exclusivity**: Intents should be distinct

### Example Phrases

Good:
```python
example_phrases=[
    "cancel my order",
    "I want to cancel",
    "stop my order",
    "abort this purchase",
]
```

Bad (too similar):
```python
example_phrases=[
    "cancel my order",
    "cancel the order",
    "cancel this order",
]
```

### Performance

1. **Catalog Size**: <1000 intents per agent (all loaded per retrieval)
2. **Embedding Precomputation**: Compute embeddings on save, not retrieval
3. **Caching**: Context embedding cached across retrievers

---

## Integration with Pipeline

### Phase 2: Situational Sensor

LLM extracts intent with confidence:

```python
{
    "intent": "order_cancellation",
    "intent_confidence": 0.6,  # Low confidence
    ...
}
```

### Phase 4: Intent Retrieval

Hybrid retrieval provides additional candidates:

```python
candidates = [
    IntentCandidate(label="order_cancellation", score=0.85, source="hybrid"),
]
```

### Phase 4: Canonical Decision

Merge sensor + hybrid:

```python
canonical, confidence = decide_canonical_intent(
    sensor_intent="order_cancellation",
    sensor_confidence=0.6,
    hybrid_candidates=candidates,
    threshold=0.7,
)
# Result: ("order_cancellation", 0.85) - hybrid wins
```

### Downstream Usage

```python
# Store in context for rule retrieval, generation, etc.
context.canonical_intent_label = canonical
context.canonical_intent_score = confidence

# Use in rule matching
if rule.required_intent == context.canonical_intent_label:
    # Rule applies
```

---

## Testing

### Unit Tests

```python
# tests/unit/alignment/retrieval/test_intent_retriever.py
- test_retrieve_with_matching_intent()
- test_retrieve_disabled_intents_excluded()
- test_retrieve_respects_selection_strategy()

# tests/unit/alignment/retrieval/test_intent_decision.py
- test_trusts_confident_sensor()
- test_prefers_hybrid_over_low_confidence_sensor()
- test_fallback_to_sensor_when_both_low()
```

---

## Future Enhancements

1. **Intent Hierarchies**: Parent/child intent relationships
2. **Multi-Intent Support**: Multiple active intents per turn
3. **Auto-Discovery**: Suggest new intents from conversation patterns
4. **Intent Transitions**: Track intent flow across turns

---

## References

- **Models**: `ruche/mechanics/focal/models/intent.py`
- **Retriever**: `ruche/mechanics/focal/retrieval/intent_retriever.py`
- **Store Interface**: `ruche/stores/agent_config_store.py`
- **Migration**: `alembic/versions/012_add_intents_table.py`
- **Tests**: `tests/unit/mechanics/focal/retrieval/test_intent_*.py`
