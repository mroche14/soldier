"""Selection Strategy Contract - Interface specification for Phases 6."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

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
    metadata: dict[str, Any]


class SelectionStrategy(ABC):
    """Interface for dynamic k-selection after similarity search.

    Selection strategies analyze score distributions to dynamically
    determine the optimal number of results to keep, rather than
    using a fixed top-k.

    Used by:
        - Rule retrieval (ConfigStore)
        - Scenario matching (ConfigStore)
        - Memory retrieval (MemoryStore)
        - Any semantic search operation

    Example:
        ```python
        strategy = AdaptiveKSelectionStrategy(alpha=1.5)
        result = strategy.select(scored_items, max_k=20, min_k=1)
        selected_rules = [item.item for item in result.selected]
        ```

    Contract guarantees:
        - Always returns at least min_k items if available
        - Never returns more than max_k items
        - Items in result.selected are sorted by score descending
        - All items in result.selected have score >= cutoff_score
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy identifier for logging.

        Returns:
            Unique strategy name (e.g., "elbow", "adaptive_k", "entropy")
        """
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
