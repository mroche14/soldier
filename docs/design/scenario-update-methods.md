# Scenario Update Methods

This document describes how Focal handles scenario updates while customers have active sessions. The core challenge: **WhatsApp and other long-lived sessions can span days or weeks, and scenario changes may be urgent.**

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

Naively changing the Scenario structure under active sessions can:
- **Corrupt session state** (internal "path" no longer matches graph)
- **Confuse the agent** (graph now says "you shouldn't be here")
- Break critical business logic (e.g., new age rule not enforced)

**Goal**: Update the Scenario **without losing context** (collected info, previous actions) and while **avoiding session corruption**.

---

## Solution: Anchor-Based Migration

Rather than tracking by step IDs (which may change), we use **content-based anchor identification** and **two-phase deployment** with **per-anchor policies**.

### Core Pillars

1. **Global Topology Mapping ("Graph Diff")** - Compare V1 and V2 structurally using content hashes
2. **Anchor Nodes & Policies** - Define what to do for sessions at each anchor
3. **Two-Phase Migration** - Mark at deployment, apply at JIT (next user message)
4. **Migration Scenarios** - Clean Graft, Gap Fill, Re-Routing strategies

All of this is defined at the **Scenario graph level**, not per-session ad-hoc.

---

## Vocabulary

| Term | Definition |
|------|------------|
| **Scenario** | The graph of a conversation workflow (nodes + transitions) |
| **Node** | A state in the Scenario (chat_state, tool_state, etc.) |
| **Rule** | Conditional behavior or branching logic at a node |
| **Anchor Node** | A node that exists in both V1 and V2 with same semantics (identified via content hash) |
| **Checkpoint** | Special node representing an irreversible or "committed" business action (e.g., "order dispatched", "payment processed") |
| **Content Hash** | Hash of stable node attributes (intent, rules, key parameters) for semantic matching |
| **Scenario Checksum** | Hash of entire graph structure, stored with session to validate path consistency |
| **Pending Migration Flag** | Marker on session saying "needs migration logic at next user message" |

---

## Step 1: Global Topology Mapping ("Graph Diff")

When we define Scenario V2, we **compare Scenario V1 and V2** structurally.

### 1.1 Compute Content Hashes

For each node in V1 and V2, build a **content hash** from stable attributes:

```python
def compute_node_content_hash(node: ScenarioStep) -> str:
    """
    Build content hash from stable semantic attributes.
    Nodes with same hash are treated as Anchors.
    """
    hash_input = {
        "intent": node.intent or node.name,
        "description": node.description,
        "rules": sorted([r.id for r in node.rules]),
        "collects_fields": sorted(node.collects_profile_fields),
        "is_checkpoint": node.is_checkpoint,
        "checkpoint_type": node.checkpoint_type,
    }
    return hashlib.sha256(json.dumps(hash_input, sort_keys=True).encode()).hexdigest()[:16]
```

Nodes with the **same content hash** across V1 and V2 are treated as **Anchor Nodes**.

### 1.2 Build Transformation Map

For each Anchor Node, classify changes between V1 and V2:

```python
@dataclass
class AnchorTransformation:
    """What changed around an anchor node between V1 and V2."""
    anchor_node_id_v1: UUID
    anchor_node_id_v2: UUID
    anchor_content_hash: str
    anchor_name: str

    # What changed BEFORE the anchor (user has passed through this)
    upstream_changes: UpstreamChanges

    # What changed AFTER the anchor (user will encounter this)
    downstream_changes: DownstreamChanges


@dataclass
class UpstreamChanges:
    """Changes upstream of an anchor."""
    inserted_nodes: List[InsertedNode]  # New nodes added before anchor
    removed_nodes: List[UUID]  # Old nodes deleted before anchor
    new_forks: List[NewFork]  # New branching logic before anchor
    modified_transitions: List[TransitionChange]


@dataclass
class DownstreamChanges:
    """Changes downstream of an anchor."""
    inserted_nodes: List[InsertedNode]  # New nodes added after anchor
    removed_nodes: List[UUID]  # Old nodes deleted after anchor
    new_forks: List[NewFork]  # New branching logic after anchor
    modified_transitions: List[TransitionChange]


@dataclass
class InsertedNode:
    """A node inserted between V1 and V2."""
    node_id: UUID
    node_name: str
    collects_fields: List[str]  # Profile fields this node collects
    has_rules: bool  # Does this node have conditional rules?
    is_required_action: bool  # Must this action be executed?


@dataclass
class NewFork:
    """A new fork (branching point) in V2."""
    fork_node_id: UUID
    fork_node_name: str
    branches: List[ForkBranch]


@dataclass
class ForkBranch:
    """One branch of a fork."""
    target_step_id: UUID
    target_step_name: str
    condition_text: str  # e.g., "age < 18"
    condition_fields: List[str]  # Fields needed to evaluate condition
```

