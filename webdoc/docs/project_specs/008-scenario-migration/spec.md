# Feature Specification: Scenario Migration System

**Feature Branch**: `008-scenario-migration`
**Created**: 2025-11-29
**Status**: Draft
**Input**: Implement anchor-based scenario migration system using content hashing for node identification, two-phase deployment (mark at deploy, apply at JIT), per-anchor policies, and three migration scenarios (Clean Graft, Gap Fill, Re-Routing).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Updates Scenario Without Breaking Active Sessions (Priority: P1)

An operator modifies a scenario (adds steps, changes forks, removes steps) while customers are actively traversing it. The system computes a Graph Diff using content hashes to identify Anchor Nodes (semantically equivalent steps between V1 and V2), generates a migration plan with per-anchor actions, and allows the operator to configure policies before deployment.

**Why this priority**: This is the core value proposition. Without this, operators cannot safely update scenarios when customers have active sessions, which is a critical limitation for production systems with long-lived conversations (WhatsApp, email support, etc.).

**Independent Test**: Can be fully tested by modifying a scenario with active sessions and verifying the transformation map correctly identifies anchors and upstream/downstream changes.

**Acceptance Scenarios**:

1. **Given** a scenario with active sessions at various steps, **When** an operator modifies the scenario, **Then** the system computes content hashes and identifies anchor nodes between V1 and V2
2. **Given** anchor nodes identified, **When** the system analyzes the graph diff, **Then** it produces a transformation map showing upstream changes (inserted nodes, new forks) and downstream changes for each anchor
3. **Given** a generated migration plan, **When** the operator reviews it, **Then** they see summary counts (clean graft, gap fill, re-route) and can configure per-anchor policies (scope filters, update_downstream)
4. **Given** an operator approving a migration plan, **When** deployment executes, **Then** sessions are marked with pending_migration flag but NOT migrated immediately

---

### User Story 2 - Customer Continues Conversation After Scenario Update (Priority: P1)

A customer who has been inactive returns to continue their conversation after the scenario was updated. The system detects the pending_migration flag, loads the migration plan, determines the migration scenario (Clean Graft, Gap Fill, or Re-Route), and applies it at JIT (Just-In-Time) before processing the turn.

**Why this priority**: This directly impacts customer experience. Customers should not be aware of internal updates unless absolutely necessary (e.g., when new required data must be collected or re-routing is needed).

**Independent Test**: Can be tested by simulating a customer return after scenario version change and verifying the correct migration scenario is executed.

**Acceptance Scenarios**:

1. **Given** a customer with pending_migration flag, **When** they send their next message, **Then** the system loads the migration plan and determines the migration scenario
2. **Given** migration scenario is "Clean Graft" (upstream unchanged), **When** migration executes, **Then** customer is silently teleported to the anchor in V2 with new downstream attached
3. **Given** migration scenario is "Gap Fill" (new upstream nodes collect data), **When** migration executes, **Then** system tries to backfill from profile/session/extraction before asking customer
4. **Given** migration scenario is "Re-Route" (new fork upstream), **When** migration executes, **Then** system evaluates fork condition and teleports to correct branch (unless blocked by checkpoint)

---

### User Story 3 - Operator Configures Per-Anchor Migration Policies (Priority: P2)

For each anchor node, operators can configure scope filters (which sessions are eligible) and update policies (whether to graft new downstream). This provides granular control over migration behavior rather than all-or-nothing.

**Why this priority**: Different anchors may require different handling. Some may need to apply to all channels, others only to WhatsApp. Some may need to preserve old downstream behavior while others should adopt new flows.

**Independent Test**: Can be tested by configuring different policies for different anchors and verifying sessions are filtered and migrated according to their anchor's policy.

**Acceptance Scenarios**:

1. **Given** an anchor policy with scope_filter including only WhatsApp channels, **When** deployment marks sessions, **Then** only WhatsApp sessions at that anchor are marked for migration
2. **Given** an anchor policy with update_downstream=false, **When** Clean Graft executes, **Then** session stays on V1 downstream behavior (version tracking updated but no teleport)
3. **Given** an anchor policy with max_session_age_days=30, **When** deployment marks sessions, **Then** sessions older than 30 days are excluded from migration

---

### User Story 4 - System Handles Re-Routing with Checkpoint Blocking (Priority: P2)

When a new fork is added upstream that would redirect a customer to a different branch, the system evaluates the fork condition. However, if the customer has already passed a checkpoint (irreversible action like payment), teleportation is blocked to prevent undoing completed actions.

**Why this priority**: Fork changes represent significant business logic updates (e.g., age restrictions). The system must handle these intelligently without reverting irreversible actions. Walking backwards through session history to find checkpoints is critical.

**Independent Test**: Can be tested by adding an upstream fork and verifying checkpoint blocking when customer has passed an irreversible step.

**Acceptance Scenarios**:

1. **Given** a customer at step C when a new fork is added at step A (with condition "age < 18"), **When** the customer returns and meets the condition, **Then** system walks backwards through step_history to find last checkpoint
2. **Given** customer passed checkpoint "Payment Processed", **When** teleport target is upstream of checkpoint, **Then** teleportation is blocked and system logs warning
3. **Given** teleportation blocked by checkpoint, **When** migration completes, **Then** customer continues on current path with checkpoint_warning in result

---

### User Story 5 - System Handles Multi-Version Gaps Without Thrashing (Priority: P2)

A customer who has been dormant for an extended period returns when the scenario has been updated multiple times (V1 -> V2 -> V3 -> V4). The system computes a composite migration that represents the net effect, pruning requirements from intermediate versions that are no longer needed in the final version.

**Why this priority**: Prevents poor customer experience and data pollution. Asking for data that's immediately obsolete confuses customers and wastes their time.

**Independent Test**: Can be tested by creating multiple sequential scenario updates and verifying a dormant customer only sees the net requirements of the final version.

**Acceptance Scenarios**:

1. **Given** V2 requires email and V3 removes that requirement, **When** a V1 customer returns to V3, **Then** email is pruned from requirements (not asked)
2. **Given** plan chain V1->V2, V2->V3 exists, **When** composite migration executes, **Then** system simulates through all versions in memory to calculate net effect
3. **Given** plan chain is broken (intermediate plan expired), **When** migration is needed, **Then** system falls back to anchor-based relocation using content hash

---

### User Story 6 - Gap Fill Retrieves Data Without Re-Asking Customer (Priority: P3)

When migration requires data the customer previously provided, the system attempts to retrieve it from: customer profile (cross-session), session variables (current session), or conversation extraction (LLM-based mining of chat history) before asking the customer again.

**Why this priority**: Improves customer experience by not asking for information they've already provided. Also maintains data consistency.

**Independent Test**: Can be tested by requiring a field during migration and verifying each gap fill source is checked in order.

**Acceptance Scenarios**:

1. **Given** customer email exists in profile, **When** gap fill executes, **Then** profile source is checked first and succeeds without asking
2. **Given** customer mentioned email in conversation but not in profile, **When** gap fill executes, **Then** LLM extracts it with confidence score
3. **Given** extraction confidence is below confirmation threshold (0.95), **When** extracted data is used, **Then** customer is asked to confirm before proceeding

---

### Edge Cases

- What happens when the old step no longer exists and no anchor can be found? -> Customer exits scenario with a friendly reset message
- What happens when a migration plan expires (older than retention period)? -> System falls back to anchor-based relocation using content hash
- How does system handle circular scenario graphs during fork analysis? -> Uses visited set to prevent infinite loops
- What happens if extraction fails or returns low confidence? -> Falls through to asking customer directly
- What happens when checkpoint data is missing from session history? -> Assume checkpoint not passed (allow teleportation)
- What happens when a session's scenario_checksum doesn't match? -> Treat as version mismatch, apply migration
- How are anchors identified when node IDs change? -> Content hash (intent, description, rules, fields) identifies semantic equivalence

## Requirements *(mandatory)*

### Functional Requirements

**Graph Diff & Anchor Identification:**
- **FR-001**: System MUST compute content hash for each node using stable semantic attributes (intent, description, rules, collected fields, checkpoint status)
- **FR-002**: System MUST identify anchor nodes as nodes with matching content hashes between V1 and V2
- **FR-003**: System MUST compute transformation map showing upstream_changes and downstream_changes for each anchor
- **FR-004**: System MUST store scenario checksum with session for version validation

**Per-Anchor Policies:**
- **FR-005**: System MUST support scope filters per anchor (include/exclude channels, session age, current nodes)
- **FR-006**: System MUST support update_downstream policy per anchor (true = graft new downstream, false = keep V1 behavior)
- **FR-007**: System MUST support force_scenario override per anchor (clean_graft, gap_fill, re_route)

**Two-Phase Deployment:**
- **FR-008**: System MUST mark eligible sessions with pending_migration flag at deployment time (Phase 1)
- **FR-009**: System MUST NOT apply migrations during deployment - only mark sessions
- **FR-010**: System MUST apply migrations at JIT (next user message) when pending_migration flag detected (Phase 2)

**Migration Scenarios:**
- **FR-011**: System MUST determine migration scenario: Clean Graft (upstream unchanged), Gap Fill (inserted upstream nodes), Re-Route (new upstream forks)
- **FR-012**: System MUST execute Clean Graft by silently teleporting to anchor in V2 if update_downstream=true
- **FR-013**: System MUST execute Gap Fill by backfilling from profile/session/extraction, asking user only for missing fields
- **FR-014**: System MUST execute Re-Route by evaluating fork conditions and teleporting to correct branch

**Checkpoint Handling:**
- **FR-015**: System MUST walk backwards through session step_history to find last checkpoint before teleportation
- **FR-016**: System MUST block teleportation if target step is upstream of a passed checkpoint
- **FR-017**: System MUST log checkpoint blocks with details for operator visibility

