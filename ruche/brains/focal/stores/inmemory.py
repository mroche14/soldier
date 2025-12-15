"""In-memory implementation of AgentConfigStore."""

from datetime import UTC, datetime
from uuid import UUID

from ruche.brains.focal.migration.models import MigrationPlan, MigrationPlanStatus
from ruche.brains.focal.models import (
    Agent,
    GlossaryItem,
    Intent,
    Rule,
    RuleRelationship,
    Scenario,
    Scope,
    Template,
    ToolActivation,
    Variable,
)
from ruche.brains.focal.stores.agent_config_store import AgentConfigStore
from ruche.interlocutor_data import InterlocutorDataField
from ruche.utils.vector import cosine_similarity


class InMemoryAgentConfigStore(AgentConfigStore):
    """In-memory implementation of AgentConfigStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._rules: dict[UUID, Rule] = {}
        self._rule_relationships: dict[UUID, RuleRelationship] = {}
        self._scenarios: dict[UUID, Scenario] = {}
        self._templates: dict[UUID, Template] = {}
        self._variables: dict[UUID, Variable] = {}
        self._agents: dict[UUID, Agent] = {}
        self._tool_activations: dict[tuple[UUID, UUID, str], ToolActivation] = {}
        self._migration_plans: dict[UUID, MigrationPlan] = {}
        self._archived_scenarios: dict[tuple[UUID, UUID, int], Scenario] = {}
        self._glossary_items: dict[UUID, GlossaryItem] = {}
        self._customer_data_fields: dict[UUID, InterlocutorDataField] = {}
        self._intents: dict[UUID, Intent] = {}

    # Rule operations
    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None:
        """Get a rule by ID."""
        rule = self._rules.get(rule_id)
        if rule and rule.tenant_id == tenant_id and not rule.is_deleted:
            return rule
        return None

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
        results = []
        for rule in self._rules.values():
            if rule.tenant_id != tenant_id:
                continue
            if rule.agent_id != agent_id:
                continue
            if rule.is_deleted:
                continue
            if enabled_only and not rule.enabled:
                continue
            if scope is not None and rule.scope != scope:
                continue
            if scope_id is not None and rule.scope_id != scope_id:
                continue
            results.append(rule)
        return results

    async def save_rule(self, rule: Rule) -> UUID:
        """Save a rule, returning its ID."""
        self._rules[rule.id] = rule
        return rule.id

    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool:
        """Soft-delete a rule by setting deleted_at."""
        rule = self._rules.get(rule_id)
        if rule and rule.tenant_id == tenant_id and not rule.is_deleted:
            rule.deleted_at = datetime.now(UTC)
            return True
        return False

    async def vector_search_rules(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Rule, float]]:
        """Search rules by vector similarity."""
        results: list[tuple[Rule, float]] = []

        for rule in self._rules.values():
            if rule.tenant_id != tenant_id:
                continue
            if rule.agent_id != agent_id:
                continue
            if rule.is_deleted:
                continue
            if not rule.enabled:
                continue
            if rule.embedding is None:
                continue

            score = cosine_similarity(query_embedding, rule.embedding)
            if score >= min_score:
                results.append((rule, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # Rule relationship operations
    async def get_rule_relationships(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        rule_ids: list[UUID] | None = None,
    ) -> list[RuleRelationship]:
        """Get rule relationships, optionally filtered by rule IDs."""
        results = []
        for rel in self._rule_relationships.values():
            if rel.tenant_id != tenant_id:
                continue
            if rel.agent_id != agent_id:
                continue
            if rel.is_deleted:
                continue
            if rule_ids and rel.source_rule_id not in rule_ids and rel.target_rule_id not in rule_ids:
                continue
            results.append(rel)
        return results

    async def save_rule_relationship(
        self,
        relationship: RuleRelationship,
    ) -> UUID:
        """Save a rule relationship, returning its ID."""
        if relationship.id not in self._rule_relationships:
            relationship.created_at = datetime.now(UTC)
        relationship.updated_at = datetime.now(UTC)
        self._rule_relationships[relationship.id] = relationship
        return relationship.id

    async def delete_rule_relationship(
        self,
        tenant_id: UUID,
        relationship_id: UUID,
    ) -> bool:
        """Soft-delete a rule relationship."""
        rel = self._rule_relationships.get(relationship_id)
        if rel and rel.tenant_id == tenant_id and not rel.is_deleted:
            rel.deleted_at = datetime.now(UTC)
            return True
        return False

    # Scenario operations
    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        """Get a scenario by ID."""
        scenario = self._scenarios.get(scenario_id)
        if scenario and scenario.tenant_id == tenant_id and not scenario.is_deleted:
            return scenario
        return None

    async def get_scenarios(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Scenario]:
        """Get scenarios for an agent."""
        results = []
        for scenario in self._scenarios.values():
            if scenario.tenant_id != tenant_id:
                continue
            if scenario.agent_id != agent_id:
                continue
            if scenario.is_deleted:
                continue
            if enabled_only and not scenario.enabled:
                continue
            results.append(scenario)
        return results

    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Save a scenario, returning its ID."""
        self._scenarios[scenario.id] = scenario
        return scenario.id

    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool:
        """Soft-delete a scenario."""
        scenario = self._scenarios.get(scenario_id)
        if scenario and scenario.tenant_id == tenant_id and not scenario.is_deleted:
            scenario.deleted_at = datetime.now(UTC)
            return True
        return False

    # Template operations
    async def get_template(self, tenant_id: UUID, template_id: UUID) -> Template | None:
        """Get a template by ID."""
        template = self._templates.get(template_id)
        if template and template.tenant_id == tenant_id and not template.is_deleted:
            return template
        return None

    async def get_templates(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
    ) -> list[Template]:
        """Get templates for an agent with optional filtering."""
        results = []
        for template in self._templates.values():
            if template.tenant_id != tenant_id:
                continue
            if template.agent_id != agent_id:
                continue
            if template.is_deleted:
                continue
            if scope is not None and template.scope != scope:
                continue
            if scope_id is not None and template.scope_id != scope_id:
                continue
            results.append(template)
        return results

    async def save_template(self, template: Template) -> UUID:
        """Save a template, returning its ID."""
        self._templates[template.id] = template
        return template.id

    async def delete_template(self, tenant_id: UUID, template_id: UUID) -> bool:
        """Soft-delete a template."""
        template = self._templates.get(template_id)
        if template and template.tenant_id == tenant_id and not template.is_deleted:
            template.deleted_at = datetime.now(UTC)
            return True
        return False

    # Variable operations
    async def get_variable(self, tenant_id: UUID, variable_id: UUID) -> Variable | None:
        """Get a variable by ID."""
        variable = self._variables.get(variable_id)
        if variable and variable.tenant_id == tenant_id and not variable.is_deleted:
            return variable
        return None

    async def get_variables(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Variable]:
        """Get variables for an agent."""
        results = []
        for variable in self._variables.values():
            if variable.tenant_id != tenant_id:
                continue
            if variable.agent_id != agent_id:
                continue
            if variable.is_deleted:
                continue
            results.append(variable)
        return results

    async def get_variable_by_name(
        self, tenant_id: UUID, agent_id: UUID, name: str
    ) -> Variable | None:
        """Get a variable by name."""
        for variable in self._variables.values():
            if variable.tenant_id != tenant_id:
                continue
            if variable.agent_id != agent_id:
                continue
            if variable.is_deleted:
                continue
            if variable.name == name:
                return variable
        return None

    async def save_variable(self, variable: Variable) -> UUID:
        """Save a variable, returning its ID."""
        self._variables[variable.id] = variable
        return variable.id

    async def delete_variable(self, tenant_id: UUID, variable_id: UUID) -> bool:
        """Soft-delete a variable."""
        variable = self._variables.get(variable_id)
        if variable and variable.tenant_id == tenant_id and not variable.is_deleted:
            variable.deleted_at = datetime.now(UTC)
            return True
        return False

    # Agent operations
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        agent = self._agents.get(agent_id)
        if agent and agent.tenant_id == tenant_id and not agent.is_deleted:
            return agent
        return None

    async def get_agents(
        self,
        tenant_id: UUID,
        *,
        enabled_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Agent], int]:
        """Get agents for a tenant with pagination."""
        results = []
        for agent in self._agents.values():
            if agent.tenant_id != tenant_id:
                continue
            if agent.is_deleted:
                continue
            if enabled_only and not agent.enabled:
                continue
            results.append(agent)

        # Sort by created_at descending (newest first)
        results.sort(key=lambda a: a.created_at, reverse=True)

        total = len(results)
        paginated = results[offset : offset + limit]
        return paginated, total

    async def save_agent(self, agent: Agent) -> UUID:
        """Save an agent, returning its ID."""
        self._agents[agent.id] = agent
        return agent.id

    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        """Soft-delete an agent."""
        agent = self._agents.get(agent_id)
        if agent and agent.tenant_id == tenant_id and not agent.is_deleted:
            agent.deleted_at = datetime.now(UTC)
            return True
        return False

    # Tool activation operations
    async def get_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> ToolActivation | None:
        """Get a tool activation by agent and tool ID."""
        key = (tenant_id, agent_id, tool_id)
        return self._tool_activations.get(key)

    async def get_tool_activations(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[ToolActivation]:
        """Get all tool activations for an agent."""
        results = []
        for key, activation in self._tool_activations.items():
            if key[0] == tenant_id and key[1] == agent_id:
                results.append(activation)
        return results

    async def get_all_tool_activations(
        self,
        tenant_id: UUID,
    ) -> list[ToolActivation]:
        """Get all tool activations across all agents for a tenant."""
        results = []
        for key, activation in self._tool_activations.items():
            if key[0] == tenant_id:
                results.append(activation)
        return results

    async def save_tool_activation(self, activation: ToolActivation) -> UUID:
        """Save a tool activation, returning its ID."""
        key = (activation.tenant_id, activation.agent_id, activation.tool_id)
        self._tool_activations[key] = activation
        return activation.id

    async def delete_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> bool:
        """Delete a tool activation."""
        key = (tenant_id, agent_id, tool_id)
        if key in self._tool_activations:
            del self._tool_activations[key]
            return True
        return False

    # Migration plan operations
    async def get_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> MigrationPlan | None:
        """Get migration plan by ID."""
        plan = self._migration_plans.get(plan_id)
        if plan and plan.tenant_id == tenant_id:
            return plan
        return None

    async def get_migration_plan_for_versions(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        from_version: int,
        to_version: int,
    ) -> MigrationPlan | None:
        """Get migration plan for specific version transition."""
        for plan in self._migration_plans.values():
            if plan.tenant_id != tenant_id:
                continue
            if plan.scenario_id != scenario_id:
                continue
            if plan.from_version != from_version:
                continue
            if plan.to_version != to_version:
                continue
            return plan
        return None

    async def save_migration_plan(self, plan: MigrationPlan) -> UUID:
        """Save or update migration plan."""
        self._migration_plans[plan.id] = plan
        return plan.id

    async def list_migration_plans(
        self,
        tenant_id: UUID,
        scenario_id: UUID | None = None,
        status: MigrationPlanStatus | None = None,
        limit: int = 50,
    ) -> list[MigrationPlan]:
        """List migration plans for scenario."""
        results = []
        for plan in self._migration_plans.values():
            if plan.tenant_id != tenant_id:
                continue
            if scenario_id is not None and plan.scenario_id != scenario_id:
                continue
            if status is not None and plan.status != status:
                continue
            results.append(plan)

        # Sort by created_at descending
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results[:limit]

    async def delete_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> bool:
        """Delete a migration plan."""
        plan = self._migration_plans.get(plan_id)
        if plan and plan.tenant_id == tenant_id:
            del self._migration_plans[plan_id]
            return True
        return False

    # Scenario version archiving
    async def archive_scenario_version(
        self, tenant_id: UUID, scenario: Scenario
    ) -> None:
        """Archive scenario version before update."""
        key = (tenant_id, scenario.id, scenario.version)
        self._archived_scenarios[key] = scenario.model_copy(deep=True)

    async def get_archived_scenario(
        self, tenant_id: UUID, scenario_id: UUID, version: int
    ) -> Scenario | None:
        """Get archived scenario by version."""
        key = (tenant_id, scenario_id, version)
        return self._archived_scenarios.get(key)

    # Glossary operations
    async def get_glossary_items(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        enabled_only: bool = True,
    ) -> list[GlossaryItem]:
        """Get all glossary items for an agent."""
        results = []
        for item in self._glossary_items.values():
            if item.tenant_id != tenant_id or item.agent_id != agent_id:
                continue
            if enabled_only and not item.enabled:
                continue
            results.append(item)
        return results

    async def save_glossary_item(self, item: GlossaryItem) -> None:
        """Save a glossary item."""
        self._glossary_items[item.id] = item

    # Customer data field operations
    async def get_customer_data_fields(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        enabled_only: bool = True,
    ) -> list[InterlocutorDataField]:
        """Get all customer data field definitions for an agent."""
        results = []
        for field in self._customer_data_fields.values():
            if field.tenant_id != tenant_id or field.agent_id != agent_id:
                continue
            if enabled_only and not field.enabled:
                continue
            results.append(field)
        return results

    async def save_customer_data_field(self, field: InterlocutorDataField) -> None:
        """Save a customer data field definition."""
        self._customer_data_fields[field.id] = field

    # Intent operations
    async def get_intent(self, tenant_id: UUID, intent_id: UUID) -> Intent | None:
        """Get an intent by ID."""
        intent = self._intents.get(intent_id)
        if intent and intent.tenant_id == tenant_id:
            return intent
        return None

    async def get_intents(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Intent]:
        """Get all intents for an agent."""
        results = []
        for intent in self._intents.values():
            if intent.tenant_id != tenant_id or intent.agent_id != agent_id:
                continue
            if enabled_only and not intent.enabled:
                continue
            results.append(intent)
        return results

    async def save_intent(self, intent: Intent) -> UUID:
        """Save an intent, returning its ID."""
        self._intents[intent.id] = intent
        return intent.id

    async def delete_intent(self, tenant_id: UUID, intent_id: UUID) -> bool:
        """Soft-delete an intent."""
        intent = self._intents.get(intent_id)
        if intent and intent.tenant_id == tenant_id and intent.enabled:
            intent.enabled = False
            return True
        return False
