<a id="focal.memory.ingestion.entity_extractor"></a>

# focal.memory.ingestion.entity\_extractor

Entity and relationship extraction from episodes.

<a id="focal.memory.ingestion.entity_extractor.EntityExtractor"></a>

## EntityExtractor Objects

```python
class EntityExtractor()
```

Extract entities and relationships from episode content using LLM.

<a id="focal.memory.ingestion.entity_extractor.EntityExtractor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(llm_provider: LLMProvider, config: EntityExtractionConfig)
```

Initialize entity extractor.

**Arguments**:

- `llm_provider` - LLM provider for extraction
- `config` - Extraction configuration

<a id="focal.memory.ingestion.entity_extractor.EntityExtractor.extract"></a>

#### extract

```python
async def extract(episode: Episode) -> EntityExtractionResult
```

Extract entities and relationships from episode content.

Uses LLMProvider with structured output to identify:
- Named entities (people, products, orders, issues, concepts)
- Relationships between those entities
- Confidence scores for each extraction

**Arguments**:

- `episode` - Episode to extract from
  

**Returns**:

- `EntityExtractionResult` - Contains lists of ExtractedEntity
  and ExtractedRelationship objects
  

**Raises**:

- `ExtractionError` - If LLM call fails or returns invalid structure

<a id="focal.memory.ingestion.entity_extractor.EntityExtractor.extract_batch"></a>

#### extract\_batch

```python
async def extract_batch(
        episodes: list[Episode]) -> list[EntityExtractionResult]
```

Extract from multiple episodes in parallel.

**Arguments**:

- `episodes` - List of episodes to extract from
  

**Returns**:

  List of EntityExtractionResult in same order as input

<a id="focal.memory.ingestion.entity_extractor.EntityDeduplicator"></a>

## EntityDeduplicator Objects

```python
class EntityDeduplicator()
```

Find and merge duplicate entities using multi-stage matching.

<a id="focal.memory.ingestion.entity_extractor.EntityDeduplicator.__init__"></a>

#### \_\_init\_\_

```python
def __init__(memory_store: MemoryStore, config: EntityDeduplicationConfig)
```

Initialize entity deduplicator.

**Arguments**:

- `memory_store` - Store for querying existing entities
- `config` - Deduplication configuration

<a id="focal.memory.ingestion.entity_extractor.EntityDeduplicator.find_duplicate"></a>

#### find\_duplicate

```python
async def find_duplicate(entity: Entity, group_id: str) -> Entity | None
```

Find duplicate entity using multi-stage pipeline.

Stages (in order, stops at first match):
1. Exact match (normalized name)
2. Fuzzy string matching (Levenshtein)
3. Embedding similarity (cosine)
4. Rule-based (domain-specific)

**Arguments**:

- `entity` - Candidate entity to check
- `group_id` - Scope for searching existing entities
  

**Returns**:

- `Entity` - Existing duplicate if found, None otherwise

<a id="focal.memory.ingestion.entity_extractor.EntityDeduplicator.merge_entities"></a>

#### merge\_entities

```python
async def merge_entities(existing: Entity, new: Entity) -> Entity
```

Merge new entity data into existing entity.

Combines attributes (new takes precedence for conflicts),
preserves temporal timestamps.

**Arguments**:

- `existing` - Entity already in MemoryStore
- `new` - Newly extracted entity with updated data
  

**Returns**:

- `Entity` - Merged entity (NOT automatically persisted)

<a id="focal.memory.ingestion.entity_extractor.update_relationship_temporal"></a>

#### update\_relationship\_temporal

```python
async def update_relationship_temporal(
        from_entity_id: UUID, to_entity_id: UUID, relation_type: str,
        new_attributes: dict[str, Any], group_id: str,
        memory_store: MemoryStore) -> Relationship
```

Update a relationship by invalidating old and creating new.

**Arguments**:

- `from_entity_id` - Source entity ID
- `to_entity_id` - Target entity ID
- `relation_type` - Relationship type
- `new_attributes` - New attributes for relationship
- `group_id` - Tenant:session identifier
- `memory_store` - Memory store
  

**Returns**:

  New relationship

