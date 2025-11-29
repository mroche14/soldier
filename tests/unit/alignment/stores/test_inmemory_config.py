"""Tests for InMemoryConfigStore."""

from uuid import uuid4

import pytest

from soldier.alignment.models import Rule, Scenario, Scope, Template, Variable
from soldier.alignment.stores import InMemoryConfigStore


@pytest.fixture
def store() -> InMemoryConfigStore:
    """Create a fresh store for each test."""
    return InMemoryConfigStore()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def sample_rule(tenant_id, agent_id) -> Rule:
    """Create a sample rule."""
    return Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Test Rule",
        condition_text="When user asks about refunds",
        action_text="Explain refund policy",
    )


class TestRuleOperations:
    """Tests for rule CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_rule(self, store, sample_rule, tenant_id):
        """Should save and retrieve a rule."""
        rule_id = await store.save_rule(sample_rule)
        retrieved = await store.get_rule(tenant_id, rule_id)

        assert retrieved is not None
        assert retrieved.id == sample_rule.id
        assert retrieved.name == "Test Rule"

    @pytest.mark.asyncio
    async def test_get_nonexistent_rule(self, store, tenant_id):
        """Should return None for nonexistent rule."""
        result = await store.get_rule(tenant_id, uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, store, sample_rule, tenant_id):
        """Should not return rules from other tenants."""
        await store.save_rule(sample_rule)
        other_tenant = uuid4()
        result = await store.get_rule(other_tenant, sample_rule.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_rules_by_agent(self, store, tenant_id, agent_id):
        """Should get all rules for an agent."""
        rules = [
            Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=f"Rule {i}",
                condition_text="Test",
                action_text="Test",
            )
            for i in range(3)
        ]
        for rule in rules:
            await store.save_rule(rule)

        results = await store.get_rules(tenant_id, agent_id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_rules_by_scope(self, store, tenant_id, agent_id):
        """Should filter rules by scope."""
        scenario_id = uuid4()
        global_rule = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Global Rule",
            condition_text="Test",
            action_text="Test",
            scope=Scope.GLOBAL,
        )
        scenario_rule = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Scenario Rule",
            condition_text="Test",
            action_text="Test",
            scope=Scope.SCENARIO,
            scope_id=scenario_id,
        )
        await store.save_rule(global_rule)
        await store.save_rule(scenario_rule)

        global_results = await store.get_rules(tenant_id, agent_id, scope=Scope.GLOBAL)
        assert len(global_results) == 1
        assert global_results[0].name == "Global Rule"

        scenario_results = await store.get_rules(
            tenant_id, agent_id, scope=Scope.SCENARIO, scope_id=scenario_id
        )
        assert len(scenario_results) == 1
        assert scenario_results[0].name == "Scenario Rule"

    @pytest.mark.asyncio
    async def test_delete_rule(self, store, sample_rule, tenant_id):
        """Should soft-delete a rule."""
        await store.save_rule(sample_rule)

        result = await store.delete_rule(tenant_id, sample_rule.id)
        assert result is True

        # Should not be retrievable after delete
        retrieved = await store.get_rule(tenant_id, sample_rule.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_enabled_only_filter(self, store, tenant_id, agent_id):
        """Should filter disabled rules when enabled_only=True."""
        enabled_rule = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Enabled",
            condition_text="Test",
            action_text="Test",
            enabled=True,
        )
        disabled_rule = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Disabled",
            condition_text="Test",
            action_text="Test",
            enabled=False,
        )
        await store.save_rule(enabled_rule)
        await store.save_rule(disabled_rule)

        results = await store.get_rules(tenant_id, agent_id, enabled_only=True)
        assert len(results) == 1
        assert results[0].name == "Enabled"

        all_results = await store.get_rules(tenant_id, agent_id, enabled_only=False)
        assert len(all_results) == 2


class TestVectorSearch:
    """Tests for vector search functionality."""

    @pytest.mark.asyncio
    async def test_vector_search_rules(self, store, tenant_id, agent_id):
        """Should search rules by vector similarity."""
        rule1 = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Similar Rule",
            condition_text="Test",
            action_text="Test",
            embedding=[1.0, 0.0, 0.0],
        )
        rule2 = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Different Rule",
            condition_text="Test",
            action_text="Test",
            embedding=[0.0, 1.0, 0.0],
        )
        await store.save_rule(rule1)
        await store.save_rule(rule2)

        query = [1.0, 0.0, 0.0]
        results = await store.vector_search_rules(query, tenant_id, agent_id)

        assert len(results) == 2
        # First result should be the most similar
        assert results[0][0].name == "Similar Rule"
        assert results[0][1] == 1.0  # Perfect match

    @pytest.mark.asyncio
    async def test_vector_search_with_limit(self, store, tenant_id, agent_id):
        """Should respect limit parameter."""
        for i in range(5):
            rule = Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=f"Rule {i}",
                condition_text="Test",
                action_text="Test",
                embedding=[float(i), 0.0, 0.0],
            )
            await store.save_rule(rule)

        query = [1.0, 0.0, 0.0]
        results = await store.vector_search_rules(query, tenant_id, agent_id, limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_vector_search_min_score(self, store, tenant_id, agent_id):
        """Should filter by minimum score."""
        high_match = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="High Match",
            condition_text="Test",
            action_text="Test",
            embedding=[1.0, 0.0, 0.0],
        )
        low_match = Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Low Match",
            condition_text="Test",
            action_text="Test",
            embedding=[0.0, 1.0, 0.0],
        )
        await store.save_rule(high_match)
        await store.save_rule(low_match)

        query = [1.0, 0.0, 0.0]
        results = await store.vector_search_rules(
            query, tenant_id, agent_id, min_score=0.9
        )
        assert len(results) == 1
        assert results[0][0].name == "High Match"


class TestScenarioOperations:
    """Tests for scenario CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_scenario(self, store, tenant_id, agent_id):
        """Should save and retrieve a scenario."""
        entry_step_id = uuid4()
        scenario = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test Scenario",
            entry_step_id=entry_step_id,
        )
        scenario_id = await store.save_scenario(scenario)
        retrieved = await store.get_scenario(tenant_id, scenario_id)

        assert retrieved is not None
        assert retrieved.name == "Test Scenario"

    @pytest.mark.asyncio
    async def test_get_scenarios_by_agent(self, store, tenant_id, agent_id):
        """Should get all scenarios for an agent."""
        for i in range(2):
            scenario = Scenario(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=f"Scenario {i}",
                entry_step_id=uuid4(),
            )
            await store.save_scenario(scenario)

        results = await store.get_scenarios(tenant_id, agent_id)
        assert len(results) == 2


