> **Status:** HISTORICAL / NOTES. This document assumes an `LLMProvider` abstraction; current Focal uses `LLMExecutor` (Agno-backed) as the single LLM interface.

Short version: your AlignmentEngine is the orchestrator; what you’re missing is “step executors” that actually hit an LLM and run tools. Agno can be that executor layer instead of you wiring OpenAI/Anthropic/etc. by hand.

I’ll debrief what you have, then show two concrete integration options, and I’ll pick one that’s easy to implement now.

1. What your AlignmentEngine already does

You actually have a very clean Parlant-style brain:

Context extraction
ContextExtractor.extract(...) → uses llm_provider + embedding_provider.

Retrieval
RuleRetriever, ScenarioRetriever, and optional MemoryRetriever → use embedding_provider and config_store to bring back candidate rules, scenarios, memories.

Rule filtering (LLM)
RuleFilter.filter(...) → another LLM call.

Scenario filtering
ScenarioFilter.evaluate(...) → graph navigation logic (maybe LLM-assisted, maybe not).

Tool execution
ToolExecutor.execute(...) → executes tools attached to rules.

Generation (LLM)
ResponseGenerator.generate(...) → builds a prompt from Context + matched_rules + history + tool_results + memory_context + templates and calls the model.

Enforcement (LLM)
EnforcementValidator.validate(...) (+ optional fallback handler) → check hard constraints, maybe re-write response.

Session & audit
SessionStore & AuditStore are your persistence + audit trail.
MigrationExecutor does scenario migration.

So: the brain is done, but the “LLM brain” is abstracted behind LLMProvider, and the “tool brain” is abstracted behind ToolExecutor. That’s exactly where Agno fits.

2. Where Agno fits conceptually

Agno gives you three big primitives: Agents, Tools, and Workflows. 
GitHub
+1

You already have your own workflow (AlignmentEngine.process_turn), so the cleanest integration is:

Keep AlignmentEngine as the top-level orchestrator.

Use Agno Agents to implement every place you currently need an LLM.

Optionally use Agno tools inside your ToolExecutor.

Concretely, these are the LLM touchpoints you can back with Agno:

ContextExtractor → Agno Agent (no tools, maybe small model).

RuleFilter → Agno Agent (classification / selection).

ResponseGenerator → Agno Agent (bigger model, tools, knowledge).

EnforcementValidator → Agno Agent (guardrail / eval style).

Plus, for multi-tenancy, every Agno call can receive user_id, session_id and session_state={"tenant_id": ..., "agent_id": ...}, which it already supports via Agent.run/arun and Workflow.run/arun parameters. 
Agno

3. Pattern A (recommended): “Agno as LLMProvider + ToolExecutor”
3.1. Wrap Agno in a LLMProvider implementation

Assume your LLMProvider interface looks roughly like:

class LLMProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        # maybe other kwargs
    ) -> str: ...


Create an implementation backed by an Agno Agent:

from agno.agent import Agent
from agno.models.openai import OpenAIChat  # or Anthropic, etc.

class AgnoLLMProvider(LLMProvider):
    def __init__(self, default_model_id: str):
        self._default_model_id = default_model_id
        # One generic agent with no tools; you can have more per step if needed
        self._agent = Agent(
            name="alignment_llm",
            model=OpenAIChat(id=default_model_id),
            # No db: you already manage history in AuditStore
            add_history_to_context=False,
            markdown=False,
        )

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        session_state: dict | None = None,
    ) -> str:
        # Optionally swap model per call
        if model and model != self._default_model_id:
            self._agent.model = OpenAIChat(id=model)

        # Build messages from system + user prompt
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        run = await self._agent.arun(
            input=messages,
            user_id=user_id,
            session_id=session_id,
            session_state=session_state or {},
        )
        # Depending on version, extract text from run; check docs for exact API
        return run.output_text  # or run.content, or run.get_content_as_string()


Now all existing components that depend on LLMProvider (ContextExtractor, RuleFilter, ResponseGenerator, EnforcementValidator) start working without rewriting your brain – they simply get backed by Agno.

How to wire tenant / session:

Inside AlignmentEngine.process_turn you already have tenant_id, agent_id, session_id. For each LLM call you can pass:

user_id = f"{tenant_id}:{agent_id}" (or user within tenant).

session_id = str(session_id)

session_state = {"tenant_id": str(tenant_id), "agent_id": str(agent_id)}

Your step components can receive these via extra kwargs and forward them to llm_provider.complete(...).

This directly leverages all the tenant-awareness patterns you collected before: session-scoped memory, per-tenant state, etc. 
Agno
+1

3.2. Implement ToolExecutor using Agno tools (optional but powerful)

Right now _execute_tools just does:

results = await self._tool_executor.execute(
    matched_rules=matched_rules,
    context=context,
)


You can implement ToolExecutor in two ways:

Option 1 – deterministic: call Python functions directly

If your “tools” are just pure Python functions attached to rules, you can:

