"""Integration tests for SessionStore and AuditStore integration in AlignmentEngine."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from ruche.alignment.context.models import Turn
from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.filtering.models import ScenarioAction, ScenarioFilterResult
from ruche.alignment.stores import InMemoryAgentConfigStore
from ruche.audit.models import TurnRecord
from ruche.audit.stores.inmemory import InMemoryAuditStore
from ruche.config.models.pipeline import PipelineConfig
from ruche.conversation.models import Channel, Session
from ruche.conversation.stores.inmemory import InMemorySessionStore
from ruche.providers.embedding import EmbeddingProvider, EmbeddingResponse
from ruche.providers.llm import LLMExecutor, LLMMessage, LLMResponse
from tests.factories.alignment import RuleFactory


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses or [
            json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"}),
            json.dumps({"evaluations": []}),
            "Test response",
        ]
        self._call_index = 0

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        response = self._responses[min(self._call_index, len(self._responses) - 1)]
        self._call_index += 1
        return LLMResponse(
            content=response,
            model="mock",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


def create_test_executors(responses: list[str] | None = None) -> dict[str, LLMExecutor]:
    """Create a set of mock executors for testing."""
    default_responses = responses or [
        json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"}),
        json.dumps({"evaluations": []}),
        "Test response",
    ]
    return {
        "context_extraction": MockLLMExecutor([default_responses[0]]),
        "rule_filtering": MockLLMExecutor([default_responses[1]] if len(default_responses) > 1 else default_responses),
        "generation": MockLLMExecutor([default_responses[2]] if len(default_responses) > 2 else default_responses),
    }


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def dimensions(self) -> int:
        return 3

    async def embed(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3] for _ in texts],
            model="mock",
            dimensions=3,
        )


class TestSessionLoading:
    """Tests for session loading from SessionStore."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.fixture
    def engine(self, stores):
        return AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
            executors=create_test_executors(),
        )

    @pytest.mark.asyncio
    async def test_loads_session_from_store(self, engine, stores) -> None:
        """Engine loads session from SessionStore when not provided."""
        tenant_id = uuid4()
        agent_id = uuid4()

        # Create and save session
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-123",
            config_version=1,
            turn_count=5,
        )
        await stores["session"].save(session)

        # Process turn without providing session
        result = await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.response is not None

        # Session should be updated
        updated = await stores["session"].get(session.session_id)
        assert updated.turn_count == 6  # Incremented from 5

    @pytest.mark.asyncio
    async def test_uses_provided_session(self, engine, stores) -> None:
        """Engine uses provided session instead of loading."""
        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-456",
            config_version=1,
            turn_count=10,
        )

        result = await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            session=session,
        )

        assert result.response is not None
        # Session passed in should be updated
        assert session.turn_count == 11


