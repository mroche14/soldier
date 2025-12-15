# Turn Brain

The complete request lifecycle for processing a single user message.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TURN BRAIN                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. RECEIVE         Validate request, load session                          │
│         │                                                                    │
│         ▼                                                                    │
│ 1b. RECONCILE       Handle scenario updates (if version changed)            │
│                     → Evaluate upstream forks, gap fill, teleport           │
│         │                                                                    │
│         ▼                                                                    │
│  2. EXTRACT         Understand user intent from message + history           │
│     CONTEXT         → LLM or embedding-based                                │
│         │                                                                    │
│         ▼                                                                    │
│  3. RETRIEVE        Find candidate rules, scenarios, memory                 │
│     CANDIDATES      → Vector search + business filters                      │
│         │                                                                    │
│         ▼                                                                    │
│  4. RERANK          Score and order candidates                              │
│                     → Reranker model (optional)                             │
│         │                                                                    │
│         ▼                                                                    │
│  5. RULE FILTER     Judge which rules apply (RuleFilter)                    │
│                     → Fast LLM decides rule relevance                       │
│         │                                                                    │
│         ▼                                                                    │
│ 5b. SCENARIO        Determine step navigation (ScenarioFilter)              │
│     FILTER          → Graph-aware, handles transitions + re-localization   │
│         │                                                                    │
│         ▼                                                                    │
│  6. EXECUTE         Run tools from matched rules                            │
│     TOOLS           → Resolve variables                                     │
│         │                                                                    │
│         ▼                                                                    │
│  7. GENERATE        Build prompt, call LLM                                  │
│     RESPONSE        → Main generation model                                 │
│         │                                                                    │
│         ▼                                                                    │
│  8. ENFORCE         Validate against hard constraints                       │
│                     → Regenerate or fallback if needed                      │
│         │                                                                    │
│         ▼                                                                    │
│  9. PERSIST         Update session, log turn, ingest memory                 │
│         │                                                                    │
│         ▼                                                                    │
│ 10. RESPOND         Return to client                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **Key Design Points**:
> - **Step 1b (Reconcile)**: Handles scenario version changes before processing. Evaluates upstream forks added since session started, teleports if needed, runs gap fill for missing data. See [scenario-update-methods.md](./scenario-update-methods.md).
> - **Steps 5 and 5b** are **separate filters** with distinct responsibilities:
>   - **RuleFilter** (5): Decides which rules apply to this turn
>   - **ScenarioFilter** (5b): Decides step navigation in graph-based scenarios
>
> See [alignment-engine.md](../architecture/alignment-engine.md) for the full scenario navigation algorithm.

## Provider Configuration

Each step can use different models/providers:

```toml
[brain.context_extraction]
llm_provider = "anthropic"
llm_model = "claude-3-haiku"           # Fast, cheap
# OR embedding-only mode (no LLM)
mode = "llm"  # "llm" | "embedding_only" | "disabled"

[brain.retrieval]
embedding_provider = "openai"
embedding_model = "text-embedding-3-small"
top_k = 20

[brain.reranking]
enabled = true
rerank_provider = "cohere"
rerank_model = "rerank-english-v3.0"
top_k = 10

# Step 5: Rule filtering (which rules apply?)
[brain.rule_filter]
enabled = true
llm_provider = "anthropic"
llm_model = "claude-3-haiku"           # Fast for yes/no
max_rules = 10

# Step 5b: Scenario filtering (graph navigation)
# See alignment-engine.md for full algorithm
[brain.scenario_filter]
# Transition thresholds
transition_threshold = 0.65            # Min score to consider transition
sanity_threshold = 0.35                # If all below, something's wrong
min_margin = 0.1                       # Required margin over runner-up

# LLM adjudication for ambiguous transitions
llm_adjudication_enabled = true
llm_provider = "anthropic"
llm_model = "claude-3-haiku"

# Loop detection
max_loop_iterations = 5
loop_detection_window = 10

# Re-localization (recovery from inconsistent state)
relocalization_enabled = true
relocalization_threshold = 0.7
relocalization_trigger_turns = 3
max_relocalization_hops = 3

[brain.generation]
llm_provider = "anthropic"
llm_model = "claude-sonnet-4-5-20250514"  # Best quality
temperature = 0.7
max_tokens = 1024

[brain.enforcement]
self_critique_enabled = false
llm_provider = "anthropic"
llm_model = "claude-3-haiku"
```

---

## Step-by-Step

### 1. Receive Request

```python
async def process_turn(request: ChatRequest) -> ChatResponse:
    """Entry point for turn processing."""

    # Validate
    if not request.message.strip():
        raise InvalidRequestError("Empty message")

    # Extract tenant from auth
    tenant_id = extract_tenant(request.auth_token)

    # Load or create session (via SessionStore)
    session = await session_store.get(request.session_id)
    if not session:
        session = Session(
            session_id=request.session_id,
            tenant_id=tenant_id,
            agent_id=request.agent_id,
        )

    # Load agent config (via ConfigStore)
    agent_config = await config_store.get_agent(tenant_id, request.agent_id)
    pipeline_config = agent_config.brain

    # Start timing
    start_time = time.monotonic()
    turn_id = generate_turn_id()
```

---

### 2. Extract Context

**Purpose**: Understand what the user actually wants, considering conversation history.

```python
async def extract_context(
    message: str,
    session: Session,
    config: ContextExtractionConfig,
) -> Context:
    """
    Extract user intent and context from message + history.

    Providers:
    - LLMExecutor: Full understanding via LLM
    - EmbeddingProvider: Lightweight embedding-only mode
    """

    # Get recent conversation history
    history = await session_store.get_recent_turns(
        session.session_id,
        limit=config.history_turns  # e.g., last 5 turns
    )

    if config.mode == "llm":
        # Use LLM to understand intent
        llm = get_llm_provider(config.llm_provider, config.llm_model)

        prompt = CONTEXT_EXTRACTION_PROMPT.format(
            history=format_history(history),
            message=message,
            active_scenario=session.active_scenario_id,
        )

        context = await llm.generate_structured(prompt, Context)

    elif config.mode == "embedding_only":
        # Lightweight: just embed message + recent context
        embedder = get_embedding_provider(
            config.embedding_provider,
            config.embedding_model
        )

        context_text = f"{format_history(history[-2:])}\nUser: {message}"
        context = Context(
            user_intent=message,  # Use raw message as intent
            embedding=await embedder.embed(context_text),
            entities=[],
            sentiment=None,
        )

    else:  # disabled
        context = Context(
            user_intent=message,
            embedding=None,
            entities=[],
            sentiment=None,
        )

    return context
```

**Context Model**:

```python
class Context(BaseModel):
    """Extracted context from user message."""

    user_intent: str              # What the user wants
    embedding: list[float] | None # Vector representation
    entities: list[str]           # Mentioned entities (order ID, product, etc.)
    sentiment: str | None         # positive, negative, neutral, frustrated
    topic: str | None             # Categorization
    requires_tool: bool = False   # Hint for tool execution

    # Scenario-related
    scenario_signal: str | None   # "start", "continue", "exit", None
    target_scenario: str | None   # If signal is "start"
```

**Prompt Template** (`alignment/context/prompts/extract_intent.txt`):

```
Analyze this conversation and extract the user's intent.

## Conversation History
{history}

## Current Message
User: {message}

## Current State
Active Scenario: {active_scenario}

## Instructions
1. What does the user want? (be specific)
2. What entities are mentioned? (order IDs, products, names)
3. What is the sentiment? (positive/negative/neutral/frustrated)
4. Should a scenario start, continue, or exit?

Respond in JSON format.
```

---

### 3. Retrieve Candidates

**Purpose**: Find potentially relevant rules, scenarios, and memory.

