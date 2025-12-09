<a id="focal.memory.stores.inmemory"></a>

# focal.memory.stores.inmemory

In-memory implementation of MemoryStore.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore"></a>

## InMemoryMemoryStore Objects

```python
class InMemoryMemoryStore(MemoryStore)
```

In-memory implementation of MemoryStore for testing and development.

Uses simple dict storage with linear scan for queries.
Implements BFS for graph traversal.
Not suitable for production use.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize empty storage.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.add_episode"></a>

#### add\_episode

```python
async def add_episode(episode: Episode) -> UUID
```

Add an episode to the store.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_episode"></a>

#### get\_episode

```python
async def get_episode(group_id: str, episode_id: UUID) -> Episode | None
```

Get an episode by ID.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_episodes"></a>

#### get\_episodes

```python
async def get_episodes(group_id: str, *, limit: int = 100) -> list[Episode]
```

Get episodes for a group.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.vector_search_episodes"></a>

#### vector\_search\_episodes

```python
async def vector_search_episodes(
        query_embedding: list[float],
        group_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.0) -> list[tuple[Episode, float]]
```

Search episodes by vector similarity.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.text_search_episodes"></a>

#### text\_search\_episodes

```python
async def text_search_episodes(query: str,
                               group_id: str,
                               *,
                               limit: int = 10) -> list[Episode]
```

Search episodes by text content (substring match).

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.delete_episode"></a>

#### delete\_episode

```python
async def delete_episode(group_id: str, episode_id: UUID) -> bool
```

Delete an episode.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.add_entity"></a>

#### add\_entity

```python
async def add_entity(entity: Entity) -> UUID
```

Add an entity to the store.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_entity"></a>

#### get\_entity

```python
async def get_entity(group_id: str, entity_id: UUID) -> Entity | None
```

Get an entity by ID.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_entities"></a>

#### get\_entities

```python
async def get_entities(group_id: str,
                       *,
                       entity_type: str | None = None,
                       limit: int = 100) -> list[Entity]
```

Get entities for a group with optional type filter.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.update_entity"></a>

#### update\_entity

```python
async def update_entity(entity: Entity) -> bool
```

Update an existing entity.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.delete_entity"></a>

#### delete\_entity

```python
async def delete_entity(group_id: str, entity_id: UUID) -> bool
```

Delete an entity.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.add_relationship"></a>

#### add\_relationship

```python
async def add_relationship(relationship: Relationship) -> UUID
```

Add a relationship to the store.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_relationship"></a>

#### get\_relationship

```python
async def get_relationship(group_id: str,
                           relationship_id: UUID) -> Relationship | None
```

Get a single relationship by ID.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.get_relationships"></a>

#### get\_relationships

```python
async def get_relationships(
        group_id: str,
        *,
        from_entity_id: UUID | None = None,
        to_entity_id: UUID | None = None,
        relation_type: str | None = None) -> list[Relationship]
```

Get relationships with optional filters.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.update_relationship"></a>

#### update\_relationship

```python
async def update_relationship(relationship: Relationship) -> bool
```

Update an existing relationship.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.delete_relationship"></a>

#### delete\_relationship

```python
async def delete_relationship(group_id: str, relationship_id: UUID) -> bool
```

Delete a relationship.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.traverse_from_entities"></a>

#### traverse\_from\_entities

```python
async def traverse_from_entities(
        entity_ids: list[UUID],
        group_id: str,
        *,
        depth: int = 2,
        relation_types: list[str] | None = None) -> list[Entity]
```

Traverse graph from given entities using BFS.

<a id="focal.memory.stores.inmemory.InMemoryMemoryStore.delete_by_group"></a>

#### delete\_by\_group

```python
async def delete_by_group(group_id: str) -> int
```

Delete all items for a group.

