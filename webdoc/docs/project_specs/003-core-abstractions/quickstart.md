# Quickstart: Core Abstractions Layer

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This guide shows how to use the core abstractions implemented in Phases 2-5.

---

## 1. Observability Setup

### Logging

```python
from focal.observability.logging import setup_logging, get_logger
from structlog.contextvars import bind_contextvars

# Configure logging (typically at app startup)
setup_logging(
    level="DEBUG",           # DEBUG for development
    format="console",        # console for development, json for production
    include_trace_id=True,
    redact_pii=True,
)

# Get a logger
logger = get_logger(__name__)

# Bind request context (typically in middleware)
bind_contextvars(
    tenant_id="tenant-123",
    agent_id="agent-456",
    session_id="session-789",
)

# Log events with structured data
logger.info("turn_started", message_length=42)
logger.debug("rule_matched", rule_id="rule-abc", score=0.95)
logger.warning("fallback_triggered", reason="low_confidence")
```

### Metrics

```python
from focal.observability.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    LLM_TOKENS,
)
import time

# Increment counter with labels
REQUEST_COUNT.labels(
    tenant_id="tenant-123",
    agent_id="agent-456",
    endpoint="/v1/chat",
    status="200",
).inc()

# Observe histogram
start = time.perf_counter()
# ... do work ...
REQUEST_LATENCY.labels(
    tenant_id="tenant-123",
    agent_id="agent-456",
    endpoint="/v1/chat",
).observe(time.perf_counter() - start)

# Count tokens
LLM_TOKENS.labels(
    provider="anthropic",
    model="claude-3-haiku",
    direction="input",
).inc(1500)
```

### Tracing

```python
from focal.observability.tracing import setup_tracing, span, add_span_attributes

# Configure tracing (typically at app startup)
setup_tracing(
    service_name="focal",
    otlp_endpoint="http://localhost:4317",  # None for console
    sample_rate=1.0,
)

# Create spans
with span("process_turn", attributes={"turn_id": "turn-123"}):
    # Nested span
    with span("context_extraction"):
        # ... extract context ...
        add_span_attributes(intent="refund_request")

    with span("llm_generation"):
        add_span_attributes(
            model="claude-3-haiku",
            tokens_input=100,
            tokens_output=50,
        )
```

---

## 2. Domain Models

### Creating Models

```python
from uuid import uuid4
from focal.alignment.models import Rule, Scope, MatchedRule
from focal.memory.models import Episode
from focal.conversation.models import Session, Channel, SessionStatus

# Create a Rule
rule = Rule(
    tenant_id=uuid4(),
    agent_id=uuid4(),
    name="Refund Policy",
    condition_text="User asks about refunds or returns",
    action_text="Explain the 30-day refund policy",
    scope=Scope.GLOBAL,
    priority=10,
    is_hard_constraint=True,
)

# Create an Episode
episode = Episode(
    group_id=f"{tenant_id}:{session_id}",
    content="I'd like to return my order from last week",
    source="user",
    occurred_at=datetime.utcnow(),
)

# Create a Session
session = Session(
    tenant_id=uuid4(),
    agent_id=uuid4(),
    channel=Channel.WEBCHAT,
    user_channel_id="user@example.com",
    config_version=1,
)
```

### Model Validation

```python
from pydantic import ValidationError

# Valid creation
rule = Rule(
    tenant_id=uuid4(),
    agent_id=uuid4(),
    name="Valid Rule",
    condition_text="When this",
    action_text="Do that",
    priority=50,  # Valid: -100 to 100
)

# Invalid creation raises ValidationError
try:
    rule = Rule(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="",  # Invalid: min_length=1
        condition_text="",  # Invalid: min_length=1
        action_text="Do that",
        priority=150,  # Invalid: max=100
    )
except ValidationError as e:
    print(e.errors())
```

---

## 3. Store Usage

### ConfigStore

```python
from focal.alignment.stores import InMemoryConfigStore
from focal.alignment.models import Rule, Scenario, Template

# Create store
config_store = InMemoryConfigStore()

# Save and retrieve rules
rule = Rule(...)
rule_id = await config_store.save_rule(rule)
retrieved = await config_store.get_rule(tenant_id, rule_id)

# Query rules by scope
rules = await config_store.get_rules(
    tenant_id=tenant_id,
    agent_id=agent_id,
    scope=Scope.SCENARIO,
    scope_id=scenario_id,
)

# Vector search
similar_rules = await config_store.vector_search_rules(
    query_embedding=[0.1, 0.2, ...],
    tenant_id=tenant_id,
    agent_id=agent_id,
    limit=10,
)
for rule, score in similar_rules:
    print(f"{rule.name}: {score:.3f}")
```

