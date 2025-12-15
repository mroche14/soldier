"""Create vector indexes for embeddings.

Revision ID: 007
Revises: 006
Create Date: 2025-11-29

This migration adds IVFFlat indexes for pgvector similarity search
on embedding columns. Must be run after data is loaded for optimal
index performance (IVFFlat builds lists based on existing data).
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create vector indexes.

    Note: For IVFFlat indexes to work properly, there should be
    some data in the tables. For production, consider:
    1. Loading initial data
    2. Running this migration
    3. REINDEX CONCURRENTLY if needed after more data
    """
    # Convert embedding columns from bytea to vector type
    # bytea cannot be directly cast to vector, so we drop and recreate
    # This is safe since these columns should be empty in a fresh database

    # rules.condition_embedding - 1536 dimensions (OpenAI ada-002 compatible)
    op.execute("ALTER TABLE rules DROP COLUMN IF EXISTS condition_embedding")
    op.execute("ALTER TABLE rules ADD COLUMN condition_embedding vector(1536)")
    op.execute(
        """
        CREATE INDEX idx_rules_embedding ON rules
        USING ivfflat (condition_embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE condition_embedding IS NOT NULL AND deleted_at IS NULL
        """
    )

    # scenarios.entry_embedding - 1536 dimensions
    op.execute("ALTER TABLE scenarios DROP COLUMN IF EXISTS entry_embedding")
    op.execute("ALTER TABLE scenarios ADD COLUMN entry_embedding vector(1536)")
    op.execute(
        """
        CREATE INDEX idx_scenarios_entry_embedding ON scenarios
        USING ivfflat (entry_embedding vector_cosine_ops)
        WITH (lists = 50)
        WHERE entry_embedding IS NOT NULL AND deleted_at IS NULL
        """
    )

    # episodes.embedding - 1536 dimensions
    op.execute("ALTER TABLE episodes DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE episodes ADD COLUMN embedding vector(1536)")
    op.execute(
        """
        CREATE INDEX idx_episodes_embedding ON episodes
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop vector indexes and revert column types."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_episodes_embedding")
    op.execute("DROP INDEX IF EXISTS idx_scenarios_entry_embedding")
    op.execute("DROP INDEX IF EXISTS idx_rules_embedding")

    # Revert column types to bytea (LargeBinary)
    op.execute(
        "ALTER TABLE episodes ALTER COLUMN embedding TYPE bytea "
        "USING embedding::text::bytea"
    )
    op.execute(
        "ALTER TABLE scenarios ALTER COLUMN entry_embedding TYPE bytea "
        "USING entry_embedding::text::bytea"
    )
    op.execute(
        "ALTER TABLE rules ALTER COLUMN condition_embedding TYPE bytea "
        "USING condition_embedding::text::bytea"
    )
