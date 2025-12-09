"""Unit tests for selection strategies."""

import pytest

from focal.alignment.retrieval.selection import (
    AdaptiveKSelectionStrategy,
    ClusterSelectionStrategy,
    ElbowSelectionStrategy,
    EntropySelectionStrategy,
    FixedKSelectionStrategy,
    ScoredItem,
    create_selection_strategy,
)


class TestScoredItem:
    """Tests for ScoredItem dataclass."""

    def test_create_valid_scored_item(self) -> None:
        """Test creating a scored item with valid score."""
        item = ScoredItem(item="test", score=0.5)
        assert item.item == "test"
        assert item.score == 0.5

    def test_score_boundary_zero(self) -> None:
        """Test score at lower boundary."""
        item = ScoredItem(item="test", score=0.0)
        assert item.score == 0.0

    def test_score_boundary_one(self) -> None:
        """Test score at upper boundary."""
        item = ScoredItem(item="test", score=1.0)
        assert item.score == 1.0

    def test_invalid_score_below_zero(self) -> None:
        """Test that negative scores raise ValueError."""
        with pytest.raises(ValueError, match="Score must be between 0.0 and 1.0"):
            ScoredItem(item="test", score=-0.1)

    def test_invalid_score_above_one(self) -> None:
        """Test that scores above 1 raise ValueError."""
        with pytest.raises(ValueError, match="Score must be between 0.0 and 1.0"):
            ScoredItem(item="test", score=1.1)


class TestFixedKSelectionStrategy:
    """Tests for FixedKSelectionStrategy."""

    def test_name_property(self) -> None:
        """Test strategy name."""
        strategy = FixedKSelectionStrategy(k=5)
        assert strategy.name == "fixed_k"

    def test_select_exact_k_items(self) -> None:
        """Test selecting exactly k items."""
        strategy = FixedKSelectionStrategy(k=3)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.8),
            ScoredItem(item="c", score=0.7),
            ScoredItem(item="d", score=0.6),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 3
        assert result.method == "fixed_k"
        assert result.cutoff_score == 0.7

    def test_select_fewer_than_k_when_not_enough_items(self) -> None:
        """Test when fewer items than k are available."""
        strategy = FixedKSelectionStrategy(k=10)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.8),
        ]
        result = strategy.select(items, max_k=20, min_k=1)

        assert len(result.selected) == 2

    def test_select_respects_max_k(self) -> None:
        """Test that max_k limits output."""
        strategy = FixedKSelectionStrategy(k=10)
        items = [ScoredItem(item=str(i), score=1.0 - i * 0.1) for i in range(10)]
        result = strategy.select(items, max_k=5, min_k=1)

        assert len(result.selected) == 5

    def test_select_respects_min_k(self) -> None:
        """Test that min_k ensures minimum output."""
        strategy = FixedKSelectionStrategy(k=1, min_score=0.9)
        items = [
            ScoredItem(item="a", score=0.5),
            ScoredItem(item="b", score=0.4),
            ScoredItem(item="c", score=0.3),
        ]
        result = strategy.select(items, max_k=10, min_k=2)

        # Even though min_score filters everything, min_k ensures we get 2
        assert len(result.selected) == 2

    def test_select_empty_list(self) -> None:
        """Test with empty input."""
        strategy = FixedKSelectionStrategy(k=5)
        result = strategy.select([], max_k=10, min_k=1)

        assert len(result.selected) == 0
        assert result.cutoff_score == 0.0

    def test_select_with_min_score_filter(self) -> None:
        """Test that min_score filters items."""
        strategy = FixedKSelectionStrategy(k=10, min_score=0.5)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.6),
            ScoredItem(item="c", score=0.3),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 2
        assert all(item.score >= 0.5 for item in result.selected)


