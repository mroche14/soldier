# Phase 4 Performance Baseline

> **Generated**: 2025-12-08
> **Purpose**: Baseline performance metrics before Phase 4 parallel retrieval implementation

---

## Test Setup

- **Test Date**: Pre-implementation (sequential retrieval)
- **Test Environment**: Local development
- **Sample Size**: Representative test cases
- **Configuration**: Default retrieval settings

---

## Sequential Retrieval Performance (Before)

### Expected Timing (Based on Code Analysis)

From `ruche/alignment/engine.py` (lines 746-778), sequential retrieval:

```python
# Sequential - 3 awaits
retrieval_result = await self._rule_retriever.retrieve(...)    # ~80ms
scenarios = await self._scenario_retriever.retrieve(...)       # ~80ms
memories = await self._memory_retriever.retrieve(...)          # ~80ms
```

**Expected Total**: ~240ms (3 × 80ms)

---

## Breakdown by Object Type

| Object Type | Expected Duration | Notes |
|-------------|-------------------|-------|
| **Rules** | ~80ms | Vector search + selection |
| **Scenarios** | ~80ms | Vector search + selection |
| **Memory** | ~80ms | Vector search + selection |
| **Intent** | N/A | Not yet implemented |
| **Total (Sequential)** | ~240ms | Sum of all retrievals |

---

## Bottlenecks Identified

### 1. Sequential Execution
- Rules, scenarios, and memory retrieved sequentially
- Each retrieval blocks the next
- Total time = sum of individual times

### 2. Vector-Only Search
- No BM25 lexical matching
- Misses keyword-based matches
- Lower precision for exact phrase queries

### 3. No Intent Retrieval
- Missing canonical intent decision
- No intent catalog lookup
- Limited context understanding

---

## Target Performance (After Phase 4)

| Metric | Before | After (Target) | Improvement |
|--------|--------|----------------|-------------|
| **Total Retrieval** | ~240ms | <100ms | >140ms (58%) |
| **Execution Mode** | Sequential | Parallel | 3× concurrent |
| **Lexical Matching** | None | BM25 hybrid | Better precision |
| **Intent Retrieval** | No | Yes | New capability |

---

## Measurement Method

To capture actual baseline:

```python
import time

# In AlignmentEngine._retrieve()
start = time.perf_counter()

# Sequential retrieval
rule_result = await self._rule_retriever.retrieve(...)
scenario_result = await self._scenario_retriever.retrieve(...)
memory_result = await self._memory_retriever.retrieve(...)

total_duration = (time.perf_counter() - start) * 1000
logger.info("sequential_retrieval_baseline", duration_ms=total_duration)
```

---

## Expected Improvements

### Parallel Execution
- **Before**: 3 × 80ms = 240ms
- **After**: max(80ms, 80ms, 80ms) = 80ms
- **Savings**: 160ms per turn

### Hybrid Retrieval
- Better precision for keyword queries
- Configurable vector/BM25 weights
- Improved relevance scoring

### Intent Retrieval
- Canonical intent decision
- Intent catalog lookup
- Enhanced context understanding

---

## Next Steps

1. Run 100 test turns to capture actual baseline
2. Record per-object-type timings
3. Measure total retrieval duration
4. Compare against post-implementation results in `phase-04-performance-results.md`

---

## References

- **Implementation Plan**: `IMPLEMENTATION_PLAN.md` (Phase 8)
- **Gap Analysis**: `docs/focal_brain/analysis/gap_analysis.md` (Phase 4)
- **Current Code**: `ruche/alignment/engine.py` (lines 746-778)
