"""Root settings model for Soldier configuration."""

from typing import Any, Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from soldier.config.models.api import APIConfig
from soldier.config.models.observability import ObservabilityConfig
from soldier.config.models.pipeline import PipelineConfig
from soldier.config.models.providers import ProvidersConfig
from soldier.config.models.selection import SelectionStrategiesConfig
from soldier.config.models.storage import StorageConfig

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Module-level variable to store TOML config for settings source
_toml_config: dict[str, Any] = {}


def set_toml_config(config: dict[str, Any]) -> None:
    """Set the TOML configuration to be used by Settings."""
    global _toml_config
    _toml_config = config


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from TOML configuration."""

    def get_field_value(
        self, field: Any, field_name: str  # noqa: ARG002
    ) -> tuple[Any, str, bool]:
        """Get field value from TOML config."""
        value = _toml_config.get(field_name)
        return value, field_name, value is not None

    def __call__(self) -> dict[str, Any]:
        """Return the TOML config values."""
        return _toml_config.copy()


class Settings(BaseSettings):
    """Root configuration object containing all nested configuration sections.

    Configuration is loaded in this order:
    1. Pydantic model defaults (in code)
    2. config/default.toml (base configuration)
    3. config/{SOLDIER_ENV}.toml (environment overrides)
    4. SOLDIER_* environment variables (runtime overrides)
    """

    model_config = SettingsConfigDict(
        env_prefix="SOLDIER_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="soldier", description="Application name for logging/tracing")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: LogLevel = Field(default="INFO", description="Logging level")

    # Nested configuration sections
    api: APIConfig = Field(default_factory=APIConfig, description="API server configuration")
    storage: StorageConfig = Field(
        default_factory=StorageConfig,
        description="Storage backend configuration",
    )
    providers: ProvidersConfig = Field(
        default_factory=ProvidersConfig,
        description="AI provider configuration",
    )
    pipeline: PipelineConfig = Field(
        default_factory=PipelineConfig,
        description="Turn pipeline configuration",
    )
    selection: SelectionStrategiesConfig = Field(
        default_factory=SelectionStrategiesConfig,
        description="Selection strategy configuration",
    )
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig,
        description="Observability configuration",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include TOML config.

        Priority order (highest to lowest):
        1. init_settings (constructor arguments)
        2. env_settings (SOLDIER_* environment variables)
        3. toml_settings (config/*.toml files)
        4. (defaults from model)
        """
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )
