"""Mock LLM provider for testing."""

from collections.abc import AsyncIterator
from typing import Any

from soldier.providers.llm.base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing.

    Returns configurable responses without making actual API calls.
    Useful for unit testing and development.
    """

    def __init__(
        self,
        default_response: str = "Mock response",
        default_model: str = "mock-model",
        responses: dict[str, str] | None = None,
        stream_chunk_size: int = 10,
    ):
        """Initialize mock provider.

        Args:
            default_response: Response to return when no match found
            default_model: Model name to report
            responses: Dict mapping message content to responses
            stream_chunk_size: Number of chars per stream chunk
        """
        self._default_response = default_response
        self._default_model = default_model
        self._responses = responses or {}
        self._stream_chunk_size = stream_chunk_size
        self._call_history: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "mock"

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Return history of calls for testing assertions."""
        return self._call_history

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history.clear()

    def set_response(self, trigger: str, response: str) -> None:
        """Set a response for a specific message content."""
        self._responses[trigger] = response

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
        """Generate mock response."""
        # Record the call
        self._call_history.append({
            "messages": messages,
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop_sequences": stop_sequences,
            "kwargs": kwargs,
        })

        # Find matching response
        content = self._default_response
        if messages:
            last_message = messages[-1].content
            if last_message in self._responses:
                content = self._responses[last_message]

        # Truncate to max_tokens (rough approximation)
        token_limit = max_tokens * 4
        if len(content) > token_limit:
            content = content[:token_limit]

        return LLMResponse(
            content=content,
            model=model or self._default_model,
            finish_reason="stop",
            usage={
                "prompt_tokens": sum(len(m.content) // 4 for m in messages),
                "completion_tokens": len(content) // 4,
                "total_tokens": sum(len(m.content) // 4 for m in messages) + len(content) // 4,
            },
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream mock response in chunks."""
        # Get full response first
        response = await self.generate(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences,
            **kwargs,
        )

        # Stream in chunks
        content = response.content
        for i in range(0, len(content), self._stream_chunk_size):
            yield content[i:i + self._stream_chunk_size]

    async def count_tokens(self, text: str) -> int:
        """Count tokens (mock uses ~4 chars per token)."""
        return len(text) // 4 + 1