**Gap Fill:**
- **FR-018**: System MUST attempt gap fill in order: profile -> session -> conversation extraction -> ask user
- **FR-019**: System MUST extract data from conversation history using confidence thresholds (default: 0.85 for use, 0.95 for no confirmation)
- **FR-020**: System MUST persist extracted values to profile for future use

**Composite Migration:**
- **FR-021**: System MUST support composite migration for multi-version gaps
- **FR-022**: System MUST prune requirements that intermediate versions needed but final version doesn't (anti-thrash)
- **FR-023**: System MUST fall back to anchor-based relocation if plan chain is broken

**Storage & Retention:**
- **FR-024**: System MUST store migration plans with configurable retention (default: 30 days)
- **FR-025**: System MUST archive previous scenario versions with configurable retention (default: 7 days)
- **FR-026**: System MUST log all migration applications for audit purposes

### Key Entities

- **MigrationPlan**: Pre-computed migration plan containing transformation_map, anchor_policies, scenario checksums, summary, and approval status
- **TransformationMap**: Complete graph diff showing anchors (with upstream/downstream changes), deleted_nodes, and new_nodes
- **AnchorTransformation**: Changes around a specific anchor (anchor_content_hash, anchor_name, upstream_changes, downstream_changes)
- **AnchorMigrationPolicy**: Per-anchor configuration (scope_filter, update_downstream, force_scenario)
- **ScopeFilter**: Filter for eligible sessions (include/exclude channels, session age, current nodes)
- **PendingMigration**: Marker on session (target_version, anchor_content_hash, migration_plan_id, marked_at)
- **StepVisit**: Record in session history (step_id, step_name, visited_at, is_checkpoint, checkpoint_description)
- **GapFillResult**: Result of gap fill attempt (filled, value, source, confidence, needs_confirmation)
- **ReconciliationResult**: Outcome of migration (action, target_step_id, collect_fields, blocked_by_checkpoint, user_message)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can configure per-anchor policies and approve scenario updates with full visibility into customer impact in under 5 minutes
- **SC-002**: 95% of returning customers after scenario updates continue seamlessly without interruption (Clean Graft path)
- **SC-003**: Gap fill successfully retrieves data without asking customers in 80%+ of cases where data was previously provided
- **SC-004**: Zero customers are teleported past checkpoints they have already completed (100% checkpoint blocking accuracy)
- **SC-005**: Composite migration eliminates 100% of "thrashing" scenarios where customers would be asked for obsolete data
- **SC-006**: Migration plan generation (graph diff + transformation map) completes within 5 seconds for scenarios with up to 50 steps
- **SC-007**: 100% of migration applications are logged with full audit trail (session, plan, scenario used, actions taken)
- **SC-008**: Operators receive clear warnings for all checkpoint conflicts and data collection requirements before approval
- **SC-009**: Two-phase deployment correctly separates marking (deployment time) from application (JIT at next message)

## Assumptions

- Scenarios are directed graphs where steps are connected by transitions with optional conditions
- Steps can be marked as "checkpoints" representing irreversible actions (e.g., payment processed)
- Content hash is stable across versions when semantic meaning is unchanged (even if IDs change)
- Customer profiles persist across sessions and scenarios, enabling cross-session gap fill
- Session step_history includes a record of visited steps with checkpoint flags for backward traversal
- Conversation history is available for LLM-based extraction within configurable turn limits
- Field definitions exist with extraction hints to guide conversation mining
- Operators have access to a review interface (Control Plane UI) for policy configuration and approval

## Dependencies

- **ConfigStore**: Must support scenario versioning, archiving, migration plan storage, and content hash queries
- **SessionStore**: Must track active_scenario_version, scenario_checksum, step_history, and pending_migration flag
- **ProfileStore**: Must support field lookup for gap fill
- **LLMProvider**: Must support structured output for conversation extraction
- **Observability**: Must support logging migration events and metrics

## Configuration

The following configuration options should be available:

```toml
[scenario_migration]
enabled = true

[scenario_migration.deployment]
auto_mark_sessions = true  # Mark sessions at deployment time
require_approval = true  # Operator must approve before deployment

[scenario_migration.gap_fill]
extraction_enabled = true
extraction_confidence_threshold = 0.85
confirmation_threshold = 0.95
max_conversation_turns = 20

[scenario_migration.re_routing]
enabled = true
notify_user = true
notification_template = "I have new instructions. Let me redirect our conversation."

[scenario_migration.checkpoints]
block_teleport_past_checkpoint = true
log_checkpoint_blocks = true

[scenario_migration.retention]
version_retention_days = 7
plan_retention_days = 30

[scenario_migration.logging]
log_clean_grafts = false  # Usually too noisy
log_gap_fills = true
log_re_routes = true
log_checkpoint_blocks = true
```

## Out of Scope

- Real-time scenario editing while customers are mid-turn (batch updates only)
- Automatic rollback of migrations after deployment
- A/B testing of scenario versions
- Migration plan editing by operators (they can configure policies, not modify computed actions)
- Cross-scenario migration (only version transitions within same scenario)
- Automatic anchor matching for significantly restructured scenarios (falls back to relocation)