class AgnoToolExecutor(ToolExecutor):
    def __init__(self, tool_registry: dict[str, callable]):
        self._tools = tool_registry

    async def execute(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for matched in matched_rules:
            for tool_cfg in matched.rule.tools:
                tool_fn = self._tools[tool_cfg.name]
                # call it; tools themselves can use Agno Agent internally if they want
                out = await tool_fn(context=context, **tool_cfg.params)
                results.append(
                    ToolResult(
                        tool_id=tool_cfg.id,
                        tool_name=tool_cfg.name,
                        inputs=tool_cfg.params,
                        outputs=out,
                        success=True,
                        execution_time_ms=...,  # measure if you want
                    )
                )
        return results


Each tool function can itself spin up an Agno Agent if needed (e.g. for RAG, structured calls, etc.), but the selection and orchestration remain deterministic, aligned with your rules.

Option 2 – agentic tools: let an Agno Agent drive tool calls

If you want the LLM to decide tool call order and usage, you can:

Declare your tools as Agno tools (functions with type hints).

Use a dedicated Agent in ToolExecutor:

from agno.agent import Agent
from agno.models.openai import OpenAIChat

class AgnoToolExecutor(ToolExecutor):
    def __init__(self, model_id: str, tools: list[callable]):
        self._agent = Agent(
            name="alignment_tool_runner",
            model=OpenAIChat(id=model_id),
            tools=tools,
        )

    async def execute(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
    ) -> list[ToolResult]:
        prompt = self._build_tool_prompt(matched_rules, context)
        run = await self._agent.arun(prompt)
        # Parse run.tool_calls / events into your ToolResult model
        ...


That’s more work, but you get full Agno tool semantics (session-aware tools, RunContext, etc.). 
GitHub

Given how strict your alignment engine is, Option 1 (deterministic) is probably better initially.

3.3. Implement step→model mapping with your existing config

You said:

In my config I already have something relating a model to the specific step but nothing executing llm calls …

You can use PipelineConfig as a central registry to decide which Agno model each step uses. For example:

@dataclass
class StepModelConfig:
    model_id: str

@dataclass
class PipelineConfig:
    models: dict[str, StepModelConfig] = field(default_factory=dict)


Then in AlignmentEngine.__init__:

self._llm_provider = AgnoLLMProvider(
    default_model_id=self._config.models["generation"].model_id,
)

self._context_extractor = ContextExtractor(
    llm_provider=self._llm_provider,
    model_id=self._config.models["context_extraction"].model_id,
    ...
)
self._rule_filter = RuleFilter(
    llm_provider=self._llm_provider,
    model_id=self._config.models["rule_filtering"].model_id,
)
self._response_generator = ResponseGenerator(
    llm_provider=self._llm_provider,
    model_id=self._config.models["generation"].model_id,
)
self._enforcement_validator = EnforcementValidator(
    llm_provider=self._llm_provider,
    model_id=self._config.models["enforcement"].model_id,
)


Each step passes its model_id down to llm_provider.complete(...) so you can run cheap models for filtering and heavier ones for generation.

4. Alternative Pattern B: Rewrite the whole brain as an Agno Workflow

You don’t have to, but for completeness:

Your process_turn maps almost 1-to-1 to an Agno Workflow where each stage is a Step with an executor (either Agent or Python function). 
Agno
+1

Roughly:

Step 0: pre_turn_reconciliation (Python function step)

Step 1: context_extraction (Agent step)

Step 2: retrieval (Python step)

Step 3: rule_filtering (Agent step)

Step 4: scenario_filtering (Python/Agent)

Step 5: tool_execution (Python or Agent with tools)

Step 6: generation (Agent step)

Step 7: enforcement (Agent step)

Step 8: persist_session_and_audit (Python step)

Then AlignmentEngine.process_turn becomes a thin wrapper that calls:

workflow_run = await alignment_workflow.arun(
    input={"message": message},
    user_id=str(tenant_id),
    session_id=str(session_id),
    session_state={"tenant_id": str(tenant_id), "agent_id": str(agent_id)},
)


and unpacks the WorkflowRunOutput into your AlignmentResult.

This gives you:

Native Agno observability (workflow events, step events, runs history). 
spacesail.mintlify.app

Less custom orchestration code, but you’d port a lot of your existing engine into workflow steps.

I’d treat this as phase 2 once Pattern A is stable.

5. What you concretely need to build next

Given your code today, I’d do this in order:

Define AgnoLLMProvider as above and plug it into:

ContextExtractor

RuleFilter

ResponseGenerator

EnforcementValidator

Thread tenant/session info through those classes:

Their public methods accept tenant_id, agent_id, session_id.

They forward those to llm_provider.complete(..., user_id=..., session_id=..., session_state=...).

Make a minimal ToolExecutor that calls Python tools deterministically. Later, decide if any tool should become a “real” Agno tool (with RunContext, etc.).

Once that’s working and you’re happy with multi-tenant isolation, you can:

Swap specific steps to use Agno Workflows (e.g. complex tool sequences).

Or gradually port the whole alignment brain to a Workflows-first design.

If you want, next step I can sketch concrete signatures for ContextExtractor, RuleFilter, ResponseGenerator, etc., showing exactly how to pass tenant_id/session_id down to the Agno provider.
