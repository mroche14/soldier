"""Observability configuration models."""

from typing import Literal

from pydantic import BaseModel, Field

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = Field(default="INFO", description="Log level")
    format: LogFormat = Field(default="json", description="Output format")
    include_trace_id: bool = Field(
        default=True,
        description="Include trace ID in logs",
    )


class TracingConfig(BaseModel):
    """Distributed tracing configuration."""

    enabled: bool = Field(default=True, description="Enable tracing")
    service_name: str = Field(default="focal", description="Service name for traces")
    otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP exporter endpoint",
    )
    sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sample rate",
    )


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = Field(default=True, description="Enable metrics")
    port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Metrics server port",
    )
    path: str = Field(default="/metrics", description="Metrics endpoint path")


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging settings",
    )
    tracing: TracingConfig = Field(
        default_factory=TracingConfig,
        description="Tracing settings",
    )
    metrics: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics settings",
    )
