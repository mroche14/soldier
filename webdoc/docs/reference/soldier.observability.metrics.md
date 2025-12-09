<a id="focal.observability.metrics"></a>

# focal.observability.metrics

Prometheus metrics for Focal.

Provides standard metrics for request tracking, latencies, token usage,
and system health.

<a id="focal.observability.metrics.setup_metrics"></a>

#### setup\_metrics

```python
def setup_metrics() -> None
```

Initialize metrics configuration.

This function is called at application startup to ensure
metrics are properly configured. Currently a no-op as
prometheus_client handles registration automatically.