```python
async def retrieve_candidates(
    context: Context,
    session: Session,
    config: RetrievalConfig,
) -> RetrievalResult:
    """
    Retrieve candidate rules, scenarios, and memory.

    Providers:
    - EmbeddingProvider: For vector search
    - ConfigStore: Rules, scenarios, templates
    - MemoryStore: Episodes, entities
    """

    embedder = get_embedding_provider(
        config.embedding_provider,
        config.embedding_model
    )

    # Get embedding for search (use pre-computed or compute)
    if context.embedding:
        query_embedding = context.embedding
    else:
        query_embedding = await embedder.embed(context.user_intent)

    # Parallel retrieval
    rules_task = retrieve_rules(query_embedding, session, config)
    scenarios_task = retrieve_scenarios(query_embedding, session, config)
    memory_task = retrieve_memory(query_embedding, session, config)

    rules, scenarios, memory = await asyncio.gather(
        rules_task, scenarios_task, memory_task
    )

    return RetrievalResult(
        candidate_rules=rules,
        candidate_scenarios=scenarios,
        memory_context=memory,
    )


async def retrieve_rules(
    query_embedding: list[float],
    session: Session,
    config: RetrievalConfig,
) -> list[CandidateRule]:
    """Retrieve rules by scope and similarity."""

    candidates = []

    # Global rules
    global_rules = await config_store.vector_search_rules(
        query_embedding=query_embedding,
        tenant_id=session.tenant_id,
        agent_id=session.agent_id,
        scope="global",
        limit=config.top_k,
    )
    candidates.extend(global_rules)

    # Scenario-scoped rules (if in scenario)
    if session.active_scenario_id:
        scenario_rules = await config_store.vector_search_rules(
            query_embedding=query_embedding,
            tenant_id=session.tenant_id,
            agent_id=session.agent_id,
            scope="scenario",
            scope_id=session.active_scenario_id,
            limit=config.top_k,
        )
        candidates.extend(scenario_rules)

    # Step-scoped rules (if in step)
    if session.active_step_id:
        step_rules = await config_store.vector_search_rules(
            query_embedding=query_embedding,
            tenant_id=session.tenant_id,
            agent_id=session.agent_id,
            scope="step",
            scope_id=session.active_step_id,
            limit=config.top_k,
        )
        candidates.extend(step_rules)

    # Apply business filters
    candidates = apply_business_filters(candidates, session)

    return candidates


def apply_business_filters(
    candidates: list[CandidateRule],
    session: Session,
) -> list[CandidateRule]:
    """Filter by enabled, max fires, cooldown."""

    filtered = []
    for rule in candidates:
        if not rule.enabled:
            continue

        fires = session.rule_fires.get(str(rule.id), 0)
        if rule.max_fires_per_session > 0 and fires >= rule.max_fires_per_session:
            continue

        last_fire = session.rule_last_fire_turn.get(str(rule.id), 0)
        if session.turn_count - last_fire < rule.cooldown_turns:
            continue

        filtered.append(rule)

    return filtered
```

---

### 4. Rerank Candidates

**Purpose**: Use a reranking model to improve ordering.

```python
async def rerank_candidates(
    context: Context,
    candidates: RetrievalResult,
    config: RerankingConfig,
) -> RetrievalResult:
    """
    Rerank candidates using a dedicated reranker model.

    Providers:
    - RerankProvider: Cohere, Voyage, CrossEncoder
    """

    if not config.enabled:
        return candidates

    reranker = get_rerank_provider(
        config.rerank_provider,
        config.rerank_model
    )

    # Rerank rules
    if candidates.candidate_rules:
        rule_texts = [
            f"{r.condition_text} → {r.action_text}"
            for r in candidates.candidate_rules
        ]

        reranked_indices = await reranker.rerank(
            query=context.user_intent,
            documents=rule_texts,
            top_k=config.top_k,
        )

        candidates.candidate_rules = [
            candidates.candidate_rules[i] for i in reranked_indices
        ]

    # Similarly for scenarios and memory...

    return candidates
```

---

### 5. Rule Filter (LLM)

**Purpose**: Use LLM to judge which rules actually apply.

> **Note**: This is the **RuleFilter**, which is separate from the **ScenarioFilter**.
> RuleFilter decides which rules apply; ScenarioFilter decides step navigation.
> See [alignment-engine.md](../architecture/alignment-engine.md) for the full separation of concerns.