class TestElbowSelectionStrategy:
    """Tests for ElbowSelectionStrategy."""

    def test_name_property(self) -> None:
        """Test strategy name."""
        strategy = ElbowSelectionStrategy()
        assert strategy.name == "elbow"

    def test_detect_clear_elbow(self) -> None:
        """Test detection of clear score drop."""
        strategy = ElbowSelectionStrategy(drop_threshold=0.3, min_score=0.0)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.85),
            ScoredItem(item="c", score=0.5),  # 41% drop - elbow
            ScoredItem(item="d", score=0.4),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        # Should cut at the elbow (after item b)
        assert len(result.selected) == 2
        assert result.metadata["elbow_idx"] == 2

    def test_no_elbow_detected(self) -> None:
        """Test when scores are uniform."""
        strategy = ElbowSelectionStrategy(drop_threshold=0.5, min_score=0.0)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.88),
            ScoredItem(item="c", score=0.86),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        # No significant drop, include all
        assert len(result.selected) == 3

    def test_respects_min_score(self) -> None:
        """Test that min_score filters items."""
        strategy = ElbowSelectionStrategy(drop_threshold=0.1, min_score=0.5)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.4),  # Below min_score
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 1

    def test_empty_list(self) -> None:
        """Test with empty input."""
        strategy = ElbowSelectionStrategy()
        result = strategy.select([], max_k=10, min_k=1)

        assert len(result.selected) == 0


class TestAdaptiveKSelectionStrategy:
    """Tests for AdaptiveKSelectionStrategy."""

    def test_name_property(self) -> None:
        """Test strategy name."""
        strategy = AdaptiveKSelectionStrategy()
        assert strategy.name == "adaptive_k"

    def test_detect_curvature_point(self) -> None:
        """Test detection of score distribution curvature."""
        strategy = AdaptiveKSelectionStrategy(alpha=1.0, min_score=0.0)
        items = [
            ScoredItem(item="a", score=0.95),
            ScoredItem(item="b", score=0.90),
            ScoredItem(item="c", score=0.85),
            ScoredItem(item="d", score=0.50),  # Sharp drop
            ScoredItem(item="e", score=0.45),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        # Should detect curvature at the sharp drop
        assert len(result.selected) <= 4
        assert result.metadata["alpha"] == 1.0

    def test_handles_two_items(self) -> None:
        """Test with only two items (not enough for curvature)."""
        strategy = AdaptiveKSelectionStrategy(min_score=0.5)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.6),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 2
        assert result.metadata["reason"] == "insufficient_points"

    def test_respects_min_score(self) -> None:
        """Test that min_score filters items."""
        strategy = AdaptiveKSelectionStrategy(alpha=1.0, min_score=0.6)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.7),
            ScoredItem(item="c", score=0.4),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert all(item.score >= 0.6 for item in result.selected)

    def test_empty_list(self) -> None:
        """Test with empty input."""
        strategy = AdaptiveKSelectionStrategy()
        result = strategy.select([], max_k=10, min_k=1)

        assert len(result.selected) == 0


class TestEntropySelectionStrategy:
    """Tests for EntropySelectionStrategy."""

    def test_name_property(self) -> None:
        """Test strategy name."""
        strategy = EntropySelectionStrategy()
        assert strategy.name == "entropy"

    def test_low_entropy_selects_fewer(self) -> None:
        """Test that low entropy (concentrated scores) selects fewer items."""
        strategy = EntropySelectionStrategy(
            low_entropy_k=2,
            high_entropy_k=8,
            entropy_threshold=0.5,
            min_score=0.0,
        )
        # Concentrated scores = low entropy
        items = [
            ScoredItem(item="a", score=0.95),
            ScoredItem(item="b", score=0.05),
            ScoredItem(item="c", score=0.05),
            ScoredItem(item="d", score=0.05),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert result.metadata["entropy"] < 0.5
        # Should use low_entropy_k
        assert len(result.selected) <= 2

    def test_high_entropy_selects_more(self) -> None:
        """Test that high entropy (spread scores) selects more items."""
        strategy = EntropySelectionStrategy(
            low_entropy_k=2,
            high_entropy_k=8,
            entropy_threshold=0.3,
            min_score=0.0,
        )
        # Spread scores = high entropy
        items = [
            ScoredItem(item=str(i), score=0.9 - i * 0.05)
            for i in range(10)
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert result.metadata["entropy"] > 0.3
        # Should use high_entropy_k
        assert len(result.selected) >= 2

    def test_respects_min_score(self) -> None:
        """Test that min_score filters items."""
        strategy = EntropySelectionStrategy(min_score=0.5)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.3),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 1
        assert result.selected[0].score >= 0.5

    def test_empty_list(self) -> None:
        """Test with empty input."""
        strategy = EntropySelectionStrategy()
        result = strategy.select([], max_k=10, min_k=1)

        assert len(result.selected) == 0
        assert result.metadata["entropy"] == 0.0


class TestClusterSelectionStrategy:
    """Tests for ClusterSelectionStrategy."""

    def test_name_property(self) -> None:
        """Test strategy name."""
        strategy = ClusterSelectionStrategy()
        assert strategy.name == "clustering"

    def test_cluster_distinct_score_groups(self) -> None:
        """Test clustering of distinct score groups."""
        strategy = ClusterSelectionStrategy(
            eps=0.1,
            top_per_cluster=2,
            min_score=0.0,
        )
        items = [
            # High cluster
            ScoredItem(item="a", score=0.95),
            ScoredItem(item="b", score=0.92),
            ScoredItem(item="c", score=0.90),
            # Low cluster
            ScoredItem(item="d", score=0.55),
            ScoredItem(item="e", score=0.52),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        # Should select from both clusters
        assert len(result.selected) >= 2
        assert "n_clusters" in result.metadata

    def test_respects_min_score(self) -> None:
        """Test that min_score filters items before clustering."""
        strategy = ClusterSelectionStrategy(min_score=0.5)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.3),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 1

    def test_handles_few_items(self) -> None:
        """Test with fewer items than top_per_cluster."""
        strategy = ClusterSelectionStrategy(top_per_cluster=5, min_score=0.0)
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.8),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        assert len(result.selected) == 2

    def test_empty_list(self) -> None:
        """Test with empty input."""
        strategy = ClusterSelectionStrategy()
        result = strategy.select([], max_k=10, min_k=1)

        assert len(result.selected) == 0
        assert result.metadata["n_clusters"] == 0


