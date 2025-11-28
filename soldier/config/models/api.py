"""API server configuration models."""

from pydantic import BaseModel, Field, field_validator


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(default=True, description="Enable rate limiting")
    requests_per_minute: int = Field(
        default=60,
        gt=0,
        description="Max requests per minute per tenant",
    )
    burst_size: int = Field(
        default=10,
        ge=0,
        description="Burst allowance above rate limit",
    )


class APIConfig(BaseModel):
    """Configuration for the HTTP API server."""

    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8000, ge=1, le=65535, description="Port number")
    workers: int = Field(default=4, ge=1, description="Number of worker processes")
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS",
    )
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting settings",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