```python
async def filter_rules(
    context: Context,
    candidates: list[CandidateRule],
    session: Session,
    config: RuleFilterConfig,
) -> RuleFilterResult:
    """
    Use LLM to filter rules.

    This filter ONLY decides which rules apply.
    It provides a coarse scenario_signal hint, but step navigation
    is handled by the dedicated ScenarioFilter (step 5b).

    Providers:
    - LLMExecutor: Fast model for yes/no decisions
    """

    if not config.enabled:
        return RuleFilterResult(
            matched_rules=candidates[:config.max_rules],
            scenario_signal=None,  # Let ScenarioFilter decide
        )

    llm = get_llm_provider(config.llm_provider, config.llm_model)

    rules_text = "\n".join([
        f"Rule {i+1}: IF '{r.condition_text}' THEN '{r.action_text}'"
        for i, r in enumerate(candidates)
    ])

    prompt = RULE_FILTER_PROMPT.format(
        user_intent=context.user_intent,
        sentiment=context.sentiment,
        rules=rules_text,
    )

    result = await llm.generate_structured(prompt, RuleFilterDecision)

    matched_rules = [
        candidates[i] for i in result.applicable_rule_indices
        if i < len(candidates)
    ]

    return RuleFilterResult(
        matched_rules=matched_rules,
        scenario_signal=result.scenario_signal,  # Coarse hint: "start" | "exit" | None
        reasoning=result.reasoning,
    )
```

**Prompt Template** (`alignment/filtering/prompts/filter_rules.txt`):

```
You are evaluating which rules apply to a user's message.

## User Intent
{user_intent}

## Sentiment
{sentiment}

## Candidate Rules
{rules}

## Instructions
1. Which rules actually apply? (list indices, 1-based)
2. Coarse scenario signal: is the user starting a new flow, exiting, or neither?
3. Brief reasoning.

Only select rules that CLEARLY match the user's intent.
False positives are worse than false negatives.

Respond in JSON:
{
  "applicable_rule_indices": [1, 3],
  "scenario_signal": null,  // "start" | "exit" | null (step navigation handled separately)
  "reasoning": "..."
}
```

---

### 5b. Scenario Filter (Graph Navigation)

**Purpose**: Determine step transitions in graph-based scenarios.

> **This is a dedicated filter**, separate from rule filtering.
> See [alignment-engine.md](../architecture/alignment-engine.md) "Scenario Navigation" for the full algorithm,
> including re-localization for recovery from inconsistent state.

```python
async def filter_scenario(
    context: Context,
    session: Session,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """
    Determine scenario step navigation.

    This filter handles:
    - Local transition evaluation (outgoing edges from current step)
    - LLM adjudication when multiple transitions match
    - Re-localization when state is inconsistent
    - Loop detection

    Only called when session.active_scenario_id is set.
    """

    if not session.active_scenario_id:
        # Not in a scenario - check if we should start one
        return await check_scenario_entry(context, session, config)

    # Load scenario and current step
    scenario = await config_store.get_scenario(session.active_scenario_id)
    current_step = scenario.get_step(session.active_step_id)

    # Delegate to ScenarioFilter (see alignment-engine.md for full implementation)
    return await evaluate_scenario(
        context=context,
        scenario=scenario,
        current_step=current_step,
        session=session,
        config=config,
    )


async def check_scenario_entry(
    context: Context,
    session: Session,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """Check if conversation should enter a scenario."""

    # Vector search scenarios by entry condition
    candidates = await config_store.vector_search_scenarios(
        query_embedding=context.embedding,
        tenant_id=session.tenant_id,
        agent_id=session.agent_id,
        limit=5,
    )

    if not candidates:
        return ScenarioFilterResult(
            scenario_action="none",
            target_scenario_id=None,
            target_step_id=None,
            confidence=1.0,
            reasoning="No scenario entry conditions matched",
        )

    # Check if best match is above threshold
    best = candidates[0]
    if best.score >= config.entry_threshold:
        scenario = await config_store.get_scenario(best.scenario_id)
        return ScenarioFilterResult(
            scenario_action="start",
            target_scenario_id=scenario.id,
            target_step_id=scenario.entry_step_id,
            confidence=best.score,
            reasoning=f"Matched scenario '{scenario.name}' entry condition",
        )

    return ScenarioFilterResult(
        scenario_action="none",
        target_scenario_id=None,
        target_step_id=None,
        confidence=1.0 - best.score,
        reasoning=f"Best scenario match {best.score:.2f} below threshold",
    )
```

