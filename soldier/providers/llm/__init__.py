"""LLM providers for text generation.

The primary interface is LLMExecutor, which:
- Takes a model string (e.g., "openrouter/anthropic/claude-3-haiku")
- Routes to the appropriate API via Agno model classes
- Supports fallback chains
- Handles tenant/session context

Model string formats:
- openrouter/{provider}/{model} -> Agno OpenRouter
- anthropic/{model} -> Agno Claude
- openai/{model} -> Agno OpenAIChat
- groq/{model} -> Agno Groq
- mock/{name} -> Mock response for testing
"""

# Data models
from soldier.providers.llm.base import (
    AuthenticationError,
    ContentFilterError,
    LLMMessage,
    LLMResponse,
    ModelError,
    ProviderError,
    RateLimitError,
    TokenUsage,
)

# Executor (primary interface)
from soldier.providers.llm.executor import (
    ExecutionContext,
    LLMExecutor,
    clear_execution_context,
    create_executor,
    create_executor_from_step_config,
    create_executors_from_pipeline_config,
    get_execution_context,
    set_execution_context,
)

# Mock provider for tests (kept for backwards compatibility)
from soldier.providers.llm.mock import MockLLMProvider

__all__ = [
    # Data models
    "LLMMessage",
    "LLMResponse",
    "TokenUsage",
    # Errors
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ModelError",
    "ContentFilterError",
    # Executor (primary interface)
    "LLMExecutor",
    "ExecutionContext",
    "set_execution_context",
    "get_execution_context",
    "clear_execution_context",
    "create_executor",
    "create_executor_from_step_config",
    "create_executors_from_pipeline_config",
    # Testing
    "MockLLMProvider",
]
