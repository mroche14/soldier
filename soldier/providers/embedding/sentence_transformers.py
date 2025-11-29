"""Sentence-Transformers embedding provider for local embeddings."""

import asyncio
from typing import Any

from sentence_transformers import SentenceTransformer

from soldier.providers.embedding.base import EmbeddingProvider, EmbeddingResponse


class SentenceTransformersProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers models."""

    def __init__(self, model_name: str = "all-mpnet-base-v2", batch_size: int = 32):
        """Initialize sentence-transformers provider.

        Args:
            model_name: Model name to load
            batch_size: Batch size for encoding
        """
        self._model_name = model_name
        self._batch_size = batch_size
        self._model: SentenceTransformer | None = None

    def _ensure_model_loaded(self) -> SentenceTransformer:
        """Lazy-load the model on first use."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return f"sentence_transformers_{self._model_name}"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        model = self._ensure_model_loaded()
        return model.get_sentence_embedding_dimension()

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> EmbeddingResponse:
        """Generate embeddings using sentence-transformers.

        Args:
            texts: List of texts to embed
            model: Ignored (model set at initialization)
            **kwargs: Additional options (ignored)

        Returns:
            EmbeddingResponse with embedding vectors
        """
        model_obj = self._ensure_model_loaded()

        # Run encoding in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings_array = await loop.run_in_executor(
            None,
            lambda: model_obj.encode(
                texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
        )

        # Convert numpy arrays to lists
        embeddings = embeddings_array.tolist()

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self._model_name,
            dimensions=self.dimensions,
            usage={"total_tokens": sum(len(t.split()) for t in texts)},
            metadata={"batch_size": self._batch_size},
        )
