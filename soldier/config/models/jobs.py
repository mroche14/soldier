"""Job configuration models.

Configuration for background job infrastructure.
"""

from pydantic import BaseModel, Field, SecretStr


class HatchetConfig(BaseModel):
    """Hatchet background job orchestration configuration.

    Hatchet is used for scheduled jobs like field expiry and orphan detection.
    """

    enabled: bool = Field(default=True, description="Enable Hatchet integration")
    server_url: str = Field(
        default="http://localhost:7077",
        description="Hatchet engine server URL",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="Hatchet API key (from HATCHET_API_KEY env var)",
    )
    worker_concurrency: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of concurrent job workers",
    )
    cron_expire_fields: str = Field(
        default="*/5 * * * *",
        description="Cron schedule for field expiry check (every 5 min)",
    )
    cron_detect_orphans: str = Field(
        default="*/15 * * * *",
        description="Cron schedule for orphan detection (every 15 min)",
    )
    cron_schema_extraction: str = Field(
        default="",
        description="Cron schedule for schema extraction (empty = triggered only)",
    )
    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed jobs",
    )
    retry_backoff_seconds: int = Field(
        default=60,
        ge=10,
        description="Initial backoff in seconds between retries",
    )


class JobsConfig(BaseModel):
    """Top-level jobs configuration."""

    hatchet: HatchetConfig = Field(
        default_factory=HatchetConfig,
        description="Hatchet configuration",
    )
