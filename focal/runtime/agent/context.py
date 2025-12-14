"""Agent execution context.

The AgentContext dataclass aggregates all runtime dependencies needed
to execute a turn for an agent.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from focal.runtime.agent.models import AgentCapabilities, AgentMetadata

if TYPE_CHECKING:
    # Avoid circular imports
    from focal.config.stores.base import ConfigStore
    from focal.customer_data.stores.base import ProfileStore
    from focal.memory.stores.base import MemoryStore


@dataclass
class AgentContext:
    """Execution context for an agent.

    Aggregates all runtime dependencies needed to process turns.
    Created by AgentRuntime and passed to pipeline execution.

    This is the runtime equivalent of dependency injection - all stores,
    providers, and configuration are resolved once and passed down.
    """

    # Agent identity
    metadata: AgentMetadata

    # Agent capabilities (feature flags)
    capabilities: AgentCapabilities

    # Store references (injected, not created here)
    config_store: "ConfigStore"
    memory_store: "MemoryStore"
    profile_store: "ProfileStore"

    # Provider references (injected)
    # Note: Providers are typically accessed through config, not stored directly
    # But could be cached here for performance

    # Configuration snapshot
    # Note: This would contain pipeline config, glossary, etc.
    # For now, these are loaded on-demand from config_store
    # Future: Consider caching here

    def __post_init__(self):
        """Validate context after initialization."""
        if not self.metadata.enabled:
            raise ValueError(f"Agent {self.metadata.agent_id} is disabled")
