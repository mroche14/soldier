"""Unit tests for TOML configuration loader."""

import tomllib
from pathlib import Path

import pytest

from focal.config.loader import (
    deep_merge,
    get_config_dir,
    get_environment,
    load_config,
    load_toml,
)


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_merge_flat_dicts(self) -> None:
        """Flat dictionaries are merged correctly."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_dicts(self) -> None:
        """Nested dictionaries are merged recursively."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_override_replaces_non_dict(self) -> None:
        """Non-dict values in override replace base values."""
        base = {"a": {"x": 1}}
        override = {"a": "replaced"}
        result = deep_merge(base, override)
        assert result == {"a": "replaced"}

    def test_base_unmodified(self) -> None:
        """Original base dictionary is not modified."""
        base = {"a": 1}
        override = {"b": 2}
        deep_merge(base, override)
        assert base == {"a": 1}

    def test_empty_override(self) -> None:
        """Empty override returns copy of base."""
        base = {"a": 1, "b": 2}
        result = deep_merge(base, {})
        assert result == base

    def test_empty_base(self) -> None:
        """Empty base returns copy of override."""
        override = {"a": 1, "b": 2}
        result = deep_merge({}, override)
        assert result == override


class TestLoadToml:
    """Tests for load_toml function."""

    def test_load_valid_toml(self, tmp_path: Path) -> None:
        """Valid TOML file is loaded correctly."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[section]\nkey = "value"\nnumber = 42')

        result = load_toml(toml_file)
        assert result == {"section": {"key": "value", "number": 42}}

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            load_toml(missing)

    def test_load_invalid_toml_raises(self, tmp_path: Path) -> None:
        """Invalid TOML syntax raises error."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text("invalid = [unclosed")

        with pytest.raises(tomllib.TOMLDecodeError):
            load_toml(invalid_file)


class TestGetEnvironment:
    """Tests for get_environment function."""

    def test_returns_env_var_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns FOCAL_ENV value when set."""
        monkeypatch.setenv("FOCAL_ENV", "production")
        assert get_environment() == "production"

    def test_defaults_to_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Defaults to 'development' when FOCAL_ENV not set."""
        monkeypatch.delenv("FOCAL_ENV", raising=False)
        assert get_environment() == "development"


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_uses_env_var_when_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uses FOCAL_CONFIG_DIR when set."""
        config_dir = tmp_path / "custom_config"
        config_dir.mkdir()
        monkeypatch.setenv("FOCAL_CONFIG_DIR", str(config_dir))

        result = get_config_dir()
        assert result == config_dir

    def test_raises_for_missing_env_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises error when FOCAL_CONFIG_DIR doesn't exist."""
        monkeypatch.setenv("FOCAL_CONFIG_DIR", str(tmp_path / "missing"))

        with pytest.raises(FileNotFoundError):
            get_config_dir()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_default_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loads default.toml configuration."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_toml = config_dir / "default.toml"
        default_toml.write_text("app_name = 'test'\ndebug = false")

        monkeypatch.setenv("FOCAL_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("FOCAL_ENV", "nonexistent")

        result = load_config()
        assert result == {"app_name": "test", "debug": False}

    def test_merges_environment_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment config overrides default config."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        default_toml = config_dir / "default.toml"
        default_toml.write_text("app_name = 'test'\ndebug = false")

        dev_toml = config_dir / "development.toml"
        dev_toml.write_text("debug = true")

        monkeypatch.setenv("FOCAL_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("FOCAL_ENV", "development")

        result = load_config()
        assert result == {"app_name": "test", "debug": True}

    def test_missing_default_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing default.toml raises error."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setenv("FOCAL_CONFIG_DIR", str(config_dir))

        with pytest.raises(FileNotFoundError, match="default.toml"):
            load_config()
