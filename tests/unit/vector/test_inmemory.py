"""Tests for InMemoryVectorStore."""

from uuid import uuid4

import pytest

from ruche.vector import (
    EntityType,
    InMemoryVectorStore,
    VectorDocument,
    VectorMetadata,
)


class TestInMemoryVectorStore:
    """Tests for InMemoryVectorStore."""

    @pytest.fixture
    def store(self) -> InMemoryVectorStore:
        """Create an in-memory store."""
        return InMemoryVectorStore(dimensions=128)

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID."""
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        """Create an agent ID."""
        return uuid4()

    @pytest.fixture
    def sample_doc(self, tenant_id, agent_id):
        """Create a sample document."""
        entity_id = uuid4()
        return VectorDocument(
            id=VectorDocument.create_id(EntityType.RULE, entity_id),
            vector=[0.1] * 128,
            metadata=VectorMetadata(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=EntityType.RULE,
                entity_id=entity_id,
                enabled=True,
            ),
            text="Sample rule condition",
        )

    @pytest.mark.asyncio
    async def test_provider_name(self, store):
        """Should return correct provider name."""
        assert store.provider_name == "inmemory"

    @pytest.mark.asyncio
    async def test_upsert_and_get(self, store, sample_doc):
        """Should upsert and retrieve documents."""
        count = await store.upsert([sample_doc])
        assert count == 1

        docs = await store.get([sample_doc.id])
        assert len(docs) == 1
        assert docs[0].id == sample_doc.id
        assert docs[0].vector == sample_doc.vector

    @pytest.mark.asyncio
    async def test_search_by_similarity(self, store, tenant_id, agent_id):
        """Should find similar vectors."""
        # Create documents with different vectors
        docs = []
        for i in range(5):
            entity_id = uuid4()
            vec = [0.0] * 128
            vec[i] = 1.0  # Make each vector unique
            docs.append(
                VectorDocument(
                    id=VectorDocument.create_id(EntityType.RULE, entity_id),
                    vector=vec,
                    metadata=VectorMetadata(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        entity_type=EntityType.RULE,
                        entity_id=entity_id,
                        enabled=True,
                    ),
                )
            )

        await store.upsert(docs)

        # Search with a query similar to the first doc
        query = [0.0] * 128
        query[0] = 1.0

        results = await store.search(
            query_vector=query,
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=3,
        )

        assert len(results) == 3
        # First result should be most similar
        assert results[0].id == docs[0].id
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_search_filters_by_tenant(self, store, agent_id):
        """Should only return results from specified tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        # Create docs for different tenants
        for tenant_id in [tenant1, tenant2]:
            entity_id = uuid4()
            doc = VectorDocument(
                id=VectorDocument.create_id(EntityType.RULE, entity_id),
                vector=[0.1] * 128,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=EntityType.RULE,
                    entity_id=entity_id,
                    enabled=True,
                ),
            )
            await store.upsert([doc])

        # Search for tenant1 only
        results = await store.search(
            query_vector=[0.1] * 128,
            tenant_id=tenant1,
        )

        assert len(results) == 1
        assert results[0].metadata.tenant_id == tenant1

    @pytest.mark.asyncio
    async def test_search_filters_by_entity_type(self, store, tenant_id, agent_id):
        """Should filter by entity type."""
        # Create rule and scenario
        for entity_type in [EntityType.RULE, EntityType.SCENARIO]:
            entity_id = uuid4()
            doc = VectorDocument(
                id=VectorDocument.create_id(entity_type, entity_id),
                vector=[0.1] * 128,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    enabled=True,
                ),
            )
            await store.upsert([doc])

        # Search for rules only
        results = await store.search(
            query_vector=[0.1] * 128,
            tenant_id=tenant_id,
            entity_types=[EntityType.RULE],
        )

        assert len(results) == 1
        assert results[0].metadata.entity_type == EntityType.RULE

    @pytest.mark.asyncio
    async def test_search_excludes_disabled(self, store, tenant_id, agent_id):
        """Should exclude disabled entities."""
        # Create enabled and disabled docs
        for enabled in [True, False]:
            entity_id = uuid4()
            doc = VectorDocument(
                id=VectorDocument.create_id(EntityType.RULE, entity_id),
                vector=[0.1] * 128,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=EntityType.RULE,
                    entity_id=entity_id,
                    enabled=enabled,
                ),
            )
            await store.upsert([doc])

        results = await store.search(
            query_vector=[0.1] * 128,
            tenant_id=tenant_id,
        )

        assert len(results) == 1
        assert results[0].metadata.enabled is True

    @pytest.mark.asyncio
    async def test_search_min_score(self, store, tenant_id, agent_id):
        """Should filter by minimum score."""
        # Create docs with varying similarity
        for i in range(5):
            entity_id = uuid4()
            vec = [0.1] * 128
            vec[0] = float(i) / 10.0  # Varying similarity
            doc = VectorDocument(
                id=VectorDocument.create_id(EntityType.RULE, entity_id),
                vector=vec,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=EntityType.RULE,
                    entity_id=entity_id,
                    enabled=True,
                ),
            )
            await store.upsert([doc])

        results = await store.search(
            query_vector=[0.1] * 128,
            tenant_id=tenant_id,
            min_score=0.9,
        )

        for result in results:
            assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_delete_by_id(self, store, sample_doc):
        """Should delete by ID."""
        await store.upsert([sample_doc])

        deleted = await store.delete([sample_doc.id])
        assert deleted == 1

        docs = await store.get([sample_doc.id])
        assert len(docs) == 0

    @pytest.mark.asyncio
    async def test_delete_by_filter(self, store, tenant_id, agent_id):
        """Should delete by filter criteria."""
        # Create multiple docs
        for _ in range(3):
            entity_id = uuid4()
            doc = VectorDocument(
                id=VectorDocument.create_id(EntityType.RULE, entity_id),
                vector=[0.1] * 128,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=EntityType.RULE,
                    entity_id=entity_id,
                    enabled=True,
                ),
            )
            await store.upsert([doc])

        deleted = await store.delete_by_filter(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert deleted == 3

        count = await store.count(tenant_id=tenant_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_count(self, store, tenant_id, agent_id):
        """Should count vectors."""
        # Create docs
        for entity_type in [EntityType.RULE, EntityType.RULE, EntityType.SCENARIO]:
            entity_id = uuid4()
            doc = VectorDocument(
                id=VectorDocument.create_id(entity_type, entity_id),
                vector=[0.1] * 128,
                metadata=VectorMetadata(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    enabled=True,
                ),
            )
            await store.upsert([doc])

        total = await store.count(tenant_id=tenant_id)
        assert total == 3

        rules = await store.count(tenant_id=tenant_id, entity_type=EntityType.RULE)
        assert rules == 2

    @pytest.mark.asyncio
    async def test_ensure_and_delete_collection(self, store):
        """Should create and delete collections."""
        await store.ensure_collection("test", dimensions=128)

        entity_id = uuid4()
        doc = VectorDocument(
            id=VectorDocument.create_id(EntityType.RULE, entity_id),
            vector=[0.1] * 128,
            metadata=VectorMetadata(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                entity_type=EntityType.RULE,
                entity_id=entity_id,
                enabled=True,
            ),
        )
        await store.upsert([doc], collection="test")

        deleted = await store.delete_collection("test")
        assert deleted is True

        count = await store.count(collection="test")
        assert count == 0

    @pytest.mark.asyncio
    async def test_clear(self, store, sample_doc):
        """Should clear all collections."""
        await store.upsert([sample_doc])
        store.clear()

        docs = await store.get([sample_doc.id])
        assert len(docs) == 0

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, store, tenant_id, agent_id):
        """Should overwrite existing vectors."""
        entity_id = uuid4()
        doc_id = VectorDocument.create_id(EntityType.RULE, entity_id)

        # Create initial doc
        doc1 = VectorDocument(
            id=doc_id,
            vector=[0.1] * 128,
            metadata=VectorMetadata(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=EntityType.RULE,
                entity_id=entity_id,
                enabled=True,
            ),
            text="Original text",
        )
        await store.upsert([doc1])

        # Update with new vector
        doc2 = VectorDocument(
            id=doc_id,
            vector=[0.9] * 128,
            metadata=VectorMetadata(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=EntityType.RULE,
                entity_id=entity_id,
                enabled=True,
            ),
            text="Updated text",
        )
        await store.upsert([doc2])

        docs = await store.get([doc_id])
        assert len(docs) == 1
        assert docs[0].vector == [0.9] * 128
        assert docs[0].text == "Updated text"
