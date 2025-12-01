"""LLM data models and error types.

This module provides the core types used by LLMExecutor:
- LLMMessage: Input message format
- LLMResponse: Output response format
- TokenUsage: Token counting
- Error types for different failure modes
"""

from typing import Any

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """A message in a conversation."""

    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class TokenUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")


class LLMResponse(BaseModel):
    """Response from an LLM call."""

    content: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    finish_reason: str | None = Field(
        default=None, description="Why generation stopped"
    )
    usage: TokenUsage | dict[str, int] | None = Field(
        default=None, description="Token usage stats"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Execution metadata"
    )
    raw_response: dict[str, Any] | None = Field(
        default=None, description="Raw provider response"
    )


# ============================================================================
# Error Types
# ============================================================================


class ProviderError(Exception):
    """Base exception for LLM provider errors."""

    pass


class AuthenticationError(ProviderError):
    """Invalid or missing API key."""

    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded."""

    pass


class ModelError(ProviderError):
    """Model not found or unavailable."""

    pass


class ContentFilterError(ProviderError):
    """Content blocked by safety filter."""

    pass