**Key behaviors** (see alignment-engine.md for full details):

| Situation | Action |
|-----------|--------|
| Not in scenario, entry matches | **Start** scenario at entry_step_id |
| In scenario, transition matches | **Transition** to target step |
| In scenario, no transition matches | **Continue** in current step |
| Terminal step, no match | **Exit** scenario |
| State inconsistent | **Relocalize** or exit |

---

### 6. Execute Tools

**Purpose**: Run tools attached to matched rules.

```python
async def execute_tools(
    matched_rules: list[MatchedRule],
    context: Context,
    session: Session,
) -> list[ToolResult]:
    """
    Execute tools from matched rules.

    Tool execution is deterministic - only runs if rule matched.
    """

    tool_results = []

    for rule in matched_rules:
        for tool_id in rule.attached_tool_ids:
            tool = await tool_registry.get(tool_id)

            # Resolve tool inputs from context/session
            inputs = resolve_tool_inputs(tool, context, session)

            try:
                result = await tool.execute(inputs, timeout=tool.timeout_ms)
                tool_results.append(ToolResult(
                    tool_id=tool_id,
                    rule_id=rule.id,
                    inputs=inputs,
                    output=result,
                    success=True,
                ))

                # Update session variables with tool output
                update_session_variables(session, tool, result)

            except ToolExecutionError as e:
                tool_results.append(ToolResult(
                    tool_id=tool_id,
                    rule_id=rule.id,
                    inputs=inputs,
                    error=str(e),
                    success=False,
                ))

    return tool_results
```

---

### 7. Generate Response

**Purpose**: Build the prompt and generate the response.

```python
async def generate_response(
    context: Context,
    matched_rules: list[MatchedRule],
    memory_context: MemoryContext,
    tool_results: list[ToolResult],
    session: Session,
    config: GenerationConfig,
) -> GenerationResult:
    """
    Generate the agent response.

    Providers:
    - LLMExecutor: Main generation model (best quality)
    """

    # Check for EXCLUSIVE template (bypasses LLM)
    exclusive_template = find_exclusive_template(matched_rules, session)
    if exclusive_template:
        rendered = render_template(exclusive_template, session.variables)
        return GenerationResult(
            response=rendered,
            template_used=exclusive_template.id,
            llm_called=False,
        )

    # Build prompt
    prompt = build_prompt(
        context=context,
        matched_rules=matched_rules,
        memory_context=memory_context,
        tool_results=tool_results,
        session=session,
        templates=find_suggest_templates(matched_rules, session),
    )

    # Call LLM
    llm = get_llm_provider(config.llm_provider, config.llm_model)

    response = await llm.generate(
        prompt=prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

    return GenerationResult(
        response=response.text,
        llm_called=True,
        tokens_used=response.usage.total_tokens,
    )


def build_prompt(
    context: Context,
    matched_rules: list[MatchedRule],
    memory_context: MemoryContext,
    tool_results: list[ToolResult],
    session: Session,
    templates: list[Template],
) -> str:
    """Assemble the full prompt for the LLM."""

    sections = []

    # System prompt
    sections.append(SYSTEM_PROMPT)

    # Active rules
    if matched_rules:
        rules_text = "\n".join([
            f"- {r.action_text}" for r in matched_rules
        ])
        sections.append(f"## Active Rules\n{rules_text}")

    # Scenario context
    if session.active_scenario_id:
        scenario = get_scenario(session.active_scenario_id)
        step = get_step(scenario, session.active_step_id)
        sections.append(f"## Current Flow\nScenario: {scenario.name}\nStep: {step.name}\n{step.description}")

    # Memory context
    if memory_context.episodes:
        memory_text = "\n".join([
            f"- {ep.content}" for ep in memory_context.episodes[:5]
        ])
        sections.append(f"## Relevant History\n{memory_text}")

    # Tool results
    if tool_results:
        tools_text = "\n".join([
            f"- {r.tool_id}: {r.output}" for r in tool_results if r.success
        ])
        sections.append(f"## Tool Results\n{tools_text}")

    # Suggested templates
    if templates:
        templates_text = "\n".join([
            f"- {t.name}: {t.text}" for t in templates
        ])
        sections.append(f"## Suggested Responses\n{templates_text}")

    # Variables
    if session.variables:
        vars_text = "\n".join([
            f"- {k}: {v}" for k, v in session.variables.items()
        ])
        sections.append(f"## Known Information\n{vars_text}")

    # User message
    sections.append(f"## User Message\n{context.user_intent}")

    return "\n\n".join(sections)
```