**Example:**

```
V1: A → B → C
V2: A → N1 → B → N2 → C

For Anchor B:
  upstream_changes:
    inserted_nodes: [N1]
  downstream_changes:
    inserted_nodes: [N2]
```

### 1.3 Scenario Checksum

Store a **checksum** of the entire scenario graph with session tracking data:

```python
def compute_scenario_checksum(scenario: Scenario) -> str:
    """Hash of entire graph structure for version validation."""
    structure = {
        "version": scenario.version,
        "steps": sorted([
            {
                "id": str(s.id),
                "hash": compute_node_content_hash(s),
                "transitions": sorted([str(t.to_step_id) for t in s.transitions])
            }
            for s in scenario.steps
        ], key=lambda x: x["id"])
    }
    return hashlib.sha256(json.dumps(structure, sort_keys=True).encode()).hexdigest()[:16]
```

A session's stored "path" is only trusted if the checksum matches the Scenario version it was built from.

---

## Step 2: Per-Anchor Policies

For each Anchor Node, operators can define a **migration policy**:

```python
@dataclass
class AnchorMigrationPolicy:
    """Migration policy for a specific anchor node."""
    anchor_content_hash: str
    anchor_name: str  # For display

    # ─────────────────────────────────────────────────────────────────────────
    # Scope Filter: Which sessions are eligible for migration at this anchor?
    # ─────────────────────────────────────────────────────────────────────────
    scope_filter: ScopeFilter

    # ─────────────────────────────────────────────────────────────────────────
    # Update Policy: What to do with downstream changes
    # ─────────────────────────────────────────────────────────────────────────
    update_downstream: bool = True  # If True, graft new downstream from V2

    # ─────────────────────────────────────────────────────────────────────────
    # Override: Force a specific migration scenario
    # ─────────────────────────────────────────────────────────────────────────
    force_scenario: Optional[str] = None  # "clean_graft" | "gap_fill" | "re_route"


@dataclass
class ScopeFilter:
    """Filter for which sessions are eligible for migration."""
    include_current_nodes: List[str] = field(default_factory=list)  # Node names
    exclude_current_nodes: List[str] = field(default_factory=list)
    include_channels: List[str] = field(default_factory=list)  # "whatsapp", "web"
    exclude_channels: List[str] = field(default_factory=list)
    max_session_age_days: Optional[int] = None
    min_session_age_days: Optional[int] = None
    custom_conditions: List[str] = field(default_factory=list)  # Custom filter expressions
```

**Example Policy:**

```python
AnchorMigrationPolicy(
    anchor_content_hash="abc123",
    anchor_name="Order Confirmation",
    scope_filter=ScopeFilter(
        include_channels=["whatsapp", "sms"],  # Only long-lived channels
        max_session_age_days=30,  # Skip very old sessions
    ),
    update_downstream=True,  # Apply new downstream flow
)
```

This makes migration **configurable per anchor**, not all-or-nothing.

---

## Step 3: Two-Phase Deployment

### Phase 1: Deployment (Mark Sessions)

When Scenario V2 is deployed:

```python
async def deploy_scenario_v2(
    scenario_id: UUID,
    new_scenario: Scenario,
    anchor_policies: List[AnchorMigrationPolicy],
    operator_id: str,
) -> DeploymentResult:
    """
    Deploy new scenario version.
    Phase 1: Mark sessions for migration, don't apply yet.
    """

    old_scenario = await config_store.get_scenario(scenario_id)

    # ═══════════════════════════════════════════════════════════════════════════
    # Step 1: Compute Graph Diff
    # ═══════════════════════════════════════════════════════════════════════════

    transformation_map = compute_transformation_map(old_scenario, new_scenario)

    # ═══════════════════════════════════════════════════════════════════════════
    # Step 2: Build Migration Plan
    # ═══════════════════════════════════════════════════════════════════════════

    migration_plan = build_migration_plan(
        transformation_map=transformation_map,
        anchor_policies=anchor_policies,
        old_scenario=old_scenario,
        new_scenario=new_scenario,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Step 3: Scan and Mark Sessions (DO NOT migrate yet)
    # ═══════════════════════════════════════════════════════════════════════════

    marked_sessions = []

    for anchor in transformation_map.anchors:
        policy = get_policy_for_anchor(anchor, anchor_policies)

        # Find sessions at or near this anchor that match scope filter
        eligible_sessions = await session_store.find_sessions(
            scenario_id=scenario_id,
            scenario_version=old_scenario.version,
            scope_filter=policy.scope_filter,
            current_anchor_hash=anchor.anchor_content_hash,
        )

        for session in eligible_sessions:
            # Mark session for migration - DO NOT change scenario yet
            session.pending_migration = PendingMigration(
                target_version=new_scenario.version,
                anchor_content_hash=anchor.anchor_content_hash,
                migration_plan_id=migration_plan.id,
                marked_at=datetime.utcnow(),
            )
            await session_store.save(session)
            marked_sessions.append(session.id)

    # ═══════════════════════════════════════════════════════════════════════════
    # Step 4: Save New Scenario Version + Plan
    # ═══════════════════════════════════════════════════════════════════════════

    await config_store.archive_scenario_version(old_scenario)
    await config_store.save_scenario(new_scenario)
    await config_store.save_migration_plan(migration_plan)

    return DeploymentResult(
        migration_plan_id=migration_plan.id,
        sessions_marked=len(marked_sessions),
        from_version=old_scenario.version,
        to_version=new_scenario.version,
    )


@dataclass
class PendingMigration:
    """Marker on session indicating migration is needed."""
    target_version: int
    anchor_content_hash: str
    migration_plan_id: UUID
    marked_at: datetime
```

