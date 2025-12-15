"""Add lineage and status columns to profile_fields.

Revision ID: 008
Revises: 007
Create Date: 2025-12-03

Adds:
- status: active/superseded/expired/orphaned
- source_item_id: for lineage tracking
- source_item_type: type of source item
- source_metadata: JSON for derivation details
- superseded_by_id: link to replacing field
- superseded_at: when superseded
- field_definition_id: link to schema definition
- expires_at: for automatic expiry
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add lineage and status columns to profile_fields."""
    # Add status column with default 'active'
    op.add_column(
        "profile_fields",
        sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "chk_field_status",
        "profile_fields",
        "status IN ('active', 'superseded', 'expired', 'orphaned')",
    )

    # Lineage columns
    op.add_column(
        "profile_fields",
        sa.Column("source_item_id", UUID, nullable=True),
    )
    op.add_column(
        "profile_fields",
        sa.Column("source_item_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "profile_fields",
        sa.Column("source_metadata", JSONB, server_default="{}", nullable=False),
    )

    # Supersession columns
    op.add_column(
        "profile_fields",
        sa.Column(
            "superseded_by_id",
            UUID,
            sa.ForeignKey("profile_fields.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "profile_fields",
        sa.Column("superseded_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Schema link
    op.add_column(
        "profile_fields",
        sa.Column("field_definition_id", UUID, nullable=True),
    )

    # Expiry column
    op.add_column(
        "profile_fields",
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Update source check constraint to include new values
    op.drop_constraint("chk_field_source", "profile_fields", type_="check")
    op.create_check_constraint(
        "chk_field_source",
        "profile_fields",
        "source IN ('user_provided', 'llm_extracted', 'tool_result', "
        "'document_extracted', 'human_entered', 'system_inferred', "
        "'USER_PROVIDED', 'EXTRACTED', 'INFERRED', 'SYSTEM')",
    )

    # Indexes for efficient queries
    op.create_index(
        "idx_profile_fields_status",
        "profile_fields",
        ["tenant_id", "profile_id", "status"],
    )
    op.create_index(
        "idx_profile_fields_source_item",
        "profile_fields",
        ["source_item_id"],
        postgresql_where=sa.text("source_item_id IS NOT NULL"),
    )
    op.create_index(
        "idx_profile_fields_expires_at",
        "profile_fields",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL AND status = 'active'"),
    )


def downgrade() -> None:
    """Remove lineage and status columns from profile_fields."""
    # Drop indexes
    op.drop_index("idx_profile_fields_expires_at")
    op.drop_index("idx_profile_fields_source_item")
    op.drop_index("idx_profile_fields_status")

    # Restore original source constraint
    op.drop_constraint("chk_field_source", "profile_fields", type_="check")
    op.create_check_constraint(
        "chk_field_source",
        "profile_fields",
        "source IN ('USER_PROVIDED', 'EXTRACTED', 'INFERRED', 'SYSTEM')",
    )

    # Drop columns
    op.drop_column("profile_fields", "expires_at")
    op.drop_column("profile_fields", "field_definition_id")
    op.drop_column("profile_fields", "superseded_at")
    op.drop_column("profile_fields", "superseded_by_id")
    op.drop_column("profile_fields", "source_metadata")
    op.drop_column("profile_fields", "source_item_type")
    op.drop_column("profile_fields", "source_item_id")

    # Drop status constraint and column
    op.drop_constraint("chk_field_status", "profile_fields", type_="check")
    op.drop_column("profile_fields", "status")
