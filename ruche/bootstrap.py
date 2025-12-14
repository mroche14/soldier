"""Bootstrap module for easy Focal setup.

Provides a simple way to initialize the full Focal stack from config,
primarily for notebooks and quick testing. Handles:
- Loading configuration from TOML files
- Creating appropriate stores (in-memory or production)
- Creating providers (embedding, rerank, LLM)
- Creating the AlignmentEngine with all dependencies

Example usage:

    from ruche.bootstrap import bootstrap

    engine, ctx = bootstrap()

    result = await engine.process_turn(
        message="Hello!",
        session_id=ctx.session_id,
        tenant_id=ctx.tenant_id,
        agent_id=ctx.agent_id,
    )
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.stores.inmemory import InMemoryAgentConfigStore
from ruche.config.models.pipeline import OpenRouterProviderConfig, PipelineConfig
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.stores.inmemory import InMemorySessionStore
from ruche.customer_data.stores.inmemory import InMemoryCustomerDataStore
from ruche.observability.logging import get_logger, setup_logging
from ruche.providers.embedding.jina import JinaEmbeddingProvider
from ruche.providers.llm import create_executor, create_executors_from_pipeline_config
from ruche.providers.rerank.jina import JinaRerankProvider

logger = get_logger(__name__)


@dataclass
class BootstrapContext:
    """Context returned from bootstrap with IDs and stores.

    Provides easy access to IDs and stores for testing.
    """

    tenant_id: UUID
    agent_id: UUID
    session_id: UUID
    customer_id: UUID
    config_store: InMemoryAgentConfigStore
    session_store: InMemorySessionStore
    profile_store: InMemoryCustomerDataStore
    embedding_provider: JinaEmbeddingProvider | None
    rerank_provider: JinaRerankProvider | None
    pipeline_config: PipelineConfig


def bootstrap(
    tenant_id: UUID | None = None,
    agent_id: UUID | None = None,
    session_id: UUID | None = None,
    customer_id: UUID | None = None,
    log_level: str = "INFO",
    model: str | None = None,
    provider_order: list[str] | None = None,
    create_session: bool = True,
) -> tuple[AlignmentEngine, BootstrapContext]:
    """Bootstrap a fully-configured AlignmentEngine.

    Creates all necessary stores, providers, and the engine based on
    environment variables and configuration.

    Args:
        tenant_id: Override tenant ID (default: random UUID)
        agent_id: Override agent ID (default: random UUID)
        session_id: Override session ID (default: random UUID)
        customer_id: Override customer ID (default: random UUID)
        log_level: Logging level (default: INFO)
        model: LLM model to use (default: from env or openrouter/openai/gpt-oss-120b)
        provider_order: OpenRouter provider order (default: ["Cerebras", "Groq", "SambaNova"])
        create_session: Whether to pre-create a session (default: True)

    Returns:
        Tuple of (AlignmentEngine, BootstrapContext)

    Environment variables used:
        JINA_API_KEY: Required for Jina embedding/rerank
        OPENROUTER_API_KEY: Required for OpenRouter LLM calls
        ANTHROPIC_API_KEY: Optional fallback for Anthropic models

    Example:
        engine, ctx = bootstrap()

        result = await engine.process_turn(
            message="Hello!",
            session_id=ctx.session_id,
            tenant_id=ctx.tenant_id,
            agent_id=ctx.agent_id,
        )
    """
    # Setup logging
    setup_logging(level=log_level)

    # Generate IDs
    _tenant_id = tenant_id or uuid4()
    _agent_id = agent_id or uuid4()
    _session_id = session_id or uuid4()
    _customer_id = customer_id or uuid4()

    # Create in-memory stores
    config_store = InMemoryAgentConfigStore()
    session_store = InMemorySessionStore()
    profile_store = InMemoryCustomerDataStore()

    # Create Jina providers (optional - depends on API key)
    embedding_provider = None
    rerank_provider = None

    jina_key = os.environ.get("JINA_API_KEY")
    if jina_key:
        embedding_provider = JinaEmbeddingProvider(
            api_key=jina_key,
            model="jina-embeddings-v3",
        )
        rerank_provider = JinaRerankProvider(
            api_key=jina_key,
            model="jina-reranker-v2-base-multilingual",
        )
        logger.info("jina_providers_created")
    else:
        logger.warning("jina_providers_skipped", reason="JINA_API_KEY not set")

    # Configure LLM
    _model = model or os.environ.get("RUCHE_DEFAULT_MODEL", "openrouter/openai/gpt-oss-120b")
    _provider_order = provider_order or ["Cerebras", "Groq", "SambaNova"]

    openrouter_config = OpenRouterProviderConfig(
        provider_order=_provider_order,
        provider_sort="latency",
        allow_fallbacks=True,
    )

    # Create pipeline config
    pipeline_config = PipelineConfig.model_validate({
        "context_extraction": {"enabled": False},  # Legacy - replaced by situation_sensor
        "situation_sensor": {"enabled": True},
        "retrieval": {"enabled": True, "top_k": 5},
        "rule_filtering": {"enabled": True},
        "generation": {"enabled": True, "temperature": 0.7},
    })

    # Create executors from pipeline config with OpenRouter routing
    executors = {
        "situation_sensor": create_executor(_model, step_name="situation_sensor", openrouter_config=openrouter_config),
        "rule_filtering": create_executor(_model, step_name="rule_filtering", openrouter_config=openrouter_config),
        "generation": create_executor(_model, step_name="generation", openrouter_config=openrouter_config),
    }

    # Create engine
    engine = AlignmentEngine(
        config_store=config_store,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        session_store=session_store,
        profile_store=profile_store,
        pipeline_config=pipeline_config,
        executors=executors,
    )

    logger.info(
        "engine_bootstrapped",
        tenant_id=str(_tenant_id),
        agent_id=str(_agent_id),
        model=_model,
        provider_order=_provider_order,
    )

    # Create context
    ctx = BootstrapContext(
        tenant_id=_tenant_id,
        agent_id=_agent_id,
        session_id=_session_id,
        customer_id=_customer_id,
        config_store=config_store,
        session_store=session_store,
        profile_store=profile_store,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        pipeline_config=pipeline_config,
    )

    # Pre-create session if requested
    if create_session:
        import asyncio

        session = Session(
            session_id=_session_id,
            tenant_id=_tenant_id,
            agent_id=_agent_id,
            customer_id=_customer_id,
            channel=Channel.API,
            user_channel_id="bootstrap-user",
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

        # Run save synchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # In Jupyter notebook with nest_asyncio
            asyncio.ensure_future(session_store.save(session))
        else:
            loop.run_until_complete(session_store.save(session))

        logger.info("session_created", session_id=str(_session_id))

    return engine, ctx


async def create_sample_rule(
    ctx: BootstrapContext,
    name: str,
    condition_text: str,
    action_text: str,
    priority: int = 50,
    is_hard_constraint: bool = False,
):
    """Create a rule with embedding.

    Helper to create rules with real embeddings.

    Args:
        ctx: Bootstrap context
        name: Rule name
        condition_text: When this rule applies
        action_text: What to do when matched
        priority: Rule priority (higher = more important)
        is_hard_constraint: Whether this is a hard constraint

    Returns:
        Created Rule
    """
    from ruche.alignment.models import Rule, Scope

    embedding = None
    if ctx.embedding_provider:
        embedding = await ctx.embedding_provider.embed_query(condition_text)

    rule = Rule(
        id=uuid4(),
        tenant_id=ctx.tenant_id,
        agent_id=ctx.agent_id,
        name=name,
        condition_text=condition_text,
        action_text=action_text,
        priority=priority,
        enabled=True,
        is_hard_constraint=is_hard_constraint,
        scope=Scope.GLOBAL,
        condition_embedding=embedding,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await ctx.config_store.save_rule(rule)
    logger.info("rule_created", name=name, has_embedding=embedding is not None)
    return rule


async def create_sample_scenario(
    ctx: BootstrapContext,
    name: str,
    description: str,
    entry_condition_text: str,
    step_instructions: str,
):
    """Create a simple single-step scenario with embedding.

    Args:
        ctx: Bootstrap context
        name: Scenario name
        description: Scenario description
        entry_condition_text: When to enter this scenario
        step_instructions: Instructions for the step

    Returns:
        Created Scenario
    """
    from ruche.alignment.models import Scenario, ScenarioStep

    scenario_id = uuid4()
    entry_step_id = uuid4()

    entry_embedding = None
    if ctx.embedding_provider:
        entry_embedding = await ctx.embedding_provider.embed_query(entry_condition_text)

    scenario = Scenario(
        id=scenario_id,
        tenant_id=ctx.tenant_id,
        agent_id=ctx.agent_id,
        name=name,
        description=description,
        entry_step_id=entry_step_id,
        entry_condition_text=entry_condition_text,
        entry_condition_embedding=entry_embedding,
        version=1,
        enabled=True,
        steps=[
            ScenarioStep(
                id=entry_step_id,
                scenario_id=scenario_id,
                name="Main Step",
                description=description,
                order=1,
                instructions=step_instructions,
                is_entry=True,
                is_terminal=True,
            ),
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    await ctx.config_store.save_scenario(scenario)
    logger.info("scenario_created", name=name, has_embedding=entry_embedding is not None)
    return scenario


# ============================================================================
# Pipeline Step Visibility Functions
# ============================================================================


def display_result(result, verbose: bool = False):
    """Display a summary of the alignment result.

    Args:
        result: AlignmentResult from process_turn
        verbose: Show additional details
    """
    print(f"Turn ID: {result.turn_id}")
    print(f"Total time: {result.total_time_ms:.2f}ms")
    print(f"\nResponse ({len(result.response)} chars):")
    print("-" * 40)
    print(result.response)
    print("-" * 40)

    if verbose:
        print(f"\nMatched rules: {len(result.matched_rules)}")
        print(f"Scenario result: {result.scenario_result}")
        print(f"Tool results: {len(result.tool_results)}")


def display_snapshot(result):
    """Display the situation snapshot from a result.

    Shows what the situation sensor detected about the user message.
    """
    snap = result.snapshot
    if not snap:
        print("No snapshot available")
        return

    print("=" * 50)
    print("SITUATION SNAPSHOT (Phase 2)")
    print("=" * 50)
    print(f"Message: {snap.message[:100]}{'...' if len(snap.message) > 100 else ''}")
    print(f"Language: {snap.language}")
    print(f"Topic: {snap.topic or 'not detected'}")
    print(f"Topic changed: {snap.topic_changed}")
    print(f"Sentiment: {snap.sentiment.value if snap.sentiment else 'unknown'}")
    print(f"Urgency: {snap.urgency.value if snap.urgency else 'normal'}")
    print(f"Tone: {snap.tone}")
    print(f"Scenario signal: {snap.scenario_signal.value if snap.scenario_signal else 'none'}")
    print(f"Intent changed: {snap.intent_changed}")
    if snap.new_intent_label:
        print(f"New intent: {snap.new_intent_label}")
    if snap.canonical_intent_label:
        print(f"Canonical intent: {snap.canonical_intent_label} (score: {snap.canonical_intent_score:.2f})")
    if snap.situation_facts:
        print(f"Situation facts: {snap.situation_facts}")
    if snap.candidate_variables:
        print(f"Extracted variables:")
        for k, v in snap.candidate_variables.items():
            print(f"  - {k}: {v.value} (scope: {v.scope})")
    print()


def display_retrieval(result):
    """Display retrieval results.

    Shows what rules, scenarios, and intents were retrieved.
    """
    print("=" * 50)
    print("RETRIEVAL RESULTS (Phase 4)")
    print("=" * 50)

    retrieval = result.retrieval
    if not retrieval:
        print("No retrieval data available")
        return

    print(f"Retrieval time: {retrieval.retrieval_time_ms:.2f}ms")
    print(f"\nRules retrieved: {len(retrieval.rules)}")
    for rule in retrieval.rules[:5]:
        print(f"  - [{rule.score:.2f}] {rule.rule_id} ({rule.source})")

    print(f"\nScenarios retrieved: {len(retrieval.scenarios)}")
    for scenario in retrieval.scenarios[:5]:
        print(f"  - [{scenario.score:.2f}] {scenario.scenario_id}")

    print(f"\nIntents retrieved: {len(retrieval.intents)}")
    for intent in retrieval.intents[:5]:
        print(f"  - [{intent.score:.2f}] {intent.intent_id} ({intent.intent_name})")
    print()


def display_filtering(result):
    """Display rule filtering results.

    Shows which rules matched and why.
    """
    print("=" * 50)
    print("RULE FILTERING RESULTS (Phase 5)")
    print("=" * 50)

    matched = result.matched_rules
    print(f"Matched rules: {len(matched)}")
    for m in matched:
        print(f"\n  Rule: {m.rule.name}")
        print(f"  ID: {m.rule.id}")
        print(f"  Relevance: {m.relevance_score:.2f}")
        print(f"  Confidence: {m.confidence_score:.2f}")
        print(f"  Reasoning: {m.reasoning}")
        print(f"  Condition: {m.rule.condition_text}")
        print(f"  Action: {m.rule.action_text}")

    if result.scenario_result:
        print(f"\nScenario action: {result.scenario_result.action}")
        print(f"Scenario ID: {result.scenario_result.scenario_id}")
        if result.scenario_result.reasoning:
            print(f"Reasoning: {result.scenario_result.reasoning}")
    print()


def display_generation(result):
    """Display generation results.

    Shows details about how the response was generated.
    """
    print("=" * 50)
    print("GENERATION RESULTS (Phase 9)")
    print("=" * 50)

    gen = result.generation
    if not gen:
        print("No generation data available")
        return

    print(f"Model: {gen.model}")
    print(f"Generation time: {gen.generation_time_ms:.2f}ms")
    print(f"Tokens - input: {gen.input_tokens or '?'}, output: {gen.output_tokens or '?'}")
    if gen.template_mode:
        print(f"Template mode: {gen.template_mode.value}")

    if result.response_plan:
        print(f"\nResponse type: {result.response_plan.global_response_type.value}")
        if result.response_plan.bullet_points:
            print("Bullet points:")
            for bp in result.response_plan.bullet_points:
                print(f"  - {bp}")
    print()


def display_enforcement(result):
    """Display enforcement/validation results.

    Shows if any constraints were violated.
    """
    print("=" * 50)
    print("ENFORCEMENT RESULTS (Phase 10)")
    print("=" * 50)

    enf = result.enforcement
    if not enf:
        print("No enforcement data available")
        return

    print(f"Is compliant: {enf.is_compliant}")
    print(f"Enforcement time: {enf.enforcement_time_ms:.2f}ms")
    print(f"Violations: {len(enf.violations)}")

    for v in enf.violations:
        print(f"\n  Rule: {v.rule_id}")
        print(f"  Type: {v.violation_type}")
        print(f"  Description: {v.description}")

    if enf.regeneration_attempted:
        print(f"\nRegeneration attempted: {enf.regeneration_succeeded}")
    print()


def display_timings(result):
    """Display pipeline step timings.

    Shows how long each step took.
    """
    print("=" * 50)
    print("PIPELINE TIMINGS")
    print("=" * 50)
    print(f"Total: {result.total_time_ms:.2f}ms\n")

    for timing in result.pipeline_timings:
        if timing.skipped:
            print(f"  {timing.step}: SKIPPED ({timing.skip_reason})")
        else:
            print(f"  {timing.step}: {timing.duration_ms:.2f}ms")
    print()


def display_all(result):
    """Display all pipeline step results.

    Comprehensive view of everything that happened.
    """
    display_snapshot(result)
    display_retrieval(result)
    display_filtering(result)
    display_generation(result)
    display_enforcement(result)
    display_timings(result)
    print("=" * 50)
    print("FINAL RESPONSE")
    print("=" * 50)
    print(result.response)