class TestHistoryLoading:
    """Tests for history loading from AuditStore."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.fixture
    def engine(self, stores):
        return AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

    @pytest.mark.asyncio
    async def test_loads_history_from_audit_store(self, engine, stores) -> None:
        """Engine loads conversation history from AuditStore."""
        tenant_id = uuid4()
        agent_id = uuid4()
        session_id = uuid4()

        # Create previous turn records
        for i in range(3):
            turn_record = TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=i + 1,
                user_message=f"User message {i}",
                agent_response=f"Agent response {i}",
                latency_ms=100,
                tokens_used=50,
                timestamp=datetime.now(UTC),
            )
            await stores["audit"].save_turn(turn_record)

        # Create session
        session = Session(
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-789",
            config_version=1,
        )
        await stores["session"].save(session)

        # Process turn - history should be loaded
        result = await engine.process_turn(
            message="New message",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result.response is not None

    @pytest.mark.asyncio
    async def test_uses_provided_history(self, engine, stores) -> None:
        """Engine uses provided history instead of loading."""
        tenant_id = uuid4()
        agent_id = uuid4()

        history = [
            Turn(role="user", content="Previous question"),
            Turn(role="assistant", content="Previous answer"),
        ]

        result = await engine.process_turn(
            message="Follow-up",
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            history=history,
            persist=False,
        )

        assert result.response is not None


class TestSessionStateUpdates:
    """Tests for session state updates after processing."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_updates_turn_count(self, stores) -> None:
        """Session turn_count is incremented after processing."""
        tenant_id = uuid4()
        agent_id = uuid4()

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-1",
            config_version=1,
            turn_count=0,
        )
        await stores["session"].save(session)

        await engine.process_turn(
            message="First message",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        updated = await stores["session"].get(session.session_id)
        assert updated.turn_count == 1

        # Process another turn
        await engine.process_turn(
            message="Second message",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        updated = await stores["session"].get(session.session_id)
        assert updated.turn_count == 2

    @pytest.mark.asyncio
    async def test_updates_rule_fires(self, stores) -> None:
        """Session tracks rule fire counts."""
        tenant_id = uuid4()
        agent_id = uuid4()

        rule = RuleFactory.create(
            tenant_id=tenant_id,
            agent_id=agent_id,
            embedding=[0.1, 0.2, 0.3],
        )
        await stores["config"].save_rule(rule)

        # Create executors that match the rule
        extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"})
        filter_resp = json.dumps({
            "evaluations": [
                {"rule_id": str(rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}
            ]
        })

        context_executor = MockLLMExecutor([extraction_resp])
        filter_executor = MockLLMExecutor([filter_resp])
        gen_executor = MockLLMExecutor(["Response with matched rule"])

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
            executors={
                "context_extraction": context_executor,
                "rule_filtering": filter_executor,
                "generation": gen_executor,
            },
        )

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-2",
            config_version=1,
        )
        await stores["session"].save(session)

        await engine.process_turn(
            message="Message that matches rule",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        updated = await stores["session"].get(session.session_id)
        rule_key = str(rule.id)
        assert rule_key in updated.rule_fires
        assert updated.rule_fires[rule_key] == 1
        assert rule_key in updated.rule_last_fire_turn
        assert updated.rule_last_fire_turn[rule_key] == 1

    @pytest.mark.asyncio
    async def test_updates_last_activity(self, stores) -> None:
        """Session last_activity_at is updated."""
        tenant_id = uuid4()
        agent_id = uuid4()

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-3",
            config_version=1,
        )
        original_activity = session.last_activity_at
        await stores["session"].save(session)

        await engine.process_turn(
            message="Hello",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        updated = await stores["session"].get(session.session_id)
        assert updated.last_activity_at >= original_activity


class TestTurnRecordPersistence:
    """Tests for turn record creation and persistence."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.fixture
    def engine(self, stores):
        return AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

    @pytest.mark.asyncio
    async def test_creates_turn_record(self, engine, stores) -> None:
        """Turn record is created and saved to AuditStore."""
        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-audit-1",
            config_version=1,
        )
        await stores["session"].save(session)

        result = await engine.process_turn(
            message="Test message for audit",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Verify turn record was saved
        turn_record = await stores["audit"].get_turn(result.turn_id)
        assert turn_record is not None
        assert turn_record.user_message == "Test message for audit"
        assert turn_record.agent_response == result.response
        assert turn_record.session_id == session.session_id
        assert turn_record.tenant_id == tenant_id
        assert turn_record.agent_id == agent_id

    @pytest.mark.asyncio
    async def test_turn_record_has_correct_turn_number(self, engine, stores) -> None:
        """Turn record has correct turn number from session."""
        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-audit-2",
            config_version=1,
            turn_count=5,
        )
        await stores["session"].save(session)

        result = await engine.process_turn(
            message="Message",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        turn_record = await stores["audit"].get_turn(result.turn_id)
        assert turn_record.turn_number == 6  # After increment

    @pytest.mark.asyncio
    async def test_turn_record_has_latency(self, engine, stores) -> None:
        """Turn record captures processing latency."""
        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-audit-3",
            config_version=1,
        )
        await stores["session"].save(session)

        result = await engine.process_turn(
            message="Message",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        turn_record = await stores["audit"].get_turn(result.turn_id)
        # latency_ms can be 0 for very fast executions (sub-millisecond)
        assert turn_record.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_persist_false_skips_audit(self, engine, stores) -> None:
        """Setting persist=False skips audit store."""
        tenant_id = uuid4()
        agent_id = uuid4()

        result = await engine.process_turn(
            message="No audit message",
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=False,
        )

        # Should not be in audit store
        turn_record = await stores["audit"].get_turn(result.turn_id)
        assert turn_record is None

    @pytest.mark.asyncio
    async def test_multiple_turns_create_history(self, engine, stores) -> None:
        """Multiple turns create retrievable history."""
        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-audit-4",
            config_version=1,
        )
        await stores["session"].save(session)

        # Process 3 turns
        for i in range(3):
            await engine.process_turn(
                message=f"Message {i}",
                session_id=session.session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

        # Verify all turns are in history
        turns = await stores["audit"].list_turns_by_session(session.session_id)
        assert len(turns) == 3
        assert turns[0].user_message == "Message 0"
        assert turns[1].user_message == "Message 1"
        assert turns[2].user_message == "Message 2"


class TestScenarioStateUpdates:
    """Tests for scenario navigation state updates."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_apply_scenario_start(self, stores) -> None:
        """Scenario start updates session state."""
        from ruche.alignment.engine import AlignmentEngine

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()
        scenario_id = uuid4()
        step_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-scenario-1",
            config_version=1,
        )

        result = ScenarioFilterResult(
            action=ScenarioAction.START,
            scenario_id=scenario_id,
            target_step_id=step_id,
            confidence=0.9,
        )

        engine._apply_scenario_result(session, result)

        assert session.active_scenario_id == scenario_id
        assert session.active_step_id == step_id
        assert len(session.step_history) == 1
        assert session.step_history[0].step_id == step_id

    @pytest.mark.asyncio
    async def test_apply_scenario_exit(self, stores) -> None:
        """Scenario exit clears session state."""
        from ruche.alignment.engine import AlignmentEngine

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-scenario-2",
            config_version=1,
            active_scenario_id=uuid4(),
            active_step_id=uuid4(),
        )

        result = ScenarioFilterResult(
            action=ScenarioAction.EXIT,
            scenario_id=session.active_scenario_id,
        )

        engine._apply_scenario_result(session, result)

        assert session.active_scenario_id is None
        assert session.active_step_id is None

    @pytest.mark.asyncio
    async def test_apply_scenario_relocalize_increments_count(self, stores) -> None:
        """Relocalization increments the counter."""
        from ruche.alignment.engine import AlignmentEngine

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-scenario-3",
            config_version=1,
            relocalization_count=0,
        )

        result = ScenarioFilterResult(
            action=ScenarioAction.RELOCALIZE,
            scenario_id=uuid4(),
            target_step_id=uuid4(),
            confidence=0.8,
        )

        engine._apply_scenario_result(session, result)

        assert session.relocalization_count == 1