**Key Point:** No live migration during deployment. Sessions are only **marked**. Actual migration is deferred to **runtime**.

### Phase 2: JIT Remediation (At Next User Message)

When a user with `pending_migration` sends a new message:

```python
async def pre_turn_reconciliation(session: Session) -> ReconciliationResult:
    """
    Check for pending migration before processing turn.
    This is the JIT remediation phase.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # Check for pending migration flag
    # ═══════════════════════════════════════════════════════════════════════════

    if session.pending_migration is None:
        # No migration pending - check for version mismatch anyway
        current_scenario = await config_store.get_scenario(session.active_scenario_id)

        if current_scenario.version == session.active_scenario_version:
            return ReconciliationResult(action="continue")

        # Version mismatch but no flag - this is a late arrival
        # Fall back to anchor-based relocation
        return await fallback_reconciliation(session, current_scenario)

    # ═══════════════════════════════════════════════════════════════════════════
    # Load migration context
    # ═══════════════════════════════════════════════════════════════════════════

    migration_plan = await config_store.get_migration_plan(
        session.pending_migration.migration_plan_id
    )

    if migration_plan is None:
        # Plan expired - fall back
        return await fallback_reconciliation(session, None)

    transformation = migration_plan.get_transformation_for_anchor(
        session.pending_migration.anchor_content_hash
    )

    profile = await profile_store.get(session.customer_profile_id)

    # ═══════════════════════════════════════════════════════════════════════════
    # Determine and execute migration scenario
    # ═══════════════════════════════════════════════════════════════════════════

    scenario_type = determine_migration_scenario(transformation, session)

    if scenario_type == "clean_graft":
        result = await execute_clean_graft(session, transformation, migration_plan)
    elif scenario_type == "gap_fill":
        result = await execute_gap_fill(session, transformation, migration_plan, profile)
    elif scenario_type == "re_route":
        result = await execute_re_route(session, transformation, migration_plan, profile)
    else:
        result = ReconciliationResult(action="continue")

    # ═══════════════════════════════════════════════════════════════════════════
    # Clear pending flag and update version (unless collecting data)
    # ═══════════════════════════════════════════════════════════════════════════

    if result.action != "collect":
        session.pending_migration = None
        session.active_scenario_version = migration_plan.to_version
        session.scenario_checksum = compute_scenario_checksum(
            await config_store.get_scenario(session.active_scenario_id)
        )
        await session_store.save(session)

    # Log for audit
    await log_migration_applied(session, migration_plan, result)

    return result
```

---

## Step 4: Migration Scenarios

Based on the transformation analysis, choose one of three migration scenarios:

```python
def determine_migration_scenario(
    transformation: AnchorTransformation,
    session: Session,
) -> str:
    """
    Determine which migration scenario applies.

    Returns: "clean_graft" | "gap_fill" | "re_route"
    """

    upstream = transformation.upstream_changes

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 1: Clean Graft - Upstream is unchanged
    # ═══════════════════════════════════════════════════════════════════════════

    if (not upstream.inserted_nodes and
        not upstream.new_forks and
        not upstream.modified_transitions):
        return "clean_graft"

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 2: Re-Route - New fork upstream that could redirect user
    # ═══════════════════════════════════════════════════════════════════════════

    if upstream.new_forks:
        # Check if any fork has rules that could redirect this user
        for fork in upstream.new_forks:
            if len(fork.branches) > 1:
                return "re_route"

    # ═══════════════════════════════════════════════════════════════════════════
    # Case 3: Gap Fill - Inserted upstream nodes (data collection or messages)
    # ═══════════════════════════════════════════════════════════════════════════

    if upstream.inserted_nodes:
        return "gap_fill"

    # Default to clean graft
    return "clean_graft"
```

