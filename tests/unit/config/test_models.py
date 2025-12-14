"""Unit tests for configuration Pydantic models."""

import pytest
from pydantic import ValidationError

from ruche.config.models import (
    APIConfig,
    EmbeddingProviderConfig,
    GenerationConfig,
    LLMProviderConfig,
    LoggingConfig,
    MetricsConfig,
    ObservabilityConfig,
    PipelineConfig,
    ProvidersConfig,
    RateLimitConfig,
    RerankProviderConfig,
    SelectionConfig,
    SelectionStrategiesConfig,
    StorageConfig,
    StoreBackendConfig,
    TracingConfig,
)
from ruche.config.models.pipeline import SituationSensorConfig


class TestRateLimitConfig:
    """Tests for RateLimitConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.requests_per_minute == 60
        assert config.burst_size == 10

    def test_requests_per_minute_must_be_positive(self) -> None:
        """requests_per_minute must be > 0."""
        with pytest.raises(ValidationError):
            RateLimitConfig(requests_per_minute=0)

    def test_burst_size_can_be_zero(self) -> None:
        """burst_size can be 0."""
        config = RateLimitConfig(burst_size=0)
        assert config.burst_size == 0

    def test_burst_size_cannot_be_negative(self) -> None:
        """burst_size must be >= 0."""
        with pytest.raises(ValidationError):
            RateLimitConfig(burst_size=-1)


class TestAPIConfig:
    """Tests for APIConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = APIConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.workers == 4
        assert config.cors_origins == ["*"]

    def test_port_range_lower_bound(self) -> None:
        """Port must be >= 1."""
        with pytest.raises(ValidationError):
            APIConfig(port=0)

    def test_port_range_upper_bound(self) -> None:
        """Port must be <= 65535."""
        with pytest.raises(ValidationError):
            APIConfig(port=65536)

    def test_valid_port(self) -> None:
        """Valid port is accepted."""
        config = APIConfig(port=443)
        assert config.port == 443

    def test_workers_must_be_positive(self) -> None:
        """Workers must be >= 1."""
        with pytest.raises(ValidationError):
            APIConfig(workers=0)

    def test_cors_origins_parsed_from_string(self) -> None:
        """CORS origins can be parsed from comma-separated string."""
        config = APIConfig(cors_origins="http://a.com, http://b.com")
        assert config.cors_origins == ["http://a.com", "http://b.com"]


class TestStoreBackendConfig:
    """Tests for StoreBackendConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = StoreBackendConfig()
        assert config.backend == "inmemory"
        assert config.connection_url is None
        assert config.pool_size == 10

    def test_valid_backends(self) -> None:
        """All valid backend types are accepted."""
        valid_backends = ["inmemory", "postgres", "redis", "mongodb", "neo4j", "dynamodb"]
        for backend in valid_backends:
            config = StoreBackendConfig(backend=backend)
            assert config.backend == backend

    def test_invalid_backend_rejected(self) -> None:
        """Invalid backend type is rejected."""
        with pytest.raises(ValidationError):
            StoreBackendConfig(backend="invalid")

    def test_pool_size_must_be_positive(self) -> None:
        """pool_size must be > 0."""
        with pytest.raises(ValidationError):
            StoreBackendConfig(pool_size=0)


class TestStorageConfig:
    """Tests for StorageConfig model."""

    def test_defaults(self) -> None:
        """Default storage backends are configured."""
        config = StorageConfig()
        assert config.config.backend == "postgres"
        assert config.memory.backend == "postgres"
        assert config.session.backend == "redis"
        assert config.audit.backend == "postgres"


class TestLLMProviderConfig:
    """Tests for LLMProviderConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = LLMProviderConfig(model="openrouter/anthropic/claude-3-haiku-20240307")
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 60

    def test_temperature_range_lower(self) -> None:
        """Temperature must be >= 0.0."""
        with pytest.raises(ValidationError):
            LLMProviderConfig(model="mock/test", temperature=-0.1)

    def test_temperature_range_upper(self) -> None:
        """Temperature must be <= 2.0."""
        with pytest.raises(ValidationError):
            LLMProviderConfig(model="mock/test", temperature=2.1)

    def test_valid_temperature(self) -> None:
        """Valid temperature values are accepted."""
        config = LLMProviderConfig(model="mock/test", temperature=1.5)
        assert config.temperature == 1.5

    def test_provider_detection_openrouter(self) -> None:
        """Provider is auto-detected from openrouter model string."""
        config = LLMProviderConfig(model="openrouter/anthropic/claude-3-haiku-20240307")
        assert config.get_provider_type() == "openrouter"
        assert config.get_model_for_api() == "anthropic/claude-3-haiku-20240307"

    def test_provider_detection_anthropic(self) -> None:
        """Provider is auto-detected from anthropic model string."""
        config = LLMProviderConfig(model="anthropic/claude-3-haiku-20240307")
        assert config.get_provider_type() == "anthropic"
        assert config.get_model_for_api() == "anthropic/claude-3-haiku-20240307"

    def test_provider_detection_openai(self) -> None:
        """Provider is auto-detected from openai model string."""
        config = LLMProviderConfig(model="openai/gpt-4o-mini")
        assert config.get_provider_type() == "openai"
        assert config.get_model_for_api() == "openai/gpt-4o-mini"

    def test_provider_detection_mock(self) -> None:
        """Provider is auto-detected from mock model string."""
        config = LLMProviderConfig(model="mock/test-model")
        assert config.get_provider_type() == "mock"
        assert config.get_model_for_api() == "mock/test-model"

    def test_api_key_is_secret(self) -> None:
        """API key is stored as SecretStr."""
        config = LLMProviderConfig(model="mock/test", api_key="sk-test-key")
        # SecretStr should not reveal value in string representation
        assert "sk-test-key" not in str(config.api_key)


