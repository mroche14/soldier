<a id="focal.config.settings"></a>

# focal.config.settings

Root settings model for Focal configuration.

<a id="focal.config.settings.set_toml_config"></a>

#### set\_toml\_config

```python
def set_toml_config(config: dict[str, Any]) -> None
```

Set the TOML configuration to be used by Settings.

<a id="focal.config.settings.TomlConfigSettingsSource"></a>

## TomlConfigSettingsSource Objects

```python
class TomlConfigSettingsSource(PydanticBaseSettingsSource)
```

Custom settings source that reads from TOML configuration.

<a id="focal.config.settings.TomlConfigSettingsSource.get_field_value"></a>

#### get\_field\_value

```python
def get_field_value(field: Any, field_name: str) -> tuple[Any, str, bool]
```

Get field value from TOML config.

<a id="focal.config.settings.TomlConfigSettingsSource.__call__"></a>

#### \_\_call\_\_

```python
def __call__() -> dict[str, Any]
```

Return the TOML config values.

<a id="focal.config.settings.Settings"></a>

## Settings Objects

```python
class Settings(BaseSettings)
```

Root configuration object containing all nested configuration sections.

Configuration is loaded in this order:
1. Pydantic model defaults (in code)
2. config/default.toml (base configuration)
3. config/{FOCAL_ENV}.toml (environment overrides)
4. FOCAL_* environment variables (runtime overrides)

<a id="focal.config.settings.Settings.settings_customise_sources"></a>

#### settings\_customise\_sources

```python
@classmethod
def settings_customise_sources(
    cls, settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource
) -> tuple[PydanticBaseSettingsSource, ...]
```

Customize settings sources to include TOML config.

Priority order (highest to lowest):
1. init_settings (constructor arguments)
2. env_settings (FOCAL_* environment variables)
3. toml_settings (config/*.toml files)
4. (defaults from model)

