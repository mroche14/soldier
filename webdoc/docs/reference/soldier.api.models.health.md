<a id="soldier.api.models.health"></a>

# soldier.api.models.health

Health check response models.

<a id="soldier.api.models.health.ComponentHealth"></a>

## ComponentHealth Objects

```python
class ComponentHealth(BaseModel)
```

Health status of a single component.

<a id="soldier.api.models.health.ComponentHealth.name"></a>

#### name

Component name.

<a id="soldier.api.models.health.ComponentHealth.status"></a>

#### status

Component status.

<a id="soldier.api.models.health.ComponentHealth.latency_ms"></a>

#### latency\_ms

Time taken to check this component in milliseconds.

<a id="soldier.api.models.health.ComponentHealth.message"></a>

#### message

Optional status message or error description.

<a id="soldier.api.models.health.HealthResponse"></a>

## HealthResponse Objects

```python
class HealthResponse(BaseModel)
```

Overall health status response for GET /health.

<a id="soldier.api.models.health.HealthResponse.status"></a>

#### status

Overall service status.

<a id="soldier.api.models.health.HealthResponse.version"></a>

#### version

Service version.

<a id="soldier.api.models.health.HealthResponse.components"></a>

#### components

Health status of individual components.

<a id="soldier.api.models.health.HealthResponse.timestamp"></a>

#### timestamp

When this health check was performed.

