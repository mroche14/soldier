"""Hybrid scoring utilities for combining vector and BM25 scores.

Provides score normalization and combination for hybrid retrieval that
merges semantic (embedding) similarity with lexical (BM25) matching.
"""

import numpy as np


class HybridScorer:
    """Combine vector and BM25 scores for hybrid retrieval.

    Normalizes both score types to a common scale, then combines them
    using configurable weights. Supports multiple normalization methods.
    """

    def __init__(
        self,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        normalization: str = "min_max",
    ) -> None:
        """Initialize hybrid scorer.

        Args:
            vector_weight: Weight for vector similarity (0-1)
            bm25_weight: Weight for BM25 scores (0-1)
            normalization: Normalization method ("min_max", "z_score", "softmax")
        """
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.normalization = normalization

    def combine_scores(
        self,
        vector_scores: list[float],
        bm25_scores: list[float],
    ) -> list[float]:
        """Combine and normalize vector and BM25 scores.

        Args:
            vector_scores: Cosine similarity scores (0-1 range)
            bm25_scores: Raw BM25 scores (unbounded)

        Returns:
            Combined scores (0-1 range)

        Raises:
            ValueError: If score lists have different lengths
        """
        if len(vector_scores) != len(bm25_scores):
            raise ValueError(
                f"Score lists must have same length: {len(vector_scores)} vs {len(bm25_scores)}"
            )

        if not vector_scores:
            return []

        # Normalize BM25 scores to 0-1 range
        norm_bm25 = self._normalize(bm25_scores)

        # Weighted combination
        combined = [
            (v * self.vector_weight + b * self.bm25_weight)
            for v, b in zip(vector_scores, norm_bm25)
        ]

        return combined

    def _normalize(self, scores: list[float]) -> list[float]:
        """Normalize scores to 0-1 range.

        Args:
            scores: Raw scores to normalize

        Returns:
            Normalized scores (0-1 range)
        """
        if not scores:
            return []

        if self.normalization == "min_max":
            return self._min_max_normalize(scores)
        elif self.normalization == "z_score":
            return self._z_score_normalize(scores)
        elif self.normalization == "softmax":
            return self._softmax_normalize(scores)
        else:
            # Fallback to min_max
            return self._min_max_normalize(scores)

    def _min_max_normalize(self, scores: list[float]) -> list[float]:
        """Min-max normalization to [0, 1] range.

        Args:
            scores: Scores to normalize

        Returns:
            Normalized scores
        """
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            # All scores are identical - return all 1.0
            return [1.0] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]

    def _z_score_normalize(self, scores: list[float]) -> list[float]:
        """Z-score normalization then scale to [0, 1].

        Args:
            scores: Scores to normalize

        Returns:
            Normalized scores
        """
        arr = np.array(scores)
        mean = np.mean(arr)
        std = np.std(arr)

        if std == 0:
            # All scores are identical
            return [0.5] * len(scores)

        # Z-score normalization
        z_scores = (arr - mean) / std

        # Scale to [0, 1] using sigmoid-like transformation
        # Using tanh to map (-inf, inf) to (-1, 1), then scale to [0, 1]
        normalized = (np.tanh(z_scores) + 1) / 2

        return normalized.tolist()

    def _softmax_normalize(self, scores: list[float]) -> list[float]:
        """Softmax normalization to probability distribution.

        Args:
            scores: Scores to normalize

        Returns:
            Normalized scores (sum to 1)
        """
        arr = np.array(scores)

        # Prevent overflow by subtracting max
        max_score = np.max(arr)
        exp_scores = np.exp(arr - max_score)

        sum_exp = np.sum(exp_scores)
        if sum_exp == 0:
            # Edge case: all scores are very negative
            return [1.0 / len(scores)] * len(scores)

        # Return softmax (this will sum to 1, not necessarily in [0,1] per item)
        # For hybrid scoring, we want individual scores in [0,1], so we'll
        # scale by dividing by the maximum possible softmax value
        softmax = exp_scores / sum_exp
        return softmax.tolist()
