## TOML Configuration Files

### default.toml (Base Defaults)

```toml
# config/default.toml
# Base configuration - all values have sensible defaults
# Override in environment-specific files

app_name = "focal"
debug = false
log_level = "INFO"

# =============================================================================
# OBSERVABILITY
# =============================================================================
# See docs/architecture/observability.md for full documentation

[observability]
log_format = "json"               # "json" for production, "console" for dev
log_include_trace_id = true       # Add trace_id from OpenTelemetry
log_redact_pii = true             # Auto-redact email, phone, SSN patterns

tracing_enabled = true
tracing_service_name = "focal"
tracing_sample_rate = 1.0         # 1.0 = 100% sampling

metrics_enabled = true
metrics_path = "/metrics"

[api]
host = "0.0.0.0"
port = 8000
workers = 4
request_timeout_seconds = 30

[api.cors]
enabled = true
allow_origins = ["*"]

[api.rate_limit]
enabled = true
requests_per_minute = 60

# =============================================================================
# PROVIDERS - Global Settings
# =============================================================================
#
# Only global provider settings here. Models are configured per pipeline step.
#

[providers]
openrouter_api_key_env = "OPENROUTER_API_KEY"
default_timeout_seconds = 30
default_fallback_on_timeout = true
default_fallback_on_rate_limit = true
default_fallback_on_error = true

# =============================================================================
# PIPELINE CONFIGURATION
# =============================================================================
#
# Each step has its own model fallback chain configured directly.
# Models use LiteLLM format: "provider/model-name"
# Models are tried in order until one succeeds (fallback chain)
# Primary: OpenRouter (built-in failover) → Direct APIs → Alternatives
#

# -----------------------------------------------------------------------------
# Input Processing (Pre-Pipeline)
# -----------------------------------------------------------------------------
[pipeline.input_processing]
# Audio → Text
audio_enabled = true
stt_models = [
    "openai/whisper-1",
    "deepgram/nova-2",
    "assemblyai/best",
]
stt_timeout_seconds = 60

# Image → Text
image_enabled = true
vision_models = [
    "openrouter/anthropic/claude-sonnet-4-5-20250514",
    "anthropic/claude-sonnet-4-5-20250514",
    "openai/gpt-4o",
    "google/gemini-1.5-pro",
]
vision_timeout_seconds = 60
image_understanding_prompt = "Describe this image in detail, including any text visible."

# Document → Text
document_enabled = true
document_models = [
    "llamaparse/default",
    "unstructured/default",
    "azure/document-intelligence",
]
document_timeout_seconds = 120

# Multimodal embedding (optional)
multimodal_retrieval_enabled = false
multimodal_embedding_models = [
    "openai/clip-vit-large-patch14",
    "cohere/embed-english-v3.0",
]

# -----------------------------------------------------------------------------
# Context Extraction Step (fast models - high volume, simple task)
# -----------------------------------------------------------------------------
[pipeline.context_extraction]
enabled = true
mode = "llm"

# LLM models for text extraction
models = [
    "openrouter/anthropic/claude-3-haiku",
    "anthropic/claude-3-haiku-20240307",
    "openai/gpt-4o-mini",
    "google/gemini-1.5-flash",
]
temperature = 0.3
max_tokens = 512
timeout_seconds = 15

# Vision LLM models (when images in context)
vision_models = [
    "openrouter/anthropic/claude-sonnet-4-5-20250514",
    "anthropic/claude-sonnet-4-5-20250514",
    "openai/gpt-4o",
    "google/gemini-1.5-pro",
]
vision_timeout_seconds = 30

# Embedding models (for embedding_only mode)
embedding_models = [
    "openai/text-embedding-3-small",
    "cohere/embed-english-v3.0",
    "voyage/voyage-large-2",
]

history_turns = 5
include_images_in_history = false
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true

# -----------------------------------------------------------------------------
# Retrieval Step
# -----------------------------------------------------------------------------
[pipeline.retrieval]
# Embedding models for vector search
embedding_models = [
    "openai/text-embedding-3-small",
    "cohere/embed-english-v3.0",
    "voyage/voyage-large-2",
]
embedding_batch_size = 100
embedding_timeout_seconds = 30

# Multimodal embedding (optional)
multimodal_embedding_enabled = false
multimodal_embedding_models = [
    "openai/clip-vit-large-patch14",
    "cohere/embed-english-v3.0",
]

# Hybrid search: Vector + BM25
# Combines semantic similarity with keyword matching
# Final score = (1 - bm25_weight) * vector_score + bm25_weight * bm25_score
hybrid_search_enabled = true
bm25_weight = 0.3               # 70% vector, 30% BM25
bm25_k1 = 1.2                   # Term frequency saturation
bm25_b = 0.75                   # Document length normalization

# Graph traversal (memory retrieval only)
# Expands results by following relationships in knowledge graph
graph_traversal_enabled = true
graph_max_hops = 2
graph_relationship_types = ["related_to", "mentioned_in", "follows", "caused_by"]
graph_max_expansion = 10

max_k = 30
min_k = 1
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true

[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"
alpha = 1.5
min_score = 0.5

[pipeline.retrieval.scenario_selection]
strategy = "entropy"
low_entropy_k = 1
medium_entropy_k = 2
high_entropy_k = 3
min_score = 0.6

[pipeline.retrieval.memory_selection]
strategy = "clustering"
eps = 0.1
min_cluster_size = 2
top_per_cluster = 3
min_score = 0.4

# -----------------------------------------------------------------------------
# Reranking Step
# -----------------------------------------------------------------------------
[pipeline.reranking]
enabled = true
models = [
    "cohere/rerank-english-v3.0",
    "voyage/rerank-1",
    "jina/jina-reranker-v2-base-multilingual",
]
timeout_seconds = 30
top_k = 10
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true

# -----------------------------------------------------------------------------
# LLM Filtering Step (fast models - simple yes/no classification)
# -----------------------------------------------------------------------------
[pipeline.llm_filtering]
enabled = true
models = [
    "openrouter/anthropic/claude-3-haiku",
    "anthropic/claude-3-haiku-20240307",
    "openai/gpt-4o-mini",
    "google/gemini-1.5-flash",
]
temperature = 0.0
max_tokens = 256
timeout_seconds = 15
batch_size = 5
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true

# -----------------------------------------------------------------------------
# Response Generation Step (best quality models - this is where it matters)
# -----------------------------------------------------------------------------
[pipeline.generation]
models = [
    "openrouter/anthropic/claude-sonnet-4-5-20250514",
    "anthropic/claude-sonnet-4-5-20250514",
    "openai/gpt-4o",
    "google/gemini-1.5-pro",
]
temperature = 0.7
max_tokens = 2048
timeout_seconds = 60
include_rule_references = false
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true
fallback_on_context_length = true

# -----------------------------------------------------------------------------
# Enforcement Step (fast models - simple binary checks)
# -----------------------------------------------------------------------------
[pipeline.enforcement]
self_critique_enabled = false
models = [
    "openrouter/anthropic/claude-3-haiku",
    "anthropic/claude-3-haiku-20240307",
    "openai/gpt-4o-mini",
    "google/gemini-1.5-flash",
]
temperature = 0.0
max_tokens = 512
timeout_seconds = 15
max_regeneration_attempts = 2
fallback_on_timeout = true
fallback_on_rate_limit = true
fallback_on_error = true

# -----------------------------------------------------------------------------
# Output Processing (Post-Pipeline)
# -----------------------------------------------------------------------------
[pipeline.output_processing]
# Text-to-Speech
tts_enabled = false
tts_models = [
    "openai/tts-1",
    "elevenlabs/eleven_multilingual_v2",
    "google/tts",
]
tts_voice = "alloy"
tts_speed = 1.0
tts_output_format = "mp3"
tts_timeout_seconds = 30

[pipeline.output_processing.tts_voice_mapping]
"openai/tts-1" = "alloy"
"elevenlabs/eleven_multilingual_v2" = "rachel"
"google/tts" = "en-US-Neural2-F"

# Image generation (continued in same section)
# image_generation_enabled = false
# image_generation_models = ["openai/dall-e-3", ...]
# image_default_size = "1024x1024"
# image_default_quality = "standard"
# image_timeout_seconds = 60

# Note: In the actual TOML file, all output_processing keys go in the same section:
# [pipeline.output_processing]
# tts_enabled = false
# tts_models = [...]
# image_generation_enabled = false
# image_generation_models = [...]
# default_output_modality = "text"
# respect_input_modality = true

# =============================================================================
# STORAGE BACKENDS
# =============================================================================

[storage.config]
backend = "postgres"

[storage.config.postgres]
host = "localhost"
port = 5432
database = "focal"
user = "focal"
pool_size = 10

[storage.memory]
backend = "postgres"

[storage.session]
cache_backend = "redis"
persistent_backend = "postgres"
cache_ttl_minutes = 60  # 1 hour in cache, then reload from persistent

[storage.session.redis]
host = "localhost"
port = 6379
db = 0

[storage.session.postgres]
# Uses same connection as storage.config.postgres by default

[storage.audit]
backend = "postgres"
retention_days = 90
```

