# ADR-002: Rule Matching Strategy

**Status**: Proposed
**Date**: 2025-01-15
**Deciders**: [Team]

## Context

Focal's alignment engine must match user messages to relevant Rules quickly and accurately. With potentially hundreds of Rules per tenant, we need an efficient matching strategy that:

1. Handles natural language conditions (no exact keyword matching)
2. Returns results in < 50ms
3. Respects Rule scopes (GLOBAL, SCENARIO, STEP)
4. Supports priority ordering and business filters

## Decision Drivers

- **Accuracy**: Semantic understanding, not just keyword overlap
- **Latency**: Must not be the bottleneck in the turn brain
- **Scalability**: Handle 100s-1000s of Rules per tenant
- **Explainability**: Why did this Rule match?

## Options Considered

### Option A: Pure Vector Similarity

Embed Rule conditions, embed user message, compute cosine similarity.

```python
def match_rules(message: str, rules: List[Rule]) -> List[MatchedRule]:
    msg_embedding = embed(message)
    scored = []
    for rule in rules:
        score = cosine_similarity(msg_embedding, rule.embedding)
        scored.append((rule, score))
    return sorted(scored, key=lambda x: x[1], reverse=True)[:N]
```

**Pros:**
- Simple implementation
- Handles paraphrasing well ("refund" matches "money back")
- Fast with vector indexes (HNSW)

**Cons:**
- No structured condition evaluation
- Embedding quality depends on model
- May miss exact matches that keyword search would catch

### Option B: Hybrid Vector + BM25

Combine semantic search with keyword matching.

```python
def match_rules(message: str, rules: List[Rule]) -> List[MatchedRule]:
    # Vector search
    msg_embedding = embed(message)
    vector_scores = {r.id: cosine_sim(msg_embedding, r.embedding) for r in rules}

    # BM25 search
    bm25_scores = bm25_search(message, [r.condition_text for r in rules])

    # Combine
    combined = {}
    for rule in rules:
        combined[rule.id] = (
            0.7 * vector_scores[rule.id] +
            0.3 * bm25_scores.get(rule.id, 0)
        )
    return sorted_by_score(combined)[:N]
```

**Pros:**
- Best of both worlds
- Catches exact matches (order numbers, product names)
- More robust than either alone

**Cons:**
- More complex implementation
- Two indexes to maintain
- Tuning the combination weights

### Option C: LLM-based Condition Evaluation

Use an LLM to evaluate whether conditions match.

```python
def match_rules(message: str, rules: List[Rule]) -> List[MatchedRule]:
    # First pass: vector similarity for candidate selection
    candidates = vector_search(message, rules, k=20)

    # Second pass: LLM evaluation
    matched = []
    for rule in candidates:
        prompt = f"Does '{message}' match condition '{rule.condition_text}'? YES/NO"
        if llm(prompt) == "YES":
            matched.append(rule)
    return matched
```

**Pros:**
- Most accurate for complex conditions
- Handles nuance and context
- Can explain matches

**Cons:**
- Slow (LLM call per candidate)
- Expensive (token costs)
- Adds latency to critical path

### Option D: Two-Stage with Cached LLM Patterns

Precompute LLM-derived patterns at Rule creation time, use fast matching at runtime.

```python
# At Rule creation time
def create_rule(rule: Rule):
    # LLM generates matching patterns
    patterns = llm(f"Generate 10 example messages that would match: {rule.condition_text}")
    rule.pattern_embeddings = [embed(p) for p in patterns]
    save(rule)

# At runtime
def match_rules(message: str, rules: List[Rule]) -> List[MatchedRule]:
    msg_embedding = embed(message)
    scored = []
    for rule in rules:
        # Max similarity across all pattern embeddings
        max_sim = max(cosine_sim(msg_embedding, pe) for pe in rule.pattern_embeddings)
        scored.append((rule, max_sim))
    return sorted(scored)[:N]
```

**Pros:**
- High accuracy (LLM-quality patterns)
- Fast at runtime (no LLM calls)
- Explainable (can show which pattern matched)

**Cons:**
- More complex Rule creation
- Pattern quality depends on LLM prompt
- Storage overhead for multiple embeddings per Rule

## Decision

**Recommended: Option B (Hybrid Vector + BM25) with Option D as enhancement**

### Core Strategy

