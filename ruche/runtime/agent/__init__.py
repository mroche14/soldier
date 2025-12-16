"""Agent runtime layer.

Manages agent lifecycle, configuration caching, and execution contexts.

Key components:
- AgentRuntime: Loads and caches agent configurations
- AgentContext: Runtime instance of configured Agent with Brain, Toolbox, Channels
- AgentTurnContext: Per-turn context wrapping FabricTurnContext with AgentContext
- AgentMetadata: Runtime view of agent configuration (deprecated - use Agent model)
- AgentCapabilities: Feature flags for agent behavior (deprecated)
"""

from ruche.runtime.agent.context import AgentContext, AgentTurnContext
from ruche.runtime.agent.models import AgentCapabilities, AgentMetadata
from ruche.runtime.agent.runtime import AgentRuntime

__all__ = [
    "AgentRuntime",
    "AgentContext",
    "AgentTurnContext",
    "AgentMetadata",
    "AgentCapabilities",
]
