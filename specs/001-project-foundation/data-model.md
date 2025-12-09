# Data Model: Configuration System

**Date**: 2025-11-28
**Feature**: 001-project-foundation

## Overview

This document defines the Pydantic models for the Focal configuration system. These models validate configuration loaded from TOML files and environment variables.

---

## Root Configuration

### Settings

The root configuration object containing all nested configuration sections.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `app_name` | `str` | `"focal"` | Application name for logging/tracing |
| `debug` | `bool` | `False` | Enable debug mode |
| `log_level` | `str` | `"INFO"` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `api` | `APIConfig` | `APIConfig()` | API server configuration |
| `storage` | `StorageConfig` | `StorageConfig()` | Storage backend configuration |
| `providers` | `ProvidersConfig` | `ProvidersConfig()` | AI provider configuration |
| `pipeline` | `PipelineConfig` | `PipelineConfig()` | Turn pipeline configuration |
| `selection` | `SelectionStrategiesConfig` | `SelectionStrategiesConfig()` | Selection strategy configuration |
| `observability` | `ObservabilityConfig` | `ObservabilityConfig()` | Observability configuration |

**Validation Rules**:
- `log_level` must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL

---

## API Configuration

### APIConfig

Configuration for the HTTP API server.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | `str` | `"0.0.0.0"` | Bind address |
| `port` | `int` | `8000` | Port number |
| `workers` | `int` | `4` | Number of worker processes |
| `cors_origins` | `list[str]` | `["*"]` | Allowed CORS origins |
| `cors_allow_credentials` | `bool` | `True` | Allow credentials in CORS |
| `rate_limit` | `RateLimitConfig` | `RateLimitConfig()` | Rate limiting settings |

**Validation Rules**:
- `port` must be between 1 and 65535
- `workers` must be >= 1

### RateLimitConfig

Rate limiting configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable rate limiting |
| `requests_per_minute` | `int` | `60` | Max requests per minute per tenant |
| `burst_size` | `int` | `10` | Burst allowance |

**Validation Rules**:
- `requests_per_minute` must be > 0
- `burst_size` must be >= 0

---

## Storage Configuration

### StorageConfig

Configuration for all storage backends.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config` | `StoreBackendConfig` | backend="postgres" | ConfigStore backend |
| `memory` | `StoreBackendConfig` | backend="postgres" | MemoryStore backend |
| `session` | `StoreBackendConfig` | backend="redis" | SessionStore backend |
| `audit` | `StoreBackendConfig` | backend="postgres" | AuditStore backend |

### StoreBackendConfig

Configuration for a single store backend.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | `str` | `"inmemory"` | Backend type |
| `connection_url` | `str \| None` | `None` | Connection URL (from env var) |
| `pool_size` | `int` | `10` | Connection pool size |
| `pool_timeout` | `int` | `30` | Pool timeout in seconds |

**Validation Rules**:
- `backend` must be one of: inmemory, postgres, redis, mongodb, neo4j, dynamodb
- `pool_size` must be > 0
- `pool_timeout` must be > 0

---

## Provider Configuration

### ProvidersConfig

Configuration for AI providers.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_llm` | `str` | `"haiku"` | Default LLM provider name |
| `default_embedding` | `str` | `"default"` | Default embedding provider name |
| `default_rerank` | `str` | `"default"` | Default rerank provider name |
| `llm` | `dict[str, LLMProviderConfig]` | `{}` | Named LLM providers |
| `embedding` | `dict[str, EmbeddingProviderConfig]` | `{}` | Named embedding providers |
| `rerank` | `dict[str, RerankProviderConfig]` | `{}` | Named rerank providers |

### LLMProviderConfig

Configuration for an LLM provider.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"anthropic"` | Provider type |
| `model` | `str` | `"claude-3-haiku-20240307"` | Model identifier |
| `api_key` | `SecretStr \| None` | `None` | API key (prefer env var) |
| `base_url` | `str \| None` | `None` | Custom API base URL |
| `max_tokens` | `int` | `4096` | Default max tokens |
| `temperature` | `float` | `0.7` | Default temperature |
| `timeout` | `int` | `60` | Request timeout in seconds |

**Validation Rules**:
- `provider` must be one of: anthropic, openai, bedrock, vertex, ollama, mock
- `temperature` must be between 0.0 and 2.0
- `max_tokens` must be > 0

### EmbeddingProviderConfig

Configuration for an embedding provider.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"openai"` | Provider type |
| `model` | `str` | `"text-embedding-3-small"` | Model identifier |
| `api_key` | `SecretStr \| None` | `None` | API key (prefer env var) |
| `dimensions` | `int` | `1536` | Embedding dimensions |
| `batch_size` | `int` | `100` | Batch size for embedding |

**Validation Rules**:
- `provider` must be one of: openai, cohere, voyage, sentence_transformers, mock
- `dimensions` must be > 0
- `batch_size` must be > 0

### RerankProviderConfig

Configuration for a rerank provider.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"cohere"` | Provider type |
| `model` | `str` | `"rerank-english-v3.0"` | Model identifier |
| `api_key` | `SecretStr \| None` | `None` | API key (prefer env var) |
| `top_k` | `int` | `10` | Number of results to return |

**Validation Rules**:
- `provider` must be one of: cohere, voyage, cross_encoder, mock
- `top_k` must be > 0

---

## Pipeline Configuration

### PipelineConfig

Configuration for the turn pipeline.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context_extraction` | `ContextExtractionConfig` | `ContextExtractionConfig()` | Context extraction step |
| `retrieval` | `RetrievalConfig` | `RetrievalConfig()` | Retrieval step |
| `reranking` | `RerankingConfig` | `RerankingConfig()` | Reranking step |
| `llm_filtering` | `LLMFilteringConfig` | `LLMFilteringConfig()` | LLM filtering step |
| `generation` | `GenerationConfig` | `GenerationConfig()` | Response generation step |
| `enforcement` | `EnforcementConfig` | `EnforcementConfig()` | Enforcement step |

### ContextExtractionConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `mode` | `str` | `"llm"` | Extraction mode |
| `llm_provider` | `str` | `"haiku"` | LLM provider for extraction |
| `history_turns` | `int` | `5` | Number of history turns to include |

**Validation Rules**:
- `mode` must be one of: llm, embedding, hybrid
- `history_turns` must be >= 0

### RetrievalConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `embedding_provider` | `str` | `"default"` | Embedding provider name |
| `max_k` | `int` | `30` | Maximum candidates to retrieve |
| `rule_selection` | `SelectionConfig` | `SelectionConfig()` | Rule selection strategy |
| `scenario_selection` | `SelectionConfig` | `SelectionConfig()` | Scenario selection strategy |
| `memory_selection` | `SelectionConfig` | `SelectionConfig()` | Memory selection strategy |

### RerankingConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `rerank_provider` | `str` | `"default"` | Rerank provider name |
| `top_k` | `int` | `10` | Number of results after reranking |

### LLMFilteringConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `llm_provider` | `str` | `"haiku"` | LLM provider for filtering |
| `batch_size` | `int` | `5` | Batch size for filtering |

### GenerationConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `llm_provider` | `str` | `"sonnet"` | LLM provider for generation |
| `temperature` | `float` | `0.7` | Generation temperature |
| `max_tokens` | `int` | `1024` | Max tokens for response |

### EnforcementConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable this step |
| `self_critique_enabled` | `bool` | `False` | Enable self-critique |
| `max_retries` | `int` | `2` | Max generation retries |

---

## Selection Strategy Configuration

### SelectionStrategiesConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rule` | `SelectionConfig` | strategy="adaptive_k" | Rule selection |
| `scenario` | `SelectionConfig` | strategy="entropy" | Scenario selection |
| `memory` | `SelectionConfig` | strategy="clustering" | Memory selection |

### SelectionConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | `str` | `"adaptive_k"` | Selection strategy |
| `min_score` | `float` | `0.5` | Minimum score threshold |
| `max_k` | `int` | `10` | Maximum items to select |
| `params` | `dict` | `{}` | Strategy-specific parameters |

**Validation Rules**:
- `strategy` must be one of: elbow, adaptive_k, entropy, clustering, fixed_k
- `min_score` must be between 0.0 and 1.0
- `max_k` must be > 0

**Strategy-specific params**:
- `elbow`: `drop_threshold` (float)
- `adaptive_k`: `alpha` (float), `curvature_threshold` (float)
- `entropy`: `low_k`, `medium_k`, `high_k` (int)
- `clustering`: `eps` (float), `top_per_cluster` (int)
- `fixed_k`: `k` (int)

---

## Observability Configuration

### ObservabilityConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `logging` | `LoggingConfig` | `LoggingConfig()` | Logging settings |
| `tracing` | `TracingConfig` | `TracingConfig()` | Tracing settings |
| `metrics` | `MetricsConfig` | `MetricsConfig()` | Metrics settings |

### LoggingConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | `str` | `"INFO"` | Log level |
| `format` | `str` | `"json"` | Output format |
| `include_trace_id` | `bool` | `True` | Include trace ID in logs |

**Validation Rules**:
- `level` must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `format` must be one of: json, console

### TracingConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable tracing |
| `service_name` | `str` | `"focal"` | Service name for traces |
| `otlp_endpoint` | `str \| None` | `None` | OTLP exporter endpoint |
| `sample_rate` | `float` | `1.0` | Trace sample rate |

**Validation Rules**:
- `sample_rate` must be between 0.0 and 1.0

### MetricsConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable metrics |
| `port` | `int` | `9090` | Metrics server port |
| `path` | `str` | `"/metrics"` | Metrics endpoint path |

**Validation Rules**:
- `port` must be between 1 and 65535

---

## Entity Relationships

```
Settings (root)
    │
    ├── APIConfig
    │   └── RateLimitConfig
    │
    ├── StorageConfig
    │   ├── StoreBackendConfig (config)
    │   ├── StoreBackendConfig (memory)
    │   ├── StoreBackendConfig (session)
    │   └── StoreBackendConfig (audit)
    │
    ├── ProvidersConfig
    │   ├── LLMProviderConfig (dict)
    │   ├── EmbeddingProviderConfig (dict)
    │   └── RerankProviderConfig (dict)
    │
    ├── PipelineConfig
    │   ├── ContextExtractionConfig
    │   ├── RetrievalConfig
    │   │   ├── SelectionConfig (rule)
    │   │   ├── SelectionConfig (scenario)
    │   │   └── SelectionConfig (memory)
    │   ├── RerankingConfig
    │   ├── LLMFilteringConfig
    │   ├── GenerationConfig
    │   └── EnforcementConfig
    │
    ├── SelectionStrategiesConfig
    │   ├── SelectionConfig (rule)
    │   ├── SelectionConfig (scenario)
    │   └── SelectionConfig (memory)
    │
    └── ObservabilityConfig
        ├── LoggingConfig
        ├── TracingConfig
        └── MetricsConfig
```

---

## State Transitions

Configuration models are immutable after loading. No state transitions apply.

The only stateful aspect is the `get_settings()` function which caches the Settings instance via `@lru_cache`. This cache can be cleared for testing via `get_settings.cache_clear()`.
