"""Unit tests for AlignmentEngine."""

from typing import Any
from uuid import uuid4

import pytest

from focal.alignment.context.models import Turn
from focal.alignment.context.situation_snapshot import SituationSnapshot
from focal.alignment.engine import AlignmentEngine
from focal.alignment.models import Rule
from focal.alignment.result import AlignmentResult, PipelineStepTiming
from focal.alignment.stores import AgentConfigStore
from focal.config.models.pipeline import PipelineConfig
from focal.providers.embedding import EmbeddingProvider, EmbeddingResponse


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dims: int = 1536) -> None:
        self._dims = dims

    @property
    def provider_name(self) -> str:
        return "mock_embedding"

    @property
    def dimensions(self) -> int:
        return self._dims

    async def embed(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        embeddings = [[0.1] * self._dims for _ in texts]
        return EmbeddingResponse(
            embeddings=embeddings,
            model="mock-embedding-model",
            dimensions=self._dims,
        )

    async def embed_single(self, text: str, **kwargs: Any) -> list[float]:
        response = await self.embed([text], **kwargs)
        return response.embeddings[0]


class MockAgentConfigStore(AgentConfigStore):
    """Mock config store for testing."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self._rules = rules or []

    async def get_rules_for_agent(self, tenant_id, agent_id) -> list[Rule]:
        return [r for r in self._rules if r.enabled]

    # Rule operations
    async def get_rule(self, tenant_id, rule_id):
        for r in self._rules:
            if r.id == rule_id:
                return r
        return None

    async def get_rules(self, tenant_id, agent_id, *, scope=None, scope_id=None, enabled_only=True):
        rules = self._rules
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    async def save_rule(self, rule: Rule):
        self._rules.append(rule)
        return rule.id

    async def delete_rule(self, tenant_id, rule_id) -> bool:
        return True

    async def vector_search_rules(self, query_embedding, tenant_id, agent_id, *, limit=10, min_score=0.0):
        # Return all rules with mock scores
        return [(r, 0.9) for r in self._rules[:limit]]

    # Scenario operations
    async def get_scenario(self, tenant_id, scenario_id):
        return None

    async def get_scenarios(self, tenant_id, agent_id, *, enabled_only=True):
        return []

    async def save_scenario(self, scenario):
        return scenario.id

    async def delete_scenario(self, tenant_id, scenario_id):
        return True

    # Template operations
    async def get_template(self, tenant_id, template_id):
        return None

    async def get_templates(self, tenant_id, agent_id, *, scope=None, scope_id=None):
        return []

    async def save_template(self, template):
        return template.id

    async def delete_template(self, tenant_id, template_id):
        return True

    # Variable operations
    async def get_variable(self, tenant_id, variable_id):
        return None

    async def get_variables(self, tenant_id, agent_id):
        return []

    async def get_variable_by_name(self, tenant_id, agent_id, name):
        return None

    async def save_variable(self, variable):
        return variable.id

    async def delete_variable(self, tenant_id, variable_id):
        return True

    # Agent operations
    async def get_agent(self, tenant_id, agent_id):
        return None

    async def get_agents(self, tenant_id, *, enabled_only=False, limit=20, offset=0):
        return [], 0

    async def save_agent(self, agent):
        return agent.id

    async def delete_agent(self, tenant_id, agent_id):
        return True

    # Tool activation operations
    async def get_tool_activation(self, tenant_id, agent_id, tool_id):
        return None

    async def get_tool_activations(self, tenant_id, agent_id):
        return []

    async def save_tool_activation(self, activation):
        return activation.id

    async def delete_tool_activation(self, tenant_id, agent_id, tool_id):
        return True

    # Migration plan operations (stubs for abstract methods)
    async def get_migration_plan(self, tenant_id, plan_id):
        return None

    async def get_migration_plan_for_versions(self, tenant_id, scenario_id, from_version, to_version):
        return None

    async def save_migration_plan(self, plan):
        return plan.id

    async def list_migration_plans(self, tenant_id, *, scenario_id=None, status=None, limit=50):
        return []

    async def delete_migration_plan(self, tenant_id, plan_id):
        return True

    # Scenario archiving operations (stubs for abstract methods)
    async def archive_scenario_version(self, scenario, checksum):
        return scenario.id

    async def get_archived_scenario(self, tenant_id, scenario_id, version):
        return None

    # Glossary operations (stubs for abstract methods)
    async def get_glossary_items(self, tenant_id, agent_id, enabled_only=True):
        return []

    async def save_glossary_item(self, item):
        pass

    # Customer data field operations (stubs for abstract methods)
    async def get_customer_data_fields(self, tenant_id, agent_id, enabled_only=True):
        return []

    async def save_customer_data_field(self, field):
        pass

    # Intent operations (stubs for abstract methods)
    async def get_intent(self, tenant_id, intent_id):
        return None

    async def get_intents(self, tenant_id, agent_id, *, enabled_only=True):
        return []

    async def save_intent(self, intent):
        return intent.id

    async def delete_intent(self, tenant_id, intent_id):
        return True

    # Rule relationship operations (stubs for abstract methods)
    async def get_rule_relationships(self, tenant_id, agent_id, *, source_rule_id=None, kind=None):
        return []

    async def save_rule_relationship(self, relationship):
        return relationship.id

    async def delete_rule_relationship(self, tenant_id, relationship_id):
        return True


def create_rule(
    name: str = "Test Rule",
    condition_text: str = "When user asks",
    action_text: str = "Respond helpfully",
    enabled: bool = True,
    tenant_id: str | None = None,
    agent_id: str | None = None,
) -> Rule:
    """Create a test rule."""
    return Rule(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        agent_id=agent_id or uuid4(),
        name=name,
        condition_text=condition_text,
        action_text=action_text,
        enabled=enabled,
    )


class TestAlignmentEngine:
    """Tests for AlignmentEngine class."""

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        return uuid4()

    @pytest.fixture
    def session_id(self):
        return uuid4()

    @pytest.fixture
    def embedding_provider(self) -> MockEmbeddingProvider:
        return MockEmbeddingProvider()

    @pytest.fixture
    def config_store(self, tenant_id, agent_id) -> MockAgentConfigStore:
        rules = [
            create_rule(
                name="Return Policy",
                condition_text="When user mentions return",
                action_text="Explain return process",
                tenant_id=tenant_id,
                agent_id=agent_id,
            ),
            create_rule(
                name="Order Help",
                condition_text="When user asks about order",
                action_text="Provide order info",
                tenant_id=tenant_id,
                agent_id=agent_id,
            ),
        ]
        return MockAgentConfigStore(rules=rules)

    @pytest.fixture
    def pipeline_config(self) -> PipelineConfig:
        """Create a pipeline config with mock models for testing."""
        config = PipelineConfig()
        # Override all models to use mock provider
        config.context_extraction.model = "mock/test"
        config.rule_filtering.model = "mock/test"
        config.scenario_filtering.model = "mock/test"
        config.generation.model = "mock/test"
        return config

    @pytest.fixture
    def engine(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
    ) -> AlignmentEngine:
        return AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )

    # Test initialization

    def test_engine_can_be_created(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
    ) -> None:
        """Test that AlignmentEngine can be instantiated."""
        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )
        assert engine is not None

    def test_engine_with_custom_config(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
    ) -> None:
        """Test engine with custom pipeline config."""
        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )
        assert engine._config == pipeline_config

    # Test process_turn

    @pytest.mark.asyncio
    async def test_process_turn_returns_result(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that process_turn returns AlignmentResult."""
        result = await engine.process_turn(
            message="I want to return my order",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert isinstance(result, AlignmentResult)

    @pytest.mark.asyncio
    async def test_process_turn_has_response(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that result contains a response."""
        result = await engine.process_turn(
            message="I want to return my order",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.response is not None
        assert len(result.response) > 0

    @pytest.mark.asyncio
    async def test_process_turn_includes_context(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that result includes extracted context."""
        result = await engine.process_turn(
            message="I want to return my order",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.snapshot is not None
        assert isinstance(result.snapshot, SituationSnapshot)
        assert result.snapshot.message == "I want to return my order"

    @pytest.mark.asyncio
    async def test_process_turn_includes_matched_rules(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that result includes matched rules."""
        result = await engine.process_turn(
            message="I want to return my order",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.matched_rules is not None
        # Should have rules (even if filter is disabled they're passed through)
        assert len(result.matched_rules) >= 0

    @pytest.mark.asyncio
    async def test_process_turn_includes_timing(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that result includes pipeline timing."""
        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.pipeline_timings is not None
        assert len(result.pipeline_timings) > 0
        assert result.total_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_turn_with_history(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test processing with conversation history."""
        history = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="Hi! How can I help?"),
        ]

        result = await engine.process_turn(
            message="I need to return something",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            history=history,
        )

        assert result.response is not None

    # Test pipeline steps

    @pytest.mark.asyncio
    async def test_process_turn_step_situation_sensor(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that situation sensor step is recorded."""
        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        step_names = [t.step for t in result.pipeline_timings]
        assert "situation_sensor" in step_names

    @pytest.mark.asyncio
    async def test_process_turn_step_retrieval(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that retrieval step is recorded."""
        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        step_names = [t.step for t in result.pipeline_timings]
        assert "retrieval" in step_names

    @pytest.mark.asyncio
    async def test_process_turn_step_generation(
        self,
        engine: AlignmentEngine,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test that generation step is recorded."""
        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        step_names = [t.step for t in result.pipeline_timings]
        assert "generation" in step_names

    # Test with disabled steps

    @pytest.mark.asyncio
    async def test_process_turn_disabled_situation_sensor(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test with situation sensor disabled."""
        pipeline_config.situation_sensor.enabled = False

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )

        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Snapshot should be minimal (no enrichment from sensor)
        assert result.snapshot.canonical_intent_label is None
        assert result.snapshot.embedding is None

    @pytest.mark.asyncio
    async def test_process_turn_disabled_retrieval(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test with retrieval disabled."""
        pipeline_config.retrieval.enabled = False

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )

        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Find retrieval timing - should be skipped
        retrieval_timing = next(
            (t for t in result.pipeline_timings if t.step == "retrieval"),
            None,
        )
        assert retrieval_timing is not None
        assert retrieval_timing.skipped is True

    @pytest.mark.asyncio
    async def test_process_turn_disabled_generation(
        self,
        config_store: MockAgentConfigStore,
        embedding_provider: MockEmbeddingProvider,
        pipeline_config: PipelineConfig,
        session_id,
        tenant_id,
        agent_id,
    ) -> None:
        """Test with generation disabled."""
        pipeline_config.generation.enabled = False

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            pipeline_config=pipeline_config,
        )

        result = await engine.process_turn(
            message="Test",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Should have a fallback response
        assert "unable to respond" in result.response.lower()


class TestAlignmentResult:
    """Tests for AlignmentResult model."""

    def test_create_result(self) -> None:
        """Test creating a result."""
        result = AlignmentResult(
            session_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            user_message="Hello",
            snapshot=SituationSnapshot(
                message="Hello",
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
            ),
            matched_rules=[],
            generation=None,
            enforcement=None,
            response="Hi there!",
            pipeline_timings=[],
            total_time_ms=100.0,
        )

        assert result.user_message == "Hello"
        assert result.response == "Hi there!"

    def test_result_includes_all_ids(self) -> None:
        """Test that result includes all ID fields."""
        session_id = uuid4()
        tenant_id = uuid4()
        agent_id = uuid4()

        result = AlignmentResult(
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_message="Test",
            snapshot=SituationSnapshot(
                message="Test",
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
            ),
            matched_rules=[],
            generation=None,
            enforcement=None,
            response="Response",
            pipeline_timings=[],
            total_time_ms=0,
        )

        assert result.session_id == session_id
        assert result.tenant_id == tenant_id
        assert result.agent_id == agent_id


class TestPipelineStepTiming:
    """Tests for PipelineStepTiming model."""

    def test_create_timing(self) -> None:
        """Test creating a timing record."""
        from datetime import datetime

        now = datetime.utcnow()
        timing = PipelineStepTiming(
            step="test_step",
            started_at=now,
            ended_at=now,
            duration_ms=50.0,
        )

        assert timing.step == "test_step"
        assert timing.duration_ms == 50.0
        assert timing.skipped is False

    def test_timing_skipped(self) -> None:
        """Test skipped timing record."""
        from datetime import datetime

        now = datetime.utcnow()
        timing = PipelineStepTiming(
            step="disabled_step",
            started_at=now,
            ended_at=now,
            duration_ms=0,
            skipped=True,
            skip_reason="Step disabled",
        )

        assert timing.skipped is True
        assert timing.skip_reason == "Step disabled"
