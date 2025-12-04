<a id="soldier.providers.embedding.base"></a>

# soldier.providers.embedding.base

EmbeddingProvider abstract interface.

<a id="soldier.providers.embedding.base.EmbeddingResponse"></a>

## EmbeddingResponse Objects

```python
class EmbeddingResponse(BaseModel)
```

Response from an embedding provider.

<a id="soldier.providers.embedding.base.EmbeddingProvider"></a>

## EmbeddingProvider Objects

```python
class EmbeddingProvider(ABC)
```

Abstract interface for text embeddings.

Provides unified access to various embedding providers
(OpenAI, Voyage, Cohere, etc.).

<a id="soldier.providers.embedding.base.EmbeddingProvider.provider_name"></a>

#### provider\_name

```python
@property
@abstractmethod
def provider_name() -> str
```

Return the provider name.

<a id="soldier.providers.embedding.base.EmbeddingProvider.dimensions"></a>

#### dimensions

```python
@property
@abstractmethod
def dimensions() -> int
```

Return the embedding dimensions.

<a id="soldier.providers.embedding.base.EmbeddingProvider.embed"></a>

#### embed

```python
@abstractmethod
async def embed(texts: list[str],
                *,
                model: str | None = None,
                **kwargs: Any) -> EmbeddingResponse
```

Generate embeddings for texts.

**Arguments**:

- `texts` - List of texts to embed
- `model` - Model to use (provider default if not specified)
- `**kwargs` - Provider-specific options
  

**Returns**:

  EmbeddingResponse with embedding vectors

<a id="soldier.providers.embedding.base.EmbeddingProvider.embed_single"></a>

#### embed\_single

```python
async def embed_single(text: str,
                       *,
                       model: str | None = None,
                       **kwargs: Any) -> list[float]
```

Generate embedding for a single text.

Convenience method that wraps embed() for single texts.

**Arguments**:

- `text` - Text to embed
- `model` - Model to use (provider default if not specified)
- `**kwargs` - Provider-specific options
  

**Returns**:

  Single embedding vector