class TestCreateSelectionStrategy:
    """Tests for the factory function."""

    @pytest.mark.parametrize(
        "strategy_name,expected_type",
        [
            ("fixed_k", FixedKSelectionStrategy),
            ("elbow", ElbowSelectionStrategy),
            ("adaptive_k", AdaptiveKSelectionStrategy),
            ("entropy", EntropySelectionStrategy),
            ("clustering", ClusterSelectionStrategy),
        ],
    )
    def test_create_all_strategies(
        self,
        strategy_name: str,
        expected_type: type,
    ) -> None:
        """Test creating each strategy type."""
        strategy = create_selection_strategy(strategy_name)
        assert isinstance(strategy, expected_type)
        assert strategy.name == strategy_name

    def test_create_with_params(self) -> None:
        """Test creating strategy with custom params."""
        strategy = create_selection_strategy("fixed_k", k=15, min_score=0.7)
        assert isinstance(strategy, FixedKSelectionStrategy)

    def test_invalid_strategy_raises(self) -> None:
        """Test that invalid strategy name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            create_selection_strategy("invalid_strategy")


class TestSelectionStrategyValidation:
    """Tests for input validation across all strategies."""

    @pytest.fixture(
        params=[
            FixedKSelectionStrategy(),
            ElbowSelectionStrategy(),
            AdaptiveKSelectionStrategy(),
            EntropySelectionStrategy(),
            ClusterSelectionStrategy(),
        ],
    )
    def strategy(self, request: pytest.FixtureRequest) -> "FixedKSelectionStrategy":
        """Provide each strategy type for testing."""
        return request.param

    def test_min_k_greater_than_max_k_raises(
        self,
        strategy: FixedKSelectionStrategy,
    ) -> None:
        """Test that min_k > max_k raises ValueError."""
        items = [ScoredItem(item="a", score=0.9)]
        with pytest.raises(ValueError, match="min_k.*cannot be greater than max_k"):
            strategy.select(items, max_k=5, min_k=10)

    def test_unsorted_items_raises(
        self,
        strategy: FixedKSelectionStrategy,
    ) -> None:
        """Test that unsorted items raise ValueError."""
        items = [
            ScoredItem(item="a", score=0.5),
            ScoredItem(item="b", score=0.9),  # Out of order
        ]
        with pytest.raises(ValueError, match="sorted by score descending"):
            strategy.select(items, max_k=10, min_k=1)

    def test_results_sorted_descending(
        self,
        strategy: FixedKSelectionStrategy,
    ) -> None:
        """Test that results are always sorted by score descending."""
        items = [
            ScoredItem(item="a", score=0.9),
            ScoredItem(item="b", score=0.8),
            ScoredItem(item="c", score=0.7),
        ]
        result = strategy.select(items, max_k=10, min_k=1)

        scores = [item.score for item in result.selected]
        assert scores == sorted(scores, reverse=True)
