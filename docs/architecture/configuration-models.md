## Pydantic Models

> **Status:** PARTIALLY STALE. The authoritative configuration models live in `ruche/config/models/`, and the canonical defaults live in `config/*.toml`. Treat the code as the source of truth and validate any snippet here against it.

### Deployment Configuration

Focal supports two deployment modes to accommodate different integration patterns. See [overview.md](./overview.md#deployment-modes) for architectural details.

```python
# ruche/config/models/deployment.py
from typing import Literal

from pydantic import BaseModel, Field


class External PlatformConfig(BaseModel):
    """Configuration for External Platform integration mode."""

    redis_bundle_prefix: str = Field(
        default="{tenant}:{agent}",
        description="Key prefix pattern for Redis bundles"
    )
    config_pointer_key: str = Field(
        default="cfg",
        description="Key suffix for version pointer"
    )
    pubsub_channel: str = Field(
        default="cfg-updated",
        description="Redis pub/sub channel for config updates"
    )
    bundle_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="TTL for cached bundles"
    )
    soft_pin_sessions: bool = Field(
        default=True,
        description="Keep existing sessions on old config version"
    )


class DeploymentConfig(BaseModel):
    """
    Deployment mode configuration.

    Controls whether Focal is the source of truth for configuration
    (standalone) or consumes configuration from an external control plane
    (external).
    """

    mode: Literal["standalone", "external"] = Field(
        default="standalone",
        description="Deployment mode: 'standalone' (Focal owns config) or 'external' (external control plane)"
    )

    # External Platform integration settings (only used when mode = "external")
    external: ExternalPlatformConfig = Field(default_factory=ExternalPlatformConfig)

    # Standalone mode settings
    enable_crud_api: bool = Field(
        default=True,
        description="Enable CRUD endpoints (auto-disabled in external mode)"
    )

    def is_standalone(self) -> bool:
        """Check if running in standalone mode."""
        return self.mode == "standalone"

    def is_external(self) -> bool:
        """Check if running in External Platform integration mode."""
        return self.mode == "external"
```

The Settings class includes deployment configuration:

```python
# In ruche/config/settings.py
from ruche.config.models.deployment import DeploymentConfig

class Settings(BaseSettings):
    # ... existing fields ...
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
```

### API Configuration

```python
# ruche/config/models/api.py
from pydantic import BaseModel, Field


class CORSConfig(BaseModel):
    """CORS configuration."""

    enabled: bool = Field(default=True, description="Enable CORS")
    allow_origins: list[str] = Field(
        default=["*"],
        description="Allowed origins"
    )
    allow_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE"],
        description="Allowed HTTP methods"
    )
    allow_headers: list[str] = Field(
        default=["*"],
        description="Allowed headers"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(default=True, description="Enable rate limiting")
    requests_per_minute: int = Field(
        default=60,
        description="Max requests per minute per tenant"
    )
    burst_size: int = Field(default=10, description="Burst allowance")


class APIConfig(BaseModel):
    """API server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of worker processes")

    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # Timeouts
    request_timeout_seconds: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    graceful_shutdown_seconds: int = Field(
        default=10,
        description="Graceful shutdown timeout"
    )
```

### Provider Configuration

Focal supports multiple AI modalities through a unified provider configuration system. For text generation, the canonical runtime interface is `LLMExecutor`, which uses **Agno** model classes internally and implements fallback chains (Agno does not provide cross-provider fallbacks).

#### Why Agno + OpenRouter?

**Agno** provides a unified interface for calling LLMs across providers while keeping model selection configuration-driven (via model strings).

**OpenRouter** aggregates providers with built-in redundancy:
- Single API key for all major models
- Automatic failover between providers
- Load balancing and rate limit handling
- Often cheaper than direct APIs

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL FALLBACK STRATEGY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request                                                         │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. OpenRouter (primary - built-in provider failover)    │   │
│  │     openrouter/anthropic/claude-sonnet-4-5-20250514     │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │ timeout / rate-limit / error                              │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  2. Direct Anthropic API                                 │   │
│  │     anthropic/claude-sonnet-4-5-20250514                │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │ timeout / rate-limit / error                              │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  3. Direct OpenAI API                                    │   │
│  │     openai/gpt-4o                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │ timeout / rate-limit / error                              │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  4. Direct Google API                                    │   │
│  │     google/gemini-1.5-pro                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│     │ all failed                                                │
│     ▼                                                           │
│  Error / Fallback template                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Provider Categories

| Category | Input | Output | Use Cases |
|----------|-------|--------|-----------|
| **LLM** | Text | Text | Generation, filtering, context extraction |
| **Vision LLM** | Image + Text | Text | Image understanding, document analysis |
| **Embedding** | Text | Vector | Semantic search, retrieval |
| **Multimodal Embedding** | Image/Text | Vector | Cross-modal search |
| **Speech-to-Text (STT)** | Audio | Text | Voice input processing |
| **Text-to-Speech (TTS)** | Text | Audio | Voice responses |
| **Image Generation** | Text | Image | Visual content creation |
| **Document Processing** | PDF/Doc | Text | Document ingestion |
| **Rerank** | Text pairs | Scores | Result reordering |

```python
# ruche/config/models/providers.py
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


# =============================================================================
# Model Specification (LLMExecutor model string format)
# =============================================================================

class ModelSpec(BaseModel):
    """
    A single model specification in the model string format used by `LLMExecutor`.

    Model string format: "provider/model-name"
    Examples:
    - "anthropic/claude-sonnet-4-5-20250514"
    - "openai/gpt-4o"
    - "openrouter/anthropic/claude-sonnet-4-5-20250514"
    - "google/gemini-1.5-pro"
    - "bedrock/anthropic.claude-3-sonnet"
    """

    model: str = Field(
        description="Model identifier (provider/model-name)"
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name for API key (auto-detected if None)"
    )
    api_base: str | None = Field(
        default=None,
        description="Custom API base URL"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Timeout for this specific model"
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Max retries before falling back to next model"
    )


# =============================================================================
# LLM Providers (Text Generation) with Fallback Chains
# =============================================================================

class LLMProviderConfig(BaseModel):
    """
    Configuration for LLM with fallback chain.

    Models are tried in order until one succeeds.
    Used by `LLMExecutor` (Agno-backed) for unified provider access.
    """

    # Fallback chain: list of models to try in order
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-3-haiku",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
            "google/gemini-1.5-flash",
        ],
        description="Fallback chain of model strings. First = primary."
    )

    # Optional detailed config per model (overrides defaults)
    model_config_overrides: dict[str, ModelSpec] = Field(
        default_factory=dict,
        description="Per-model configuration overrides"
    )

    # Generation defaults (applied to all models in chain)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=100000)
    timeout_seconds: int = Field(default=30, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(
        default=True,
        description="Try next model on timeout"
    )
    fallback_on_rate_limit: bool = Field(
        default=True,
        description="Try next model on rate limit (429)"
    )
    fallback_on_error: bool = Field(
        default=True,
        description="Try next model on API error (5xx)"
    )
    fallback_on_context_length: bool = Field(
        default=True,
        description="Try next model if context too long"
    )


# =============================================================================
# Vision LLM Providers (Image + Text → Text) with Fallback Chains
# =============================================================================

class VisionLLMProviderConfig(BaseModel):
    """Configuration for vision-capable LLM with fallback chain."""

    # Fallback chain for vision models
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-sonnet-4-5-20250514",
            "anthropic/claude-sonnet-4-5-20250514",
            "openai/gpt-4o",
            "google/gemini-1.5-pro",
        ],
        description="Fallback chain of vision model strings"
    )

    # Image handling
    max_image_size_mb: float = Field(
        default=20.0,
        description="Maximum image size in MB"
    )
    supported_formats: list[str] = Field(
        default=["png", "jpg", "jpeg", "gif", "webp"],
        description="Supported image formats"
    )

    # Generation defaults
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=100000)
    timeout_seconds: int = Field(default=60, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Embedding Providers (Text → Vector) with Fallback Chains
# =============================================================================

class EmbeddingProviderConfig(BaseModel):
    """
    Configuration for text embedding with fallback chain.

    Note: Fallback for embeddings is tricky because different models
    produce different vector spaces. Use fallbacks only for availability,
    not for mixing embeddings in the same index.
    """

    # Fallback chain for embedding models
    models: list[str] = Field(
        default=[
            "openai/text-embedding-3-small",
            "cohere/embed-english-v3.0",
            "voyage/voyage-large-2",
        ],
        description="Fallback chain of embedding model strings"
    )

    # Embedding settings
    dimensions: int | None = Field(
        default=None,
        description="Embedding dimensions (None = model default)"
    )
    batch_size: int = Field(default=100, ge=1, le=2048)
    timeout_seconds: int = Field(default=30, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Multimodal Embedding Providers (Image/Text → Vector)
# =============================================================================

class MultimodalEmbeddingProviderConfig(BaseModel):
    """Configuration for multimodal embedding (CLIP-style) with fallback."""

    models: list[str] = Field(
        default=[
            "openai/clip-vit-large-patch14",
            "cohere/embed-english-v3.0",  # Supports images
        ],
        description="Fallback chain of multimodal embedding models"
    )

    dimensions: int = Field(default=768, description="Embedding dimensions")
    timeout_seconds: int = Field(default=30, ge=1)

    # Modality support
    supports_image: bool = Field(default=True)
    supports_text: bool = Field(default=True)


# =============================================================================
# Speech-to-Text Providers (Audio → Text) with Fallback Chains
# =============================================================================

class STTProviderConfig(BaseModel):
    """Configuration for speech-to-text with fallback chain."""

    # Fallback chain for STT models
    models: list[str] = Field(
        default=[
            "openai/whisper-1",
            "deepgram/nova-2",
            "assemblyai/best",
        ],
        description="Fallback chain of STT models"
    )

    # Audio settings
    language: str | None = Field(
        default=None,
        description="Language code (None = auto-detect)"
    )
    supported_formats: list[str] = Field(
        default=["mp3", "wav", "m4a", "webm", "ogg", "flac"],
        description="Supported audio formats"
    )
    max_duration_seconds: int = Field(
        default=300,
        description="Maximum audio duration"
    )
    timeout_seconds: int = Field(default=60, ge=1)

    # Processing options
    enable_word_timestamps: bool = Field(
        default=False,
        description="Include word-level timestamps"
    )
    enable_diarization: bool = Field(
        default=False,
        description="Speaker diarization (if supported)"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Text-to-Speech Providers (Text → Audio) with Fallback Chains
# =============================================================================

class TTSProviderConfig(BaseModel):
    """Configuration for text-to-speech with fallback chain."""

    # Fallback chain for TTS models
    models: list[str] = Field(
        default=[
            "openai/tts-1",
            "elevenlabs/eleven_multilingual_v2",
            "google/tts",
            "azure/tts",
        ],
        description="Fallback chain of TTS models"
    )

    # Voice settings (provider-specific, may need mapping)
    voice: str = Field(
        default="alloy",
        description="Voice identifier (provider-specific)"
    )
    voice_mapping: dict[str, str] = Field(
        default_factory=lambda: {
            "openai/tts-1": "alloy",
            "elevenlabs/eleven_multilingual_v2": "rachel",
            "google/tts": "en-US-Neural2-F",
            "azure/tts": "en-US-JennyNeural",
        },
        description="Voice mapping per provider"
    )
    speed: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speech speed multiplier"
    )

    # Output settings
    output_format: Literal["mp3", "wav", "ogg", "flac"] = Field(
        default="mp3",
        description="Output audio format"
    )
    sample_rate: int = Field(
        default=24000,
        description="Sample rate in Hz"
    )
    timeout_seconds: int = Field(default=30, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Image Generation Providers (Text → Image) with Fallback Chains
# =============================================================================

class ImageGenerationProviderConfig(BaseModel):
    """Configuration for image generation with fallback chain."""

    # Fallback chain for image generation
    models: list[str] = Field(
        default=[
            "openai/dall-e-3",
            "stability/stable-diffusion-xl-1024-v1-0",
            "replicate/stability-ai/sdxl",
        ],
        description="Fallback chain of image generation models"
    )

    # Generation settings
    default_size: str = Field(
        default="1024x1024",
        description="Default image size"
    )
    default_quality: Literal["standard", "hd"] = Field(
        default="standard",
        description="Image quality"
    )
    default_style: Literal["natural", "vivid"] = Field(
        default="natural",
        description="Image style"
    )
    timeout_seconds: int = Field(default=60, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Document Processing Providers (PDF/Doc → Text) with Fallback Chains
# =============================================================================

class DocumentProcessingProviderConfig(BaseModel):
    """Configuration for document processing with fallback chain."""

    # Fallback chain for document processing
    models: list[str] = Field(
        default=[
            "llamaparse/default",
            "unstructured/default",
            "azure/document-intelligence",
        ],
        description="Fallback chain of document processing providers"
    )

    # Processing options
    extract_tables: bool = Field(
        default=True,
        description="Extract tables as structured data"
    )
    extract_images: bool = Field(
        default=False,
        description="Extract embedded images"
    )
    ocr_enabled: bool = Field(
        default=True,
        description="Enable OCR for scanned documents"
    )
    ocr_language: str = Field(
        default="eng",
        description="OCR language code"
    )
    timeout_seconds: int = Field(default=120, ge=1)

    # Supported formats
    supported_formats: list[str] = Field(
        default=["pdf", "docx", "doc", "pptx", "xlsx", "txt", "html", "md"],
        description="Supported document formats"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Rerank Providers (Text pairs → Scores) with Fallback Chains
# =============================================================================

class RerankProviderConfig(BaseModel):
    """Configuration for reranking with fallback chain."""

    # Fallback chain for reranking
    models: list[str] = Field(
        default=[
            "cohere/rerank-english-v3.0",
            "voyage/rerank-1",
            "jina/jina-reranker-v2-base-multilingual",
        ],
        description="Fallback chain of rerank models"
    )

    top_k: int = Field(default=10, ge=1, le=100)
    timeout_seconds: int = Field(default=30, ge=1)

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Root Providers Configuration
# =============================================================================

class ProvidersConfig(BaseModel):
    """
    Global provider settings and defaults.

    NOTE: Models are configured directly on each brain step, not here.
    This config only holds global settings like timeout defaults and
    fallback behavior defaults that steps can inherit.
    """

    # -------------------------------------------------------------------------
    # Global settings
    # -------------------------------------------------------------------------
    openrouter_api_key_env: str = Field(
        default="OPENROUTER_API_KEY",
        description="Env var for OpenRouter API key"
    )

    # -------------------------------------------------------------------------
    # Default fallback behavior (inherited by steps if not specified)
    # -------------------------------------------------------------------------
    default_timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Default timeout for provider calls"
    )
    default_fallback_on_timeout: bool = Field(
        default=True,
        description="Try next model on timeout"
    )
    default_fallback_on_rate_limit: bool = Field(
        default=True,
        description="Try next model on rate limit (429)"
    )
    default_fallback_on_error: bool = Field(
        default=True,
        description="Try next model on API error (5xx)"
    )
```

#### LLMExecutor Integration

LLM calls are executed via `LLMExecutor`, which uses Agno model classes internally and implements the fallback chain itself.

```python
from ruche.config.settings import get_settings
from ruche.providers.llm import LLMMessage, create_executor_from_step_config

settings = get_settings()
executor = create_executor_from_step_config(settings.brain.generation, "generation")

response = await executor.generate(
    messages=[LLMMessage(role="user", content="Hello, world!")],
)
```

### Selection Strategy Configuration

```python
# ruche/config/models/selection.py
from typing import Literal

from pydantic import BaseModel, Field


class ElbowSelectionConfig(BaseModel):
    """Configuration for elbow selection strategy."""

    strategy: Literal["elbow"] = "elbow"
    drop_threshold: float = Field(
        default=0.15,
        ge=0.01,
        le=1.0,
        description="Minimum relative drop to trigger cutoff"
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Absolute minimum score to include"
    )


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
    low_entropy_k: int = Field(
        default=3,
        ge=1,
        description="Items to take when confident (entropy < 1.0)"
    )
    medium_entropy_k: int = Field(
        default=5,
        ge=1,
        description="Items to take when uncertain (entropy 1.0-2.0)"
    )
    high_entropy_k: int = Field(
        default=10,
        ge=1,
        description="Items to take when very uncertain (entropy > 2.0)"
    )
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)


class ClusterSelectionConfig(BaseModel):
    """Configuration for clustering-based selection strategy."""

    strategy: Literal["clustering"] = "clustering"
    eps: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="DBSCAN neighborhood size (score distance)"
    )
    min_cluster_size: int = Field(
        default=2,
        ge=1,
        description="Minimum items to form a cluster"
    )
    top_per_cluster: int = Field(
        default=3,
        ge=1,
        description="Items to take from each cluster"
    )
    min_score: float = Field(default=0.4, ge=0.0, le=1.0)


class FixedKSelectionConfig(BaseModel):
    """Configuration for fixed-k selection strategy."""

    strategy: Literal["fixed_k"] = "fixed_k"
    k: int = Field(default=5, ge=1, le=100, description="Fixed number of items")
    min_score: float | None = Field(
        default=None,
        description="Optional minimum score filter"
    )


# Union type for any selection strategy config
SelectionStrategyConfig = (
    ElbowSelectionConfig
    | AdaptiveKSelectionConfig
    | EntropySelectionConfig
    | ClusterSelectionConfig
    | FixedKSelectionConfig
)


def get_default_selection_config(strategy: str) -> SelectionStrategyConfig:
    """Get default configuration for a strategy."""
    defaults = {
        "elbow": ElbowSelectionConfig,
        "adaptive_k": AdaptiveKSelectionConfig,
        "entropy": EntropySelectionConfig,
        "clustering": ClusterSelectionConfig,
        "fixed_k": FixedKSelectionConfig,
    }
    if strategy not in defaults:
        raise ValueError(f"Unknown strategy: {strategy}")
    return defaults[strategy]()
```

### Brain Configuration

The brain configuration defines which model/provider is used at each step. This enables:
- Different models for different tasks (fast model for filtering, best model for generation)
- Multimodal processing (vision for images, STT for audio)
- Cost optimization (cheaper models for simple tasks)

```python
# ruche/config/models/brain.py
from typing import Literal

from pydantic import BaseModel, Field

from ruche.config.models.selection import (
    AdaptiveKSelectionConfig,
    ClusterSelectionConfig,
    EntropySelectionConfig,
    SelectionStrategyConfig,
)


# =============================================================================
# Input Processing (Pre-Brain)
# =============================================================================

class InputProcessingConfig(BaseModel):
    """
    Configuration for input modality processing.

    Converts non-text inputs to text BEFORE the alignment brain.
    Each modality has its own model fallback chain.
    """

    # -------------------------------------------------------------------------
    # Audio input (voice messages)
    # -------------------------------------------------------------------------
    audio_enabled: bool = Field(
        default=True,
        description="Accept audio input"
    )
    stt_models: list[str] = Field(
        default=[
            "openai/whisper-1",
            "deepgram/nova-2",
            "assemblyai/best",
        ],
        description="Speech-to-text model fallback chain"
    )
    stt_timeout_seconds: int = Field(default=60, ge=1)

    # -------------------------------------------------------------------------
    # Image input
    # -------------------------------------------------------------------------
    image_enabled: bool = Field(
        default=True,
        description="Accept image input"
    )
    vision_models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-sonnet-4-5-20250514",
            "anthropic/claude-sonnet-4-5-20250514",
            "openai/gpt-4o",
            "google/gemini-1.5-pro",
        ],
        description="Vision LLM model fallback chain for image understanding"
    )
    vision_timeout_seconds: int = Field(default=60, ge=1)
    image_understanding_prompt: str = Field(
        default="Describe this image in detail, including any text visible.",
        description="Prompt for image-to-text conversion"
    )

    # -------------------------------------------------------------------------
    # Document input
    # -------------------------------------------------------------------------
    document_enabled: bool = Field(
        default=True,
        description="Accept document input (PDF, DOCX, etc.)"
    )
    document_models: list[str] = Field(
        default=[
            "llamaparse/default",
            "unstructured/default",
            "azure/document-intelligence",
        ],
        description="Document processing model fallback chain"
    )
    document_timeout_seconds: int = Field(default=120, ge=1)

    # -------------------------------------------------------------------------
    # Multimodal embedding (for retrieval with images)
    # -------------------------------------------------------------------------
    multimodal_retrieval_enabled: bool = Field(
        default=False,
        description="Enable image-based retrieval using multimodal embeddings"
    )
    multimodal_embedding_models: list[str] = Field(
        default=[
            "openai/clip-vit-large-patch14",
            "cohere/embed-english-v3.0",
        ],
        description="Multimodal embedding model fallback chain"
    )


# =============================================================================
# Context Extraction Step
# =============================================================================

class ContextExtractionConfig(BaseModel):
    """
    Configuration for context extraction step.

    Understands user intent from message + conversation history.
    Uses fast/cheap models since this is high-volume, simple task.
    """

    enabled: bool = Field(default=True, description="Enable context extraction")
    mode: Literal["llm", "vision_llm", "embedding_only", "disabled"] = Field(
        default="llm",
        description="Extraction mode"
    )

    # -------------------------------------------------------------------------
    # LLM models for text-only extraction (fast models recommended)
    # -------------------------------------------------------------------------
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-3-haiku",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
            "google/gemini-1.5-flash",
        ],
        description="LLM model fallback chain for context extraction"
    )
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=10000)
    timeout_seconds: int = Field(default=15, ge=1)

    # -------------------------------------------------------------------------
    # Vision LLM models (when images are in context)
    # -------------------------------------------------------------------------
    vision_models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-sonnet-4-5-20250514",
            "anthropic/claude-sonnet-4-5-20250514",
            "openai/gpt-4o",
            "google/gemini-1.5-pro",
        ],
        description="Vision LLM model fallback chain (when images in context)"
    )
    vision_timeout_seconds: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # Embedding models (for embedding_only mode)
    # -------------------------------------------------------------------------
    embedding_models: list[str] = Field(
        default=[
            "openai/text-embedding-3-small",
            "cohere/embed-english-v3.0",
            "voyage/voyage-large-2",
        ],
        description="Embedding model fallback chain for embedding_only mode"
    )

    # -------------------------------------------------------------------------
    # History settings
    # -------------------------------------------------------------------------
    history_turns: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Number of history turns to include"
    )
    include_images_in_history: bool = Field(
        default=False,
        description="Include images from history (requires vision_llm)"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Retrieval Step
# =============================================================================

class RetrievalConfig(BaseModel):
    """
    Configuration for retrieval step.

    Finds relevant rules, scenarios, and memory via hybrid search:
    - Vector search (semantic similarity)
    - BM25 keyword search (exact term matching)
    - Graph traversal (relationship-based, memory only)

    See docs/design/decisions/002-rule-matching-strategy.md for algorithm details.
    """

    # -------------------------------------------------------------------------
    # Embedding models for text retrieval
    # -------------------------------------------------------------------------
    embedding_models: list[str] = Field(
        default=[
            "openai/text-embedding-3-small",
            "cohere/embed-english-v3.0",
            "voyage/voyage-large-2",
        ],
        description="Embedding model fallback chain"
    )
    embedding_batch_size: int = Field(default=100, ge=1, le=2048)
    embedding_timeout_seconds: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # Multimodal embedding (for image-based retrieval)
    # -------------------------------------------------------------------------
    multimodal_embedding_enabled: bool = Field(
        default=False,
        description="Enable multimodal embedding for image search"
    )
    multimodal_embedding_models: list[str] = Field(
        default=[
            "openai/clip-vit-large-patch14",
            "cohere/embed-english-v3.0",
        ],
        description="Multimodal embedding model fallback chain"
    )

    # -------------------------------------------------------------------------
    # Hybrid Search: Vector + BM25
    # -------------------------------------------------------------------------
    # Combines semantic similarity (vector) with keyword matching (BM25)
    # Final score = (1 - bm25_weight) * vector_score + bm25_weight * bm25_score
    #
    hybrid_search_enabled: bool = Field(
        default=True,
        description="Enable hybrid vector + BM25 search"
    )
    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 score (vector gets 1 - this value)"
    )
    bm25_k1: float = Field(
        default=1.2,
        ge=0.0,
        le=3.0,
        description="BM25 term frequency saturation parameter"
    )
    bm25_b: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="BM25 document length normalization (0=no norm, 1=full norm)"
    )

    # -------------------------------------------------------------------------
    # Graph Traversal (Memory retrieval only)
    # -------------------------------------------------------------------------
    # After vector+BM25 retrieval, optionally expand results by traversing
    # relationships in the knowledge graph. Only applies to MemoryStore.
    #
    graph_traversal_enabled: bool = Field(
        default=True,
        description="Enable graph traversal for memory retrieval"
    )
    graph_max_hops: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum relationship hops from seed nodes"
    )
    graph_relationship_types: list[str] = Field(
        default=["related_to", "mentioned_in", "follows", "caused_by"],
        description="Relationship types to traverse"
    )
    graph_max_expansion: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum nodes to add via graph expansion"
    )

    # -------------------------------------------------------------------------
    # Retrieval limits
    # -------------------------------------------------------------------------
    max_k: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum candidates to retrieve"
    )
    min_k: int = Field(
        default=1,
        ge=1,
        description="Minimum results to return"
    )

    # -------------------------------------------------------------------------
    # Selection strategies per retrieval type
    # -------------------------------------------------------------------------
    rule_selection: SelectionStrategyConfig = Field(
        default_factory=AdaptiveKSelectionConfig,
        description="Selection strategy for rules"
    )
    scenario_selection: SelectionStrategyConfig = Field(
        default_factory=lambda: EntropySelectionConfig(
            low_entropy_k=1,
            medium_entropy_k=2,
            high_entropy_k=3,
            min_score=0.6,
        ),
        description="Selection strategy for scenarios"
    )
    memory_selection: SelectionStrategyConfig = Field(
        default_factory=lambda: ClusterSelectionConfig(
            eps=0.1,
            top_per_cluster=3,
            min_score=0.4,
        ),
        description="Selection strategy for memory"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Reranking Step
# =============================================================================

class RerankingConfig(BaseModel):
    """Configuration for reranking step."""

    enabled: bool = Field(default=True, description="Enable reranking")

    # -------------------------------------------------------------------------
    # Rerank models
    # -------------------------------------------------------------------------
    models: list[str] = Field(
        default=[
            "cohere/rerank-english-v3.0",
            "voyage/rerank-1",
            "jina/jina-reranker-v2-base-multilingual",
        ],
        description="Rerank model fallback chain"
    )
    timeout_seconds: int = Field(default=30, ge=1)

    # Reranking settings
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Items to keep after reranking"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# LLM Filtering Step
# =============================================================================

class LLMFilteringConfig(BaseModel):
    """
    Configuration for LLM filtering step.

    Uses LLM to judge which rules actually apply.
    Fast models recommended since this is simple yes/no classification.
    """

    enabled: bool = Field(default=True, description="Enable LLM filtering")

    # -------------------------------------------------------------------------
    # LLM models for filtering (fast models recommended)
    # -------------------------------------------------------------------------
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-3-haiku",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
            "google/gemini-1.5-flash",
        ],
        description="LLM model fallback chain for filtering"
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=256, ge=1, le=2048)
    timeout_seconds: int = Field(default=15, ge=1)

    # Filtering settings
    batch_size: int = Field(
        default=5,
        ge=1,
        description="Rules to evaluate per LLM call"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Response Generation Step
# =============================================================================

class GenerationConfig(BaseModel):
    """
    Configuration for response generation step.

    The main LLM generation - use best quality models here.
    This is where response quality matters most.
    """

    # -------------------------------------------------------------------------
    # LLM models for generation (best quality models recommended)
    # -------------------------------------------------------------------------
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-sonnet-4-5-20250514",
            "anthropic/claude-sonnet-4-5-20250514",
            "openai/gpt-4o",
            "google/gemini-1.5-pro",
        ],
        description="LLM model fallback chain for generation"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=100000)
    timeout_seconds: int = Field(default=60, ge=1)

    # Response formatting
    include_rule_references: bool = Field(
        default=False,
        description="Include matched rule IDs in response metadata"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)
    fallback_on_context_length: bool = Field(
        default=True,
        description="Try next model if context too long"
    )


# =============================================================================
# Enforcement Step
# =============================================================================

class EnforcementConfig(BaseModel):
    """
    Configuration for enforcement step.

    Validates response against hard constraints.
    Fast models recommended for self-critique (simple binary checks).
    """

    # -------------------------------------------------------------------------
    # Self-critique configuration
    # -------------------------------------------------------------------------
    self_critique_enabled: bool = Field(
        default=False,
        description="Enable LLM self-critique"
    )

    # LLM models for self-critique (fast models recommended)
    models: list[str] = Field(
        default=[
            "openrouter/anthropic/claude-3-haiku",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
            "google/gemini-1.5-flash",
        ],
        description="LLM model fallback chain for self-critique"
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    timeout_seconds: int = Field(default=15, ge=1)

    # Enforcement settings
    max_regeneration_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max attempts to regenerate failed responses"
    )

    # Fallback behavior
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Output Processing (Post-Brain)
# =============================================================================

class OutputProcessingConfig(BaseModel):
    """
    Configuration for output modality processing.

    Converts text response to target modality AFTER generation.
    Each output modality has its own model fallback chain.
    """

    # -------------------------------------------------------------------------
    # Text-to-Speech
    # -------------------------------------------------------------------------
    tts_enabled: bool = Field(
        default=False,
        description="Generate audio response"
    )
    tts_models: list[str] = Field(
        default=[
            "openai/tts-1",
            "elevenlabs/eleven_multilingual_v2",
            "google/tts",
        ],
        description="TTS model fallback chain"
    )
    tts_voice: str = Field(
        default="alloy",
        description="Voice identifier (provider-specific)"
    )
    tts_voice_mapping: dict[str, str] = Field(
        default_factory=lambda: {
            "openai/tts-1": "alloy",
            "elevenlabs/eleven_multilingual_v2": "rachel",
            "google/tts": "en-US-Neural2-F",
        },
        description="Voice mapping per provider"
    )
    tts_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    tts_output_format: Literal["mp3", "wav", "ogg", "flac"] = Field(default="mp3")
    tts_timeout_seconds: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # Image generation
    # -------------------------------------------------------------------------
    image_generation_enabled: bool = Field(
        default=False,
        description="Allow image generation in responses"
    )
    image_generation_models: list[str] = Field(
        default=[
            "openai/dall-e-3",
            "stability/stable-diffusion-xl-1024-v1-0",
            "replicate/stability-ai/sdxl",
        ],
        description="Image generation model fallback chain"
    )
    image_default_size: str = Field(default="1024x1024")
    image_default_quality: Literal["standard", "hd"] = Field(default="standard")
    image_timeout_seconds: int = Field(default=60, ge=1)

    # -------------------------------------------------------------------------
    # Response modality selection
    # -------------------------------------------------------------------------
    default_output_modality: Literal["text", "audio", "multimodal"] = Field(
        default="text",
        description="Default output modality"
    )
    respect_input_modality: bool = Field(
        default=True,
        description="Match output modality to input (voice in → voice out)"
    )

    # Fallback behavior (applies to all output modalities)
    fallback_on_timeout: bool = Field(default=True)
    fallback_on_rate_limit: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


# =============================================================================
# Full Brain Configuration
# =============================================================================

class PipelineConfig(BaseModel):
    """
    Full brain configuration.

    Defines which model/provider is used at each step.
    """

    # Pre-brain: Input modality processing
    input_processing: InputProcessingConfig = Field(
        default_factory=InputProcessingConfig
    )

    # Brain steps
    context_extraction: ContextExtractionConfig = Field(
        default_factory=ContextExtractionConfig
    )
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    reranking: RerankingConfig = Field(default_factory=RerankingConfig)
    llm_filtering: LLMFilteringConfig = Field(default_factory=LLMFilteringConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    enforcement: EnforcementConfig = Field(default_factory=EnforcementConfig)

    # Post-brain: Output modality processing
    output_processing: OutputProcessingConfig = Field(
        default_factory=OutputProcessingConfig
    )
```

#### Brain Model Reference

Each brain step has its own model fallback chain configured directly. No indirection through named profiles - models are specified exactly where they're used.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MULTIMODAL BRAIN                                  │
│                   (models configured directly per step)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT (any modality)                                                        │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  INPUT PROCESSING                                                       │ │
│  │                                                                         │ │
│  │  Audio ──► stt_models ────────────────────────────────────┐            │ │
│  │            [whisper-1 → deepgram → assemblyai]             │            │ │
│  │                                                            │            │ │
│  │  Image ──► vision_models ─────────────────────────────────┼──► Text    │ │
│  │            [claude-sonnet → gpt-4o → gemini-pro]          │            │ │
│  │                                                            │            │ │
│  │  Document ──► document_models ────────────────────────────┘            │ │
│  │               [llamaparse → unstructured → azure]                       │ │
│  │                                                                         │ │
│  │  Text ────────────────────────────────────────────────────────► Text   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  CONTEXT EXTRACTION                                                     │ │
│  │  models: [claude-haiku → gpt-4o-mini → gemini-flash]                   │ │
│  │  vision_models: [claude-sonnet → gpt-4o → gemini-pro]                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  RETRIEVAL                                                              │ │
│  │  embedding_models: [text-embedding-3-small → cohere → voyage]          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  RERANKING                                                              │ │
│  │  models: [cohere/rerank → voyage/rerank → jina/rerank]                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  LLM FILTERING                                                          │ │
│  │  models: [claude-haiku → gpt-4o-mini → gemini-flash]                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  GENERATION                                                             │ │
│  │  models: [claude-sonnet → gpt-4o → gemini-pro]                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  ENFORCEMENT                                                            │ │
│  │  models: [claude-haiku → gpt-4o-mini → gemini-flash]                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  OUTPUT PROCESSING                                                      │ │
│  │                                                                         │ │
│  │  Text ────────────────────────────────────────────────────────► Text   │ │
│  │                                                                         │ │
│  │  Text ──► tts_models ─────────────────────────────────────────► Audio  │ │
│  │           [openai/tts → elevenlabs → google/tts]                       │ │
│  │                                                                         │ │
│  │  Text ──► image_generation_models ────────────────────────────► Image  │ │
│  │           [dall-e-3 → stable-diffusion → sdxl]                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  OUTPUT (target modality)                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Storage Configuration

```python
# ruche/config/models/storage.py
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class PostgresConfig(BaseModel):
    """PostgreSQL connection configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="focal")
    user: str = Field(default="focal")
    password: SecretStr = Field(default=SecretStr(""))

    # Connection pool
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0)

    @property
    def dsn(self) -> str:
        """Get connection string (without password)."""
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0, ge=0, le=15)
    password: SecretStr | None = Field(default=None)

    # Connection pool
    max_connections: int = Field(default=50, ge=1)

    @property
    def url(self) -> str:
        """Get Redis URL (without password)."""
        return f"redis://{self.host}:{self.port}/{self.db}"


class Neo4jConfig(BaseModel):
    """Neo4j connection configuration."""

    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: SecretStr = Field(default=SecretStr(""))
    database: str = Field(default="neo4j")

    # Connection pool
    max_connection_pool_size: int = Field(default=50, ge=1)


class MongoDBConfig(BaseModel):
    """MongoDB connection configuration."""

    uri: str = Field(default="mongodb://localhost:27017")
    database: str = Field(default="focal")

    # Connection pool
    max_pool_size: int = Field(default=50, ge=1)


class ConfigStoreConfig(BaseModel):
    """Configuration for ConfigStore backend."""

    backend: Literal["postgres", "mongodb", "inmemory"] = Field(
        default="postgres",
        description="Storage backend"
    )
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)


class MemoryStoreConfig(BaseModel):
    """Configuration for MemoryStore backend."""

    backend: Literal["postgres", "neo4j", "mongodb", "inmemory"] = Field(
        default="postgres",
        description="Storage backend"
    )
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)


class SessionStoreConfig(BaseModel):
    """Configuration for SessionStore backend.

    Sessions use two-tier storage:
    - Cache (Redis): Fast access, short TTL
    - Persistent (PostgreSQL/MongoDB): Long-term storage

    On cache miss, session is loaded from persistent store and re-cached.
    """

    cache_backend: Literal["redis", "inmemory"] = Field(
        default="redis",
        description="Cache backend for fast session access"
    )
    persistent_backend: Literal["postgres", "mongodb"] = Field(
        default="postgres",
        description="Persistent backend for long-term session storage"
    )
    redis: RedisConfig = Field(default_factory=RedisConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)

    # Cache TTL (how long session stays in cache after last activity)
    cache_ttl_minutes: int = Field(
        default=60,
        ge=1,
        description="Cache TTL in minutes (session reloaded from persistent on miss)"
    )


class AuditStoreConfig(BaseModel):
    """Configuration for AuditStore backend."""

    backend: Literal["postgres", "timescale", "clickhouse", "mongodb", "inmemory"] = Field(
        default="postgres",
        description="Storage backend"
    )
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)

    # Retention
    retention_days: int = Field(
        default=90,
        ge=1,
        description="Days to retain audit records"
    )


class StorageConfig(BaseModel):
    """All storage configurations."""

    config: ConfigStoreConfig = Field(default_factory=ConfigStoreConfig)
    memory: MemoryStoreConfig = Field(default_factory=MemoryStoreConfig)
    session: SessionStoreConfig = Field(
        default_factory=SessionStoreConfig
    )
    audit: AuditStoreConfig = Field(default_factory=AuditStoreConfig)
```

### Observability Configuration

See [observability.md](./observability.md) for detailed architecture. The Pydantic model below defines the configuration schema.

```python
# ruche/config/models/observability.py
from typing import Literal

from pydantic import BaseModel, Field


class ObservabilityConfig(BaseModel):
    """
    Observability configuration for logging, tracing, and metrics.

    Note: Root-level `log_level` and `debug` settings are in the main Settings
    class for backward compatibility. This config handles advanced settings.

    See docs/architecture/observability.md for full documentation.
    """

    # -------------------------------------------------------------------------
    # Logging (extends root-level log_level)
    # -------------------------------------------------------------------------
    log_format: Literal["json", "console"] = Field(
        default="json",
        description="Log output format: 'json' for production, 'console' for dev"
    )
    log_include_trace_id: bool = Field(
        default=True,
        description="Include OpenTelemetry trace_id in log entries"
    )
    log_redact_pii: bool = Field(
        default=True,
        description="Auto-redact email, phone, SSN patterns from logs"
    )
    log_redact_patterns: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns to redact from logs"
    )

    # -------------------------------------------------------------------------
    # Tracing (OpenTelemetry)
    # -------------------------------------------------------------------------
    tracing_enabled: bool = Field(
        default=True,
        description="Enable distributed tracing"
    )
    tracing_service_name: str = Field(
        default="focal",
        description="Service name for traces (overridden by OTEL_SERVICE_NAME)"
    )
    tracing_otlp_endpoint: str = Field(
        default="",
        description="OTLP endpoint (empty = use OTEL_EXPORTER_OTLP_ENDPOINT env var)"
    )
    tracing_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (1.0 = 100%, reduce in production)"
    )
    tracing_propagators: list[str] = Field(
        default=["tracecontext", "baggage"],
        description="W3C trace context propagators"
    )

    # -------------------------------------------------------------------------
    # Metrics (Prometheus)
    # -------------------------------------------------------------------------
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics endpoint"
    )
    metrics_path: str = Field(
        default="/metrics",
        description="Path for metrics endpoint"
    )
    metrics_include_default: bool = Field(
        default=True,
        description="Include Python process metrics (memory, GC, etc.)"
    )
```

The Settings class includes observability configuration:

```python
# In ruche/config/settings.py
from ruche.config.models.observability import ObservabilityConfig

class Settings(BaseSettings):
    # ... existing fields ...

    # Root-level logging (for backward compatibility)
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Advanced observability settings
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
```

---
