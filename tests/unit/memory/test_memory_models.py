"""Tests for memory domain models."""

from datetime import UTC, datetime
from uuid import uuid4

from soldier.memory.models import Entity, Episode, Relationship


class TestEpisode:
    """Tests for Episode model."""

    def test_create_valid_episode(self) -> None:
        """Should create a valid episode."""
        episode = Episode(
            group_id="tenant:session",
            content="User mentioned order #12345",
            source="user",
            occurred_at=datetime.now(UTC),
        )
        assert episode.content == "User mentioned order #12345"
        assert episode.source == "user"
        assert episode.content_type == "message"

    def test_episode_with_embedding(self) -> None:
        """Should create episode with embedding."""
        episode = Episode(
            group_id="tenant:session",
            content="Test content",
            source="agent",
            occurred_at=datetime.now(UTC),
            embedding=[0.1, 0.2, 0.3],
            embedding_model="test-model",
        )
        assert episode.embedding == [0.1, 0.2, 0.3]
        assert episode.embedding_model == "test-model"

    def test_episode_auto_sets_recorded_at(self) -> None:
        """Should automatically set recorded_at."""
        episode = Episode(
            group_id="tenant:session",
            content="Test",
            source="system",
            occurred_at=datetime.now(UTC),
        )
        assert episode.recorded_at is not None

    def test_episode_with_entity_links(self) -> None:
        """Should create episode with entity links."""
        entity_ids = [uuid4(), uuid4()]
        episode = Episode(
            group_id="tenant:session",
            content="Test",
            source="agent",
            occurred_at=datetime.now(UTC),
            entity_ids=entity_ids,
        )
        assert len(episode.entity_ids) == 2


class TestEntity:
    """Tests for Entity model."""

    def test_create_valid_entity(self) -> None:
        """Should create a valid entity."""
        entity = Entity(
            group_id="tenant:session",
            name="Order #12345",
            entity_type="order",
            valid_from=datetime.now(UTC),
        )
        assert entity.name == "Order #12345"
        assert entity.entity_type == "order"
        assert entity.valid_to is None

    def test_entity_with_attributes(self) -> None:
        """Should create entity with attributes."""
        entity = Entity(
            group_id="tenant:session",
            name="John Doe",
            entity_type="person",
            attributes={"email": "john@example.com", "role": "customer"},
            valid_from=datetime.now(UTC),
        )
        assert entity.attributes["email"] == "john@example.com"
        assert entity.attributes["role"] == "customer"

    def test_entity_temporal_validity(self) -> None:
        """Should track temporal validity."""
        valid_from = datetime.now(UTC)
        entity = Entity(
            group_id="tenant:session",
            name="Test",
            entity_type="test",
            valid_from=valid_from,
            valid_to=datetime.now(UTC),
        )
        assert entity.valid_from == valid_from
        assert entity.valid_to is not None


class TestRelationship:
    """Tests for Relationship model."""

    def test_create_valid_relationship(self) -> None:
        """Should create a valid relationship."""
        from_id = uuid4()
        to_id = uuid4()
        relationship = Relationship(
            group_id="tenant:session",
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type="ordered",
            valid_from=datetime.now(UTC),
        )
        assert relationship.from_entity_id == from_id
        assert relationship.to_entity_id == to_id
        assert relationship.relation_type == "ordered"

    def test_relationship_with_attributes(self) -> None:
        """Should create relationship with attributes."""
        relationship = Relationship(
            group_id="tenant:session",
            from_entity_id=uuid4(),
            to_entity_id=uuid4(),
            relation_type="owns",
            attributes={"quantity": 2, "status": "active"},
            valid_from=datetime.now(UTC),
        )
        assert relationship.attributes["quantity"] == 2
        assert relationship.attributes["status"] == "active"
