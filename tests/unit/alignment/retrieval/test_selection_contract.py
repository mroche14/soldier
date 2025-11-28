"""Contract tests for SelectionStrategy interface.

These tests define the contract that ALL SelectionStrategy implementations
must satisfy. Each implementation must pass all these tests.
"""

from abc import ABC, abstractmethod

import pytest

from soldier.alignment.retrieval.selection import (
    AdaptiveKSelectionStrategy,
    ClusterSelectionStrategy,
    ElbowSelectionStrategy,
    EntropySelectionStrategy,
    FixedKSelectionStrategy,
    ScoredItem,
    SelectionResult,
    SelectionStrategy,
)


class SelectionStrategyContract(ABC):
    """Contract tests that all SelectionStrategy implementations must pass.

    Subclass this and provide a strategy fixture to test your implementation.
    """

    @pytest.fixture
    @abstractmethod
    def strategy(self) -> SelectionStrategy:
        """Return the strategy implementation to test."""
        pass

    @pytest.fixture
    def scored_items(self) -> list[ScoredItem[str]]:
        """Standard test items sorted by score descending."""
        return [
            ScoredItem(item="a", score=0.95),
            ScoredItem(item="b", score=0.85),
            ScoredItem(item="c", score=0.75),
            ScoredItem(item="d", score=0.65),
            ScoredItem(item="e", score=0.55),
            ScoredItem(item="f", score=0.45),
            ScoredItem(item="g", score=0.35),
        ]

    # --- Contract: name property ---

    def test_name_returns_string(self, strategy: SelectionStrategy) -> None:
        """Contract: name property must return a non-empty string."""
        assert isinstance(strategy.name, str)
        assert len(strategy.name) > 0

    # --- Contract: select method ---

    def test_select_returns_selection_result(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: select must return a SelectionResult."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        assert isinstance(result, SelectionResult)

    def test_select_result_has_required_fields(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: SelectionResult must have all required fields."""
        result = strategy.select(scored_items, max_k=10, min_k=1)

        assert hasattr(result, "selected")
        assert hasattr(result, "cutoff_score")
        assert hasattr(result, "method")
        assert hasattr(result, "metadata")

    def test_select_method_matches_strategy_name(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: result.method must equal strategy.name."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        assert result.method == strategy.name

    # --- Contract: max_k constraint ---

    def test_select_never_exceeds_max_k(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: never return more than max_k items."""
        result = strategy.select(scored_items, max_k=3, min_k=1)
        assert len(result.selected) <= 3

    def test_select_max_k_one(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: max_k=1 should return at most 1 item."""
        result = strategy.select(scored_items, max_k=1, min_k=1)
        assert len(result.selected) <= 1

    # --- Contract: min_k constraint ---

    def test_select_returns_at_least_min_k_when_available(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: return at least min_k items when enough are available."""
        result = strategy.select(scored_items, max_k=10, min_k=3)
        assert len(result.selected) >= 3

    def test_select_returns_all_when_fewer_than_min_k(
        self,
        strategy: SelectionStrategy,
    ) -> None:
        """Contract: return all items when fewer than min_k available."""
        items = [ScoredItem(item="a", score=0.9)]
        result = strategy.select(items, max_k=10, min_k=5)
        # Can't return min_k=5 when only 1 item exists
        assert len(result.selected) == 1

    # --- Contract: ordering ---

    def test_select_results_sorted_descending(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: selected items must be sorted by score descending."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        scores = [item.score for item in result.selected]
        assert scores == sorted(scores, reverse=True)

    # --- Contract: cutoff_score ---

    def test_select_cutoff_score_is_minimum(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: cutoff_score equals the lowest score in selected."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        if result.selected:
            min_score = min(item.score for item in result.selected)
            assert result.cutoff_score == min_score

    def test_select_all_selected_above_cutoff(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: all selected items have score >= cutoff_score."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        for item in result.selected:
            assert item.score >= result.cutoff_score

    # --- Contract: empty input ---

    def test_select_empty_input_returns_empty(
        self,
        strategy: SelectionStrategy,
    ) -> None:
        """Contract: empty input returns empty result."""
        result = strategy.select([], max_k=10, min_k=1)
        assert len(result.selected) == 0
        assert result.cutoff_score == 0.0

    # --- Contract: validation ---

    def test_select_rejects_unsorted_input(
        self,
        strategy: SelectionStrategy,
    ) -> None:
        """Contract: unsorted input raises ValueError."""
        unsorted = [
            ScoredItem(item="a", score=0.5),
            ScoredItem(item="b", score=0.9),
        ]
        with pytest.raises(ValueError):
            strategy.select(unsorted, max_k=10, min_k=1)

    def test_select_rejects_min_k_greater_than_max_k(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: min_k > max_k raises ValueError."""
        with pytest.raises(ValueError):
            strategy.select(scored_items, max_k=5, min_k=10)

    # --- Contract: metadata ---

    def test_select_metadata_is_dict(
        self,
        strategy: SelectionStrategy,
        scored_items: list[ScoredItem[str]],
    ) -> None:
        """Contract: metadata must be a dict."""
        result = strategy.select(scored_items, max_k=10, min_k=1)
        assert isinstance(result.metadata, dict)


# --- Concrete test classes for each implementation ---


class TestFixedKStrategyContract(SelectionStrategyContract):
    """Contract tests for FixedKSelectionStrategy."""

    @pytest.fixture
    def strategy(self) -> SelectionStrategy:
        return FixedKSelectionStrategy(k=5, min_score=0.0)


class TestElbowStrategyContract(SelectionStrategyContract):
    """Contract tests for ElbowSelectionStrategy."""

    @pytest.fixture
    def strategy(self) -> SelectionStrategy:
        return ElbowSelectionStrategy(drop_threshold=0.2, min_score=0.0)


class TestAdaptiveKStrategyContract(SelectionStrategyContract):
    """Contract tests for AdaptiveKSelectionStrategy."""

    @pytest.fixture
    def strategy(self) -> SelectionStrategy:
        return AdaptiveKSelectionStrategy(alpha=1.5, min_score=0.0)


class TestEntropyStrategyContract(SelectionStrategyContract):
    """Contract tests for EntropySelectionStrategy."""

    @pytest.fixture
    def strategy(self) -> SelectionStrategy:
        return EntropySelectionStrategy(
            low_entropy_k=3,
            high_entropy_k=7,
            entropy_threshold=0.5,
            min_score=0.0,
        )


class TestClusteringStrategyContract(SelectionStrategyContract):
    """Contract tests for ClusterSelectionStrategy."""

    @pytest.fixture
    def strategy(self) -> SelectionStrategy:
        return ClusterSelectionStrategy(
            eps=0.1,
            min_samples=1,
            top_per_cluster=3,
            min_score=0.0,
        )