class TestScenarioTransition:
    """Tests for scenario transition action."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_apply_scenario_transition(self, stores) -> None:
        """Scenario transition updates step without changing scenario."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()
        scenario_id = uuid4()
        old_step_id = uuid4()
        new_step_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-transition",
            config_version=1,
            active_scenario_id=scenario_id,
            active_step_id=old_step_id,
        )

        result = ScenarioFilterResult(
            action=ScenarioAction.TRANSITION,
            scenario_id=scenario_id,
            target_step_id=new_step_id,
            confidence=0.85,
            reasoning="User completed step",
        )

        engine._apply_scenario_result(session, result)

        assert session.active_scenario_id == scenario_id  # Unchanged
        assert session.active_step_id == new_step_id  # Updated
        assert len(session.step_history) == 1
        assert session.step_history[0].step_id == new_step_id
        assert session.step_history[0].transition_reason == "User completed step"


class TestStepHistoryTrimming:
    """Tests for step history size limits."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_step_history_trimmed_at_max(self, stores) -> None:
        """Step history is trimmed when exceeding max size."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        # Create session with 100 steps already
        from datetime import UTC, datetime

        from ruche.conversation.models import StepVisit

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-history-trim",
            config_version=1,
            step_history=[
                StepVisit(
                    step_id=uuid4(),
                    entered_at=datetime.now(UTC),
                    turn_number=i,
                    transition_reason="test",
                    confidence=0.9,
                )
                for i in range(100)
            ],
        )

        # Add one more step via scenario result
        result = ScenarioFilterResult(
            action=ScenarioAction.START,
            scenario_id=uuid4(),
            target_step_id=uuid4(),
            confidence=0.9,
        )

        engine._apply_scenario_result(session, result)

        # Should be trimmed to 100 (keeping most recent)
        assert len(session.step_history) == 100


