"""Unit tests for BrainFactory."""

import pytest
from uuid import uuid4

from ruche.runtime.brain.factory import BrainFactory
from ruche.brains.focal.models.agent import Agent


class MockBrain:
    """Mock brain implementation."""

    def __init__(self, brain_type: str):
        self.brain_type = brain_type

    async def think(self, context):
        """Mock think method."""
        return None


def focal_factory(agent: Agent) -> MockBrain:
    """Factory for FOCAL brain."""
    return MockBrain("focal")


def langgraph_factory(agent: Agent) -> MockBrain:
    """Factory for LangGraph brain."""
    return MockBrain("langgraph")


def agno_factory(agent: Agent) -> MockBrain:
    """Factory for Agno brain."""
    return MockBrain("agno")


def custom_factory(agent: Agent) -> MockBrain:
    """Factory for custom brain."""
    return MockBrain("custom")


@pytest.fixture
def agent():
    """Create test agent."""
    return Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Test Agent",
        current_version="1",
    )


class TestBrainFactory:
    """Tests for BrainFactory."""

    def test_creates_focal_brain(self, agent):
        """Create FOCAL brain."""
        factory = BrainFactory(focal_factory=focal_factory)

        brain = factory.create("focal", agent)

        assert isinstance(brain, MockBrain)
        assert brain.brain_type == "focal"

    def test_creates_langgraph_brain(self, agent):
        """Create LangGraph brain."""
        factory = BrainFactory(langgraph_factory=langgraph_factory)

        brain = factory.create("langgraph", agent)

        assert isinstance(brain, MockBrain)
        assert brain.brain_type == "langgraph"

    def test_creates_agno_brain(self, agent):
        """Create Agno brain."""
        factory = BrainFactory(agno_factory=agno_factory)

        brain = factory.create("agno", agent)

        assert isinstance(brain, MockBrain)
        assert brain.brain_type == "agno"

    def test_raises_on_unknown_brain_type(self, agent):
        """Raise ValueError for unknown brain type."""
        factory = BrainFactory(focal_factory=focal_factory)

        with pytest.raises(ValueError, match="Unknown brain type"):
            factory.create("unknown", agent)

    def test_error_message_includes_available_types(self, agent):
        """Error message lists available types."""
        factory = BrainFactory(
            focal_factory=focal_factory,
            langgraph_factory=langgraph_factory,
        )

        with pytest.raises(ValueError) as exc_info:
            factory.create("unknown", agent)

        error_msg = str(exc_info.value)
        assert "focal" in error_msg
        assert "langgraph" in error_msg

    def test_registers_custom_brain(self, agent):
        """Register custom brain factory."""
        factory = BrainFactory()

        factory.register("custom", custom_factory)

        brain = factory.create("custom", agent)
        assert brain.brain_type == "custom"

    def test_register_overwrites_existing(self, agent):
        """Registering same type overwrites existing factory."""
        factory = BrainFactory(focal_factory=focal_factory)

        # Override focal with custom
        factory.register("focal", custom_factory)

        brain = factory.create("focal", agent)
        assert brain.brain_type == "custom"

    def test_available_types_property(self):
        """Get list of available brain types."""
        factory = BrainFactory(
            focal_factory=focal_factory,
            langgraph_factory=langgraph_factory,
        )

        types = factory.available_types

        assert "focal" in types
        assert "langgraph" in types
        assert len(types) == 2

    def test_available_types_includes_registered(self):
        """Include registered types in available_types."""
        factory = BrainFactory(focal_factory=focal_factory)
        factory.register("custom", custom_factory)

        types = factory.available_types

        assert "focal" in types
        assert "custom" in types

    def test_factory_without_any_brains(self, agent):
        """Factory without any registered brains."""
        factory = BrainFactory()

        assert factory.available_types == []

        with pytest.raises(ValueError):
            factory.create("focal", agent)

    def test_factory_passes_agent_to_brain(self):
        """Factory passes agent to brain constructor."""
        received_agents = []

        def tracking_factory(agent: Agent) -> MockBrain:
            received_agents.append(agent)
            return MockBrain("tracked")

        factory = BrainFactory(focal_factory=tracking_factory)
        agent = Agent(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Tracked Agent",
            current_version="1",
        )

        factory.create("focal", agent)

        assert len(received_agents) == 1
        assert received_agents[0] == agent

    def test_all_three_factories_in_constructor(self, agent):
        """Initialize with all three factory types."""
        factory = BrainFactory(
            focal_factory=focal_factory,
            langgraph_factory=langgraph_factory,
            agno_factory=agno_factory,
        )

        assert len(factory.available_types) == 3
        assert factory.create("focal", agent).brain_type == "focal"
        assert factory.create("langgraph", agent).brain_type == "langgraph"
        assert factory.create("agno", agent).brain_type == "agno"

    def test_optional_factories_in_constructor(self, agent):
        """Optional factories can be omitted."""
        # Only focal
        factory1 = BrainFactory(focal_factory=focal_factory)
        assert factory1.available_types == ["focal"]

        # Only langgraph
        factory2 = BrainFactory(langgraph_factory=langgraph_factory)
        assert factory2.available_types == ["langgraph"]

        # Focal and agno
        factory3 = BrainFactory(
            focal_factory=focal_factory,
            agno_factory=agno_factory,
        )
        assert len(factory3.available_types) == 2
        assert "focal" in factory3.available_types
        assert "agno" in factory3.available_types


class TestBrainTypeValidation:
    """Tests for brain type validation."""

    def test_brain_type_case_sensitive(self, agent):
        """Brain type is case-sensitive."""
        factory = BrainFactory(focal_factory=focal_factory)

        # Lowercase works
        brain1 = factory.create("focal", agent)
        assert brain1 is not None

        # Uppercase fails
        with pytest.raises(ValueError):
            factory.create("FOCAL", agent)

    def test_empty_string_brain_type(self, agent):
        """Empty string brain type raises error."""
        factory = BrainFactory(focal_factory=focal_factory)

        with pytest.raises(ValueError):
            factory.create("", agent)
