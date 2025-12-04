<a id="soldier.alignment.retrieval.scenario_retriever"></a>

# soldier.alignment.retrieval.scenario\_retriever

Scenario retrieval using embeddings and selection strategies.

<a id="soldier.alignment.retrieval.scenario_retriever.ScenarioRetriever"></a>

## ScenarioRetriever Objects

```python
class ScenarioRetriever()
```

Retrieve candidate scenarios using similarity against entry conditions.

Scenarios are retrieved by comparing the user message embedding against
each scenario's entry condition embedding. Selection strategies filter
to the most relevant candidates.

<a id="soldier.alignment.retrieval.scenario_retriever.ScenarioRetriever.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore,
             embedding_provider: EmbeddingProvider,
             selection_config: SelectionConfig | None = None) -> None
```

Initialize the scenario retriever.

**Arguments**:

- `config_store` - Store for scenario definitions
- `embedding_provider` - Provider for query embeddings
- `selection_config` - Configuration for selection strategy

<a id="soldier.alignment.retrieval.scenario_retriever.ScenarioRetriever.selection_strategy_name"></a>

#### selection\_strategy\_name

```python
@property
def selection_strategy_name() -> str
```

Return the selection strategy name.

<a id="soldier.alignment.retrieval.scenario_retriever.ScenarioRetriever.retrieve"></a>

#### retrieve

```python
async def retrieve(tenant_id: UUID, agent_id: UUID,
                   context: Context) -> list[ScoredScenario]
```

Retrieve scenarios for an agent and apply selection.

**Arguments**:

- `tenant_id` - Tenant identifier
- `agent_id` - Agent identifier
- `context` - Extracted context with embedding
  

**Returns**:

  List of scored scenarios sorted by relevance

