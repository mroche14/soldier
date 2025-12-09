<a id="focal.api.dependencies"></a>

# focal.api.dependencies

Dependency injection for API routes.

Provides FastAPI dependencies for stores and providers used by API endpoints.
Dependencies are configured based on settings and can be overridden for testing.

<a id="focal.api.dependencies.get_settings"></a>

#### get\_settings

```python
@lru_cache
def get_settings() -> Settings
```

Get application settings.

Loads configuration from TOML files and environment variables.
Cached to avoid reloading on every request.

**Returns**:

  Settings object with all configuration

<a id="focal.api.dependencies.get_config_store"></a>

#### get\_config\_store

```python
def get_config_store() -> ConfigStore
```

Get the ConfigStore instance.

**Returns**:

  ConfigStore for rules, scenarios, templates, variables

<a id="focal.api.dependencies.get_session_store"></a>

#### get\_session\_store

```python
def get_session_store() -> SessionStore
```

Get the SessionStore instance.

**Returns**:

  SessionStore for session state

<a id="focal.api.dependencies.get_audit_store"></a>

#### get\_audit\_store

```python
def get_audit_store() -> AuditStore
```

Get the AuditStore instance.

**Returns**:

  AuditStore for turn records and audit events

<a id="focal.api.dependencies.get_llm_provider"></a>

#### get\_llm\_provider

```python
def get_llm_provider(
        _settings: Annotated[Settings, Depends(get_settings)]) -> LLMProvider
```

Get the LLMProvider instance.

**Arguments**:

- `_settings` - Application settings (unused, for future provider selection)
  

**Returns**:

  LLMProvider for text generation

<a id="focal.api.dependencies.get_embedding_provider"></a>

#### get\_embedding\_provider

```python
def get_embedding_provider(
    _settings: Annotated[Settings,
                         Depends(get_settings)]) -> EmbeddingProvider
```

Get the EmbeddingProvider instance.

**Arguments**:

- `settings` - Application settings
  

**Returns**:

  EmbeddingProvider for vector embeddings

<a id="focal.api.dependencies.get_alignment_engine"></a>

#### get\_alignment\_engine

```python
def get_alignment_engine(
        config_store: Annotated[ConfigStore,
                                Depends(get_config_store)],
        session_store: Annotated[SessionStore,
                                 Depends(get_session_store)],
        audit_store: Annotated[AuditStore,
                               Depends(get_audit_store)],
        llm_provider: Annotated[LLMProvider,
                                Depends(get_llm_provider)],
        embedding_provider: Annotated[EmbeddingProvider,
                                      Depends(get_embedding_provider)],
        settings: Annotated[Settings,
                            Depends(get_settings)]) -> AlignmentEngine
```

Get the AlignmentEngine instance.

Creates the alignment engine with all required dependencies.

**Arguments**:

- `config_store` - Store for configuration
- `session_store` - Store for sessions
- `audit_store` - Store for audit records
- `llm_provider` - LLM provider
- `embedding_provider` - Embedding provider
- `settings` - Application settings
  

**Returns**:

  AlignmentEngine for processing turns

<a id="focal.api.dependencies.reset_dependencies"></a>

#### reset\_dependencies

```python
def reset_dependencies() -> None
```

Reset all cached dependencies.

Used for testing to ensure fresh instances.