class TestEmbeddingProviderConfig:
    """Tests for EmbeddingProviderConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = EmbeddingProviderConfig()
        assert config.provider == "openai"
        assert config.dimensions == 1536
        assert config.batch_size == 100

    def test_dimensions_must_be_positive(self) -> None:
        """dimensions must be > 0."""
        with pytest.raises(ValidationError):
            EmbeddingProviderConfig(dimensions=0)


class TestRerankProviderConfig:
    """Tests for RerankProviderConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = RerankProviderConfig()
        assert config.provider == "cohere"
        assert config.top_k == 10

    def test_top_k_must_be_positive(self) -> None:
        """top_k must be > 0."""
        with pytest.raises(ValidationError):
            RerankProviderConfig(top_k=0)


class TestProvidersConfig:
    """Tests for ProvidersConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = ProvidersConfig()
        assert config.default_embedding == "default"
        assert config.default_rerank == "default"
        assert config.embedding == {}
        assert config.rerank == {}


class TestSelectionConfig:
    """Tests for SelectionConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = SelectionConfig()
        assert config.strategy == "adaptive_k"
        assert config.min_score == 0.5
        assert config.max_k == 10

    def test_min_score_range_lower(self) -> None:
        """min_score must be >= 0.0."""
        with pytest.raises(ValidationError):
            SelectionConfig(min_score=-0.1)

    def test_min_score_range_upper(self) -> None:
        """min_score must be <= 1.0."""
        with pytest.raises(ValidationError):
            SelectionConfig(min_score=1.1)

    def test_valid_strategies(self) -> None:
        """All valid strategy types are accepted."""
        valid_strategies = ["elbow", "adaptive_k", "entropy", "clustering", "fixed_k"]
        for strategy in valid_strategies:
            config = SelectionConfig(strategy=strategy)
            assert config.strategy == strategy

    def test_max_k_must_be_positive(self) -> None:
        """max_k must be > 0."""
        with pytest.raises(ValidationError):
            SelectionConfig(max_k=0)


