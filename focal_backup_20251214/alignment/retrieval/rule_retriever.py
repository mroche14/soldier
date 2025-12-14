"""Rule retrieval with scope hierarchy and business filters."""

import time
from uuid import UUID

from rank_bm25 import BM25Okapi

from focal.alignment.context.situation_snapshot import SituationSnapshot
from focal.alignment.models import Rule, Scope
from focal.alignment.retrieval.models import RetrievalResult, RuleSource, ScoredRule
from focal.alignment.retrieval.reranker import RuleReranker
from focal.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from focal.alignment.stores import AgentConfigStore
from focal.config.models.pipeline import HybridRetrievalConfig
from focal.config.models.selection import SelectionConfig
from focal.observability.logging import get_logger
from focal.providers.embedding import EmbeddingProvider
from focal.utils.hybrid import HybridScorer
from focal.utils.vector import cosine_similarity

logger = get_logger(__name__)


class RuleRetriever:
    """Retrieve candidate rules using embeddings and selection strategies.

    Supports:
    - Scope hierarchy (global → scenario → step)
    - Business filters (max_fires, cooldown, enabled)
    - Adaptive selection strategies
    - Optional reranking for improved precision
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
        reranker: RuleReranker | None = None,
        hybrid_config: HybridRetrievalConfig | None = None,
    ) -> None:
        """Initialize the rule retriever.

        Args:
            config_store: Store for rule definitions
            embedding_provider: Provider for query embeddings
            selection_config: Configuration for selection strategy
            reranker: Optional reranker for result refinement
            hybrid_config: Optional hybrid retrieval configuration
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )
        self._reranker = reranker
        self._hybrid_config = hybrid_config
        self._hybrid_scorer = (
            HybridScorer(
                vector_weight=hybrid_config.vector_weight,
                bm25_weight=hybrid_config.bm25_weight,
                normalization=hybrid_config.normalization,
            )
            if hybrid_config and hybrid_config.enabled
            else None
        )

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        snapshot: SituationSnapshot,
        *,
        active_scenario_id: UUID | None = None,
        active_step_id: UUID | None = None,
        fired_rule_counts: dict[UUID, int] | None = None,
        last_fired_turns: dict[UUID, int] | None = None,
        current_turn: int = 0,
    ) -> RetrievalResult:
        """Retrieve rules across scopes with business filters applied.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            snapshot: Situational snapshot with message and embedding
            active_scenario_id: Current scenario for scenario-scoped rules
            active_step_id: Current step for step-scoped rules
            fired_rule_counts: Rule fire counts for max_fires filter
            last_fired_turns: Last fire turn for cooldown filter
            current_turn: Current turn count for cooldown logic

        Returns:
            RetrievalResult with scored rules and metadata
        """
        fired_rule_counts = fired_rule_counts or {}
        last_fired_turns = last_fired_turns or {}

        start_time = time.perf_counter()

        embedding = snapshot.embedding
        if embedding is None:
            embedding = await self._embedding_provider.embed_single(snapshot.message)

        query_text = snapshot.message

        candidates: list[ScoredRule] = []
        candidates.extend(
            await self._retrieve_scope(
                tenant_id,
                agent_id,
                scope=Scope.GLOBAL,
                scope_id=None,
                source=RuleSource.GLOBAL,
                embedding=embedding,
                query_text=query_text,
                fired_rule_counts=fired_rule_counts,
                last_fired_turns=last_fired_turns,
                current_turn=current_turn,
            )
        )

        if active_scenario_id:
            candidates.extend(
                await self._retrieve_scope(
                    tenant_id,
                    agent_id,
                    scope=Scope.SCENARIO,
                    scope_id=active_scenario_id,
                    source=RuleSource.SCENARIO,
                    embedding=embedding,
                    query_text=query_text,
                    fired_rule_counts=fired_rule_counts,
                    last_fired_turns=last_fired_turns,
                    current_turn=current_turn,
                )
            )

        if active_step_id:
            candidates.extend(
                await self._retrieve_scope(
                    tenant_id,
                    agent_id,
                    scope=Scope.STEP,
                    scope_id=active_step_id,
                    source=RuleSource.STEP,
                    embedding=embedding,
                    query_text=query_text,
                    fired_rule_counts=fired_rule_counts,
                    last_fired_turns=last_fired_turns,
                    current_turn=current_turn,
                )
            )

        # Optional reranking
        if self._reranker and candidates:
            candidates = await self._reranker.rerank(snapshot.message, candidates)

        selected_rules = self._apply_selection(candidates)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        selection_metadata = {
            "strategy": self._selection_strategy.name,
            "min_score": self._selection_config.min_score,
            "max_k": self._selection_config.max_k,
            "min_k": self._selection_config.min_k,
        }

        logger.debug(
            "rules_retrieved",
            total_candidates=len(candidates),
            selected=len(selected_rules),
            elapsed_ms=elapsed_ms,
        )

        return RetrievalResult(
            rules=selected_rules,
            retrieval_time_ms=elapsed_ms,
            selection_metadata={"rules": selection_metadata},
        )

    async def _retrieve_scope(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scope: Scope,
        scope_id: UUID | None,
        source: RuleSource,
        embedding: list[float],
        query_text: str,
        fired_rule_counts: dict[UUID, int],
        last_fired_turns: dict[UUID, int],
        current_turn: int,
    ) -> list[ScoredRule]:
        """Retrieve and score rules for a specific scope."""
        rules = await self._config_store.get_rules(
            tenant_id,
            agent_id,
            scope=scope,
            scope_id=scope_id,
            enabled_only=True,
        )

        # Filter by business rules
        filtered_rules = [
            rule
            for rule in rules
            if self._passes_business_filters(
                rule,
                fired_rule_counts=fired_rule_counts,
                last_fired_turns=last_fired_turns,
                current_turn=current_turn,
            )
        ]

        if not filtered_rules:
            return []

        # Use hybrid scoring if configured, else vector-only
        if self._hybrid_scorer:
            scored = self._hybrid_retrieval(filtered_rules, embedding, query_text, source)
        else:
            scored = self._vector_only_retrieval(filtered_rules, embedding, source)

        # Sort by score descending for selection
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored

    def _vector_only_retrieval(
        self,
        rules: list[Rule],
        query_embedding: list[float],
        source: RuleSource,
    ) -> list[ScoredRule]:
        """Vector-only retrieval using cosine similarity."""
        scored: list[ScoredRule] = []
        for rule in rules:
            score = self._compute_score(rule, query_embedding)
            scored.append(ScoredRule(rule=rule, score=score, source=source))
        return scored

    def _hybrid_retrieval(
        self,
        rules: list[Rule],
        query_embedding: list[float],
        query_text: str,
        source: RuleSource,
    ) -> list[ScoredRule]:
        """Hybrid retrieval combining vector and BM25 scores."""
        # Compute vector scores
        vector_scores = [
            cosine_similarity(query_embedding, rule.embedding)
            if rule.embedding
            else 0.0
            for rule in rules
        ]

        # Compute BM25 scores
        corpus = [rule.condition_text.split() for rule in rules]
        bm25 = BM25Okapi(corpus)
        bm25_scores = bm25.get_scores(query_text.split())

        # Combine scores
        combined_scores = self._hybrid_scorer.combine_scores(vector_scores, list(bm25_scores))

        # Build scored rules
        scored = [
            ScoredRule(rule=rule, score=score, source=source)
            for rule, score in zip(rules, combined_scores)
        ]

        return scored

    def _compute_score(self, rule: Rule, query_embedding: list[float]) -> float:
        """Compute similarity score for a rule."""
        if rule.embedding is None:
            return 0.0
        try:
            return cosine_similarity(query_embedding, rule.embedding)
        except ValueError:
            return 0.0

    def _passes_business_filters(
        self,
        rule: Rule,
        *,
        fired_rule_counts: dict[UUID, int],
        last_fired_turns: dict[UUID, int],
        current_turn: int,
    ) -> bool:
        """Apply enabled/max_fires/cooldown filters."""
        if not rule.enabled:
            return False

        if rule.max_fires_per_session > 0:
            fired_count = fired_rule_counts.get(rule.id, 0)
            if fired_count >= rule.max_fires_per_session:
                return False

        if rule.cooldown_turns > 0:
            last_fired = last_fired_turns.get(rule.id)
            if last_fired is not None and (current_turn - last_fired) <= rule.cooldown_turns:
                return False

        return True

    def _apply_selection(self, scored_rules: list[ScoredRule]) -> list[ScoredRule]:
        """Apply selection strategy and min_score filtering."""
        if not scored_rules:
            return []

        scored_rules = sorted(scored_rules, key=lambda r: r.score, reverse=True)

        # Filter by min_score but keep ability to satisfy min_k
        above_threshold = [
            rule for rule in scored_rules if rule.score >= self._selection_config.min_score
        ]
        pool = (
            above_threshold
            if len(above_threshold) >= self._selection_config.min_k
            else scored_rules
        )

        items = [ScoredItem(item=rule, score=rule.score) for rule in pool]
        selection = self._selection_strategy.select(
            items,
            max_k=self._selection_config.max_k,
            min_k=self._selection_config.min_k,
        )
        return [item.item for item in selection.selected]
