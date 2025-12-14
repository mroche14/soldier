"""Reranker wrappers for retrieval (rules, scenarios, memory, intents)."""

from collections.abc import Iterable

from ruche.alignment.models import Rule
from ruche.alignment.retrieval.models import ScoredRule, ScoredScenario
from ruche.observability.logging import get_logger
from ruche.providers.rerank import RerankProvider

logger = get_logger(__name__)


class RuleReranker:
    """Apply a rerank provider to reorder scored rules.

    Reranking improves retrieval precision by using a cross-encoder
    model to score query-document pairs more accurately than
    embedding-based similarity alone.
    """

    def __init__(self, provider: RerankProvider, top_k: int | None = None) -> None:
        """Initialize the reranker.

        Args:
            provider: RerankProvider implementation
            top_k: Optional limit on results to keep from reranker
        """
        self._provider = provider
        self._top_k = top_k

    async def rerank(
        self,
        query: str,
        scored_rules: list[ScoredRule],
    ) -> list[ScoredRule]:
        """Rerank scored rules using the provider.

        Args:
            query: Query text to rank against
            scored_rules: Existing scored rules

        Returns:
            Reranked scored rules (may be a subset if top_k is set)
        """
        if not scored_rules:
            return []

        documents = [self._format_rule(rule.rule) for rule in scored_rules]
        response = await self._provider.rerank(
            query=query,
            documents=documents,
            top_k=self._top_k,
        )

        index_map = dict(enumerate(scored_rules))
        reranked: list[ScoredRule] = []

        for result in response.results:
            candidate = index_map.get(result.index)
            if candidate:
                reranked.append(
                    ScoredRule(
                        rule=candidate.rule,
                        score=result.score,
                        source=candidate.source,
                    )
                )

        if not reranked:
            logger.debug("rerank_no_results", count=len(scored_rules))
            return scored_rules

        return reranked

    def _format_rule(self, rule: Rule) -> str:
        """Format rule text for reranking."""
        return "\n".join(self._non_empty([rule.condition_text, rule.action_text]))

    def _non_empty(self, items: Iterable[str]) -> list[str]:
        """Return non-empty strings from iterable."""
        return [item for item in items if item]


class ScenarioReranker:
    """Apply a rerank provider to reorder scored scenarios.

    Reranking improves scenario selection precision by using a cross-encoder
    model to score query-scenario pairs more accurately.
    """

    def __init__(self, provider: RerankProvider, top_k: int | None = None) -> None:
        """Initialize the reranker.

        Args:
            provider: RerankProvider implementation
            top_k: Optional limit on results to keep from reranker
        """
        self._provider = provider
        self._top_k = top_k

    async def rerank(
        self,
        query: str,
        scored_scenarios: list[ScoredScenario],
    ) -> list[ScoredScenario]:
        """Rerank scored scenarios using the provider.

        Args:
            query: Query text to rank against
            scored_scenarios: Existing scored scenarios

        Returns:
            Reranked scored scenarios (may be a subset if top_k is set)
        """
        if not scored_scenarios:
            return []

        documents = [scenario.scenario_name for scenario in scored_scenarios]
        response = await self._provider.rerank(
            query=query,
            documents=documents,
            top_k=self._top_k,
        )

        index_map = dict(enumerate(scored_scenarios))
        reranked: list[ScoredScenario] = []

        for result in response.results:
            candidate = index_map.get(result.index)
            if candidate:
                reranked.append(
                    ScoredScenario(
                        scenario_id=candidate.scenario_id,
                        scenario_name=candidate.scenario_name,
                        score=result.score,
                    )
                )

        if not reranked:
            logger.debug("rerank_no_results", count=len(scored_scenarios))
            return scored_scenarios

        return reranked
