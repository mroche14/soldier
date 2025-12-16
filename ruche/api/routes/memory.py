"""Memory management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ruche.api.dependencies import MemoryStoreDep
from ruche.api.middleware.auth import TenantContextDep
from ruche.api.models.memory import (
    EpisodeCreate,
    EpisodeResponse,
    EpisodeSearchResult,
    EntityResponse,
    MemorySearchResponse,
)
from ruche.memory.models import Episode
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/memory")


@router.post("/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    request: EpisodeCreate,
    tenant_context: TenantContextDep,
    memory_store: MemoryStoreDep,
) -> EpisodeResponse:
    """Create a new episode in memory.

    Episodes represent atomic units of memory - individual pieces
    of information like messages, events, or facts.

    Args:
        request: Episode creation request
        tenant_context: Authenticated tenant context
        memory_store: Memory storage backend

    Returns:
        Created episode with ID and timestamps
    """
    logger.info(
        "create_episode_request",
        tenant_id=str(tenant_context.tenant_id),
        content_type=request.content_type,
        source=request.source,
    )

    # Build group_id from tenant context
    # For now, using tenant_id as group_id (in production would include session_id)
    group_id = f"{tenant_context.tenant_id}"

    # Create episode
    episode = Episode(
        group_id=group_id,
        content=request.content,
        content_type=request.content_type,
        source=request.source,
        source_metadata=request.source_metadata,
        occurred_at=request.occurred_at,
        entity_ids=request.entity_ids,
    )

    # Save to store
    episode_id = await memory_store.add_episode(episode)

    logger.info(
        "episode_created",
        tenant_id=str(tenant_context.tenant_id),
        episode_id=str(episode_id),
    )

    # Fetch the saved episode to get computed fields
    saved_episode = await memory_store.get_episode(group_id, episode_id)
    if not saved_episode:
        raise HTTPException(status_code=500, detail="Episode not found after creation")

    return EpisodeResponse.from_episode(saved_episode)


@router.get("/search", response_model=MemorySearchResponse)
async def search_memory(
    tenant_context: TenantContextDep,
    memory_store: MemoryStoreDep,
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum results to return"),
    search_type: Literal["vector", "text"] = Query(
        default="vector",
        description="Search type: vector (semantic) or text (keyword)",
    ),
    min_score: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (vector search only)",
    ),
) -> MemorySearchResponse:
    """Search memory using semantic or keyword search.

    Supports two search modes:
    - vector: Semantic similarity search using embeddings
    - text: Keyword/BM25 search for exact terms

    Args:
        tenant_context: Authenticated tenant context
        query: Search query string
        limit: Maximum number of results
        search_type: Type of search to perform
        min_score: Minimum similarity score for vector search
        memory_store: Memory storage backend

    Returns:
        Search results with episodes and scores
    """
    logger.debug(
        "search_memory_request",
        tenant_id=str(tenant_context.tenant_id),
        query=query,
        search_type=search_type,
        limit=limit,
    )

    # Build group_id
    group_id = f"{tenant_context.tenant_id}"

    results = []

    if search_type == "vector":
        # For vector search, we would need to embed the query first
        # For now, this is a simplified implementation
        # In production, would call embedding provider to get query embedding
        logger.warning(
            "vector_search_not_fully_implemented",
            msg="Vector search requires embedding provider integration",
        )
        # Placeholder - would need query embedding
        # query_embedding = await embedding_provider.embed_single(query)
        # episode_scores = await memory_store.vector_search_episodes(
        #     query_embedding=query_embedding,
        #     group_id=group_id,
        #     limit=limit,
        #     min_score=min_score,
        # )
        episode_scores = []
    else:
        # Text search
        episodes = await memory_store.text_search_episodes(
            query=query,
            group_id=group_id,
            limit=limit,
        )
        # Text search doesn't return scores, use 1.0 for all
        episode_scores = [(ep, 1.0) for ep in episodes]

    # Convert to response format
    for episode, score in episode_scores:
        results.append(
            EpisodeSearchResult(
                episode=EpisodeResponse.from_episode(episode),
                score=score,
            )
        )

    logger.info(
        "memory_search_completed",
        tenant_id=str(tenant_context.tenant_id),
        results_count=len(results),
        search_type=search_type,
    )

    return MemorySearchResponse(
        results=results,
        query=query,
        limit=limit,
        search_type=search_type,
    )


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    tenant_context: TenantContextDep,
    memory_store: MemoryStoreDep,
) -> EntityResponse:
    """Get an entity by ID.

    Entities represent named things in the knowledge graph
    like people, orders, products, etc.

    Args:
        entity_id: Entity identifier
        tenant_context: Authenticated tenant context
        memory_store: Memory storage backend

    Returns:
        Entity details

    Raises:
        HTTPException: 404 if entity not found
    """
    logger.debug(
        "get_entity_request",
        tenant_id=str(tenant_context.tenant_id),
        entity_id=str(entity_id),
    )

    # Build group_id
    group_id = f"{tenant_context.tenant_id}"

    entity = await memory_store.get_entity(group_id, entity_id)
    if not entity:
        logger.warning(
            "entity_not_found",
            tenant_id=str(tenant_context.tenant_id),
            entity_id=str(entity_id),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Entity {entity_id} not found",
        )

    return EntityResponse.from_entity(entity)
