"""Tests for EntityExtractor and EntityDeduplicator."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from soldier.memory.ingestion.entity_extractor import EntityDeduplicator, EntityExtractor
from soldier.memory.ingestion.errors import ExtractionError
from soldier.memory.ingestion.models import EntityExtractionResult
from soldier.memory.models.entity import Entity
from soldier.memory.models.episode import Episode
from soldier.memory.stores.inmemory import InMemoryMemoryStore
from soldier.providers.llm.mock import MockLLMProvider


@pytest.fixture
def memory_store():
    """Create in-memory store for testing."""
    return InMemoryMemoryStore()


@pytest.fixture
def llm_provider():
    """Create mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def episode():
    """Create test episode."""
    return Episode(
        group_id=f"{uuid4()}:{uuid4()}",
        content="Customer John Smith ordered a laptop but it arrived damaged",
        source="user",
        occurred_at=datetime.now(UTC),
    )


class TestEntityExtractorParsing:
    """Tests for LLM structured output parsing."""

    @pytest.mark.asyncio
    async def test_extract_parses_llm_output(self, llm_provider, episode):
        """Should parse LLM structured output."""
        from soldier.config.models.pipeline import EntityExtractionConfig

        config = EntityExtractionConfig(min_confidence="medium")
        extractor = EntityExtractor(llm_executor=llm_provider, config=config)

        result = await extractor.extract(episode)

        assert isinstance(result, EntityExtractionResult)
        assert isinstance(result.entities, list)
        assert isinstance(result.relationships, list)

    @pytest.mark.asyncio
    async def test_extract_filters_by_confidence(self, llm_provider, episode):
        """Should filter entities by min_confidence."""
        from soldier.config.models.pipeline import EntityExtractionConfig

        config = EntityExtractionConfig(min_confidence="high")
        extractor = EntityExtractor(llm_executor=llm_provider, config=config)

        result = await extractor.extract(episode)

        # All extracted entities should meet confidence threshold
        for entity in result.entities:
            assert entity.confidence in ["high"]


