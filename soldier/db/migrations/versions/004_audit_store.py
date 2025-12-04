"""Create AuditStore tables.

Revision ID: 004
Revises: 003
Create Date: 2025-11-29

Tables: turn_records, audit_events
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create AuditStore tables."""
    # turn_records table
    op.create_table(
        "turn_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("turn_number", sa.Integer, nullable=False),
        sa.Column("user_message", sa.Text, nullable=False),
        sa.Column("assistant_response", sa.Text),
        sa.Column("context_extracted", JSONB),
        sa.Column("rules_matched", JSONB, server_default="[]"),
        sa.Column("scenario_state", JSONB),
        sa.Column("tools_executed", JSONB, server_default="[]"),
        sa.Column("token_usage", JSONB),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_turn_records_session", "turn_records", ["session_id"])
    op.create_index("idx_turn_records_tenant", "turn_records", ["tenant_id"])
    op.create_index(
        "idx_turn_records_created",
        "turn_records",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("session_id", UUID),
        sa.Column("turn_id", UUID, sa.ForeignKey("turn_records.id")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_events_tenant", "audit_events", ["tenant_id"])
    op.create_index(
        "idx_audit_events_session",
        "audit_events",
        ["session_id"],
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )
    op.create_index(
        "idx_audit_events_type", "audit_events", ["tenant_id", "event_type"]
    )
    op.create_index(
        "idx_audit_events_created",
        "audit_events",
        ["tenant_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Drop AuditStore tables."""
    op.drop_table("audit_events")
    op.drop_table("turn_records")
