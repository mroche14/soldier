# Selection Strategies

After semantic similarity search (for rules, scenarios, or memory), we need to decide **how many** results to keep. This is the "k selection" problem.

Fixed `top_k` is naive—it ignores the actual score distribution. Selection strategies analyze the scores to dynamically determine the optimal cutoff.

## The Problem

```
Query: "I want to return my order"

Retrieved rules (sorted by similarity):
  1. "Customer wants refund"     → 0.92  ← Clear match
  2. "Customer asks about return"→ 0.89  ← Clear match
  3. "Order status inquiry"      → 0.71  ← Maybe relevant?
  4. "Shipping question"         → 0.45  ← Noise
  5. "General greeting"          → 0.42  ← Noise
  ...

With fixed top_k=5: We include noise (items 4, 5)
With fixed top_k=2: We might miss item 3 when it's relevant
```

**Solution**: Analyze the score distribution to find the natural cutoff.

---

## SelectionStrategy Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, TypeVar, Generic

T = TypeVar('T')  # The type of items being selected (Rule, Episode, etc.)


@dataclass
class ScoredItem(Generic[T]):
    """An item with its similarity score."""
    item: T
    score: float


@dataclass
class SelectionResult(Generic[T]):
    """Result of selection with metadata."""
    selected: List[ScoredItem[T]]
    cutoff_score: float
    method: str
    metadata: dict  # Strategy-specific info (entropy, cluster count, etc.)


