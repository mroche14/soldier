"""Fix memory store tables to match Episode/Entity/Relationship models.

Revision ID: 012
Revises: 011
Create Date: 2025-12-09

The original migration 003 had schema mismatches with the models.
This migration drops and recreates all memory tables with correct schemas:

Episodes:
- content_type instead of episode_type
- group_id as primary grouping (composite: tenant_id:session_id)
- source, source_metadata, entity_ids columns
- occurred_at instead of valid_from/valid_to
- embedding as TEXT (pgvector string format)

Entities:
- group_id instead of tenant_id/agent_id/customer_profile_id
- valid_from, valid_to, recorded_at columns
- embedding as TEXT (pgvector string format)

Relationships:
- group_id instead of tenant_id
- from_entity_id, to_entity_id instead of source_entity_id, target_entity_id
- relation_type instead of relationship_type
- attributes instead of metadata
- valid_from, valid_to, recorded_at columns
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Recreate memory store tables with correct schemas."""
    # Drop old tables (they had wrong schemas)
    # Must drop in order: relationships -> entities -> episodes (FK constraints)
    op.drop_table("relationships")
    op.drop_table("entities")
    op.drop_table("episodes")

    # Create episodes with correct schema
    op.create_table(
        "episodes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("group_id", sa.String(200), nullable=False),  # tenant_id:session_id composite
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False, server_default="message"),
        sa.Column("source", sa.String(50), nullable=False),  # user, agent, system, external
        sa.Column("source_metadata", JSONB, server_default="{}"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("entity_ids", sa.ARRAY(sa.Text), server_default="{}"),  # array of UUID strings
        sa.CheckConstraint(
            "content_type IN ('message', 'event', 'document', 'summary', 'meta_summary')",
            name="chk_episodes_content_type",
        ),
        sa.CheckConstraint(
            "source IN ('user', 'agent', 'system', 'external')",
            name="chk_episodes_source",
        ),
    )
    # Add embedding column as vector type (using raw SQL for pgvector)
    op.execute("ALTER TABLE episodes ADD COLUMN embedding vector(1536)")
    op.create_index("idx_episodes_group_id", "episodes", ["group_id"])
    op.create_index("idx_episodes_occurred", "episodes", ["group_id", "occurred_at"])
    op.create_index("idx_episodes_content_type", "episodes", ["group_id", "content_type"])
    # Create IVFFlat index for vector similarity search
    op.execute(
        """
        CREATE INDEX idx_episodes_embedding ON episodes
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )

    # Create entities with correct schema
    op.create_table(
        "entities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("group_id", sa.String(200), nullable=False),  # tenant_id:session_id composite
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("attributes", JSONB, server_default="{}"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    # Add embedding column as vector type
    op.execute("ALTER TABLE entities ADD COLUMN embedding vector(1536)")
    op.create_index("idx_entities_group_id", "entities", ["group_id"])
    op.create_index("idx_entities_name", "entities", ["group_id", "name"])
    op.create_index("idx_entities_type", "entities", ["group_id", "entity_type"])

    # Create relationships with correct schema
    op.create_table(
        "relationships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("group_id", sa.String(200), nullable=False),  # tenant_id:session_id composite
        sa.Column("from_entity_id", UUID, nullable=False),
        sa.Column("to_entity_id", UUID, nullable=False),
        sa.Column("relation_type", sa.String(100), nullable=False),
        sa.Column("attributes", JSONB, server_default="{}"),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_relationships_group_id", "relationships", ["group_id"])
    op.create_index("idx_relationships_from", "relationships", ["from_entity_id"])
    op.create_index("idx_relationships_to", "relationships", ["to_entity_id"])
    op.create_index("idx_relationships_type", "relationships", ["group_id", "relation_type"])


def downgrade() -> None:
    """Restore original memory store tables schema (migration 003)."""
    # Drop new tables
    op.drop_table("relationships")
    op.drop_table("entities")
    op.drop_table("episodes")

    # Recreate original episodes schema from migration 003
    op.create_table(
        "episodes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("customer_profile_id", UUID),
        sa.Column("session_id", UUID),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.LargeBinary),
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

    # Recreate original entities schema from migration 003
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

    # Recreate original relationships schema from migration 003
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