---

### 8. Enforce Constraints

**Purpose**: Validate response against hard constraints.

```python
async def enforce_constraints(
    response: str,
    matched_rules: list[MatchedRule],
    context: Context,
    config: EnforcementConfig,
) -> EnforcementResult:
    """
    Validate response against hard constraint rules.

    Providers:
    - LLMExecutor: For self-critique (optional)
    """

    hard_rules = [r for r in matched_rules if r.is_hard_constraint]

    if not hard_rules:
        return EnforcementResult(
            response=response,
            passed=True,
            regenerated=False,
        )

    # Check each hard constraint
    for rule in hard_rules:
        if violates_constraint(response, rule):
            # Try regeneration with stronger prompt
            new_response = await regenerate_with_constraint(
                response, rule, context, config
            )

            if violates_constraint(new_response, rule):
                # Fall back to safe template
                fallback = get_fallback_template(rule)
                if fallback:
                    return EnforcementResult(
                        response=render_template(fallback, {}),
                        passed=False,
                        regenerated=True,
                        fallback_used=fallback.id,
                    )
            else:
                response = new_response

    # Optional: self-critique
    if config.self_critique_enabled:
        critique = await self_critique(response, matched_rules, config)
        if not critique.passed:
            response = await regenerate_from_critique(
                response, critique, config
            )

    return EnforcementResult(
        response=response,
        passed=True,
        regenerated=False,
    )
```

---

### 9. Persist State

**Purpose**: Update session, log turn, ingest to memory.

```python
async def persist_state(
    session: Session,
    turn_id: str,
    request: ChatRequest,
    response: str,
    matched_rules: list[MatchedRule],
    tool_results: list[ToolResult],
    scenario_before: dict,
    scenario_result: ScenarioFilterResult,
    start_time: float,
    tokens_used: int,
):
    """
    Persist all state changes.

    Stores:
    - SessionStore: Session state
    - AuditStore: Turn record
    - MemoryStore: Episode ingestion (async)

    Note: Scenario state (active_scenario_id, active_step_id) is already
    updated by apply_scenario_result() before this function is called.
    """

    # Update session state
    session.turn_count += 1
    session.last_activity_at = datetime.utcnow()

    # Update rule fires
    for rule in matched_rules:
        rule_id = str(rule.id)
        session.rule_fires[rule_id] = session.rule_fires.get(rule_id, 0) + 1
        session.rule_last_fire_turn[rule_id] = session.turn_count

    # Save session (via SessionStore)
    # Note: Scenario step already updated by apply_scenario_result()
    await session_store.save(session)

    # Create turn record
    turn = TurnRecord(
        turn_id=turn_id,
        tenant_id=session.tenant_id,
        agent_id=session.agent_id,
        session_id=session.session_id,
        turn_number=session.turn_count,
        user_message=request.message,
        agent_response=response,
        matched_rule_ids=[r.id for r in matched_rules],
        tool_calls=tool_results,
        scenario_before=scenario_before,
        scenario_after={
            "id": session.active_scenario_id,
            "step": session.active_step_id,
        },
        latency_ms=int((time.monotonic() - start_time) * 1000),
        tokens_used=tokens_used,
        timestamp=datetime.utcnow(),
    )

    # Save turn record (via AuditStore)
    await audit_store.save(turn)

    # Ingest to memory (async, don't block response)
    asyncio.create_task(
        ingest_to_memory(session, request.message, response)
    )


async def ingest_to_memory(
    session: Session,
    user_message: str,
    agent_response: str,
):
    """Add conversation turn to long-term memory."""

    group_id = f"{session.tenant_id}:{session.session_id}"

    # Create episode for user message
    user_episode = Episode(
        group_id=group_id,
        content=user_message,
        content_type="user_message",
        source="user",
        occurred_at=datetime.utcnow(),
    )

    # Create episode for agent response
    agent_episode = Episode(
        group_id=group_id,
        content=agent_response,
        content_type="agent_message",
        source="agent",
        occurred_at=datetime.utcnow(),
    )

    # Compute embeddings and save (via MemoryStore)
    await memory_store.add_episode(user_episode)
    await memory_store.add_episode(agent_episode)

    # Extract entities (optional, can be async background job)
    # entities = await entity_extractor.extract(user_message + " " + agent_response)
    # for entity in entities:
    #     await memory_store.add_entity(entity)
```

