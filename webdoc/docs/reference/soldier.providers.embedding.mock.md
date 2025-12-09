<a id="focal.providers.embedding.mock"></a>

# focal.providers.embedding.mock

Mock embedding provider for testing.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider"></a>

## MockEmbeddingProvider Objects

```python
class MockEmbeddingProvider(EmbeddingProvider)
```

Mock embedding provider for testing.

Generates deterministic embeddings based on text content
without making actual API calls.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.__init__"></a>

#### \_\_init\_\_

```python
def __init__(dimensions: int = 384, default_model: str = "mock-embedding")
```

Initialize mock provider.

**Arguments**:

- `dimensions` - Embedding vector dimensions
- `default_model` - Model name to report

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.provider_name"></a>

#### provider\_name

```python
@property
def provider_name() -> str
```

Return the provider name.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.dimensions"></a>

#### dimensions

```python
@property
def dimensions() -> int
```

Return embedding dimensions.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.call_history"></a>

#### call\_history

```python
@property
def call_history() -> list[dict[str, Any]]
```

Return history of calls for testing assertions.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.clear_history"></a>

#### clear\_history

```python
def clear_history() -> None
```

Clear call history.

<a id="focal.providers.embedding.mock.MockEmbeddingProvider.embed"></a>

#### embed

```python
async def embed(texts: list[str],
                *,
                model: str | None = None,
                **kwargs: Any) -> EmbeddingResponse
```

Generate mock embeddings.

