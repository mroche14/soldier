"""Entity and relationship extraction from episodes."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import Levenshtein

from ruche.config.models.pipeline import (
    EntityDeduplicationConfig,
    EntityExtractionConfig,
)
from ruche.memory.ingestion.errors import ExtractionError
from ruche.memory.ingestion.models import (
    EntityExtractionResult,
    ExtractedEntity,
    ExtractedRelationship,
)
from ruche.memory.models.entity import Entity
from ruche.memory.models.episode import Episode
from ruche.memory.models.relationship import Relationship
from ruche.memory.store import MemoryStore
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.llm import LLMMessage

logger = get_logger(__name__)


class EntityExtractor:
    """Extract entities and relationships from episode content using LLM."""

    def __init__(
        self,
        llm_executor: Any,
        config: EntityExtractionConfig,
    ):
        """Initialize entity extractor.

        Args:
            llm_executor: LLM executor (or any object with compatible generate method)
            config: Extraction configuration
        """
        self._llm_executor = llm_executor
        self._config = config

    async def extract(
        self,
        episode: Episode,
    ) -> EntityExtractionResult:
        """Extract entities and relationships from episode content.

        Uses LLMProvider with structured output to identify:
        - Named entities (people, products, orders, issues, concepts)
        - Relationships between those entities
        - Confidence scores for each extraction

        Args:
            episode: Episode to extract from

        Returns:
            EntityExtractionResult: Contains lists of ExtractedEntity
            and ExtractedRelationship objects

        Raises:
            ExtractionError: If LLM call fails or returns invalid structure
        """
        try:
            # Build extraction prompt
            prompt = self._build_extraction_prompt(episode.content)

            # Call LLM with timeout
            messages = [
                LLMMessage(role="system", content=prompt["system"]),
                LLMMessage(role="user", content=prompt["user"]),
            ]

            response = await asyncio.wait_for(
                self._llm_executor.generate(
                    messages,
                    max_tokens=self._config.max_tokens,
                    temperature=self._config.temperature,
                ),
                timeout=self._config.timeout_ms / 1000,
            )

            # Parse response into structured output
            result = self._parse_llm_response(response.content)

            # Filter by confidence
            result = self._filter_by_confidence(result)

            logger.info(
                "entities_extracted",
                episode_id=episode.id,
                entity_count=len(result.entities),
                relationship_count=len(result.relationships),
            )

            return result

        except TimeoutError:
            logger.error(
                "extraction_timeout",
                episode_id=episode.id,
                timeout_ms=self._config.timeout_ms,
            )
            raise ExtractionError(
                message=f"Entity extraction timed out after {self._config.timeout_ms}ms",
                episode_id=episode.id,
            ) from None
        except Exception as e:
            logger.error(
                "extraction_failed",
                episode_id=episode.id,
                error=str(e),
            )
            raise ExtractionError(
                message=f"Entity extraction failed: {str(e)}",
                episode_id=episode.id,
                cause=e,
            ) from e

    async def extract_batch(
        self,
        episodes: list[Episode],
    ) -> list[EntityExtractionResult]:
        """Extract from multiple episodes in parallel.

        Args:
            episodes: List of episodes to extract from

        Returns:
            List of EntityExtractionResult in same order as input
        """
        tasks = [self.extract(episode) for episode in episodes]

        # Execute in batches
        results = []
        for i in range(0, len(tasks), self._config.batch_size):
            batch = tasks[i : i + self._config.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)

        # Convert exceptions to empty results
        return [
            r if isinstance(r, EntityExtractionResult) else EntityExtractionResult()
            for r in results
        ]

    def _build_extraction_prompt(self, content: str) -> dict[str, str]:
        """Build extraction prompt for LLM.

        Args:
            content: Episode content to extract from

        Returns:
            Dict with system and user prompts
        """
        system_prompt = """You are an entity extraction system for a knowledge graph.
Extract named entities from the following conversation turn.

Entity types to extract:
- person: People, customers, employees (must have name if known)
- order: Purchase orders, transactions
- product: Items, goods mentioned
- issue: Problems, complaints, damage
- concept: Abstract entities specific to domain (e.g., "loyalty status", "account")

For each entity, provide:
1. name: Exact text from conversation if possible
2. type: Choose from above types
3. attributes: Key-value pairs like {"email": "...", "status": "..."}
4. confidence: high/medium/low - only include high/medium

Extract relationships:
- from_name: Source entity name
- to_name: Target entity name
- relation_type: contains, ordered, has_issue, owns, related_to, etc.
- confidence: high/medium/low

Return JSON format:
{
  "entities": [
    {"name": "...", "type": "person", "attributes": {}, "confidence": "high"}
  ],
  "relationships": [
    {"from_name": "...", "to_name": "...", "relation_type": "ordered", "attributes": {}, "confidence": "high"}
  ]
}

