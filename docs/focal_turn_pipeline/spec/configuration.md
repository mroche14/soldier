## 4. Pipeline Configuration

### 4.1 Configuration Source

Currently, pipeline configuration is stored in **TOML files** and loaded at startup:

```
config/default.toml          → Base defaults
config/{environment}.toml    → Environment overrides (development, staging, production)
```

> **Future Direction:** Configuration should be stored in a database/service so that app developers can modify settings in real-time without redeployment. The runtime could poll for changes or receive "config update" events. This is not implemented yet.

### 4.2 Per-Step Configuration

Each pipeline step can be individually configured. Model strings use provider prefixes (e.g., `openrouter/anthropic/claude-3-haiku`) and support OpenRouter provider routing.

```toml
# =============================================================================
# Situational Sensor (Phase 2)
# =============================================================================
[pipeline.situational_sensor]
enabled = true
mode = "llm"
model = "openrouter/anthropic/claude-3-5-haiku-20241022"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["Anthropic", "Google"]    # OpenRouter provider preference
provider_sort = "latency"                   # "latency" | "price" | "throughput"
allow_fallbacks = true                      # Allow other providers if listed fail
ignore_providers = []                       # Never use these providers
history_turns = 5

# =============================================================================
# Retrieval (Phase 4) - Per-object-type reranking + selection
# =============================================================================
[pipeline.retrieval]
enabled = true
embedding_provider = "default"              # References [providers.embedding.default]
max_k = 30

# RULES: High precision needed, reranking recommended
[pipeline.retrieval.rule_selection]
reranking_enabled = true
rerank_provider = "default"
rerank_top_k = 20
strategy = "adaptive_k"
min_score = 0.5
max_k = 10

# SCENARIOS: Often ambiguous, reranking usually not needed
[pipeline.retrieval.scenario_selection]
reranking_enabled = false
strategy = "entropy"
min_score = 0.5
max_k = 5

# MEMORY: Reranking helps find most relevant memories
[pipeline.retrieval.memory_selection]
reranking_enabled = true
rerank_provider = "default"
rerank_top_k = 15
strategy = "clustering"
min_score = 0.4
max_k = 15

# INTENTS: Clear boundaries, reranking improves accuracy
[pipeline.retrieval.intent_selection]
reranking_enabled = true
rerank_provider = "default"
rerank_top_k = 10
strategy = "elbow"
min_score = 0.6
max_k = 5

# =============================================================================
# Rule Filtering (Phase 5)
# =============================================================================
[pipeline.rule_filtering]
enabled = true
model = "openrouter/anthropic/claude-3-5-haiku-20241022"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["Anthropic", "Google"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []
batch_size = 5

# =============================================================================
# Scenario Filtering (Phase 6)
# =============================================================================
[pipeline.scenario_filtering]
enabled = true
model = "openrouter/anthropic/claude-3-5-haiku-20241022"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["Anthropic", "Google"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []

# =============================================================================
# Generation (Phase 9)
# =============================================================================
[pipeline.generation]
enabled = true
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["Anthropic"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []
temperature = 0.7
max_tokens = 1024

# =============================================================================
# Enforcement (Phase 10)
# =============================================================================
[pipeline.enforcement]
enabled = true
self_critique_enabled = false
max_retries = 2
```

**OpenRouter Provider Routing:**

Each LLM step can control which OpenRouter providers handle the request:

| Option | Description |
|--------|-------------|
| `provider_order` | Try providers in this order (e.g., `["Anthropic", "Together"]`) |
| `provider_sort` | Sort remaining by `"latency"`, `"price"`, or `"throughput"` |
| `allow_fallbacks` | If `true`, allow providers not in `provider_order` |
| `ignore_providers` | Never use these providers |

See: https://openrouter.ai/docs#provider-routing

### 4.3 Configuration Modes

Pre-defined configurations for common use cases:

#### Minimal Mode (Fastest, Cheapest)



#### Balanced Mode (Recommended) For example :

Enables all steps with appropriate model tiers. Good balance of quality and cost.

```toml
[pipeline.situational_sensor]
enabled = true
model = "openrouter/anthropic/claude-3-haiku-20240307"

[pipeline.reranking]
enabled = true

[pipeline.rule_filtering]
enabled = true
model = "openrouter/anthropic/claude-3-haiku-20240307"

[pipeline.generation]
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"

[pipeline.enforcement]
enabled = true
self_critique_enabled = false
max_retries = 2
llm_judge_models = ["openrouter/anthropic/claude-3-haiku-20240307"]
```

#### Maximum Quality Mode

### 4.4 Mode Summary

| Mode | Situational Sensor | Reranking | Rule Filter | Generation | Enforcement |
|------|-------------------|-----------|-------------|------------|-------------|
| **Minimal** | Haiku | ❌ Off | ❌ Off | Haiku | Deterministic only |
| **Balanced** | Haiku | ✅ On | Haiku | Sonnet | + LLM Judge (Haiku) |
| **Maximum** | Sonnet | ✅ On | Sonnet | Sonnet | + LLM Judge + Relevance + Grounding |

---

### 4.5 Object Selection Configuration

Each object type has its own **reranking + selection strategy** configuration under `[pipeline.retrieval.*_selection]`.

See Section 3.5 for the unified selection pipeline concept.

```toml
# =============================================================================
# Per-Object-Type Reranking + Selection
# =============================================================================

# RULES: High precision needed, reranking recommended
[pipeline.retrieval.rule_selection]
reranking_enabled = true
rerank_provider = "default"    # References [providers.rerank.default]
rerank_top_k = 20
strategy = "adaptive_k"        # "fixed_k" | "elbow" | "adaptive_k" | "entropy" | "clustering"
min_score = 0.5
max_k = 10

# SCENARIOS: Often ambiguous, reranking usually not needed
[pipeline.retrieval.scenario_selection]
reranking_enabled = false
strategy = "entropy"
min_score = 0.5
max_k = 5

# MEMORY: Reranking helps find most relevant memories
[pipeline.retrieval.memory_selection]
reranking_enabled = true
rerank_provider = "default"
rerank_top_k = 15
strategy = "clustering"
min_score = 0.4
max_k = 15

# INTENTS: Clear boundaries, reranking improves accuracy
[pipeline.retrieval.intent_selection]
reranking_enabled = true
rerank_provider = "default"
rerank_top_k = 10
strategy = "elbow"
min_score = 0.6
max_k = 5
```

**Recommendations by object type:**

| Object | Reranking | Strategy | Rationale |
|--------|-----------|----------|-----------|
| **Rules** | ✅ Yes | `adaptive_k` | High precision matters; curvature analysis handles varying distributions |
| **Scenarios** | ❌ No | `entropy` | Usually few scenarios; LLM filtering handles ambiguity |
| **Memory** | ✅ Yes | `clustering` | Groups related memories; reranking improves relevance |
| **Intents** | ✅ Yes | `elbow` | Clear relevant/irrelevant boundary; reranking sharpens it |

**Configuration by mode:**

| Mode | Rules | Scenarios | Memory | Intents |
|------|-------|-----------|--------|---------|
| **Minimal** | No rerank, `fixed_k(5)` | No rerank, `fixed_k(3)` | No rerank, `fixed_k(5)` | No rerank, `fixed_k(3)` |
| **Balanced** | Rerank, `adaptive_k` | No rerank, `entropy` | Rerank, `clustering` | Rerank, `elbow` |
| **Maximum** | Rerank, `adaptive_k` | Rerank, `entropy` | Rerank, `clustering` | Rerank, `elbow` |

---
