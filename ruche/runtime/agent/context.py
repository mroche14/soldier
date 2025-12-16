"""Agent execution context.

The AgentContext dataclass aggregates all runtime dependencies needed
to execute a turn for an agent.

The AgentTurnContext wraps FabricTurnContext with AgentContext to provide
the complete context for Brain.think() execution.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    # Avoid circular imports
    from ruche.brains.focal.models.agent import Agent
    from ruche.infrastructure.channels.models import ChannelBinding, ChannelPolicy
    from ruche.infrastructure.providers.llm.executor import LLMExecutor
    from ruche.infrastructure.toolbox.models import ToolResult
    from ruche.infrastructure.toolbox.toolbox import Toolbox
    from ruche.runtime.acf.models import LogicalTurn
    from ruche.runtime.brain.protocol import Brain


@dataclass
class AgentContext:
    """Runtime instance of a configured Agent.

    Created by AgentRuntime, cached for reuse, invalidated on config change.
    Contains all components needed to process a turn.

    This is the authoritative AgentContext structure per AGENT_RUNTIME_SPEC.md.
    It holds the instantiated components (Brain, Toolbox, ChannelBindings) rather
    than just metadata and store references.
    """

    # Configuration (from ConfigStore)
    agent: "Agent"
    """Agent configuration model (defines WHAT the agent is)."""

    # Brain (FOCAL, LangGraph, Agno)
    brain: "Brain"
    """Brain implementation for this agent (FOCAL, LangGraph, etc.)."""

    # Tool execution facade
    toolbox: "Toolbox"
    """Toolbox for discovering and executing tools."""

    # Available channels for this agent
    channel_bindings: dict[str, "ChannelBinding"]
    """Channel bindings keyed by channel name (e.g., 'whatsapp', 'webchat')."""

    # Channel policies (single source of truth for channel behavior)
    channel_policies: dict[str, "ChannelPolicy"]
    """
    Channel policies keyed by channel name.
    Single source of truth for channel behavior, used by ACF, Agent, and ChannelGateway.
    """

    # Optional: Agent-specific LLM executor (if different from default)
    llm_executor: "LLMExecutor | None" = None
    """Optional agent-specific LLM executor override."""

    @property
    def agent_id(self) -> UUID:
        """Agent identifier from configuration."""
        return self.agent.id

    @property
    def tenant_id(self) -> UUID:
        """Tenant identifier from configuration."""
        return self.agent.tenant_id


@dataclass
class AgentTurnContext:
    """Per-turn context wrapping FabricTurnContext with AgentContext.

    This is the context passed to Brain.think() - it provides:
    - Access to the current turn via fabric context
    - Access to agent configuration via agent context
    - Convenience methods for common operations

    The FabricTurnContext is NOT serializable (rebuilt each Hatchet step),
    but AgentContext is stable for the agent's lifetime.
    """

    fabric: Any  # FabricTurnContext - using Any to avoid circular import
    agent_context: AgentContext

    @property
    def toolbox(self) -> "Toolbox":
        """Access the agent's toolbox for tool execution."""
        return self.agent_context.toolbox

    @property
    def logical_turn(self) -> "LogicalTurn":
        """Access the logical turn being processed."""
        return self.fabric.logical_turn

    async def has_pending_messages(self) -> bool:
        """Check if there are pending messages in the channel.

        This callback is provided by ACF's FabricTurnContext to allow
        Brain to check if the user has sent more messages while thinking.

        Returns:
            True if new messages have arrived during processing
        """
        return await self.fabric.has_pending_messages()

    async def emit_event(self, event: Any) -> None:
        """Emit an event to the ACF event bus.

        Args:
            event: ACFEvent to emit (using Any to avoid forward reference issues)
        """
        await self.fabric.emit_event(event)

    async def execute_tool(self, tool_name: str, args: dict[str, Any]) -> "ToolResult":
        """Execute a tool through the agent's toolbox.

        This is a convenience method that provides the full context
        to the toolbox for enforcement and audit.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments

        Returns:
            ToolResult with execution outcome
        """
        return await self.toolbox.execute(tool_name, args, self)
