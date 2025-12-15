# TOML Configuration Files

> **Source of truth:** `config/*.toml`. This document shows conventions and excerpts; if something conflicts, follow the TOML files and `ruche/config/models/`.

## Files and precedence

Configuration values are resolved in this order (later overrides earlier):

1. Pydantic defaults
2. `config/default.toml`
3. `config/{RUCHE_ENV}.toml` (`development`, `staging`, `production`)
4. Environment variables (`RUCHE_*`)

## Model strings (LLMExecutor)

LLM steps are configured with:

- `model`: the primary model string
- `fallback_models`: optional list of model strings to try if the primary fails

`LLMExecutor` routes based on model string prefix (e.g., `openrouter/`, `anthropic/`, `openai/`, `groq/`, `mock/`).

## Example: `config/default.toml` (excerpt)

```toml
# config/default.toml

app_name = "focal"
debug = false
log_level = "INFO"

[api]
host = "0.0.0.0"
port = 8000
workers = 4

[storage.config]
backend = "postgres"

[storage.session]
backend = "redis"

[providers.embedding.default]
provider = "jina"
model = "jina-embeddings-v3"
dimensions = 1024

[providers.rerank.default]
provider = "jina"
model = "jina-reranker-v2-base-multilingual"

[brain.turn_context]
load_glossary = true
load_interlocutor_data_schema = true
enable_scenario_reconciliation = true

[brain.situational_sensor]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["cerebras", "groq", "google-vertex", "sambanova"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []
temperature = 0.0
max_tokens = 800
history_turns = 5
include_glossary = true
include_schema_mask = true

[brain.retrieval]
enabled = true
embedding_provider = "default"
max_k = 30

[brain.rule_filtering]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
batch_size = 5

[brain.scenario_filtering]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]

[brain.generation]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
temperature = 0.7
max_tokens = 1024

[brain.enforcement]
enabled = true
self_critique_enabled = false
max_retries = 2
```

## Example: `config/test.toml` (excerpt)

```toml
# config/test.toml

debug = true
log_level = "DEBUG"

[storage.config]
backend = "inmemory"

[storage.memory]
backend = "inmemory"

[storage.session]
backend = "inmemory"

[storage.audit]
backend = "inmemory"

[providers.embedding.default]
provider = "mock"
model = "mock-embedding"

[providers.rerank.default]
provider = "mock"
model = "mock-rerank"

[brain.context_extraction]
model = "mock/haiku"

[brain.rule_filtering]
model = "mock/haiku"

[brain.scenario_filtering]
model = "mock/haiku"

[brain.generation]
model = "mock/sonnet"
```

## Notes

- OpenRouter provider routing is configured per-step via `provider_order`, `provider_sort`, `allow_fallbacks`, and `ignore_providers`.
- Embedding and rerank models are configured under `[providers.embedding.*]` and `[providers.rerank.*]`, and referenced from brain steps by provider name (e.g., `embedding_provider = "default"`).
