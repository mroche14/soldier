> **Status:** HISTORICAL / NOTES. This document assumes an `LLMProvider` abstraction; current Focal uses `LLMExecutor` (Agno-backed) as the single LLM interface.

1. Your abstractions are already good

Things you’ve done right:

LLMProvider is small and focused: generate, generate_stream, generate_structured, count_tokens – exactly what your alignment engine needs.

Pydantic models for messages/responses: makes it easy to log, persist, or wrap into TurnRecord.

Explicit error types: AuthenticationError, RateLimitError, etc. Good for your alignment pipeline to decide what to do on errors.

OpenRouter provider:

Maps directly onto OpenAI-style API.

Normalizes usage into TokenUsage.

Has a structured generation method that wraps JSON schema.

So the foundation is fine. The tweaks are mostly about ergonomics, observability, and future-proofing.

2. Concrete improvements
2.1. LLMMessage & LLMResponse tweaks

a) Make roles stricter + tool role

Right now:

class LLMMessage(BaseModel):
    role: str
    content: str


I’d tighten this to avoid random roles sneaking in, and keep room for tool calls:

from typing import Literal

class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="Role in the conversation"
    )
    content: str = Field(..., description="Message content")


You’ll eventually want "tool" for tool output injected into the conversation.

b) Normalize usage type

You currently have:

usage: TokenUsage | dict[str, int] | None


I’d strongly recommend normalizing to always TokenUsage | None and convert dicts inside providers. That way all your analytics / logging / billing code doesn’t have to check types:

class LLMResponse(BaseModel):
    content: str
    model: str
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_response: dict | None = None


If a provider only gives you a dict, convert it there.

c) Add observability fields

You’re building a serious alignment engine; you’ll want to track latencies and request IDs:

class LLMResponse(BaseModel):
    ...
    latency_ms: float | None = Field(
        default=None, description="End-to-end latency from provider"
    )
    request_id: str | None = Field(
        default=None, description="Provider request ID if available"
    )


Then in each provider, set them when possible.

2.2. LLMProvider interface improvements

Two small but useful things:

a) Allow per-call metadata & tracing

Add optional metadata in the interface so callers (like your AlignmentEngine) can pass tenant/session context that the provider will attach to LLMResponse.metadata (and/or provider request):

async def generate(
    self,
    messages: list[LLMMessage],
    *,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    stop_sequences: list[str] | None = None,
    request_metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> LLMResponse: ...


Same for generate_structured. Inside providers you can attach this to the provider’s metadata field or headers.

This is where you’ll eventually pass things like:

request_metadata = {
    "tenant_id": str(tenant_id),
    "agent_id": str(agent_id),
    "session_id": str(session_id),
    "step": "rule_filtering",
}


b) Streaming type

Returning AsyncIterator[str] is fine. At some point you might want:

AsyncIterator[LLMResponseChunk]


where LLMResponseChunk could include partial usage or provider metadata, but you don’t have to change that now.

2.3. OpenRouterProvider specifics

Overall it’s good. A few concrete upgrades:

2.3.1. Pass through **kwargs to the OpenAI client

Right now you build request_kwargs but ignore custom **kwargs. I’d merge them in after filtering reserved keys:

request_kwargs: dict[str, Any] = {
    "model": model or self._default_model,
    "max_tokens": max_tokens,
    "temperature": temperature,
    "messages": openai_messages,
    "extra_headers": self._get_extra_headers(),
}

if stop_sequences:
    request_kwargs["stop"] = stop_sequences

# Merge additional kwargs, but don't allow overriding core params by accident
for k, v in kwargs.items():
    if k not in request_kwargs:
        request_kwargs[k] = v


So you can do things like:

provider.generate(..., top_p=0.9, presence_penalty=0.2)


and have them go through.

2.3.2. Latency measurement & request_id

Around the API call, add:

import time

