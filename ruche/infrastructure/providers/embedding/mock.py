"""Mock embedding provider for testing."""

import hashlib
from typing import Any

from ruche.infrastructure.providers.embedding.base import EmbeddingProvider, EmbeddingResponse


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing.

    Generates deterministic embeddings based on text content
    without making actual API calls.
    """

    def __init__(
        self,
        dimensions: int = 384,
        default_model: str = "mock-embedding",
    ):
        """Initialize mock provider.

        Args:
            dimensions: Embedding vector dimensions
            default_model: Model name to report
        """
        self._dimensions = dimensions
        self._default_model = default_model
        self._call_history: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "mock"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Return history of calls for testing assertions."""
        return self._call_history

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history.clear()

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate deterministic embedding from text.

        Uses text hash to generate reproducible vectors.
        Similar texts will NOT have similar embeddings (this is a mock).
        """
        # Hash the text for reproducibility
        text_hash = hashlib.sha256(text.encode()).digest()

        # Generate deterministic values from hash
        embedding = []
        for i in range(self._dimensions):
            # Use hash bytes cyclically
            byte_val = text_hash[i % len(text_hash)]
            # Normalize to [-1, 1]
            normalized = (byte_val / 127.5) - 1.0
            embedding.append(normalized)

        # Normalize to unit length
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate mock embeddings."""
        # Record the call
        self._call_history.append({
            "texts": texts,
            "model": model or self._default_model,
            "kwargs": kwargs,
        })

        embeddings = [self._generate_embedding(text) for text in texts]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model or self._default_model,
            dimensions=self._dimensions,
            usage={
                "total_tokens": sum(len(t) // 4 for t in texts),
            },
        )
