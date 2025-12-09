<a id="focal.config.models.api"></a>

# focal.config.models.api

API server configuration models.

<a id="focal.config.models.api.RateLimitConfig"></a>

## RateLimitConfig Objects

```python
class RateLimitConfig(BaseModel)
```

Rate limiting configuration.

<a id="focal.config.models.api.APIConfig"></a>

## APIConfig Objects

```python
class APIConfig(BaseModel)
```

Configuration for the HTTP API server.

<a id="focal.config.models.api.APIConfig.parse_cors_origins"></a>

#### parse\_cors\_origins

```python
@field_validator("cors_origins", mode="before")
@classmethod
def parse_cors_origins(cls, v: str | list[str]) -> list[str]
```

Parse CORS origins from string or list.

