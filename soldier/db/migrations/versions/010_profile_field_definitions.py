"""Create profile_field_definitions table.

Revision ID: 010
Revises: 009
Create Date: 2025-12-03

Table for schema-driven field definitions that define:
- What data can be collected
- How to validate it
- How to collect it (prompts)
- Privacy classification
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create profile_field_definitions table."""
    op.create_table(
        "profile_field_definitions",
        # Identity
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        # Definition
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Type and Validation
        sa.Column("value_type", sa.String(50), nullable=False),
        sa.Column("validation_regex", sa.String(500), nullable=True),
        sa.Column("validation_tool_id", sa.String(255), nullable=True),
        sa.Column("allowed_values", ARRAY(sa.Text), nullable=True),
        sa.Column(
            "validation_mode",
            sa.String(20),
            server_default="strict",
            nullable=False,
        ),
        # Collection Settings
        sa.Column("required_verification", sa.Boolean, server_default="false"),
        sa.Column("verification_methods", ARRAY(sa.Text), server_default="{}"),
        sa.Column("collection_prompt", sa.Text, nullable=True),
        sa.Column("extraction_examples", ARRAY(sa.Text), server_default="{}"),
        sa.Column("extraction_prompt_hint", sa.Text, nullable=True),
        # Privacy Classification
        sa.Column("is_pii", sa.Boolean, server_default="false"),
        sa.Column("encryption_required", sa.Boolean, server_default="false"),
        sa.Column("retention_days", sa.Integer, nullable=True),
        # Freshness
        sa.Column("freshness_seconds", sa.Integer, nullable=True),
        # Admin
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        # Constraints
        sa.UniqueConstraint(
            "tenant_id", "agent_id", "name", name="uq_field_definition"
        ),
        sa.CheckConstraint(
            "value_type IN ('string', 'email', 'phone', 'date', 'number', 'boolean', 'json')",
            name="chk_definition_value_type",
        ),
        sa.CheckConstraint(
            "validation_mode IN ('strict', 'warn', 'disabled')",
            name="chk_definition_validation_mode",
        ),
    )

    # Indexes
    op.create_index(
        "idx_field_definitions_tenant_agent",
        "profile_field_definitions",
        ["tenant_id", "agent_id"],
    )
    op.create_index(
        "idx_field_definitions_enabled",
        "profile_field_definitions",
        ["tenant_id", "agent_id", "enabled"],
    )


def downgrade() -> None:
    """Drop profile_field_definitions table."""
    op.drop_table("profile_field_definitions")