class TestToolOutputVariables:
    """Tests for tool outputs updating session variables."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_tool_outputs_update_session_variables(self, stores) -> None:
        """Tool outputs are stored in session variables."""
        from ruche.alignment.context.situation_snapshot import SituationSnapshot
        from ruche.alignment.execution import ToolExecutor
        from ruche.alignment.filtering.models import MatchedRule
        from ruche.config.models.pipeline import PipelineConfig, ToolExecutionConfig

        tenant_id = uuid4()
        agent_id = uuid4()

        # Create a rule with attached tool
        rule = RuleFactory.create(
            tenant_id=tenant_id,
            agent_id=agent_id,
            embedding=[0.1, 0.2, 0.3],
            attached_tool_ids=["test_tool"],
        )
        await stores["config"].save_rule(rule)

        # Create tool that returns outputs
        async def test_tool(snapshot: SituationSnapshot, matched: MatchedRule) -> dict[str, object]:
            return {"extracted_name": "John", "extracted_email": "john@example.com"}

        test_tool.__name__ = "test_tool"

        tool_executor = ToolExecutor(
            tools={"test_tool": test_tool},
            timeout_ms=5000,
        )

        # Create executors that match the rule
        extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"})
        filter_resp = json.dumps({
            "evaluations": [
                {"rule_id": str(rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}
            ]
        })

        context_executor = MockLLMExecutor([extraction_resp])
        filter_executor = MockLLMExecutor([filter_resp])
        gen_executor = MockLLMExecutor(["Response with tool result"])

        pipeline_config = PipelineConfig(
            tool_execution=ToolExecutionConfig(enabled=True),
        )

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=pipeline_config,
            tool_executor=tool_executor,
            executors={
                "context_extraction": context_executor,
                "rule_filtering": filter_executor,
                "generation": gen_executor,
            },
        )

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-tool-outputs",
            config_version=1,
        )
        await stores["session"].save(session)

        await engine.process_turn(
            message="Extract info from this",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        updated = await stores["session"].get(session.session_id)
        assert "extracted_name" in updated.variables
        assert updated.variables["extracted_name"] == "John"
        assert "extracted_email" in updated.variables
        assert updated.variables["extracted_email"] == "john@example.com"


class TestMemoryRetrieverIntegration:
    """Tests for memory retriever branch in retrieval."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_memory_retrieval_included_in_result(self, stores) -> None:
        """Memory episodes are retrieved when memory_store provided."""
        from datetime import UTC, datetime

        from ruche.memory.models import Episode
        from ruche.memory.stores.inmemory import InMemoryMemoryStore

        memory_store = InMemoryMemoryStore()
        tenant_id = uuid4()
        agent_id = uuid4()
        group_id = f"{tenant_id}:{agent_id}"

        # Add an episode with embedding
        episode = Episode(
            group_id=group_id,
            content="User previously mentioned they like pizza",
            source="agent",
            occurred_at=datetime.now(UTC),
            embedding=[0.1, 0.2, 0.3],
        )
        await memory_store.add_episode(episode)

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            memory_store=memory_store,
            pipeline_config=PipelineConfig(),
        )

        result = await engine.process_turn(
            message="What food do I like?",
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=False,
        )

        # Memory episodes should be in retrieval result
        assert result.retrieval is not None
        assert len(result.retrieval.memory_episodes) > 0
        assert result.retrieval.memory_episodes[0].content == "User previously mentioned they like pizza"


