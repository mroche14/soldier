<a id="soldier.providers.rerank.base"></a>

# soldier.providers.rerank.base

RerankProvider abstract interface.

<a id="soldier.providers.rerank.base.RerankResult"></a>

## RerankResult Objects

```python
class RerankResult(BaseModel)
```

A single reranked result.

<a id="soldier.providers.rerank.base.RerankResponse"></a>

## RerankResponse Objects

```python
class RerankResponse(BaseModel)
```

Response from a rerank provider.

<a id="soldier.providers.rerank.base.RerankProvider"></a>

## RerankProvider Objects

```python
class RerankProvider(ABC)
```

Abstract interface for reranking.

Provides unified access to various reranking providers
(Cohere, Voyage, cross-encoders, etc.).

<a id="soldier.providers.rerank.base.RerankProvider.provider_name"></a>

#### provider\_name

```python
@property
@abstractmethod
def provider_name() -> str
```

Return the provider name.

<a id="soldier.providers.rerank.base.RerankProvider.rerank"></a>

#### rerank

```python
@abstractmethod
async def rerank(query: str,
                 documents: list[str],
                 *,
                 model: str | None = None,
                 top_k: int | None = None,
                 **kwargs: Any) -> RerankResponse
```

Rerank documents by relevance to query.

**Arguments**:

- `query` - Query to rank documents against
- `documents` - List of documents to rerank
- `model` - Model to use (provider default if not specified)
- `top_k` - Return only top K results (all if not specified)
- `**kwargs` - Provider-specific options
  

**Returns**:

  RerankResponse with sorted results

