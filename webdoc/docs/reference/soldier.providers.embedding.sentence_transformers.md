<a id="soldier.providers.embedding.sentence_transformers"></a>

# soldier.providers.embedding.sentence\_transformers

Sentence-Transformers embedding provider for local embeddings.

<a id="soldier.providers.embedding.sentence_transformers.SentenceTransformersProvider"></a>

## SentenceTransformersProvider Objects

```python
class SentenceTransformersProvider(EmbeddingProvider)
```

Embedding provider using sentence-transformers models.

<a id="soldier.providers.embedding.sentence_transformers.SentenceTransformersProvider.__init__"></a>

#### \_\_init\_\_

```python
def __init__(model_name: str = "all-mpnet-base-v2", batch_size: int = 32)
```

Initialize sentence-transformers provider.

**Arguments**:

- `model_name` - Model name to load
- `batch_size` - Batch size for encoding

<a id="soldier.providers.embedding.sentence_transformers.SentenceTransformersProvider.provider_name"></a>

#### provider\_name

```python
@property
def provider_name() -> str
```

Return the provider name.

<a id="soldier.providers.embedding.sentence_transformers.SentenceTransformersProvider.dimensions"></a>

#### dimensions

```python
@property
def dimensions() -> int
```

Return embedding dimensions.

<a id="soldier.providers.embedding.sentence_transformers.SentenceTransformersProvider.embed"></a>

#### embed

```python
async def embed(texts: list[str],
                *,
                model: str | None = None,
                **kwargs: Any) -> EmbeddingResponse
```

Generate embeddings using sentence-transformers.

**Arguments**:

- `texts` - List of texts to embed
- `model` - Ignored (model set at initialization)
- `**kwargs` - Additional options (ignored)
  

**Returns**:

  EmbeddingResponse with embedding vectors

