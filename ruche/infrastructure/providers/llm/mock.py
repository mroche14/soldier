"""Mock LLM provider for testing."""

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel

from ruche.providers.llm.base import LLMMessage, LLMResponse, TokenUsage

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider:
    """Mock LLM provider for testing.

    Returns configurable responses without making actual API calls.
    Useful for unit testing and development.

    This is a standalone class (not extending any base) for backwards
    compatibility with existing tests.
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
        """Stream mock response in chunks."""
        return self._generate_stream_impl(
            messages, model, max_tokens, temperature, stop_sequences, **kwargs
        )

    async def _generate_stream_impl(
        self,
        messages: list[LLMMessage],
        model: str | None,
        max_tokens: int,
        temperature: float,
        stop_sequences: list[str] | None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Internal stream implementation."""
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

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        """Generate mock structured output matching a Pydantic schema.

        Creates a valid instance of the schema with default/mock values.

        Args:
            prompt: User prompt
            schema: Pydantic model class to parse response into
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific options

        Returns:
            Tuple of (parsed model instance, LLMResponse)
        """
        # Record the call
        self._call_history.append({
            "method": "generate_structured",
            "prompt": prompt,
            "schema": schema.__name__,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "kwargs": kwargs,
        })

        # Generate a mock instance with default values
        # This will use Pydantic's model construction with optional fields
        mock_data = self._generate_mock_data(schema)
        parsed = schema.model_validate(mock_data)

        # Create response
        content = json.dumps(mock_data)
        usage = TokenUsage(
            prompt_tokens=len(prompt) // 4,
            completion_tokens=len(content) // 4,
            total_tokens=(len(prompt) + len(content)) // 4,
        )

        response = LLMResponse(
            content=content,
            model=self._default_model,
            finish_reason="stop",
            usage=usage,
        )

        return parsed, response

    def _generate_mock_data(self, schema: type[BaseModel]) -> dict[str, Any]:
        """Generate mock data for a Pydantic schema."""
        result: dict[str, Any] = {}
        for field_name, field_info in schema.model_fields.items():
            annotation = field_info.annotation
            if annotation is None:
                result[field_name] = "mock"
            elif annotation is str:
                result[field_name] = f"mock_{field_name}"
            elif annotation is int:
                result[field_name] = 42
            elif annotation is float:
                result[field_name] = 3.14
            elif annotation is bool:
                result[field_name] = True
            elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                result[field_name] = ["item1", "item2"]
            elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                result[field_name] = self._generate_mock_data(annotation)
            else:
                result[field_name] = "mock"
        return result

    async def count_tokens(self, text: str) -> int:
        """Count tokens (mock uses ~4 chars per token)."""
        return len(text) // 4 + 1
