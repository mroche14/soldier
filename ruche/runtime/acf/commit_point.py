"""Commit point tracking for safe superseding.

Commit points are irreversible moments in turn processing where we must
commit to the current turn and cannot supersede anymore.
"""

from ruche.runtime.acf.models import LogicalTurn, SideEffect, SideEffectPolicy


class CommitPointTracker:
    """Tracks commit points during turn processing.

    A commit point is reached when:
    1. An irreversible side effect is executed
    2. A scenario checkpoint is reached
    3. Response is sent to user (implicit commit)

    After a commit point, new messages must be queued as separate turns.
    """

    def has_reached_commit_point(self, turn: LogicalTurn) -> bool:
        """Check if turn has reached a commit point.

        Args:
            turn: Turn to check

        Returns:
            True if commit point reached, False otherwise
        """
        # Check for irreversible side effects
        for side_effect in turn.side_effects:
            if side_effect.policy == SideEffectPolicy.IRREVERSIBLE:
                return True

        # Check for scenario checkpoints
        # (In future: check session state for checkpoint markers)

        return False

    def record_side_effect(
        self,
        turn: LogicalTurn,
        effect_type: str,
        policy: SideEffectPolicy,
        tool_name: str | None = None,
        idempotency_key: str | None = None,
        details: dict | None = None,
    ) -> SideEffect:
        """Record a side effect on the turn.

        Args:
            turn: Turn to record effect on
            effect_type: Type of effect (tool_call, api_call, etc.)
            policy: Reversibility policy
            tool_name: Tool name if tool call
            idempotency_key: Key for idempotent effects
            details: Additional effect data

        Returns:
            The created SideEffect
        """
        side_effect = SideEffect(
            effect_type=effect_type,
            policy=policy,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            details=details or {},
        )

        turn.side_effects.append(side_effect)
        return side_effect

    def classify_tool_policy(self, tool_name: str) -> SideEffectPolicy:
        """Classify a tool's side effect policy.

        Args:
            tool_name: Name of the tool

        Returns:
            Side effect policy for this tool

        Note:
            This is a placeholder. In production, tool policies should be
            configured in the tool registry.
        """
        # Placeholder classification
        # In reality, this should come from tool metadata
        IRREVERSIBLE_TOOLS = {
            "send_email",
            "send_sms",
            "create_order",
            "process_refund",
            "cancel_order",
        }

        IDEMPOTENT_TOOLS = {
            "get_order",
            "search_products",
            "validate_address",
        }

        if tool_name in IRREVERSIBLE_TOOLS:
            return SideEffectPolicy.IRREVERSIBLE
        elif tool_name in IDEMPOTENT_TOOLS:
            return SideEffectPolicy.IDEMPOTENT
        else:
            # Conservative default: assume reversible
            return SideEffectPolicy.REVERSIBLE