start = time.perf_counter()
response = await self._async_client.chat.completions.create(**request_kwargs)
latency_ms = (time.perf_counter() - start) * 1000
request_id = getattr(response, "id", None)


Then put them into LLMResponse:

return LLMResponse(
    content=content,
    model=response.model,
    finish_reason=choice.finish_reason,
    usage=usage,
    latency_ms=latency_ms,
    request_id=request_id,
    raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
)


You already had raw_response, so fill it when you can.

2.3.3. generate_structured should also accept model / kwargs

Currently:

request_kwargs: dict[str, Any] = {
    "model": self._default_model,
    "max_tokens": max_tokens,
    "messages": messages,
    "temperature": 0.0,
    "extra_headers": self._get_extra_headers(),
}


I’d keep it symmetric with generate:

async def generate_structured(
    self,
    prompt: str,
    schema: type[T],
    *,
    system_prompt: str | None = None,
    max_tokens: int = 1024,
    model: str | None = None,
    **kwargs: Any,
) -> tuple[T, LLMResponse]:
    ...
    request_kwargs: dict[str, Any] = {
        "model": model or self._default_model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": 0.0,
        "extra_headers": self._get_extra_headers(),
    }
    # merge kwargs like in generate()


That way your pipeline can choose cheaper models for structured tasks if needed.

2.3.4. JSON parsing robustness

You already handle json blocks, which is nice. One more tiny hardening:

Strip whitespace before json.loads.

Optionally catch and log the raw content when parsing fails (before raising ProviderError), because you’ll want that when debugging failures.

try:
    parsed_dict = json.loads(content.strip())
except json.JSONDecodeError as e:
    logger.error("json_parse_failed", content=content[:500])
    raise ProviderError(f"Failed to parse JSON response: {e}") from e

2.3.5. generate_stream pattern is fine

Your pattern:

def generate_stream(...)-> AsyncIterator[str]:
    return self._generate_stream_impl(...)

async def _generate_stream_impl(...)-> AsyncIterator[str]:
    stream = await self._async_client.chat.completions.create(**request_kwargs)
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


is technically correct: _generate_stream_impl is an async generator, and returning it from a sync method that advertises AsyncIterator[str] is exactly what callers expect (async for token in provider.generate_stream(...): ...).

If you later want to stream also usage/metadata, you could yield e.g. LLMResponse-like chunks, but you’re fine for now.

3. How this helps you plug Agno later

Given this LLMProvider interface, an AgnoProvider becomes pretty trivial:

from agno.agent import Agent
from agno.models.openai import OpenAIChat  # or Anthropic, etc.

class AgnoProvider(LLMProvider):
    def __init__(self, default_model: str):
        self._default_model = default_model
        self._agent = Agent(
            name="alignment_llm",
            model=OpenAIChat(id=default_model),
            add_history_to_context=False,
            markdown=False,
        )

    @property
    def provider_name(self) -> str:
        return "agno"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        request_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # Optionally switch model
        if model and model != self._default_model:
            self._agent.model = OpenAIChat(id=model)

        # Convert messages to whatever Agno expects (depends on version)
        history = [{"role": m.role, "content": m.content} for m in messages]

        start = time.perf_counter()
        run = await self._agent.arun(
            input=history,
            max_tokens=max_tokens,
            temperature=temperature,
            # Thread tenant/session here via request_metadata if you want
            session_state=request_metadata or {},
        )
        latency_ms = (time.perf_counter() - start) * 1000

        text = run.output_text  # or equivalent, depending on Agno version

        # You might not have token usage here initially – set to None or estimate
        return LLMResponse(
            content=text,
            model=model or self._default_model,
            finish_reason="stop",
            usage=None,
            latency_ms=latency_ms,
            metadata=request_metadata or {},
            raw_response=run.model_dump() if hasattr(run, "model_dump") else None,
        )

    # generate_stream / generate_structured could be no-op or not implemented at first


Because all your alignment components only depend on LLMProvider, you can swap in OpenRouterProvider, AgnoProvider, or a composite provider that chooses per-step model.