### MemoryStore

```python
from focal.memory.stores import InMemoryMemoryStore
from focal.memory.models import Episode, Entity, Relationship

# Create store
memory_store = InMemoryMemoryStore()

# Add and search episodes
episode = Episode(
    group_id=f"{tenant_id}:{session_id}",
    content="User mentioned order #12345",
    source="agent",
    occurred_at=datetime.utcnow(),
    embedding=[0.1, 0.2, ...],  # Precomputed
)
await memory_store.add_episode(episode)

# Vector search
results = await memory_store.vector_search_episodes(
    query_embedding=[0.1, 0.2, ...],
    group_id=group_id,
    limit=5,
)

# Text search
results = await memory_store.text_search_episodes(
    query="order",
    group_id=group_id,
)

# Entity and relationship management
entity = Entity(
    group_id=group_id,
    name="Order #12345",
    entity_type="order",
    attributes={"status": "shipped"},
    valid_from=datetime.utcnow(),
)
await memory_store.add_entity(entity)

# Graph traversal
related = await memory_store.traverse_from_entities(
    entity_ids=[entity.id],
    group_id=group_id,
    depth=2,
)
```

### SessionStore

```python
from focal.conversation.stores import InMemorySessionStore
from focal.conversation.models import Session, Channel

# Create store
session_store = InMemorySessionStore()

# Get or create session
session = await session_store.get_by_channel(
    tenant_id=tenant_id,
    channel=Channel.WEBCHAT,
    user_channel_id="user@example.com",
)

if session is None:
    session = Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=Channel.WEBCHAT,
        user_channel_id="user@example.com",
        config_version=1,
    )
    await session_store.save(session)

# Update session
session.turn_count += 1
session.last_activity_at = datetime.utcnow()
await session_store.save(session)

# List sessions
sessions = await session_store.list_by_agent(
    tenant_id=tenant_id,
    agent_id=agent_id,
    status=SessionStatus.ACTIVE,
    limit=100,
)
```

### AuditStore

```python
from focal.audit.stores import InMemoryAuditStore
from focal.audit.models import TurnRecord, AuditEvent

# Create store
audit_store = InMemoryAuditStore()

# Save turn record
turn = TurnRecord(
    turn_id=uuid4(),
    tenant_id=tenant_id,
    agent_id=agent_id,
    session_id=session_id,
    turn_number=1,
    user_message="Hello",
    agent_response="Hi! How can I help?",
    latency_ms=234,
    tokens_used=150,
    timestamp=datetime.utcnow(),
)
await audit_store.save_turn(turn)

# Query turns
turns = await audit_store.list_turns_by_session(
    session_id=session_id,
    limit=50,
)

# Save audit event
event = AuditEvent(
    tenant_id=tenant_id,
    event_type="rule_fired",
    event_data={"rule_id": str(rule_id), "turn": 1},
    session_id=session_id,
)
await audit_store.save_event(event)
```

### ProfileStore

```python
from focal.profile.stores import InMemoryProfileStore
from focal.profile.models import CustomerProfile, ProfileField, ProfileFieldSource

# Create store
profile_store = InMemoryProfileStore()

# Get or create profile
profile = await profile_store.get_or_create(
    tenant_id=tenant_id,
    channel=Channel.WEBCHAT,
    user_channel_id="user@example.com",
)

# Update profile field
field = ProfileField(
    name="email",
    value="user@example.com",
    value_type="email",
    source=ProfileFieldSource.USER_PROVIDED,
    verified=True,
)
await profile_store.update_field(tenant_id, profile.id, field)

# Link additional channel
from focal.profile.models import ChannelIdentity
identity = ChannelIdentity(
    channel=Channel.WHATSAPP,
    channel_user_id="+1234567890",
    verified=True,
)
await profile_store.link_channel(tenant_id, profile.id, identity)
```

---

## 4. Provider Usage

### LLM Provider

