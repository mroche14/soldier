"""LLM Executor - Executes LLM calls for pipeline steps using Agno.

Each pipeline step gets its own executor configured with:
- A specific model (from config)
- Fallback models (optional)
- Execution parameters (timeout, retries)

The executor handles:
- Model selection and API routing based on model string prefix
- Fallback chain on failure (Agno doesn't have this natively)
- Observability (latency, request tracking)
- Tenant/session context via ExecutionContext

Uses Agno model classes internally:
- OpenRouter for openrouter/* models
- Claude for anthropic/* models
- OpenAIChat for openai/* models
- Groq for groq/* models
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from soldier.observability.logging import get_logger
from soldier.providers.llm.base import (
    LLMMessage,
    LLMResponse,
    ProviderError,
    RateLimitError,
    TokenUsage,
)

if TYPE_CHECKING:
    from agno.agent import Agent

    from soldier.config.models.pipeline import OpenRouterProviderConfig, PipelineConfig

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


# ============================================================================
# Execution Context (avoids parameter threading)
# ============================================================================


@dataclass
class ExecutionContext:
    """Context for LLM execution - tenant, session, step info.

    Set once at the start of process_turn(), available to all executors
    without threading through every method call.
    """

    tenant_id: UUID
    agent_id: UUID
    session_id: UUID
    turn_id: UUID | None = None
    step: str | None = None  # "context_extraction", "rule_filtering", etc.

    # Optional: for billing/analytics
    customer_id: str | None = None
    plan_tier: str | None = None


# Context variable - async-safe, no threading needed
_execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "execution_context", default=None
)


def set_execution_context(ctx: ExecutionContext) -> None:
    """Set execution context for current async task."""
    _execution_context.set(ctx)


def get_execution_context() -> ExecutionContext | None:
    """Get execution context for current async task."""
    return _execution_context.get()


def clear_execution_context() -> None:
    """Clear execution context."""
    _execution_context.set(None)


# ============================================================================
# LLM Executor
# ============================================================================


class LLMExecutor:
    """Executes LLM calls for a pipeline step using Agno.

    Each step (context extraction, filtering, generation) gets its own
    executor with its own model configuration.

    Features:
    - Automatic model routing based on model string prefix
    - Fallback chain on failure (Agno doesn't have this natively)
    - Observability (latency_ms, request metadata)
    - Tenant context from ExecutionContext (no param threading)

    Model string format:
        openrouter/anthropic/claude-3-haiku -> OpenRouter(id="anthropic/claude-3-haiku")
        anthropic/claude-3-haiku -> Claude(id="claude-3-haiku")
        openai/gpt-4o -> OpenAIChat(id="gpt-4o")
        groq/llama-3.1-70b -> Groq(id="llama-3.1-70b")
        mock/test -> Mock response (for testing)

    Example:
        executor = LLMExecutor(
            model="openrouter/anthropic/claude-3-haiku-20240307",
            fallback_models=["anthropic/claude-3-haiku-20240307"],
        )

        response = await executor.generate(
            messages=[LLMMessage(role="user", content="Hello")],
        )
    """

    def __init__(
        self,
        model: str,
        fallback_models: list[str] | None = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        step_name: str | None = None,
        openrouter_config: OpenRouterProviderConfig | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            model: Primary model string (e.g., 'openrouter/anthropic/claude-3-haiku')
            fallback_models: Models to try if primary fails
            max_retries: Max retries per model (not used yet, for future)
            timeout: Request timeout in seconds
            step_name: Pipeline step name for logging
            openrouter_config: OpenRouter-specific provider routing config
        """
        self._model = model
        self._fallback_models = fallback_models or []
        self._max_retries = max_retries
        self._timeout = timeout
        self._step_name = step_name
        self._openrouter_config = openrouter_config

        # Cache for Agno agents (one per model string)
        self._agents: dict[str, Agent] = {}

    @property
    def model(self) -> str:
        """Primary model for this executor."""
        return self._model

    @property
    def step_name(self) -> str | None:
        """Pipeline step this executor serves."""
        return self._step_name

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text from messages.

        Uses primary model, falls back to fallback_models on failure.
        Automatically includes tenant/session context from ExecutionContext.

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Stop generation strings (not all providers support)
            **kwargs: Additional provider-specific options

        Returns:
            LLMResponse with generated content and metadata
        """
        models_to_try = [self._model] + self._fallback_models
        last_error: Exception | None = None

        ctx = get_execution_context()

        for model in models_to_try:
            try:
                response = await self._generate_with_model(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

                # Add context metadata to response
                if ctx:
                    response.metadata["tenant_id"] = str(ctx.tenant_id)
                    response.metadata["agent_id"] = str(ctx.agent_id)
                    response.metadata["session_id"] = str(ctx.session_id)
                    response.metadata["step"] = self._step_name or ctx.step

                return response

            except RateLimitError as e:
                logger.warning(
                    "executor_rate_limited",
                    model=model,
                    step=self._step_name,
                    error=str(e),
                )
                last_error = e
                continue

            except ProviderError as e:
                logger.warning(
                    "executor_provider_error",
                    model=model,
                    step=self._step_name,
                    error=str(e),
                )
                last_error = e
                continue

            except Exception as e:
                logger.warning(
                    "executor_unexpected_error",
                    model=model,
                    step=self._step_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                last_error = e
                continue

        raise ProviderError(
            f"All models failed for step {self._step_name}. "
            f"Tried: {models_to_try}. Last error: {last_error}"
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        """Generate structured output matching a Pydantic schema.

        Args:
            prompt: User prompt
            schema: Pydantic model to parse response into
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            **kwargs: Additional options

        Returns:
            Tuple of (parsed model, LLMResponse)
        """
        models_to_try = [self._model] + self._fallback_models
        last_error: Exception | None = None

        for model in models_to_try:
            try:
                return await self._generate_structured_with_model(
                    model=model,
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except ProviderError as e:
                last_error = e
                continue

        raise ProviderError(
            f"Structured generation failed for all models. Last error: {last_error}"
        )

    def generate_stream(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream generated text.

        Note: Streaming doesn't support fallback - uses primary model only.
        """
        return self._generate_stream_impl(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Uses tiktoken for OpenAI-compatible models, estimates for others.
        """
        provider_type, _ = self._parse_model(self._model)

        if provider_type in ("openrouter", "openai"):
            try:
                import tiktoken

                enc = tiktoken.get_encoding("cl100k_base")
                return len(enc.encode(text))
            except Exception:
                pass

        # Fallback estimate (~4 chars per token)
        return max(1, len(text) // 4)

    # ========================================================================
    # Internal: Agno-based execution
    # ========================================================================

    def _get_or_create_agent(self, model: str) -> Agent | None:
        """Get cached Agno agent or create new one for model."""
        if model in self._agents:
            return self._agents[model]

        provider_type, _ = self._parse_model(model)
        if provider_type == "mock":
            return None

        agno_model = self._create_agno_model(model)
        if agno_model is None:
            return None

        from agno.agent import Agent

        agent = Agent(
            model=agno_model,
            num_history_messages=0,  # We manage history ourselves
            markdown=False,
        )
        self._agents[model] = agent
        return agent

    def _create_agno_model(self, model: str) -> Any:
        """Create Agno model class from model string.

        Returns None for mock models.
        """
        provider_type, api_model = self._parse_model(model)

        if provider_type == "openrouter":
            from agno.models.openrouter import OpenRouter

            # Build extra_body from openrouter config if present
            # Note: Must use extra_body, not request_params, because OpenRouter-specific
            # fields like 'provider' need to be passed via extra_body to the OpenAI client
            extra_body = None
            if self._openrouter_config:
                extra_body = self._openrouter_config.to_request_params()
                if extra_body:
                    logger.debug(
                        "openrouter_provider_config_applied",
                        model=model,
                        step=self._step_name,
                        provider_order=self._openrouter_config.provider_order,
                        provider_sort=self._openrouter_config.provider_sort,
                    )

            return OpenRouter(id=api_model, extra_body=extra_body)

        elif provider_type == "anthropic":
            from agno.models.anthropic import Claude

            return Claude(id=api_model)

        elif provider_type == "openai":
            from agno.models.openai import OpenAIChat

            return OpenAIChat(id=api_model)

        elif provider_type == "groq":
            from agno.models.groq import Groq

            return Groq(id=api_model)

        elif provider_type == "mock":
            return None

        else:
            # Default to OpenRouter for unknown prefixes
            from agno.models.openrouter import OpenRouter

            logger.warning(
                "unknown_provider_defaulting_to_openrouter",
                model=model,
                provider_type=provider_type,
            )
            return OpenRouter(id=model)

    def _format_messages_for_agno(self, messages: list[LLMMessage]) -> str:
        """Convert our messages to Agno input format.

        Agno agents take a string input. For multi-turn, we format as conversation.
        System messages are handled separately by Agno.
        """
        # Extract non-system messages for the main input
        user_messages = [m for m in messages if m.role != "system"]

        if len(user_messages) == 1:
            return user_messages[0].content

        # Format multi-turn as conversation text
        parts = []
        for msg in user_messages:
            if msg.role == "user":
                parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}")
        return "\n\n".join(parts)

    def _get_system_prompt(self, messages: list[LLMMessage]) -> str | None:
        """Extract system prompt from messages."""
        for msg in messages:
            if msg.role == "system":
                return msg.content
        return None

    async def _generate_with_model(
        self,
        model: str,
        messages: list[LLMMessage],
        max_tokens: int,  # noqa: ARG002
        temperature: float,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> LLMResponse:
        """Execute generation with a specific model using Agno.

        Note: max_tokens, temperature, kwargs are part of the interface but
        not all passed to Agno (which configures these at model creation time).
        """
        provider_type, api_model = self._parse_model(model)

        # Handle mock separately
        if provider_type == "mock":
            return self._mock_response(model, messages)

        agent = self._get_or_create_agent(model)
        if agent is None:
            return self._mock_response(model, messages)

        # Format input for Agno
        input_text = self._format_messages_for_agno(messages)
        system_prompt = self._get_system_prompt(messages)

        # Update agent's system prompt if provided
        if system_prompt:
            agent.instructions = [system_prompt]

        start_time = time.perf_counter()

        try:
            # Run the Agno agent
            run_response = await agent.arun(input_text)
            content = run_response.content if run_response.content else ""

        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg and "limit" in error_msg:
                raise RateLimitError(f"Rate limited: {e}") from e
            raise ProviderError(f"Agno execution failed: {e}") from e

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract backend provider info from Agno response (useful for OpenRouter)
        backend_provider = getattr(run_response, "model_provider", None)
        provider_data = getattr(run_response, "model_provider_data", None)

        # Build metadata
        metadata: dict[str, Any] = {
            "latency_ms": latency_ms,
            "model_requested": model,
            "provider": provider_type,
        }
        if backend_provider:
            metadata["backend_provider"] = backend_provider
        if provider_data:
            metadata["provider_data"] = provider_data

        # Build response
        response = LLMResponse(
            content=content,
            model=model,
            finish_reason="stop",
            usage=None,  # Agno doesn't expose token usage consistently
            metadata=metadata,
        )

        logger.debug(
            "executor_generate_complete",
            model=model,
            step=self._step_name,
            latency_ms=round(latency_ms, 2),
            content_length=len(content),
            backend_provider=backend_provider,
        )

        return response

    async def _generate_structured_with_model(
        self,
        model: str,
        prompt: str,
        schema: type[T],
        system_prompt: str | None,
        max_tokens: int,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        """Execute structured generation with a specific model.

        Uses JSON schema prompting and parses the response.
        """
        json_schema = schema.model_json_schema()
        schema_str = json.dumps(json_schema, indent=2)

        json_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
```json
{schema_str}
```

Output only the JSON, no other text."""

        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=json_prompt))

        response = await self._generate_with_model(
            model, messages, max_tokens, 0.0, **kwargs
        )

        # Parse JSON from response
        content = response.content.strip()
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        try:
            parsed = schema.model_validate_json(content)
        except Exception as e:
            logger.warning(
                "structured_parse_failed",
                schema=schema.__name__,
                content_preview=content[:200],
                error=str(e),
            )
            raise ProviderError(f"Failed to parse structured response: {e}") from e

        return parsed, response

    async def _generate_stream_impl(
        self,
        model: str,
        messages: list[LLMMessage],
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream implementation using Agno."""
        provider_type, _ = self._parse_model(model)

        if provider_type == "mock":
            yield f"Mock streaming response for {model}"
            return

        agent = self._get_or_create_agent(model)
        if agent is None:
            yield f"Mock streaming response for {model}"
            return

        input_text = self._format_messages_for_agno(messages)
        system_prompt = self._get_system_prompt(messages)

        if system_prompt:
            agent.instructions = [system_prompt]

        try:
            # Use Agno's streaming - returns async iterator directly
            async for chunk in agent.arun(input_text, stream=True):
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error("streaming_failed", model=model, error=str(e))
            # Fallback to non-streaming
            response = await self._generate_with_model(
                model, messages, max_tokens, temperature, **kwargs
            )
            yield response.content

    def _mock_response(self, model: str, messages: list[LLMMessage]) -> LLMResponse:  # noqa: ARG002
        """Generate mock response for testing."""
        return LLMResponse(
            content=f"Mock response for {model}",
            model=model,
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            metadata={},
        )

    def _parse_model(self, model: str) -> tuple[str, str]:
        """Parse model string into (provider_type, api_model).

        Examples:
            "openrouter/anthropic/claude-3-haiku" -> ("openrouter", "anthropic/claude-3-haiku")
            "anthropic/claude-3-haiku" -> ("anthropic", "claude-3-haiku")
            "openai/gpt-4o-mini" -> ("openai", "gpt-4o-mini")
            "groq/llama-3.1-70b" -> ("groq", "llama-3.1-70b")
            "mock/test" -> ("mock", "test")
        """
        parts = model.split("/")

        if len(parts) >= 3 and parts[0] == "openrouter":
            return "openrouter", "/".join(parts[1:])
        elif len(parts) >= 2:
            return parts[0], "/".join(parts[1:])
        else:
            return "mock", model


# ============================================================================
# Factory functions
# ============================================================================


def create_executor(
    model: str,
    fallback_models: list[str] | None = None,
    step_name: str | None = None,
    timeout: float = 60.0,
    openrouter_config: OpenRouterProviderConfig | None = None,
) -> LLMExecutor:
    """Create an LLMExecutor with the given configuration.

    Args:
        model: Primary model string
        fallback_models: Models to try if primary fails
        step_name: Pipeline step name for logging
        timeout: Request timeout
        openrouter_config: OpenRouter-specific provider routing config

    Returns:
        Configured LLMExecutor
    """
    return LLMExecutor(
        model=model,
        fallback_models=fallback_models,
        step_name=step_name,
        timeout=timeout,
        openrouter_config=openrouter_config,
    )


def create_executor_from_step_config(
    step_config: Any,
    step_name: str,
) -> LLMExecutor:
    """Create an LLMExecutor from pipeline step configuration.

    Args:
        step_config: Pipeline step config with model, fallback_models, and optional openrouter
        step_name: Name of the step

    Returns:
        Configured LLMExecutor
    """
    return LLMExecutor(
        model=step_config.model,
        fallback_models=getattr(step_config, "fallback_models", []),
        timeout=getattr(step_config, "timeout", 60.0),
        step_name=step_name,
        openrouter_config=getattr(step_config, "openrouter", None),
    )


def create_executors_from_pipeline_config(
    config: PipelineConfig,
) -> dict[str, LLMExecutor]:
    """Create all executors from pipeline configuration.

    Args:
        config: Full pipeline configuration

    Returns:
        Dict mapping step name to executor
    """
    executors = {}

    if config.context_extraction.enabled:
        executors["context_extraction"] = create_executor_from_step_config(
            config.context_extraction, "context_extraction"
        )

    if config.rule_filtering.enabled:
        executors["rule_filtering"] = create_executor_from_step_config(
            config.rule_filtering, "rule_filtering"
        )

    if config.scenario_filtering.enabled:
        executors["scenario_filtering"] = create_executor_from_step_config(
            config.scenario_filtering, "scenario_filtering"
        )

    if config.generation.enabled:
        executors["generation"] = create_executor_from_step_config(
            config.generation, "generation"
        )

    # Memory ingestion executors
    if config.memory_ingestion.entity_extraction.enabled:
        executors["entity_extraction"] = create_executor_from_step_config(
            config.memory_ingestion.entity_extraction, "entity_extraction"
        )

    return executors