### development.toml (Development Overrides)

```toml
# config/development.toml
# Local development configuration

debug = true
log_level = "DEBUG"

[observability]
log_format = "console"            # Pretty-printed for local development
tracing_sample_rate = 1.0         # 100% sampling in dev

[api]
workers = 1

[api.rate_limit]
enabled = false

# Use in-memory stores for faster local development
[storage.config]
backend = "inmemory"

[storage.memory]
backend = "inmemory"

[storage.session]
backend = "inmemory"

[storage.audit]
backend = "inmemory"

# Use cheaper models in development (override generation models)
[pipeline.generation]
models = [
    "openrouter/anthropic/claude-3-haiku",
    "anthropic/claude-3-haiku-20240307",
    "openai/gpt-4o-mini",
]
max_tokens = 1024

[pipeline.enforcement]
self_critique_enabled = false
```

### production.toml (Production Overrides)

```toml
# config/production.toml
# Production configuration

debug = false
log_level = "INFO"

[observability]
log_format = "json"
tracing_sample_rate = 0.1         # 10% sampling in production (reduce noise)

[api]
workers = 8
request_timeout_seconds = 60

[api.rate_limit]
requests_per_minute = 120
burst_size = 20

# Use best models in production (explicit quality models)
[pipeline.generation]
models = [
    "openrouter/anthropic/claude-sonnet-4-5-20250514",
    "anthropic/claude-sonnet-4-5-20250514",
    "openai/gpt-4o",
    "google/gemini-1.5-pro",
]
max_tokens = 4096
timeout_seconds = 90

[pipeline.enforcement]
self_critique_enabled = true
# Keep using fast models for critique (already configured in default)

# Production storage (credentials from env vars)
[storage.config]
backend = "postgres"

[storage.config.postgres]
host = "${POSTGRES_HOST}"
port = 5432
database = "focal"
user = "${POSTGRES_USER}"
# password via FOCAL_STORAGE__CONFIG__POSTGRES__PASSWORD env var
pool_size = 20
max_overflow = 40

[storage.memory]
backend = "neo4j"

[storage.memory.neo4j]
uri = "${NEO4J_URI}"
user = "${NEO4J_USER}"
database = "focal"

[storage.session]
cache_backend = "redis"
persistent_backend = "postgres"
cache_ttl_minutes = 60

[storage.session.redis]
host = "${REDIS_HOST}"
port = 6379
max_connections = 100

[storage.audit]
backend = "timescale"
retention_days = 365
```

### test.toml (Testing Overrides)

```toml
# config/test.toml
# Test configuration

debug = true
log_level = "WARNING"

[observability]
log_format = "console"            # Human-readable for test output
tracing_enabled = false           # Disable tracing in tests
metrics_enabled = false           # Disable metrics in tests

[api]
port = 8001
workers = 1

# Always use in-memory stores for tests
[storage.config]
backend = "inmemory"

[storage.memory]
backend = "inmemory"

[storage.session]
backend = "inmemory"

[storage.audit]
backend = "inmemory"

# Use mock models in tests (each step can be overridden)
[pipeline.context_extraction]
models = ["mock/test-model"]

[pipeline.retrieval]
embedding_models = ["mock/test-embedding"]

[pipeline.reranking]
models = ["mock/test-rerank"]

[pipeline.llm_filtering]
models = ["mock/test-model"]

[pipeline.generation]
models = ["mock/test-model"]

[pipeline.enforcement]
models = ["mock/test-model"]
```

---

