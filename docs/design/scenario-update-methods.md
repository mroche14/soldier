# Scenario Update Methods

This document describes how Soldier handles scenario updates while customers have active sessions. The core challenge: **WhatsApp and other long-lived sessions can span days or weeks, and scenario changes may be urgent.**

## Problem Statement

Scenarios are directed graphs that customers traverse over time. When a scenario is updated mid-session:

```
Customer is here ──────────┐
                           ▼
Old scenario:   A ──────► B ──────► C

New scenario:   A ──► N1 ──► B ──► N2 ──► C
                      │             │
                 [age check]   [new fork]
                      │             │
                      └──► D        └──► E
```

**Questions that must be answered:**

1. Should the customer see N2 and the new downstream fork?
2. What if N1 collected critical data needed for the fork at N2?
3. What if N1 had a fork that would have sent the customer to D instead of B?
4. What if the customer already completed an irreversible action at B?

---

## Solution: Pre-Computed Migration Plans

Rather than computing reconciliation logic per-session at runtime, we **pre-compute a Migration Plan** when the scenario is updated. This plan specifies exactly what should happen for customers at each step.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MIGRATION PLAN CONCEPT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Scenario V1 → V2 update generates:                                         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  MIGRATION PLAN (computed once, applied to many sessions)              │ │
│  │                                                                         │ │
│  │  For customers at step A:                                              │ │
│  │    → action: continue                                                  │ │
│  │    → collect: []                                                       │ │
│  │                                                                         │ │
│  │  For customers at step B:                                              │ │
│  │    → action: collect_then_continue                                     │ │
│  │    → collect: ["email"]                                                │ │
│  │    → reason: "New step N1 collects email, needed for fork at N2"       │ │
│  │                                                                         │ │
│  │  For customers at step C:                                              │ │
│  │    → action: evaluate_teleport                                         │ │
│  │    → condition: "age < 18"                                             │ │
│  │    → if true: teleport to D                                            │ │
│  │    → if false: continue                                                │ │
│  │    → blocked_by: [checkpoint_order_placed]                             │ │
│  │                                                                         │ │
│  │  For customers at step X (deleted):                                    │ │
│  │    → action: relocate                                                  │ │
│  │    → target: B (nearest anchor)                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  At runtime: lookup plan[session.active_step_id], apply                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Benefits

| Aspect | Benefit |
|--------|---------|
| **Performance** | Computed once per update, not per-session |
| **Reviewable** | Operator sees exactly what will happen before deploying |
| **Auditable** | "Migration plan X was applied to session Y" |
| **Testable** | Plan can be validated before deployment |
| **Debuggable** | Clear artifact explains why customer was moved/asked |

---

## Scenario Update Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCENARIO UPDATE WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. EDIT              Operator modifies scenario in Control Plane UI         │
│         │                                                                    │
│         ▼                                                                    │
│  2. GENERATE          System computes MigrationPlan automatically            │
│     PLAN              → Analyze graph diff                                   │
│                       → Determine action for each step in old version       │
│                       → Identify data requirements and checkpoint conflicts │
│         │                                                                    │
│         ▼                                                                    │
│  3. REVIEW            Operator reviews migration summary                     │
│     (required)        → Affected steps, required data collection            │
│                       → Teleportation targets, checkpoint warnings          │
│                       → Can modify actions before confirming                │
│         │                                                                    │
│         ▼                                                                    │
│  4. APPROVE           Operator confirms deployment                           │
│         │                                                                    │
│         ▼                                                                    │
│  5. DEPLOY            Save new scenario version + migration plan             │
│                       → Archive old version (7-day retention)               │
│                       → Publish config update via PubSub                    │
│         │                                                                    │
│         ▼                                                                    │
│  6. APPLY             On each session's next turn:                           │
│     (per session)     → Check version mismatch                              │
│                       → Lookup plan[current_step_id]                        │
│                       → Apply action (collect/teleport/continue)            │
│                       → Update session.active_scenario_version              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Migration Plan

```python
@dataclass
class MigrationPlan:
    """Pre-computed migration plan for a scenario version transition.

    Generated when a scenario is updated. Contains instructions for
    what to do with customers at each step of the old version.
    """
    id: UUID = field(default_factory=uuid4)
    scenario_id: UUID
    from_version: int
    to_version: int

    # Action for each step in the OLD version
    # Key: step_id from old version
    step_actions: Dict[UUID, StepMigrationAction] = field(default_factory=dict)

    # Summary for operator review
    summary: MigrationSummary

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # Operator who triggered update
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    # Status
    status: str = "pending"  # "pending" | "approved" | "deployed" | "superseded"
```

### Step Migration Action

