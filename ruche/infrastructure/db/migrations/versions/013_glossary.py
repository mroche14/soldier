"""Create glossary_items table.

Revision ID: 013
Revises: 012
Create Date: 2025-12-15

Tables: glossary_items
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create glossary_items table."""
    op.create_table(
        "glossary_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("definition", sa.Text, nullable=False),
        sa.Column("usage_hint", sa.Text),
        sa.Column("aliases", sa.ARRAY(sa.Text)),
        sa.Column("category", sa.String(100)),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    # Index for tenant_id + agent_id lookups
    op.create_index(
        "idx_glossary_items_tenant_agent",
        "glossary_items",
        ["tenant_id", "agent_id"],
    )

    # Index for term searches
    op.create_index(
        "idx_glossary_items_term",
        "glossary_items",
        ["tenant_id", "agent_id", "term"],
    )


def downgrade() -> None:
    """Drop glossary_items table."""
    op.drop_table("glossary_items")