Only include entities and relationships with high or medium confidence. Skip ambiguous mentions."""

        user_prompt = f"Extract entities and relationships from this text:\n\n{content}"

        return {"system": system_prompt, "user": user_prompt}

    def _parse_llm_response(self, response: str) -> EntityExtractionResult:
        """Parse LLM response into structured result.

        Args:
            response: Raw LLM response

        Returns:
            EntityExtractionResult
        """
        try:
            import json

            # Try to parse as JSON
            data = json.loads(response)

            entities = [
                ExtractedEntity(
                    name=e.get("name", ""),
                    type=e.get("type", "concept"),
                    attributes=e.get("attributes", {}),
                    confidence=e.get("confidence", "medium"),
                )
                for e in data.get("entities", [])
            ]

            relationships = [
                ExtractedRelationship(
                    from_name=r.get("from_name", ""),
                    to_name=r.get("to_name", ""),
                    relation_type=r.get("relation_type", "related_to"),
                    attributes=r.get("attributes", {}),
                    confidence=r.get("confidence", "medium"),
                )
                for r in data.get("relationships", [])
            ]

            return EntityExtractionResult(
                entities=entities,
                relationships=relationships,
            )

        except Exception:
            # Return empty result if parsing fails
            return EntityExtractionResult()

    def _filter_by_confidence(
        self, result: EntityExtractionResult
    ) -> EntityExtractionResult:
        """Filter result by minimum confidence threshold.

        Args:
            result: Extraction result to filter

        Returns:
            Filtered result
        """
        confidence_levels = {"high": 3, "medium": 2, "low": 1}
        min_level = confidence_levels.get(self._config.min_confidence, 2)

        filtered_entities = [
            e
            for e in result.entities
            if confidence_levels.get(e.confidence, 0) >= min_level
        ]

        filtered_relationships = [
            r
            for r in result.relationships
            if confidence_levels.get(r.confidence, 0) >= min_level
        ]

        return EntityExtractionResult(
            entities=filtered_entities,
            relationships=filtered_relationships,
        )


class EntityDeduplicator:
    """Find and merge duplicate entities using multi-stage matching."""

    def __init__(
        self,
        memory_store: MemoryStore,
        config: EntityDeduplicationConfig,
    ):
        """Initialize entity deduplicator.

        Args:
            memory_store: Store for querying existing entities
            config: Deduplication configuration
        """
        self._memory_store = memory_store
        self._config = config

    async def find_duplicate(
        self,
        entity: Entity,
        group_id: str,
    ) -> Entity | None:
        """Find duplicate entity using multi-stage pipeline.

        Stages (in order, stops at first match):
        1. Exact match (normalized name)
        2. Fuzzy string matching (Levenshtein)
        3. Embedding similarity (cosine)
        4. Rule-based (domain-specific)

        Args:
            entity: Candidate entity to check
            group_id: Scope for searching existing entities

        Returns:
            Entity: Existing duplicate if found, None otherwise
        """
        # Get existing entities of same type in group
        existing_entities = await self._memory_store.get_entities(
            group_id=group_id, entity_type=entity.entity_type
        )

        if not existing_entities:
            return None

        # Stage 1: Exact match
        if self._config.exact_match_enabled:
            duplicate = self._exact_match(entity, existing_entities)
            if duplicate:
                logger.debug(
                    "deduplication_stage",
                    stage="exact",
                    entity_name=entity.name,
                    duplicate_id=duplicate.id,
                )
                return duplicate

        # Stage 2: Fuzzy match
        if self._config.fuzzy_match_enabled:
            duplicate = self._fuzzy_match(entity, existing_entities)
            if duplicate:
                logger.debug(
                    "deduplication_stage",
                    stage="fuzzy",
                    entity_name=entity.name,
                    duplicate_id=duplicate.id,
                )
                return duplicate

        # Stage 3: Embedding similarity
        if self._config.embedding_match_enabled and entity.embedding:
            duplicate = self._embedding_match(entity, existing_entities)
            if duplicate:
                logger.debug(
                    "deduplication_stage",
                    stage="embedding",
                    entity_name=entity.name,
                    duplicate_id=duplicate.id,
                )
                return duplicate

        # Stage 4: Rule-based
        if self._config.rule_based_enabled:
            duplicate = self._rule_based_match(entity, existing_entities)
            if duplicate:
                logger.debug(
                    "deduplication_stage",
                    stage="rule_based",
                    entity_name=entity.name,
                    duplicate_id=duplicate.id,
                )
                return duplicate

        return None

    async def merge_entities(
        self,
        existing: Entity,
        new: Entity,
    ) -> Entity:
        """Merge new entity data into existing entity.

        Combines attributes (new takes precedence for conflicts),
        preserves temporal timestamps.

        Args:
            existing: Entity already in MemoryStore
            new: Newly extracted entity with updated data

        Returns:
            Entity: Merged entity (NOT automatically persisted)
        """
        # Merge attributes (new overwrites existing)
        merged_attrs = existing.attributes.copy()
        merged_attrs.update(new.attributes)

        # Create merged entity
        merged = Entity(
            id=existing.id,  # Keep existing ID
            group_id=existing.group_id,
            name=existing.name,  # Keep original name
            entity_type=existing.entity_type,
            attributes=merged_attrs,
            valid_from=existing.valid_from,  # Keep original
            valid_to=None,  # Still valid
            recorded_at=existing.recorded_at,  # Keep original
            embedding=existing.embedding or new.embedding,  # Prefer existing
        )

        return merged

    def _exact_match(
        self, entity: Entity, existing_entities: list[Entity]
    ) -> Entity | None:
        """Stage 1: Exact match on normalized name.

        Args:
            entity: Candidate entity
            existing_entities: Existing entities to check

        Returns:
            Matching entity or None
        """
        normalized = self._normalize_name(entity.name)

        for existing in existing_entities:
            if self._normalize_name(existing.name) == normalized:
                return existing

        return None

    def _fuzzy_match(
        self, entity: Entity, existing_entities: list[Entity]
    ) -> Entity | None:
        """Stage 2: Fuzzy string matching using Levenshtein distance.

        Args:
            entity: Candidate entity
            existing_entities: Existing entities to check

        Returns:
            Matching entity or None
        """
        normalized = self._normalize_name(entity.name)
        threshold = self._config.fuzzy_threshold

        for existing in existing_entities:
            existing_normalized = self._normalize_name(existing.name)
            similarity = Levenshtein.ratio(normalized, existing_normalized)

            if similarity >= threshold:
                return existing

        return None

    def _embedding_match(
        self, entity: Entity, existing_entities: list[Entity]
    ) -> Entity | None:
        """Stage 3: Embedding similarity using cosine distance.

        Args:
            entity: Candidate entity
            existing_entities: Existing entities to check

        Returns:
            Matching entity or None
        """
        if not entity.embedding:
            return None

        threshold = self._config.embedding_threshold

        for existing in existing_entities:
            if not existing.embedding:
                continue

            similarity = self._cosine_similarity(entity.embedding, existing.embedding)

            if similarity >= threshold:
                return existing

        return None

    def _rule_based_match(
        self, entity: Entity, existing_entities: list[Entity]
    ) -> Entity | None:
        """Stage 4: Rule-based domain-specific matching.

        Args:
            entity: Candidate entity
            existing_entities: Existing entities to check

        Returns:
            Matching entity or None
        """
        # Person: match by email or phone
        if entity.entity_type == "person":
            email = entity.attributes.get("email")
            phone = entity.attributes.get("phone")

            for existing in existing_entities:
                if email and existing.attributes.get("email") == email:
                    return existing
                if phone and existing.attributes.get("phone") == phone:
                    return existing

        # Order: match by order_id
        if entity.entity_type == "order":
            order_id = entity.attributes.get("order_id")

            if order_id:
                for existing in existing_entities:
                    if existing.attributes.get("order_id") == order_id:
                        return existing

        return None

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize entity name for comparison.

        Args:
            name: Entity name

        Returns:
            Normalized name
        """
        import re

        # Lowercase, remove punctuation, trim whitespace
        normalized = name.lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0-1)
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return float(dot_product / (magnitude1 * magnitude2))