### Scenario 1: Clean Graft (Happy Path)

**When:** Upstream from V1 to V2 is identical. User's path to current position is valid.

**Action:** Teleport session to same anchor in V2, attach new downstream.

```
Graph:
  V1: A → B → C
  V2: A → B → N2 → C

User at B in V1:
  → Teleport to B in V2
  → Future flow: B → N2 → C
```

```python
async def execute_clean_graft(
    session: Session,
    transformation: AnchorTransformation,
    plan: MigrationPlan,
) -> ReconciliationResult:
    """
    Clean Graft: Upstream unchanged, just attach new downstream.
    This is the safest and simplest migration.
    """

    # Map session to the anchor node in V2
    new_step_id = transformation.anchor_node_id_v2

    # Check if policy allows downstream update
    policy = plan.get_policy_for_anchor(transformation.anchor_content_hash)

    if not policy.update_downstream:
        # Stay on V1 behavior - just update version tracking
        return ReconciliationResult(
            action="continue",
            reason="Policy: update_downstream=False"
        )

    return ReconciliationResult(
        action="teleport",
        target_step_id=new_step_id,
        teleport_reason="Clean graft: upstream unchanged",
        user_message=None,  # Silent - user doesn't notice
    )
```

### Scenario 2: Gap Fill (Inserted Upstream Nodes)

**When:** New nodes were inserted upstream. User "skipped" them.

**Key Question:** Can we pretend the new node(s) already happened, or must we run them now?

```
Graph:
  V1: A → B
  V2: A → N1 → B

User at B in V1:
  → N1 was inserted upstream
  → Check what N1 requires
```

```python
async def execute_gap_fill(
    session: Session,
    transformation: AnchorTransformation,
    plan: MigrationPlan,
    profile: CustomerProfile,
) -> ReconciliationResult:
    """
    Gap Fill: Handle inserted upstream nodes.

    For each inserted node:
    - If only a text message: ignore (user doesn't need to see it)
    - If requires data: try to backfill from profile/session/conversation
    - If data not found: pause and ask user
    """

    missing_fields = []

    for inserted_node in transformation.upstream_changes.inserted_nodes:
        # ═══════════════════════════════════════════════════════════════════════
        # Check if this node is just a message (can be ignored)
        # ═══════════════════════════════════════════════════════════════════════

        if not inserted_node.collects_fields and not inserted_node.has_rules:
            # Just a text message - user doesn't need to see it retroactively
            continue

        # ═══════════════════════════════════════════════════════════════════════
        # Check if required action must be executed
        # ═══════════════════════════════════════════════════════════════════════

        if inserted_node.is_required_action:
            # Cannot skip - must execute
            return ReconciliationResult(
                action="execute_action",
                execute_actions=[inserted_node.node_id],
                user_message=None,
            )

        # ═══════════════════════════════════════════════════════════════════════
        # Node collects data - try gap fill
        # ═══════════════════════════════════════════════════════════════════════

        for field_name in inserted_node.collects_fields:
            # Check if field is actually needed downstream
            if not is_field_needed_downstream(
                field_name,
                transformation.anchor_node_id_v2,
                plan.new_scenario
            ):
                continue  # Can skip - field not used

            # Try to fill from profile/session/conversation
            result = await fill_gap(field_name, profile, session)

            if not result.filled:
                missing_fields.append(field_name)

    # ═══════════════════════════════════════════════════════════════════════════
    # Result
    # ═══════════════════════════════════════════════════════════════════════════

    if missing_fields:
        return ReconciliationResult(
            action="collect",
            collect_fields=missing_fields,
            user_message=build_collection_prompt(missing_fields),
        )

    # All gaps filled - proceed with clean graft
    return ReconciliationResult(
        action="teleport",
        target_step_id=transformation.anchor_node_id_v2,
        teleport_reason="Gap fill complete",
        user_message=None,
    )
```

### Scenario 3: Re-Routing (New Fork)

**When:** New fork upstream with rules that could redirect user.

**This is the most complex and risky scenario.**

```
Graph:
  V1: A → B → C
  V2: A → N1 → B → N2 → C
            │
       [age < 18]
            │
            └──► D → N2 → C

User at B in V1:
  → New fork at N1 with age rule
  → Evaluate: should user be on B path or D path?
```

