"""Enable Row Level Security for tenant isolation.

Revision ID: 016
Revises: 017
Create Date: 2025-12-16

Enables PostgreSQL Row Level Security (RLS) on all tables with tenant_id.
Applies tenant_isolation policy to enforce database-level multi-tenancy.

Note: Connection must set current_tenant before queries:
    SET app.current_tenant = '<tenant_id>'
"""

from alembic import op

revision = "016"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable RLS and create tenant_isolation policies."""
    # ConfigStore tables
    _enable_rls_for_table("agents")
    _enable_rls_for_table("rules")
    _enable_rls_for_table("scenarios")
    _enable_rls_for_table("templates")
    _enable_rls_for_table("variables")
    _enable_rls_for_table("tool_activations")
    _enable_rls_for_table("glossary_items")
    _enable_rls_for_table("intents")
    _enable_rls_for_table("rule_relationships")

    # SessionStore tables
    _enable_rls_for_table("sessions")

    # AuditStore tables
    _enable_rls_for_table("turn_records")
    _enable_rls_for_table("audit_events")

    # ProfileStore tables
    _enable_rls_for_table("customer_profiles")
    _enable_rls_for_table("channel_identities")
    _enable_rls_for_table("profile_fields")
    _enable_rls_for_table("profile_assets")
    _enable_rls_for_table("profile_field_definitions")

    # MigrationStore tables
    _enable_rls_for_table("scenario_archives")
    _enable_rls_for_table("migration_plans")

    # Note: MemoryStore tables (episodes, entities, relationships) do NOT need RLS
    # because they use group_id (composite tenant_id:session_id) instead of tenant_id


def downgrade() -> None:
    """Disable RLS and drop tenant_isolation policies."""
    # ConfigStore tables
    _disable_rls_for_table("agents")
    _disable_rls_for_table("rules")
    _disable_rls_for_table("scenarios")
    _disable_rls_for_table("templates")
    _disable_rls_for_table("variables")
    _disable_rls_for_table("tool_activations")
    _disable_rls_for_table("glossary_items")
    _disable_rls_for_table("intents")
    _disable_rls_for_table("rule_relationships")

    # SessionStore tables
    _disable_rls_for_table("sessions")

    # AuditStore tables
    _disable_rls_for_table("turn_records")
    _disable_rls_for_table("audit_events")

    # ProfileStore tables
    _disable_rls_for_table("customer_profiles")
    _disable_rls_for_table("channel_identities")
    _disable_rls_for_table("profile_fields")
    _disable_rls_for_table("profile_assets")
    _disable_rls_for_table("profile_field_definitions")

    # MigrationStore tables
    _disable_rls_for_table("scenario_archives")
    _disable_rls_for_table("migration_plans")


def _enable_rls_for_table(table_name: str) -> None:
    """Enable RLS and create tenant_isolation policy for a table."""
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant')::uuid)
        """
    )


def _disable_rls_for_table(table_name: str) -> None:
    """Drop tenant_isolation policy and disable RLS for a table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