If you want, next step we can do a tiny refactor of one of your LLM-using classes (e.g. ContextExtractor) to show exactly how to pass tenant_id, agent_id, session_id down to the LLMProvider.generate via request_metadata, so your Agno integration and OpenRouter logging both get rich context automatically.

You said:
cant  Agno be more integrated than this ?
ChatGPT said:
Thought for 1m 28s

Yeah, Agno can absolutely be way more integrated than “just another LLMProvider”. What I gave you before was the minimal integration. You can push it at least two more levels deeper.

Let me structure it so you can decide how far you want to go.

Mental model: three integration levels

Think of it like this:

Level 1 – Thin integration
Agno is just a fancy LLMProvider (what we discussed): you keep your AlignmentEngine as-is and swap OpenRouterProvider with AgnoProvider.

Level 2 – Deep integration inside your steps (recommended next)
Your AlignmentEngine stays the orchestrator, but:

each LLM-heavy step (context extraction, rule filtering, generation, enforcement) is powered by a dedicated Agno Agent;

your tools become Agno tools with RunContext;

multi-tenancy uses Agno’s session + session_state.

Level 3 – Full Agno workflow / AgentOS front-end
You express process_turn itself as an Agno Workflow, so the entire pipeline is first-class in Agno’s world (steps, events, observability). Your current AlignmentEngine essentially becomes a thin domain wrapper around those steps.

Right now you’re at Level 0/1. You’re asking, “Can’t I go to 2 or 3?” → yes.

I’ll focus on Level 2, which gives you much more value without rewriting everything.

Level 2: Agno inside your AlignmentEngine

Your current AlignmentEngine.process_turn:

already does a beautiful 8-step pipeline;

already has tenant_id, agent_id, session_id;

already has ToolExecutor, LLMProvider, MemoryRetriever, etc.

So we don’t throw this away. We just:

replace your LLM guts with Agno Agents,

replace your tools with Agno tools using RunContext,

thread tenant/session info straight into Agno’s session state.

1. Replace OpenRouterProvider with an AgnoProvider (but richer)

Instead of your OpenRouterProvider, you define something like:

# ruche/providers/llm/agno.py  (conceptual)

from agno.agent import Agent
from agno.models.openai import OpenAIChat   # or Anthropic, etc.

