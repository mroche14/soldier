"""Create ProfileStore tables.

Revision ID: 005
Revises: 004
Create Date: 2025-11-29

Tables: customer_profiles, channel_identities, profile_fields, profile_assets
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create ProfileStore tables."""
    # customer_profiles table
    op.create_table(
        "customer_profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("merged_into_id", UUID, sa.ForeignKey("customer_profiles.id")),
    )
    op.create_index("idx_profiles_tenant", "customer_profiles", ["tenant_id"])
    # Partial unique index for tenant_id + external_id (only when external_id is set)
    op.execute(
        "CREATE UNIQUE INDEX uq_profiles_external "
        "ON customer_profiles (tenant_id, external_id) WHERE external_id IS NOT NULL"
    )

    # channel_identities table
    op.create_table(
        "channel_identities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column(
            "profile_id", UUID, sa.ForeignKey("customer_profiles.id"), nullable=False
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("channel_user_id", sa.String(255), nullable=False),
        sa.Column("verified", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "tenant_id", "channel", "channel_user_id", name="uq_channel_identity"
        ),
    )
    op.create_index("idx_channel_identities_profile", "channel_identities", ["profile_id"])
    op.create_index(
        "idx_channel_identities_lookup",
        "channel_identities",
        ["tenant_id", "channel", "channel_user_id"],
    )

    # profile_fields table
    op.create_table(
        "profile_fields",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column(
            "profile_id", UUID, sa.ForeignKey("customer_profiles.id"), nullable=False
        ),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("field_value", sa.Text),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("verified", sa.Boolean, server_default="false"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "source IN ('USER_PROVIDED', 'EXTRACTED', 'INFERRED', 'SYSTEM')",
            name="chk_field_source",
        ),
    )
    op.create_index("idx_profile_fields_profile", "profile_fields", ["profile_id"])
    op.create_index(
        "idx_profile_fields_name",
        "profile_fields",
        ["tenant_id", "profile_id", "field_name"],
    )

    # profile_assets table
    op.create_table(
        "profile_assets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column(
            "profile_id", UUID, sa.ForeignKey("customer_profiles.id"), nullable=False
        ),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("asset_reference", sa.String(500), nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_profile_assets_profile", "profile_assets", ["profile_id"])
    op.create_index(
        "idx_profile_assets_type",
        "profile_assets",
        ["tenant_id", "profile_id", "asset_type"],
    )


def downgrade() -> None:
    """Drop ProfileStore tables."""
    op.drop_table("profile_assets")
    op.drop_table("profile_fields")
    op.drop_table("channel_identities")
    op.drop_table("customer_profiles")
