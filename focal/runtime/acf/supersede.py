"""Supersede coordination logic.

Handles decisions about what to do when new messages arrive during
turn processing. This is ACF's enforcement layer - the actual decision
logic comes from CognitivePipeline.
"""

from datetime import datetime
from uuid import UUID, uuid4

from focal.runtime.acf.models import (
    LogicalTurn,
    LogicalTurnStatus,
    SupersedeAction,
    SupersedeDecision,
)


class SupersedeCoordinator:
    """Coordinates supersede decisions between ACF and CognitivePipeline.

    ACF owns the facts:
    - Has this turn executed irreversible side effects?
    - What is the current interrupt point?
    - Can we even consider superseding?

    CognitivePipeline owns the decision:
    - Is the new message a correction, clarification, or new request?
    - Which action makes semantic sense?

    This coordinator bridges the two.
    """

    def can_supersede(self, turn: LogicalTurn) -> bool:
        """Check if turn is eligible for superseding.

        Args:
            turn: Current turn being processed

        Returns:
            True if turn can be superseded, False otherwise
        """
        # Already complete or superseded - cannot supersede
        if turn.status in [LogicalTurnStatus.COMPLETE, LogicalTurnStatus.SUPERSEDED]:
            return False

        # Still accumulating - always can supersede (will just absorb)
        if turn.status == LogicalTurnStatus.ACCUMULATING:
            return True

        # Processing - check for irreversible effects
        if turn.status == LogicalTurnStatus.PROCESSING:
            return not any(se.irreversible for se in turn.side_effects)

        return False

    def enforce_decision(
        self,
        decision: SupersedeDecision,
        current_turn: LogicalTurn,
        new_message_id: UUID,
        new_message_timestamp: datetime,
    ) -> LogicalTurn:
        """Enforce a supersede decision from CognitivePipeline.

        Args:
            decision: What action to take
            current_turn: Turn being processed
            new_message_id: ID of new message
            new_message_timestamp: When new message arrived

        Returns:
            Either the modified current_turn or a new turn
        """
        if decision.action == SupersedeAction.SUPERSEDE:
            return self._handle_supersede(
                current_turn, new_message_id, new_message_timestamp
            )

        elif decision.action == SupersedeAction.ABSORB:
            return self._handle_absorb(
                current_turn, new_message_id, new_message_timestamp
            )

        elif decision.action == SupersedeAction.QUEUE:
            # Queue means current turn continues, new message goes to queue
            # ACF caller is responsible for actually enqueueing
            return current_turn

        elif decision.action == SupersedeAction.FORCE_COMPLETE:
            # Force complete means ignore new message temporarily
            # ACF caller may re-process it after current turn completes
            return current_turn

        else:
            raise ValueError(f"Unknown supersede action: {decision.action}")

    def _handle_supersede(
        self,
        current_turn: LogicalTurn,
        new_message_id: UUID,
        new_message_timestamp: datetime,
    ) -> LogicalTurn:
        """Create new turn, mark current as superseded.

        Args:
            current_turn: Turn being superseded
            new_message_id: First message of new turn
            new_message_timestamp: Message timestamp

        Returns:
            New LogicalTurn that supersedes current
        """
        # Mark current turn as superseded
        new_turn_id = uuid4()
        current_turn.mark_superseded(by_turn_id=new_turn_id)

        # Create new turn inheriting turn_group_id
        new_turn = LogicalTurn(
            id=new_turn_id,
            session_key=current_turn.session_key,
            turn_group_id=current_turn.turn_group_id,  # INHERIT for idempotency
            messages=[new_message_id],
            first_at=new_message_timestamp,
            last_at=new_message_timestamp,
            superseded_from=current_turn.id,
            status=LogicalTurnStatus.ACCUMULATING,
        )

        return new_turn

    def _handle_absorb(
        self,
        current_turn: LogicalTurn,
        new_message_id: UUID,
        new_message_timestamp: datetime,
    ) -> LogicalTurn:
        """Absorb new message into current turn.

        Args:
            current_turn: Turn to absorb into
            new_message_id: Message to absorb
            new_message_timestamp: Message timestamp

        Returns:
            Modified current_turn
        """
        current_turn.absorb_message(new_message_id, new_message_timestamp)
        return current_turn


def build_tool_idempotency_key(
    tool_name: str,
    business_key: str,
    turn: LogicalTurn,
) -> str:
    """Build idempotency key scoped to turn group.

    This ensures:
    - Supersede chain shares key → one execution
    - QUEUE creates new key → allows re-execution in new context

    Args:
        tool_name: Name of the tool
        business_key: Business-level key (e.g., order_id)
        turn: Current logical turn

    Returns:
        Idempotency key for tool execution
    """
    return f"{tool_name}:{business_key}:turn_group:{turn.turn_group_id}"
