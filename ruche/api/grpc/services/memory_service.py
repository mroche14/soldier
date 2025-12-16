"""MemoryService gRPC implementation."""

from datetime import datetime
from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from ruche.api.grpc import memory_pb2, memory_pb2_grpc
from ruche.infrastructure.stores.memory.interface import MemoryStore
from ruche.memory.models import Episode
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class MemoryService(memory_pb2_grpc.MemoryServiceServicer):
    """gRPC MemoryService implementation.

    Provides memory management operations via gRPC.
    """

    def __init__(self, memory_store: MemoryStore) -> None:
        """Initialize MemoryService.

        Args:
            memory_store: Memory storage backend
        """
        self._memory_store = memory_store

    def _datetime_to_timestamp(self, dt: datetime) -> Timestamp:
        """Convert datetime to protobuf Timestamp.

        Args:
            dt: Python datetime

        Returns:
            Protobuf Timestamp
        """
        timestamp = Timestamp()
        timestamp.FromDatetime(dt)
        return timestamp

    def _timestamp_to_datetime(self, ts: Timestamp) -> datetime:
        """Convert protobuf Timestamp to datetime.

        Args:
            ts: Protobuf Timestamp

        Returns:
            Python datetime
        """
        return ts.ToDatetime()

    async def AddEpisode(
        self, request: memory_pb2.AddEpisodeRequest, context: grpc.aio.ServicerContext
    ) -> memory_pb2.AddEpisodeResponse:
        """Add a new episode to memory.

        Args:
            request: Add episode request
            context: gRPC context

        Returns:
            AddEpisodeResponse with episode ID
        """
        logger.info(
            "grpc_add_episode_request",
            tenant_id=request.tenant_id,
            content_type=request.content_type,
            source=request.source,
        )

        try:
            tenant_id = UUID(request.tenant_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return memory_pb2.AddEpisodeResponse()

        # Build group_id from tenant context
        group_id = f"{tenant_id}"

        # Convert timestamp
        occurred_at = (
            self._timestamp_to_datetime(request.occurred_at)
            if request.HasField("occurred_at")
            else datetime.utcnow()
        )

        # Create episode
        episode = Episode(
            group_id=group_id,
            content=request.content,
            content_type=request.content_type,
            source=request.source,
            source_metadata=dict(request.source_metadata) if request.source_metadata else None,
            occurred_at=occurred_at,
            entity_ids=list(request.entity_ids) if request.entity_ids else None,
        )

        # Save to store
        episode_id = await self._memory_store.add_episode(episode)

        logger.info(
            "grpc_episode_created",
            tenant_id=request.tenant_id,
            episode_id=str(episode_id),
        )

        # Fetch the saved episode to get timestamps
        saved_episode = await self._memory_store.get_episode(group_id, episode_id)
        if not saved_episode:
            await context.abort(
                grpc.StatusCode.INTERNAL,
                "Episode not found after creation",
            )
            return memory_pb2.AddEpisodeResponse()

        return memory_pb2.AddEpisodeResponse(
            episode_id=str(episode_id),
            created_at=self._datetime_to_timestamp(saved_episode.created_at),
        )

    async def Search(
        self, request: memory_pb2.SearchRequest, context: grpc.aio.ServicerContext
    ) -> memory_pb2.SearchResponse:
        """Search memory using semantic or keyword search.

        Args:
            request: Search request
            context: gRPC context

        Returns:
            SearchResponse with results
        """
        logger.info(
            "grpc_search_request",
            tenant_id=request.tenant_id,
            query=request.query,
            search_type=request.search_type,
            limit=request.limit,
        )

        try:
            tenant_id = UUID(request.tenant_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return memory_pb2.SearchResponse()

        group_id = f"{tenant_id}"
        limit = request.limit if request.limit > 0 else 10

        # Determine search type
        if request.search_type == "text":
            # Text search
            results = await self._memory_store.search_text(
                group_id=group_id,
                query=request.query,
                limit=limit,
            )
        else:
            # Vector search (default)
            results = await self._memory_store.search_vector(
                group_id=group_id,
                query=request.query,
                limit=limit,
                min_score=request.min_score if request.min_score > 0 else 0.0,
            )

        # Convert to gRPC results
        grpc_results = []
        for result in results:
            grpc_results.append(
                memory_pb2.SearchResult(
                    episode_id=str(result.episode_id),
                    content=result.content,
                    score=result.score,
                    occurred_at=self._datetime_to_timestamp(result.occurred_at),
                )
            )

        logger.info(
            "grpc_search_completed",
            tenant_id=request.tenant_id,
            results_count=len(grpc_results),
        )

        return memory_pb2.SearchResponse(
            results=grpc_results,
            total_count=len(grpc_results),
        )

    async def GetEntity(
        self, request: memory_pb2.GetEntityRequest, context: grpc.aio.ServicerContext
    ) -> memory_pb2.Entity:
        """Get a specific entity by ID.

        Args:
            request: Get entity request
            context: gRPC context

        Returns:
            Entity
        """
        logger.info(
            "grpc_get_entity_request",
            tenant_id=request.tenant_id,
            entity_id=request.entity_id,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            entity_id = UUID(request.entity_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return memory_pb2.Entity()

        group_id = f"{tenant_id}"

        # Get entity from store
        entity = await self._memory_store.get_entity(group_id, entity_id)

        if not entity:
            await context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Entity {entity_id} not found",
            )
            return memory_pb2.Entity()

        logger.info(
            "grpc_get_entity_completed",
            tenant_id=request.tenant_id,
            entity_id=request.entity_id,
        )

        return memory_pb2.Entity(
            id=str(entity.id),
            name=entity.name,
            entity_type=entity.entity_type,
            attributes=entity.attributes if entity.attributes else {},
            created_at=self._datetime_to_timestamp(entity.created_at),
        )