```python
@dataclass
class StepMigrationAction:
    """What to do for customers at a specific step in the old version."""

    # Identity
    from_step_id: UUID
    from_step_name: str  # For readability in review UI

    # Action type
    action: str  # "continue" | "collect" | "teleport" | "relocate" | "exit"

    # ─────────────────────────────────────────────────────────────────────────
    # For action="collect": Fields that must be collected before continuing
    # ─────────────────────────────────────────────────────────────────────────
    collect_fields: List[str] = field(default_factory=list)
    collect_reason: Optional[str] = None  # "Required for fork at step N2"

    # ─────────────────────────────────────────────────────────────────────────
    # For action="teleport": Conditional move to different step
    # ─────────────────────────────────────────────────────────────────────────
    teleport_target_id: Optional[UUID] = None
    teleport_target_name: Optional[str] = None  # For readability
    teleport_condition: Optional[str] = None  # "age < 18" (evaluated at runtime)
    teleport_condition_fields: List[str] = field(default_factory=list)  # ["age"]
    teleport_fallback_action: str = "continue"  # What if condition is false

    # ─────────────────────────────────────────────────────────────────────────
    # For action="relocate": Step was deleted, move to anchor
    # ─────────────────────────────────────────────────────────────────────────
    relocate_target_id: Optional[UUID] = None
    relocate_target_name: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Checkpoint protection: Teleportation blocked if these were passed
    # ─────────────────────────────────────────────────────────────────────────
    blocked_by_checkpoints: List[CheckpointRef] = field(default_factory=list)

    # ─────────────────────────────────────────────────────────────────────────
    # For action="execute": Required actions that were skipped
    # ─────────────────────────────────────────────────────────────────────────
    execute_actions: List[UUID] = field(default_factory=list)

    # ─────────────────────────────────────────────────────────────────────────
    # Human-readable explanation (shown in review UI and logs)
    # ─────────────────────────────────────────────────────────────────────────
    reason: str = ""


@dataclass
class CheckpointRef:
    """Reference to a checkpoint that might block teleportation."""
    step_id: UUID
    step_name: str
    checkpoint_description: str  # "Order placed", "Payment processed"
```

### Migration Summary

```python
@dataclass
class MigrationSummary:
    """Human-readable summary for operator review before deployment."""

    # Counts
    total_steps_in_old_version: int
    steps_unchanged: int          # action="continue" with no collection
    steps_needing_collection: int # action="collect"
    steps_with_teleport: int      # action="teleport"
    steps_deleted: int            # action="relocate"
    steps_with_actions: int       # action="execute"

    # Affected customers (estimated)
    estimated_sessions_affected: int = 0  # Count from SessionStore
    sessions_by_step: Dict[str, int] = field(default_factory=dict)  # step_name -> count

    # Warnings that need operator attention
    warnings: List[MigrationWarning] = field(default_factory=list)

    # Field collection requirements
    fields_to_collect: List[FieldCollectionInfo] = field(default_factory=list)


@dataclass
class MigrationWarning:
    """Warning for operator review."""
    severity: str  # "info" | "warning" | "critical"
    step_name: str
    message: str
    # e.g., "Customers at 'Order Confirmation' who are under 18 should be rejected,
    #        but checkpoint 'Payment Processed' prevents teleportation.
    #        These sessions will continue with a logged warning."


@dataclass
class FieldCollectionInfo:
    """Information about a field that needs collection."""
    field_name: str
    display_name: str
    affected_steps: List[str]  # Step names where this applies
    reason: str  # "Required for premium eligibility check"
    can_extract_from_conversation: bool  # Hint for runtime
```

---

## Migration Plan Generation

When an operator saves a scenario update, the system generates a migration plan:

```python
async def generate_migration_plan(
    old_scenario: Scenario,
    new_scenario: Scenario,
    operator_id: Optional[str] = None,
) -> MigrationPlan:
    """
    Generate a migration plan for transitioning from old to new scenario version.

    Analyzes the graph diff and determines what action is needed for
    customers at each step of the old version.
    """

    plan = MigrationPlan(
        scenario_id=old_scenario.id,
        from_version=old_scenario.version,
        to_version=new_scenario.version,
        created_by=operator_id,
        step_actions={},
        summary=MigrationSummary(
            total_steps_in_old_version=len(old_scenario.steps),
            steps_unchanged=0,
            steps_needing_collection=0,
            steps_with_teleport=0,
            steps_deleted=0,
            steps_with_actions=0,
        )
    )

    # Build lookup structures
    old_step_ids = {s.id for s in old_scenario.steps}
    new_step_ids = {s.id for s in new_scenario.steps}
    new_steps_by_id = {s.id: s for s in new_scenario.steps}

    # Process each step in the old version
    for old_step in old_scenario.steps:
        action = await compute_step_action(
            old_step=old_step,
            old_scenario=old_scenario,
            new_scenario=new_scenario,
            old_step_ids=old_step_ids,
            new_step_ids=new_step_ids,
        )

        plan.step_actions[old_step.id] = action

        # Update summary counts
        if action.action == "continue" and not action.collect_fields:
            plan.summary.steps_unchanged += 1
        elif action.action == "collect" or action.collect_fields:
            plan.summary.steps_needing_collection += 1
        elif action.action == "teleport":
            plan.summary.steps_with_teleport += 1
        elif action.action == "relocate":
            plan.summary.steps_deleted += 1
        elif action.action == "execute":
            plan.summary.steps_with_actions += 1

    # Generate warnings
    plan.summary.warnings = generate_warnings(plan)

    # Estimate affected sessions
    plan.summary.estimated_sessions_affected = await count_affected_sessions(
        old_scenario.id,
        old_scenario.version
    )

    return plan


async def compute_step_action(
    old_step: ScenarioStep,
    old_scenario: Scenario,
    new_scenario: Scenario,
    old_step_ids: Set[UUID],
    new_step_ids: Set[UUID],
) -> StepMigrationAction:
    """Compute the migration action for a single step."""

    action = StepMigrationAction(
        from_step_id=old_step.id,
        from_step_name=old_step.name,
        action="continue",
        reason="No changes affecting this step"
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 1: Step was deleted
    # ═══════════════════════════════════════════════════════════════════════════

    if old_step.id not in new_step_ids:
        anchor = find_nearest_anchor_in_new(old_step, old_scenario, new_scenario)

        action.action = "relocate"
        action.relocate_target_id = anchor.id if anchor else None
        action.relocate_target_name = anchor.name if anchor else None
        action.reason = f"Step deleted. Relocating to '{anchor.name if anchor else 'exit'}'."

        return action

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 2: Check for new upstream forks
    # ═══════════════════════════════════════════════════════════════════════════

    new_upstream_forks = find_new_upstream_forks(
        old_step.id, old_scenario, new_scenario
    )

    for fork in new_upstream_forks:
        # Check if fork could redirect customer elsewhere
        branches = get_fork_branches(fork, new_scenario)

        if len(branches) > 1:
            # Find which branch leads to current position
            branch_to_current = find_branch_leading_to(
                branches, old_step.id, new_scenario
            )

            # Other branches are potential teleport targets
            other_branches = [b for b in branches if b != branch_to_current]

            if other_branches:
                target_branch = other_branches[0]  # Primary alternate branch

                action.action = "teleport"
                action.teleport_target_id = target_branch.target_step_id
                action.teleport_target_name = target_branch.target_step_name
                action.teleport_condition = target_branch.condition_text
                action.teleport_condition_fields = target_branch.condition_fields
                action.teleport_fallback_action = "continue"
                action.reason = f"New fork at '{fork.name}'. If {target_branch.condition_text}, customer should be at '{target_branch.target_step_name}'."

                # Find checkpoints between alternate branch and current position
                checkpoints = find_checkpoints_between(
                    target_branch.target_step_id,
                    old_step.id,
                    new_scenario
                )
                action.blocked_by_checkpoints = [
                    CheckpointRef(
                        step_id=cp.id,
                        step_name=cp.name,
                        checkpoint_description=cp.checkpoint_description or "Irreversible action"
                    )
                    for cp in checkpoints
                ]

                return action

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 3: Check for data collection requirements
    # ═══════════════════════════════════════════════════════════════════════════

    new_upstream_steps = find_new_upstream_steps(
        old_step.id, old_scenario, new_scenario
    )

    fields_needed = []
    for upstream_step in new_upstream_steps:
        for field_name in upstream_step.collects_profile_fields:
            # Check if any downstream step/fork needs this field
            if is_field_needed_downstream(field_name, old_step.id, new_scenario):
                fields_needed.append(field_name)

    if fields_needed:
        action.action = "collect"
        action.collect_fields = list(set(fields_needed))
        action.collect_reason = f"New upstream step(s) collect data needed downstream."
        action.reason = f"Must collect: {', '.join(fields_needed)}"
        return action

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 4: Check for required actions
    # ═══════════════════════════════════════════════════════════════════════════

    required_actions = []
    for upstream_step in new_upstream_steps:
        if upstream_step.is_required_action:
            required_actions.append(upstream_step.id)

    if required_actions:
        action.action = "execute"
        action.execute_actions = required_actions
        action.reason = f"Must execute {len(required_actions)} required action(s)."
        return action

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 5: No changes affecting this step
    # ═══════════════════════════════════════════════════════════════════════════

    return action
```

### Warning Generation

```python
def generate_warnings(plan: MigrationPlan) -> List[MigrationWarning]:
    """Generate warnings for operator review."""

    warnings = []

    for step_id, action in plan.step_actions.items():
        # Warn about checkpoint-blocked teleports
        if action.action == "teleport" and action.blocked_by_checkpoints:
            for checkpoint in action.blocked_by_checkpoints:
                warnings.append(MigrationWarning(
                    severity="warning",
                    step_name=action.from_step_name,
                    message=f"Customers at '{action.from_step_name}' who match "
                            f"'{action.teleport_condition}' should be at "
                            f"'{action.teleport_target_name}', but checkpoint "
                            f"'{checkpoint.checkpoint_description}' at "
                            f"'{checkpoint.step_name}' may prevent this. "
                            f"Sessions past this checkpoint will continue with a warning."
                ))

        # Warn about deleted steps with no anchor
        if action.action == "relocate" and action.relocate_target_id is None:
            warnings.append(MigrationWarning(
                severity="critical",
                step_name=action.from_step_name,
                message=f"Step '{action.from_step_name}' was deleted and no anchor "
                        f"could be found. Customers will exit the scenario."
            ))

        # Warn about required data collection
        if action.collect_fields:
            for field in action.collect_fields:
                warnings.append(MigrationWarning(
                    severity="info",
                    step_name=action.from_step_name,
                    message=f"Customers at '{action.from_step_name}' may be asked for "
                            f"'{field}' if not already in their profile."
                ))

    return warnings
```

---

## Runtime Application

At runtime, applying migration is a simple lookup and apply. For multi-version gaps, we use **Composite Migration** (see Edge Cases section) to prevent thrashing.