class AgnoProvider(LLMProvider):
    def __init__(self, default_model: str):
        self._default_model = default_model
        self._agent = Agent(
            name="focal_generic_llm",
            model=OpenAIChat(id=default_model),
            add_history_to_context=False,
            markdown=False,
        )

    @property
    def provider_name(self) -> str:
        return "agno"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        request_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # 1) choose model
        if model and model != self._default_model:
            self._agent.model = OpenAIChat(id=model)

        # 2) convert messages -> Agno input (depends on version; conceptually):
        history = [{"role": m.role, "content": m.content} for m in messages]

        # 3) propagate tenant/session context from request_metadata
        session_state = (request_metadata or {}).copy()

        start = time.perf_counter()
        run = await self._agent.arun(
            input=history,
            max_tokens=max_tokens,
            temperature=temperature,
            session_state=session_state,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        text = run.output_text  # or equivalent

        return LLMResponse(
            content=text,
            model=model or self._default_model,
            finish_reason="stop",
            usage=None,  # can be filled if Agno exposes it
            latency_ms=latency_ms,
            metadata=request_metadata or {},
            raw_response=run.model_dump() if hasattr(run, "model_dump") else None,
        )


Key difference vs OpenRouter:
👉 this is now a full Agno Agent call, not just a naked OpenAI API call.

Then in your ContextExtractor, RuleFilter, ResponseGenerator, EnforcementValidator, you:

add tenant_id, agent_id, session_id parameters;

pass them down as request_metadata:

await self._llm_provider.generate(
    messages,
    model=self._model_id_for_this_step,
    request_metadata={
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "session_id": str(session_id),
        "step": "context_extraction",
    },
)


Now every LLM step in your pipeline is:

a call to an Agno Agent,

with proper session_state and multi-tenant context,

but still orchestrated by your own AlignmentEngine.

That’s already a big integration jump.

2. Make your tools real Agno tools (RunContext, multi-tenant)

Right now _execute_tools:

results = await self._tool_executor.execute(
    matched_rules=matched_rules,
    context=context,
)


You can define ToolExecutor to operate on Agno tools that accept run_context: RunContext exactly like in the Agno multi-tenant doc you pasted earlier:

# ruche/alignment/execution/agno_tool_executor.py (conceptual)

from agno.run import RunContext

class AgnoToolExecutor(ToolExecutor):
    def __init__(self, tools: dict[str, callable]):
        self._tools = tools

    async def execute(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: UUID,
    ) -> list[ToolResult]:
        results: list[ToolResult] = []

        # Build a shared RunContext for this turn
        run_context = RunContext(
            session_state={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": str(session_id),
            },
            # you can add more metadata if Agno supports it
        )

        for matched in matched_rules:
            for tool_cfg in matched.rule.tools:
                tool_fn = self._tools[tool_cfg.name]

                start = time.perf_counter()
                try:
                    # Agno will inject run_context if the function signature has it
                    output = await tool_fn(
                        run_context=run_context,
                        context=context,
                        **(tool_cfg.params or {}),
                    )
                    success = True
                    error = None
                except Exception as e:
                    output = None
                    success = False
                    error = str(e)

                elapsed = (time.perf_counter() - start) * 1000

                results.append(
                    ToolResult(
                        tool_id=tool_cfg.id,
                        tool_name=tool_cfg.name,
                        inputs=tool_cfg.params or {},
                        outputs=output,
                        success=success,
                        error=error,
                        execution_time_ms=elapsed,
                    )
                )

        return results


And a tool looks like:

from agno.run import RunContext

async def fetch_customer_data(
    run_context: RunContext,
    context: Context,
    data_type: str,
) -> dict:
    tenant_id = run_context.session_state["tenant_id"]
    customer_id = context.extracted_customer_id
    # now query tenant-specific DB safely
    return await query_customer(tenant_id, customer_id, data_type)


This is exactly the Agno pattern you pasted:

tools get run_context injected,

you fetch tenant_id, customer_id from session_state,

tools are tenant-aware without exposing raw tenant IDs to the LLM.

Now your rule-attached tools are first-class Agno tools.

3. Use Agno’s multi-tenant session context end-to-end

You already pass tenant_id, agent_id, session_id into process_turn.

If you stick to Level 2, do this:

For every LLM call (context, filtering, generation, enforcement), pass:

request_metadata = {
    "tenant_id": str(tenant_id),
    "agent_id": str(agent_id),
    "session_id": str(session_id),
    "step": "generation",
}


And let your AgnoProvider push it into session_state.

For tools, create a RunContext with the same keys.

Now Agno’s own mechanisms (session-scoped state, optional Agent memory, etc.) line up with your SessionStore + AuditStore. You still persist everything in your stores, but Agno now has a coherent notion of “this run belongs to tenant X / agent Y / session Z”.

That’s a lot more integrated than just “use it as an HTTP client”.

Level 3 (for later): turn the whole AlignmentEngine into an Agno Workflow

If you want the maximum Agno integration:

Express process_turn as an Agno Workflow with steps:

pre_turn_reconciliation

context_extraction

retrieval

rule_filtering

scenario_filtering

tool_execution

generation

enforcement

persist_session_and_audit

Each step is either:

a pure-Python call to your existing code, or

an Agno Agent call, or

a combination (e.g. Python transforms + Agent).

You call workflow.run(...) (or arun) from your HTTP layer with:

user_id = str(tenant_id)
session_id = str(session_id)
additional_data = {"agent_id": str(agent_id)}


This gives you:

Agno’s workflow observability on top of your own timings,

native Agno session handling for multi-tenant context,

and you can still keep AlignmentResult as your domain object.

But this is a bigger refactor. I’d treat Level 3 as a second phase.

TL;DR – “More integrated” in practice

If you want Agno to be more than “just an HTTP client”, for SmartBeez / focal I’d do:

Swap OpenRouterProvider → AgnoProvider, but keep LLMProvider interface.

Each pipeline step uses a dedicated Agno Agent (model + instructions per step).

Pass tenant_id/agent_id/session_id via request_metadata → session_state.

Rebuild ToolExecutor on Agno tools + RunContext, so:

tools read tenant_id from run_context.session_state,

rules decide which tools fire,

Agno gives you tenant safety “for free”.

Later, optionally:

wrap process_turn as an Agno Workflow for full-step observability.

That’s a real integration: your alignment engine becomes a domain-specific layer on top of Agno’s Agents / Tools / Session system, not just another client around OpenAI.

You said:
for agno workflow I can choose a specific LLM by step ? remember that everything will be mutli tenat and agent specific. all agents will use the same workflow but specificities will be needed by agent
ChatGPT said:

Yes 👍
With Agno Workflows you can absolutely:

Use a different LLM per step

Make those choices agent-specific and tenant-specific

Still reuse one shared workflow definition across all agents/tenants.

Let’s break down how to do it in a way that fits your Focal/SmartBeez architecture.

1. Levels where you can vary the model

In Agno there are basically three levers:

Per-Agent model
Each Agent has its own model=... (e.g. Haiku for filtering, Sonnet for generation).

Per-Step model in a Workflow
A Workflow step is usually:

either a pure Python function, or

a call to an Agent (or an inner Workflow).

So you can simply use different Agents per step, each with its own model.

Per-Run override (per tenant/agent)
At runtime, you can decide which Agent or model to use based on:

tenant_id

agent_id

plan / tier / SLA

So a typical pattern for you:

Step “context extraction” → cheap model (Haiku / gpt-4o-mini).

Step “rule filtering” → similar cheap model.

Step “generation” → stronger model (Sonnet / gpt-4.1 / Llama 3.3 70B).

Step “enforcement” → small but strict model.

All of that while using the same Workflow for all tenants.

2. Single workflow, many agents/tenants

Think:

# Pseudo-API for an Agno-style workflow

async def alignment_workflow_step_context(input: StepInput) -> StepOutput: ...
async def alignment_workflow_step_retrieval(input: StepInput) -> StepOutput: ...
async def alignment_workflow_step_rule_filtering(input: StepInput) -> StepOutput: ...
async def alignment_workflow_step_generation(input: StepInput) -> StepOutput: ...
...


Each LLM step can:

Either directly call an Agent that’s bound to a specific model

Or choose the Agent/model dynamically based on step_input.additional_data
(which you fill with tenant_id, agent_id, etc. at workflow.run() time).

So you have one workflow definition, but at runtime you can do:

workflow.run(
    input={"message": "..."},
    additional_data={
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "plan": "enterprise",
    },
)


Then inside the step you pick the right Agent/model.

3. A concrete design that fits Focal

Let’s map it to your engine:

3.1. Agent catalog

You keep a little registry in your app:

# Pseudo-code
AGENT_CONFIG = {
    # For each business agent (your domain "agent_id")
    "support_agent_basic": {
        "context_model": "anthropic/claude-3-haiku-20240307",
        "rule_filter_model": "gpt-4o-mini",
        "generation_model": "gpt-4.1-mini",
        "enforcement_model": "gpt-4o-mini",
    },
    "support_agent_premium": {
        "context_model": "anthropic/claude-3-5-sonnet-20241022",
        "rule_filter_model": "gpt-4o",
        "generation_model": "gpt-4.1",
        "enforcement_model": "sonnet",
    },
}


Plus possibly tenant overrides:

TENANT_OVERRIDES = {
    "tenant_123": {
        "support_agent_basic": {
            "generation_model": "gpt-4.1-mini",  # cheaper custom choice
        }
    }
}


A helper:

def resolve_model(tenant_id: str, agent_id: str, step: str) -> str:
    base = AGENT_CONFIG[agent_id][step]
    override = (
        TENANT_OVERRIDES.get(tenant_id, {})
        .get(agent_id, {})
        .get(step)
    )
    return override or base

3.2. Agents per step

Define one Agno Agent per step “type”, not per tenant:

from agno.agent import Agent
from agno.models.openai import OpenAIChat

context_agent = Agent(
    name="context_extractor",
    model=OpenAIChat(id="anthropic/claude-3-haiku-20240307"),
)

rule_filter_agent = Agent(
    name="rule_filter",
    model=OpenAIChat(id="gpt-4o-mini"),
)

generation_agent = Agent(
    name="generator",
    model=OpenAIChat(id="gpt-4.1-mini"),
)

enforcement_agent = Agent(
    name="enforcer",
    model=OpenAIChat(id="gpt-4o-mini"),
)


You don’t hardcode models; instead you override agent.model at runtime per tenant/agent.

3.3. Workflow step that picks model per tenant/agent

Example for “generation” step inside the Workflow:

from agno.workflows import StepInput, StepOutput

async def step_generation(input: StepInput) -> StepOutput:
    message = input.data["message"]
    tenant_id = input.additional_data["tenant_id"]
    agent_id = input.additional_data["agent_id"]

    # 1) Resolve which model to use for THIS agent+tenant+step
    model_id = resolve_model(tenant_id, agent_id, step="generation_model")

    # 2) Override the agent model dynamically
    generation_agent.model = OpenAIChat(id=model_id)

    # 3) Run the agent with session context
    run = await generation_agent.arun(
        input=message,
        user_id=f"{tenant_id}:{agent_id}",
        session_id=input.additional_data["session_id"],
        session_state={
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "session_id": input.additional_data["session_id"],
        },
    )

    return StepOutput(
        data={
            "response": run.output_text,
            "model_used": model_id,
        }
    )


You’d do the same pattern for:

context extraction step (cheap model)

rule filtering step

enforcement step

Same workflow, same step function, but model_id varies per tenant/agent via additional_data.

4. Multi-tenant specifics

You want:

everything will be multi tenant and agent specific. all agents will use the same workflow but specificities will be needed by agent

That’s exactly what this gives you:

Same workflow code for everyone.

tenant_id + agent_id passed once at run(...).

Each step:

resolves the right model for this tenant/agent,

sets Agent.model accordingly,

uses user_id/session_id/session_state for Agno’s internal state.

Additionally:

Tools can read tenant context through RunContext.session_state["tenant_id"].

Knowledge filters / vector DB queries can do {"tenant_id": tenant_id}.

Feature flags per plan (basic vs premium) can be checked in additional_data["plan"] or session_state.

5. How this ties back to your current AlignmentEngine

You have two options:

Keep AlignmentEngine as the orchestrator, and call Agno Agents inside your step classes.

You handle steps, timings, sessions, audit.

Agno is “per-step brain” + Tools + multi-tenant context.

Express the AlignmentEngine pipeline as an Agno Workflow, then your HTTP layer just calls the Workflow.

You still keep AlignmentResult as your final object (returned from the workflow).

All per-step model selection & multi-tenant logic sits inside Agno-land.

Either way, per-step, per-agent, per-tenant model choice is completely doable.

If you want, next I can sketch an actual pseudo-Workflow signature that mimics your AlignmentEngine.process_turn exactly, with:

input={"message": ..., "session_id": ...}

additional_data={"tenant_id": ..., "agent_id": ..., "plan": ...}

and show how each step maps to your current methods (_extract_context, _retrieve_rules, _filter_rules, etc.) with per-step model selection.
