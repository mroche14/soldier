"""Create sessions table for persistent session storage.

Revision ID: 017
Revises: 015
Create Date: 2025-12-16

Tables: sessions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "017"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sessions table for persistent storage.

    Stores session data as fallback/long-term storage for Redis cache.
    Redis handles hot cache (30 min TTL), PostgreSQL provides persistence.
    """
    op.create_table(
        "sessions",
        sa.Column("session_id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("user_channel_id", sa.String(255), nullable=False),
        sa.Column("customer_profile_id", UUID),
        sa.Column("config_version", sa.Integer, nullable=False),

        # Multi-scenario support
        sa.Column("active_scenarios", JSONB, server_default="[]"),

        # Legacy single-scenario fields (deprecated)
        sa.Column("active_scenario_id", UUID),
        sa.Column("active_step_id", UUID),
        sa.Column("active_scenario_version", sa.Integer),
        sa.Column("step_history", JSONB, server_default="[]"),
        sa.Column("relocalization_count", sa.Integer, server_default="0"),

        # Tracking
        sa.Column("rule_fires", JSONB, server_default="{}"),
        sa.Column("rule_last_fire_turn", JSONB, server_default="{}"),
        sa.Column("variables", JSONB, server_default="{}"),
        sa.Column("variable_updated_at", JSONB, server_default="{}"),
        sa.Column("turn_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="'active'", nullable=False),

        # Migration support
        sa.Column("pending_migration", JSONB),
        sa.Column("scenario_checksum", sa.String(64)),

        # Timestamps
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_activity_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),

        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'abandoned')",
            name="chk_sessions_status"
        ),
    )

    # Index for tenant+session lookups
    op.create_index(
        "idx_sessions_tenant_session",
        "sessions",
        ["tenant_id", "session_id"],
    )

    # Index for tenant+agent lookups
    op.create_index(
        "idx_sessions_tenant_agent",
        "sessions",
        ["tenant_id", "agent_id"],
    )

    # Index for channel-based lookups
    op.create_index(
        "idx_sessions_channel",
        "sessions",
        ["tenant_id", "channel", "user_channel_id"],
    )

    # Index for customer profile lookups
    op.create_index(
        "idx_sessions_customer",
        "sessions",
        ["tenant_id", "customer_profile_id"],
        postgresql_where=sa.text("customer_profile_id IS NOT NULL"),
    )

    # Index for last_activity_at for cleanup queries
    op.create_index(
        "idx_sessions_last_activity",
        "sessions",
        ["last_activity_at"],
    )


def downgrade() -> None:
    """Drop sessions table."""
    op.drop_table("sessions")
