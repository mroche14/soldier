<a id="focal.alignment.retrieval.selection"></a>

# focal.alignment.retrieval.selection

Selection strategies for dynamic k-selection after similarity search.

Selection strategies analyze score distributions to dynamically determine
the optimal number of results to keep, rather than using a fixed top-k.

<a id="focal.alignment.retrieval.selection.ScoredItem"></a>

## ScoredItem Objects

```python
@dataclass
class ScoredItem(Generic[T])
```

An item with its similarity score.

**Attributes**:

- `item` - The item being scored
- `score` - Similarity score between 0.0 and 1.0

<a id="focal.alignment.retrieval.selection.SelectionResult"></a>

## SelectionResult Objects

```python
@dataclass
class SelectionResult(Generic[T])
```

Result of selection with metadata.

**Attributes**:

- `selected` - Items that passed selection
- `cutoff_score` - Score threshold used for cutoff
- `method` - Name of the strategy used
- `metadata` - Strategy-specific metadata for logging/debugging

<a id="focal.alignment.retrieval.selection.SelectionStrategy"></a>

## SelectionStrategy Objects

```python
class SelectionStrategy(ABC)
```

Interface for dynamic k-selection after similarity search.

Selection strategies analyze score distributions to dynamically
determine the optimal number of results to keep, rather than
using a fixed top-k.

Contract guarantees:
    - Always returns at least min_k items if available
    - Never returns more than max_k items
    - Items in result.selected are sorted by score descending
    - All items in result.selected have score >= cutoff_score

<a id="focal.alignment.retrieval.selection.SelectionStrategy.name"></a>

#### name

```python
@property
@abstractmethod
def name() -> str
```

Return strategy identifier for logging.

<a id="focal.alignment.retrieval.selection.SelectionStrategy.select"></a>

#### select

```python
@abstractmethod
def select(items: list[ScoredItem[T]],
           max_k: int = 20,
           min_k: int = 1) -> SelectionResult[T]
```

Select items based on score distribution.

**Arguments**:

- `items` - List of scored items, MUST be sorted by score descending
- `max_k` - Maximum items to return (hard cap)
- `min_k` - Minimum items to return (even if scores are low)
  

**Returns**:

  SelectionResult with selected items and metadata
  

**Raises**:

- `ValueError` - If items is not sorted by score descending
- `ValueError` - If min_k > max_k

<a id="focal.alignment.retrieval.selection.FixedKSelectionStrategy"></a>

## FixedKSelectionStrategy Objects

```python
class FixedKSelectionStrategy(SelectionStrategy)
```

Simple top-k selection strategy.

Always returns exactly k items (or fewer if not enough items available).
Used as baseline/fallback when dynamic selection is not needed.

<a id="focal.alignment.retrieval.selection.FixedKSelectionStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(k: int = 10, min_score: float = 0.0) -> None
```

Initialize fixed-k strategy.

**Arguments**:

- `k` - Number of items to select
- `min_score` - Minimum score threshold (items below are excluded)

<a id="focal.alignment.retrieval.selection.ElbowSelectionStrategy"></a>

## ElbowSelectionStrategy Objects

```python
class ElbowSelectionStrategy(SelectionStrategy)
```

Selection using elbow detection in score distribution.

Finds the point where scores drop significantly relative to previous
scores. Best for cases with clear separations between relevant and
irrelevant items.

<a id="focal.alignment.retrieval.selection.ElbowSelectionStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(drop_threshold: float = 0.2, min_score: float = 0.5) -> None
```

Initialize elbow strategy.

**Arguments**:

- `drop_threshold` - Relative drop threshold to detect elbow (0-1)
- `min_score` - Minimum absolute score threshold

<a id="focal.alignment.retrieval.selection.AdaptiveKSelectionStrategy"></a>

## AdaptiveKSelectionStrategy Objects

```python
class AdaptiveKSelectionStrategy(SelectionStrategy)
```

Selection using curvature analysis of score distribution.

Analyzes the second derivative of the score curve to find optimal
cutoff points. Works well for general-purpose retrieval.

<a id="focal.alignment.retrieval.selection.AdaptiveKSelectionStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(alpha: float = 1.5, min_score: float = 0.5) -> None
```

Initialize adaptive-k strategy.

**Arguments**:

- `alpha` - Curvature sensitivity multiplier (higher = more selective)
- `min_score` - Minimum absolute score threshold

<a id="focal.alignment.retrieval.selection.EntropySelectionStrategy"></a>

## EntropySelectionStrategy Objects

```python
class EntropySelectionStrategy(SelectionStrategy)
```

Selection based on Shannon entropy of score distribution.

When entropy is low (scores concentrated), select fewer items.
When entropy is high (scores spread), select more items.
Best for ambiguous queries where confidence varies.

<a id="focal.alignment.retrieval.selection.EntropySelectionStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(low_entropy_k: int = 3,
             high_entropy_k: int = 10,
             entropy_threshold: float = 0.5,
             min_score: float = 0.5) -> None
```

Initialize entropy strategy.

**Arguments**:

- `low_entropy_k` - K when entropy is below threshold
- `high_entropy_k` - K when entropy is above threshold
- `entropy_threshold` - Normalized entropy threshold (0-1)
- `min_score` - Minimum absolute score threshold

<a id="focal.alignment.retrieval.selection.ClusterSelectionStrategy"></a>

## ClusterSelectionStrategy Objects

```python
class ClusterSelectionStrategy(SelectionStrategy)
```

Selection using DBSCAN clustering on scores.

Groups items by score similarity and selects top items from each cluster.
Best for multi-topic queries where there are distinct groups of results.

<a id="focal.alignment.retrieval.selection.ClusterSelectionStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(eps: float = 0.1,
             min_samples: int = 1,
             top_per_cluster: int = 3,
             min_score: float = 0.5) -> None
```

Initialize clustering strategy.

**Arguments**:

- `eps` - DBSCAN epsilon parameter (distance threshold for clustering)
- `min_samples` - Minimum samples per cluster
- `top_per_cluster` - How many items to take from each cluster
- `min_score` - Minimum absolute score threshold

<a id="focal.alignment.retrieval.selection.create_selection_strategy"></a>

#### create\_selection\_strategy

```python
def create_selection_strategy(strategy: str,
                              **kwargs: Any) -> SelectionStrategy
```

Factory function to create selection strategies.

**Arguments**:

- `strategy` - Strategy name (fixed_k, elbow, adaptive_k, entropy, clustering)
- `**kwargs` - Strategy-specific parameters
  

**Returns**:

  Configured SelectionStrategy instance
  

**Raises**:

- `ValueError` - If strategy name is not recognized