1. **Embedding**: Each Rule stores an embedding of `condition_text + action_text`
2. **Vector Search**: Retrieve top-K candidates by cosine similarity
3. **BM25 Boost**: Re-rank candidates using BM25 score for keyword relevance
4. **Priority + Scope Weighting**: Apply business rules to final ranking

### Implementation

```python
async def match_rules(
    session: SessionState,
    message: str,
    tenant_id: str
) -> List[MatchedRule]:

    # 1. Collect candidates by scope
    candidates = await collect_candidates(session, tenant_id)

    # 2. Embed message
    msg_embedding = await embedder.embed(message)

    # 3. Vector similarity (via pgvector or Neo4j vector index)
    vector_results = await vector_search(
        embedding=msg_embedding,
        rule_ids=[r.id for r in candidates],
        limit=30  # Over-fetch for re-ranking
    )

    # 4. BM25 scores
    bm25_results = await bm25_search(
        query=message,
        rule_ids=[r.id for r in candidates]
    )

    # 5. Combine scores
    scored = []
    for rule in candidates:
        vec_score = vector_results.get(rule.id, 0)
        bm25_score = bm25_results.get(rule.id, 0)

        # Hybrid score
        hybrid = 0.7 * vec_score + 0.3 * normalize(bm25_score)

        # Scope weight
        scope_weight = {Scope.GLOBAL: 1.0, Scope.SCENARIO: 1.1, Scope.STEP: 1.2}

        # Final score
        final = (
            0.6 * hybrid +
            0.3 * normalize(rule.priority) +
            0.1 * scope_weight[rule.scope]
        )

        scored.append(MatchedRule(
            rule=rule,
            similarity_score=vec_score,
            final_score=final
        ))

    # 6. Filter by business rules
    filtered = apply_filters(scored, session)

    # 7. Sort with deterministic tiebreaker and return top-N
    filtered.sort(
        key=lambda m: (-m.final_score, -m.rule.priority, str(m.rule.id))
    )
    return filtered[:MAX_MATCHED_RULES]
```

### Deterministic Tiebreaker

When two rules have identical final scores, use a deterministic tiebreaker to ensure consistent ordering:

```python
def sort_with_tiebreaker(scored_rules: list[ScoredRule]) -> list[ScoredRule]:
    """
    Sort rules by score with deterministic tiebreaker.

    Order:
    1. Final score (descending) - primary sort
    2. Priority (descending) - higher priority wins ties
    3. Rule ID (ascending) - stable ordering for equal priority
    """
    return sorted(
        scored_rules,
        key=lambda r: (-r.final_score, -r.rule.priority, str(r.rule.id)),
    )
```

**Why this matters:**
- Without tiebreaker, equal-scored rules appear in arbitrary order
- This causes non-deterministic behavior across runs
- Priority serves as explicit business preference
- Rule ID ensures stable ordering when all else is equal

### Tuning Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| Vector weight | 0.7 | Higher = more semantic |
| BM25 weight | 0.3 | Higher = more keyword-focused |
| Priority weight | 0.3 | How much priority matters |
| Scope weight | 0.1 | Preference for specific scopes |
| Match threshold | 0.5 | Minimum score to consider |
| Max candidates | 30 | Over-fetch for re-ranking |
| Max matched | 10 | Final output limit |

### Future Enhancement: LLM-Derived Patterns (Option D)

When accuracy matters more than creation-time complexity:

1. At Rule creation, generate example messages via LLM
2. Store multiple embeddings per Rule
3. At runtime, use max similarity across patterns

This is additive—doesn't change the core algorithm.

## Consequences

### Positive
- Fast (< 50ms for typical workloads)
- Accurate (semantic + keyword coverage)
- Explainable (can show similarity scores)
- Scalable (vector indexes handle 1000s of Rules)

### Negative
- Two indexes to maintain (vector + full-text)
- Weight tuning may require experimentation
- BM25 on Rule conditions is less natural than on documents

### Neutral
- Embedding model choice affects accuracy (can swap models)
- Can evolve to Option D if accuracy gaps found

## Validation Plan

1. Create benchmark dataset: 100 Rules, 500 test messages with expected matches
2. Measure precision/recall at different thresholds
3. Compare latency: vector-only vs. hybrid
4. A/B test in production: track rule match → user satisfaction

## References

- [Hybrid Search in Practice](https://www.pinecone.io/learn/hybrid-search/)
- [BM25 Explained](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables)
- [pgvector Performance](https://github.com/pgvector/pgvector)
