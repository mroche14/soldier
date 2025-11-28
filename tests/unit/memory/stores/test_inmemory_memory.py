"""Tests for InMemoryMemoryStore."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from soldier.memory.models import Entity, Episode, Relationship
from soldier.memory.stores import InMemoryMemoryStore


@pytest.fixture
def store() -> InMemoryMemoryStore:
    """Create a fresh store for each test."""
    return InMemoryMemoryStore()


@pytest.fixture
def group_id():
    return f"{uuid4()}:{uuid4()}"


@pytest.fixture
def sample_episode(group_id) -> Episode:
    """Create a sample episode."""
    return Episode(
        group_id=group_id,
        content="User asked about refund policy",
        source="user",
        occurred_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_entity(group_id) -> Entity:
    """Create a sample entity."""
    return Entity(
        group_id=group_id,
        name="John Doe",
        entity_type="person",
        valid_from=datetime.now(timezone.utc),
    )


class TestEpisodeOperations:
    """Tests for episode CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_get_episode(self, store, sample_episode, group_id):
        """Should add and retrieve an episode."""
        episode_id = await store.add_episode(sample_episode)
        retrieved = await store.get_episode(group_id, episode_id)

        assert retrieved is not None
        assert retrieved.id == sample_episode.id
        assert retrieved.content == "User asked about refund policy"

    @pytest.mark.asyncio
    async def test_get_nonexistent_episode(self, store, group_id):
        """Should return None for nonexistent episode."""
        result = await store.get_episode(group_id, uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_group_isolation(self, store, sample_episode, group_id):
        """Should not return episodes from other groups."""
        await store.add_episode(sample_episode)
        other_group = f"{uuid4()}:{uuid4()}"
        result = await store.get_episode(other_group, sample_episode.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_episodes_by_group(self, store, group_id):
        """Should get all episodes for a group."""
        episodes = [
            Episode(
                group_id=group_id,
                content=f"Message {i}",
                source="user",
                occurred_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]
        for ep in episodes:
            await store.add_episode(ep)

        results = await store.get_episodes(group_id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_delete_episode(self, store, sample_episode, group_id):
        """Should delete an episode."""
        await store.add_episode(sample_episode)

        result = await store.delete_episode(group_id, sample_episode.id)
        assert result is True

        retrieved = await store.get_episode(group_id, sample_episode.id)
        assert retrieved is None


class TestVectorSearch:
    """Tests for vector search functionality."""

    @pytest.mark.asyncio
    async def test_vector_search_episodes(self, store, group_id):
        """Should search episodes by vector similarity."""
        ep1 = Episode(
            group_id=group_id,
            content="Similar content",
            source="user",
            occurred_at=datetime.now(timezone.utc),
            embedding=[1.0, 0.0, 0.0],
        )
        ep2 = Episode(
            group_id=group_id,
            content="Different content",
            source="user",
            occurred_at=datetime.now(timezone.utc),
            embedding=[0.0, 1.0, 0.0],
        )
        await store.add_episode(ep1)
        await store.add_episode(ep2)

        query = [1.0, 0.0, 0.0]
        results = await store.vector_search_episodes(query, group_id)

        assert len(results) == 2
        assert results[0][0].content == "Similar content"
        assert results[0][1] == 1.0

    @pytest.mark.asyncio
    async def test_vector_search_min_score(self, store, group_id):
        """Should filter by minimum score."""
        ep1 = Episode(
            group_id=group_id,
            content="High match",
            source="user",
            occurred_at=datetime.now(timezone.utc),
            embedding=[1.0, 0.0, 0.0],
        )
        ep2 = Episode(
            group_id=group_id,
            content="Low match",
            source="user",
            occurred_at=datetime.now(timezone.utc),
            embedding=[0.0, 1.0, 0.0],
        )
        await store.add_episode(ep1)
        await store.add_episode(ep2)

        query = [1.0, 0.0, 0.0]
        results = await store.vector_search_episodes(query, group_id, min_score=0.9)
        assert len(results) == 1
        assert results[0][0].content == "High match"


class TestTextSearch:
    """Tests for text search functionality."""

    @pytest.mark.asyncio
    async def test_text_search_episodes(self, store, group_id):
        """Should search episodes by text content."""
        ep1 = Episode(
            group_id=group_id,
            content="Refund policy question",
            source="user",
            occurred_at=datetime.now(timezone.utc),
        )
        ep2 = Episode(
            group_id=group_id,
            content="Order status inquiry",
            source="user",
            occurred_at=datetime.now(timezone.utc),
        )
        await store.add_episode(ep1)
        await store.add_episode(ep2)

        results = await store.text_search_episodes("refund", group_id)
        assert len(results) == 1
        assert results[0].content == "Refund policy question"


class TestEntityOperations:
    """Tests for entity CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_get_entity(self, store, sample_entity, group_id):
        """Should add and retrieve an entity."""
        entity_id = await store.add_entity(sample_entity)
        retrieved = await store.get_entity(group_id, entity_id)

        assert retrieved is not None
        assert retrieved.name == "John Doe"

    @pytest.mark.asyncio
    async def test_get_entities_by_type(self, store, group_id):
        """Should filter entities by type."""
        person = Entity(group_id=group_id, name="John", entity_type="person", valid_from=datetime.now(timezone.utc))
        product = Entity(group_id=group_id, name="Widget", entity_type="product", valid_from=datetime.now(timezone.utc))
        await store.add_entity(person)
        await store.add_entity(product)

        results = await store.get_entities(group_id, entity_type="person")
        assert len(results) == 1
        assert results[0].name == "John"

    @pytest.mark.asyncio
    async def test_update_entity(self, store, sample_entity, group_id):
        """Should update an entity."""
        await store.add_entity(sample_entity)
        sample_entity.name = "Jane Doe"

        result = await store.update_entity(sample_entity)
        assert result is True

        retrieved = await store.get_entity(group_id, sample_entity.id)
        assert retrieved.name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_delete_entity(self, store, sample_entity, group_id):
        """Should delete an entity."""
        await store.add_entity(sample_entity)

        result = await store.delete_entity(group_id, sample_entity.id)
        assert result is True

        retrieved = await store.get_entity(group_id, sample_entity.id)
        assert retrieved is None


class TestRelationshipOperations:
    """Tests for relationship operations."""

    @pytest.mark.asyncio
    async def test_add_and_get_relationship(self, store, group_id):
        """Should add and retrieve relationships."""
        entity1 = Entity(group_id=group_id, name="Person", entity_type="person", valid_from=datetime.now(timezone.utc))
        entity2 = Entity(group_id=group_id, name="Company", entity_type="organization", valid_from=datetime.now(timezone.utc))
        await store.add_entity(entity1)
        await store.add_entity(entity2)

        rel = Relationship(
            group_id=group_id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relation_type="works_at",
            valid_from=datetime.now(timezone.utc),
        )
        await store.add_relationship(rel)

        results = await store.get_relationships(group_id, from_entity_id=entity1.id)
        assert len(results) == 1
        assert results[0].relation_type == "works_at"

    @pytest.mark.asyncio
    async def test_filter_relationships_by_type(self, store, group_id):
        """Should filter relationships by type."""
        entity1 = Entity(group_id=group_id, name="Person", entity_type="person", valid_from=datetime.now(timezone.utc))
        entity2 = Entity(group_id=group_id, name="Company", entity_type="organization", valid_from=datetime.now(timezone.utc))
        await store.add_entity(entity1)
        await store.add_entity(entity2)

        rel1 = Relationship(
            group_id=group_id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relation_type="works_at",
            valid_from=datetime.now(timezone.utc),
        )
        rel2 = Relationship(
            group_id=group_id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relation_type="owns",
            valid_from=datetime.now(timezone.utc),
        )
        await store.add_relationship(rel1)
        await store.add_relationship(rel2)

        results = await store.get_relationships(group_id, relation_type="works_at")
        assert len(results) == 1


class TestGraphTraversal:
    """Tests for graph traversal functionality."""

    @pytest.mark.asyncio
    async def test_traverse_from_entities(self, store, group_id):
        """Should traverse graph using BFS."""
        entity1 = Entity(group_id=group_id, name="A", entity_type="node", valid_from=datetime.now(timezone.utc))
        entity2 = Entity(group_id=group_id, name="B", entity_type="node", valid_from=datetime.now(timezone.utc))
        entity3 = Entity(group_id=group_id, name="C", entity_type="node", valid_from=datetime.now(timezone.utc))
        await store.add_entity(entity1)
        await store.add_entity(entity2)
        await store.add_entity(entity3)

        # A -> B -> C
        rel1 = Relationship(
            group_id=group_id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relation_type="connected",
            valid_from=datetime.now(timezone.utc),
        )
        rel2 = Relationship(
            group_id=group_id,
            from_entity_id=entity2.id,
            to_entity_id=entity3.id,
            relation_type="connected",
            valid_from=datetime.now(timezone.utc),
        )
        await store.add_relationship(rel1)
        await store.add_relationship(rel2)

        # Start from A, depth 2 should reach C
        results = await store.traverse_from_entities([entity1.id], group_id, depth=2)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_traverse_respects_depth(self, store, group_id):
        """Should respect depth limit."""
        entity1 = Entity(group_id=group_id, name="A", entity_type="node", valid_from=datetime.now(timezone.utc))
        entity2 = Entity(group_id=group_id, name="B", entity_type="node", valid_from=datetime.now(timezone.utc))
        entity3 = Entity(group_id=group_id, name="C", entity_type="node", valid_from=datetime.now(timezone.utc))
        await store.add_entity(entity1)
        await store.add_entity(entity2)
        await store.add_entity(entity3)

        rel1 = Relationship(
            group_id=group_id,
            from_entity_id=entity1.id,
            to_entity_id=entity2.id,
            relation_type="connected",
            valid_from=datetime.now(timezone.utc),
        )
        rel2 = Relationship(
            group_id=group_id,
            from_entity_id=entity2.id,
            to_entity_id=entity3.id,
            relation_type="connected",
            valid_from=datetime.now(timezone.utc),
        )
        await store.add_relationship(rel1)
        await store.add_relationship(rel2)

        # Start from A, depth 1 should only reach B
        results = await store.traverse_from_entities([entity1.id], group_id, depth=1)
        names = {e.name for e in results}
        assert "A" in names
        assert "B" in names
        assert "C" not in names


class TestBulkOperations:
    """Tests for bulk operations."""

    @pytest.mark.asyncio
    async def test_delete_by_group(self, store, group_id):
        """Should delete all items for a group."""
        ep = Episode(
            group_id=group_id,
            content="Test",
            source="user",
            occurred_at=datetime.now(timezone.utc),
        )
        entity = Entity(group_id=group_id, name="Test", entity_type="test", valid_from=datetime.now(timezone.utc))
        await store.add_episode(ep)
        await store.add_entity(entity)

        count = await store.delete_by_group(group_id)
        assert count == 2

        episodes = await store.get_episodes(group_id)
        entities = await store.get_entities(group_id)
        assert len(episodes) == 0
        assert len(entities) == 0
