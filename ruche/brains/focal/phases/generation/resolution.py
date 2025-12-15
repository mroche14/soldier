"""Turn resolution determination.

Determines final resolution based on categories and response type.
"""

from ruche.brains.focal.models.outcome import OutcomeCategory, TurnOutcome


def determine_resolution(
    categories: list[OutcomeCategory],
    response_type: str | None = None,
) -> str:
    """Determine turn resolution from categories and response type.

    Args:
        categories: All categories accumulated during pipeline
        response_type: From ResponsePlan (ASK, ANSWER, ESCALATE, etc.)

    Returns:
        Resolution: ANSWERED, PARTIAL, REDIRECTED, ERROR, BLOCKED
    """
    # Priority order (earlier wins)
    if OutcomeCategory.POLICY_RESTRICTION in categories:
        return "BLOCKED"

    if OutcomeCategory.SYSTEM_ERROR in categories:
        return "ERROR"

    if response_type == "ESCALATE":
        return "REDIRECTED"

    if OutcomeCategory.AWAITING_USER_INPUT in categories:
        return "PARTIAL"

    if OutcomeCategory.ANSWERED in categories:
        return "ANSWERED"

    # Default: if none of the above, consider it answered
    return "ANSWERED"


def build_turn_outcome(
    categories: list[OutcomeCategory],
    response_type: str | None = None,
    escalation_reason: str | None = None,
    blocking_rule_id: str | None = None,
) -> TurnOutcome:
    """Build complete TurnOutcome from pipeline state.

    Args:
        categories: All categories from pipeline and LLM
        response_type: From ResponsePlan
        escalation_reason: If escalated, why
        blocking_rule_id: If blocked, which rule

    Returns:
        Complete TurnOutcome
    """
    resolution = determine_resolution(categories, response_type)

    return TurnOutcome(
        resolution=resolution,
        categories=categories,
        escalation_reason=escalation_reason,
        blocking_rule_id=blocking_rule_id,
    )
