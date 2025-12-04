# Quickstart: Alignment Pipeline

**Feature**: 004-alignment-pipeline
**Date**: 2025-11-28

This guide shows how to use the Alignment Pipeline after implementation.

## Prerequisites

```bash
# Install dependencies (already in pyproject.toml after Phase 6)
uv sync
```

## Basic Usage

### 1. Process a Simple Message

```python
from uuid import uuid4
from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.stores.inmemory import InMemoryConfigStore
from soldier.conversation.stores.inmemory import InMemorySessionStore
from soldier.conversation.models import Channel, Session
from soldier.audit.stores.inmemory import InMemoryAuditStore
from soldier.memory.stores.inmemory import InMemoryMemoryStore
from soldier.providers.llm.mock import MockLLMProvider
from soldier.providers.embedding.mock import MockEmbeddingProvider
from soldier.config.models.pipeline import PipelineConfig

# Create stores (use in-memory for development)
config_store = InMemoryConfigStore()
session_store = InMemorySessionStore()
audit_store = InMemoryAuditStore()
memory_store = InMemoryMemoryStore()

# Create providers
llm_provider = MockLLMProvider(default_response="Hello! How can I help?")
embedding_provider = MockEmbeddingProvider(dimensions=1536)

# Create engine with all stores
engine = AlignmentEngine(
    config_store=config_store,
    llm_provider=llm_provider,
    embedding_provider=embedding_provider,
    session_store=session_store,
    audit_store=audit_store,
    memory_store=memory_store,
    pipeline_config=PipelineConfig(),
)

# Create a session
tenant_id = uuid4()
agent_id = uuid4()
session = Session(
    tenant_id=tenant_id,
    agent_id=agent_id,
    channel=Channel.API,
    user_channel_id="user-123",
    config_version=1,
)
await session_store.save(session)

# Process a turn - engine handles session loading, state updates, and persistence
result = await engine.process_turn(
    message="I want to return my order",
    session_id=session.session_id,
    tenant_id=tenant_id,
    agent_id=agent_id,
)

print(result.response)  # The agent's response
print(f"Processed in {result.total_time_ms}ms")
print(f"Turn ID: {result.turn_id}")  # For audit trail

# Session state is automatically updated
updated_session = await session_store.get(session.session_id)
print(f"Turn count: {updated_session.turn_count}")

# Turn record is automatically saved to audit store
turn_record = await audit_store.get_turn(result.turn_id)
print(f"Audit record: {turn_record.user_message} -> {turn_record.agent_response}")
```

### 2. Using Selection Strategies

```python
from soldier.alignment.retrieval.selection import (
    AdaptiveKSelectionStrategy,
    EntropySelectionStrategy,
    ScoredItem,
)

# Create scored items (from vector search)
items = [
    ScoredItem(item=rule1, score=0.95),
    ScoredItem(item=rule2, score=0.89),
    ScoredItem(item=rule3, score=0.45),  # Will likely be cut
]

# Use adaptive-k selection
strategy = AdaptiveKSelectionStrategy(alpha=1.5, min_score=0.5)
result = strategy.select(items, max_k=20, min_k=1)

print(f"Selected {len(result.selected)} items")
print(f"Cutoff score: {result.cutoff_score}")
print(f"Strategy: {result.method}")
```

### 3. Context Extraction

```python
from soldier.alignment.context.extractor import ContextExtractor
from soldier.alignment.context.models import Turn

extractor = ContextExtractor(
    llm_provider=llm_provider,
    embedding_provider=embedding_provider,
)

# Extract context with full LLM analysis
context = await extractor.extract(
    message="I need to return order #12345, it arrived damaged",
    history=[
        Turn(role="assistant", content="Welcome! How can I help?"),
    ],
    mode="llm",
)

print(f"Intent: {context.intent}")  # "return damaged order"
print(f"Entities: {context.entities}")  # [order_id: 12345]
print(f"Sentiment: {context.sentiment}")  # "negative"
print(f"Scenario signal: {context.scenario_signal}")  # "start"
```

### 4. Configuring the Pipeline

Pipeline behavior is configured via TOML:

