<a id="soldier.config.loader"></a>

# soldier.config.loader

TOML configuration loader with deep merge support.

<a id="soldier.config.loader.get_config_dir"></a>

#### get\_config\_dir

```python
def get_config_dir() -> Path
```

Get the configuration directory path.

The config directory can be overridden with SOLDIER_CONFIG_DIR env var.
Defaults to 'config/' relative to the project root.

<a id="soldier.config.loader.get_environment"></a>

#### get\_environment

```python
def get_environment() -> str
```

Get the current environment from SOLDIER_ENV.

Defaults to 'development' if not set.

<a id="soldier.config.loader.load_toml"></a>

#### load\_toml

```python
def load_toml(file_path: Path) -> dict[str, Any]
```

Load a TOML file and return its contents as a dictionary.

**Arguments**:

- `file_path` - Path to the TOML file
  

**Returns**:

  Dictionary containing the TOML data
  

**Raises**:

- `FileNotFoundError` - If the file doesn't exist
- `tomllib.TOMLDecodeError` - If the TOML syntax is invalid

<a id="soldier.config.loader.deep_merge"></a>

#### deep\_merge

```python
def deep_merge(base: dict[str, Any], override: dict[str,
                                                    Any]) -> dict[str, Any]
```

Deep merge two dictionaries, with override taking precedence.

For nested dictionaries, values are merged recursively.
For other values, override replaces base.

**Arguments**:

- `base` - Base dictionary
- `override` - Override dictionary (takes precedence)
  

**Returns**:

  Merged dictionary

<a id="soldier.config.loader.load_config"></a>

#### load\_config

```python
def load_config() -> dict[str, Any]
```

Load configuration from TOML files.

Loading order:
1. config/default.toml (required)
2. config/{SOLDIER_ENV}.toml (optional)

**Returns**:

  Merged configuration dictionary

