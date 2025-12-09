"""Alignment retrieval module.

Contains components for retrieving candidate rules, scenarios, intents, and memory
using vector similarity and selection strategies.
"""

from focal.alignment.retrieval.intent_retriever import (
    IntentRetriever,
    decide_canonical_intent,
)
from focal.alignment.retrieval.models import (
    RetrievalResult,
    RuleSource,
    ScoredEpisode,
    ScoredRule,
    ScoredScenario,
)
from focal.alignment.retrieval.reranker import RuleReranker, ScenarioReranker
from focal.alignment.retrieval.rule_retriever import RuleRetriever
from focal.alignment.retrieval.scenario_retriever import ScenarioRetriever
from focal.alignment.retrieval.selection import (
    AdaptiveKSelectionStrategy,
    ClusterSelectionStrategy,
    ElbowSelectionStrategy,
    EntropySelectionStrategy,
    FixedKSelectionStrategy,
    ScoredItem,
    SelectionResult,
    SelectionStrategy,
    create_selection_strategy,
)

__all__ = [
    # Selection strategies
    "SelectionStrategy",
    "ScoredItem",
    "SelectionResult",
    "FixedKSelectionStrategy",
    "ElbowSelectionStrategy",
    "AdaptiveKSelectionStrategy",
    "EntropySelectionStrategy",
    "ClusterSelectionStrategy",
    "create_selection_strategy",
    # Retrieval components
    "RuleRetriever",
    "RuleReranker",
    "ScenarioRetriever",
    "ScenarioReranker",
    "IntentRetriever",
    "decide_canonical_intent",
    # Retrieval models
    "ScoredRule",
    "ScoredScenario",
    "ScoredEpisode",
    "RuleSource",
    "RetrievalResult",
]
