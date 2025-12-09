"""Add intents table for intent catalog.

Revision ID: 012_add_intents_table
Revises: 011_add_customer_context_vault
Create Date: 2025-12-08

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012_add_intents_table"
down_revision: str | None = "011_add_customer_context_vault"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create intents table."""
    op.create_table(
        "intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "example_phrases",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
    )

    # Create indexes for efficient queries
    op.create_index(
        "ix_intents_tenant_agent",
        "intents",
        ["tenant_id", "agent_id"],
        unique=False,
    )

    op.create_index(
        "ix_intents_label",
        "intents",
        ["label"],
        unique=False,
    )

    op.create_index(
        "ix_intents_enabled",
        "intents",
        ["enabled"],
        unique=False,
    )

    # Create composite index for common query pattern
    op.create_index(
        "ix_intents_tenant_agent_enabled",
        "intents",
        ["tenant_id", "agent_id", "enabled"],
        unique=False,
    )


def downgrade() -> None:
    """Drop intents table."""
    op.drop_index("ix_intents_tenant_agent_enabled", table_name="intents")
    op.drop_index("ix_intents_enabled", table_name="intents")
    op.drop_index("ix_intents_label", table_name="intents")
    op.drop_index("ix_intents_tenant_agent", table_name="intents")
    op.drop_table("intents")
