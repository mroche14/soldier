"""Create intents table.

Revision ID: 014
Revises: 013
Create Date: 2025-12-15

Tables: intents
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create intents table."""
    op.create_table(
        "intents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("examples", sa.ARRAY(sa.Text)),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )

    # Index for tenant_id + agent_id lookups (excluding soft-deleted)
    op.create_index(
        "idx_intents_tenant_agent",
        "intents",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Index for label lookups
    op.create_index(
        "idx_intents_label",
        "intents",
        ["tenant_id", "agent_id", "label"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Drop intents table."""
    op.drop_table("intents")