async def update_relationship_temporal(
    from_entity_id: UUID,
    to_entity_id: UUID,
    relation_type: str,
    new_attributes: dict[str, Any],
    group_id: str,
    memory_store: MemoryStore,
) -> Relationship:
    """Update a relationship by invalidating old and creating new.

    Args:
        from_entity_id: Source entity ID
        to_entity_id: Target entity ID
        relation_type: Relationship type
        new_attributes: New attributes for relationship
        group_id: Tenant:session identifier
        memory_store: Memory store

    Returns:
        New relationship
    """
    # Find existing active relationships of this type from this entity
    # Don't filter by to_entity_id - we want to invalidate ALL relationships
    # of this type, even if they point to different entities
    existing = await memory_store.get_relationships(
        group_id=group_id,
        from_entity_id=from_entity_id,
        relation_type=relation_type,
    )

    # Invalidate all active relationships of this type
    now = datetime.now(UTC)
    for rel in existing:
        if rel.valid_to is None:  # Only if currently active
            rel.valid_to = now
            await memory_store.update_relationship(rel)

    # Create new relationship with current timestamp
    new_rel = Relationship(
        group_id=group_id,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_type,
        attributes=new_attributes,
        valid_from=now,
        valid_to=None,  # Currently active
    )

    await memory_store.add_relationship(new_rel)
    return new_rel
