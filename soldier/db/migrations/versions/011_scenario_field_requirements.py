"""Create scenario_field_requirements table.

Revision ID: 011
Revises: 010
Create Date: 2025-12-03

Table for binding profile field requirements to scenarios/steps:
- Which fields are required for each scenario
- Collection order and fallback behavior
- Step-level bindings for conditional requirements
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scenario_field_requirements table."""
    op.create_table(
        "scenario_field_requirements",
        # Identity
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        # Scenario binding
        sa.Column("scenario_id", UUID, nullable=False),
        sa.Column("step_id", UUID, nullable=True),  # NULL = scenario-wide
        # Field reference
        sa.Column("field_name", sa.String(50), nullable=False),
        # Requirement settings
        sa.Column(
            "required_level",
            sa.String(20),
            server_default="hard",
            nullable=False,
        ),
        sa.Column(
            "fallback_action",
            sa.String(20),
            server_default="ask",
            nullable=False,
        ),
        sa.Column("collection_order", sa.Integer, server_default="0"),
        # Conditional requirement
        sa.Column("condition_expression", sa.Text, nullable=True),
        # Admin flags
        sa.Column("requires_human_review", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        # Constraints
        sa.CheckConstraint(
            "required_level IN ('hard', 'soft')",
            name="chk_requirement_level",
        ),
        sa.CheckConstraint(
            "fallback_action IN ('ask', 'skip', 'block', 'extract')",
            name="chk_fallback_action",
        ),
    )

    # Indexes
    op.create_index(
        "idx_scenario_requirements_scenario",
        "scenario_field_requirements",
        ["tenant_id", "scenario_id"],
    )
    op.create_index(
        "idx_scenario_requirements_step",
        "scenario_field_requirements",
        ["tenant_id", "scenario_id", "step_id"],
    )
    op.create_index(
        "idx_scenario_requirements_order",
        "scenario_field_requirements",
        ["scenario_id", "collection_order"],
    )


def downgrade() -> None:
    """Drop scenario_field_requirements table."""
    op.drop_table("scenario_field_requirements")
