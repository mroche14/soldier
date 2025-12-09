<a id="focal.alignment.models.context"></a>

# focal.alignment.models.context

Context models for alignment domain.

<a id="focal.alignment.models.context.UserIntent"></a>

## UserIntent Objects

```python
class UserIntent(BaseModel)
```

Classified user intent.

<a id="focal.alignment.models.context.ExtractedEntities"></a>

## ExtractedEntities Objects

```python
class ExtractedEntities(BaseModel)
```

Named entities from message.

<a id="focal.alignment.models.context.Context"></a>

## Context Objects

```python
class Context(BaseModel)
```

Extracted understanding of user message.

Contains the processed understanding of a user's message
including intent, entities, and metadata.

