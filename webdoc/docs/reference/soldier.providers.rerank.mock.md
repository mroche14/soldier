<a id="focal.providers.rerank.mock"></a>

# focal.providers.rerank.mock

Mock rerank provider for testing.

<a id="focal.providers.rerank.mock.MockRerankProvider"></a>

## MockRerankProvider Objects

```python
class MockRerankProvider(RerankProvider)
```

Mock rerank provider for testing.

Uses simple text similarity for ranking without making API calls.

<a id="focal.providers.rerank.mock.MockRerankProvider.__init__"></a>

#### \_\_init\_\_

```python
def __init__(default_model: str = "mock-rerank")
```

Initialize mock provider.

**Arguments**:

- `default_model` - Model name to report

<a id="focal.providers.rerank.mock.MockRerankProvider.provider_name"></a>

#### provider\_name

```python
@property
def provider_name() -> str
```

Return the provider name.

<a id="focal.providers.rerank.mock.MockRerankProvider.call_history"></a>

#### call\_history

```python
@property
def call_history() -> list[dict[str, Any]]
```

Return history of calls for testing assertions.

<a id="focal.providers.rerank.mock.MockRerankProvider.clear_history"></a>

#### clear\_history

```python
def clear_history() -> None
```

Clear call history.

<a id="focal.providers.rerank.mock.MockRerankProvider.rerank"></a>

#### rerank

```python
async def rerank(query: str,
                 documents: list[str],
                 *,
                 model: str | None = None,
                 top_k: int | None = None,
                 **kwargs: Any) -> RerankResponse
```

Rerank documents using word overlap similarity.