```python
from focal.providers.llm import MockLLMProvider
from focal.providers.factory import create_llm_provider

# Create mock provider directly
llm = MockLLMProvider(
    default_response="I understand your request.",
)

# Or via factory
from focal.config.models import LLMProviderConfig
config = LLMProviderConfig(provider="mock", default_response="Test response")
llm = create_llm_provider(config)

# Generate text
response = await llm.generate(
    prompt="What is your return policy?",
    system_prompt="You are a helpful customer service agent.",
    max_tokens=200,
    temperature=0.7,
)
print(response.text)
print(f"Tokens: {response.usage.total_tokens}")

# Generate structured output
from pydantic import BaseModel

class Intent(BaseModel):
    primary: str
    confidence: float

intent = await llm.generate_structured(
    prompt="User says: I want to return my order",
    schema=Intent,
)
print(f"Intent: {intent.primary} ({intent.confidence:.2f})")
```

### Embedding Provider

```python
from focal.providers.embedding import MockEmbeddingProvider

# Create provider
embedding = MockEmbeddingProvider(dimensions=384)

# Embed single text
vector = await embedding.embed("I want to return my order")
print(f"Dimensions: {len(vector)}")  # 384

# Batch embed
texts = ["Return policy", "Shipping info", "Contact us"]
vectors = await embedding.embed_batch(texts)
print(f"Embedded {len(vectors)} texts")
```

### Rerank Provider

```python
from focal.providers.rerank import MockRerankProvider

# Create provider
reranker = MockRerankProvider(score_strategy="position")

# Rerank documents
query = "return policy"
documents = [
    "Our shipping takes 3-5 days",
    "Returns are accepted within 30 days",
    "Contact support at help@example.com",
]

results = await reranker.rerank(query, documents, top_k=2)
for result in results:
    print(f"[{result.index}] {result.score:.2f}: {result.document[:50]}...")
```

---

## 5. Testing Patterns

### Using Fixtures

```python
import pytest
from uuid import uuid4

@pytest.fixture
def tenant_id():
    return uuid4()

@pytest.fixture
def agent_id():
    return uuid4()

@pytest.fixture
def config_store():
    return InMemoryConfigStore()

@pytest.fixture
def llm_provider():
    return MockLLMProvider(default_response="Test response")

@pytest.mark.asyncio
async def test_save_and_get_rule(config_store, tenant_id, agent_id):
    rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Test Rule",
        condition_text="When test",
        action_text="Do test",
    )

    rule_id = await config_store.save_rule(rule)
    retrieved = await config_store.get_rule(tenant_id, rule_id)

    assert retrieved is not None
    assert retrieved.name == "Test Rule"
```

### Contract Tests

```python
# tests/unit/alignment/stores/test_config_store_contract.py
import pytest
from abc import ABC, abstractmethod

class ConfigStoreContract(ABC):
    """Base class for ConfigStore contract tests."""

    @pytest.fixture
    @abstractmethod
    def store(self):
        """Return store implementation to test."""
        pass

    @pytest.mark.asyncio
    async def test_save_and_get_rule(self, store, tenant_id, agent_id):
        rule = Rule(...)
        rule_id = await store.save_rule(rule)
        retrieved = await store.get_rule(tenant_id, rule_id)
        assert retrieved == rule

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, store):
        # Test that tenant A cannot see tenant B's data
        ...


class TestInMemoryConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()


# Later: class TestPostgresConfigStore(ConfigStoreContract): ...
```

---

## Common Patterns

### 1. Always Bind Context Early

```python
# In middleware or request handler
bind_contextvars(
    tenant_id=str(request.tenant_id),
    agent_id=str(request.agent_id),
    session_id=str(session.session_id),
)
# All subsequent logs automatically include context
```

### 2. Use Async Throughout

```python
# All store operations are async
async def process_turn(session: Session, message: str):
    rules = await config_store.get_rules(...)
    episodes = await memory_store.vector_search_episodes(...)
    # ...
```

### 3. Tenant Isolation is Mandatory

```python
# Always pass tenant_id to store operations
rules = await config_store.get_rules(
    tenant_id=tenant_id,  # Required!
    agent_id=agent_id,
)
```

### 4. Soft Delete for Audit Trail

```python
# Delete marks deleted_at, doesn't remove data
await config_store.delete_rule(tenant_id, rule_id)

# Query excludes deleted by default
active_rules = await config_store.get_rules(...)  # deleted_at IS NULL
```
