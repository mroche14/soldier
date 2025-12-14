"""Embedding manager for entity embeddings.

Handles all embedding operations for entities (rules, scenarios, episodes):
- Generating embeddings via configured provider
- Storing embeddings in vector store for similarity search
- Batch operations for migrations
- Cleanup on entity deletion
"""

from uuid import UUID

from focal.alignment.models import Rule, Scenario
from focal.memory.models import Episode
from focal.observability.logging import get_logger
from focal.providers.embedding import EmbeddingProvider
from focal.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorStore,
)

logger = get_logger(__name__)


class EmbeddingManager:
    """Manages embeddings for entities (rules, scenarios, episodes).

    Responsibilities:
    - Generate embeddings using configured provider
    - Store/update embeddings in vector store
    - Delete embeddings when entities are removed
    - Batch sync for migrations

    Acts as the single source of truth for embedding operations,
    bridging entity storage (AgentConfigStore, MemoryStore) with
    vector storage (VectorStore).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        *,
        collection: str = "default",
    ):
        """Initialize embedding manager.

        Args:
            vector_store: Vector storage backend
            embedding_provider: Embedding generation provider
            collection: Default collection name
        """
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._collection = collection

    async def sync_rule(
        self,
        rule: Rule,
        *,
        generate_embedding: bool = True,
    ) -> None:
        """Sync a rule's embedding to vector store.

        Args:
            rule: Rule to sync
            generate_embedding: Whether to generate embedding if missing
        """
        vector = rule.condition_embedding

        # Generate embedding if needed
        if vector is None and generate_embedding:
            vector = await self._embedding_provider.embed_single(
                rule.condition_text,
                task="retrieval.passage",
            )
            logger.debug(
                "generated_rule_embedding",
                rule_id=str(rule.id),
                dimensions=len(vector),
            )

        if vector is None:
            logger.warning(
                "rule_has_no_embedding",
                rule_id=str(rule.id),
            )
            return

        doc = VectorDocument(
            id=VectorDocument.create_id(EntityType.RULE, rule.id),
            vector=vector,
            metadata=VectorMetadata(
                tenant_id=rule.tenant_id,
                agent_id=rule.agent_id,
                entity_type=EntityType.RULE,
                entity_id=rule.id,
                scope=rule.scope.value if rule.scope else None,
                scope_id=rule.scope_id,
                enabled=rule.enabled,
                embedding_model=rule.embedding_model,
            ),
            text=rule.condition_text,
        )

        await self._vector_store.upsert([doc], collection=self._collection)

        logger.debug(
            "rule_synced_to_vector_store",
            rule_id=str(rule.id),
            collection=self._collection,
        )

    async def sync_scenario(
        self,
        scenario: Scenario,
        *,
        generate_embedding: bool = True,
    ) -> None:
        """Sync a scenario's entry embedding to vector store.

        Args:
            scenario: Scenario to sync
            generate_embedding: Whether to generate embedding if missing
        """
        vector = scenario.entry_embedding

        # Generate embedding if needed
        if vector is None and generate_embedding and scenario.entry_condition:
            vector = await self._embedding_provider.embed_single(
                scenario.entry_condition,
                task="retrieval.passage",
            )
            logger.debug(
                "generated_scenario_embedding",
                scenario_id=str(scenario.id),
                dimensions=len(vector),
            )

        if vector is None:
            logger.warning(
                "scenario_has_no_embedding",
                scenario_id=str(scenario.id),
            )
            return

        doc = VectorDocument(
            id=VectorDocument.create_id(EntityType.SCENARIO, scenario.id),
            vector=vector,
            metadata=VectorMetadata(
                tenant_id=scenario.tenant_id,
                agent_id=scenario.agent_id,
                entity_type=EntityType.SCENARIO,
                entity_id=scenario.id,
                enabled=scenario.enabled,
                extra={"version": scenario.version},
            ),
            text=scenario.entry_condition,
        )

        await self._vector_store.upsert([doc], collection=self._collection)

        logger.debug(
            "scenario_synced_to_vector_store",
            scenario_id=str(scenario.id),
            collection=self._collection,
        )

    async def sync_episode(
        self,
        episode: Episode,
        *,
        generate_embedding: bool = True,
    ) -> None:
        """Sync an episode's embedding to vector store.

        Args:
            episode: Episode to sync
            generate_embedding: Whether to generate embedding if missing
        """
        vector = episode.embedding

        # Generate embedding if needed
        if vector is None and generate_embedding:
            # Combine user message and agent response for embedding
            text = f"{episode.user_message}\n{episode.agent_response or ''}"
            vector = await self._embedding_provider.embed_single(
                text,
                task="retrieval.passage",
            )
            logger.debug(
                "generated_episode_embedding",
                episode_id=str(episode.id),
                dimensions=len(vector),
            )

        if vector is None:
            logger.warning(
                "episode_has_no_embedding",
                episode_id=str(episode.id),
            )
            return

        # Parse group_id to get tenant_id and agent_id
        parts = episode.group_id.split(":")
        tenant_id = UUID(parts[0])
        agent_id = UUID(parts[1]) if len(parts) > 1 else tenant_id

        doc = VectorDocument(
            id=VectorDocument.create_id(EntityType.EPISODE, episode.id),
            vector=vector,
            metadata=VectorMetadata(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=EntityType.EPISODE,
                entity_id=episode.id,
                embedding_model=episode.embedding_model,
                extra={
                    "session_id": episode.session_id,
                    "turn_number": episode.turn_number,
                },
            ),
            text=episode.user_message,
        )

        await self._vector_store.upsert([doc], collection=self._collection)

        logger.debug(
            "episode_synced_to_vector_store",
            episode_id=str(episode.id),
            collection=self._collection,
        )

    async def delete_rule(self, rule_id: UUID) -> None:
        """Delete a rule's vector from store."""
        vector_id = VectorDocument.create_id(EntityType.RULE, rule_id)
        await self._vector_store.delete([vector_id], collection=self._collection)

        logger.debug(
            "rule_deleted_from_vector_store",
            rule_id=str(rule_id),
        )

    async def delete_scenario(self, scenario_id: UUID) -> None:
        """Delete a scenario's vector from store."""
        vector_id = VectorDocument.create_id(EntityType.SCENARIO, scenario_id)
        await self._vector_store.delete([vector_id], collection=self._collection)

        logger.debug(
            "scenario_deleted_from_vector_store",
            scenario_id=str(scenario_id),
        )

    async def delete_episode(self, episode_id: UUID) -> None:
        """Delete an episode's vector from store."""
        vector_id = VectorDocument.create_id(EntityType.EPISODE, episode_id)
        await self._vector_store.delete([vector_id], collection=self._collection)

        logger.debug(
            "episode_deleted_from_vector_store",
            episode_id=str(episode_id),
        )

    async def sync_rules_batch(
        self,
        rules: list[Rule],
        *,
        generate_embeddings: bool = True,
        batch_size: int = 100,
    ) -> int:
        """Sync multiple rules to vector store.

        Args:
            rules: Rules to sync
            generate_embeddings: Whether to generate missing embeddings
            batch_size: Batch size for embedding generation

        Returns:
            Number of rules synced
        """
        synced = 0

        # Separate rules with/without embeddings
        with_embedding = [r for r in rules if r.condition_embedding]
        without_embedding = [r for r in rules if not r.condition_embedding]

        # Sync rules that already have embeddings
        if with_embedding:
            docs = [
                VectorDocument(
                    id=VectorDocument.create_id(EntityType.RULE, rule.id),
                    vector=rule.condition_embedding,
                    metadata=VectorMetadata(
                        tenant_id=rule.tenant_id,
                        agent_id=rule.agent_id,
                        entity_type=EntityType.RULE,
                        entity_id=rule.id,
                        scope=rule.scope.value if rule.scope else None,
                        scope_id=rule.scope_id,
                        enabled=rule.enabled,
                        embedding_model=rule.embedding_model,
                    ),
                    text=rule.condition_text,
                )
                for rule in with_embedding
            ]
            await self._vector_store.upsert(docs, collection=self._collection)
            synced += len(docs)

        # Generate and sync rules without embeddings
        if generate_embeddings and without_embedding:
            for i in range(0, len(without_embedding), batch_size):
                batch = without_embedding[i : i + batch_size]
                texts = [r.condition_text for r in batch]

                response = await self._embedding_provider.embed(
                    texts,
                    task="retrieval.passage",
                )

                docs = [
                    VectorDocument(
                        id=VectorDocument.create_id(EntityType.RULE, rule.id),
                        vector=embedding,
                        metadata=VectorMetadata(
                            tenant_id=rule.tenant_id,
                            agent_id=rule.agent_id,
                            entity_type=EntityType.RULE,
                            entity_id=rule.id,
                            scope=rule.scope.value if rule.scope else None,
                            scope_id=rule.scope_id,
                            enabled=rule.enabled,
                            embedding_model=response.model,
                        ),
                        text=rule.condition_text,
                    )
                    for rule, embedding in zip(batch, response.embeddings)
                ]
                await self._vector_store.upsert(docs, collection=self._collection)
                synced += len(docs)

        logger.info(
            "rules_batch_synced",
            synced=synced,
            total=len(rules),
        )

        return synced

    async def delete_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> int:
        """Delete all vectors for an agent.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID

        Returns:
            Number of vectors deleted
        """
        deleted = await self._vector_store.delete_by_filter(
            tenant_id=tenant_id,
            agent_id=agent_id,
            collection=self._collection,
        )

        logger.info(
            "agent_vectors_deleted",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            deleted=deleted,
        )

        return deleted

    async def delete_by_tenant(self, tenant_id: UUID) -> int:
        """Delete all vectors for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of vectors deleted
        """
        deleted = await self._vector_store.delete_by_filter(
            tenant_id=tenant_id,
            collection=self._collection,
        )

        logger.info(
            "tenant_vectors_deleted",
            tenant_id=str(tenant_id),
            deleted=deleted,
        )

        return deleted
