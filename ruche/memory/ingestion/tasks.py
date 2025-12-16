"""Background task handlers for memory ingestion."""

from uuid import UUID

from ruche.memory.ingestion.entity_extractor import EntityDeduplicator, EntityExtractor
from ruche.memory.ingestion.summarizer import ConversationSummarizer
from ruche.memory.models.entity import Entity
from ruche.infrastructure.stores.memory.interface import MemoryStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


async def extract_entities(
    episode_id: UUID,
    group_id: str,
    memory_store: MemoryStore,
    entity_extractor: EntityExtractor,
    entity_deduplicator: EntityDeduplicator,
) -> None:
    """Extract entities from an episode asynchronously.

    Args:
        episode_id: Episode to process
        group_id: Tenant:session identifier
        memory_store: Memory store
        entity_extractor: Entity extractor service
        entity_deduplicator: Entity deduplicator service
    """
    try:
        # Get episode
        episode = await memory_store.get_episode(group_id, episode_id)
        if not episode:
            logger.warning("episode_not_found", episode_id=episode_id)
            return

        # Extract entities and relationships
        result = await entity_extractor.extract(episode)

        # Process each entity
        for extracted_entity in result.entities:
            # Create entity model
            entity = Entity(
                group_id=group_id,
                name=extracted_entity.name,
                entity_type=extracted_entity.type,
                attributes=extracted_entity.attributes,
                valid_from=episode.occurred_at,
            )

            # Check for duplicates
            duplicate = await entity_deduplicator.find_duplicate(entity, group_id)

            if duplicate:
                # Merge and update
                merged = await entity_deduplicator.merge_entities(duplicate, entity)
                await memory_store.update_entity(merged)
                logger.debug(
                    "entity_merged",
                    entity_name=entity.name,
                    existing_id=duplicate.id,
                )
            else:
                # Add new entity
                await memory_store.add_entity(entity)
                logger.debug("entity_created", entity_name=entity.name, entity_id=entity.id)

        # Process relationships
        # (Implementation would create relationship objects and store them)

        logger.info(
            "entities_extracted",
            episode_id=episode_id,
            entity_count=len(result.entities),
            relationship_count=len(result.relationships),
        )

    except Exception as e:
        logger.error(
            "entity_extraction_failed",
            episode_id=episode_id,
            error=str(e),
        )
        raise


async def check_summarization(
    group_id: str,
    _memory_store: MemoryStore,
    summarizer: ConversationSummarizer,
) -> None:
    """Check if summarization threshold reached and summarize if needed.

    Args:
        group_id: Tenant:session identifier
        _memory_store: Memory store (not directly used, summarizer has its own)
        summarizer: Conversation summarizer service
    """
    try:
        # Check and summarize if threshold reached
        summary = await summarizer.check_and_summarize_if_needed(group_id)

        if summary:
            logger.info(
                "summarization_triggered",
                group_id=group_id,
                summary_id=summary.id,
            )
        else:
            logger.debug(
                "summarization_threshold_not_reached",
                group_id=group_id,
            )

    except Exception as e:
        logger.error(
            "summarization_check_failed",
            group_id=group_id,
            error=str(e),
        )
        raise
