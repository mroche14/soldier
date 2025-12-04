<a id="soldier.alignment.retrieval.reranker"></a>

# soldier.alignment.retrieval.reranker

Reranker wrapper for rule retrieval.

<a id="soldier.alignment.retrieval.reranker.RuleReranker"></a>

## RuleReranker Objects

```python
class RuleReranker()
```

Apply a rerank provider to reorder scored rules.

Reranking improves retrieval precision by using a cross-encoder
model to score query-document pairs more accurately than
embedding-based similarity alone.

<a id="soldier.alignment.retrieval.reranker.RuleReranker.__init__"></a>

#### \_\_init\_\_

```python
def __init__(provider: RerankProvider, top_k: int | None = None) -> None
```

Initialize the reranker.

**Arguments**:

- `provider` - RerankProvider implementation
- `top_k` - Optional limit on results to keep from reranker

<a id="soldier.alignment.retrieval.reranker.RuleReranker.rerank"></a>

#### rerank

```python
async def rerank(query: str,
                 scored_rules: list[ScoredRule]) -> list[ScoredRule]
```

Rerank scored rules using the provider.

**Arguments**:

- `query` - Query text to rank against
- `scored_rules` - Existing scored rules
  

**Returns**:

  Reranked scored rules (may be a subset if top_k is set)

