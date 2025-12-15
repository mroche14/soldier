"""ConfigStore abstract interface.

Manages agent configuration data including rules, scenarios, templates,
variables, and migration plans.
"""

from abc import ABC, abstractmethod
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
from ruche.interlocutor_data import InterlocutorDataField


class ConfigStore(ABC):
    """Abstract interface for agent configuration storage.

    Manages rules, scenarios, templates, variables, and agent
    configuration with support for vector search and scoping.
    """

    # Rule operations
    @abstractmethod
    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None:
        """Get a rule by ID."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def save_rule(self, rule: Rule) -> UUID:
        """Save a rule, returning its ID."""
        pass

    @abstractmethod
    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool:
        """Soft-delete a rule by setting deleted_at."""
        pass

    @abstractmethod
    async def vector_search_rules(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Rule, float]]:
        """Search rules by vector similarity, returning (rule, score) pairs."""
        pass

    # Rule relationship operations
    @abstractmethod
    async def get_rule_relationships(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        rule_ids: list[UUID] | None = None,
    ) -> list[RuleRelationship]:
        """Get rule relationships, optionally filtered by rule IDs."""
        pass

    @abstractmethod
    async def save_rule_relationship(
        self,
        relationship: RuleRelationship,
    ) -> UUID:
        """Save a rule relationship, returning its ID."""
        pass

    @abstractmethod
    async def delete_rule_relationship(
        self,
        tenant_id: UUID,
        relationship_id: UUID,
    ) -> bool:
        """Soft-delete a rule relationship."""
        pass

    # Scenario operations
    @abstractmethod
    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        """Get a scenario by ID."""
        pass

    @abstractmethod
    async def get_scenarios(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Scenario]:
        """Get scenarios for an agent."""
        pass

    @abstractmethod
    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Save a scenario, returning its ID."""
        pass

    @abstractmethod
    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool:
        """Soft-delete a scenario."""
        pass

    # Template operations
    @abstractmethod
    async def get_template(self, tenant_id: UUID, template_id: UUID) -> Template | None:
        """Get a template by ID."""
        pass

    @abstractmethod
    async def get_templates(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
    ) -> list[Template]:
        """Get templates for an agent with optional filtering."""
        pass

    @abstractmethod
    async def save_template(self, template: Template) -> UUID:
        """Save a template, returning its ID."""
        pass

    @abstractmethod
    async def delete_template(self, tenant_id: UUID, template_id: UUID) -> bool:
        """Soft-delete a template."""
        pass

    # Variable operations
    @abstractmethod
    async def get_variable(self, tenant_id: UUID, variable_id: UUID) -> Variable | None:
        """Get a variable by ID."""
        pass

    @abstractmethod
    async def get_variables(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Variable]:
        """Get variables for an agent."""
        pass

    @abstractmethod
    async def get_variable_by_name(
        self, tenant_id: UUID, agent_id: UUID, name: str
    ) -> Variable | None:
        """Get a variable by name."""
        pass

    @abstractmethod
    async def save_variable(self, variable: Variable) -> UUID:
        """Save a variable, returning its ID."""
        pass

    @abstractmethod
    async def delete_variable(self, tenant_id: UUID, variable_id: UUID) -> bool:
        """Soft-delete a variable."""
        pass

    # Agent operations
    @abstractmethod
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        pass

    @abstractmethod
    async def get_agents(
        self,
        tenant_id: UUID,
        *,
        enabled_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Agent], int]:
        """Get agents for a tenant with pagination.

        Returns:
            Tuple of (agents list, total count)
        """
        pass

    @abstractmethod
    async def save_agent(self, agent: Agent) -> UUID:
        """Save an agent, returning its ID."""
        pass

    @abstractmethod
    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool:
        """Soft-delete an agent."""
        pass

    # Tool activation operations
    @abstractmethod
    async def get_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> ToolActivation | None:
        """Get a tool activation by agent and tool ID."""
        pass

    @abstractmethod
    async def get_tool_activations(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[ToolActivation]:
        """Get all tool activations for an agent."""
        pass

    @abstractmethod
    async def save_tool_activation(self, activation: ToolActivation) -> UUID:
        """Save a tool activation, returning its ID."""
        pass

    @abstractmethod
    async def delete_tool_activation(
        self, tenant_id: UUID, agent_id: UUID, tool_id: str
    ) -> bool:
        """Delete a tool activation."""
        pass

    # Migration plan operations
    @abstractmethod
    async def get_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> MigrationPlan | None:
        """Get migration plan by ID."""
        pass

    @abstractmethod
    async def get_migration_plan_for_versions(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        from_version: int,
        to_version: int,
    ) -> MigrationPlan | None:
        """Get migration plan for specific version transition."""
        pass

    @abstractmethod
    async def save_migration_plan(self, plan: MigrationPlan) -> UUID:
        """Save or update migration plan."""
        pass

    @abstractmethod
    async def list_migration_plans(
        self,
        tenant_id: UUID,
        scenario_id: UUID | None = None,
        status: MigrationPlanStatus | None = None,
        limit: int = 50,
    ) -> list[MigrationPlan]:
        """List migration plans for scenario."""
        pass

    @abstractmethod
    async def delete_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> bool:
        """Delete a migration plan."""
        pass

    # Scenario version archiving
    @abstractmethod
    async def archive_scenario_version(
        self, tenant_id: UUID, scenario: Scenario
    ) -> None:
        """Archive scenario version before update."""
        pass

    @abstractmethod
    async def get_archived_scenario(
        self, tenant_id: UUID, scenario_id: UUID, version: int
    ) -> Scenario | None:
        """Get archived scenario by version."""
        pass

    # Glossary operations (Phase 1)
    @abstractmethod
    async def get_glossary_items(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[GlossaryItem]:
        """Get all glossary items for an agent."""
        pass

    @abstractmethod
    async def save_glossary_item(self, item: GlossaryItem) -> UUID:
        """Save a glossary item."""
        pass

    # Customer data field operations (Phase 1)
    @abstractmethod
    async def get_customer_data_fields(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[InterlocutorDataField]:
        """Get all customer data field definitions for an agent."""
        pass

    @abstractmethod
    async def save_customer_data_field(self, field: InterlocutorDataField) -> UUID:
        """Save a customer data field definition."""
        pass

    # Intent operations (Phase 4)
    @abstractmethod
    async def get_intent(self, tenant_id: UUID, intent_id: UUID) -> Intent | None:
        """Get an intent by ID.

        Args:
            tenant_id: Tenant identifier
            intent_id: Intent identifier

        Returns:
            Intent if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_intents(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[Intent]:
        """Get all intents for an agent.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            enabled_only: Only return enabled intents

        Returns:
            List of intents for the agent
        """
        pass

    @abstractmethod
    async def save_intent(self, intent: Intent) -> UUID:
        """Save an intent, returning its ID.

        Args:
            intent: Intent to save

        Returns:
            UUID of the saved intent
        """
        pass

    @abstractmethod
    async def delete_intent(self, tenant_id: UUID, intent_id: UUID) -> bool:
        """Soft-delete an intent.

        Args:
            tenant_id: Tenant identifier
            intent_id: Intent identifier

        Returns:
            True if deleted, False if not found
        """
        pass