class SelectionStrategy(ABC):
    """
    Interface for dynamic k-selection after similarity search.

    Used by:
    - Rule retrieval (ConfigStore)
    - Scenario matching (ConfigStore)
    - Memory retrieval (MemoryStore)
    - Any semantic search operation
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        pass

    @abstractmethod
    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        """
        Select items based on score distribution.

        Args:
            items: List of scored items, sorted by score descending
            max_k: Maximum items to return
            min_k: Minimum items to return (even if scores are low)

        Returns:
            SelectionResult with selected items and metadata
        """
        pass
```

---

## Strategy Implementations

### 1. Elbow Method (Relative Score Drop)

The simplest approach: cut when the score drops significantly from the previous item.

**Logic**: If the gap between consecutive scores exceeds a threshold, we've hit the "noise tail."

```python
class ElbowSelectionStrategy(SelectionStrategy):
    """
    Cut at the first significant score drop (the "elbow").

    Best for: Clear separation between relevant and irrelevant results.

    Config:
        drop_threshold: Minimum relative drop to trigger cutoff (default 0.15)
        min_score: Absolute minimum score to include (default 0.5)
    """

    def __init__(
        self,
        drop_threshold: float = 0.15,
        min_score: float = 0.5,
    ):
        self.drop_threshold = drop_threshold
        self.min_score = min_score

    @property
    def name(self) -> str:
        return "elbow"

    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        if not items:
            return SelectionResult([], 0.0, self.name, {})

        selected = []
        cutoff_score = 0.0

        for i, item in enumerate(items[:max_k]):
            # Always include up to min_k
            if i < min_k:
                selected.append(item)
                continue

            # Check absolute minimum score
            if item.score < self.min_score:
                break

            # Check for significant drop from previous
            if i > 0:
                prev_score = items[i - 1].score
                drop = (prev_score - item.score) / prev_score

                if drop > self.drop_threshold:
                    cutoff_score = prev_score
                    break

            selected.append(item)
            cutoff_score = item.score

        return SelectionResult(
            selected=selected,
            cutoff_score=cutoff_score,
            method=self.name,
            metadata={
                "drop_threshold": self.drop_threshold,
                "min_score": self.min_score,
            }
        )
```

**When to use**:
- Simple queries with clear relevance separation
- Fast, low-overhead selection
- Default fallback strategy

---

### 2. Adaptive-K Method (Curvature Analysis)

Analyzes the "curvature" of the score curve to find where the marginal gain becomes insignificant.

**Logic**: Instead of looking at raw drops, we analyze the rate of change (first derivative) and acceleration (second derivative) to detect when we hit the "noise floor."

```python
import numpy as np

class AdaptiveKSelectionStrategy(SelectionStrategy):
    """
    Adaptive-k selection using score curve analysis.

    Analyzes the curvature of the score distribution to find the
    natural cutoff point where adding more results has diminishing returns.

    Best for: Complex queries, varied score distributions.

    Config:
        alpha: Sensitivity (higher = stricter, fewer results). Default 1.5
        min_score: Absolute minimum score. Default 0.4
    """

    def __init__(
        self,
        alpha: float = 1.5,
        min_score: float = 0.4,
    ):
        self.alpha = alpha
        self.min_score = min_score

    @property
    def name(self) -> str:
        return "adaptive_k"

    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        if not items:
            return SelectionResult([], 0.0, self.name, {})

        scores = [item.score for item in items[:max_k]]

        # Filter by minimum score first
        valid_count = sum(1 for s in scores if s >= self.min_score)
        scores = scores[:valid_count] if valid_count > 0 else scores[:min_k]

        if len(scores) <= min_k:
            selected = items[:len(scores)]
            return SelectionResult(
                selected=list(selected),
                cutoff_score=scores[-1] if scores else 0.0,
                method=self.name,
                metadata={"reason": "below_min_k"}
            )

        # Calculate first derivative (rate of score drop)
        diffs = np.abs(np.diff(scores))

        if len(diffs) == 0:
            return SelectionResult(
                selected=list(items[:min_k]),
                cutoff_score=scores[min_k - 1],
                method=self.name,
                metadata={"reason": "no_variance"}
            )

        # Calculate mean drop to establish baseline
        mean_drop = np.mean(diffs)

        # Find cutoff point
        cutoff_idx = len(scores)
        for i, drop in enumerate(diffs):
            # Cut when drop exceeds alpha * mean (outlier drop)
            if drop > (mean_drop * self.alpha):
                cutoff_idx = i + 1
                break

        # Ensure we respect min_k
        cutoff_idx = max(cutoff_idx, min_k)

        selected = items[:cutoff_idx]

        return SelectionResult(
            selected=list(selected),
            cutoff_score=scores[cutoff_idx - 1],
            method=self.name,
            metadata={
                "alpha": self.alpha,
                "mean_drop": float(mean_drop),
                "cutoff_idx": cutoff_idx,
            }
        )
```

**When to use**:
- General-purpose, robust selection
- When score distributions vary widely
- Production default for most use cases

---

### 3. Entropy-Based Selection (Information Method)

Measures uncertainty (Shannon Entropy) to decide how many results the LLM needs.

**Logic**:
- **Low entropy** (scores like [0.95, 0.20, 0.15]): Model is confident. Take few results.
- **High entropy** (scores like [0.75, 0.74, 0.73]): Model is confused. Take more results to give LLM context.

```python
from scipy.stats import entropy as shannon_entropy

class EntropySelectionStrategy(SelectionStrategy):
    """
    Entropy-based selection using score distribution uncertainty.

    When scores are tightly clustered (high entropy), we're uncertain
    which results are best → take more items.
    When scores are spread out (low entropy), we're confident
    about the top results → take fewer items.

    Best for: Queries where relevance is ambiguous.

    Config:
        low_entropy_k: Items to take when confident (entropy < 1.0)
        medium_entropy_k: Items to take when uncertain (entropy 1.0-2.0)
        high_entropy_k: Items to take when very uncertain (entropy > 2.0)
        min_score: Absolute minimum score. Default 0.3
    """

    def __init__(
        self,
        low_entropy_k: int = 3,
        medium_entropy_k: int = 5,
        high_entropy_k: int = 10,
        min_score: float = 0.3,
    ):
        self.low_entropy_k = low_entropy_k
        self.medium_entropy_k = medium_entropy_k
        self.high_entropy_k = high_entropy_k
        self.min_score = min_score

    @property
    def name(self) -> str:
        return "entropy"

    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        if not items:
            return SelectionResult([], 0.0, self.name, {})

        # Filter by minimum score
        valid_items = [item for item in items if item.score >= self.min_score]
        if len(valid_items) < min_k:
            valid_items = items[:min_k]

        scores = [item.score for item in valid_items[:max_k]]

        if not scores:
            return SelectionResult([], 0.0, self.name, {"entropy": 0.0})

        # Normalize scores to probabilities
        total = sum(scores)
        if total == 0:
            probs = [1.0 / len(scores)] * len(scores)
        else:
            probs = [s / total for s in scores]

        # Calculate Shannon entropy
        score_entropy = float(shannon_entropy(probs))

        # Dynamic k based on entropy
        if score_entropy < 1.0:
            target_k = self.low_entropy_k      # Clear winner
        elif score_entropy < 2.0:
            target_k = self.medium_entropy_k   # Some uncertainty
        else:
            target_k = self.high_entropy_k     # Ambiguous query

        # Clamp to valid range
        target_k = max(min_k, min(target_k, len(valid_items), max_k))

        selected = valid_items[:target_k]

        return SelectionResult(
            selected=list(selected),
            cutoff_score=selected[-1].score if selected else 0.0,
            method=self.name,
            metadata={
                "entropy": score_entropy,
                "target_k": target_k,
                "confidence": "high" if score_entropy < 1.0 else "medium" if score_entropy < 2.0 else "low",
            }
        )
```

**When to use**:
- Ambiguous queries
- When you want the selection to adapt to query difficulty
- When downstream LLM can handle variable context sizes

---

### 4. Clustering-Based Selection (Topic Method)

Handles "multiple valid answer groups" by clustering results and taking representatives from each cluster.

**Logic**: Sometimes a query matches distinct groups (e.g., "deploy" matches both AWS and K8s tools). This strategy identifies clusters and includes results from each relevant cluster.

```python
from sklearn.cluster import DBSCAN
import numpy as np

class ClusterSelectionStrategy(SelectionStrategy):
    """
    Clustering-based selection for multi-topic queries.

    Groups similar results into clusters and selects the top items
    from each relevant cluster. Handles queries that match multiple
    distinct topics.

    Best for: Broad queries, multi-topic matching.

    Config:
        eps: DBSCAN neighborhood size (score distance). Default 0.1
        min_cluster_size: Minimum items to form a cluster. Default 2
        top_per_cluster: Items to take from each cluster. Default 3
        min_score: Absolute minimum score. Default 0.4
    """

    def __init__(
        self,
        eps: float = 0.1,
        min_cluster_size: int = 2,
        top_per_cluster: int = 3,
        min_score: float = 0.4,
    ):
        self.eps = eps
        self.min_cluster_size = min_cluster_size
        self.top_per_cluster = top_per_cluster
        self.min_score = min_score

    @property
    def name(self) -> str:
        return "clustering"

    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        if not items:
            return SelectionResult([], 0.0, self.name, {})

        # Filter by minimum score
        valid_items = [item for item in items if item.score >= self.min_score]
        if len(valid_items) < min_k:
            valid_items = items[:min_k]

        if len(valid_items) <= self.min_cluster_size:
            return SelectionResult(
                selected=list(valid_items),
                cutoff_score=valid_items[-1].score if valid_items else 0.0,
                method=self.name,
                metadata={"clusters": 1, "reason": "too_few_items"}
            )

        # Cluster by score (1D clustering)
        scores = np.array([[item.score] for item in valid_items])

        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_cluster_size
        ).fit(scores)

        labels = clustering.labels_

        # Group items by cluster
        clusters: dict[int, list[ScoredItem]] = {}
        noise_items: list[ScoredItem] = []

        for item, label in zip(valid_items, labels):
            if label == -1:  # Noise
                noise_items.append(item)
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(item)

        # Select top items from each cluster
        selected = []

        # Sort clusters by their top score (best cluster first)
        sorted_clusters = sorted(
            clusters.items(),
            key=lambda x: x[1][0].score if x[1] else 0,
            reverse=True
        )

        for cluster_id, cluster_items in sorted_clusters:
            # Items are already sorted by score
            for item in cluster_items[:self.top_per_cluster]:
                if len(selected) < max_k:
                    selected.append(item)

        # Include high-scoring noise items
        for item in noise_items:
            if len(selected) < max_k and item.score > self.min_score:
                selected.append(item)

        # Ensure min_k
        while len(selected) < min_k and len(valid_items) > len(selected):
            for item in valid_items:
                if item not in selected:
                    selected.append(item)
                    break

        # Sort final selection by score
        selected.sort(key=lambda x: x.score, reverse=True)

        return SelectionResult(
            selected=selected,
            cutoff_score=selected[-1].score if selected else 0.0,
            method=self.name,
            metadata={
                "num_clusters": len(clusters),
                "cluster_sizes": {k: len(v) for k, v in clusters.items()},
                "noise_count": len(noise_items),
            }
        )
```

**When to use**:
- Broad or ambiguous queries
- When results naturally group into topics
- Multi-intent detection

---

### 5. Fixed-K Selection (Baseline)

Simple fixed top-k for comparison and fallback.

```python
class FixedKSelectionStrategy(SelectionStrategy):
    """
    Fixed top-k selection (baseline).

    Always returns exactly k items (or fewer if not available).
    Use as fallback or for comparison benchmarks.

    Config:
        k: Number of items to select. Default 5
        min_score: Optional minimum score filter. Default None
    """

    def __init__(
        self,
        k: int = 5,
        min_score: float | None = None,
    ):
        self.k = k
        self._min_score = min_score

    @property
    def name(self) -> str:
        return "fixed_k"

    def select(
        self,
        items: List[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        if not items:
            return SelectionResult([], 0.0, self.name, {})

        # Apply min_score filter if set
        if self._min_score is not None:
            items = [item for item in items if item.score >= self._min_score]

        target_k = min(self.k, max_k, len(items))
        target_k = max(target_k, min_k)

        selected = items[:target_k]

        return SelectionResult(
            selected=list(selected),
            cutoff_score=selected[-1].score if selected else 0.0,
            method=self.name,
            metadata={"fixed_k": self.k}
        )
```

---

## Strategy Comparison

| Strategy | Speed | Best For | Handles Multi-Topic | Adaptive |
|----------|-------|----------|---------------------|----------|
| **Elbow** | Fast | Clear separations | No | Yes |
| **Adaptive-K** | Fast | General use | No | Yes |
| **Entropy** | Medium | Ambiguous queries | No | Yes |
| **Clustering** | Slower | Multi-topic queries | Yes | Yes |
| **Fixed-K** | Fastest | Baseline/fallback | No | No |

---

## Configuration

Selection strategies are configured via TOML files with Pydantic validation. See [configuration.md](./configuration.md) for full configuration system details.

### TOML Configuration

Each retrieval type (rules, scenarios, memory) can use a different selection strategy:

```toml
# config/default.toml

[pipeline.retrieval]
embedding_provider = "default"
max_k = 30                       # Retrieve up to 30 candidates
min_k = 1

# Selection strategy for rules
[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"
alpha = 1.5
min_score = 0.5

# Selection strategy for scenarios
[pipeline.retrieval.scenario_selection]
strategy = "entropy"
low_entropy_k = 1                # Usually one scenario is active
medium_entropy_k = 2
high_entropy_k = 3
min_score = 0.6

# Selection strategy for memory
[pipeline.retrieval.memory_selection]
strategy = "clustering"
eps = 0.1
min_cluster_size = 2
top_per_cluster = 3
min_score = 0.4
```

### Pydantic Models

Selection strategies are defined as Pydantic models in `ruche/config/models/selection.py`:

```python
# ruche/config/models/selection.py
from typing import Literal
from pydantic import BaseModel, Field


class AdaptiveKSelectionConfig(BaseModel):
    """Configuration for adaptive-k selection strategy."""

    strategy: Literal["adaptive_k"] = "adaptive_k"
    alpha: float = Field(
        default=1.5,
        ge=0.5,
        le=5.0,
        description="Sensitivity (higher = stricter, fewer results)"
    )
    min_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Absolute minimum score"
    )


class EntropySelectionConfig(BaseModel):
    """Configuration for entropy-based selection strategy."""

    strategy: Literal["entropy"] = "entropy"
    low_entropy_k: int = Field(default=3, ge=1)
    medium_entropy_k: int = Field(default=5, ge=1)
    high_entropy_k: int = Field(default=10, ge=1)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)


# Union type for any selection strategy config
SelectionStrategyConfig = (
    ElbowSelectionConfig
    | AdaptiveKSelectionConfig
    | EntropySelectionConfig
    | ClusterSelectionConfig
    | FixedKSelectionConfig
)
```

### Strategy Factory

Create selection strategies from Pydantic config:

```python
# ruche/brains/focal/retrieval/selection.py
from ruche.config.models.selection import SelectionStrategyConfig


def create_selection_strategy(config: SelectionStrategyConfig) -> SelectionStrategy:
    """Factory function to create selection strategy from Pydantic config."""

    match config.strategy:
        case "elbow":
            return ElbowSelectionStrategy(
                drop_threshold=config.drop_threshold,
                min_score=config.min_score,
            )
        case "adaptive_k":
            return AdaptiveKSelectionStrategy(
                alpha=config.alpha,
                min_score=config.min_score,
            )
        case "entropy":
            return EntropySelectionStrategy(
                low_entropy_k=config.low_entropy_k,
                medium_entropy_k=config.medium_entropy_k,
                high_entropy_k=config.high_entropy_k,
                min_score=config.min_score,
            )
        case "clustering":
            return ClusterSelectionStrategy(
                eps=config.eps,
                min_cluster_size=config.min_cluster_size,
                top_per_cluster=config.top_per_cluster,
                min_score=config.min_score,
            )
        case "fixed_k":
            return FixedKSelectionStrategy(
                k=config.k,
                min_score=config.min_score,
            )
        case _:
            raise ValueError(f"Unknown strategy: {config.strategy}")
```

### Environment Variable Overrides

Override strategy configuration via environment variables:

```bash
# Change rule selection to entropy strategy
export RUCHE_PIPELINE__RETRIEVAL__RULE_SELECTION__STRATEGY=entropy
export RUCHE_PIPELINE__RETRIEVAL__RULE_SELECTION__LOW_ENTROPY_K=5
export RUCHE_PIPELINE__RETRIEVAL__RULE_SELECTION__MIN_SCORE=0.6

# Adjust adaptive-k sensitivity
export RUCHE_PIPELINE__RETRIEVAL__RULE_SELECTION__ALPHA=2.0
```

---

## Usage in Pipeline

### Rule Retrieval

```python
from ruche.config.settings import get_settings
from ruche.brains.focal.retrieval.selection import create_selection_strategy


async def retrieve_rules(
    query_embedding: list[float],
    session: Session,
    config_store: ConfigStore,
) -> list[Rule]:
    """Retrieve rules with dynamic selection."""

    # Get settings from centralized config
    settings = get_settings()
    retrieval_config = settings.pipeline.retrieval

    # Get raw candidates from vector search
    raw_candidates = await config_store.vector_search_rules(
        query_embedding=query_embedding,
        tenant_id=session.tenant_id,
        agent_id=session.agent_id,
        limit=retrieval_config.max_k,  # Retrieve more than we need
    )

    # Create selection strategy from Pydantic config
    strategy = create_selection_strategy(retrieval_config.rule_selection)

    scored_items = [
        ScoredItem(item=rule, score=rule.similarity_score)
        for rule in raw_candidates
    ]

    result = strategy.select(
        items=scored_items,
        max_k=retrieval_config.max_k,
        min_k=retrieval_config.min_k,
    )

    # Log selection metadata for observability
    logger.info(
        "Rule selection",
        strategy=result.method,
        input_count=len(raw_candidates),
        output_count=len(result.selected),
        cutoff_score=result.cutoff_score,
        metadata=result.metadata,
    )

    return [item.item for item in result.selected]
```

### Memory Retrieval

```python
from ruche.config.settings import get_settings
from ruche.brains.focal.retrieval.selection import create_selection_strategy


async def retrieve_memory(
    query_embedding: list[float],
    group_id: str,
    memory_store: MemoryStore,
) -> list[Episode]:
    """Retrieve memory episodes with dynamic selection."""

    # Get settings from centralized config
    settings = get_settings()
    retrieval_config = settings.pipeline.retrieval

    # Get raw candidates
    raw_episodes = await memory_store.vector_search_episodes(
        query_embedding=query_embedding,
        group_id=group_id,
        limit=retrieval_config.max_k,
    )

    # Create selection strategy from Pydantic config
    strategy = create_selection_strategy(retrieval_config.memory_selection)

    scored_items = [
        ScoredItem(item=episode, score=episode.similarity_score)
        for episode in raw_episodes
    ]

    result = strategy.select(
        items=scored_items,
        max_k=retrieval_config.max_k,
        min_k=1,
    )

    return [item.item for item in result.selected]
```

---

## Observability

Selection results should be logged for debugging and tuning. See [observability.md](./observability.md) for the overall logging architecture.

Example structured log output:

```json
{
  "logical_turn_id": "abc123",
  "retrieval": {
    "rules": {
      "strategy": "adaptive_k",
      "input_count": 25,
      "output_count": 4,
      "cutoff_score": 0.78,
      "metadata": {
        "alpha": 1.5,
        "mean_drop": 0.08,
        "cutoff_idx": 4
      }
    },
    "scenarios": {
      "strategy": "entropy",
      "input_count": 5,
      "output_count": 1,
      "cutoff_score": 0.91,
      "metadata": {
        "entropy": 0.45,
        "confidence": "high"
      }
    },
    "memory": {
      "strategy": "clustering",
      "input_count": 20,
      "output_count": 7,
      "cutoff_score": 0.52,
      "metadata": {
        "num_clusters": 2,
        "cluster_sizes": {"0": 4, "1": 3}
      }
    }
  }
}
```

---

## Recommendations

| Use Case | Recommended Strategy | Why |
|----------|---------------------|-----|
| **Rule matching** | `adaptive_k` | Robust, handles varied distributions |
| **Scenario detection** | `entropy` | Low entropy = confident single match |
| **Memory retrieval** | `clustering` | Conversations have multiple topics |
| **Tool selection** | `elbow` | Usually clear relevance separation |
| **Fallback** | `fixed_k` | Predictable, debuggable |

### Tuning Tips

1. **Start with `adaptive_k`** as the default, then tune if needed
2. **Monitor cutoff scores** in production to detect drift
3. **Use `entropy` when** query ambiguity varies significantly
4. **Use `clustering` when** you expect multi-topic results
5. **Lower `min_score`** if you're missing relevant results
6. **Raise `alpha`** in adaptive_k if you're getting too much noise