class TestTemplateOperations:
    """Tests for template CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_template(self, store, tenant_id, agent_id):
        """Should save and retrieve a template."""
        template = Template(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Welcome Template",
            text="Hello {name}!",
        )
        template_id = await store.save_template(template)
        retrieved = await store.get_template(tenant_id, template_id)

        assert retrieved is not None
        assert retrieved.name == "Welcome Template"


class TestVariableOperations:
    """Tests for variable CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_variable(self, store, tenant_id, agent_id):
        """Should save and retrieve a variable."""
        variable = Variable(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="user_name",
            resolver_tool_id="get_user_name",
        )
        variable_id = await store.save_variable(variable)
        retrieved = await store.get_variable(tenant_id, variable_id)

        assert retrieved is not None
        assert retrieved.name == "user_name"

    @pytest.mark.asyncio
    async def test_get_variable_by_name(self, store, tenant_id, agent_id):
        """Should get variable by name."""
        variable = Variable(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="user_email",
            resolver_tool_id="get_email",
        )
        await store.save_variable(variable)

        retrieved = await store.get_variable_by_name(tenant_id, agent_id, "user_email")
        assert retrieved is not None
        assert retrieved.name == "user_email"

        not_found = await store.get_variable_by_name(tenant_id, agent_id, "nonexistent")
        assert not_found is None
