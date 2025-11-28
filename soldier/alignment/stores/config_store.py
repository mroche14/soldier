"""ConfigStore abstract interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from soldier.alignment.models import Rule, Scenario, Scope, Template, Variable


class ConfigStore(ABC):
    """Abstract interface for configuration storage.

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

    # Scenario operations
    @abstractmethod
    async def get_scenario(
        self, tenant_id: UUID, scenario_id: UUID
    ) -> Scenario | None:
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
    async def get_template(
        self, tenant_id: UUID, template_id: UUID
    ) -> Template | None:
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
    async def get_variable(
        self, tenant_id: UUID, variable_id: UUID
    ) -> Variable | None:
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
