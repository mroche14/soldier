"""AgentRuntime: Lifecycle and caching for agent execution contexts.

The AgentRuntime manages:
1. Loading agent configuration from ConfigStore
2. Caching AgentContext instances
3. Cache invalidation on config changes
4. Providing execution contexts to pipeline
"""

import hashlib
import json
from typing import TYPE_CHECKING
from uuid import UUID

from ruche.runtime.agent.context import AgentContext
from ruche.runtime.agent.models import AgentCapabilities, AgentMetadata

if TYPE_CHECKING:
    from ruche.config.stores.base import ConfigStore
    from ruche.interlocutor_data.stores.base import ProfileStore
    from ruche.memory.stores.base import MemoryStore


class AgentRuntime:
    """Manages agent lifecycle and execution context caching.

    Responsibilities:
    - Load agent configuration from stores
    - Build and cache AgentContext instances
    - Invalidate cache when configuration changes
    - Provide execution contexts to pipelines

    Note: This is a runtime optimization layer. The actual configuration
    lives in ConfigStore.
    """

    def __init__(
        self,
        config_store: "ConfigStore",
        memory_store: "MemoryStore",
        profile_store: "ProfileStore",
        cache_ttl_seconds: int = 300,  # 5 minutes default
    ):
        """Initialize agent runtime.

        Args:
            config_store: Configuration store for agent data
            memory_store: Memory store for conversations
            profile_store: Customer profile store
            cache_ttl_seconds: How long to cache agent contexts
        """
        self._config_store = config_store
        self._memory_store = memory_store
        self._profile_store = profile_store
        self._cache_ttl_seconds = cache_ttl_seconds

        # Cache: agent_id -> AgentContext
        self._context_cache: dict[UUID, AgentContext] = {}

        # Cache: agent_id -> config_hash
        self._config_hashes: dict[UUID, str] = {}

    async def get_context(
        self, tenant_id: UUID, agent_id: UUID, force_reload: bool = False
    ) -> AgentContext:
        """Get execution context for an agent.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            force_reload: Force reload from store (skip cache)

        Returns:
            AgentContext ready for pipeline execution

        Raises:
            ValueError: If agent not found or disabled
        """
        # Check cache if not forcing reload
        if not force_reload and agent_id in self._context_cache:
            context = self._context_cache[agent_id]

            # Verify config hasn't changed
            if await self._is_config_current(tenant_id, agent_id):
                return context

        # Load fresh context
        context = await self._load_context(tenant_id, agent_id)

        # Cache it
        self._context_cache[agent_id] = context

        return context

    async def invalidate(self, agent_id: UUID) -> None:
        """Invalidate cached context for an agent.

        Args:
            agent_id: Agent to invalidate
        """
        self._context_cache.pop(agent_id, None)
        self._config_hashes.pop(agent_id, None)

    async def invalidate_all(self) -> None:
        """Invalidate all cached contexts."""
        self._context_cache.clear()
        self._config_hashes.clear()

    async def _load_context(self, tenant_id: UUID, agent_id: UUID) -> AgentContext:
        """Load agent context from stores.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Loaded AgentContext

        Raises:
            ValueError: If agent not found
        """
        # Load agent from ConfigStore
        # Note: This assumes ConfigStore has a get_agent method
        # Actual implementation depends on ConfigStore interface
        agent = await self._config_store.get_agent(tenant_id, agent_id)

        if agent is None:
            raise ValueError(f"Agent {agent_id} not found for tenant {tenant_id}")

        # Build metadata
        metadata = AgentMetadata(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            version=agent.current_version,
            enabled=agent.enabled,
            default_model=agent.settings.model,
            default_temperature=agent.settings.temperature,
            default_max_tokens=agent.settings.max_tokens,
        )

        # Build capabilities
        # Note: In future, this would be loaded from agent configuration
        # For now, use sensible defaults
        capabilities = AgentCapabilities()

        # Compute config hash for cache invalidation
        config_hash = self._compute_config_hash(agent)
        metadata.config_hash = config_hash
        self._config_hashes[agent_id] = config_hash

        # Build context
        context = AgentContext(
            metadata=metadata,
            capabilities=capabilities,
            config_store=self._config_store,
            memory_store=self._memory_store,
            profile_store=self._profile_store,
        )

        return context

    async def _is_config_current(self, tenant_id: UUID, agent_id: UUID) -> bool:
        """Check if cached config is still current.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            True if cached config matches current config
        """
        # Get current config hash
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if agent is None:
            return False

        current_hash = self._compute_config_hash(agent)

        # Compare with cached hash
        cached_hash = self._config_hashes.get(agent_id)
        return current_hash == cached_hash

    def _compute_config_hash(self, agent: "Agent") -> str:
        """Compute hash of agent configuration.

        Args:
            agent: Agent model

        Returns:
            SHA256 hash of configuration
        """
        # Create deterministic representation
        config_data = {
            "id": str(agent.id),
            "version": agent.current_version,
            "settings": agent.settings.model_dump(),
            "system_prompt": agent.system_prompt,
        }

        # Serialize and hash
        config_json = json.dumps(config_data, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()