```python
async def execute_re_route(
    session: Session,
    transformation: AnchorTransformation,
    plan: MigrationPlan,
    profile: CustomerProfile,
) -> ReconciliationResult:
    """
    Re-Route: Handle new forks that could redirect user.

    1. Evaluate fork conditions using user's current data
    2. Determine correct path in V2
    3. Check checkpoint blocking
    4. Teleport to correct position (or stay if blocked)
    """

    for fork in transformation.upstream_changes.new_forks:
        if len(fork.branches) <= 1:
            continue  # Not really a fork

        # ═══════════════════════════════════════════════════════════════════════
        # Step 1: Find which branch leads to current anchor
        # ═══════════════════════════════════════════════════════════════════════

        branch_to_current = find_branch_leading_to(
            fork.branches,
            transformation.anchor_node_id_v2,
            plan.new_scenario,
        )

        other_branches = [b for b in fork.branches if b != branch_to_current]

        if not other_branches:
            continue  # All branches lead to same place

        # ═══════════════════════════════════════════════════════════════════════
        # Step 2: Gather data needed for fork condition
        # ═══════════════════════════════════════════════════════════════════════

        condition_data = {}
        missing_fields = []

        for branch in other_branches:
            for field_name in branch.condition_fields:
                if field_name in condition_data:
                    continue

                result = await fill_gap(field_name, profile, session)
                if result.filled:
                    condition_data[field_name] = result.value
                else:
                    missing_fields.append(field_name)

        if missing_fields:
            return ReconciliationResult(
                action="collect",
                collect_fields=missing_fields,
                user_message=build_collection_prompt(missing_fields),
            )

        # ═══════════════════════════════════════════════════════════════════════
        # Step 3: Evaluate fork conditions
        # ═══════════════════════════════════════════════════════════════════════

        for branch in other_branches:
            should_take_branch = evaluate_condition(
                branch.condition_text,
                condition_data,
            )

            if should_take_branch:
                # User should be on a different path!

                # ═══════════════════════════════════════════════════════════════
                # Step 4: Check checkpoint blocking
                # ═══════════════════════════════════════════════════════════════

                last_checkpoint = find_last_checkpoint_in_path(session)

                if last_checkpoint:
                    # Check if teleporting would cross (go before) the checkpoint
                    if is_step_before_checkpoint(
                        branch.target_step_id,
                        last_checkpoint.step_id,
                        plan.new_scenario,
                    ):
                        # BLOCKED - cannot undo irreversible action
                        logger.warning(
                            "re_route_blocked_by_checkpoint",
                            session_id=session.id,
                            checkpoint=last_checkpoint.checkpoint_description,
                            would_teleport_to=branch.target_step_name,
                        )

                        return ReconciliationResult(
                            action="continue",
                            blocked_by_checkpoint=True,
                            checkpoint_warning=f"Would redirect to '{branch.target_step_name}' "
                                             f"but checkpoint '{last_checkpoint.checkpoint_description}' "
                                             f"prevents this.",
                        )

                # ═══════════════════════════════════════════════════════════════
                # Step 5: Execute teleportation
                # ═══════════════════════════════════════════════════════════════

                return ReconciliationResult(
                    action="teleport",
                    target_step_id=branch.target_step_id,
                    teleport_reason=f"Re-route: {branch.condition_text} evaluated true",
                    user_message="I have new instructions regarding your request. "
                                "Let me redirect our conversation.",
                )

    # No re-routing needed - fall through to gap fill or clean graft
    if transformation.upstream_changes.inserted_nodes:
        return await execute_gap_fill(session, transformation, plan, profile)

    return await execute_clean_graft(session, transformation, plan)
```

---

## Checkpoint Handling

Checkpoints represent **irreversible actions** that cannot be undone. When migrating, we must respect these.

### Finding Last Checkpoint

Walk **backwards** through the session's path to find the most recent checkpoint:

```python
def find_last_checkpoint_in_path(session: Session) -> Optional[CheckpointInfo]:
    """
    Walk backwards through session history to find last checkpoint.

    Checkpoints are irreversible actions like:
    - "Order placed"
    - "Payment processed"
    - "Contract signed"
    """

    # Session stores visited steps in order
    for visit in reversed(session.step_history):
        if visit.is_checkpoint:
            return CheckpointInfo(
                step_id=visit.step_id,
                step_name=visit.step_name,
                checkpoint_description=visit.checkpoint_description,
                passed_at=visit.visited_at,
            )

    return None  # No checkpoint in history


def is_step_before_checkpoint(
    target_step_id: UUID,
    checkpoint_step_id: UUID,
    scenario: Scenario,
) -> bool:
    """
    Check if target_step comes before checkpoint in the graph.

    If true, teleporting to target would "undo" the checkpoint,
    which is not allowed.
    """

    # BFS from target to see if we can reach checkpoint
    visited = set()
    queue = [target_step_id]

    while queue:
        current = queue.pop(0)

        if current == checkpoint_step_id:
            return True  # Target is upstream of checkpoint

        if current in visited:
            continue
        visited.add(current)

        step = scenario.get_step(current)
        if step:
            for transition in step.transitions:
                queue.append(transition.to_step_id)

    return False  # Target is not upstream of checkpoint


@dataclass
class CheckpointInfo:
    """Information about a checkpoint in the session's path."""
    step_id: UUID
    step_name: str
    checkpoint_description: str
    passed_at: datetime
```

