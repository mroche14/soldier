"""Real end-to-end test with actual LLM, embedding, and rerank providers.

Run with: uv run pytest tests/e2e/test_real_pipeline.py -v -s
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.models import Rule, Scenario, ScenarioStep, Template, Scope
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore
from soldier.config.models.pipeline import OpenRouterProviderConfig, PipelineConfig
from soldier.conversation.models import Session, SessionStatus, Channel
from soldier.conversation.stores.inmemory import InMemorySessionStore
from soldier.customer_data.stores.inmemory import InMemoryCustomerDataStore
from soldier.observability.logging import setup_logging, get_logger
from soldier.providers.embedding.jina import JinaEmbeddingProvider
from soldier.providers.rerank.jina import JinaRerankProvider
from soldier.providers.llm import create_executor

# Configure logging
setup_logging(level="INFO")
logger = get_logger(__name__)


# Skip if API keys not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY") or not os.environ.get("JINA_API_KEY"),
    reason="OPENROUTER_API_KEY and JINA_API_KEY required"
)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def customer_id():
    return uuid4()


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def config_store():
    return InMemoryAgentConfigStore()


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.fixture
def profile_store():
    return InMemoryCustomerDataStore()


@pytest.fixture
def embedding_provider():
    """Create real Jina embedding provider."""
    return JinaEmbeddingProvider(
        api_key=os.environ["JINA_API_KEY"],
        model="jina-embeddings-v3",
    )


@pytest.fixture
def rerank_provider():
    """Create real Jina rerank provider."""
    return JinaRerankProvider(
        api_key=os.environ["JINA_API_KEY"],
        model="jina-reranker-v2-base-multilingual",
    )


@pytest.fixture
async def sample_rules(config_store, tenant_id, agent_id, embedding_provider):
    """Create sample rules with real embeddings."""
    rules_data = [
        {
            "name": "Greeting Rule",
            "condition_text": "User sends a greeting or says hello",
            "action_text": "Respond with a friendly greeting and ask how you can help today",
            "priority": 80,
            "is_hard_constraint": False,
        },
        {
            "name": "Order Status Rule",
            "condition_text": "User asks about their order status or tracking information",
            "action_text": "Ask for the order number if not provided, then look up and provide status",
            "priority": 90,
            "is_hard_constraint": False,
        },
        {
            "name": "Professional Language Rule",
            "condition_text": "Any customer interaction",
            "action_text": "Always use professional, helpful language. Never be rude or dismissive.",
            "priority": 100,
            "is_hard_constraint": True,
        },
    ]

    rules = []
    for data in rules_data:
        # Get real embedding for condition (embed_query returns list[float])
        embedding = await embedding_provider.embed_query(data["condition_text"])

        rule = Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name=data["name"],
            condition_text=data["condition_text"],
            action_text=data["action_text"],
            priority=data["priority"],
            enabled=True,
            is_hard_constraint=data["is_hard_constraint"],
            scope=Scope.GLOBAL,
            condition_embedding=embedding,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await config_store.save_rule(rule)
        rules.append(rule)

    logger.info("rules_created_with_embeddings", count=len(rules))
    return rules


@pytest.fixture
async def sample_scenario(config_store, tenant_id, agent_id, embedding_provider):
    """Create sample scenario with real embedding."""
    scenario_id = uuid4()
    entry_step_id = uuid4()

    entry_embedding = await embedding_provider.embed_query("User asks about an order")

    scenario = Scenario(
        id=scenario_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Order Support Flow",
        description="Handle customer order inquiries",
        entry_step_id=entry_step_id,
        entry_condition_text="User asks about an order",
        entry_condition_embedding=entry_embedding,
        version=1,
        enabled=True,
        steps=[
            ScenarioStep(
                id=entry_step_id,
                scenario_id=scenario_id,
                name="Collect Order Info",
                description="Get order details from customer",
                order=1,
                instructions="Ask for order number and provide status",
                is_entry=True,
                is_terminal=True,
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    await config_store.save_scenario(scenario)
    logger.info("scenario_created_with_embedding", scenario_id=str(scenario_id))
    return scenario


@pytest.fixture
async def sample_session(session_store, tenant_id, agent_id, customer_id, session_id):
    """Create sample session."""
    session = Session(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        customer_id=customer_id,
        channel=Channel.API,
        user_channel_id="test-user-real",
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
    return session


class TestRealPipeline:
    """End-to-end tests with real providers."""

    @pytest.mark.asyncio
    async def test_real_greeting(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        rerank_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_session,
    ):
        """Test with real LLM, embedding, and rerank."""
        # Use the model from config: openrouter/openai/gpt-oss-120b (cerebras/groq)
        model = "openrouter/openai/gpt-oss-120b"

        # CRITICAL: Must pass provider_order to route to Cerebras/Groq for fast inference
        # Without this, OpenRouter picks ANY provider which can be very slow
        openrouter_config = OpenRouterProviderConfig(
            provider_order=["Cerebras", "Groq", "SambaNova"],
            provider_sort="latency",
            allow_fallbacks=True,
        )

        pipeline_config = PipelineConfig.model_validate({
            # Disable context_extraction - SituationSensor replaces it (per Phase 2 docs)
            "context_extraction": {"enabled": False},
            "situation_sensor": {"enabled": True},
            "retrieval": {"enabled": True, "top_k": 5},
            "reranking": {"enabled": True, "top_k": 3},
            "rule_filtering": {"enabled": True},
            "generation": {"enabled": True, "temperature": 0.7},
        })

        # Create executors for each step - pass openrouter_config for fast provider routing
        executors = {
            "context_extraction": create_executor(model, step_name="context_extraction", openrouter_config=openrouter_config),
            "situation_sensor": create_executor(model, step_name="situation_sensor", openrouter_config=openrouter_config),
            "rule_filtering": create_executor(model, step_name="rule_filtering", openrouter_config=openrouter_config),
            "generation": create_executor(model, step_name="generation", openrouter_config=openrouter_config),
        }

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            rerank_provider=rerank_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=pipeline_config,
            executors=executors,
        )

        # Test greeting
        print("\n" + "="*70)
        print("TEST: Greeting Message")
        print("="*70)

        result = await engine.process_turn(
            message="Hello! I need some help today.",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=True,
        )

        print(f"\nRESPONSE:\n{result.response}")
        print(f"\n{'='*70}")
        print("PIPELINE LATENCIES:")
        print("="*70)
        for timing in result.pipeline_timings:
            status = "SKIPPED" if timing.skipped else f"{timing.duration_ms:.2f}ms"
            print(f"  {timing.step:25} {status}")
        print(f"  {'─'*40}")
        print(f"  {'TOTAL':25} {result.total_time_ms:.2f}ms")
        print(f"\nMatched Rules: {len(result.matched_rules)}")
        for mr in result.matched_rules:
            score = getattr(mr, 'relevance_score', getattr(mr, 'match_score', 0.0))
            print(f"  - {mr.rule.name} (score: {score:.2f})")

        assert result.response is not None
        assert len(result.response) > 20
        assert result.total_time_ms > 0

    @pytest.mark.asyncio
    async def test_real_order_inquiry(
        self,
        config_store,
        session_store,
        profile_store,
        embedding_provider,
        rerank_provider,
        tenant_id,
        agent_id,
        session_id,
        sample_rules,
        sample_scenario,
        sample_session,
    ):
        """Test order inquiry with real providers."""
        # Use the model from config: openrouter/openai/gpt-oss-120b (cerebras/groq)
        model = "openrouter/openai/gpt-oss-120b"

        # CRITICAL: Must pass provider_order to route to Cerebras/Groq for fast inference
        openrouter_config = OpenRouterProviderConfig(
            provider_order=["Cerebras", "Groq", "SambaNova"],
            provider_sort="latency",
            allow_fallbacks=True,
        )

        pipeline_config = PipelineConfig.model_validate({
            # Disable context_extraction - SituationSensor replaces it (per Phase 2 docs)
            "context_extraction": {"enabled": False},
            "situation_sensor": {"enabled": True},
            "retrieval": {"enabled": True, "top_k": 5},
            "reranking": {"enabled": True, "top_k": 3},
            "rule_filtering": {"enabled": True},
            "generation": {"enabled": True},
        })

        # Pass openrouter_config for fast provider routing
        executors = {
            "context_extraction": create_executor(model, step_name="context_extraction", openrouter_config=openrouter_config),
            "situation_sensor": create_executor(model, step_name="situation_sensor", openrouter_config=openrouter_config),
            "rule_filtering": create_executor(model, step_name="rule_filtering", openrouter_config=openrouter_config),
            "generation": create_executor(model, step_name="generation", openrouter_config=openrouter_config),
        }

        engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            rerank_provider=rerank_provider,
            session_store=session_store,
            profile_store=profile_store,
            pipeline_config=pipeline_config,
            executors=executors,
        )

        print("\n" + "="*70)
        print("TEST: Order Status Inquiry")
        print("="*70)

        result = await engine.process_turn(
            message="Where is my order? I ordered something last week and haven't received it.",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            persist=True,
        )

        print(f"\nRESPONSE:\n{result.response}")
        print(f"\n{'='*70}")
        print("PIPELINE LATENCIES:")
        print("="*70)
        for timing in result.pipeline_timings:
            status = "SKIPPED" if timing.skipped else f"{timing.duration_ms:.2f}ms"
            print(f"  {timing.step:25} {status}")
        print(f"  {'─'*40}")
        print(f"  {'TOTAL':25} {result.total_time_ms:.2f}ms")
        print(f"\nMatched Rules: {len(result.matched_rules)}")
        for mr in result.matched_rules:
            score = getattr(mr, 'relevance_score', getattr(mr, 'match_score', 0.0))
            print(f"  - {mr.rule.name} (score: {score:.2f})")
        if result.scenario_result:
            print(f"\nScenario: {result.scenario_result.action}")

        assert result.response is not None
        assert result.total_time_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
