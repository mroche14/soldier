"""Brain protocol definitions.

Brain is an ABC that thinking units implement. Agent owns its Brain.
FOCAL, LangGraph, Agno are Brain implementations.
"""

from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    from ruche.brains.focal.models.brain_result import BrainResult
    from ruche.runtime.agent.context import AgentTurnContext


class SupersedeDecision:
    """Decision on whether to supersede current turn with new message."""

    supersede: bool
    reason: str


class Brain(Protocol):
    """Protocol that all brain implementations must satisfy.

    A Brain is the thinking unit of an Agent. It receives context
    about the current turn and produces a BrainResult with response
    segments, artifacts, and optional handoff requests.
    """

    name: str

    async def think(self, ctx: "AgentTurnContext") -> "BrainResult":
        """Process a turn and generate a response.

        Args:
            ctx: The turn context with access to toolbox, session, etc.

        Returns:
            BrainResult containing response segments and artifacts
        """
        ...


class SupersedeCapable(Protocol):
    """Protocol for brains that can decide on message supersession.

    When a new message arrives while processing is ongoing,
    the brain can decide whether to:
    - Continue with current turn (supersede=False)
    - Abandon current turn and start fresh (supersede=True)
    """

    async def decide_supersede(
        self,
        current: "LogicalTurn",
        new: "RawMessage",
        interrupt_point: str,
    ) -> SupersedeDecision:
        """Decide if new message should supersede current processing.

        Args:
            current: The logical turn currently being processed
            new: The new incoming message
            interrupt_point: Where in processing we currently are

        Returns:
            SupersedeDecision indicating whether to supersede
        """
        ...
