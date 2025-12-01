# LLM Executor Refactoring Study: Agno Integration

## Executive Summary

This study proposes simplifying our LLM layer by:
1. Removing the `LLMProvider` abstract class and its implementations
2. Using Agno's model classes (`OpenRouter`, `Claude`, `OpenAIChat`) for API calls
3. Keeping `LLMExecutor` as our single interface with fallback chain support
4. Retaining our `LLMMessage`/`LLMResponse` types for internal consistency

**Key Finding**: Agno does NOT have native fallback model support (it's a [feature request #3318](https://github.com/agno-agi/agno/issues/3318)). We must implement fallback ourselves, which our current `LLMExecutor` already does well.

---

## 1. Current Architecture

### What We Have Now

```
LLMProvider (abstract)
├── AnthropicProvider
├── OpenAIProvider
├── OpenRouterProvider
└── MockLLMProvider

LLMExecutor
├── Takes model string (e.g., "openrouter/anthropic/claude-3-haiku")
├── Routes to correct API based on prefix
├── Implements fallback chain
└── Handles ExecutionContext (tenant/session)
```

### Problems
1. **Redundant layers** - `LLMProvider` implementations duplicate what `LLMExecutor` already does
2. **Two ways to call LLMs** - confusing for developers
3. **Provider classes maintain their own clients** - duplicated connection management

---

## 2. Proposed Architecture

### New Structure

```
LLMExecutor (single interface)
├── Uses Agno model classes internally
├── Implements fallback chain (Agno doesn't have this)
├── Handles ExecutionContext
└── Converts between our types and Agno types

Agno Model Classes (internal, not exposed)
├── OpenRouter(id="anthropic/claude-3-haiku")
├── Claude(id="claude-3-haiku")
├── OpenAIChat(id="gpt-4o")
└── (mock handled separately)
```

### What We Keep (Our Code)

| Component | Reason |
|-----------|--------|
| `LLMExecutor` | Our fallback chain, Agno doesn't have this |
| `LLMMessage` | Our internal API, convert to Agno format internally |
| `LLMResponse` | Wrap Agno's `RunResponse`, add our metadata |
| `TokenUsage` | Normalized token tracking |
| `ExecutionContext` | Tenant/session context (async-safe) |
| Error types | `ProviderError`, `RateLimitError`, etc. |

### What We Use From Agno

| Component | How We Use It |
|-----------|---------------|
| `OpenRouter` | For `openrouter/*` model strings |
| `Claude` | For `anthropic/*` model strings |
| `OpenAIChat` | For `openai/*` model strings |
| `Groq` | For `groq/*` model strings (future) |
| `Agent` | Wrapper for running models |
| `RunResponse` | Extract content, convert to our `LLMResponse` |

### What We Remove

| Component | Replacement |
|-----------|-------------|
| `AnthropicProvider` | Agno's `Claude` |
| `OpenAIProvider` | Agno's `OpenAIChat` |
| `OpenRouterProvider` | Agno's `OpenRouter` |
| `MockLLMProvider` | `mock/*` prefix in executor |
| `LLMProvider` abstract class | Not needed |

---

## 3. Model String Format

Config-driven model selection (unchanged):

```toml
[pipeline.context_extraction]
model = "openrouter/anthropic/claude-3-haiku-20240307"
fallback_models = ["anthropic/claude-3-haiku-20240307"]

[pipeline.generation]
model = "anthropic/claude-3-5-sonnet-20241022"
fallback_models = ["openrouter/anthropic/claude-3-5-sonnet-20241022"]

[pipeline.rule_filtering]
model = "openai/gpt-4o-mini"
```

### Routing Logic

| Model String | Agno Class | Notes |
|--------------|------------|-------|
| `openrouter/anthropic/claude-3-haiku` | `OpenRouter(id="anthropic/claude-3-haiku")` | Via OpenRouter API |
| `openrouter/openai/gpt-4o` | `OpenRouter(id="openai/gpt-4o")` | Via OpenRouter API |
| `anthropic/claude-3-haiku` | `Claude(id="claude-3-haiku")` | Direct Anthropic API |
| `openai/gpt-4o` | `OpenAIChat(id="gpt-4o")` | Direct OpenAI API |
| `groq/llama-3.1-70b` | `Groq(id="llama-3.1-70b")` | Direct Groq API |
| `mock/test` | None (internal mock) | For testing |

---

## 4. Fallback Handling

### Why We Must Implement This Ourselves

Agno does NOT have native fallback model support:
- [Feature request #3318](https://github.com/agno-agi/agno/issues/3318) - "fallback model in agent"
- [PR #3929](https://github.com/agno-agi/agno/pull/3929) - Only for OpenRouter-specific fallback (not cross-provider)

### Our Fallback Strategy (Keep Current Implementation)

```python
async def generate(self, messages: list[LLMMessage], ...) -> LLMResponse:
    models_to_try = [self._model] + self._fallback_models
    last_error: Exception | None = None

    for model in models_to_try:
        try:
            # Create Agno model for this attempt
            agno_model = self._create_agno_model(model)
            agent = Agent(model=agno_model)

            # Run and convert response
            run = await agent.arun(formatted_messages)
            return self._convert_to_llm_response(run, model)

        except RateLimitError as e:
            logger.warning("rate_limited", model=model)
            last_error = e
            continue

        except ProviderError as e:
            logger.warning("provider_error", model=model)
            last_error = e
            continue

    raise ProviderError(f"All models failed: {models_to_try}")
```

### Fallback Scenarios

| Primary Model | Fallback | Use Case |
|--------------|----------|----------|
| `openrouter/anthropic/claude-3-haiku` | `anthropic/claude-3-haiku` | OpenRouter down → direct API |
| `anthropic/claude-3-5-sonnet` | `openrouter/anthropic/claude-3-5-sonnet` | Anthropic rate limited → OpenRouter |
| `openai/gpt-4o` | `openrouter/openai/gpt-4o` | OpenAI issues → OpenRouter |

---

## 5. Implementation Details

### New LLMExecutor Structure

```python
# soldier/providers/llm/executor.py

from agno.agent import Agent, RunResponse
from agno.models.openrouter import OpenRouter
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq

class LLMExecutor:
    """Single interface for LLM calls with fallback support."""

    def __init__(
        self,
        model: str,
        *,
        fallback_models: list[str] | None = None,
        step_name: str | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
    ):
        self._model = model
        self._fallback_models = fallback_models or []
        self._step_name = step_name
        self._max_retries = max_retries
        self._timeout = timeout_seconds

        # Cache for Agno agents (one per model)
        self._agents: dict[str, Agent] = {}

    def _get_or_create_agent(self, model: str) -> Agent | None:
        """Get cached agent or create new one for model."""
        if model in self._agents:
            return self._agents[model]

        agno_model = self._create_agno_model(model)
        if agno_model is None:
            return None  # Mock model

        agent = Agent(
            model=agno_model,
            add_history_to_context=False,  # We manage history
            markdown=False,
        )
        self._agents[model] = agent
        return agent

    def _create_agno_model(self, model: str):
        """Create Agno model class from model string."""
        if model.startswith("openrouter/"):
            model_id = model.removeprefix("openrouter/")
            return OpenRouter(id=model_id)

        elif model.startswith("anthropic/"):
            model_id = model.removeprefix("anthropic/")
            return Claude(id=model_id)

        elif model.startswith("openai/"):
            model_id = model.removeprefix("openai/")
            return OpenAIChat(id=model_id)

        elif model.startswith("groq/"):
            model_id = model.removeprefix("groq/")
            return Groq(id=model_id)

        elif model.startswith("mock/"):
            return None  # Handle mock internally

        else:
            # Default to OpenRouter for unknown prefixes
            return OpenRouter(id=model)

    def _format_messages_for_agno(self, messages: list[LLMMessage]) -> str:
        """Convert our messages to Agno input format."""
        # For simple cases, Agno takes a string
        # For chat, we format as conversation
        if len(messages) == 1:
            return messages[0].content

        # Format multi-turn as text
        parts = []
        for msg in messages:
            if msg.role == "system":
                parts.append(f"[System]: {msg.content}")
            elif msg.role == "user":
                parts.append(f"[User]: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"[Assistant]: {msg.content}")
        return "\n\n".join(parts)

    def _convert_run_response(
        self,
        run: RunResponse,
        model: str,
        latency_ms: float,
    ) -> LLMResponse:
        """Convert Agno RunResponse to our LLMResponse."""
        ctx = get_execution_context()

        metadata = {}
        if ctx:
            metadata["tenant_id"] = str(ctx.tenant_id)
            metadata["agent_id"] = str(ctx.agent_id)
            metadata["session_id"] = str(ctx.session_id)
            metadata["step"] = self._step_name

        return LLMResponse(
            content=run.content,
            model=model,
            finish_reason="stop",
            usage=None,  # Agno doesn't expose this consistently
            latency_ms=latency_ms,
            metadata=metadata,
        )

    def _mock_response(self, model: str) -> LLMResponse:
        """Generate mock response for testing."""
        return LLMResponse(
            content=f"Mock response from {model}",
            model=model,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            metadata={},
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate with fallback chain."""
        models_to_try = [self._model] + self._fallback_models
        last_error: Exception | None = None

        for model in models_to_try:
            try:
                # Handle mock
                if model.startswith("mock/"):
                    return self._mock_response(model)

                agent = self._get_or_create_agent(model)
                input_text = self._format_messages_for_agno(messages)

                start = time.perf_counter()
                run: RunResponse = await agent.arun(input_text)
                latency_ms = (time.perf_counter() - start) * 1000

                return self._convert_run_response(run, model, latency_ms)

            except Exception as e:
                logger.warning(
                    "executor_model_failed",
                    model=model,
                    step=self._step_name,
                    error=str(e),
                )
                last_error = e
                continue

        raise ProviderError(
            f"All models failed for {self._step_name}: {models_to_try}. "
            f"Last error: {last_error}"
        )
```

---

## 6. Migration Plan

### Phase 1: Add Agno Dependency
```bash
uv add agno
```

### Phase 2: Update LLMExecutor
1. Add Agno imports
2. Implement `_create_agno_model()` routing
3. Implement `_format_messages_for_agno()`
4. Update `generate()` to use Agno agents
5. Keep fallback chain logic

### Phase 3: Remove Old Provider Classes
1. Delete `soldier/providers/llm/anthropic.py`
2. Delete `soldier/providers/llm/openai.py`
3. Delete `soldier/providers/llm/openrouter.py`
4. Delete `soldier/providers/llm/mock.py` (keep mock logic in executor)
5. Remove `LLMProvider` from `base.py`

### Phase 4: Update Exports
```python
# soldier/providers/llm/__init__.py
from soldier.providers.llm.base import (
    LLMMessage,
    LLMResponse,
    TokenUsage,
    ProviderError,
    RateLimitError,
    # ... other error types
)
from soldier.providers.llm.executor import (
    LLMExecutor,
    ExecutionContext,
    set_execution_context,
    get_execution_context,
    clear_execution_context,
)
```

### Phase 5: Update Tests
1. Remove tests for deleted provider classes
2. Update integration tests to use `mock/` prefix
3. Verify fallback chain tests pass

---

## 7. Benefits

| Benefit | Description |
|---------|-------------|
| **Simpler** | One class instead of abstract + 4 implementations |
| **Config-driven** | Model string is all you need |
| **Agno ecosystem** | Access to Agno's tools, memory, workflows later |
| **Maintained** | Agno maintains API clients, not us |
| **Fallback preserved** | Our fallback chain still works |

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Agno API changes | Pin version, test on upgrade |
| Agno doesn't expose token usage | Estimate or accept None |
| Agno Agent overhead | Cache agents per model |
| Multi-turn handling | Format messages ourselves |

---

## 9. Open Questions

1. **Structured output**: Does Agno's `response_model` work well enough, or do we keep our JSON parsing?
2. **Streaming**: How does `agent.arun_stream()` work? Do we need it?
3. **Token counting**: Agno doesn't expose this - do we estimate or drop?

---

## 10. References

- [Agno OpenRouter Docs](https://docs.agno.com/reference/models/openrouter)
- [Agno GitHub](https://github.com/agno-agi/agno)
- [Fallback Feature Request #3318](https://github.com/agno-agi/agno/issues/3318)
- [Agno PyPI](https://pypi.org/project/agno/)