```python
async def pre_turn_reconciliation(session: Session) -> ReconciliationResult:
    """Check for scenario updates before processing turn."""

    if session.active_scenario_id is None:
        return ReconciliationResult(action="continue")

    scenario = await config_store.get_scenario(session.active_scenario_id)

    # No change?
    if scenario.version == session.active_scenario_version:
        return ReconciliationResult(action="continue")

    # Get profile for gap fill
    profile = await profile_store.get(session.customer_profile_id)

    # Check version gap
    version_gap = scenario.version - session.active_scenario_version

    if version_gap > 1:
        # Multi-version gap: use composite migration to prevent thrashing
        # See "Version Chaining: Composite Migration" in Edge Cases section
        result = await execute_composite_migration(
            session=session,
            start_version=session.active_scenario_version,
            end_version=scenario.version,
            profile=profile
        )
    else:
        # Single version jump: simple plan application
        plan = await get_migration_plan(
            scenario_id=session.active_scenario_id,
            from_version=session.active_scenario_version,
            to_version=scenario.version
        )

        if plan is None:
            result = await fallback_reconciliation(session, scenario)
        else:
            result = await apply_migration_plan(session, plan, profile)

    # Update session version (unless collecting data)
    if result.action != "collect":
        session.active_scenario_version = scenario.version
        await session_store.save(session)

    # Log for audit
    await log_migration_applied(session, version_gap, result)

    return result


async def apply_migration_plan(
    session: Session,
    plan: MigrationPlan,
    profile: CustomerProfile,
) -> ReconciliationResult:
    """Apply a pre-computed migration plan to a session."""

    # Lookup action for current step
    action = plan.step_actions.get(session.active_step_id)

    if action is None:
        # Step not in plan (shouldn't happen, but handle gracefully)
        logger.warning("step_not_in_migration_plan",
            session_id=session.id,
            step_id=session.active_step_id
        )
        return ReconciliationResult(action="continue")

    # ═══════════════════════════════════════════════════════════════════════════
    # Action: continue
    # ═══════════════════════════════════════════════════════════════════════════

    if action.action == "continue":
        return ReconciliationResult(action="continue")

    # ═══════════════════════════════════════════════════════════════════════════
    # Action: relocate (step was deleted)
    # ═══════════════════════════════════════════════════════════════════════════

    if action.action == "relocate":
        if action.relocate_target_id is None:
            return ReconciliationResult(
                action="exit_scenario",
                user_message="I need to start fresh. Let me help you from the beginning."
            )

        return ReconciliationResult(
            action="teleport",
            target_step_id=action.relocate_target_id,
            teleport_reason="Step no longer exists",
            user_message=None  # Silent relocation
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Action: collect (gather missing data)
    # ═══════════════════════════════════════════════════════════════════════════

    if action.action == "collect":
        missing_fields = []

        for field_name in action.collect_fields:
            # Try gap fill
            result = await fill_gap(field_name, profile, session)
            if not result.filled:
                missing_fields.append(field_name)

        if missing_fields:
            return ReconciliationResult(
                action="collect",
                collect_fields=missing_fields,
                user_message=build_collection_prompt(missing_fields)
            )

        # All fields filled - continue
        return ReconciliationResult(action="continue")

    # ═══════════════════════════════════════════════════════════════════════════
    # Action: teleport (fork would have routed elsewhere)
    # ═══════════════════════════════════════════════════════════════════════════

    if action.action == "teleport":
        # Check if blocked by checkpoint
        for checkpoint in action.blocked_by_checkpoints:
            if has_passed_checkpoint(session, checkpoint.step_id):
                logger.warning("teleport_blocked_by_checkpoint",
                    session_id=session.id,
                    checkpoint=checkpoint.checkpoint_description,
                    would_teleport_to=action.teleport_target_name
                )
                return ReconciliationResult(
                    action="continue",
                    blocked_by_checkpoint=True,
                    checkpoint_warning=f"Would redirect to '{action.teleport_target_name}' "
                                       f"but '{checkpoint.checkpoint_description}' prevents this."
                )

        # Gather data for condition evaluation
        if action.teleport_condition and action.teleport_condition_fields:
            condition_data = {}
            missing_fields = []

            for field_name in action.teleport_condition_fields:
                result = await fill_gap(field_name, profile, session)
                if result.filled:
                    condition_data[field_name] = result.value
                else:
                    missing_fields.append(field_name)

            # Need to collect data before we can evaluate condition
            if missing_fields:
                return ReconciliationResult(
                    action="collect",
                    collect_fields=missing_fields,
                    user_message=build_collection_prompt(missing_fields)
                )

            # Evaluate condition
            should_teleport = evaluate_condition(action.teleport_condition, condition_data)

            if not should_teleport:
                # Condition not met - use fallback
                if action.teleport_fallback_action == "continue":
                    return ReconciliationResult(action="continue")
                # Could support other fallback actions here

        # Teleport
        return ReconciliationResult(
            action="teleport",
            target_step_id=action.teleport_target_id,
            teleport_reason=action.reason,
            user_message="I have updated instructions. Let me redirect our conversation."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Action: execute (run required actions)
    # ═══════════════════════════════════════════════════════════════════════════

    if action.action == "execute":
        return ReconciliationResult(
            action="execute_action",
            execute_actions=action.execute_actions
        )

    # Unknown action
    logger.error("unknown_migration_action", action=action.action)
    return ReconciliationResult(action="continue")


def has_passed_checkpoint(session: Session, checkpoint_step_id: UUID) -> bool:
    """Check if session has passed through a checkpoint step."""
    return any(
        visit.step_id == checkpoint_step_id
        for visit in session.step_history
    )
```

