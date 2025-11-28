"""In-memory implementation of ConfigStore."""

from datetime import UTC, datetime
from uuid import UUID

from soldier.alignment.models import Rule, Scenario, Scope, Template, Variable
from soldier.alignment.stores.config_store import ConfigStore
from soldier.utils.vector import cosine_similarity


class InMemoryConfigStore(ConfigStore):
    """In-memory implementation of ConfigStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._rules: dict[UUID, Rule] = {}
        self._scenarios: dict[UUID, Scenario] = {}
        self._templates: dict[UUID, Template] = {}
        self._variables: dict[UUID, Variable] = {}

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
