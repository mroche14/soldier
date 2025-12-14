"""Shared test fixtures for the Focal test suite."""

import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def test_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_toml_files(test_config_dir: Path) -> Callable[[dict[str, str]], None]:
    """Factory fixture to create TOML files in the test config directory.

    Usage:
        def test_something(mock_toml_files):
            mock_toml_files({
                "default.toml": "app_name = 'test'",
                "development.toml": "debug = true",
            })
    """

    def _create_toml_files(files: dict[str, str]) -> None:
        for filename, content in files.items():
            toml_file = test_config_dir / filename
            toml_file.write_text(content)

    return _create_toml_files


class EnvOverrideContext:
    """Context manager for temporarily setting environment variables."""

    def __init__(self, overrides: dict[str, str]) -> None:
        self.overrides = overrides
        self.original_env: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.overrides.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *args: Any) -> None:
        for key in self.overrides:
            if self.original_env[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = self.original_env[key]


@pytest.fixture
def env_override() -> Generator[Callable[[dict[str, str]], EnvOverrideContext], None, None]:
    """Context manager for temporarily setting environment variables.

    Usage:
        def test_something(env_override):
            with env_override({"RUCHE_DEBUG": "true"}):
                # test code here
    """

    def _env_override(overrides: dict[str, str]) -> EnvOverrideContext:
        return EnvOverrideContext(overrides)

    yield _env_override


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Clear the settings cache before and after each test.

    This ensures test isolation for configuration tests.
    """
    from ruche.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
