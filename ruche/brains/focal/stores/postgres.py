"""PostgreSQL implementation of AgentConfigStore.

Uses asyncpg for async database access and pgvector for
vector similarity search.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

from ruche.brains.focal.migration.models import MigrationPlan, MigrationPlanStatus
from ruche.brains.focal.models import (
    Agent,
    Intent,
    Rule,
    Scenario,
    Scope,
    Template,
    ToolActivation,
    Variable,
)
from ruche.brains.focal.stores.agent_config_store import AgentConfigStore
from ruche.infrastructure.db.errors import ConnectionError
from ruche.infrastructure.db.pool import PostgresPool
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class PostgresAgentConfigStore(AgentConfigStore):
    """PostgreSQL implementation of AgentConfigStore.

    Uses asyncpg connection pool for efficient database access
    and pgvector for vector similarity search.
    """

    def __init__(self, pool: PostgresPool) -> None:
        """Initialize with connection pool.

        Args:
            pool: PostgreSQL connection pool
        """
        self._pool = pool

    # Rule operations
    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None:
        """Get a rule by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, name, description,
                           condition_text, condition_embedding, embedding_model,
                           action_type, action_config, scope, scope_id,
                           priority, enabled, created_at, updated_at, deleted_at
                    FROM rules
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    rule_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_rule(row)
                return None
        except Exception as e:
            logger.error("postgres_get_rule_error", rule_id=str(rule_id), error=str(e))
            raise ConnectionError(f"Failed to get rule: {e}", cause=e) from e

    async def get_rules(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
        enabled_only: bool = True,
    ) -> list[Rule]:
        """Get rules for an agent with optional filtering."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, name, description,
                           condition_text, condition_embedding, embedding_model,
                           action_type, action_config, scope, scope_id,
                           priority, enabled, created_at, updated_at, deleted_at
                    FROM rules
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                """
                params: list = [tenant_id, agent_id]

                if enabled_only:
                    query += " AND enabled = true"

                if scope is not None:
                    params.append(scope.value)
                    query += f" AND scope = ${len(params)}"

                if scope_id is not None:
                    params.append(scope_id)
                    query += f" AND scope_id = ${len(params)}"

                query += " ORDER BY priority DESC, created_at DESC"

                rows = await conn.fetch(query, *params)
                return [self._row_to_rule(row) for row in rows]
        except Exception as e:
            logger.error("postgres_get_rules_error", agent_id=str(agent_id), error=str(e))
            raise ConnectionError(f"Failed to get rules: {e}", cause=e) from e

    async def save_rule(self, rule: Rule) -> UUID:
        """Save a rule, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                embedding_bytes = self._embedding_to_bytes(rule.embedding)
                # Store additional rule fields in action_config JSON
                action_config = {
                    "max_fires_per_session": rule.max_fires_per_session,
                    "cooldown_turns": rule.cooldown_turns,
                    "is_hard_constraint": rule.is_hard_constraint,
                    "attached_tool_ids": rule.attached_tool_ids,
                    "attached_template_ids": [str(t) for t in rule.attached_template_ids],
                }
                await conn.execute(
                    """
                    INSERT INTO rules (
                        id, tenant_id, agent_id, name, description,
                        condition_text, condition_embedding, embedding_model,
                        action_type, action_config, scope, scope_id,
                        priority, enabled, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        condition_text = EXCLUDED.condition_text,
                        condition_embedding = EXCLUDED.condition_embedding,
                        embedding_model = EXCLUDED.embedding_model,
                        action_type = EXCLUDED.action_type,
                        action_config = EXCLUDED.action_config,
                        scope = EXCLUDED.scope,
                        scope_id = EXCLUDED.scope_id,
                        priority = EXCLUDED.priority,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    rule.id,
                    rule.tenant_id,
                    rule.agent_id,
                    rule.name,
                    rule.description,
                    rule.condition_text,
                    embedding_bytes,
                    rule.embedding_model,
                    rule.action_text,  # Store action_text in action_type column
                    json.dumps(action_config),
                    rule.scope.value,
                    rule.scope_id,
                    rule.priority,
                    rule.enabled,
                    rule.created_at,
                    datetime.now(UTC),
                )
                logger.debug("rule_saved", rule_id=str(rule.id))
                return rule.id
        except Exception as e:
            logger.error("postgres_save_rule_error", rule_id=str(rule.id), error=str(e))
            raise ConnectionError(f"Failed to save rule: {e}", cause=e) from e

    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool:
        """Soft-delete a rule by setting deleted_at."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE rules
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    rule_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("rule_deleted", rule_id=str(rule_id))
                return deleted
        except Exception as e:
            logger.error("postgres_delete_rule_error", rule_id=str(rule_id), error=str(e))
            raise ConnectionError(f"Failed to delete rule: {e}", cause=e) from e

    async def vector_search_rules(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Rule, float]]:
        """Search rules by vector similarity using pgvector."""
        try:
            async with self._pool.acquire() as conn:
                # Convert embedding to pgvector format
                embedding_str = f"[{','.join(map(str, query_embedding))}]"

                rows = await conn.fetch(
                    """
                    SELECT id, tenant_id, agent_id, name, description,
                           condition_text, condition_embedding, embedding_model,
                           action_type, action_config, scope, scope_id,
                           priority, enabled, created_at, updated_at, deleted_at,
                           1 - (condition_embedding <=> $1::vector) AS score
                    FROM rules
                    WHERE tenant_id = $2 AND agent_id = $3
                      AND deleted_at IS NULL AND enabled = true
                      AND condition_embedding IS NOT NULL
                      AND 1 - (condition_embedding <=> $1::vector) >= $4
                    ORDER BY score DESC
                    LIMIT $5
                    """,
                    embedding_str,
                    tenant_id,
                    agent_id,
                    min_score,
                    limit,
                )
                return [(self._row_to_rule(row), row["score"]) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_vector_search_rules_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to search rules: {e}", cause=e) from e

    # Scenario operations
    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        """Get a scenario by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, name, description, version,
                           entry_condition, entry_embedding, steps, enabled,
                           created_at, updated_at, deleted_at
                    FROM scenarios
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    scenario_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_scenario(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_scenario_error", scenario_id=str(scenario_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get scenario: {e}", cause=e) from e

    async def get_scenarios(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Scenario]:
        """Get scenarios for an agent."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, name, description, version,
                           entry_condition, entry_embedding, steps, enabled,
                           created_at, updated_at, deleted_at
                    FROM scenarios
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                """
                if enabled_only:
                    query += " AND enabled = true"
                query += " ORDER BY created_at DESC"

                rows = await conn.fetch(query, tenant_id, agent_id)
                return [self._row_to_scenario(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_scenarios_error", agent_id=str(agent_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get scenarios: {e}", cause=e) from e

    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Save a scenario, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                embedding_bytes = self._embedding_to_bytes(scenario.entry_embedding)
                await conn.execute(
                    """
                    INSERT INTO scenarios (
                        id, tenant_id, agent_id, name, description, version,
                        entry_condition, entry_embedding, steps, enabled,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        version = EXCLUDED.version,
                        entry_condition = EXCLUDED.entry_condition,
                        entry_embedding = EXCLUDED.entry_embedding,
                        steps = EXCLUDED.steps,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    scenario.id,
                    scenario.tenant_id,
                    scenario.agent_id,
                    scenario.name,
                    scenario.description,
                    scenario.version,
                    scenario.entry_condition,
                    embedding_bytes,
                    json.dumps([s.model_dump(mode="json") for s in scenario.steps]),
                    scenario.enabled,
                    scenario.created_at,
                    datetime.now(UTC),
                )
                logger.debug("scenario_saved", scenario_id=str(scenario.id))
                return scenario.id
        except Exception as e:
            logger.error(
                "postgres_save_scenario_error", scenario_id=str(scenario.id), error=str(e)
            )
            raise ConnectionError(f"Failed to save scenario: {e}", cause=e) from e

    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool:
        """Soft-delete a scenario."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE scenarios
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    scenario_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("scenario_deleted", scenario_id=str(scenario_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_scenario_error",
                scenario_id=str(scenario_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete scenario: {e}", cause=e) from e

    # Template operations
    async def get_template(self, tenant_id: UUID, template_id: UUID) -> Template | None:
        """Get a template by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, name, content, mode,
                           scope, scope_id, created_at, updated_at, deleted_at
                    FROM templates
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    template_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_template(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_template_error", template_id=str(template_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get template: {e}", cause=e) from e

    async def get_templates(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
    ) -> list[Template]:
        """Get templates for an agent with optional filtering."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, name, content, mode,
                           scope, scope_id, created_at, updated_at, deleted_at
                    FROM templates
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                """
                params: list = [tenant_id, agent_id]

                if scope is not None:
                    params.append(scope.value)
                    query += f" AND scope = ${len(params)}"

                if scope_id is not None:
                    params.append(scope_id)
                    query += f" AND scope_id = ${len(params)}"

                query += " ORDER BY created_at DESC"

                rows = await conn.fetch(query, *params)
                return [self._row_to_template(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_templates_error", agent_id=str(agent_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get templates: {e}", cause=e) from e

    async def save_template(self, template: Template) -> UUID:
        """Save a template, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO templates (
                        id, tenant_id, agent_id, name, content, mode,
                        scope, scope_id, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        content = EXCLUDED.content,
                        mode = EXCLUDED.mode,
                        scope = EXCLUDED.scope,
                        scope_id = EXCLUDED.scope_id,
                        updated_at = NOW()
                    """,
                    template.id,
                    template.tenant_id,
                    template.agent_id,
                    template.name,
                    template.content,
                    template.mode.value,
                    template.scope.value,
                    template.scope_id,
                    template.created_at,
                    datetime.now(UTC),
                )
                logger.debug("template_saved", template_id=str(template.id))
                return template.id
        except Exception as e:
            logger.error(
                "postgres_save_template_error", template_id=str(template.id), error=str(e)
            )
            raise ConnectionError(f"Failed to save template: {e}", cause=e) from e

    async def delete_template(self, tenant_id: UUID, template_id: UUID) -> bool:
        """Soft-delete a template."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE templates
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    template_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("template_deleted", template_id=str(template_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_template_error",
                template_id=str(template_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete template: {e}", cause=e) from e

    # Variable operations
    async def get_variable(self, tenant_id: UUID, variable_id: UUID) -> Variable | None:
        """Get a variable by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, name, description,
                           default_value, update_policy, resolver_tool_id,
                           created_at, updated_at, deleted_at
                    FROM variables
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    variable_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_variable(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_variable_error", variable_id=str(variable_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get variable: {e}", cause=e) from e

    async def get_variables(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Variable]:
        """Get variables for an agent."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, tenant_id, agent_id, name, description,
                           default_value, update_policy, resolver_tool_id,
                           created_at, updated_at, deleted_at
                    FROM variables
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                    ORDER BY name ASC
                    """,
                    tenant_id,
                    agent_id,
                )
                return [self._row_to_variable(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_variables_error", agent_id=str(agent_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get variables: {e}", cause=e) from e

    async def get_variable_by_name(
        self, tenant_id: UUID, agent_id: UUID, name: str
    ) -> Variable | None:
        """Get a variable by name."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, name, description,
                           default_value, update_policy, resolver_tool_id,
                           created_at, updated_at, deleted_at
                    FROM variables
                    WHERE tenant_id = $1 AND agent_id = $2 AND name = $3
                      AND deleted_at IS NULL
                    """,
                    tenant_id,
                    agent_id,
                    name,
                )
                if row:
                    return self._row_to_variable(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_variable_by_name_error",
                agent_id=str(agent_id),
                name=name,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get variable: {e}", cause=e) from e

    async def save_variable(self, variable: Variable) -> UUID:
        """Save a variable, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO variables (
                        id, tenant_id, agent_id, name, description,
                        default_value, update_policy, resolver_tool_id,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        default_value = EXCLUDED.default_value,
                        update_policy = EXCLUDED.update_policy,
                        resolver_tool_id = EXCLUDED.resolver_tool_id,
                        updated_at = NOW()
                    """,
                    variable.id,
                    variable.tenant_id,
                    variable.agent_id,
                    variable.name,
                    variable.description,
                    variable.default_value,
                    variable.update_policy.value,
                    variable.resolver_tool_id,
                    variable.created_at,
                    datetime.now(UTC),
                )
                logger.debug("variable_saved", variable_id=str(variable.id))
                return variable.id
        except Exception as e:
            logger.error(
                "postgres_save_variable_error",
                variable_id=str(variable.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save variable: {e}", cause=e) from e

    async def delete_variable(self, tenant_id: UUID, variable_id: UUID) -> bool:
        """Soft-delete a variable."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE variables
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    variable_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("variable_deleted", variable_id=str(variable_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_variable_error",
                variable_id=str(variable_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete variable: {e}", cause=e) from e

    # Agent operations
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, name, description, system_prompt,
                           default_model, enabled, created_at, updated_at, deleted_at
                    FROM agents
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    agent_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_agent(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_agent_error", agent_id=str(agent_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get agent: {e}", cause=e) from e

    async def get_agents(
        self,
        tenant_id: UUID,
        *,
        enabled_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Agent], int]:
        """Get agents for a tenant with pagination."""
        try:
            async with self._pool.acquire() as conn:
                # Build query
                where_clause = "tenant_id = $1 AND deleted_at IS NULL"
                params: list = [tenant_id]

                if enabled_only:
                    where_clause += " AND enabled = true"

                # Get total count
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(*) FROM agents WHERE {where_clause}",
                    *params,
                )
                total = count_row["count"]

                # Get paginated results
                params.extend([limit, offset])
                rows = await conn.fetch(
                    f"""
                    SELECT id, tenant_id, name, description, system_prompt,
                           default_model, enabled, created_at, updated_at, deleted_at
                    FROM agents
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params) - 1} OFFSET ${len(params)}
                    """,
                    *params,
                )
                agents = [self._row_to_agent(row) for row in rows]
                return agents, total
        except Exception as e:
            logger.error(
                "postgres_get_agents_error", tenant_id=str(tenant_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get agents: {e}", cause=e) from e

    async def save_agent(self, agent: Agent) -> UUID:
        """Save an agent, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agents (
                        id, tenant_id, name, description, system_prompt,
                        default_model, enabled, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        system_prompt = EXCLUDED.system_prompt,
                        default_model = EXCLUDED.default_model,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    agent.id,
                    agent.tenant_id,
                    agent.name,
                    agent.description,
                    agent.system_prompt,
                    agent.settings.model,  # Use settings.model instead of default_model
                    agent.enabled,
                    agent.created_at,
                    datetime.now(UTC),
                )
                logger.debug("agent_saved", agent_id=str(agent.id))
                return agent.id
        except Exception as e:
            logger.error(
                "postgres_save_agent_error", agent_id=str(agent.id), error=str(e)
            )
            raise ConnectionError(f"Failed to save agent: {e}", cause=e) from e

    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        """Soft-delete an agent."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE agents
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    agent_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("agent_deleted", agent_id=str(agent_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_agent_error", agent_id=str(agent_id), error=str(e)
            )
            raise ConnectionError(f"Failed to delete agent: {e}", cause=e) from e

    # Tool activation operations
    async def get_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> ToolActivation | None:
        """Get a tool activation by agent and tool ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, tool_id, enabled,
                           policy_overrides, created_at, updated_at
                    FROM tool_activations
                    WHERE tenant_id = $1 AND agent_id = $2 AND tool_id = $3
                    """,
                    tenant_id,
                    agent_id,
                    tool_id,
                )
                if row:
                    return self._row_to_tool_activation(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_tool_activation_error",
                agent_id=str(agent_id),
                tool_id=tool_id,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get tool activation: {e}", cause=e) from e

    async def get_tool_activations(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[ToolActivation]:
        """Get all tool activations for an agent."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, tenant_id, agent_id, tool_id, enabled,
                           policy_overrides, created_at, updated_at
                    FROM tool_activations
                    WHERE tenant_id = $1 AND agent_id = $2
                    ORDER BY tool_id ASC
                    """,
                    tenant_id,
                    agent_id,
                )
                return [self._row_to_tool_activation(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_tool_activations_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get tool activations: {e}", cause=e) from e

    async def get_all_tool_activations(
        self,
        tenant_id: UUID,
    ) -> list[ToolActivation]:
        """Get all tool activations across all agents for a tenant."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, tenant_id, agent_id, tool_id, enabled,
                           policy_overrides, created_at, updated_at
                    FROM tool_activations
                    WHERE tenant_id = $1
                    ORDER BY agent_id ASC, tool_id ASC
                    """,
                    tenant_id,
                )
                return [self._row_to_tool_activation(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_all_tool_activations_error",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise ConnectionError(
                f"Failed to get all tool activations: {e}", cause=e
            ) from e

    async def save_tool_activation(self, activation: ToolActivation) -> UUID:
        """Save a tool activation, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tool_activations (
                        id, tenant_id, agent_id, tool_id, enabled,
                        policy_overrides, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (tenant_id, agent_id, tool_id) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        policy_overrides = EXCLUDED.policy_overrides,
                        updated_at = NOW()
                    """,
                    activation.id,
                    activation.tenant_id,
                    activation.agent_id,
                    activation.tool_id,
                    activation.enabled,
                    json.dumps(activation.policy_overrides),
                    activation.created_at,
                    datetime.now(UTC),
                )
                logger.debug("tool_activation_saved", activation_id=str(activation.id))
                return activation.id
        except Exception as e:
            logger.error(
                "postgres_save_tool_activation_error",
                activation_id=str(activation.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save tool activation: {e}", cause=e) from e

    async def delete_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> bool:
        """Delete a tool activation."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM tool_activations
                    WHERE tenant_id = $1 AND agent_id = $2 AND tool_id = $3
                    """,
                    tenant_id,
                    agent_id,
                    tool_id,
                )
                deleted = result == "DELETE 1"
                if deleted:
                    logger.info(
                        "tool_activation_deleted",
                        agent_id=str(agent_id),
                        tool_id=tool_id,
                    )
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_tool_activation_error",
                agent_id=str(agent_id),
                tool_id=tool_id,
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete tool activation: {e}", cause=e) from e

    # Migration plan operations
    async def get_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> MigrationPlan | None:
        """Get migration plan by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, scenario_id, from_version, to_version,
                           status, transformation_map, anchor_policies, scope_filter,
                           created_at, approved_at, deployed_at
                    FROM migration_plans
                    WHERE id = $1 AND tenant_id = $2
                    """,
                    plan_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_migration_plan(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_migration_plan_error",
                plan_id=str(plan_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get migration plan: {e}", cause=e) from e

    async def get_migration_plan_for_versions(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        from_version: int,
        to_version: int,
    ) -> MigrationPlan | None:
        """Get migration plan for specific version transition."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, scenario_id, from_version, to_version,
                           status, transformation_map, anchor_policies, scope_filter,
                           created_at, approved_at, deployed_at
                    FROM migration_plans
                    WHERE tenant_id = $1 AND scenario_id = $2
                      AND from_version = $3 AND to_version = $4
                    """,
                    tenant_id,
                    scenario_id,
                    from_version,
                    to_version,
                )
                if row:
                    return self._row_to_migration_plan(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_migration_plan_for_versions_error",
                scenario_id=str(scenario_id),
                from_version=from_version,
                to_version=to_version,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get migration plan: {e}", cause=e) from e

    async def save_migration_plan(self, plan: MigrationPlan) -> UUID:
        """Save or update migration plan."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO migration_plans (
                        id, tenant_id, scenario_id, from_version, to_version,
                        status, transformation_map, anchor_policies, scope_filter,
                        created_at, approved_at, deployed_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        transformation_map = EXCLUDED.transformation_map,
                        anchor_policies = EXCLUDED.anchor_policies,
                        scope_filter = EXCLUDED.scope_filter,
                        approved_at = EXCLUDED.approved_at,
                        deployed_at = EXCLUDED.deployed_at
                    """,
                    plan.id,
                    plan.tenant_id,
                    plan.scenario_id,
                    plan.from_version,
                    plan.to_version,
                    plan.status.value,
                    plan.transformation_map.model_dump_json(),
                    json.dumps({k: v.model_dump(mode="json") for k, v in plan.anchor_policies.items()}),
                    plan.scope_filter.model_dump_json() if plan.scope_filter else None,
                    plan.created_at,
                    plan.approved_at,
                    plan.deployed_at,
                )
                logger.debug("migration_plan_saved", plan_id=str(plan.id))
                return plan.id
        except Exception as e:
            logger.error(
                "postgres_save_migration_plan_error",
                plan_id=str(plan.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save migration plan: {e}", cause=e) from e

    async def list_migration_plans(
        self,
        tenant_id: UUID,
        scenario_id: UUID | None = None,
        status: MigrationPlanStatus | None = None,
        limit: int = 50,
    ) -> list[MigrationPlan]:
        """List migration plans for scenario."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, scenario_id, from_version, to_version,
                           status, transformation_map, anchor_policies, scope_filter,
                           created_at, approved_at, deployed_at
                    FROM migration_plans
                    WHERE tenant_id = $1
                """
                params: list = [tenant_id]

                if scenario_id is not None:
                    params.append(scenario_id)
                    query += f" AND scenario_id = ${len(params)}"

                if status is not None:
                    params.append(status.value)
                    query += f" AND status = ${len(params)}"

                params.append(limit)
                query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

                rows = await conn.fetch(query, *params)
                return [self._row_to_migration_plan(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_list_migration_plans_error",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to list migration plans: {e}", cause=e) from e

    async def delete_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> bool:
        """Delete a migration plan."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM migration_plans
                    WHERE id = $1 AND tenant_id = $2
                    """,
                    plan_id,
                    tenant_id,
                )
                deleted = result == "DELETE 1"
                if deleted:
                    logger.info("migration_plan_deleted", plan_id=str(plan_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_migration_plan_error",
                plan_id=str(plan_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete migration plan: {e}", cause=e) from e

    # Scenario version archiving
    async def archive_scenario_version(
        self, tenant_id: UUID, scenario: Scenario
    ) -> None:
        """Archive scenario version before update."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO scenario_archives (
                        tenant_id, scenario_id, version, scenario_data, archived_at
                    ) VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (tenant_id, scenario_id, version) DO NOTHING
                    """,
                    tenant_id,
                    scenario.id,
                    scenario.version,
                    scenario.model_dump_json(),
                )
                logger.debug(
                    "scenario_version_archived",
                    scenario_id=str(scenario.id),
                    version=scenario.version,
                )
        except Exception as e:
            logger.error(
                "postgres_archive_scenario_error",
                scenario_id=str(scenario.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to archive scenario: {e}", cause=e) from e

    async def get_archived_scenario(
        self, tenant_id: UUID, scenario_id: UUID, version: int
    ) -> Scenario | None:
        """Get archived scenario by version."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT scenario_data
                    FROM scenario_archives
                    WHERE tenant_id = $1 AND scenario_id = $2 AND version = $3
                    """,
                    tenant_id,
                    scenario_id,
                    version,
                )
                if row:
                    return Scenario.model_validate_json(row["scenario_data"])
                return None
        except Exception as e:
            logger.error(
                "postgres_get_archived_scenario_error",
                scenario_id=str(scenario_id),
                version=version,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get archived scenario: {e}", cause=e) from e

    # Helper methods for row conversion
    def _row_to_rule(self, row) -> Rule:
        """Convert database row to Rule model."""
        from uuid import UUID as UUIDType

        embedding = self._bytes_to_embedding(row["condition_embedding"])
        # Parse action_config for additional fields
        action_config = json.loads(row["action_config"]) if row["action_config"] else {}

        return Rule(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            description=row["description"],
            condition_text=row["condition_text"],
            embedding=embedding,
            embedding_model=row["embedding_model"],
            action_text=row["action_type"],  # action_type column stores action_text
            scope=Scope(row["scope"]),
            scope_id=row["scope_id"],
            priority=row["priority"],
            enabled=row["enabled"],
            max_fires_per_session=action_config.get("max_fires_per_session", 0),
            cooldown_turns=action_config.get("cooldown_turns", 0),
            is_hard_constraint=action_config.get("is_hard_constraint", False),
            attached_tool_ids=action_config.get("attached_tool_ids", []),
            attached_template_ids=[UUIDType(t) for t in action_config.get("attached_template_ids", [])],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_scenario(self, row) -> Scenario:
        """Convert database row to Scenario model."""
        from ruche.brains.focal.models import ScenarioStep

        steps_data = json.loads(row["steps"]) if row["steps"] else []
        steps = [ScenarioStep.model_validate(s) for s in steps_data]
        embedding = self._bytes_to_embedding(row["entry_embedding"])

        return Scenario(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
            entry_condition=row["entry_condition"],
            entry_embedding=embedding,
            steps=steps,
            enabled=row["enabled"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    def _row_to_template(self, row) -> Template:
        """Convert database row to Template model."""
        from ruche.brains.focal.models import TemplateResponseMode

        return Template(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            content=row["content"],
            mode=TemplateResponseMode(row["mode"]),
            scope=Scope(row["scope"]),
            scope_id=row["scope_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    def _row_to_variable(self, row) -> Variable:
        """Convert database row to Variable model."""
        from ruche.brains.focal.models import UpdatePolicy

        return Variable(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            description=row["description"],
            default_value=row["default_value"],
            update_policy=UpdatePolicy(row["update_policy"]),
            resolver_tool_id=row["resolver_tool_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    def _row_to_agent(self, row) -> Agent:
        """Convert database row to Agent model."""
        from ruche.brains.focal.models.agent import AgentSettings

        # Reconstruct settings from database columns
        settings = AgentSettings(
            model=row["default_model"],
        )

        return Agent(
            id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            description=row["description"],
            system_prompt=row["system_prompt"],
            enabled=row["enabled"],
            settings=settings,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row.get("deleted_at"),
        )

    def _row_to_tool_activation(self, row) -> ToolActivation:
        """Convert database row to ToolActivation model."""
        return ToolActivation(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            tool_id=row["tool_id"],
            enabled=row["enabled"],
            policy_overrides=json.loads(row["policy_overrides"]) if row["policy_overrides"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_migration_plan(self, row) -> MigrationPlan:
        """Convert database row to MigrationPlan model."""
        from ruche.brains.focal.migration.models import (
            AnchorMigrationPolicy,
            ScopeFilter,
            TransformationMap,
        )

        transformation_map = TransformationMap.model_validate_json(row["transformation_map"])
        anchor_policies_data = json.loads(row["anchor_policies"]) if row["anchor_policies"] else {}
        anchor_policies = {
            k: AnchorMigrationPolicy.model_validate(v)
            for k, v in anchor_policies_data.items()
        }
        scope_filter = None
        if row["scope_filter"]:
            scope_filter = ScopeFilter.model_validate_json(row["scope_filter"])

        return MigrationPlan(
            id=row["id"],
            tenant_id=row["tenant_id"],
            scenario_id=row["scenario_id"],
            from_version=row["from_version"],
            to_version=row["to_version"],
            status=MigrationPlanStatus(row["status"]),
            transformation_map=transformation_map,
            anchor_policies=anchor_policies,
            scope_filter=scope_filter,
            created_at=row["created_at"],
            approved_at=row["approved_at"],
            deployed_at=row["deployed_at"],
        )

    def _embedding_to_bytes(self, embedding: list[float] | None) -> str | None:
        """Convert embedding list to pgvector string format."""
        if embedding is None:
            return None
        return f"[{','.join(map(str, embedding))}]"

    def _bytes_to_embedding(self, data: str | None) -> list[float] | None:
        """Convert pgvector string to embedding list."""
        if data is None:
            return None
        # pgvector returns string like "[0.1,0.2,...]"
        clean = data.strip("[]")
        if not clean:
            return None
        return [float(x) for x in clean.split(",")]

    def _row_to_intent(self, row) -> Intent:
        """Convert database row to Intent model."""
        return Intent(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["label"],
            description=row["description"],
            example_phrases=row["examples"] if row["examples"] else [],
            embedding=None,
            embedding_model=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            enabled=row["enabled"],
        )

    def _row_to_rule_relationship(self, row):
        """Convert database row to RuleRelationship model."""
        from ruche.brains.focal.models import RuleRelationship, RuleRelationshipKind

        return RuleRelationship(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            source_rule_id=row["from_rule_id"],
            target_rule_id=row["to_rule_id"],
            kind=RuleRelationshipKind(row["relationship_type"]),
            created_at=row["created_at"],
            deleted_at=row["deleted_at"],
        )

    def _row_to_glossary_item(self, row):
        """Convert database row to GlossaryItem model."""
        from ruche.brains.focal.models import GlossaryItem

        return GlossaryItem(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            term=row["term"],
            definition=row["definition"],
            usage_hint=row["usage_hint"],
            aliases=row["aliases"] if row["aliases"] else [],
            category=row["category"],
            priority=row["priority"],
            enabled=row["enabled"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_interlocutor_data_field(self, row):
        """Convert database row to InterlocutorDataField model."""
        from ruche.domain.interlocutor.models import InterlocutorDataField, ValidationMode

        return InterlocutorDataField(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row["description"],
            value_type=row["value_type"],
            validation_regex=row["validation_regex"],
            validation_tool_id=row["validation_tool_id"],
            allowed_values=row["allowed_values"],
            validation_mode=ValidationMode(row["validation_mode"]),
            required_verification=row["required_verification"],
            verification_methods=row["verification_methods"] if row["verification_methods"] else [],
            collection_prompt=row["collection_prompt"],
            extraction_examples=row["extraction_examples"] if row["extraction_examples"] else [],
            extraction_prompt_hint=row["extraction_prompt_hint"],
            is_pii=row["is_pii"],
            encryption_required=row["encryption_required"],
            retention_days=row["retention_days"],
            freshness_seconds=row["freshness_seconds"],
            enabled=row["enabled"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # Intent operations (Phase 4)
    async def get_intent(self, tenant_id: UUID, intent_id: UUID) -> Intent | None:
        """Get an intent by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, agent_id, label, description,
                           examples, enabled, created_at, updated_at, deleted_at
                    FROM intents
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    intent_id,
                    tenant_id,
                )
                if row:
                    return self._row_to_intent(row)
                return None
        except Exception as e:
            logger.error("postgres_get_intent_error", intent_id=str(intent_id), error=str(e))
            raise ConnectionError(f"Failed to get intent: {e}", cause=e) from e

    async def get_intents(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Intent]:
        """Get all intents for an agent."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, label, description,
                           examples, enabled, created_at, updated_at, deleted_at
                    FROM intents
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                """
                if enabled_only:
                    query += " AND enabled = true"
                query += " ORDER BY label ASC"

                rows = await conn.fetch(query, tenant_id, agent_id)
                return [self._row_to_intent(row) for row in rows]
        except Exception as e:
            logger.error("postgres_get_intents_error", agent_id=str(agent_id), error=str(e))
            raise ConnectionError(f"Failed to get intents: {e}", cause=e) from e

    async def save_intent(self, intent: Intent) -> UUID:
        """Save an intent, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO intents (
                        id, tenant_id, agent_id, label, description,
                        examples, enabled, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        label = EXCLUDED.label,
                        description = EXCLUDED.description,
                        examples = EXCLUDED.examples,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    intent.id,
                    intent.tenant_id,
                    intent.agent_id,
                    intent.name,
                    intent.description,
                    intent.example_phrases,
                    intent.enabled,
                    intent.created_at,
                    datetime.now(UTC),
                )
                logger.debug("intent_saved", intent_id=str(intent.id))
                return intent.id
        except Exception as e:
            logger.error("postgres_save_intent_error", intent_id=str(intent.id), error=str(e))
            raise ConnectionError(f"Failed to save intent: {e}", cause=e) from e

    async def delete_intent(self, tenant_id: UUID, intent_id: UUID) -> bool:
        """Soft-delete an intent."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE intents
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    intent_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("intent_deleted", intent_id=str(intent_id))
                return deleted
        except Exception as e:
            logger.error("postgres_delete_intent_error", intent_id=str(intent_id), error=str(e))
            raise ConnectionError(f"Failed to delete intent: {e}", cause=e) from e

    # Rule relationship operations
    async def get_rule_relationships(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        rule_ids: list[UUID] | None = None,
    ) -> list:
        """Get rule relationships, optionally filtered by rule IDs."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, from_rule_id, to_rule_id,
                           relationship_type, created_at, deleted_at
                    FROM rule_relationships
                    WHERE tenant_id = $1 AND agent_id = $2 AND deleted_at IS NULL
                """
                params: list = [tenant_id, agent_id]

                if rule_ids:
                    params.append(rule_ids)
                    query += f" AND (from_rule_id = ANY(${len(params)}) OR to_rule_id = ANY(${len(params)}))"

                query += " ORDER BY created_at DESC"

                rows = await conn.fetch(query, *params)
                return [self._row_to_rule_relationship(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_rule_relationships_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get rule relationships: {e}", cause=e) from e

    async def save_rule_relationship(self, relationship) -> UUID:
        """Save a rule relationship, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO rule_relationships (
                        id, tenant_id, agent_id, from_rule_id, to_rule_id,
                        relationship_type, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        from_rule_id = EXCLUDED.from_rule_id,
                        to_rule_id = EXCLUDED.to_rule_id,
                        relationship_type = EXCLUDED.relationship_type
                    """,
                    relationship.id,
                    relationship.tenant_id,
                    relationship.agent_id,
                    relationship.source_rule_id,
                    relationship.target_rule_id,
                    relationship.kind.value,
                    relationship.created_at,
                )
                logger.debug("rule_relationship_saved", relationship_id=str(relationship.id))
                return relationship.id
        except Exception as e:
            logger.error(
                "postgres_save_rule_relationship_error",
                relationship_id=str(relationship.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save rule relationship: {e}", cause=e) from e

    async def delete_rule_relationship(
        self,
        tenant_id: UUID,
        relationship_id: UUID,
    ) -> bool:
        """Soft-delete a rule relationship."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE rule_relationships
                    SET deleted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
                    """,
                    relationship_id,
                    tenant_id,
                )
                deleted = result == "UPDATE 1"
                if deleted:
                    logger.info("rule_relationship_deleted", relationship_id=str(relationship_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_rule_relationship_error",
                relationship_id=str(relationship_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete rule relationship: {e}", cause=e) from e

    # Glossary operations (Phase 1)
    async def get_glossary_items(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list:
        """Get all glossary items for an agent."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, term, definition,
                           usage_hint, aliases, category, priority, enabled,
                           created_at, updated_at
                    FROM glossary_items
                    WHERE tenant_id = $1 AND agent_id = $2
                """
                if enabled_only:
                    query += " AND enabled = true"
                query += " ORDER BY priority DESC, term ASC"

                rows = await conn.fetch(query, tenant_id, agent_id)
                return [self._row_to_glossary_item(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_glossary_items_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get glossary items: {e}", cause=e) from e

    async def save_glossary_item(self, item) -> UUID:
        """Save a glossary item, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO glossary_items (
                        id, tenant_id, agent_id, term, definition,
                        usage_hint, aliases, category, priority, enabled,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (id) DO UPDATE SET
                        term = EXCLUDED.term,
                        definition = EXCLUDED.definition,
                        usage_hint = EXCLUDED.usage_hint,
                        aliases = EXCLUDED.aliases,
                        category = EXCLUDED.category,
                        priority = EXCLUDED.priority,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    item.id,
                    item.tenant_id,
                    item.agent_id,
                    item.term,
                    item.definition,
                    item.usage_hint,
                    item.aliases,
                    item.category,
                    item.priority,
                    item.enabled,
                    item.created_at,
                    datetime.now(UTC),
                )
                logger.debug("glossary_item_saved", glossary_item_id=str(item.id))
                return item.id
        except Exception as e:
            logger.error(
                "postgres_save_glossary_item_error",
                glossary_item_id=str(item.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save glossary item: {e}", cause=e) from e

    # Interlocutor data field operations (Phase 1)
    async def get_interlocutor_data_fields(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list:
        """Get all interlocutor data field definitions for an agent."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, tenant_id, agent_id, name, display_name, description,
                           value_type, validation_regex, validation_tool_id,
                           allowed_values, validation_mode, required_verification,
                           verification_methods, collection_prompt, extraction_examples,
                           extraction_prompt_hint, is_pii, encryption_required,
                           retention_days, freshness_seconds, enabled,
                           created_at, updated_at
                    FROM profile_field_definitions
                    WHERE tenant_id = $1 AND agent_id = $2
                """
                if enabled_only:
                    query += " AND enabled = true"
                query += " ORDER BY name ASC"

                rows = await conn.fetch(query, tenant_id, agent_id)
                return [self._row_to_interlocutor_data_field(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_interlocutor_data_fields_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get interlocutor data fields: {e}", cause=e) from e

    async def save_interlocutor_data_field(self, field) -> UUID:
        """Save an interlocutor data field definition, returning its ID."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO profile_field_definitions (
                        id, tenant_id, agent_id, name, display_name, description,
                        value_type, validation_regex, validation_tool_id,
                        allowed_values, validation_mode, required_verification,
                        verification_methods, collection_prompt, extraction_examples,
                        extraction_prompt_hint, is_pii, encryption_required,
                        retention_days, freshness_seconds, enabled,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
                    ON CONFLICT (tenant_id, agent_id, name) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        value_type = EXCLUDED.value_type,
                        validation_regex = EXCLUDED.validation_regex,
                        validation_tool_id = EXCLUDED.validation_tool_id,
                        allowed_values = EXCLUDED.allowed_values,
                        validation_mode = EXCLUDED.validation_mode,
                        required_verification = EXCLUDED.required_verification,
                        verification_methods = EXCLUDED.verification_methods,
                        collection_prompt = EXCLUDED.collection_prompt,
                        extraction_examples = EXCLUDED.extraction_examples,
                        extraction_prompt_hint = EXCLUDED.extraction_prompt_hint,
                        is_pii = EXCLUDED.is_pii,
                        encryption_required = EXCLUDED.encryption_required,
                        retention_days = EXCLUDED.retention_days,
                        freshness_seconds = EXCLUDED.freshness_seconds,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    field.id,
                    field.tenant_id,
                    field.agent_id,
                    field.name,
                    field.display_name,
                    field.description,
                    field.value_type,
                    field.validation_regex,
                    field.validation_tool_id,
                    field.allowed_values,
                    field.validation_mode.value,
                    field.required_verification,
                    field.verification_methods,
                    field.collection_prompt,
                    field.extraction_examples,
                    field.extraction_prompt_hint,
                    field.is_pii,
                    field.encryption_required,
                    field.retention_days,
                    field.freshness_seconds,
                    field.enabled,
                    field.created_at,
                    datetime.now(UTC),
                )
                logger.debug("interlocutor_data_field_saved", field_id=str(field.id))
                return field.id
        except Exception as e:
            logger.error(
                "postgres_save_interlocutor_data_field_error",
                field_id=str(field.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to save interlocutor data field: {e}", cause=e) from e

    # Legacy method name for backwards compatibility
    async def get_customer_data_fields(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list:
        """Get all customer data field definitions for an agent.

        DEPRECATED: Use get_interlocutor_data_fields instead.
        """
        return await self.get_interlocutor_data_fields(tenant_id, agent_id, enabled_only=enabled_only)

    async def save_customer_data_field(self, field) -> UUID:
        """Save a customer data field definition.

        DEPRECATED: Use save_interlocutor_data_field instead.
        """
        return await self.save_interlocutor_data_field(field)