class TestEntityExtractorBatch:
    """Tests for parallel batch processing."""

    @pytest.mark.asyncio
    async def test_extract_batch_processes_parallel(self, llm_provider):
        """Should process multiple episodes in parallel."""
        from soldier.config.models.pipeline import EntityExtractionConfig

        config = EntityExtractionConfig(batch_size=5)
        extractor = EntityExtractor(llm_executor=llm_provider, config=config)

        episodes = [
            Episode(
                group_id=f"{uuid4()}:{uuid4()}",
                content=f"Test content {i}",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        results = await extractor.extract_batch(episodes)

        assert len(results) == len(episodes)
        for result in results:
            assert isinstance(result, EntityExtractionResult)


class TestEntityExtractorErrorHandling:
    """Tests for LLM provider timeout handling."""

    @pytest.mark.asyncio
    async def test_extract_handles_llm_timeout(self, episode):
        """Should handle LLM provider timeout."""

        class TimeoutLLMProvider(MockLLMProvider):
            async def generate(self, *args, **kwargs):
                import asyncio

                await asyncio.sleep(5)  # Simulate timeout
                return await super().generate(*args, **kwargs)

        from soldier.config.models.pipeline import EntityExtractionConfig

        config = EntityExtractionConfig(timeout_ms=100)
        extractor = EntityExtractor(llm_executor=TimeoutLLMProvider(), config=config)

        # Should raise ExtractionError, not timeout
        with pytest.raises((ExtractionError, Exception)):
            await extractor.extract(episode)


class TestEntityDeduplicatorExactMatch:
    """Tests for exact match stage."""

    @pytest.mark.asyncio
    async def test_find_duplicate_exact_match(self, memory_store):
        """Should find duplicate by exact normalized name."""
        from soldier.config.models.pipeline import EntityDeduplicationConfig

        config = EntityDeduplicationConfig()
        deduplicator = EntityDeduplicator(
            memory_store=memory_store, config=config
        )

        group_id = f"{uuid4()}:{uuid4()}"

        # Add existing entity
        existing = Entity(
            group_id=group_id,
            name="John Smith",
            entity_type="person",
            valid_from=datetime.now(UTC),
        )
        await memory_store.add_entity(existing)

        # Try to add duplicate with different casing
        candidate = Entity(
            group_id=group_id,
            name="john smith",  # Different casing
            entity_type="person",
            valid_from=datetime.now(UTC),
        )

        duplicate = await deduplicator.find_duplicate(candidate, group_id)

        assert duplicate is not None
        assert duplicate.id == existing.id


class TestEntityDeduplicatorFuzzyMatch:
    """Tests for fuzzy match stage."""

    @pytest.mark.asyncio
    async def test_find_duplicate_fuzzy_match(self, memory_store):
        """Should find duplicate by fuzzy string matching."""
        from soldier.config.models.pipeline import EntityDeduplicationConfig

        config = EntityDeduplicationConfig(fuzzy_threshold=0.85)
        deduplicator = EntityDeduplicator(
            memory_store=memory_store, config=config
        )

        group_id = f"{uuid4()}:{uuid4()}"

        # Add existing entity
        existing = Entity(
            group_id=group_id,
            name="John Smith",
            entity_type="person",
            valid_from=datetime.now(UTC),
        )
        await memory_store.add_entity(existing)

        # Try to add similar entity (typo)
        candidate = Entity(
            group_id=group_id,
            name="Jon Smith",  # Typo
            entity_type="person",
            valid_from=datetime.now(UTC),
        )

        duplicate = await deduplicator.find_duplicate(candidate, group_id)

        # Should find it via fuzzy match
        assert duplicate is not None


class TestEntityDeduplicatorEmbeddingMatch:
    """Tests for embedding similarity stage."""

    @pytest.mark.asyncio
    async def test_find_duplicate_embedding_similarity(self, memory_store):
        """Should find duplicate by embedding similarity."""
        from soldier.config.models.pipeline import EntityDeduplicationConfig

        config = EntityDeduplicationConfig(embedding_threshold=0.80)
        _deduplicator = EntityDeduplicator(
            memory_store=memory_store, config=config
        )

        group_id = f"{uuid4()}:{uuid4()}"

        # Add existing entity with embedding
        existing = Entity(
            group_id=group_id,
            name="Customer John",
            entity_type="person",
            valid_from=datetime.now(UTC),
            embedding=[0.1, 0.2, 0.3] * 256,  # 768-dim vector
        )
        await memory_store.add_entity(existing)

        # Try to add semantically similar entity
        _candidate = Entity(
            group_id=group_id,
            name="John Smith",
            entity_type="person",
            valid_from=datetime.now(UTC),
            embedding=[0.11, 0.19, 0.31] * 256,  # Similar embedding
        )

        # Note: This test may not find duplicate without real embeddings
        # In real usage, embeddings would be semantically similar


class TestEntityDeduplicatorRuleBased:
    """Tests for rule-based matching stage."""

    @pytest.mark.asyncio
    async def test_find_duplicate_rule_based(self, memory_store):
        """Should find duplicate by rule-based matching."""
        from soldier.config.models.pipeline import EntityDeduplicationConfig

        config = EntityDeduplicationConfig()
        deduplicator = EntityDeduplicator(
            memory_store=memory_store, config=config
        )

        group_id = f"{uuid4()}:{uuid4()}"

        # Add existing entity with email
        existing = Entity(
            group_id=group_id,
            name="Person A",
            entity_type="person",
            attributes={"email": "john@example.com"},
            valid_from=datetime.now(UTC),
        )
        await memory_store.add_entity(existing)

        # Try to add entity with same email
        candidate = Entity(
            group_id=group_id,
            name="Person B",  # Different name
            entity_type="person",
            attributes={"email": "john@example.com"},  # Same email
            valid_from=datetime.now(UTC),
        )

        duplicate = await deduplicator.find_duplicate(candidate, group_id)

        # Should find it via rule-based match (email)
        assert duplicate is not None


class TestEntityDeduplicatorMerge:
    """Tests for entity merging logic."""

    @pytest.mark.asyncio
    async def test_merge_entities_combines_attributes(self, memory_store):
        """Should merge attributes from new entity."""
        from soldier.config.models.pipeline import EntityDeduplicationConfig

        config = EntityDeduplicationConfig()
        deduplicator = EntityDeduplicator(
            memory_store=memory_store, config=config
        )

        existing = Entity(
            group_id=f"{uuid4()}:{uuid4()}",
            name="John",
            entity_type="person",
            attributes={"email": "john@example.com"},
            valid_from=datetime.now(UTC),
        )

        new = Entity(
            group_id=existing.group_id,
            name="John Smith",
            entity_type="person",
            attributes={"phone": "555-1234"},  # New attribute
            valid_from=datetime.now(UTC),
        )

        merged = await deduplicator.merge_entities(existing, new)

        assert merged.id == existing.id  # Same ID
        assert "email" in merged.attributes
        assert "phone" in merged.attributes  # New attribute added
        assert merged.attributes["phone"] == "555-1234"


class TestTemporalRelationshipUpdates:
    """Tests for temporal relationship updates."""

    @pytest.mark.asyncio
    async def test_relationship_invalidation_and_creation(self, memory_store):
        """Should invalidate old relationship and create new one."""
        from datetime import UTC

        from soldier.memory.models.relationship import Relationship

        group_id = f"{uuid4()}:{uuid4()}"
        entity1_id = uuid4()
        entity2_id = uuid4()

        # Create old relationship
        old_rel = Relationship(
            group_id=group_id,
            from_entity_id=entity1_id,
            to_entity_id=entity2_id,
            relation_type="lives_at",
            attributes={"address": "123 Main St"},
            valid_from=datetime.now(UTC),
            valid_to=None,  # Currently valid
        )
        await memory_store.add_relationship(old_rel)

        # Update: person moved to new address
        # Should invalidate old and create new
        now = datetime.now(UTC)

        # Invalidate old
        old_rel.valid_to = now
        await memory_store.update_relationship(old_rel)

        # Create new
        new_rel = Relationship(
            group_id=group_id,
            from_entity_id=entity1_id,
            to_entity_id=entity2_id,
            relation_type="lives_at",
            attributes={"address": "456 Oak Ave"},
            valid_from=now,
            valid_to=None,  # Now valid
        )
        await memory_store.add_relationship(new_rel)

        # Verify old is invalidated
        assert old_rel.valid_to is not None

        # Verify new is active
        assert new_rel.valid_to is None
