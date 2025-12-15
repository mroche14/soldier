"""End-to-end test for AlignmentEngine.

Tests the full pipeline with a mock agent configuration.
Run with: uv run pytest tests/e2e/test_alignment_engine_e2e.py -v -s
"""

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

# Load .env file before any skipif checks
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import pytest

from ruche.brains.focal.engine import AlignmentEngine
from ruche.brains.focal.models import Rule, Scenario, ScenarioStep, Template, Scope
from ruche.brains.focal.stores.inmemory import InMemoryAgentConfigStore
from ruche.config.models.pipeline import PipelineConfig
from ruche.conversation.models import Session, SessionStatus, Channel
from ruche.conversation.stores.inmemory import InMemorySessionStore
from ruche.interlocutor_data.stores.inmemory import InMemoryInterlocutorDataStore
from ruche.observability.logging import setup_logging, get_logger
from ruche.infrastructure.providers.embedding.mock import MockEmbeddingProvider
from ruche.infrastructure.providers.llm import create_executor

# Configure logging for test visibility
setup_logging(level="DEBUG")
logger = get_logger(__name__)


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def interlocutor_id():
    """Test customer ID."""
    return uuid4()


@pytest.fixture
def session_id():
    """Test session ID."""
    return uuid4()


@pytest.fixture
def config_store():
    """Create in-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def session_store():
    """Create in-memory session store."""
    return InMemorySessionStore()


@pytest.fixture
def profile_store():
    """Create in-memory profile store."""
    return InMemoryInterlocutorDataStore()


@pytest.fixture
def embedding_provider():
    """Create mock embedding provider."""
    return MockEmbeddingProvider(dimensions=1024)


@pytest.fixture
async def sample_rules(config_store, tenant_id, agent_id):
    """Create sample rules in the store."""
    rules = [
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Greeting Rule",
            condition_text="User sends a greeting or says hello",
            action_text="Respond with a friendly greeting and ask how you can help",
            priority=100,
            enabled=True,
            is_hard_constraint=False,
            scope=Scope.GLOBAL,
            condition_embedding=[0.1] * 1024,  # Mock embedding
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Order Status Rule",
            condition_text="User asks about their order status or tracking",
            action_text="Ask for the order number and provide status information",
            priority=90,
            enabled=True,
            is_hard_constraint=False,
            scope=Scope.GLOBAL,
            condition_embedding=[0.2] * 1024,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="No Profanity Rule",
            condition_text="User message or response contains profanity",
            action_text="NEVER use profanity in responses. Always maintain professional language.",
            priority=100,  # Max allowed priority
            enabled=True,
            is_hard_constraint=True,  # Hard constraint
            scope=Scope.GLOBAL,
            condition_embedding=[0.3] * 1024,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]

    for rule in rules:
        await config_store.save_rule(rule)

    logger.info("sample_rules_created", count=len(rules))
    return rules


@pytest.fixture
async def sample_scenario(config_store, tenant_id, agent_id):
    """Create a sample scenario in the store."""
    scenario_id = uuid4()
    entry_step_id = uuid4()
    step2_id = uuid4()
    scenario = Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Order Support Flow",
        description="Handle customer order inquiries",
        entry_step_id=entry_step_id,
        entry_condition_text="User asks about an order",
        entry_condition_embedding=[0.25] * 1024,
        version=1,
        enabled=True,
        steps=[
            ScenarioStep(
                id=entry_step_id,
                scenario_id=scenario_id,
                name="Collect Order Number",
                description="Ask for and validate order number",
                order=1,
                instructions="Ask the customer for their order number in format ORD-XXXXX",
                is_checkpoint=False,
                is_entry=True,
            ),
            ScenarioStep(
                id=step2_id,
                scenario_id=scenario_id,
                name="Provide Status",
                description="Look up and provide order status",
                order=2,
                instructions="Look up the order and provide current status",
                is_checkpoint=False,
                is_terminal=True,
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    await config_store.save_scenario(scenario)
    logger.info("sample_scenario_created", scenario_id=str(scenario.id))
    return scenario


@pytest.fixture
async def sample_templates(config_store, tenant_id, agent_id):
    """Create sample templates in the store."""
    templates = [
        Template(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="fallback_response",
            text="I apologize, but I'm having trouble understanding. Could you please rephrase your question?",
            mode="FALLBACK",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]

    for template in templates:
        await config_store.save_template(template)

    logger.info("sample_templates_created", count=len(templates))
    return templates


@pytest.fixture
async def sample_session(session_store, tenant_id, agent_id, interlocutor_id, session_id):
    """Create a sample session."""
    session = Session(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        interlocutor_id=interlocutor_id,
        channel=Channel.API,
        user_channel_id="test-user-123",
        config_version=1,
        status=SessionStatus.ACTIVE,
        turn_count=0,
        variables={},
        rule_fires={},
        rule_last_fire_turn={},
        variable_updated_at={},
        step_history=[],
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
    )

    await session_store.save(session)
    logger.info("sample_session_created", session_id=str(session_id))
    return session


def get_pipeline_config(use_mock: bool = True) -> PipelineConfig:
    """Get pipeline config - mock or real LLM."""
    if use_mock:
        # Use mock for fast testing
        return PipelineConfig()
    else:
        # Use real LLM (openrouter/groq/chatgpt-oss-120b)
        return PipelineConfig.model_validate({
            "situation_sensor": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
            },
            "rule_filtering": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
            },
            "generation": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
            },
        })


class TestAlignmentEngineE2E:
    """End-to-end tests for AlignmentEngine."""

    @pytest.mark.asyncio
    async def test_greeting_message(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_templates,
        sample_session,
    ):
        """Test processing a simple greeting message."""
        # Create mock executors for testing without real LLM
        executors = {
            "context_extraction": create_executor("mock/default", step_name="context_extraction"),
            "situation_sensor": create_executor("mock/default", step_name="situation_sensor"),
            "rule_filtering": create_executor("mock/default", step_name="rule_filtering"),
            "generation": create_executor("mock/default", step_name="generation"),
        }

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=PipelineConfig(),
            executors=executors,
        )

        # Process a greeting message
        result = await engine.process_turn(
            message="Hello! How are you?",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=True,
        )

        logger.info(
            "turn_result",
            turn_id=str(result.turn_id),
            response_length=len(result.response),
            matched_rules=len(result.matched_rules),
            total_time_ms=result.total_time_ms,
            pipeline_steps=[t.step for t in result.pipeline_timings],
        )

        # Assertions
        assert result.response is not None
        assert len(result.response) > 0
        assert result.turn_id is not None
        assert result.total_time_ms > 0

        # Check pipeline steps executed
        step_names = [t.step for t in result.pipeline_timings]
        assert "situation_sensor" in step_names
        assert "retrieval" in step_names
        assert "generation" in step_names

    @pytest.mark.asyncio
    async def test_order_inquiry(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_templates,
        sample_session,
    ):
        """Test processing an order inquiry message."""
        executors = {
            "context_extraction": create_executor("mock/default", step_name="context_extraction"),
            "situation_sensor": create_executor("mock/default", step_name="situation_sensor"),
            "rule_filtering": create_executor("mock/default", step_name="rule_filtering"),
            "generation": create_executor("mock/default", step_name="generation"),
        }

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=PipelineConfig(),
            executors=executors,
        )

        # Process order inquiry
        result = await engine.process_turn(
            message="Where is my order? I placed it last week.",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=True,
        )

        logger.info(
            "order_inquiry_result",
            turn_id=str(result.turn_id),
            response=result.response[:200] if result.response else None,
            matched_rules=len(result.matched_rules),
            scenario_result=result.scenario_result.action if result.scenario_result else None,
        )

        # Assertions
        assert result.response is not None
        assert result.turn_id is not None

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_templates,
        sample_session,
    ):
        """Test a multi-turn conversation."""
        executors = {
            "context_extraction": create_executor("mock/default", step_name="context_extraction"),
            "situation_sensor": create_executor("mock/default", step_name="situation_sensor"),
            "rule_filtering": create_executor("mock/default", step_name="rule_filtering"),
            "generation": create_executor("mock/default", step_name="generation"),
        }

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=PipelineConfig(),
            executors=executors,
        )

        messages = [
            "Hi there!",
            "I need help with my order",
            "The order number is ORD-12345",
        ]

        results = []
        for i, message in enumerate(messages):
            result = await engine.process_turn(
                message=message,
                session_id=session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                persist=True,
            )
            results.append(result)

            logger.info(
                f"turn_{i+1}_result",
                message=message,
                response_preview=result.response[:100] if result.response else None,
                matched_rules=len(result.matched_rules),
            )

        # Verify session was updated
        updated_session = await session_store.get(session_id)
        assert updated_session is not None
        assert updated_session.turn_count == 3

        logger.info(
            "multi_turn_complete",
            total_turns=len(results),
            final_turn_count=updated_session.turn_count,
        )


class TestAlignmentEngineWithRealLLM:
    """E2E tests using real LLM (requires API key)."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set"
    )
    async def test_real_llm_greeting(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_templates,
        sample_session,
    ):
        """Test with real LLM (openrouter/openai/gpt-oss-120b)."""
        # Create real LLM executors
        pipeline_config = PipelineConfig.model_validate({
            "situation_sensor": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
                "temperature": 0.0,
            },
            "rule_filtering": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
            },
            "generation": {
                "enabled": True,
                "model": "openrouter/openai/gpt-oss-120b",
                "temperature": 0.7,
            },
        })

        from ruche.infrastructure.providers.llm import create_executors_from_pipeline_config
        executors = create_executors_from_pipeline_config(pipeline_config)

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=pipeline_config,
            executors=executors,
        )

        # Process a greeting message
        result = await engine.process_turn(
            message="Hello! I'm looking for help with my order.",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=True,
        )

        logger.info(
            "real_llm_result",
            turn_id=str(result.turn_id),
            response=result.response,
            matched_rules=len(result.matched_rules),
            total_time_ms=result.total_time_ms,
            pipeline_timings={t.step: t.duration_ms for t in result.pipeline_timings},
        )

        # Assertions
        assert result.response is not None
        assert len(result.response) > 10  # Should be a real response
        assert result.total_time_ms > 0

        print(f"\n{'='*60}")
        print(f"REAL LLM RESPONSE:")
        print(f"{'='*60}")
        print(result.response)
        print(f"{'='*60}")
        print(f"Total time: {result.total_time_ms:.2f}ms")
        print(f"Matched rules: {len(result.matched_rules)}")
        for timing in result.pipeline_timings:
            if not timing.skipped:
                print(f"  {timing.step}: {timing.duration_ms:.2f}ms")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
