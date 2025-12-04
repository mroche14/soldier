<a id="soldier.memory.store"></a>

# soldier.memory.store

MemoryStore abstract interface.

<a id="soldier.memory.store.MemoryStore"></a>

## MemoryStore Objects

```python
class MemoryStore(ABC)
```

Abstract interface for memory storage.

Manages episodes, entities, and relationships with support
for vector search, text search, and graph traversal.

<a id="soldier.memory.store.MemoryStore.add_episode"></a>

#### add\_episode

```python
@abstractmethod
async def add_episode(episode: Episode) -> UUID
```

Add an episode to the store.

<a id="soldier.memory.store.MemoryStore.get_episode"></a>

#### get\_episode

```python
@abstractmethod
async def get_episode(group_id: str, episode_id: UUID) -> Episode | None
```

Get an episode by ID.

<a id="soldier.memory.store.MemoryStore.get_episodes"></a>

#### get\_episodes

```python
@abstractmethod
async def get_episodes(group_id: str, *, limit: int = 100) -> list[Episode]
```

Get episodes for a group.

<a id="soldier.memory.store.MemoryStore.vector_search_episodes"></a>

#### vector\_search\_episodes

```python
@abstractmethod
async def vector_search_episodes(
        query_embedding: list[float],
        group_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.0) -> list[tuple[Episode, float]]
```

Search episodes by vector similarity.

<a id="soldier.memory.store.MemoryStore.text_search_episodes"></a>

#### text\_search\_episodes

```python
@abstractmethod
async def text_search_episodes(query: str,
                               group_id: str,
                               *,
                               limit: int = 10) -> list[Episode]
```

Search episodes by text content.

<a id="soldier.memory.store.MemoryStore.delete_episode"></a>

#### delete\_episode

```python
@abstractmethod
async def delete_episode(group_id: str, episode_id: UUID) -> bool
```

Delete an episode.

<a id="soldier.memory.store.MemoryStore.add_entity"></a>

#### add\_entity

```python
@abstractmethod
async def add_entity(entity: Entity) -> UUID
```

Add an entity to the store.

<a id="soldier.memory.store.MemoryStore.get_entity"></a>

#### get\_entity

```python
@abstractmethod
async def get_entity(group_id: str, entity_id: UUID) -> Entity | None
```

Get an entity by ID.

<a id="soldier.memory.store.MemoryStore.get_entities"></a>

#### get\_entities

```python
@abstractmethod
async def get_entities(group_id: str,
                       *,
                       entity_type: str | None = None,
                       limit: int = 100) -> list[Entity]
```

Get entities for a group with optional type filter.

<a id="soldier.memory.store.MemoryStore.update_entity"></a>

#### update\_entity

```python
@abstractmethod
async def update_entity(entity: Entity) -> bool
```

Update an existing entity.

<a id="soldier.memory.store.MemoryStore.delete_entity"></a>

#### delete\_entity

```python
@abstractmethod
async def delete_entity(group_id: str, entity_id: UUID) -> bool
```

Delete an entity.

<a id="soldier.memory.store.MemoryStore.add_relationship"></a>

#### add\_relationship

```python
@abstractmethod
async def add_relationship(relationship: Relationship) -> UUID
```

Add a relationship to the store.

<a id="soldier.memory.store.MemoryStore.get_relationship"></a>

#### get\_relationship

```python
@abstractmethod
async def get_relationship(group_id: str,
                           relationship_id: UUID) -> Relationship | None
```

Get a single relationship by ID.

<a id="soldier.memory.store.MemoryStore.get_relationships"></a>

#### get\_relationships

```python
@abstractmethod
async def get_relationships(
        group_id: str,
        *,
        from_entity_id: UUID | None = None,
        to_entity_id: UUID | None = None,
        relation_type: str | None = None) -> list[Relationship]
```

Get relationships with optional filters.

<a id="soldier.memory.store.MemoryStore.update_relationship"></a>

#### update\_relationship

```python
@abstractmethod
async def update_relationship(relationship: Relationship) -> bool
```

Update an existing relationship.

<a id="soldier.memory.store.MemoryStore.delete_relationship"></a>

#### delete\_relationship

```python
@abstractmethod
async def delete_relationship(group_id: str, relationship_id: UUID) -> bool
```

Delete a relationship.

<a id="soldier.memory.store.MemoryStore.traverse_from_entities"></a>

#### traverse\_from\_entities

```python
@abstractmethod
async def traverse_from_entities(
        entity_ids: list[UUID],
        group_id: str,
        *,
        depth: int = 2,
        relation_types: list[str] | None = None) -> list[Entity]
```

Traverse graph from given entities up to specified depth.

<a id="soldier.memory.store.MemoryStore.delete_by_group"></a>

#### delete\_by\_group

```python
@abstractmethod
async def delete_by_group(group_id: str) -> int
```

Delete all episodes, entities, and relationships for a group.

Returns count of deleted items.

