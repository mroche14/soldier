"""Agent Conversation Fabric core models.

This module contains the foundational data models for ACF:
- LogicalTurn: Atomic unit of user intent (beats)
- FabricTurnContext: Protocol for ACF's interface to Agent
- Supporting enums and lifecycle models
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class LogicalTurnStatus(str, Enum):
    """Lifecycle states for a logical turn.

    ACF manages these transitions:
    - ACCUMULATING: Waiting for more messages, can absorb new ones
    - PROCESSING: Pipeline is running, may be able to absorb
    - COMPLETE: Response sent successfully
    - SUPERSEDED: Cancelled by newer turn
    """

    ACCUMULATING = "accumulating"
    PROCESSING = "processing"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"


class SupersedeAction(str, Enum):
    """Four-state supersede model.

    When a new message arrives during PROCESSING, CognitivePipeline
    advises ACF which action to take. ACF enforces the decision.
    """

    SUPERSEDE = "supersede"  # Cancel current, start new with all messages
    ABSORB = "absorb"  # Add message to current turn, may restart from checkpoint
    QUEUE = "queue"  # Finish current, then process new as separate turn
    FORCE_COMPLETE = "force_complete"  # Almost done, just finish


class SupersedeDecision(BaseModel):
    """Full decision from CognitivePipeline about how to handle new message."""

    action: SupersedeAction = Field(..., description="What action to take")
    absorb_strategy: str | None = Field(
        default=None, description="How to absorb if ABSORB action"
    )
    reason: str = Field(..., description="Why this decision was made")
    restart_from_phase: int | None = Field(
        default=None, description="Which phase to restart from if ABSORB"
    )


class PhaseArtifact(BaseModel):
    """Cached result from a pipeline phase for checkpoint reuse."""

    phase_number: int = Field(..., description="Which phase produced this")
    phase_name: str = Field(..., description="Phase name for logging")
    artifact_data: dict[str, Any] = Field(..., description="Phase-specific output")
    created_at: datetime = Field(default_factory=utc_now)
    input_hash: str | None = Field(
        default=None, description="Hash of inputs for cache validation"
    )


class SideEffectPolicy(str, Enum):
    """Classification of side effects for supersede decisions."""

    REVERSIBLE = "reversible"  # Can undo, safe to supersede
    IRREVERSIBLE = "irreversible"  # Cannot undo, must queue new messages
    IDEMPOTENT = "idempotent"  # Safe to retry, can supersede


class SideEffect(BaseModel):
    """Record of a side effect executed during turn processing."""

    effect_type: str = Field(..., description="Type of effect (tool_call, api_call)")
    policy: SideEffectPolicy = Field(..., description="Reversibility classification")
    executed_at: datetime = Field(default_factory=utc_now)
    tool_name: str | None = Field(default=None, description="Tool name if tool call")
    idempotency_key: str | None = Field(
        default=None, description="Key for idempotent effects"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Effect-specific data"
    )

    @property
    def irreversible(self) -> bool:
        """Check if this effect prevents superseding."""
        return self.policy == SideEffectPolicy.IRREVERSIBLE


class ScenarioStepRef(BaseModel):
    """Reference to a scenario step state at a point in time."""

    scenario_id: UUID
    scenario_version: int
    step_id: UUID
    step_name: str | None = None


class LogicalTurn(BaseModel):
    """A conversational beat: the atomic unit of user intent.

    A LogicalTurn may contain multiple raw messages that arrived
    in rapid succession and should be treated as one request.

    ACF owns the lifecycle of LogicalTurn:
    - Creation from first RawMessage
    - Accumulation of additional messages
    - Status transitions
    - Supersede enforcement
    """

    id: UUID = Field(default_factory=uuid4)
    session_key: str = Field(
        ..., description="Composite: tenant:agent:customer:channel"
    )

    # Turn grouping for idempotency scoping
    turn_group_id: UUID = Field(default_factory=uuid4)

    # Message accumulation
    messages: list[UUID] = Field(default_factory=list, description="Ordered message IDs")
    status: LogicalTurnStatus = Field(default=LogicalTurnStatus.ACCUMULATING)

    # Timing for adaptive accumulation
    first_at: datetime = Field(..., description="When first message arrived")
    last_at: datetime = Field(..., description="When last message arrived")

    # Completion detection
    completion_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    completion_reason: str | None = Field(
        default=None,
        description="Why accumulation ended (timeout, ai_predicted, explicit_signal, channel_hint)",
    )

    # Checkpoint reuse
    phase_artifacts: dict[int, PhaseArtifact] = Field(default_factory=dict)

    # Side effect tracking
    side_effects: list[SideEffect] = Field(default_factory=list)

    # Scenario state snapshot for safe superseding
    scenario_states_at_start: dict[UUID, ScenarioStepRef] = Field(default_factory=dict)

    # Supersede tracking
    superseded_by: UUID | None = Field(
        default=None, description="Turn that replaced this one"
    )
    superseded_from: UUID | None = Field(
        default=None, description="Turn this one replaced"
    )
    interrupt_point: str | None = Field(
        default=None, description="Where in pipeline when interrupted"
    )

    def can_absorb_message(self) -> bool:
        """Determine if this turn can absorb another incoming message.

        Note: This is a quick check. For PROCESSING status, ACF will
        consult CognitivePipeline via decide_supersede() for the full decision.

        Returns:
            True if message can potentially be added to this turn
        """
        if self.status in [LogicalTurnStatus.COMPLETE, LogicalTurnStatus.SUPERSEDED]:
            return False

        if self.status == LogicalTurnStatus.PROCESSING:
            # Can only absorb if no irreversible side effects executed yet
            return not any(se.irreversible for se in self.side_effects)

        # ACCUMULATING status - always can absorb
        return True

    def absorb_message(self, message_id: UUID, timestamp: datetime) -> None:
        """Add a message to this turn."""
        if not self.can_absorb_message():
            raise ValueError(f"Cannot absorb message in status {self.status}")
        self.messages.append(message_id)
        self.last_at = timestamp

    def mark_processing(self, reason: str = "timeout") -> None:
        """Transition from ACCUMULATING to PROCESSING."""
        if self.status != LogicalTurnStatus.ACCUMULATING:
            raise ValueError(f"Cannot start processing from status {self.status}")
        self.status = LogicalTurnStatus.PROCESSING
        self.completion_reason = reason

    def mark_complete(self) -> None:
        """Mark turn as successfully completed."""
        self.status = LogicalTurnStatus.COMPLETE

    def mark_superseded(
        self, by_turn_id: UUID | None = None, at_point: str | None = None
    ) -> None:
        """Mark turn as superseded by a newer turn."""
        self.status = LogicalTurnStatus.SUPERSEDED
        self.superseded_by = by_turn_id
        self.interrupt_point = at_point


class FabricTurnContext(Protocol):
    """ACF's interface to Agent - infrastructure only.

    IMPORTANT: This context is NOT serializable. It contains live callbacks
    (has_pending_messages, emit_event) that point back to ACF.

    Hatchet serializes only DATA (logical_turn, session_key, IDs).
    FabricTurnContext is REBUILT fresh at the start of each Hatchet step.
    """

    logical_turn: LogicalTurn
    session_key: str
    channel: str

    async def has_pending_messages(self) -> bool:
        """Query: Did any new message arrive during this turn?

        This is a FACT query. Brain decides what to do with the answer.
        Must be monotonic within a turn (once True, stays True).
        """
        ...

    async def emit_event(self, event: "ACFEvent") -> None:
        """Emit an ACFEvent for routing/persistence.

        ACF will:
        - Route to appropriate listeners
        - Persist side effects to LogicalTurn
        - Forward to analytics/live UIs
        """
        ...


@dataclass
class FabricTurnContextImpl:
    """Concrete implementation of FabricTurnContext with live callbacks.

    This is the actual implementation that ACF creates at the start of
    each Hatchet workflow step. It holds references to the workflow's
    internal state and provides the callbacks to the Brain.
    """

    logical_turn: LogicalTurn
    session_key: str
    channel: str
    _check_pending: Callable[[], Awaitable[bool]]
    _route_event: Callable[["ACFEvent"], Awaitable[None]]

    async def has_pending_messages(self) -> bool:
        """Check if new messages arrived during turn processing."""
        return await self._check_pending()

    async def emit_event(self, event: "ACFEvent") -> None:
        """Route event to ACF event handling."""
        await self._route_event(event)


class AccumulationHint(BaseModel):
    """Hint from CognitivePipeline to ACF about expected input.

    Stored in session.last_pipeline_result and loaded by NEXT turn's
    accumulation step. This avoids circular dependency.
    """

    awaiting_required_field: bool = Field(
        default=False, description="Extend window significantly - expecting answer"
    )
    expects_followup: bool = Field(
        default=False, description="Extend window moderately - may have followup"
    )
    input_complete_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Pipeline's guess if input complete"
    )
    expected_input_type: str | None = Field(
        default=None,
        description="What we're waiting for (order_number, confirmation, etc.)",
    )


class MessageShape(str, Enum):
    """Classification of message completeness for accumulation timing."""

    GREETING_ONLY = "greeting_only"  # +500ms
    FRAGMENT = "fragment"  # +400ms
    INCOMPLETE_ENTITY = "incomplete_entity"  # +600ms
    POSSIBLY_INCOMPLETE = "possibly_incomplete"  # +200ms
    LIKELY_COMPLETE = "likely_complete"  # +0ms
