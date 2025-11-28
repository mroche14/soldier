"""LLMProvider abstract interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """A message in a conversation."""

    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    finish_reason: str | None = Field(
        default=None, description="Why generation stopped"
    )
    usage: dict[str, int] | None = Field(
        default=None, description="Token usage stats"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )


class LLMProvider(ABC):
    """Abstract interface for LLM text generation.

    Provides unified access to various LLM providers
    (Anthropic, OpenAI, etc.) with streaming support.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text from messages.

        Args:
            messages: Conversation messages
            model: Model to use (provider default if not specified)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Stop generation on these strings
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream generated text.

        Args:
            messages: Conversation messages
            model: Model to use (provider default if not specified)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop_sequences: Stop generation on these strings
            **kwargs: Provider-specific options

        Yields:
            Text chunks as they are generated
        """
        ...

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Default implementation estimates ~4 chars per token.
        Providers should override with accurate counts.
        """
        return len(text) // 4 + 1
