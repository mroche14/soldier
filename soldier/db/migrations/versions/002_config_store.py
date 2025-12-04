"""Create ConfigStore tables.

Revision ID: 002
Revises: 001
Create Date: 2025-11-29

Tables: agents, rules, scenarios, templates, variables, tool_activations
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create ConfigStore tables."""
    # agents table
    op.create_table(
        "agents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("system_prompt", sa.Text),
        sa.Column("default_model", sa.String(100)),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "idx_agents_tenant",
        "agents",
        ["tenant_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Partial unique index for tenant_id + name (only for non-deleted)
    op.execute(
        "CREATE UNIQUE INDEX uq_agents_tenant_name "
        "ON agents (tenant_id, name) WHERE deleted_at IS NULL"
    )

    # rules table
    op.create_table(
        "rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("condition_text", sa.Text, nullable=False),
        sa.Column("condition_embedding", sa.LargeBinary),  # vector stored as bytes
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_config", JSONB, server_default="{}"),
        sa.Column("scope", sa.String(20), server_default="'GLOBAL'", nullable=False),
        sa.Column("scope_id", UUID),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("scope IN ('GLOBAL', 'SCENARIO', 'STEP')", name="chk_rules_scope"),
    )
    op.create_index(
        "idx_rules_tenant_agent",
        "rules",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_rules_scope",
        "rules",
        ["tenant_id", "agent_id", "scope", "scope_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # scenarios table
    op.create_table(
        "scenarios",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("entry_condition", sa.Text),
        sa.Column("entry_embedding", sa.LargeBinary),  # vector stored as bytes
        sa.Column("steps", JSONB, server_default="[]"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index(
        "idx_scenarios_tenant_agent",
        "scenarios",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # templates table
    op.create_table(
        "templates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("mode", sa.String(20), server_default="'SUGGEST'", nullable=False),
        sa.Column("scope", sa.String(20), server_default="'GLOBAL'", nullable=False),
        sa.Column("scope_id", UUID),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("mode IN ('SUGGEST', 'EXCLUSIVE', 'FALLBACK')", name="chk_templates_mode"),
        sa.CheckConstraint("scope IN ('GLOBAL', 'SCENARIO', 'STEP')", name="chk_templates_scope"),
    )
    op.create_index(
        "idx_templates_tenant_agent",
        "templates",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # variables table
    op.create_table(
        "variables",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("default_value", sa.Text),
        sa.Column("update_policy", sa.String(30), server_default="'REPLACE'"),
        sa.Column("resolver_tool_id", sa.String(255)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "update_policy IN ('REPLACE', 'APPEND', 'MERGE')",
            name="chk_variables_policy",
        ),
    )
    op.create_index(
        "idx_variables_tenant_agent",
        "variables",
        ["tenant_id", "agent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Partial unique index for tenant_id + agent_id + name (only for non-deleted)
    op.execute(
        "CREATE UNIQUE INDEX uq_variables_tenant_agent_name "
        "ON variables (tenant_id, agent_id, name) WHERE deleted_at IS NULL"
    )

    # tool_activations table
    op.create_table(
        "tool_activations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("tool_id", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("policy_overrides", JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "agent_id", "tool_id", name="uq_tool_activations"),
    )
    op.create_index(
        "idx_tool_activations_tenant_agent",
        "tool_activations",
        ["tenant_id", "agent_id"],
    )


def downgrade() -> None:
    """Drop ConfigStore tables."""
    op.drop_table("tool_activations")
    op.drop_table("variables")
    op.drop_table("templates")
    op.drop_table("scenarios")
    op.drop_table("rules")
    op.drop_table("agents")