class TestSelectionStrategiesConfig:
    """Tests for SelectionStrategiesConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = SelectionStrategiesConfig()
        assert config.rule.strategy == "adaptive_k"
        assert config.scenario.strategy == "entropy"
        assert config.memory.strategy == "clustering"


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = PipelineConfig()
        assert config.context_extraction.enabled is True
        assert config.retrieval.enabled is True
        assert "openrouter/anthropic/claude-sonnet" in config.generation.model

    def test_step_can_be_disabled(self) -> None:
        """Pipeline steps can be disabled."""
        config = PipelineConfig(
            context_extraction={"enabled": False},
            reranking={"enabled": False},
        )
        assert config.context_extraction.enabled is False
        assert config.reranking.enabled is False

    def test_model_and_fallbacks(self) -> None:
        """Model and fallback_models can be configured."""
        config = PipelineConfig(
            generation={
                "model": "openrouter/anthropic/claude-3-opus-20240229",
                "fallback_models": ["anthropic/claude-3-opus-20240229"],
            }
        )
        assert config.generation.model == "openrouter/anthropic/claude-3-opus-20240229"
        assert len(config.generation.fallback_models) == 1


class TestGenerationConfig:
    """Tests for GenerationConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = GenerationConfig()
        assert config.enabled is True
        assert "openrouter/anthropic/claude-sonnet" in config.model
        assert config.fallback_models == []
        assert config.temperature == 0.7
        assert config.max_tokens == 1024


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.include_trace_id is True

    def test_valid_levels(self) -> None:
        """All valid log levels are accepted."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_valid_formats(self) -> None:
        """All valid formats are accepted."""
        for fmt in ["json", "console"]:
            config = LoggingConfig(format=fmt)
            assert config.format == fmt


class TestTracingConfig:
    """Tests for TracingConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = TracingConfig()
        assert config.enabled is True
        assert config.service_name == "focal"
        assert config.sample_rate == 1.0

    def test_sample_rate_range(self) -> None:
        """sample_rate must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TracingConfig(sample_rate=-0.1)
        with pytest.raises(ValidationError):
            TracingConfig(sample_rate=1.1)


class TestMetricsConfig:
    """Tests for MetricsConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.port == 9090
        assert config.path == "/metrics"

    def test_port_range(self) -> None:
        """Port must be valid."""
        with pytest.raises(ValidationError):
            MetricsConfig(port=0)
        with pytest.raises(ValidationError):
            MetricsConfig(port=65536)


class TestObservabilityConfig:
    """Tests for ObservabilityConfig model."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = ObservabilityConfig()
        assert config.logging.level == "INFO"
        assert config.tracing.enabled is True
        assert config.metrics.enabled is True


class TestSituationSensorConfig:
    """Tests for SituationSensorConfig model (Phase 2)."""

    def test_defaults(self) -> None:
        """Default values are correct."""
        config = SituationSensorConfig()
        assert config.enabled is True
        assert config.model == "openrouter/openai/gpt-oss-120b"
        assert config.fallback_models == ["anthropic/claude-3-5-haiku-20241022"]
        assert config.temperature == 0.0
        assert config.max_tokens == 800
        assert config.history_turns == 5
        assert config.include_glossary is True
        assert config.include_schema_mask is True

    def test_history_turns_must_be_non_negative(self) -> None:
        """history_turns must be >= 0."""
        with pytest.raises(ValidationError):
            SituationSensorConfig(history_turns=-1)

        # Zero is valid (no history)
        config = SituationSensorConfig(history_turns=0)
        assert config.history_turns == 0

    def test_max_tokens_must_be_positive(self) -> None:
        """max_tokens must be > 0."""
        with pytest.raises(ValidationError):
            SituationSensorConfig(max_tokens=0)

    def test_temperature_range(self) -> None:
        """temperature must be between 0 and 2."""
        with pytest.raises(ValidationError):
            SituationSensorConfig(temperature=-0.1)
        with pytest.raises(ValidationError):
            SituationSensorConfig(temperature=2.1)

        # Valid range
        config = SituationSensorConfig(temperature=0.7)
        assert config.temperature == 0.7

    def test_custom_model(self) -> None:
        """Can specify custom model."""
        config = SituationSensorConfig(model="openrouter/anthropic/claude-3-opus")
        assert config.model == "openrouter/anthropic/claude-3-opus"

    def test_disabling_features(self) -> None:
        """Can disable glossary and schema mask."""
        config = SituationSensorConfig(
            include_glossary=False,
            include_schema_mask=False,
        )
        assert config.include_glossary is False
        assert config.include_schema_mask is False

    def test_embedded_in_pipeline_config(self) -> None:
        """SituationSensorConfig is embedded in PipelineConfig."""
        pipeline = PipelineConfig()
        assert hasattr(pipeline, "situation_sensor")
        assert isinstance(pipeline.situation_sensor, SituationSensorConfig)
        assert pipeline.situation_sensor.enabled is True
