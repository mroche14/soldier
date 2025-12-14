"""Intent retrieval using hybrid search.

Retrieves candidate intents by comparing user messages against
intent example phrases using both vector similarity and (future) BM25.
"""

from uuid import UUID

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.models import Intent, IntentCandidate, ScoredIntent
from ruche.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from ruche.alignment.stores import AgentConfigStore
from ruche.config.models.selection import SelectionConfig
from ruche.observability.logging import get_logger
from ruche.providers.embedding import EmbeddingProvider
from ruche.utils.vector import cosine_similarity

logger = get_logger(__name__)


def decide_canonical_intent(
    sensor_intent: str | None,
    sensor_confidence: float | None,
    hybrid_candidates: list[IntentCandidate],
    threshold: float = 0.7,
) -> tuple[str | None, float | None]:
    """Merge LLM sensor intent with hybrid retrieval results.

    P4.3: Decide canonical intent

    Strategy:
    1. If sensor_confidence >= threshold, trust LLM sensor
    2. Else if top hybrid candidate score >= threshold, use that
    3. Else return sensor intent (lower confidence)

    Args:
        sensor_intent: Intent from Situational Sensor (Phase 2)
        sensor_confidence: Confidence from LLM
        hybrid_candidates: Scored intents from retrieval
        threshold: Minimum confidence to trust

    Returns:
        (canonical_intent_label, confidence_score)
    """
    # If LLM sensor is confident, use it
    if sensor_confidence and sensor_confidence >= threshold:
        logger.debug(
            "using_sensor_intent",
            intent=sensor_intent,
            confidence=sensor_confidence,
            reason="sensor_confidence_above_threshold",
        )
        return sensor_intent, sensor_confidence

    # Check hybrid retrieval
    if hybrid_candidates:
        top_candidate = hybrid_candidates[0]
        if top_candidate.score >= threshold:
            logger.debug(
                "using_hybrid_intent",
                intent=top_candidate.intent_name,
                score=top_candidate.score,
                reason="hybrid_score_above_threshold",
            )
            return top_candidate.intent_name, top_candidate.score

    # Fallback to sensor (even if low confidence)
    logger.debug(
        "using_sensor_intent_fallback",
        intent=sensor_intent,
        confidence=sensor_confidence or 0.0,
        hybrid_candidates_count=len(hybrid_candidates),
        reason="no_confident_match",
    )
    return sensor_intent, sensor_confidence or 0.0


class IntentRetriever:
    """Retrieve candidate intents using hybrid search.

    Intents are matched by comparing the user message against
    example phrases using both vector similarity and lexical matching.

    P4.2: Hybrid intent retrieval
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
    ) -> None:
        """Initialize the intent retriever.

        Args:
            config_store: Store for intent definitions
            embedding_provider: Provider for query embeddings
            selection_config: Configuration for selection strategy
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )

    @property
    def selection_strategy_name(self) -> str:
        """Return the selection strategy name."""
        return self._selection_strategy.name

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        snapshot: SituationSnapshot,
    ) -> list[IntentCandidate]:
        """Retrieve intent candidates for the user message.

        P4.2: Hybrid intent retrieval
        Returns scored candidates for P4.3 to merge with LLM sensor

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            snapshot: Situation snapshot with embedding

        Returns:
            List of scored intent candidates
        """
        intents = await self._config_store.get_intents(tenant_id, agent_id)
        if not intents:
            logger.debug(
                "no_intents_configured",
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
            )
            return []

        # Compute query embedding
        query_embedding = snapshot.embedding
        if query_embedding is None:
            query_embedding = await self._embedding_provider.embed_single(snapshot.message)

        # Score each intent against query
        scored: list[ScoredIntent] = []
        for intent in intents:
            score = self._score_intent(intent, query_embedding, snapshot.message)
            scored.append(
                ScoredIntent(
                    intent_id=intent.id,
                    intent_name=intent.name,
                    score=score,
                )
            )

        # Sort by score descending
        scored.sort(key=lambda ic: ic.score, reverse=True)

        # Apply selection strategy
        scored_items = [ScoredItem(item=s, score=s.score) for s in scored]
        selected = self._selection_strategy.select(
            scored_items,
            max_k=self._selection_config.max_k,
            min_k=self._selection_config.min_k,
        )

        # Convert to IntentCandidates
        candidates = [
            IntentCandidate(
                intent_id=item.item.intent_id,
                intent_name=item.item.intent_name,
                score=item.item.score,
                source="hybrid",
            )
            for item in selected.selected
        ]

        logger.debug(
            "intent_retrieval_complete",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            total_intents=len(intents),
            candidates_selected=len(candidates),
            top_score=candidates[0].score if candidates else 0.0,
            strategy=self.selection_strategy_name,
        )

        return candidates

    def _score_intent(
        self,
        intent: Intent,
        query_embedding: list[float],
        query_text: str,
    ) -> float:
        """Score intent using vector similarity.

        Future: Add BM25 lexical matching here for hybrid scoring.

        Args:
            intent: Intent to score
            query_embedding: Query message embedding
            query_text: Raw query text (for future BM25)

        Returns:
            Similarity score (0-1)
        """
        if intent.embedding:
            return cosine_similarity(query_embedding, intent.embedding)
        return 0.0