---

## Gap Fill Implementation

When data collection is required, gap fill attempts to find the value without asking:

```python
async def fill_gap(
    field_name: str,
    profile: CustomerProfile,
    session: Session,
) -> GapFillResult:
    """
    Try to fill a missing field without asking the user.

    Tier 1: Structured data (Profile + Session) - instant, reliable
    Tier 2: Conversation extraction (LLM) - slower, less reliable
    Tier 3: Ask user - caller handles this case
    """

    # ═══════════════════════════════════════════════════════════════════════
    # TIER 1: Structured Data
    # ═══════════════════════════════════════════════════════════════════════

    # Check profile (cross-session, cross-scenario)
    if field_name in profile.fields:
        field = profile.fields[field_name]
        if not field.is_expired():
            return GapFillResult(
                filled=True,
                value=field.value,
                source="profile",
                confidence=field.confidence
            )

    # Check session variables (current conversation)
    if field_name in session.variables:
        return GapFillResult(
            filled=True,
            value=session.variables[field_name],
            source="session",
            confidence=1.0
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TIER 2: Conversation Extraction
    # ═══════════════════════════════════════════════════════════════════════

    field_def = await get_field_definition(field_name)

    extraction = await extract_field_from_conversation(
        field_name=field_name,
        field_type=field_def.value_type,
        extraction_hints=field_def.extraction_prompt_hint,
        examples=field_def.extraction_examples,
        session=session,
        max_turns=20,
    )

    if extraction.found and extraction.confidence >= 0.85:
        # Persist to profile for future use
        await profile.set_field(
            name=field_name,
            value=extraction.value,
            source="conversation_extraction",
            confidence=extraction.confidence,
            needs_confirmation=(extraction.confidence < 0.95)
        )

        return GapFillResult(
            filled=True,
            value=extraction.value,
            source="extraction",
            confidence=extraction.confidence,
            needs_confirmation=(extraction.confidence < 0.95)
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TIER 3: Must ask user (caller handles)
    # ═══════════════════════════════════════════════════════════════════════

    return GapFillResult(filled=False)


@dataclass
class GapFillResult:
    """Result of gap fill attempt."""
    filled: bool
    value: Any = None
    source: str = ""  # "profile" | "session" | "extraction"
    confidence: float = 1.0
    needs_confirmation: bool = False
```

### Extraction Prompt

```python
EXTRACTION_PROMPT = """
You are extracting specific information from a conversation history.

## Field to Extract
Name: {field_name}
Display Name: {field_display_name}
Type: {field_type}

## Extraction Hints
{extraction_hints}

## Examples of Valid Values
{examples}

## Conversation History
{conversation}

## Instructions
Search for any mention of the customer's {field_display_name}.

Look for:
- Direct statements ("My email is...", "I'm 25 years old")
- Indirect mentions ("You can reach me at john@...", "I was born in 1998")
- Information provided in context (signature, casual mention)

If found:
- Extract the exact value
- Quote the source text
- Rate confidence (0.0-1.0) based on clarity

If not found or ambiguous, say so.

Respond in JSON:
{{
  "found": true,
  "value": "john@example.com",
  "confidence": 0.95,
  "source_quote": "You can reach me at john@example.com",
  "reasoning": "Customer explicitly provided email"
}}
"""
```

---

## Reconciliation Result

```python
@dataclass
class ReconciliationResult:
    """Result of applying migration plan to a session."""
    action: str  # "continue" | "teleport" | "collect" | "execute_action" | "exit_scenario"

    # For teleport
    target_step_id: Optional[UUID] = None
    teleport_reason: Optional[str] = None

    # For collect
    collect_fields: List[str] = field(default_factory=list)

    # For execute_action
    execute_actions: List[UUID] = field(default_factory=list)

    # User-facing message (if any)
    user_message: Optional[str] = None

    # Warnings
    blocked_by_checkpoint: bool = False
    checkpoint_warning: Optional[str] = None
```

---

## Storage and Retention

### Migration Plan Storage

```python
# Migration plans are stored per scenario version transition
# Key pattern: migration_plan:{scenario_id}:{from_version}:{to_version}

async def save_migration_plan(plan: MigrationPlan) -> None:
    """Save a migration plan."""
    key = f"migration_plan:{plan.scenario_id}:{plan.from_version}:{plan.to_version}"
    await config_store.save(key, plan, ttl_days=30)


async def get_migration_plan(
    scenario_id: UUID,
    from_version: int,
    to_version: int,
) -> Optional[MigrationPlan]:
    """Get a migration plan for a specific version transition."""

    # Direct transition?
    key = f"migration_plan:{scenario_id}:{from_version}:{to_version}"
    plan = await config_store.get(key)

    if plan:
        return plan

    # Version gap - try to chain plans
    # e.g., from V1 to V3, might need V1→V2 then V2→V3
    # For now, return None and let runtime fall back to anchor-based relocation
    return None
```

### Scenario Version Retention

