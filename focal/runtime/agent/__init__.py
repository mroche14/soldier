"""Agent runtime layer.

Manages agent lifecycle, configuration caching, and execution contexts.

Key components:
- AgentRuntime: Loads and caches agent configurations
- AgentContext: Aggregated execution context for pipeline
- AgentMetadata: Runtime view of agent configuration
- AgentCapabilities: Feature flags for agent behavior
"""

from focal.runtime.agent.context import AgentContext
from focal.runtime.agent.models import AgentCapabilities, AgentMetadata
from focal.runtime.agent.runtime import AgentRuntime

__all__ = [
    "AgentRuntime",
    "AgentContext",
    "AgentMetadata",
    "AgentCapabilities",
]