```toml
# config/default.toml

[pipeline.context_extraction]
enabled = true
mode = "llm"  # llm, embedding_only, disabled
provider = "default"

[pipeline.retrieval]
max_k = 30
min_k = 1
embedding_provider = "default"

[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"
alpha = 1.5
min_score = 0.5

[pipeline.retrieval.scenario_selection]
strategy = "entropy"
min_score = 0.6

[pipeline.reranking]
enabled = true
provider = "cohere"

[pipeline.rule_filtering]
enabled = true
provider = "default"

[pipeline.scenario_filtering]
enabled = true
provider = "default"

[pipeline.generation]
enabled = true
provider = "default"
max_tokens = 1024
temperature = 0.7

[pipeline.enforcement]
enabled = true
max_regenerations = 1
```

### 5. Working with Rules

```python
from soldier.alignment.models import Rule
from soldier.alignment.models.enums import Scope, TemplateMode

# Create a rule
rule = Rule(
    id=uuid4(),
    tenant_id=tenant_id,
    agent_id=agent_id,
    name="Return Policy",
    condition_text="User asks about returning an order",
    action_text="Explain the 30-day return policy",
    scope=Scope.GLOBAL,
    enabled=True,
    priority=100,
)

# Save to store
await config_store.save_rule(rule)

# Create a rule with an attached template
rule_with_template = Rule(
    id=uuid4(),
    tenant_id=tenant_id,
    agent_id=agent_id,
    name="Greeting Template",
    condition_text="User greets the agent",
    action_text="Respond with greeting",
    attached_template_ids=[template_id],  # Template references
)

# Create a hard constraint rule
hard_constraint = Rule(
    id=uuid4(),
    tenant_id=tenant_id,
    agent_id=agent_id,
    name="No Competitor Mentions",
    condition_text="Any message",
    action_text="Never mention competitors",
    is_hard_constraint=True,  # Must be satisfied or fallback
)
```

### 6. Scenario Navigation

```python
# The scenario filter handles navigation automatically based on
# the current session state and user message

result = await engine.process_turn(
    message="Yes, I want to proceed with the return",
    session_id=session_id,  # Session is already in a scenario
    tenant_id=tenant_id,
    agent_id=agent_id,
)

# Check scenario navigation result
if result.scenario_result:
    print(f"Action: {result.scenario_result.action}")  # "transition"
    print(f"New step: {result.scenario_result.target_step_id}")
```

### 7. Tool Execution

```python
# Tools are attached to rules and executed automatically

# Check tool results in the alignment result
for tool_result in result.tool_results:
    print(f"Tool: {tool_result.tool_name}")
    print(f"Success: {tool_result.success}")
    if tool_result.success:
        print(f"Output: {tool_result.outputs}")
    else:
        print(f"Error: {tool_result.error}")
```

### 8. Observability

```python
# Pipeline timings are available for performance analysis
for timing in result.pipeline_timings:
    print(f"{timing.step}: {timing.duration_ms}ms")
    if timing.skipped:
        print(f"  (skipped: {timing.skip_reason})")

# Structured logging is automatic
# Logs include: tenant_id, session_id, turn_id, step timings
```

## Testing

```python
import pytest
from soldier.alignment.retrieval.selection import (
    SelectionStrategyContract,
    ElbowSelectionStrategy,
    AdaptiveKSelectionStrategy,
)

# All strategies pass the same contract tests
class TestElbowStrategy(SelectionStrategyContract):
    @pytest.fixture
    def strategy(self):
        return ElbowSelectionStrategy()

class TestAdaptiveKStrategy(SelectionStrategyContract):
    @pytest.fixture
    def strategy(self):
        return AdaptiveKSelectionStrategy()
```

## Common Patterns

### Disabling Steps for Speed

```toml
# For maximum speed (embedding-only, no filtering)
[pipeline.context_extraction]
mode = "embedding_only"

[pipeline.reranking]
enabled = false

[pipeline.rule_filtering]
enabled = false

[pipeline.scenario_filtering]
enabled = false
```

### Different Strategies per Content Type

```toml
# Rules: adaptive-k for general use
[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"
alpha = 1.5

# Scenarios: entropy (usually one clear match)
[pipeline.retrieval.scenario_selection]
strategy = "entropy"
low_entropy_k = 1

# Memory: clustering (multi-topic conversations)
[pipeline.retrieval.memory_selection]
strategy = "clustering"
top_per_cluster = 3
```

## Next Steps

- See `data-model.md` for complete data model documentation
- See `contracts/` for interface specifications
- See `tasks.md` for implementation tasks (after `/speckit.tasks`)
