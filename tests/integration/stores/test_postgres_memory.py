"""Integration tests for PostgresMemoryStore.

Tests CRUD operations, vector search, and graph traversal
against a real PostgreSQL database with pgvector.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from ruche.memory.models import Entity, Episode, Relationship
from ruche.memory.stores.postgres import PostgresMemoryStore


@pytest_asyncio.fixture
async def memory_store(postgres_pool):
    """Create PostgresMemoryStore with test pool."""
    return PostgresMemoryStore(postgres_pool)


@pytest.fixture
def sample_episode():
    """Create a sample episode for testing."""
    return Episode(
        id=uuid4(),
        group_id="tenant1:session1",
        content="The user mentioned they prefer Python programming",
        content_type="message",
        source="user",
        source_metadata={"turn": 1},
        occurred_at=datetime.now(UTC),
        embedding=[0.1, 0.2, 0.3] * 512,  # 1536 dimensions
        embedding_model="text-embedding-3-small",
    )


@pytest.fixture
def sample_entity():
    """Create a sample entity for testing."""
    return Entity(
        id=uuid4(),
        group_id="tenant1",
        name="Python",
        entity_type="programming_language",
        attributes={"paradigm": "multi-paradigm", "typed": "dynamic"},
        valid_from=datetime.now(UTC),
    )


@pytest.fixture
def sample_relationship(sample_entity):
    """Create a sample relationship for testing."""
    target_entity_id = uuid4()
    return Relationship(
        id=uuid4(),
        group_id="tenant1",
        from_entity_id=sample_entity.id,
        to_entity_id=target_entity_id,
        relation_type="PREFERS",
        attributes={"context": "user preference"},
        valid_from=datetime.now(UTC),
    )


@pytest.mark.integration
class TestPostgresMemoryStoreEpisode:
    """Test episode CRUD operations."""

    async def test_add_and_get_episode(
        self, memory_store, sample_episode, clean_postgres
    ):
        """Test adding and retrieving an episode."""
        # Add
        episode_id = await memory_store.add_episode(sample_episode)
        assert episode_id == sample_episode.id

        # Get
        retrieved = await memory_store.get_episode(
            sample_episode.group_id, sample_episode.id
        )
        assert retrieved is not None
        assert retrieved.content == sample_episode.content
        assert retrieved.content_type == sample_episode.content_type

    async def test_get_episodes_by_group(
        self, memory_store, clean_postgres
    ):
        """Test listing episodes by group."""
        group_id = "tenant1:session1"

        # Create multiple episodes
        for i in range(3):
            episode = Episode(
                id=uuid4(),
                group_id=group_id,
                content=f"Episode content {i}",
                content_type="message",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            await memory_store.add_episode(episode)

        # Get episodes
        episodes = await memory_store.get_episodes(group_id, limit=10)
        assert len(episodes) == 3

    async def test_delete_episode(
        self, memory_store, sample_episode, clean_postgres
    ):
        """Test deleting an episode."""
        await memory_store.add_episode(sample_episode)

        # Delete
        deleted = await memory_store.delete_episode(
            sample_episode.group_id, sample_episode.id
        )
        assert deleted is True

        # Should not be found
        retrieved = await memory_store.get_episode(
            sample_episode.group_id, sample_episode.id
        )
        assert retrieved is None

    async def test_text_search_episodes(
        self, memory_store, clean_postgres
    ):
        """Test text search on episode content."""
        group_id = "tenant1:session1"

        # Create episodes with different content
        episode1 = Episode(
            id=uuid4(),
            group_id=group_id,
            content="User loves Python programming",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
        )
        episode2 = Episode(
            id=uuid4(),
            group_id=group_id,
            content="User prefers JavaScript",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
        )

        await memory_store.add_episode(episode1)
        await memory_store.add_episode(episode2)

        # Search for Python
        results = await memory_store.text_search_episodes("Python", group_id)
        assert len(results) == 1
        assert "Python" in results[0].content


@pytest.mark.integration
class TestPostgresMemoryStoreEntity:
    """Test entity CRUD operations."""

    async def test_add_and_get_entity(
        self, memory_store, sample_entity, clean_postgres
    ):
        """Test adding and retrieving an entity."""
        # Add
        entity_id = await memory_store.add_entity(sample_entity)
        assert entity_id == sample_entity.id

        # Get
        retrieved = await memory_store.get_entity(
            sample_entity.group_id, sample_entity.id
        )
        assert retrieved is not None
        assert retrieved.name == sample_entity.name
        assert retrieved.entity_type == sample_entity.entity_type

    async def test_get_entities_by_type(
        self, memory_store, clean_postgres
    ):
        """Test filtering entities by type."""
        group_id = "tenant1"

        # Create entities with different types
        entity1 = Entity(
            id=uuid4(),
            group_id=group_id,
            name="Python",
            entity_type="programming_language",
            valid_from=datetime.now(UTC),
        )
        entity2 = Entity(
            id=uuid4(),
            group_id=group_id,
            name="Alice",
            entity_type="person",
            valid_from=datetime.now(UTC),
        )

        await memory_store.add_entity(entity1)
        await memory_store.add_entity(entity2)

        # Filter by type
        languages = await memory_store.get_entities(
            group_id, entity_type="programming_language"
        )
        assert len(languages) == 1
        assert languages[0].name == "Python"

    async def test_update_entity(
        self, memory_store, sample_entity, clean_postgres
    ):
        """Test updating an entity."""
        await memory_store.add_entity(sample_entity)

        # Update
        sample_entity.name = "Python 3"
        sample_entity.attributes["version"] = "3.11"
        updated = await memory_store.update_entity(sample_entity)
        assert updated is True

        # Verify update
        retrieved = await memory_store.get_entity(
            sample_entity.group_id, sample_entity.id
        )
        assert retrieved.name == "Python 3"
        assert retrieved.attributes["version"] == "3.11"

    async def test_delete_entity(
        self, memory_store, sample_entity, clean_postgres
    ):
        """Test deleting an entity."""
        await memory_store.add_entity(sample_entity)

        # Delete
        deleted = await memory_store.delete_entity(
            sample_entity.group_id, sample_entity.id
        )
        assert deleted is True

        # Should not be found
        retrieved = await memory_store.get_entity(
            sample_entity.group_id, sample_entity.id
        )
        assert retrieved is None


@pytest.mark.integration
class TestPostgresMemoryStoreRelationship:
    """Test relationship CRUD operations."""

    async def test_add_and_get_relationship(
        self, memory_store, sample_entity, sample_relationship, clean_postgres
    ):
        """Test adding and retrieving a relationship."""
        # First add the source entity
        await memory_store.add_entity(sample_entity)

        # Add relationship
        rel_id = await memory_store.add_relationship(sample_relationship)
        assert rel_id == sample_relationship.id

        # Get relationship
        retrieved = await memory_store.get_relationship(
            sample_relationship.group_id, sample_relationship.id
        )
        assert retrieved is not None
        assert retrieved.relation_type == sample_relationship.relation_type

    async def test_get_relationships_by_source(
        self, memory_store, clean_postgres
    ):
        """Test getting relationships by source entity."""
        group_id = "tenant1"

        # Create entities
        source = Entity(
            id=uuid4(),
            group_id=group_id,
            name="User",
            entity_type="person",
            valid_from=datetime.now(UTC),
        )
        target1 = Entity(
            id=uuid4(),
            group_id=group_id,
            name="Python",
            entity_type="programming_language",
            valid_from=datetime.now(UTC),
        )
        target2 = Entity(
            id=uuid4(),
            group_id=group_id,
            name="JavaScript",
            entity_type="programming_language",
            valid_from=datetime.now(UTC),
        )

        await memory_store.add_entity(source)
        await memory_store.add_entity(target1)
        await memory_store.add_entity(target2)

        # Create relationships
        rel1 = Relationship(
            id=uuid4(),
            group_id=group_id,
            from_entity_id=source.id,
            to_entity_id=target1.id,
            relation_type="KNOWS",
            valid_from=datetime.now(UTC),
        )
        rel2 = Relationship(
            id=uuid4(),
            group_id=group_id,
            from_entity_id=source.id,
            to_entity_id=target2.id,
            relation_type="KNOWS",
            valid_from=datetime.now(UTC),
        )

        await memory_store.add_relationship(rel1)
        await memory_store.add_relationship(rel2)

        # Get relationships from source
        relationships = await memory_store.get_relationships(
            group_id, from_entity_id=source.id
        )
        assert len(relationships) == 2

    async def test_delete_relationship(
        self, memory_store, sample_entity, sample_relationship, clean_postgres
    ):
        """Test deleting a relationship."""
        await memory_store.add_entity(sample_entity)
        await memory_store.add_relationship(sample_relationship)

        # Delete
        deleted = await memory_store.delete_relationship(
            sample_relationship.group_id, sample_relationship.id
        )
        assert deleted is True

        # Should not be found
        retrieved = await memory_store.get_relationship(
            sample_relationship.group_id, sample_relationship.id
        )
        assert retrieved is None


@pytest.mark.integration
class TestPostgresMemoryStoreGroupIsolation:
    """Test group isolation."""

    async def test_group_isolation_episodes(
        self, memory_store, clean_postgres
    ):
        """Test that episodes are isolated by group."""
        group1 = "tenant1:session1"
        group2 = "tenant2:session2"

        episode1 = Episode(
            id=uuid4(),
            group_id=group1,
            content="Group 1 episode",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
        )
        episode2 = Episode(
            id=uuid4(),
            group_id=group2,
            content="Group 2 episode",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
        )

        await memory_store.add_episode(episode1)
        await memory_store.add_episode(episode2)

        # Group 1 should only see their episode
        episodes1 = await memory_store.get_episodes(group1)
        assert len(episodes1) == 1
        assert episodes1[0].content == "Group 1 episode"

        # Group 2 should only see their episode
        episodes2 = await memory_store.get_episodes(group2)
        assert len(episodes2) == 1
        assert episodes2[0].content == "Group 2 episode"

    async def test_group_isolation_entities(
        self, memory_store, clean_postgres
    ):
        """Test that entities are isolated by group."""
        group1 = "tenant1"
        group2 = "tenant2"

        entity1 = Entity(
            id=uuid4(),
            group_id=group1,
            name="Group 1 Entity",
            entity_type="test",
            valid_from=datetime.now(UTC),
        )
        entity2 = Entity(
            id=uuid4(),
            group_id=group2,
            name="Group 2 Entity",
            entity_type="test",
            valid_from=datetime.now(UTC),
        )

        await memory_store.add_entity(entity1)
        await memory_store.add_entity(entity2)

        # Group 1 should only see their entity
        entities1 = await memory_store.get_entities(group1)
        assert len(entities1) == 1
        assert entities1[0].name == "Group 1 Entity"

        # Group 2 should only see their entity
        entities2 = await memory_store.get_entities(group2)
        assert len(entities2) == 1
        assert entities2[0].name == "Group 2 Entity"

        # Cross-group access should fail
        cross = await memory_store.get_entity(group2, entity1.id)
        assert cross is None


@pytest.mark.integration
class TestPostgresMemoryStoreVectorSearch:
    """Test vector similarity search."""

    async def test_vector_search_episodes(
        self, memory_store, clean_postgres
    ):
        """Test vector similarity search on episodes."""
        group_id = "tenant1:session1"

        # Create episodes with embeddings
        episode1 = Episode(
            id=uuid4(),
            group_id=group_id,
            content="Python is a great language",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
            embedding=[0.1] * 1536,  # Simple test embedding
            embedding_model="test",
        )
        episode2 = Episode(
            id=uuid4(),
            group_id=group_id,
            content="JavaScript is versatile",
            content_type="message",
            source="user",
            occurred_at=datetime.now(UTC),
            embedding=[0.9] * 1536,  # Different embedding
            embedding_model="test",
        )

        await memory_store.add_episode(episode1)
        await memory_store.add_episode(episode2)

        # Search with embedding similar to episode1
        query_embedding = [0.1] * 1536
        results = await memory_store.vector_search_episodes(
            query_embedding, group_id, limit=2
        )

        # Episode1 should be more similar (higher score)
        assert len(results) >= 1
        # First result should have score >= 0
        episode, score = results[0]
        assert score >= 0


@pytest.mark.integration
class TestPostgresMemoryStoreBulkOperations:
    """Test bulk operations."""

    async def test_delete_by_group(
        self, memory_store, clean_postgres
    ):
        """Test deleting all data for a group."""
        group_id = "tenant1:session1"

        # Create episodes
        for i in range(3):
            episode = Episode(
                id=uuid4(),
                group_id=group_id,
                content=f"Episode {i}",
                content_type="message",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            await memory_store.add_episode(episode)

        # Create entities
        for i in range(2):
            entity = Entity(
                id=uuid4(),
                group_id=group_id,
                name=f"Entity {i}",
                entity_type="test",
                valid_from=datetime.now(UTC),
            )
            await memory_store.add_entity(entity)

        # Delete all
        deleted_count = await memory_store.delete_by_group(group_id)
        assert deleted_count >= 5

        # Verify deletion
        episodes = await memory_store.get_episodes(group_id)
        entities = await memory_store.get_entities(group_id)

        assert len(episodes) == 0
        assert len(entities) == 0
