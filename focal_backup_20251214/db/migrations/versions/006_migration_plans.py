"""Create migration planning tables.

Revision ID: 006
Revises: 005
Create Date: 2025-11-29

Tables: migration_plans, scenario_archives
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create migration planning tables."""
    # scenario_archives table (must be created before migration_plans for FK)
    op.create_table(
        "scenario_archives",
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("scenario_id", UUID, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("scenario_data", JSONB, nullable=False),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("tenant_id", "scenario_id", "version"),
    )

    # migration_plans table
    op.create_table(
        "migration_plans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("scenario_id", UUID, nullable=False),
        sa.Column("from_version", sa.Integer, nullable=False),
        sa.Column("to_version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="'DRAFT'", nullable=False),
        sa.Column("transformation_map", JSONB, nullable=False),
        sa.Column("anchor_policies", JSONB, server_default="{}"),
        sa.Column("scope_filter", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("deployed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'DEPLOYED', 'REJECTED')",
            name="chk_migration_status",
        ),
    )
    op.create_index(
        "idx_migration_plans_scenario",
        "migration_plans",
        ["tenant_id", "scenario_id", "from_version", "to_version"],
    )


def downgrade() -> None:
    """Drop migration planning tables."""
    op.drop_table("migration_plans")
    op.drop_table("scenario_archives")
