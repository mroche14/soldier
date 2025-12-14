"""Qdrant vector store implementation.

This module provides a VectorStore implementation using Qdrant,
a high-performance vector similarity search engine.

Qdrant supports:
- Fast approximate nearest neighbor search
- Rich filtering with payload conditions
- Hybrid search combining vectors with metadata
- Cloud-hosted or self-hosted deployment
"""

import os
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from ruche.observability.logging import get_logger
from ruche.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)

logger = get_logger(__name__)

# Distance metric mapping
DISTANCE_METRICS = {
    "cosine": models.Distance.COSINE,
    "euclidean": models.Distance.EUCLID,
    "dot": models.Distance.DOT,
}


class QdrantVectorStore(VectorStore):
    """Vector store implementation using Qdrant.

    Supports both Qdrant Cloud and self-hosted instances.
    Uses async client for non-blocking operations.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_prefix: str = "focal",
        timeout: float = 60.0,
    ):
        """Initialize Qdrant vector store.

        Args:
            url: Qdrant server URL (defaults to QDRANT_URL env var)
            api_key: Qdrant API key (defaults to QDRANT_API_KEY env var)
            collection_prefix: Prefix for collection names
            timeout: Request timeout in seconds
        """
        self._url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self._api_key = api_key or os.environ.get("QDRANT_API_KEY")
        self._collection_prefix = collection_prefix
        self._timeout = timeout

        # Initialize async client
        if self._api_key:
            self._client = AsyncQdrantClient(
                url=self._url,
                api_key=self._api_key,
                timeout=timeout,
            )
        else:
            self._client = AsyncQdrantClient(
                url=self._url,
                timeout=timeout,
            )

        logger.info(
            "qdrant_store_initialized",
            url=self._url,
            has_api_key=bool(self._api_key),
            prefix=self._collection_prefix,
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "qdrant"

    def _full_collection_name(self, collection: str) -> str:
        """Get full collection name with prefix."""
        return f"{self._collection_prefix}_{collection}"

    def _metadata_to_payload(self, metadata: VectorMetadata) -> dict[str, Any]:
        """Convert VectorMetadata to Qdrant payload format."""
        payload: dict[str, Any] = {
            "tenant_id": str(metadata.tenant_id),
            "agent_id": str(metadata.agent_id),
            "entity_type": metadata.entity_type.value,
            "entity_id": str(metadata.entity_id),
            "enabled": metadata.enabled,
        }

        if metadata.scope:
            payload["scope"] = metadata.scope
        if metadata.scope_id:
            payload["scope_id"] = str(metadata.scope_id)
        if metadata.embedding_model:
            payload["embedding_model"] = metadata.embedding_model
        if metadata.extra:
            payload["extra"] = metadata.extra

        return payload

    def _payload_to_metadata(self, payload: dict[str, Any]) -> VectorMetadata:
        """Convert Qdrant payload to VectorMetadata."""
        return VectorMetadata(
            tenant_id=UUID(payload["tenant_id"]),
            agent_id=UUID(payload["agent_id"]),
            entity_type=EntityType(payload["entity_type"]),
            entity_id=UUID(payload["entity_id"]),
            scope=payload.get("scope"),
            scope_id=UUID(payload["scope_id"]) if payload.get("scope_id") else None,
            enabled=payload.get("enabled", True),
            embedding_model=payload.get("embedding_model"),
            extra=payload.get("extra", {}),
        )

    def _build_filter(
        self,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_types: list[EntityType] | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> models.Filter:
        """Build Qdrant filter from search parameters."""
        conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=str(tenant_id)),
            ),
            models.FieldCondition(
                key="enabled",
                match=models.MatchValue(value=True),
            ),
        ]

        if agent_id:
            conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=str(agent_id)),
                )
            )

        if entity_types:
            conditions.append(
                models.FieldCondition(
                    key="entity_type",
                    match=models.MatchAny(any=[et.value for et in entity_types]),
                )
            )

        if filter_metadata:
            for key, value in filter_metadata.items():
                if isinstance(value, UUID):
                    value = str(value)
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )

        return models.Filter(must=conditions)

    async def upsert(
        self,
        documents: list[VectorDocument],
        *,
        collection: str = "default",
    ) -> int:
        """Insert or update vectors in Qdrant."""
        if not documents:
            return 0

        collection_name = self._full_collection_name(collection)

        points = [
            models.PointStruct(
                id=doc.id,
                vector=doc.vector,
                payload={
                    **self._metadata_to_payload(doc.metadata),
                    "text": doc.text,
                },
            )
            for doc in documents
        ]

        try:
            await self._client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )

            logger.debug(
                "qdrant_upsert_success",
                collection=collection_name,
                count=len(points),
            )

            return len(points)

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_upsert_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant upsert failed: {e}") from e

    async def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_types: list[EntityType] | None = None,
        collection: str = "default",
        limit: int = 10,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
        include_vectors: bool = False,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors in Qdrant."""
        collection_name = self._full_collection_name(collection)

        query_filter = self._build_filter(
            tenant_id=tenant_id,
            agent_id=agent_id,
            entity_types=entity_types,
            filter_metadata=filter_metadata,
        )

        try:
            response = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=min_score if min_score > 0 else None,
                with_vectors=include_vectors,
                with_payload=True,
            )

            search_results = []
            for point in response.points:
                payload = point.payload or {}
                search_results.append(
                    VectorSearchResult(
                        id=str(point.id),
                        score=point.score,
                        metadata=self._payload_to_metadata(payload),
                        vector=point.vector if include_vectors else None,
                    )
                )

            logger.debug(
                "qdrant_search_success",
                collection=collection_name,
                results=len(search_results),
                min_score=min_score,
            )

            return search_results

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_search_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant search failed: {e}") from e

    async def delete(
        self,
        ids: list[str],
        *,
        collection: str = "default",
    ) -> int:
        """Delete vectors by ID from Qdrant."""
        if not ids:
            return 0

        collection_name = self._full_collection_name(collection)

        try:
            await self._client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=ids),
                wait=True,
            )

            logger.debug(
                "qdrant_delete_success",
                collection=collection_name,
                count=len(ids),
            )

            return len(ids)

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_delete_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant delete failed: {e}") from e

    async def delete_by_filter(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        entity_ids: list[UUID] | None = None,
        collection: str = "default",
    ) -> int:
        """Delete vectors matching filter criteria."""
        collection_name = self._full_collection_name(collection)

        conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=str(tenant_id)),
            )
        ]

        if agent_id:
            conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=str(agent_id)),
                )
            )

        if entity_type:
            conditions.append(
                models.FieldCondition(
                    key="entity_type",
                    match=models.MatchValue(value=entity_type.value),
                )
            )

        if entity_ids:
            conditions.append(
                models.FieldCondition(
                    key="entity_id",
                    match=models.MatchAny(any=[str(eid) for eid in entity_ids]),
                )
            )

        try:
            # Get count before delete for return value
            count_before = await self.count(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=entity_type,
                collection=collection,
            )

            await self._client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=conditions)
                ),
                wait=True,
            )

            count_after = await self.count(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=entity_type,
                collection=collection,
            )

            deleted = count_before - count_after

            logger.debug(
                "qdrant_delete_by_filter_success",
                collection=collection_name,
                deleted=deleted,
            )

            return deleted

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_delete_by_filter_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant delete by filter failed: {e}") from e

    async def get(
        self,
        ids: list[str],
        *,
        collection: str = "default",
        include_vectors: bool = True,
    ) -> list[VectorDocument]:
        """Get vectors by ID from Qdrant."""
        if not ids:
            return []

        collection_name = self._full_collection_name(collection)

        try:
            results = await self._client.retrieve(
                collection_name=collection_name,
                ids=ids,
                with_vectors=include_vectors,
                with_payload=True,
            )

            documents = []
            for point in results:
                payload = point.payload or {}
                documents.append(
                    VectorDocument(
                        id=str(point.id),
                        vector=point.vector if include_vectors else [],
                        metadata=self._payload_to_metadata(payload),
                        text=payload.get("text"),
                    )
                )

            return documents

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_get_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant get failed: {e}") from e

    async def count(
        self,
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        collection: str = "default",
    ) -> int:
        """Count vectors matching criteria."""
        collection_name = self._full_collection_name(collection)

        conditions: list[models.FieldCondition] = []

        if tenant_id:
            conditions.append(
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=str(tenant_id)),
                )
            )

        if agent_id:
            conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=str(agent_id)),
                )
            )

        if entity_type:
            conditions.append(
                models.FieldCondition(
                    key="entity_type",
                    match=models.MatchValue(value=entity_type.value),
                )
            )

        try:
            count_filter = models.Filter(must=conditions) if conditions else None
            result = await self._client.count(
                collection_name=collection_name,
                count_filter=count_filter,
                exact=True,
            )
            return result.count

        except UnexpectedResponse as e:
            # Collection might not exist
            if "not found" in str(e).lower():
                return 0
            logger.error(
                "qdrant_count_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant count failed: {e}") from e

    async def ensure_collection(
        self,
        collection: str,
        *,
        dimensions: int,
        distance_metric: str = "cosine",
    ) -> None:
        """Ensure a collection exists with the specified configuration."""
        collection_name = self._full_collection_name(collection)

        distance = DISTANCE_METRICS.get(distance_metric, models.Distance.COSINE)

        try:
            # Check if collection exists
            collections = await self._client.get_collections()
            exists = any(c.name == collection_name for c in collections.collections)

            if not exists:
                await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=dimensions,
                        distance=distance,
                    ),
                )

                # Create payload indexes for efficient filtering
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="tenant_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="agent_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="entity_type",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="enabled",
                    field_schema=models.PayloadSchemaType.BOOL,
                )

                logger.info(
                    "qdrant_collection_created",
                    collection=collection_name,
                    dimensions=dimensions,
                    distance=distance_metric,
                )
            else:
                logger.debug(
                    "qdrant_collection_exists",
                    collection=collection_name,
                )

        except UnexpectedResponse as e:
            logger.error(
                "qdrant_ensure_collection_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant ensure collection failed: {e}") from e

    async def delete_collection(self, collection: str) -> bool:
        """Delete an entire collection."""
        collection_name = self._full_collection_name(collection)

        try:
            await self._client.delete_collection(collection_name=collection_name)
            logger.info("qdrant_collection_deleted", collection=collection_name)
            return True

        except UnexpectedResponse as e:
            if "not found" in str(e).lower():
                return False
            logger.error(
                "qdrant_delete_collection_error",
                collection=collection_name,
                error=str(e),
            )
            raise RuntimeError(f"Qdrant delete collection failed: {e}") from e

    async def close(self) -> None:
        """Close the Qdrant client."""
        await self._client.close()
        logger.debug("qdrant_client_closed")
