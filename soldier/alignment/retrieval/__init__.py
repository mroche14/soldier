"""Alignment retrieval module.

Contains components for retrieving candidate rules, scenarios, and memory
using vector similarity and selection strategies.
"""

from soldier.alignment.retrieval.models import (
    RetrievalResult,
    RuleSource,
    ScoredEpisode,
    ScoredRule,
    ScoredScenario,
)
from soldier.alignment.retrieval.reranker import RuleReranker
from soldier.alignment.retrieval.rule_retriever import RuleRetriever
from soldier.alignment.retrieval.scenario_retriever import ScenarioRetriever
from soldier.alignment.retrieval.selection import (
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
    # Retrieval models
    "ScoredRule",
    "ScoredScenario",
    "ScoredEpisode",
    "RuleSource",
    "RetrievalResult",
]
