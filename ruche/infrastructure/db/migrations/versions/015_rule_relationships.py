"""Create rule_relationships table.

Revision ID: 015
Revises: 014
Create Date: 2025-12-15

Tables: rule_relationships
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create rule_relationships table."""
    op.create_table(
        "rule_relationships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("from_rule_id", UUID, sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("to_rule_id", UUID, sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "relationship_type IN ('depends_on', 'implies', 'excludes')",
            name="chk_rule_relationships_type",
        ),
    )

    # Index for tenant_id + agent_id lookups (excluding soft-deleted)
    op.create_index(
        "idx_rule_relationships_tenant_agent",
        "rule_relationships",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Index for from_rule_id lookups (to find all relationships from a rule)
    op.create_index(
        "idx_rule_relationships_from_rule",
        "rule_relationships",
        ["tenant_id", "agent_id", "from_rule_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Index for to_rule_id lookups (to find all relationships to a rule)
    op.create_index(
        "idx_rule_relationships_to_rule",
        "rule_relationships",
        ["tenant_id", "agent_id", "to_rule_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Drop rule_relationships table."""
    op.drop_table("rule_relationships")
