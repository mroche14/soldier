<a id="focal.api.routes.health"></a>

# focal.api.routes.health

Health check and metrics endpoints.

<a id="focal.api.routes.health.health_check"></a>

#### health\_check

```python
@router.get("/health", response_model=HealthResponse)
async def health_check(_settings: SettingsDep, config_store: ConfigStoreDep,
                       session_store: SessionStoreDep,
                       audit_store: AuditStoreDep) -> HealthResponse
```

Check service health status.

Returns the overall health status of the service along with
the status of individual components.

**Arguments**:

- `_settings` - Application settings (unused, for future version info)
- `config_store` - Configuration store
- `session_store` - Session store
- `audit_store` - Audit store
  

**Returns**:

  HealthResponse with status and component health

<a id="focal.api.routes.health.get_metrics"></a>

#### get\_metrics

```python
@router.get("/metrics")
async def get_metrics() -> Response
```

Get Prometheus metrics.

Returns metrics in Prometheus text format for scraping.

**Returns**:

  Prometheus metrics as text/plain