```python
async def save_scenario(scenario: Scenario, plan: MigrationPlan) -> None:
    """Save scenario with its migration plan."""

    current = await config_store.get_scenario(scenario.id)

    if current:
        # Archive current version
        await config_store.archive_scenario_version(current)

    # Increment version and save
    scenario.version += 1
    await config_store.save_scenario(scenario)

    # Save migration plan
    await save_migration_plan(plan)

    # Mark previous plan as superseded
    if current:
        old_plan = await get_migration_plan(
            scenario.id,
            current.version - 1,
            current.version
        )
        if old_plan:
            old_plan.status = "superseded"
            await save_migration_plan(old_plan)
```

**Retention policy:**
- Scenario versions: Previous version only, 7 days
- Migration plans: 30 days (longer than versions to support late migrations)
- If version or plan not found: Fall back to anchor-based relocation

---

## User Experience

### Silent Operations

These happen without user notification:
- Downstream steps added (encountered naturally)
- Gap fill from CustomerProfile (instant)
- Gap fill from session variables (instant)
- Relocation to anchor when step deleted (silent teleport)

### User-Facing Prompts

**Data collection** (when gap fill fails):
```
"Before we continue, I need to confirm a few things. What is your email address?"
```

**Teleportation** (when fork redirects):
```
"I have updated instructions I need to follow. Let me redirect our conversation."
```

**Confirmation** (when extraction confidence is medium):
```
"Just to confirm - your email is john@example.com, correct?"
```

---

## Configuration

```toml
[scenario_reconciliation]
enabled = true

# Migration plan generation
[scenario_reconciliation.plan_generation]
auto_generate = true  # Generate plan on scenario save
require_approval = true  # Operator must approve before deployment

# Gap fill settings
[scenario_reconciliation.gap_fill]
extraction_enabled = true
extraction_confidence_threshold = 0.85
confirmation_threshold = 0.95
max_conversation_turns = 20

# Teleportation settings
[scenario_reconciliation.teleportation]
enabled = true
notify_user = true
notification_template = "I have updated instructions. Let me redirect our conversation."

# Retention
[scenario_reconciliation.retention]
version_retention_days = 7
plan_retention_days = 30

# Logging
[scenario_reconciliation.logging]
log_checkpoint_blocks = true
log_teleportations = true
log_gap_fills = true
```

---

## Observability

See [observability.md](../architecture/observability.md) for the overall logging, tracing, and metrics architecture. This section covers scenario reconciliation-specific observability.

### Events

```python
class MigrationAppliedEvent(BaseModel):
    """Logged when a migration plan is applied to a session."""
    session_id: UUID
    scenario_id: UUID
    plan_id: UUID
    from_version: int
    to_version: int

    # What happened
    step_before: UUID
    action_taken: str
    step_after: Optional[UUID] = None

    # Details
    fields_collected: List[str] = []
    fields_gap_filled: Dict[str, str] = {}  # field_name -> source
    actions_executed: List[UUID] = []

    # Warnings
    blocked_by_checkpoint: bool = False
    checkpoint_id: Optional[UUID] = None

    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Metrics

- `migration_plans_generated_total` (counter)
- `migration_plans_approved_total` (counter)
- `migration_applied_total` (counter) - by action type
- `migration_teleportations_total` (counter) - by reason
- `migration_gap_fills_total` (counter) - by source (profile/session/extraction/ask)
- `migration_checkpoint_blocks_total` (counter)
- `migration_plan_generation_duration_ms` (histogram)
- `migration_application_duration_ms` (histogram)

---

## Edge Cases

### Version Gap (Session Very Old)

If a session is on V1 and current is V5, we might not have a direct V1→V5 plan:

```python
async def fallback_reconciliation(
    session: Session,
    scenario: Scenario
) -> ReconciliationResult:
    """Fallback when no migration plan is available."""

    # Try to find current step in new scenario
    if scenario.has_step(session.active_step_id):
        # Step still exists - just update version
        return ReconciliationResult(action="continue")

    # Step deleted - find anchor
    anchor = find_nearest_anchor(session.step_history, scenario)

    if anchor:
        return ReconciliationResult(
            action="teleport",
            target_step_id=anchor.id,
            teleport_reason="Fallback relocation (migration plan unavailable)"
        )

    return ReconciliationResult(
        action="exit_scenario",
        user_message="I need to start fresh. Let me help you from the beginning."
    )
```

### Version Chaining: Composite Migration (Plan Squashing)

When a user is dormant while the scenario is updated multiple times (e.g., V1 → V2 → V3), naive sequential execution of migration plans leads to **thrashing** - executing useless intermediate actions that erode user trust.

#### The Thrashing Problem

```
User is dormant at Step A (V1)

Update 1 (V2): Add Step B between A and C
               Step B requires "email"

Update 2 (V3): Delete Step B, replace with Step D
               Step D requires "phone"

