"""Create MemoryStore tables.

Revision ID: 003
Revises: 002
Create Date: 2025-11-29

Tables: episodes, entities, relationships
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create MemoryStore tables."""
    # episodes table
    op.create_table(
        "episodes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("customer_profile_id", UUID),
        sa.Column("session_id", UUID),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.LargeBinary),  # vector stored as bytes
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("episode_type", sa.String(50), nullable=False),
        sa.Column("importance", sa.Float, server_default="0.5"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("group_id", UUID),
        sa.CheckConstraint(
            "episode_type IN ('TURN', 'SUMMARY', 'FACT', 'EVENT')",
            name="chk_episodes_type",
        ),
    )
    op.create_index("idx_episodes_tenant_agent", "episodes", ["tenant_id", "agent_id"])
    op.create_index(
        "idx_episodes_customer",
        "episodes",
        ["tenant_id", "customer_profile_id"],
        postgresql_where=sa.text("customer_profile_id IS NOT NULL"),
    )
    op.create_index(
        "idx_episodes_session",
        "episodes",
        ["session_id"],
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )
    op.create_index(
        "idx_episodes_group",
        "episodes",
        ["group_id"],
        postgresql_where=sa.text("group_id IS NOT NULL"),
    )
    op.create_index("idx_episodes_valid", "episodes", ["valid_from", "valid_to"])

    # entities table
    op.create_table(
        "entities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("customer_profile_id", UUID),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("canonical_name", sa.String(500)),
        sa.Column("attributes", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_entities_tenant_agent", "entities", ["tenant_id", "agent_id"])
    op.create_index("idx_entities_name", "entities", ["tenant_id", "name"])
    op.create_index("idx_entities_type", "entities", ["tenant_id", "entity_type"])

    # relationships table
    op.create_table(
        "relationships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("source_entity_id", UUID, sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("target_entity_id", UUID, sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            "valid_from",
            name="uq_relationships",
        ),
    )
    op.create_index("idx_relationships_source", "relationships", ["source_entity_id"])
    op.create_index("idx_relationships_target", "relationships", ["target_entity_id"])
    op.create_index(
        "idx_relationships_type", "relationships", ["tenant_id", "relationship_type"]
    )


def downgrade() -> None:
    """Drop MemoryStore tables."""
    op.drop_table("relationships")
    op.drop_table("entities")
    op.drop_table("episodes")
