"""Enable pgvector extension.

Revision ID: 001
Revises:
Create Date: 2025-11-29
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgvector extension for vector similarity search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove pgvector extension."""
    op.execute("DROP EXTENSION IF EXISTS vector")