### Checkpoint Blocking Logic

When a migration would teleport a user past a checkpoint they've already completed:

1. **Do NOT teleport** - the action is irreversible
2. **Log a warning** - operators should know this happened
3. **Continue on current path** - respect the completed action
4. **Optionally notify via LLM** - explain to user if appropriate

```python
# In execute_re_route, when checkpoint blocks teleportation:

if is_step_before_checkpoint(branch.target_step_id, last_checkpoint.step_id, ...):
    # The new rules say user should be rejected/redirected,
    # BUT they already completed an irreversible action.
    #
    # We CANNOT undo: "Order dispatched", "Payment processed", etc.
    #
    # So we continue but log the anomaly for operators.

    logger.warning(
        "teleport_blocked_by_checkpoint",
        session_id=session.id,
        checkpoint=last_checkpoint.checkpoint_description,
        would_teleport_to=branch.target_step_name,
        new_rule=branch.condition_text,
    )

    return ReconciliationResult(
        action="continue",
        blocked_by_checkpoint=True,
        checkpoint_warning=f"New rule '{branch.condition_text}' would redirect "
                          f"to '{branch.target_step_name}', but checkpoint "
                          f"'{last_checkpoint.checkpoint_description}' prevents this."
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
                confidence=field.confidence,
            )

    # Check session variables (current conversation)
    if field_name in session.variables:
        return GapFillResult(
            filled=True,
            value=session.variables[field_name],
            source="session",
            confidence=1.0,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TIER 2: Conversation Extraction (LLM)
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
            needs_confirmation=(extraction.confidence < 0.95),
        )

        return GapFillResult(
            filled=True,
            value=extraction.value,
            source="extraction",
            confidence=extraction.confidence,
            needs_confirmation=(extraction.confidence < 0.95),
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

## Data Models

### Migration Plan

```python
@dataclass
class MigrationPlan:
    """Pre-computed migration plan for a scenario version transition."""

    id: UUID = field(default_factory=uuid4)
    scenario_id: UUID
    from_version: int
    to_version: int

    # Graph analysis
    transformation_map: TransformationMap
    scenario_checksum_v1: str
    scenario_checksum_v2: str

    # Per-anchor policies
    anchor_policies: Dict[str, AnchorMigrationPolicy]  # Key: content_hash

    # Summary for operator review
    summary: MigrationSummary

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    # Status
    status: str = "pending"  # "pending" | "approved" | "deployed" | "superseded"


@dataclass
class TransformationMap:
    """Complete transformation analysis between two scenario versions."""

    anchors: List[AnchorTransformation]  # Nodes that exist in both versions
    deleted_nodes: List[DeletedNode]  # Nodes in V1 but not V2
    new_nodes: List[UUID]  # Nodes in V2 but not V1

    def get_transformation_for_anchor(self, content_hash: str) -> Optional[AnchorTransformation]:
        for anchor in self.anchors:
            if anchor.anchor_content_hash == content_hash:
                return anchor
        return None


@dataclass
class DeletedNode:
    """A node that was deleted between V1 and V2."""
    node_id_v1: UUID
    node_name: str
    nearest_anchor_hash: Optional[str]  # Anchor to relocate to
    nearest_anchor_id_v2: Optional[UUID]
```

### Session Fields

```python
@dataclass
class Session:
    """Session model with migration support."""

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    customer_profile_id: UUID

    # Scenario tracking
    active_scenario_id: Optional[UUID] = None
    active_scenario_version: Optional[int] = None
    scenario_checksum: Optional[str] = None  # For validation
    active_step_id: Optional[UUID] = None

    # Migration support
    pending_migration: Optional[PendingMigration] = None

    # History for checkpoint detection
    step_history: List[StepVisit] = field(default_factory=list)

    # Session data
    variables: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StepVisit:
    """Record of a step visit in session history."""
    step_id: UUID
    step_name: str
    visited_at: datetime
    is_checkpoint: bool = False
    checkpoint_description: Optional[str] = None


@dataclass
class PendingMigration:
    """Marker indicating session needs migration at next turn."""
    target_version: int
    anchor_content_hash: str
    migration_plan_id: UUID
    marked_at: datetime
