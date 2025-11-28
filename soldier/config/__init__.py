"""Configuration loading for Soldier.

This module provides the central configuration system for Soldier.
Configuration is loaded from TOML files with environment variable overrides.

Usage:
    from soldier.config import get_settings

    settings = get_settings()
    port = settings.api.port
    debug = settings.debug
"""

from functools import lru_cache

from soldier.config.loader import load_config
from soldier.config.settings import Settings, set_toml_config


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton settings instance.

    Configuration is loaded in this order:
    1. Pydantic model defaults (in code)
    2. config/default.toml (base configuration)
    3. config/{SOLDIER_ENV}.toml (environment overrides)
    4. SOLDIER_* environment variables (runtime overrides)

    The result is cached for the lifetime of the process.
    Call `get_settings.cache_clear()` to reload configuration.

    Returns:
        Settings instance with all configuration loaded and validated
    """
    # Load TOML configuration and set it for the custom source
    config_dict = load_config()
    set_toml_config(config_dict)

    # Create settings - pydantic-settings will use env vars with higher priority
    return Settings()


def reload_settings() -> Settings:
    """Clear the settings cache and reload configuration.

    Useful for testing or when configuration files have changed.

    Returns:
        Fresh Settings instance
    """
    get_settings.cache_clear()
    return get_settings()


__all__ = ["get_settings", "reload_settings", "Settings"]
