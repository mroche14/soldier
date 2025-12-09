<a id="focal.memory.ingestion.models"></a>

# focal.memory.ingestion.models

Structured output models for entity extraction.

<a id="focal.memory.ingestion.models.ExtractedEntity"></a>

## ExtractedEntity Objects

```python
class ExtractedEntity(BaseModel)
```

Pydantic model for LLM structured output during entity extraction.

<a id="focal.memory.ingestion.models.ExtractedRelationship"></a>

## ExtractedRelationship Objects

```python
class ExtractedRelationship(BaseModel)
```

Pydantic model for LLM structured output during relationship extraction.

<a id="focal.memory.ingestion.models.EntityExtractionResult"></a>

## EntityExtractionResult Objects

```python
class EntityExtractionResult(BaseModel)
```

Complete extraction result from LLM containing all entities and relationships.

