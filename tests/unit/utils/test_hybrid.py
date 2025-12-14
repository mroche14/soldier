"""Tests for hybrid scoring utilities."""

import pytest

from ruche.utils.hybrid import HybridScorer


class TestHybridScorer:
    """Test hybrid score combination."""

    def test_combine_scores_basic(self):
        """Test basic score combination."""
        scorer = HybridScorer(vector_weight=0.7, bm25_weight=0.3)
        vector_scores = [0.8, 0.6, 0.4]
        bm25_scores = [10.0, 5.0, 2.0]

        combined = scorer.combine_scores(vector_scores, bm25_scores)

        assert len(combined) == 3
        assert all(0.0 <= score <= 1.0 for score in combined)
        # Higher vector + higher bm25 should give highest combined score
        assert combined[0] > combined[1] > combined[2]

    def test_combine_scores_equal_weights(self):
        """Test combination with equal weights."""
        scorer = HybridScorer(vector_weight=0.5, bm25_weight=0.5)
        vector_scores = [1.0, 0.5]
        bm25_scores = [10.0, 20.0]

        combined = scorer.combine_scores(vector_scores, bm25_scores)

        assert len(combined) == 2
        # Second item has higher BM25, should influence final score
        assert combined[1] > combined[0]

    def test_combine_scores_mismatched_lengths_raises(self):
        """Test that mismatched score lists raise ValueError."""
        scorer = HybridScorer()
        vector_scores = [0.8, 0.6]
        bm25_scores = [10.0]

        with pytest.raises(ValueError, match="same length"):
            scorer.combine_scores(vector_scores, bm25_scores)

    def test_combine_scores_empty_lists(self):
        """Test empty score lists."""
        scorer = HybridScorer()
        combined = scorer.combine_scores([], [])
        assert combined == []

    def test_min_max_normalization(self):
        """Test min-max normalization."""
        scorer = HybridScorer(normalization="min_max")
        scores = [10.0, 5.0, 2.0, 1.0]

        normalized = scorer._min_max_normalize(scores)

        assert normalized[0] == 1.0  # Max score
        assert normalized[-1] == 0.0  # Min score
        assert all(0.0 <= score <= 1.0 for score in normalized)

    def test_min_max_normalization_identical_scores(self):
        """Test min-max normalization with identical scores."""
        scorer = HybridScorer(normalization="min_max")
        scores = [5.0, 5.0, 5.0]

        normalized = scorer._min_max_normalize(scores)

        # All identical scores should normalize to 1.0
        assert all(score == 1.0 for score in normalized)

    def test_z_score_normalization(self):
        """Test z-score normalization."""
        scorer = HybridScorer(normalization="z_score")
        scores = [10.0, 5.0, 0.0, -5.0]

        normalized = scorer._z_score_normalize(scores)

        assert len(normalized) == 4
        assert all(0.0 <= score <= 1.0 for score in normalized)
        # Higher raw scores should still be higher after normalization
        assert normalized[0] > normalized[1] > normalized[2] > normalized[3]

    def test_z_score_normalization_identical_scores(self):
        """Test z-score normalization with identical scores."""
        scorer = HybridScorer(normalization="z_score")
        scores = [5.0, 5.0, 5.0]

        normalized = scorer._z_score_normalize(scores)

        # All identical scores should normalize to 0.5 (middle value)
        assert all(score == 0.5 for score in normalized)

    def test_softmax_normalization(self):
        """Test softmax normalization."""
        scorer = HybridScorer(normalization="softmax")
        scores = [10.0, 5.0, 2.0]

        normalized = scorer._softmax_normalize(scores)

        assert len(normalized) == 3
        # Softmax values should sum to 1
        assert abs(sum(normalized) - 1.0) < 1e-6
        # Higher scores should have higher softmax values
        assert normalized[0] > normalized[1] > normalized[2]

    def test_softmax_normalization_overflow_protection(self):
        """Test softmax handles large scores without overflow."""
        scorer = HybridScorer(normalization="softmax")
        scores = [1000.0, 999.0, 998.0]

        normalized = scorer._softmax_normalize(scores)

        # Should not raise overflow error
        assert len(normalized) == 3
        assert abs(sum(normalized) - 1.0) < 1e-6

    def test_hybrid_scoring_vector_dominant(self):
        """Test hybrid scoring when vector weight dominates."""
        scorer = HybridScorer(vector_weight=0.9, bm25_weight=0.1)
        vector_scores = [0.9, 0.5, 0.1]
        bm25_scores = [1.0, 10.0, 5.0]  # BM25 disagrees with vector

        combined = scorer.combine_scores(vector_scores, bm25_scores)

        # Vector should dominate, so ordering should follow vector scores
        assert combined[0] > combined[1] > combined[2]

    def test_hybrid_scoring_bm25_dominant(self):
        """Test hybrid scoring when BM25 weight dominates."""
        scorer = HybridScorer(vector_weight=0.1, bm25_weight=0.9)
        vector_scores = [0.9, 0.5, 0.1]
        bm25_scores = [1.0, 10.0, 5.0]  # BM25 disagrees with vector

        combined = scorer.combine_scores(vector_scores, bm25_scores)

        # BM25 should dominate, so ordering should follow BM25 scores
        assert combined[1] > combined[2] > combined[0]

    def test_normalization_fallback_to_min_max(self):
        """Test that invalid normalization falls back to min_max."""
        scorer = HybridScorer(normalization="invalid_method")
        scores = [10.0, 5.0, 2.0]

        normalized = scorer._normalize(scores)

        # Should use min_max as fallback
        assert normalized[0] == 1.0
        assert normalized[-1] == 0.0
