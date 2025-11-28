"""Rule retrieval with scope hierarchy and business filters."""

import time
from uuid import UUID

from soldier.alignment.context.models import Context
from soldier.alignment.models import Rule, Scope
from soldier.alignment.retrieval.models import RetrievalResult, RuleSource, ScoredRule
from soldier.alignment.retrieval.reranker import RuleReranker
from soldier.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from soldier.alignment.stores import ConfigStore
from soldier.config.models.selection import SelectionConfig
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider
from soldier.utils.vector import cosine_similarity

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
        config_store: ConfigStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
        reranker: RuleReranker | None = None,
    ) -> None:
        """Initialize the rule retriever.

        Args:
            config_store: Store for rule definitions
            embedding_provider: Provider for query embeddings
            selection_config: Configuration for selection strategy
            reranker: Optional reranker for result refinement
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )
        self._reranker = reranker

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        context: Context,
        *,
        active_scenario_id: UUID | None = None,
        active_step_id: UUID | None = None,
        fired_rule_counts: dict[UUID, int] | None = None,
        last_fired_turns: dict[UUID, int] | None = None,
    ) -> RetrievalResult:
        """Retrieve rules across scopes with business filters applied.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            context: Extracted context with embedding
            active_scenario_id: Current scenario for scenario-scoped rules
            active_step_id: Current step for step-scoped rules
            fired_rule_counts: Rule fire counts for max_fires filter
            last_fired_turns: Last fire turn for cooldown filter

        Returns:
            RetrievalResult with scored rules and metadata
        """
        fired_rule_counts = fired_rule_counts or {}
        last_fired_turns = last_fired_turns or {}

        start_time = time.perf_counter()

        embedding = context.embedding
        if embedding is None:
            embedding = await self._embedding_provider.embed_single(context.message)

        candidates: list[ScoredRule] = []
        candidates.extend(
            await self._retrieve_scope(
                tenant_id,
                agent_id,
                scope=Scope.GLOBAL,
                scope_id=None,
                source=RuleSource.GLOBAL,
                embedding=embedding,
                fired_rule_counts=fired_rule_counts,
                last_fired_turns=last_fired_turns,
                current_turn=context.turn_count,
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
                    fired_rule_counts=fired_rule_counts,
                    last_fired_turns=last_fired_turns,
                    current_turn=context.turn_count,
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
                    fired_rule_counts=fired_rule_counts,
                    last_fired_turns=last_fired_turns,
                    current_turn=context.turn_count,
                )
            )

        # Optional reranking
        if self._reranker and candidates:
            candidates = await self._reranker.rerank(context.message, candidates)

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

        scored: list[ScoredRule] = []
        for rule in rules:
            if not self._passes_business_filters(
                rule,
                fired_rule_counts=fired_rule_counts,
                last_fired_turns=last_fired_turns,
                current_turn=current_turn,
            ):
                continue

            score = self._compute_score(rule, embedding)
            scored.append(ScoredRule(rule=rule, score=score, source=source))

        # Sort by score descending for selection
        scored.sort(key=lambda r: r.score, reverse=True)
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