User returns...
```

**Bad (Sequential Execution):**
1. V1→V2: Move to Step B, ask for email
2. User provides email
3. V2→V3: Move to Step D, discard email, ask for phone
4. **Result**: User was forced to provide data that was immediately obsolete

**Good (Composite Migration):**
1. Squash V1→V2→V3 into single net effect
2. Calculate: Step A → Step D (skip B entirely)
3. Prune requirements: email is not needed in V3, only phone
4. **Result**: User is asked only for phone

#### Solution: Treat Intermediate Versions as Transient Calculations

We "squash" the chain of migration plans into a single **Net Result** before touching the session. This relies on two phases:

1. **Transitive Resolution**: Calculate the net movement across all plans
2. **Requirement Pruning**: Keep only data requirements that matter in the final version

```python
async def execute_composite_migration(
    session: Session,
    start_version: int,
    end_version: int,
    profile: CustomerProfile,
) -> ReconciliationResult:
    """
    Calculate the net effect of multiple version updates and apply
    them atomically to the session.

    This prevents "thrashing" - asking users for data that intermediate
    versions needed but the final version doesn't.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 1: Fetch the Plan Chain
    # ═══════════════════════════════════════════════════════════════════════════

    plans = await config_store.get_plan_chain(
        scenario_id=session.active_scenario_id,
        start_version=start_version,
        end_version=end_version
    )

    if not plans:
        # No plans available - fall back to anchor-based relocation
        return await fallback_reconciliation(session, end_version)

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 2: In-Memory Simulation (Transitive Resolution)
    # ═══════════════════════════════════════════════════════════════════════════

    virtual_step_id = session.active_step_id
    accumulated_requirements = set()
    accumulated_condition_fields = set()
    checkpoints_encountered = []

    for plan in plans:
        action = plan.step_actions.get(virtual_step_id)

        if action is None:
            # Step exists unchanged in this version transition
            continue

        # Track movement (but don't persist yet)
        if action.action in ("teleport", "relocate"):
            virtual_step_id = action.teleport_target_id or action.relocate_target_id

        # Accumulate potential data requirements (dirty list)
        if action.collect_fields:
            accumulated_requirements.update(action.collect_fields)

        if action.teleport_condition_fields:
            accumulated_condition_fields.update(action.teleport_condition_fields)

        # Track checkpoints for blocking logic
        if action.blocked_by_checkpoints:
            checkpoints_encountered.extend(action.blocked_by_checkpoints)

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 3: Requirement Pruning (The "Anti-Thrash" Logic)
    # ═══════════════════════════════════════════════════════════════════════════

    # Load the FINAL scenario version
    final_scenario = await config_store.get_scenario(
        session.active_scenario_id,
        version=end_version
    )
    final_step = final_scenario.get_step(virtual_step_id)

    if final_step is None:
        # Virtual step doesn't exist in final version - find anchor
        anchor = find_nearest_anchor_in_scenario(
            virtual_step_id, final_scenario
        )
        if anchor:
            virtual_step_id = anchor.id
            final_step = anchor
        else:
            return ReconciliationResult(
                action="exit_scenario",
                user_message="I need to start fresh. Let me help you from the beginning."
            )

    # Prune requirements: only keep fields needed in final version
    final_requirements = set()

    for field_name in accumulated_requirements | accumulated_condition_fields:
        if is_field_needed_in_future(field_name, final_step, final_scenario):
            final_requirements.add(field_name)
        # else: field was needed by intermediate version but not final - prune it

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 4: Gap Fill (Only for Pruned Requirements)
    # ═══════════════════════════════════════════════════════════════════════════

    missing_fields = []

    for field_name in final_requirements:
        result = await fill_gap(field_name, profile, session)
        if not result.filled:
            missing_fields.append(field_name)

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 5: Atomic Application
    # ═══════════════════════════════════════════════════════════════════════════

    # Check checkpoint blocking (using accumulated checkpoints)
    for checkpoint in checkpoints_encountered:
        if has_passed_checkpoint(session, checkpoint.step_id):
            # Can't complete migration - blocked by irreversible action
            logger.warning("composite_migration_blocked",
                session_id=session.id,
                checkpoint=checkpoint.checkpoint_description
            )
            # Continue at current position in final version
            return ReconciliationResult(
                action="continue",
                blocked_by_checkpoint=True,
                checkpoint_warning=f"Migration blocked by '{checkpoint.checkpoint_description}'"
            )

    # Build result
    if missing_fields:
        return ReconciliationResult(
            action="collect",
            collect_fields=missing_fields,
            user_message=build_collection_prompt(missing_fields)
        )

    # Determine if we need to teleport
    if virtual_step_id != session.active_step_id:
        return ReconciliationResult(
            action="teleport",
            target_step_id=virtual_step_id,
            teleport_reason=f"Composite migration V{start_version}→V{end_version}",
            user_message=None  # Silent unless significant change
        )

    return ReconciliationResult(action="continue")


def is_field_needed_in_future(
    field_name: str,
    step: ScenarioStep,
    scenario: Scenario,
) -> bool:
    """
    Determine if a field is actually needed in the final scenario graph.

    A field is needed if:
    1. The current step requires it
    2. An outgoing transition condition uses it
    3. An immediate downstream step requires it
    """

    # Check current step requirements
    if field_name in step.collects_profile_fields:
        return True

    # Check outgoing transition conditions
    for transition in step.transitions:
        if field_name in transition.condition_fields:
            return True

    # Check immediate downstream steps
    for transition in step.transitions:
        downstream_step = scenario.get_step(transition.to_step_id)
        if downstream_step and field_name in downstream_step.collects_profile_fields:
            return True

    return False


async def get_plan_chain(
    scenario_id: UUID,
    start_version: int,
    end_version: int,
) -> List[MigrationPlan]:
    """
    Retrieve all migration plans needed to go from start_version to end_version.

    Returns plans in order: [V1→V2, V2→V3, V3→V4, ...]
    Returns empty list if any plan in the chain is missing.
    """

    plans = []

    current_version = start_version
    while current_version < end_version:
        next_version = current_version + 1

        plan = await config_store.get_migration_plan(
            scenario_id=scenario_id,
            from_version=current_version,
            to_version=next_version
        )

        if plan is None:
            # Gap in chain - can't composite
            logger.warning("migration_plan_chain_broken",
                scenario_id=scenario_id,
                missing_from=current_version,
                missing_to=next_version
            )
            return []

        plans.append(plan)
        current_version = next_version

    return plans
```

#### Updated Runtime Entry Point

The `pre_turn_reconciliation` function now uses composite migration:

```python
async def pre_turn_reconciliation(session: Session) -> ReconciliationResult:
    """Check for scenario updates before processing turn."""

    if session.active_scenario_id is None:
        return ReconciliationResult(action="continue")

    scenario = await config_store.get_scenario(session.active_scenario_id)

    # No change?
    if scenario.version == session.active_scenario_version:
        return ReconciliationResult(action="continue")

    # Get profile for gap fill
    profile = await profile_store.get(session.customer_profile_id)

    # Version gap > 1? Use composite migration to prevent thrashing
    version_gap = scenario.version - session.active_scenario_version

    if version_gap > 1:
        result = await execute_composite_migration(
            session=session,
            start_version=session.active_scenario_version,
            end_version=scenario.version,
            profile=profile
        )
    else:
        # Single version jump - use simple plan application
        plan = await get_migration_plan(
            scenario_id=session.active_scenario_id,
            from_version=session.active_scenario_version,
            to_version=scenario.version
        )

        if plan is None:
            result = await fallback_reconciliation(session, scenario)
        else:
            result = await apply_migration_plan(session, plan, profile)

    # Update session version (unless collecting data)
    if result.action != "collect":
        session.active_scenario_version = scenario.version
        await session_store.save(session)

    # Log for audit
    await log_migration_applied(session, version_gap, result)

    return result
```

#### Benefits of Composite Migration

| Aspect | Without Composite | With Composite |
|--------|-------------------|----------------|
| **User Experience** | Confusing - asked for data that's immediately obsolete | Clean - only relevant questions for final state |
| **Data Integrity** | Polluted - session contains fragments from deleted flows | Pure - reflects only active scenario version |
| **Performance** | Slow - multiple DB writes per intermediate version | Fast - single atomic update V1→V3 |
| **Auditability** | Noisy - many migration events | Clean - one composite migration event |

### Circular References in Scenario

Graph traversal uses visited set to prevent infinite loops:

```python
def find_new_upstream_forks(
    target_step_id: UUID,
    old_scenario: Scenario,
    new_scenario: Scenario,
) -> List[ScenarioStep]:
    """Find forks in new scenario that are upstream of target step."""

    visited = set()
    forks = []

    def walk(step_id: UUID):
        if step_id in visited:
            return
        visited.add(step_id)

        step = new_scenario.get_step(step_id)
        if step is None:
            return

        # Check if this is a fork (multiple transitions)
        if len(step.transitions) > 1:
            # Is this fork new or modified?
            old_step = old_scenario.get_step(step_id)
            if old_step is None or transitions_changed(old_step, step):
                forks.append(step)

        # Walk predecessors
        for pred_id in get_predecessors(step_id, new_scenario):
            walk(pred_id)

    walk(target_step_id)
    return forks
```

---

## Operator Review UI

The Control Plane should display migration plans for review:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MIGRATION PLAN: Support Flow v3 → v4                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Summary                                                                     │
│  ────────────────────────────────────────────────────────────────────────── │
│  Total steps in v3:       8                                                 │
│  Unchanged:               5                                                 │
│  Need data collection:    2                                                 │
│  Will teleport:           1                                                 │
│  Deleted (relocate):      0                                                 │
│                                                                              │
│  Estimated sessions affected: 142                                           │
│                                                                              │
│  Warnings                                                                   │
│  ────────────────────────────────────────────────────────────────────────── │
│  ⚠️  Customers at 'Order Confirmation' who are under 18 should be          │
│      rejected, but checkpoint 'Payment Processed' prevents this.            │
│      These sessions will continue with a logged warning.                    │
│                                                                              │
│  ℹ️  Customers at 'Welcome' may be asked for 'email' if not in profile.    │
│                                                                              │
│  Step Details                                                               │
│  ────────────────────────────────────────────────────────────────────────── │
│  Welcome           → collect ['email']     (12 sessions)                   │
│  Product Selection → continue              (45 sessions)                   │
│  Cart Review       → continue              (28 sessions)                   │
│  Checkout          → teleport to Rejected  (3 sessions)                    │
│                      if age < 18                                            │
│                      blocked by: Payment Processed                          │
│  Order Confirmation→ continue              (54 sessions)                   │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                                  │
│  │    Approve      │  │     Cancel      │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## See Also

- [Customer Profile](./customer-profile.md) - Persistent customer data enabling gap fill
- [Alignment Engine](../architecture/alignment-engine.md) - Scenario navigation and step transitions
- [Domain Model](./domain-model.md) - Core entity definitions
- [Turn Pipeline](./turn-pipeline.md) - Where reconciliation fits in request processing