---

### 10. Return Response

```python
    return ChatResponse(
        response=response,
        turn_id=turn_id,
        session_id=session.session_id,
        scenario={
            "id": session.active_scenario_id,
            "step": session.active_step_id,
        } if session.active_scenario_id else None,
        matched_rules=[r.id for r in matched_rules],
        tools_called=[r.tool_id for r in tool_results],
        latency_ms=latency_ms,
    )
```

---

## Full Brain Orchestration

```python
async def process_turn(request: ChatRequest) -> ChatResponse:
    """Complete turn processing brain."""

    # 1. Receive
    session, agent_config, turn_id, start_time = await receive_request(request)
    brain = agent_config.brain

    # 2. Extract Context
    context = await extract_context(
        message=request.message,
        session=session,
        config=brain.context_extraction,
    )

    # 3. Retrieve Candidates
    candidates = await retrieve_candidates(
        context=context,
        session=session,
        config=brain.retrieval,
    )

    # 4. Rerank
    candidates = await rerank_candidates(
        context=context,
        candidates=candidates,
        config=brain.reranking,
    )

    # 5. Rule Filter (which rules apply?)
    rule_filter_result = await filter_rules(
        context=context,
        candidates=candidates.candidate_rules,
        session=session,
        config=brain.rule_filter,
    )

    # 5b. Scenario Filter (graph navigation)
    # See alignment-engine.md for full algorithm including re-localization
    scenario_before = {
        "scenario_id": session.active_scenario_id,
        "step_id": session.active_step_id,
    }

    scenario_result = await filter_scenario(
        context=context,
        session=session,
        config=brain.scenario_filter,
    )

    # Apply scenario navigation result to session
    await apply_scenario_result(session, scenario_result)

    # 6. Execute Tools
    tool_results = await execute_tools(
        matched_rules=rule_filter_result.matched_rules,
        context=context,
        session=session,
    )

    # 7. Generate Response
    generation = await generate_response(
        context=context,
        matched_rules=rule_filter_result.matched_rules,
        memory_context=candidates.memory_context,
        tool_results=tool_results,
        session=session,
        config=brain.generation,
    )

    # 8. Enforce Constraints
    enforcement = await enforce_constraints(
        response=generation.response,
        matched_rules=rule_filter_result.matched_rules,
        context=context,
        config=brain.enforcement,
    )

    # 9. Persist
    await persist_state(
        session=session,
        turn_id=turn_id,
        request=request,
        response=enforcement.response,
        matched_rules=rule_filter_result.matched_rules,
        tool_results=tool_results,
        scenario_before=scenario_before,
        scenario_result=scenario_result,
        start_time=start_time,
        tokens_used=generation.tokens_used,
    )

    # 10. Return
    return build_response(session, enforcement.response, turn_id, start_time)


async def apply_scenario_result(
    session: Session,
    result: ScenarioFilterResult,
    scenario: Scenario | None = None,
):
    """Apply scenario navigation result to session state.

    Args:
        session: The session to update
        result: The ScenarioFilter decision
        scenario: The scenario object (needed for "start" to capture version)
    """

    if result.scenario_action == "start":
        session.active_scenario_id = result.target_scenario_id
        session.active_step_id = result.target_step_id
        session.active_scenario_version = scenario.version if scenario else None
        session.relocalization_count = 0
        session.step_history.append(StepVisit(
            step_id=result.target_step_id,
            entered_at=datetime.utcnow(),
            turn_number=session.turn_count,
            transition_reason="entry",
            confidence=result.confidence,
        ))

    elif result.scenario_action == "transition":
        session.active_step_id = result.target_step_id
        session.step_history.append(StepVisit(
            step_id=result.target_step_id,
            entered_at=datetime.utcnow(),
            turn_number=session.turn_count,
            transition_reason=f"transition:{result.reasoning}",
            confidence=result.confidence,
        ))

    elif result.scenario_action == "relocalize":
        session.active_step_id = result.target_step_id
        session.relocalization_count += 1
        session.step_history.append(StepVisit(
            step_id=result.target_step_id,
            entered_at=datetime.utcnow(),
            turn_number=session.turn_count,
            transition_reason="relocalize",
            confidence=result.confidence,
        ))

    elif result.scenario_action == "exit":
        session.active_scenario_id = None
        session.active_step_id = None
        session.active_scenario_version = None
        session.relocalization_count = 0

    # Bound history size
    if len(session.step_history) > Session.MAX_STEP_HISTORY:
        session.step_history = session.step_history[-Session.MAX_STEP_HISTORY:]
```