class TestScenarioFilteringDisabled:
    """Tests for scenario filtering disabled path."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_scenario_filtering_disabled_returns_none(self, stores) -> None:
        """Scenario result is None when filtering disabled."""
        from ruche.config.models.pipeline import (
            PipelineConfig,
            ScenarioFilteringConfig,
        )

        pipeline_config = PipelineConfig(
            scenario_filtering=ScenarioFilteringConfig(enabled=False),
        )

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=pipeline_config,
        )

        result = await engine.process_turn(
            message="Hello",
            session_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            persist=False,
        )

        assert result.scenario_result is None


class TestRerankerCreation:
    """Tests for reranker initialization."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_reranker_created_when_provider_and_config_enabled(self, stores) -> None:
        """Reranker is created when rerank_provider provided and enabled."""
        from ruche.config.models.pipeline import PipelineConfig, RerankingConfig, RetrievalConfig
        from ruche.providers.rerank.mock import MockRerankProvider

        rerank_provider = MockRerankProvider()

        pipeline_config = PipelineConfig(
            retrieval=RetrievalConfig(
                rule_reranking=RerankingConfig(enabled=True, top_k=5),
            ),
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        # Create a rule with embedding
        rule = RuleFactory.create(
            tenant_id=tenant_id,
            agent_id=agent_id,
            embedding=[0.1, 0.2, 0.3],
        )
        await stores["config"].save_rule(rule)

        # Create executors that match the rule
        extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"})
        filter_resp = json.dumps({
            "evaluations": [
                {"rule_id": str(rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}
            ]
        })

        context_executor = MockLLMExecutor([extraction_resp])
        filter_executor = MockLLMExecutor([filter_resp])
        gen_executor = MockLLMExecutor(["Test response"])

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors={
                "context_extraction": context_executor,
                "rule_filtering": filter_executor,
                "generation": gen_executor,
            },
            session_store=stores["session"],
            audit_store=stores["audit"],
            rerank_provider=rerank_provider,
            pipeline_config=pipeline_config,
        )

        await engine.process_turn(
            message="Test reranking",
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=False,
        )

        # Reranker should have been called
        assert len(rerank_provider.call_history) > 0


class TestEnforcementFallback:
    """Tests for enforcement fallback handler."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_fallback_handler_used_when_enforcement_fails(self, stores) -> None:
        """Fallback handler is invoked when enforcement validation fails."""
        from ruche.alignment.enforcement import EnforcementValidator, FallbackHandler
        from ruche.alignment.generation import PromptBuilder, ResponseGenerator
        from ruche.alignment.models.enums import TemplateResponseMode
        from ruche.alignment.models import Template
        from ruche.config.models.pipeline import EnforcementConfig, PipelineConfig

        tenant_id = uuid4()
        agent_id = uuid4()

        # Create a fallback template FIRST
        fallback_template = Template(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="safe_fallback",
            text="I cannot help with that request.",
            mode=TemplateResponseMode.FALLBACK,
        )
        await stores["config"].save_template(fallback_template)

        # Create a hard constraint rule with attached fallback template
        hard_rule = RuleFactory.create(
            tenant_id=tenant_id,
            agent_id=agent_id,
            embedding=[0.1, 0.2, 0.3],
            is_hard_constraint=True,
            action_text="prohibited phrase",  # Response will contain this
            attached_template_ids=[fallback_template.id],
        )
        await stores["config"].save_rule(hard_rule)

        # Create executors that match the rule and generate violating response
        extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral"})
        filter_resp = json.dumps({
            "evaluations": [
                {"rule_id": str(hard_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}
            ]
        })

        context_executor = MockLLMExecutor([extraction_resp])
        filter_executor = MockLLMExecutor([filter_resp])
        gen_executor = MockLLMExecutor(["This response contains prohibited phrase"])  # Violates hard constraint

        prompt_builder = PromptBuilder()
        response_generator = ResponseGenerator(
            llm_executor=gen_executor,
            prompt_builder=prompt_builder,
        )
        enforcement_validator = EnforcementValidator(
            response_generator=response_generator,
            agent_config_store=stores["config"],
            max_retries=0,  # Don't retry, go straight to fallback
        )
        fallback_handler = FallbackHandler()

        pipeline_config = PipelineConfig(
            enforcement=EnforcementConfig(enabled=True),
        )

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=pipeline_config,
            enforcement_validator=enforcement_validator,
            fallback_handler=fallback_handler,
            executors={
                "context_extraction": context_executor,
                "rule_filtering": filter_executor,
                "generation": gen_executor,
            },
        )

        result = await engine.process_turn(
            message="Trigger violation",
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=False,
        )

        # The fallback should have been applied
        assert result.enforcement is not None
        assert result.enforcement.fallback_used is True
        assert result.response == "I cannot help with that request."


class TestEngineWithoutAuditStore:
    """Tests for engine behavior when no audit store is provided."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
        }

    @pytest.mark.asyncio
    async def test_engine_works_without_audit_store(self, stores) -> None:
        """Engine works correctly when no audit_store is provided."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=None,  # No audit store
            pipeline_config=PipelineConfig(),
        )

        tenant_id = uuid4()
        agent_id = uuid4()

        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.API,
            user_channel_id="user-no-audit",
            config_version=1,
        )
        await stores["session"].save(session)

        result = await engine.process_turn(
            message="Hello without audit",
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Should still work without audit store
        assert result.response is not None
        assert result.turn_id is not None

        # Session should still be updated
        updated = await stores["session"].get(session.session_id)
        assert updated.turn_count == 1

    @pytest.mark.asyncio
    async def test_load_history_without_audit_store_returns_empty(self, stores) -> None:
        """_load_history returns empty list when no audit_store."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=None,
            pipeline_config=PipelineConfig(),
        )

        # Directly call _load_history
        history = await engine._load_history(uuid4())
        assert history == []

    @pytest.mark.asyncio
    async def test_persist_turn_record_without_audit_store_returns(self, stores) -> None:
        """_persist_turn_record is no-op when no audit_store."""
        from ruche.alignment.context.situation_snapshot import SituationSnapshot
        from ruche.alignment.generation.models import GenerationResult
        from ruche.alignment.result import AlignmentResult
        from ruche.alignment.retrieval.models import RetrievalResult

        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=None,
            pipeline_config=PipelineConfig(),
        )

        # Create minimal result
        result = AlignmentResult(
            turn_id=uuid4(),
            session_id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            user_message="test",
            snapshot=SituationSnapshot(
                message="test",
                embedding=[0.1, 0.2, 0.3],
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
            ),
            retrieval=RetrievalResult(),
            matched_rules=[],
            tool_results=[],
            generation=GenerationResult(response="test", generation_time_ms=0),
            response="test",
            pipeline_timings=[],
            total_time_ms=0,
        )
        generation_result = GenerationResult(response="test", generation_time_ms=0)

        # Should return without error
        await engine._persist_turn_record(result, None, generation_result)


