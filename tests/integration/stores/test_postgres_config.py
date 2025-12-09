"""Integration tests for PostgresAgentConfigStore.

Tests CRUD operations, vector search, and tenant isolation
against a real PostgreSQL database with pgvector.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from soldier.alignment.models import (
    Agent,
    Rule,
    Scenario,
    ScenarioStep,
    Scope,
    Template,
    TemplateResponseMode,
    Variable,
    VariableUpdatePolicy,
)
from soldier.alignment.stores.postgres import PostgresAgentConfigStore


@pytest_asyncio.fixture
async def config_store(postgres_pool):
    """Create PostgresAgentConfigStore with test pool."""
    return PostgresAgentConfigStore(postgres_pool)


@pytest.fixture
def sample_agent(tenant_id):
    """Create a sample agent for testing."""
    return Agent(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Test Agent",
        description="Agent for integration tests",
        system_prompt="You are a helpful assistant",
        enabled=True,
    )


@pytest.fixture
def sample_rule(tenant_id, sample_agent):
    """Create a sample rule for testing."""
    return Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=sample_agent.id,
        name="Test Rule",
        description="Rule for integration tests",
        condition_text="When user asks about pricing",
        action_text="Provide pricing information from our catalog",
        scope=Scope.GLOBAL,
        priority=10,
        enabled=True,
    )


@pytest.fixture
def sample_scenario(tenant_id, sample_agent):
    """Create a sample scenario for testing."""
    return Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=sample_agent.id,
        name="Test Scenario",
        description="Scenario for integration tests",
        version=1,
        entry_condition="User wants to sign up",
        steps=[
            ScenarioStep(
                id=uuid4(),
                name="greeting",
                goal="Greet the user",
                transitions=[],
            )
        ],
        enabled=True,
    )


@pytest.fixture
def sample_template(tenant_id, sample_agent):
    """Create a sample template for testing."""
    return Template(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=sample_agent.id,
        name="Test Template",
        content="Hello, how can I help you today?",
        mode=TemplateResponseMode.SUGGEST,
        scope=Scope.GLOBAL,
    )


@pytest.fixture
def sample_variable(tenant_id, sample_agent):
    """Create a sample variable for testing."""
    return Variable(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=sample_agent.id,
        name="user_name",
        description="Customer's name",
        resolver_tool_id="get_user_name",
        update_policy=VariableUpdatePolicy.ON_DEMAND,
    )


@pytest.mark.integration
class TestPostgresAgentConfigStoreAgent:
    """Test agent CRUD operations."""

    async def test_save_and_get_agent(
        self, config_store, sample_agent, clean_postgres
    ):
        """Test saving and retrieving an agent."""
        # Save
        agent_id = await config_store.save_agent(sample_agent)
        assert agent_id == sample_agent.id

        # Get
        retrieved = await config_store.get_agent(
            sample_agent.tenant_id, sample_agent.id
        )
        assert retrieved is not None
        assert retrieved.name == sample_agent.name
        assert retrieved.description == sample_agent.description

    async def test_get_agents_pagination(
        self, config_store, tenant_id, clean_postgres
    ):
        """Test listing agents with pagination."""
        # Create multiple agents
        agents = []
        for i in range(5):
            agent = Agent(
                id=uuid4(),
                tenant_id=tenant_id,
                name=f"Agent {i}",
                enabled=True,
            )
            await config_store.save_agent(agent)
            agents.append(agent)

        # Get first page
        result, total = await config_store.get_agents(
            tenant_id, limit=2, offset=0
        )
        assert len(result) == 2
        assert total == 5

        # Get second page
        result, total = await config_store.get_agents(
            tenant_id, limit=2, offset=2
        )
        assert len(result) == 2

    async def test_soft_delete_agent(
        self, config_store, sample_agent, clean_postgres
    ):
        """Test soft-deleting an agent."""
        await config_store.save_agent(sample_agent)

        # Delete
        deleted = await config_store.delete_agent(
            sample_agent.tenant_id, sample_agent.id
        )
        assert deleted is True

        # Should not be found
        retrieved = await config_store.get_agent(
            sample_agent.tenant_id, sample_agent.id
        )
        assert retrieved is None


@pytest.mark.integration
class TestPostgresAgentConfigStoreRule:
    """Test rule CRUD operations."""

    async def test_save_and_get_rule(
        self, config_store, sample_agent, sample_rule, clean_postgres
    ):
        """Test saving and retrieving a rule."""
        await config_store.save_agent(sample_agent)

        # Save rule
        rule_id = await config_store.save_rule(sample_rule)
        assert rule_id == sample_rule.id

        # Get rule
        retrieved = await config_store.get_rule(
            sample_rule.tenant_id, sample_rule.id
        )
        assert retrieved is not None
        assert retrieved.name == sample_rule.name
        assert retrieved.condition_text == sample_rule.condition_text

    async def test_get_rules_by_scope(
        self, config_store, sample_agent, tenant_id, clean_postgres
    ):
        """Test filtering rules by scope."""
        await config_store.save_agent(sample_agent)

        # Create rules with different scopes
        global_rule = Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=sample_agent.id,
            name="Global Rule",
            condition_text="Always",
            action_text="Do something global",
            scope=Scope.GLOBAL,
        )
        scenario_rule = Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=sample_agent.id,
            name="Scenario Rule",
            condition_text="In scenario",
            action_text="Do something in scenario",
            scope=Scope.SCENARIO,
            scope_id=uuid4(),
        )

        await config_store.save_rule(global_rule)
        await config_store.save_rule(scenario_rule)

        # Filter by scope
        global_rules = await config_store.get_rules(
            tenant_id, sample_agent.id, scope=Scope.GLOBAL
        )
        assert len(global_rules) == 1
        assert global_rules[0].name == "Global Rule"


@pytest.mark.integration
class TestPostgresAgentConfigStoreTenantIsolation:
    """Test tenant isolation."""

    async def test_tenant_isolation_agents(
        self, config_store, clean_postgres
    ):
        """Test that agents are isolated by tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        agent1 = Agent(
            id=uuid4(),
            tenant_id=tenant1,
            name="Tenant 1 Agent",
            enabled=True,
        )
        agent2 = Agent(
            id=uuid4(),
            tenant_id=tenant2,
            name="Tenant 2 Agent",
            enabled=True,
        )

        await config_store.save_agent(agent1)
        await config_store.save_agent(agent2)

        # Tenant 1 should only see their agent
        result1, _ = await config_store.get_agents(tenant1)
        assert len(result1) == 1
        assert result1[0].name == "Tenant 1 Agent"

        # Tenant 2 should only see their agent
        result2, _ = await config_store.get_agents(tenant2)
        assert len(result2) == 1
        assert result2[0].name == "Tenant 2 Agent"

        # Cross-tenant access should fail
        cross_tenant = await config_store.get_agent(tenant2, agent1.id)
        assert cross_tenant is None


@pytest.mark.integration
class TestPostgresAgentConfigStoreSoftDelete:
    """Test soft delete behavior."""

    async def test_soft_deleted_not_in_list(
        self, config_store, sample_agent, sample_rule, clean_postgres
    ):
        """Test that soft-deleted items don't appear in lists."""
        await config_store.save_agent(sample_agent)
        await config_store.save_rule(sample_rule)

        # Delete rule
        await config_store.delete_rule(sample_rule.tenant_id, sample_rule.id)

        # Should not appear in list
        rules = await config_store.get_rules(
            sample_rule.tenant_id, sample_agent.id
        )
        assert len(rules) == 0

    async def test_delete_nonexistent_returns_false(
        self, config_store, tenant_id, clean_postgres
    ):
        """Test deleting nonexistent item returns False."""
        deleted = await config_store.delete_agent(tenant_id, uuid4())
        assert deleted is False
