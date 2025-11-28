"""Selection strategies for dynamic k-selection after similarity search.

Selection strategies analyze score distributions to dynamically determine
the optimal number of results to keep, rather than using a fixed top-k.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import numpy as np
from scipy import stats
from sklearn.cluster import DBSCAN

T = TypeVar("T")


@dataclass
class ScoredItem(Generic[T]):
    """An item with its similarity score.

    Attributes:
        item: The item being scored
        score: Similarity score between 0.0 and 1.0
    """

    item: T
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")


@dataclass
class SelectionResult(Generic[T]):
    """Result of selection with metadata.

    Attributes:
        selected: Items that passed selection
        cutoff_score: Score threshold used for cutoff
        method: Name of the strategy used
        metadata: Strategy-specific metadata for logging/debugging
    """

    selected: list[ScoredItem[T]]
    cutoff_score: float
    method: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SelectionStrategy(ABC):
    """Interface for dynamic k-selection after similarity search.

    Selection strategies analyze score distributions to dynamically
    determine the optimal number of results to keep, rather than
    using a fixed top-k.

    Contract guarantees:
        - Always returns at least min_k items if available
        - Never returns more than max_k items
        - Items in result.selected are sorted by score descending
        - All items in result.selected have score >= cutoff_score
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy identifier for logging."""
        pass

    @abstractmethod
    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        """Select items based on score distribution.

        Args:
            items: List of scored items, MUST be sorted by score descending
            max_k: Maximum items to return (hard cap)
            min_k: Minimum items to return (even if scores are low)

        Returns:
            SelectionResult with selected items and metadata

        Raises:
            ValueError: If items is not sorted by score descending
            ValueError: If min_k > max_k
        """
        pass

    def _validate_inputs(
        self,
        items: list[ScoredItem[T]],
        max_k: int,
        min_k: int,
    ) -> None:
        """Validate common inputs for all strategies."""
        if min_k > max_k:
            raise ValueError(f"min_k ({min_k}) cannot be greater than max_k ({max_k})")
        if len(items) > 1:
            for i in range(len(items) - 1):
                if items[i].score < items[i + 1].score:
                    raise ValueError("Items must be sorted by score descending")


class FixedKSelectionStrategy(SelectionStrategy):
    """Simple top-k selection strategy.

    Always returns exactly k items (or fewer if not enough items available).
    Used as baseline/fallback when dynamic selection is not needed.
    """

    def __init__(self, k: int = 10, min_score: float = 0.0) -> None:
        """Initialize fixed-k strategy.

        Args:
            k: Number of items to select
            min_score: Minimum score threshold (items below are excluded)
        """
        self._k = k
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "fixed_k"

    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        self._validate_inputs(items, max_k, min_k)

        if not items:
            return SelectionResult(
                selected=[],
                cutoff_score=0.0,
                method=self.name,
                metadata={"k": self._k},
            )

        # Apply k limit and max_k constraint
        effective_k = min(self._k, max_k)

        # Filter by min_score and take top k
        filtered = [item for item in items if item.score >= self._min_score]
        selected = filtered[:effective_k]

        # Ensure min_k is satisfied (even if below min_score)
        if len(selected) < min_k and len(items) >= min_k:
            selected = items[:min_k]

        cutoff = selected[-1].score if selected else 0.0

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff,
            method=self.name,
            metadata={"k": self._k, "min_score": self._min_score},
        )


class ElbowSelectionStrategy(SelectionStrategy):
    """Selection using elbow detection in score distribution.

    Finds the point where scores drop significantly relative to previous
    scores. Best for cases with clear separations between relevant and
    irrelevant items.
    """

    def __init__(
        self,
        drop_threshold: float = 0.2,
        min_score: float = 0.5,
    ) -> None:
        """Initialize elbow strategy.

        Args:
            drop_threshold: Relative drop threshold to detect elbow (0-1)
            min_score: Minimum absolute score threshold
        """
        self._drop_threshold = drop_threshold
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "elbow"

    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        self._validate_inputs(items, max_k, min_k)

        if not items:
            return SelectionResult(
                selected=[],
                cutoff_score=0.0,
                method=self.name,
                metadata={"drop_threshold": self._drop_threshold},
            )

        # Find elbow point by detecting relative score drop
        elbow_idx = len(items)
        for i in range(1, len(items)):
            if items[i - 1].score > 0:
                relative_drop = (items[i - 1].score - items[i].score) / items[i - 1].score
                if relative_drop > self._drop_threshold:
                    elbow_idx = i
                    break

        # Apply min_score filter
        score_cutoff_idx = len(items)
        for i, item in enumerate(items):
            if item.score < self._min_score:
                score_cutoff_idx = i
                break

        # Use the more restrictive cutoff
        cutoff_idx = min(elbow_idx, score_cutoff_idx, max_k)

        # Ensure min_k constraint
        cutoff_idx = max(cutoff_idx, min(min_k, len(items)))

        selected = items[:cutoff_idx]
        cutoff = selected[-1].score if selected else 0.0

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff,
            method=self.name,
            metadata={
                "drop_threshold": self._drop_threshold,
                "min_score": self._min_score,
                "elbow_idx": elbow_idx,
            },
        )


class AdaptiveKSelectionStrategy(SelectionStrategy):
    """Selection using curvature analysis of score distribution.

    Analyzes the second derivative of the score curve to find optimal
    cutoff points. Works well for general-purpose retrieval.
    """

    def __init__(
        self,
        alpha: float = 1.5,
        min_score: float = 0.5,
    ) -> None:
        """Initialize adaptive-k strategy.

        Args:
            alpha: Curvature sensitivity multiplier (higher = more selective)
            min_score: Minimum absolute score threshold
        """
        self._alpha = alpha
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "adaptive_k"

    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        self._validate_inputs(items, max_k, min_k)

        if not items:
            return SelectionResult(
                selected=[],
                cutoff_score=0.0,
                method=self.name,
                metadata={"alpha": self._alpha},
            )

        if len(items) <= 2:
            # Not enough points for curvature analysis
            selected = [item for item in items if item.score >= self._min_score]
            if len(selected) < min_k:
                selected = items[:min_k]
            return SelectionResult(
                selected=selected[:max_k],
                cutoff_score=selected[-1].score if selected else 0.0,
                method=self.name,
                metadata={"alpha": self._alpha, "reason": "insufficient_points"},
            )

        scores = np.array([item.score for item in items])

        # Compute first and second derivatives
        first_deriv = np.diff(scores)
        second_deriv = np.diff(first_deriv) if len(first_deriv) > 1 else np.array([0])

        # Find point of maximum curvature (most negative second derivative)
        if len(second_deriv) > 0:
            # Normalize by standard deviation to make alpha scale-independent
            std = np.std(second_deriv) if np.std(second_deriv) > 0 else 1.0
            threshold = -self._alpha * std
            curvature_idx = len(items)
            for i, d2 in enumerate(second_deriv):
                if d2 < threshold:
                    curvature_idx = i + 2  # +2 because of double diff
                    break
        else:
            curvature_idx = len(items)

        # Apply min_score filter
        score_cutoff_idx = len(items)
        for i, item in enumerate(items):
            if item.score < self._min_score:
                score_cutoff_idx = i
                break

        # Use more restrictive cutoff
        cutoff_idx = min(curvature_idx, score_cutoff_idx, max_k)
        cutoff_idx = max(cutoff_idx, min(min_k, len(items)))

        selected = items[:cutoff_idx]
        cutoff = selected[-1].score if selected else 0.0

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff,
            method=self.name,
            metadata={
                "alpha": self._alpha,
                "min_score": self._min_score,
                "curvature_idx": curvature_idx,
            },
        )


class EntropySelectionStrategy(SelectionStrategy):
    """Selection based on Shannon entropy of score distribution.

    When entropy is low (scores concentrated), select fewer items.
    When entropy is high (scores spread), select more items.
    Best for ambiguous queries where confidence varies.
    """

    def __init__(
        self,
        low_entropy_k: int = 3,
        high_entropy_k: int = 10,
        entropy_threshold: float = 0.5,
        min_score: float = 0.5,
    ) -> None:
        """Initialize entropy strategy.

        Args:
            low_entropy_k: K when entropy is below threshold
            high_entropy_k: K when entropy is above threshold
            entropy_threshold: Normalized entropy threshold (0-1)
            min_score: Minimum absolute score threshold
        """
        self._low_entropy_k = low_entropy_k
        self._high_entropy_k = high_entropy_k
        self._entropy_threshold = entropy_threshold
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "entropy"

    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        self._validate_inputs(items, max_k, min_k)

        if not items:
            return SelectionResult(
                selected=[],
                cutoff_score=0.0,
                method=self.name,
                metadata={"entropy": 0.0},
            )

        scores = np.array([item.score for item in items])

        # Normalize scores to probabilities
        score_sum = np.sum(scores)
        if score_sum > 0:
            probs = scores / score_sum
            # Calculate Shannon entropy
            entropy = float(stats.entropy(probs))
            # Normalize entropy by max possible entropy
            max_entropy = np.log(len(scores)) if len(scores) > 1 else 1.0
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            normalized_entropy = 0.0

        # Choose k based on entropy
        if normalized_entropy < self._entropy_threshold:
            target_k = self._low_entropy_k
        else:
            target_k = self._high_entropy_k

        # Apply constraints
        target_k = min(target_k, max_k)
        target_k = max(target_k, min_k)

        # Filter by min_score and select
        filtered = [item for item in items if item.score >= self._min_score]
        selected = filtered[:target_k]

        # Ensure min_k
        if len(selected) < min_k and len(items) >= min_k:
            selected = items[:min_k]

        cutoff = selected[-1].score if selected else 0.0

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff,
            method=self.name,
            metadata={
                "entropy": normalized_entropy,
                "threshold": self._entropy_threshold,
                "target_k": target_k,
            },
        )


class ClusterSelectionStrategy(SelectionStrategy):
    """Selection using DBSCAN clustering on scores.

    Groups items by score similarity and selects top items from each cluster.
    Best for multi-topic queries where there are distinct groups of results.
    """

    def __init__(
        self,
        eps: float = 0.1,
        min_samples: int = 1,
        top_per_cluster: int = 3,
        min_score: float = 0.5,
    ) -> None:
        """Initialize clustering strategy.

        Args:
            eps: DBSCAN epsilon parameter (distance threshold for clustering)
            min_samples: Minimum samples per cluster
            top_per_cluster: How many items to take from each cluster
            min_score: Minimum absolute score threshold
        """
        self._eps = eps
        self._min_samples = min_samples
        self._top_per_cluster = top_per_cluster
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "clustering"

    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        self._validate_inputs(items, max_k, min_k)

        if not items:
            return SelectionResult(
                selected=[],
                cutoff_score=0.0,
                method=self.name,
                metadata={"n_clusters": 0},
            )

        # Filter by min_score first
        filtered = [(i, item) for i, item in enumerate(items) if item.score >= self._min_score]

        if not filtered:
            # Fall back to min_k items if nothing passes threshold
            selected = items[: min(min_k, len(items))]
            return SelectionResult(
                selected=selected,
                cutoff_score=selected[-1].score if selected else 0.0,
                method=self.name,
                metadata={"n_clusters": 0, "reason": "below_threshold"},
            )

        if len(filtered) <= self._top_per_cluster:
            # Not enough items for meaningful clustering
            selected = [item for _, item in filtered]
            if len(selected) < min_k:
                selected = items[:min_k]
            return SelectionResult(
                selected=selected[:max_k],
                cutoff_score=selected[-1].score if selected else 0.0,
                method=self.name,
                metadata={"n_clusters": 1, "reason": "insufficient_items"},
            )

        # Cluster by scores
        scores = np.array([[item.score] for _, item in filtered])
        clustering = DBSCAN(eps=self._eps, min_samples=self._min_samples).fit(scores)
        labels = clustering.labels_

        # Group items by cluster
        clusters: dict[int, list[tuple[int, ScoredItem[T]]]] = {}
        for (orig_idx, item), label in zip(filtered, labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append((orig_idx, item))

        # Select top items from each cluster (sorted by original index to maintain score order)
        selected = []
        for label in sorted(clusters.keys()):
            cluster_items = clusters[label]
            # Items are already sorted by score (original order), take top_per_cluster
            for _, item in cluster_items[: self._top_per_cluster]:
                if len(selected) < max_k:
                    selected.append(item)

        # Sort by score descending
        selected.sort(key=lambda x: x.score, reverse=True)

        # Ensure min_k
        if len(selected) < min_k and len(items) >= min_k:
            # Add more items from original list
            existing_items = {id(s.item) for s in selected}
            for item in items:
                if id(item.item) not in existing_items and len(selected) < min_k:
                    selected.append(item)
            selected.sort(key=lambda x: x.score, reverse=True)

        cutoff = selected[-1].score if selected else 0.0

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff,
            method=self.name,
            metadata={
                "n_clusters": len(set(labels)) - (1 if -1 in labels else 0),
                "eps": self._eps,
                "top_per_cluster": self._top_per_cluster,
            },
        )


def create_selection_strategy(
    strategy: str,
    **kwargs: Any,
) -> SelectionStrategy:
    """Factory function to create selection strategies.

    Args:
        strategy: Strategy name (fixed_k, elbow, adaptive_k, entropy, clustering)
        **kwargs: Strategy-specific parameters

    Returns:
        Configured SelectionStrategy instance

    Raises:
        ValueError: If strategy name is not recognized
    """
    strategies: dict[str, type[SelectionStrategy]] = {
        "fixed_k": FixedKSelectionStrategy,
        "elbow": ElbowSelectionStrategy,
        "adaptive_k": AdaptiveKSelectionStrategy,
        "entropy": EntropySelectionStrategy,
        "clustering": ClusterSelectionStrategy,
    }

    if strategy not in strategies:
        valid = ", ".join(strategies.keys())
        raise ValueError(f"Unknown strategy: {strategy}. Valid options: {valid}")

    return strategies[strategy](**kwargs)