```

### Migration Summary

```python
@dataclass
class MigrationSummary:
    """Human-readable summary for operator review before deployment."""

    # Counts
    total_anchors: int
    anchors_with_clean_graft: int
    anchors_with_gap_fill: int
    anchors_with_re_route: int
    nodes_deleted: int

    # Affected customers (estimated)
    estimated_sessions_affected: int = 0
    sessions_by_anchor: Dict[str, int] = field(default_factory=dict)

    # Warnings that need operator attention
    warnings: List[MigrationWarning] = field(default_factory=list)

    # Field collection requirements
    fields_to_collect: List[FieldCollectionInfo] = field(default_factory=list)


@dataclass
class MigrationWarning:
    """Warning for operator review."""
    severity: str  # "info" | "warning" | "critical"
    anchor_name: str
    message: str


@dataclass
class FieldCollectionInfo:
    """Information about a field that needs collection."""
    field_name: str
    display_name: str
    affected_anchors: List[str]
    reason: str
    can_extract_from_conversation: bool
```

### Reconciliation Result

```python
@dataclass
class ReconciliationResult:
    """Result of applying migration to a session."""

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

    # Checkpoint blocking
    blocked_by_checkpoint: bool = False
    checkpoint_warning: Optional[str] = None

    # Debug/audit
    reason: Optional[str] = None