---

## Latency Breakdown

Target: < 1600ms end-to-end (with both filters)

| Step | Target | Provider | Notes |
|------|--------|----------|-------|
| 1. Receive | 10ms | SessionStore | Session lookup |
| 2. Context Extraction | 200ms | LLM (Haiku) | Can disable for speed |
| 3. Retrieval | 50ms | Embedding + Stores | Parallel queries |
| 4. Reranking | 100ms | Reranker | Can disable |
| 5. Rule Filter | 150ms | LLM (Haiku) | Can disable |
| 5b. Scenario Filter | 100ms | Embedding + LLM | LLM only if ambiguous |
| 6. Tool Execution | 200ms | External APIs | Depends on tools |
| 7. Generation | 500ms | LLM (Sonnet) | Main model |
| 8. Enforcement | 50ms | - | Usually no regen |
| 9. Persist | 30ms | All Stores | Async where possible |

**Fast mode** (disable context extraction + rule filter LLM): ~1000ms
**Full mode** (all steps): ~1500ms

---

## Configuration Modes

### Minimal (Fastest)

```toml
[brain.context_extraction]
mode = "disabled"

[brain.reranking]
enabled = false

[brain.rule_filter]
enabled = false

[brain.scenario_filter]
llm_adjudication_enabled = false   # Embedding-only
relocalization_enabled = false

[brain.generation]
llm_model = "claude-3-haiku"
```

### Balanced (Recommended)

```toml
[brain.context_extraction]
mode = "llm"
llm_model = "claude-3-haiku"

[brain.reranking]
enabled = true

[brain.rule_filter]
enabled = true
llm_model = "claude-3-haiku"

[brain.scenario_filter]
llm_adjudication_enabled = true
llm_model = "claude-3-haiku"
relocalization_enabled = true

[brain.generation]
llm_model = "claude-sonnet-4-5-20250514"
```

### Maximum Quality

```toml
[brain.context_extraction]
mode = "llm"
llm_model = "claude-sonnet-4-5-20250514"

[brain.reranking]
enabled = true

[brain.rule_filter]
enabled = true
llm_model = "claude-sonnet-4-5-20250514"

[brain.scenario_filter]
llm_adjudication_enabled = true
llm_model = "claude-sonnet-4-5-20250514"
relocalization_enabled = true
relocalization_threshold = 0.8   # Higher threshold for better precision

[brain.generation]
llm_model = "claude-sonnet-4-5-20250514"

[brain.enforcement]
self_critique_enabled = true
```
