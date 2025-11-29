"""Migration configuration models.

Defines configuration for scenario migration behavior loaded from TOML.
"""

from pydantic import BaseModel, Field


class DeploymentConfig(BaseModel):
    """Deployment phase configuration."""

    auto_mark_sessions: bool = Field(
        default=True, description="Auto-mark sessions during deployment"
    )
    require_approval: bool = Field(
        default=True, description="Require operator approval"
    )


class GapFillConfig(BaseModel):
    """Gap fill configuration."""

    extraction_enabled: bool = Field(
        default=True, description="Enable LLM extraction"
    )
    extraction_confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Min confidence to use"
    )
    confirmation_threshold: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Threshold for no confirmation"
    )
    max_conversation_turns: int = Field(
        default=20, ge=1, description="Max turns to analyze"
    )


class ReRoutingConfig(BaseModel):
    """Re-routing configuration."""

    enabled: bool = Field(default=True, description="Enable re-routing")
    notify_user: bool = Field(default=True, description="Notify user of redirect")
    notification_template: str = Field(
        default="I have new instructions. Let me redirect our conversation.",
        description="User notification message",
    )


class CheckpointConfig(BaseModel):
    """Checkpoint handling configuration."""

    block_teleport_past_checkpoint: bool = Field(
        default=True, description="Block teleport past checkpoints"
    )
    log_checkpoint_blocks: bool = Field(
        default=True, description="Log checkpoint blocks"
    )


class RetentionConfig(BaseModel):
    """Retention configuration."""

    version_retention_days: int = Field(
        default=7, ge=1, description="Days to retain archived versions"
    )
    plan_retention_days: int = Field(
        default=30, ge=1, description="Days to retain migration plans"
    )


class MigrationLoggingConfig(BaseModel):
    """Migration logging configuration."""

    log_clean_grafts: bool = Field(
        default=False, description="Log clean graft migrations"
    )
    log_gap_fills: bool = Field(default=True, description="Log gap fill migrations")
    log_re_routes: bool = Field(default=True, description="Log re-route migrations")
    log_checkpoint_blocks: bool = Field(
        default=True, description="Log checkpoint blocks"
    )


class ScenarioMigrationConfig(BaseModel):
    """Root migration configuration."""

    enabled: bool = Field(default=True, description="Enable migration system")
    deployment: DeploymentConfig = Field(
        default_factory=DeploymentConfig, description="Deployment settings"
    )
    gap_fill: GapFillConfig = Field(
        default_factory=GapFillConfig, description="Gap fill settings"
    )
    re_routing: ReRoutingConfig = Field(
        default_factory=ReRoutingConfig, description="Re-routing settings"
    )
    checkpoints: CheckpointConfig = Field(
        default_factory=CheckpointConfig, description="Checkpoint settings"
    )
    retention: RetentionConfig = Field(
        default_factory=RetentionConfig, description="Retention settings"
    )
    logging: MigrationLoggingConfig = Field(
        default_factory=MigrationLoggingConfig, description="Logging settings"
    )
