<a id="soldier.observability.metrics"></a>

# soldier.observability.metrics

Prometheus metrics for Soldier.

Provides standard metrics for request tracking, latencies, token usage,
and system health.

<a id="soldier.observability.metrics.setup_metrics"></a>

#### setup\_metrics

```python
def setup_metrics() -> None
```

Initialize metrics configuration.

This function is called at application startup to ensure
metrics are properly configured. Currently a no-op as
prometheus_client handles registration automatically.

