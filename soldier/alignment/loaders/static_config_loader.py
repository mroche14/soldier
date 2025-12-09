"""Static configuration loader for Phase 1.

Loads glossary and customer data schema from AgentConfigStore.
"""

from uuid import UUID

from soldier.alignment.models import GlossaryItem
from soldier.alignment.stores.agent_config_store import AgentConfigStore
from soldier.customer_data import CustomerDataField
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


class StaticConfigLoader:
    """Loads static configuration for a turn."""

    def __init__(self, config_store: AgentConfigStore):
        """Initialize loader.

        Args:
            config_store: AgentConfigStore implementation
        """
        self._config_store = config_store

    async def load_glossary(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, GlossaryItem]:
        """Load glossary items.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID

        Returns:
            Dictionary mapping term -> GlossaryItem
        """
        items = await self._config_store.get_glossary_items(
            tenant_id=tenant_id,
            agent_id=agent_id,
            enabled_only=True,
        )

        logger.info(
            "glossary_loaded",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            item_count=len(items),
        )

        return {item.term: item for item in items}

    async def load_customer_data_schema(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, CustomerDataField]:
        """Load customer data field definitions.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID

        Returns:
            Dictionary mapping field name -> CustomerDataField
        """
        fields = await self._config_store.get_customer_data_fields(
            tenant_id=tenant_id,
            agent_id=agent_id,
            enabled_only=True,
        )

        logger.info(
            "customer_data_schema_loaded",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            field_count=len(fields),
        )

        return {field.name: field for field in fields}
