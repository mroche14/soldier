"""TOML configuration loader with deep merge support."""

import os
import tomllib
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get the configuration directory path.

    The config directory can be overridden with SOLDIER_CONFIG_DIR env var.
    Defaults to 'config/' relative to the project root.
    """
    config_dir_env = os.environ.get("SOLDIER_CONFIG_DIR")
    if config_dir_env:
        path = Path(config_dir_env)
        if not path.exists():
            raise FileNotFoundError(f"Config directory not found: {config_dir_env}")
        return path

    # Default: look for config/ in current directory or parent directories
    current = Path.cwd()
    for _ in range(5):  # Look up to 5 levels
        config_path = current / "config"
        if config_path.exists():
            return config_path
        current = current.parent

    # Fallback to relative path
    return Path("config")


def get_environment() -> str:
    """Get the current environment from SOLDIER_ENV.

    Defaults to 'development' if not set.
    """
    return os.environ.get("SOLDIER_ENV", "development")


def load_toml(file_path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dictionary.

    Args:
        file_path: Path to the TOML file

    Returns:
        Dictionary containing the TOML data

    Raises:
        FileNotFoundError: If the file doesn't exist
        tomllib.TOMLDecodeError: If the TOML syntax is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with file_path.open("rb") as f:
        return tomllib.load(f)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence.

    For nested dictionaries, values are merged recursively.
    For other values, override replaces base.

    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config() -> dict[str, Any]:
    """Load configuration from TOML files.

    Loading order:
    1. config/default.toml (required)
    2. config/{SOLDIER_ENV}.toml (optional)

    Returns:
        Merged configuration dictionary
    """
    config_dir = get_config_dir()
    env = get_environment()

    # Load default config (required)
    default_path = config_dir / "default.toml"
    if not default_path.exists():
        raise FileNotFoundError(
            f"Default configuration file not found: {default_path}. "
            "Create config/default.toml or set SOLDIER_CONFIG_DIR."
        )

    config = load_toml(default_path)

    # Load environment-specific config (optional)
    env_path = config_dir / f"{env}.toml"
    if env_path.exists():
        env_config = load_toml(env_path)
        config = deep_merge(config, env_config)

    return config
