# Configuration Architecture

Soldier uses a **centralized TOML-based configuration** with **Pydantic models** for validation. No hardcoded values in code—only defaults in Pydantic models.

## Philosophy

```
Configuration lives in files, not code.
Code defines structure and defaults.
TOML files override defaults per environment.
```

---

## Folder Structure

```
soldier/
├── .env                             # Secrets (gitignored, NEVER commit)
├── .env.example                     # Template for .env (committed)
│
├── config/                          # Configuration files (per environment)
│   ├── default.toml                 # Base defaults (committed, no secrets)
│   ├── development.toml             # Local development overrides
│   ├── staging.toml                 # Staging environment
│   ├── production.toml              # Production environment
│   └── test.toml                    # Test environment
│
└── soldier/
    └── config/                      # Configuration loading code
        ├── __init__.py
        ├── loader.py                # TOML loader + .env loading
        ├── settings.py              # Root Settings class
        ├── secrets.py               # Secret provider abstraction
        │
        └── models/                  # Pydantic models for each section
            ├── __init__.py
            ├── pipeline.py          # Pipeline step configurations
            ├── providers.py         # LLM, Embedding, Rerank provider configs
            ├── storage.py           # Store backend configurations
            ├── selection.py         # Selection strategy configurations
            ├── api.py               # API server configurations
            └── agent.py             # Per-agent configurations
```

**Key principle:** Secrets (API keys, passwords) go in `.env` at project root. Non-secret configuration goes in `config/*.toml` files.

---

## Configuration Loading

### Environment Resolution

```python
# soldier/config/loader.py
import os
from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel


def get_config_path() -> Path:
    """Resolve config directory from environment or default."""
    config_dir = os.getenv("SOLDIER_CONFIG_DIR", "config")
    return Path(config_dir)


def get_environment() -> str:
    """Get current environment from SOLDIER_ENV or default to 'development'."""
    return os.getenv("SOLDIER_ENV", "development")


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file, return empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries, override takes precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    """
    Load configuration with environment-specific overrides.

    Resolution order (later overrides earlier):
    1. default.toml (base defaults)
    2. {environment}.toml (environment-specific)
    3. Environment variables (SOLDIER_*)
    """
    config_path = get_config_path()
    env = get_environment()

    # Load base defaults
    config = load_toml(config_path / "default.toml")

    # Override with environment-specific
    env_config = load_toml(config_path / f"{env}.toml")
    config = deep_merge(config, env_config)

    return config
```

### Settings Class

```python
# soldier/config/settings.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from soldier.config.loader import load_config
from soldier.config.models.api import APIConfig
from soldier.config.models.pipeline import PipelineConfig
from soldier.config.models.providers import ProvidersConfig
from soldier.config.models.storage import StorageConfig


class Settings(BaseSettings):
    """
    Root configuration for Soldier.

    All values have defaults defined here or in nested models.
    TOML files and environment variables override these defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="SOLDIER_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Application metadata
    app_name: str = Field(default="soldier", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Nested configurations
    api: APIConfig = Field(default_factory=APIConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @classmethod
    def from_toml(cls) -> "Settings":
        """Load settings from TOML files with environment overrides."""
        config_dict = load_config()
        return cls(**config_dict)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.from_toml()
```

---