class TestMemoryContextBuilding:
    """Tests for memory context string building."""

    @pytest.fixture
    def stores(self):
        return {
            "config": InMemoryAgentConfigStore(),
            "session": InMemorySessionStore(),
            "audit": InMemoryAuditStore(),
        }

    @pytest.mark.asyncio
    async def test_build_memory_context_formats_episodes(self, stores) -> None:
        """Memory context is formatted from episodes."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        from ruche.alignment.retrieval.models import ScoredEpisode

        episodes = [
            ScoredEpisode(
                episode_id=uuid4(),
                content="User likes coffee",
                score=0.9,
            ),
            ScoredEpisode(
                episode_id=uuid4(),
                content="User works remotely",
                score=0.85,
            ),
        ]

        context = engine._build_memory_context(episodes)

        assert context is not None
        assert "Recent relevant memories:" in context
        assert "User likes coffee" in context
        assert "User works remotely" in context

    @pytest.mark.asyncio
    async def test_build_memory_context_empty_returns_none(self, stores) -> None:
        """Memory context is None when no episodes."""
        engine = AlignmentEngine(
            config_store=stores["config"],
            embedding_provider=MockEmbeddingProvider(),
            executors=create_test_executors(),
            session_store=stores["session"],
            audit_store=stores["audit"],
            pipeline_config=PipelineConfig(),
        )

        context = engine._build_memory_context([])

        assert context is None
