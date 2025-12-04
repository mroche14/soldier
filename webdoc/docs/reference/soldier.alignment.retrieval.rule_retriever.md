<a id="soldier.alignment.retrieval.rule_retriever"></a>

# soldier.alignment.retrieval.rule\_retriever

Rule retrieval with scope hierarchy and business filters.

<a id="soldier.alignment.retrieval.rule_retriever.RuleRetriever"></a>

## RuleRetriever Objects

```python
class RuleRetriever()
```

Retrieve candidate rules using embeddings and selection strategies.

Supports:
- Scope hierarchy (global → scenario → step)
- Business filters (max_fires, cooldown, enabled)
- Adaptive selection strategies
- Optional reranking for improved precision

<a id="soldier.alignment.retrieval.rule_retriever.RuleRetriever.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore,
             embedding_provider: EmbeddingProvider,
             selection_config: SelectionConfig | None = None,
             reranker: RuleReranker | None = None) -> None
```

Initialize the rule retriever.

**Arguments**:

- `config_store` - Store for rule definitions
- `embedding_provider` - Provider for query embeddings
- `selection_config` - Configuration for selection strategy
- `reranker` - Optional reranker for result refinement

<a id="soldier.alignment.retrieval.rule_retriever.RuleRetriever.retrieve"></a>

#### retrieve

```python
async def retrieve(
        tenant_id: UUID,
        agent_id: UUID,
        context: Context,
        *,
        active_scenario_id: UUID | None = None,
        active_step_id: UUID | None = None,
        fired_rule_counts: dict[UUID, int] | None = None,
        last_fired_turns: dict[UUID, int] | None = None) -> RetrievalResult
```

Retrieve rules across scopes with business filters applied.

**Arguments**:

- `tenant_id` - Tenant identifier
- `agent_id` - Agent identifier
- `context` - Extracted context with embedding
- `active_scenario_id` - Current scenario for scenario-scoped rules
- `active_step_id` - Current step for step-scoped rules
- `fired_rule_counts` - Rule fire counts for max_fires filter
- `last_fired_turns` - Last fire turn for cooldown filter
  

**Returns**:

  RetrievalResult with scored rules and metadata

