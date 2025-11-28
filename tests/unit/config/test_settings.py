"""Unit tests for Settings class and get_settings function."""

from pathlib import Path

import pytest

from soldier.config import get_settings, reload_settings
from soldier.config.settings import Settings


class TestSettings:
    """Tests for Settings model."""

    def test_default_values(self) -> None:
        """Settings has sensible defaults."""
        settings = Settings()
        assert settings.app_name == "soldier"
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_nested_defaults(self) -> None:
        """Nested configuration has defaults."""
        settings = Settings()
        assert settings.api.port == 8000
        assert settings.api.workers == 4
        assert settings.api.rate_limit.enabled is True

    def test_storage_defaults(self) -> None:
        """Storage configuration has defaults."""
        settings = Settings()
        assert settings.storage.config.backend == "postgres"
        assert settings.storage.session.backend == "redis"

    def test_provider_defaults(self) -> None:
        """Provider configuration has defaults."""
        settings = Settings()
        assert settings.providers.default_llm == "haiku"

    def test_pipeline_defaults(self) -> None:
        """Pipeline configuration has defaults."""
        settings = Settings()
        assert settings.pipeline.context_extraction.enabled is True
        assert settings.pipeline.generation.llm_provider == "sonnet"

    def test_observability_defaults(self) -> None:
        """Observability configuration has defaults."""
        settings = Settings()
        assert settings.observability.logging.level == "INFO"
        assert settings.observability.tracing.enabled is True


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_settings returns a Settings instance."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("app_name = 'test'")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")

        # Clear any cached settings
        get_settings.cache_clear()

        settings = get_settings()
        assert isinstance(settings, Settings)
        assert settings.app_name == "test"

    def test_settings_cached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_settings returns cached instance."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("app_name = 'cached'")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")

        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings_clears_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """reload_settings returns fresh instance."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("app_name = 'original'")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")

        get_settings.cache_clear()
        settings1 = get_settings()
        assert settings1.app_name == "original"

        # Update config file
        default_toml.write_text("app_name = 'updated'")

        # Reload should get new value
        settings2 = reload_settings()
        assert settings2.app_name == "updated"


class TestEnvironmentVariableOverrides:
    """Tests for environment variable configuration overrides."""

    def test_top_level_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Top-level values can be overridden with env vars."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("debug = false")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")
        monkeypatch.setenv("SOLDIER_DEBUG", "true")

        get_settings.cache_clear()
        settings = get_settings()
        assert settings.debug is True

    def test_nested_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nested values can be overridden with double underscore."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("[api]\nport = 8000")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")
        monkeypatch.setenv("SOLDIER_API__PORT", "9000")

        get_settings.cache_clear()
        settings = get_settings()
        assert settings.api.port == 9000

    def test_deeply_nested_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deeply nested values can be overridden."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("[api.rate_limit]\nenabled = true")

        monkeypatch.setenv("SOLDIER_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SOLDIER_ENV", "nonexistent")
        monkeypatch.setenv("SOLDIER_API__RATE_LIMIT__ENABLED", "false")

        get_settings.cache_clear()
        settings = get_settings()
        assert settings.api.rate_limit.enabled is False
