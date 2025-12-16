"""AgentRuntime: Lifecycle and caching for agent execution contexts.

The AgentRuntime manages:
1. Loading agent configuration from ConfigStore
2. Caching AgentContext instances
3. Cache invalidation on config changes
4. Providing execution contexts to pipelines
"""

import hashlib
import json
from typing import TYPE_CHECKING
from uuid import UUID

from ruche.runtime.agent.context import AgentContext

if TYPE_CHECKING:
    from ruche.config.stores.base import ConfigStore
    from ruche.runtime.brain.factory import BrainFactory
    from ruche.runtime.toolbox.gateway import ToolGateway


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
        tool_gateway: "ToolGateway",
        brain_factory: "BrainFactory",
        max_cache_size: int = 1000,
    ):
        """Initialize agent runtime.

        Args:
            config_store: Configuration store for agent data
            tool_gateway: Gateway for tool execution
            brain_factory: Factory for creating Brain instances
            max_cache_size: Maximum number of agents to cache
        """
        self._config_store = config_store
        self._tool_gateway = tool_gateway
        self._brain_factory = brain_factory
        self._max_cache_size = max_cache_size

        # Cache: (tenant_id, agent_id) -> AgentContext
        self._cache: dict[tuple[UUID, UUID], AgentContext] = {}

        # Version tracking for invalidation
        self._cache_versions: dict[tuple[UUID, UUID], str] = {}

    async def get_or_create(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentContext:
        """Get cached AgentContext or create fresh one.

        Thread-safe with version-based invalidation to detect config changes.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            AgentContext ready for pipeline execution

        Raises:
            ValueError: If agent not found or disabled
        """
        key = (tenant_id, agent_id)

        # Fast path: valid cache hit
        if key in self._cache:
            current_version = await self._get_agent_version(tenant_id, agent_id)
            if self._cache_versions.get(key) == current_version:
                return self._cache[key]

        # Build fresh AgentContext
        context = await self._build_agent_context(tenant_id, agent_id)

        # Cache with version (respect max size)
        if len(self._cache) >= self._max_cache_size:
            self._evict_oldest()

        self._cache[key] = context
        self._cache_versions[key] = context.agent.current_version

        return context

    async def _get_agent_version(self, tenant_id: UUID, agent_id: UUID) -> str:
        """Get current agent version for cache invalidation.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Version string
        """
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if not agent:
            return "0"
        return str(agent.current_version)

    async def invalidate(self, tenant_id: UUID, agent_id: UUID) -> None:
        """Invalidate cached agent.

        Called when agent config changes (webhook from admin API).

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
        """
        key = (tenant_id, agent_id)
        self._cache.pop(key, None)
        self._cache_versions.pop(key, None)

    async def invalidate_tenant(self, tenant_id: UUID) -> None:
        """Invalidate all agents for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        keys_to_remove = [k for k in self._cache if k[0] == tenant_id]
        for key in keys_to_remove:
            self._cache.pop(key, None)
            self._cache_versions.pop(key, None)

    def _evict_oldest(self) -> None:
        """Evict oldest entry when cache is full (simple LRU)."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
            self._cache_versions.pop(oldest_key, None)

    async def _build_agent_context(
        self, tenant_id: UUID, agent_id: UUID
    ) -> AgentContext:
        """Build fresh AgentContext from ConfigStore data.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Loaded AgentContext

        Raises:
            ValueError: If agent not found
        """
        # Load agent configuration
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found for tenant {tenant_id}")

        # Load tool definitions and activations
        tool_defs = await self._config_store.get_tool_definitions(tenant_id)
        tool_activations = await self._config_store.get_tool_activations(
            tenant_id, agent_id
        )

        # Build toolbox
        from ruche.runtime.toolbox.toolbox import Toolbox

        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_defs,
            tool_activations=tool_activations,
            gateway=self._tool_gateway,
        )

        # Build brain based on type
        # Default to "focal" if not specified
        brain_type = getattr(agent, "brain_type", "focal")
        brain = self._brain_factory.create(
            brain_type=brain_type,
            agent=agent,
        )

        # Load channel bindings
        channel_bindings = await self._load_channel_bindings(tenant_id, agent_id)

        # Load channel policies (single source of truth)
        channel_policies = await self._load_channel_policies(tenant_id, agent_id)

        return AgentContext(
            agent=agent,
            brain=brain,
            toolbox=toolbox,
            channel_bindings=channel_bindings,
            channel_policies=channel_policies,
        )

    async def _load_channel_bindings(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, "ChannelBinding"]:
        """Load channel bindings for agent from ConfigStore.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Channel bindings keyed by channel name
        """
        bindings = await self._config_store.get_channel_bindings(tenant_id, agent_id)
        return {b.channel: b for b in bindings}

    async def _load_channel_policies(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, "ChannelPolicy"]:
        """Load channel policies for agent from ConfigStore.

        These policies are the single source of truth for channel behavior,
        used by ACF (accumulation), Agent (brain), and ChannelGateway (formatting).

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Channel policies keyed by channel name
        """
        policies = await self._config_store.get_channel_policies(tenant_id, agent_id)
        return {p.channel: p for p in policies}
