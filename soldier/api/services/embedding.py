"""Async embedding service for rule embedding computation."""

from uuid import UUID

from soldier.alignment.stores.config_store import ConfigStore
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider

logger = get_logger(__name__)


class EmbeddingService:
    """Service for async embedding computation.

    Handles background computation of embeddings for rules
    without blocking API responses.
    """

    def __init__(
        self,
        config_store: ConfigStore,
        embedding_provider: EmbeddingProvider,
        max_retries: int = 3,
    ) -> None:
        """Initialize embedding service.

        Args:
            config_store: Store for persisting updated embeddings
            embedding_provider: Provider for computing embeddings
            max_retries: Maximum retry attempts on failure
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._max_retries = max_retries

    async def compute_rule_embedding(
        self,
        tenant_id: UUID,
        rule_id: UUID,
    ) -> bool:
        """Compute and persist embedding for a rule.

        This method is designed to be called as a background task.
        It fetches the rule, computes embedding, and saves the updated rule.

        Args:
            tenant_id: Tenant owning the rule
            rule_id: Rule to compute embedding for

        Returns:
            True if embedding was successfully computed and saved
        """
        for attempt in range(self._max_retries):
            try:
                # Fetch the current rule
                rule = await self._config_store.get_rule(tenant_id, rule_id)
                if rule is None:
                    logger.warning(
                        "rule_not_found_for_embedding",
                        tenant_id=str(tenant_id),
                        rule_id=str(rule_id),
                    )
                    return False

                # Compute embedding from condition and action text
                text = f"{rule.condition_text} {rule.action_text}"
                embedding = await self._embedding_provider.embed_single(text)

                # Update rule with new embedding
                rule.embedding = embedding
                rule.embedding_model = self._embedding_provider.provider_name

                # Save updated rule
                await self._config_store.save_rule(rule)

                logger.info(
                    "rule_embedding_computed",
                    tenant_id=str(tenant_id),
                    rule_id=str(rule_id),
                    embedding_dim=len(embedding),
                )
                return True

            except Exception as e:
                logger.warning(
                    "embedding_computation_failed",
                    tenant_id=str(tenant_id),
                    rule_id=str(rule_id),
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    error=str(e),
                )
                if attempt == self._max_retries - 1:
                    logger.error(
                        "embedding_computation_exhausted",
                        tenant_id=str(tenant_id),
                        rule_id=str(rule_id),
                        error=str(e),
                    )
                    return False

        return False

    async def compute_rule_embeddings_batch(
        self,
        tenant_id: UUID,
        rule_ids: list[UUID],
    ) -> dict[UUID, bool]:
        """Compute embeddings for multiple rules.

        Args:
            tenant_id: Tenant owning the rules
            rule_ids: List of rule IDs to process

        Returns:
            Dict mapping rule_id to success status
        """
        results = {}
        for rule_id in rule_ids:
            results[rule_id] = await self.compute_rule_embedding(tenant_id, rule_id)
        return results


async def schedule_embedding_computation(
    embedding_service: EmbeddingService,
    tenant_id: UUID,
    rule_id: UUID,
) -> None:
    """Background task for embedding computation.

    This function is designed to be passed to FastAPI's BackgroundTasks.

    Args:
        embedding_service: Service to use for computation
        tenant_id: Tenant owning the rule
        rule_id: Rule to compute embedding for
    """
    await embedding_service.compute_rule_embedding(tenant_id, rule_id)