```

---

## Multi-Version Handling

When a session spans multiple version updates (V1 → V2 → V3):

### Composite Migration

```python
async def execute_composite_migration(
    session: Session,
    start_version: int,
    end_version: int,
    profile: CustomerProfile,
) -> ReconciliationResult:
    """
    Handle multi-version gaps by computing net effect.

    Prevents "thrashing" - asking for data that intermediate
    versions needed but final version doesn't.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 1: Fetch Plan Chain
    # ═══════════════════════════════════════════════════════════════════════════

    plans = await get_plan_chain(
        scenario_id=session.active_scenario_id,
        start_version=start_version,
        end_version=end_version,
    )

    if not plans:
        # Chain broken - fall back to anchor-based relocation
        return await fallback_reconciliation(session, end_version)

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 2: Simulate Through All Versions (In Memory)
    # ═══════════════════════════════════════════════════════════════════════════

    virtual_step_hash = compute_node_content_hash(
        await get_step(session.active_step_id)
    )
    accumulated_requirements = set()
    checkpoints_encountered = []

    for plan in plans:
        transformation = plan.transformation_map.get_transformation_for_anchor(
            virtual_step_hash
        )

        if transformation is None:
            continue  # Step unchanged in this version

        # Track field requirements from this version
        for node in transformation.upstream_changes.inserted_nodes:
            accumulated_requirements.update(node.collects_fields)

        # Track checkpoints
        for fork in transformation.upstream_changes.new_forks:
            for branch in fork.branches:
                checkpoints = find_checkpoints_in_path(
                    branch.target_step_id,
                    plan.new_scenario,
                )
                checkpoints_encountered.extend(checkpoints)

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 3: Prune Requirements (Anti-Thrash)
    # ═══════════════════════════════════════════════════════════════════════════

    final_scenario = await config_store.get_scenario(
        session.active_scenario_id,
        version=end_version,
    )

    final_requirements = set()
    for field_name in accumulated_requirements:
        if is_field_needed_in_scenario(field_name, final_scenario):
            final_requirements.add(field_name)
        # else: field needed by intermediate version but not final - PRUNE

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 4: Gap Fill Only Final Requirements
    # ═══════════════════════════════════════════════════════════════════════════

    missing_fields = []
    for field_name in final_requirements:
        result = await fill_gap(field_name, profile, session)
        if not result.filled:
            missing_fields.append(field_name)

    if missing_fields:
        return ReconciliationResult(
            action="collect",
            collect_fields=missing_fields,
            user_message=build_collection_prompt(missing_fields),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 5: Apply Final Position
    # ═══════════════════════════════════════════════════════════════════════════

    # Find anchor in final version
    final_anchor = find_anchor_by_hash(virtual_step_hash, final_scenario)

    if final_anchor is None:
        return ReconciliationResult(
            action="exit_scenario",
            user_message="I need to start fresh. Let me help you from the beginning.",
        )

    return ReconciliationResult(
        action="teleport",
        target_step_id=final_anchor.id,
        teleport_reason=f"Composite migration V{start_version}→V{end_version}",
        user_message=None,
    )
```

### Benefits of Composite Migration

| Aspect | Without Composite | With Composite |
|--------|-------------------|----------------|
| **User Experience** | Confusing - asked for data that's immediately obsolete | Clean - only questions for final state |
| **Data Integrity** | Polluted - session contains fragments from deleted flows | Pure - reflects only active version |
| **Performance** | Slow - multiple DB writes per intermediate version | Fast - single atomic update |
| **Auditability** | Noisy - many migration events | Clean - one composite event |

---

## User Experience

### Silent Operations

These happen without user notification:
- Clean graft (just attaching new downstream)
- Gap fill from profile (instant)
- Gap fill from session variables (instant)
- Relocation to anchor when step deleted

### User-Facing Prompts

**Data collection** (when gap fill fails):
```
"Before we continue, I need to confirm a few things. What is your email address?"
```

**Re-routing** (when fork redirects):
```
"I have new instructions regarding your request. Let me redirect our conversation."
```

**Confirmation** (when extraction confidence is medium):
```
"Just to confirm - your email is john@example.com, correct?"
```

---

## Configuration

```toml
[scenario_migration]
enabled = true

# Two-phase deployment
[scenario_migration.deployment]
auto_mark_sessions = true  # Mark sessions at deployment time
require_approval = true  # Operator must approve before deployment

# Gap fill settings
[scenario_migration.gap_fill]
extraction_enabled = true
extraction_confidence_threshold = 0.85
confirmation_threshold = 0.95
max_conversation_turns = 20

# Re-routing settings
[scenario_migration.re_routing]
enabled = true
notify_user = true
notification_template = "I have new instructions. Let me redirect our conversation."

# Checkpoint handling
[scenario_migration.checkpoints]
block_teleport_past_checkpoint = true
log_checkpoint_blocks = true

# Retention
[scenario_migration.retention]
version_retention_days = 7
plan_retention_days = 30

# Logging
[scenario_migration.logging]
log_clean_grafts = false  # Usually too noisy
log_gap_fills = true
log_re_routes = true
log_checkpoint_blocks = true
```

---

## Observability

### Events

```python
class MigrationAppliedEvent(BaseModel):
    """Logged when a migration is applied to a session."""

    session_id: UUID
    scenario_id: UUID
    plan_id: UUID
    from_version: int
    to_version: int

    # Migration scenario used
    migration_scenario: str  # "clean_graft" | "gap_fill" | "re_route"

    # What happened
    anchor_hash: str
    step_before: UUID
    action_taken: str
    step_after: Optional[UUID] = None

    # Gap fill details
    fields_gap_filled: Dict[str, str] = {}  # field_name -> source
    fields_collected: List[str] = []  # Asked user

    # Checkpoint details
    blocked_by_checkpoint: bool = False
    checkpoint_id: Optional[UUID] = None
    checkpoint_description: Optional[str] = None

    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Metrics

```
migration_plans_generated_total (counter)
migration_plans_approved_total (counter)
migration_sessions_marked_total (counter) - at deployment
migration_applied_total (counter) - by scenario type
migration_gap_fills_total (counter) - by source
migration_checkpoint_blocks_total (counter)
migration_plan_generation_duration_ms (histogram)
migration_application_duration_ms (histogram)
```

---

## Trade-offs and Alternatives

### Cheap & Simple Alternative

Accept the "delta" created by updating a Scenario under active sessions:

```
Pros:
- No complexity
- No migration infrastructure

Cons:
- Some users may be "out of sync"
- New rules may not apply to existing sessions
- Inconsistent behavior during rollouts
```

**Use this when:**
- Scenario updates are rare
- Sessions are short-lived
- Business rules are not critical

### Full Migration (This Document)

Use anchor-based migration with two-phase deployment:

```
Pros:
- Consistent behavior
- New rules applied properly
- Checkpoint respect
- Operator visibility

Cons:
- More complex
- Requires migration infrastructure
- Some edge cases require manual handling
```

**Use this when:**
- Channels are long-lived (WhatsApp, SMS)
- New rules are business-critical
- Consistent behavior required across all sessions

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
│  Total anchors:         8                                                   │
│  Clean graft:           5                                                   │
│  Gap fill:              2                                                   │
│  Re-route:              1                                                   │
│  Nodes deleted:         0                                                   │
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
│  Anchor Details                                                             │
│  ────────────────────────────────────────────────────────────────────────── │
│  Welcome           → gap_fill (email)    (12 sessions)                     │
│                      scope: WhatsApp only                                   │
│                      update_downstream: true                                │
│                                                                              │
│  Product Selection → clean_graft          (45 sessions)                    │
│                                                                              │
│  Checkout          → re_route             (3 sessions)                     │
│                      if age < 18 → Rejected                                 │
│                      blocked by: Payment Processed                          │
│                                                                              │
│  Order Confirmation→ clean_graft          (54 sessions)                    │
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
