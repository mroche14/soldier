# Data Model: Scenario Migration System

**Feature**: 008-scenario-migration
**Date**: 2025-11-29

## Overview

This document defines the data models for the anchor-based scenario migration system. Models follow existing Focal patterns: Pydantic BaseModel, UUID identifiers, tenant scoping, and soft deletes where applicable.

---

## Core Entities

### MigrationPlan

Pre-computed migration plan for transitioning sessions from one scenario version to another.

```python
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum

class MigrationPlanStatus(str, Enum):
    """Migration plan lifecycle status."""
    PENDING = "pending"      # Generated, awaiting approval
    APPROVED = "approved"    # Approved by operator
    DEPLOYED = "deployed"    # Applied to sessions
    SUPERSEDED = "superseded"  # Replaced by newer plan
    REJECTED = "rejected"    # Operator rejected


class MigrationScenario(str, Enum):
    """Type of migration to apply at an anchor."""
    CLEAN_GRAFT = "clean_graft"  # Upstream unchanged, graft new downstream
    GAP_FILL = "gap_fill"        # New upstream nodes collect data
    RE_ROUTE = "re_route"        # New upstream fork may redirect


class MigrationPlan(BaseModel):
    """Pre-computed migration plan for scenario version transition."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    scenario_id: UUID

    # Version transition
    from_version: int
    to_version: int
    scenario_checksum_v1: str  # Hash of old scenario graph
    scenario_checksum_v2: str  # Hash of new scenario graph

    # Graph analysis result
    transformation_map: "TransformationMap"

    # Per-anchor policies (key: anchor_content_hash)
    anchor_policies: dict[str, "AnchorMigrationPolicy"] = Field(default_factory=dict)

    # Operator review summary
    summary: "MigrationSummary"

    # Lifecycle
    status: MigrationPlanStatus = MigrationPlanStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    deployed_at: datetime | None = None

    # Retention
    expires_at: datetime | None = None  # Auto-cleanup after this date
```

**Relationships**:
- References `Scenario` by `scenario_id`
- Contains `TransformationMap` (embedded)
- Contains `AnchorMigrationPolicy` per anchor (embedded)

**Validation Rules**:
- `from_version < to_version`
- `status` transitions: PENDING → APPROVED → DEPLOYED (or PENDING → REJECTED)
- `approved_at` required when `status == APPROVED`

---

### TransformationMap

Complete graph diff between two scenario versions.

```python
class TransformationMap(BaseModel):
    """Complete analysis of changes between scenario versions."""

    # Anchor nodes (exist in both versions with same semantic content)
    anchors: list["AnchorTransformation"] = Field(default_factory=list)

    # Nodes deleted in V2
    deleted_nodes: list["DeletedNode"] = Field(default_factory=list)

    # Nodes added in V2 (not anchors)
    new_node_ids: list[UUID] = Field(default_factory=list)

    def get_anchor_by_hash(self, content_hash: str) -> "AnchorTransformation | None":
        """Find anchor transformation by content hash."""
        for anchor in self.anchors:
            if anchor.anchor_content_hash == content_hash:
                return anchor
        return None
```

---

### AnchorTransformation

Changes around a specific anchor node between versions.

```python
class AnchorTransformation(BaseModel):
    """Changes around an anchor node between V1 and V2."""

    # Anchor identification
    anchor_content_hash: str  # SHA-256 truncated to 16 chars
    anchor_name: str  # Human-readable name
    anchor_node_id_v1: UUID  # Step ID in V1
    anchor_node_id_v2: UUID  # Step ID in V2

    # What changed UPSTREAM (customer has already passed through)
    upstream_changes: "UpstreamChanges"

    # What changed DOWNSTREAM (customer will encounter)
    downstream_changes: "DownstreamChanges"

    # Computed migration scenario
    migration_scenario: MigrationScenario
```

---

### UpstreamChanges / DownstreamChanges

```python
class InsertedNode(BaseModel):
    """A node inserted between V1 and V2."""
    node_id: UUID
    node_name: str
    collects_fields: list[str] = Field(default_factory=list)
    has_rules: bool = False
    is_required_action: bool = False
    is_checkpoint: bool = False


class NewFork(BaseModel):
    """A new fork (branching point) added in V2."""
    fork_node_id: UUID
    fork_node_name: str
    branches: list["ForkBranch"] = Field(default_factory=list)


class ForkBranch(BaseModel):
    """One branch of a fork."""
    target_step_id: UUID
    target_step_name: str
    condition_text: str  # Natural language condition
    condition_fields: list[str] = Field(default_factory=list)  # Fields needed


class TransitionChange(BaseModel):
    """A modified transition between versions."""
    from_step_id: UUID
    to_step_id_v1: UUID | None  # Old target (None if new)
    to_step_id_v2: UUID | None  # New target (None if removed)
    change_type: str  # "added" | "removed" | "modified"


class UpstreamChanges(BaseModel):
    """Changes upstream of an anchor (customer already passed through)."""
    inserted_nodes: list[InsertedNode] = Field(default_factory=list)
    removed_node_ids: list[UUID] = Field(default_factory=list)
    new_forks: list[NewFork] = Field(default_factory=list)
    modified_transitions: list[TransitionChange] = Field(default_factory=list)


class DownstreamChanges(BaseModel):
    """Changes downstream of an anchor (customer will encounter)."""
    inserted_nodes: list[InsertedNode] = Field(default_factory=list)
    removed_node_ids: list[UUID] = Field(default_factory=list)
    new_forks: list[NewFork] = Field(default_factory=list)
    modified_transitions: list[TransitionChange] = Field(default_factory=list)
```

---

### DeletedNode

```python
class DeletedNode(BaseModel):
    """A node that existed in V1 but not in V2."""
    node_id_v1: UUID
    node_name: str
    nearest_anchor_hash: str | None = None  # Anchor to relocate to
    nearest_anchor_id_v2: UUID | None = None  # Step ID in V2 for relocation
```

---

### AnchorMigrationPolicy

Per-anchor configuration set by operator.

```python
class ScopeFilter(BaseModel):
    """Filter for which sessions are eligible for migration."""
    include_channels: list[str] = Field(default_factory=list)  # Empty = all
    exclude_channels: list[str] = Field(default_factory=list)
    include_current_nodes: list[str] = Field(default_factory=list)  # Node names
    exclude_current_nodes: list[str] = Field(default_factory=list)
    max_session_age_days: int | None = None
    min_session_age_days: int | None = None
    custom_conditions: list[str] = Field(default_factory=list)  # Future: DSL

    def matches(self, session: "Session", step_name: str) -> bool:
        """Check if session matches this filter."""
        # Channel filtering
        if self.include_channels and session.channel.value not in self.include_channels:
            return False
        if session.channel.value in self.exclude_channels:
            return False

        # Node filtering
        if self.include_current_nodes and step_name not in self.include_current_nodes:
            return False
        if step_name in self.exclude_current_nodes:
            return False

        # Age filtering
        if self.max_session_age_days:
            age = (datetime.utcnow() - session.created_at).days
            if age > self.max_session_age_days:
                return False
        if self.min_session_age_days:
            age = (datetime.utcnow() - session.created_at).days
            if age < self.min_session_age_days:
                return False

        return True


class AnchorMigrationPolicy(BaseModel):
    """Migration policy for a specific anchor node."""
    anchor_content_hash: str
    anchor_name: str  # For display

    # Scope: which sessions are eligible
    scope_filter: ScopeFilter = Field(default_factory=ScopeFilter)

    # Update policy
    update_downstream: bool = True  # If True, graft new downstream from V2

    # Override: force specific migration scenario
    force_scenario: str | None = None  # "clean_graft" | "gap_fill" | "re_route"
```

---

### MigrationSummary

Human-readable summary for operator review.

```python
class MigrationWarning(BaseModel):
    """Warning for operator attention."""
    severity: str  # "info" | "warning" | "critical"
    anchor_name: str
    message: str
    affected_sessions_estimate: int = 0


class FieldCollectionInfo(BaseModel):
    """Information about a field that needs collection."""
    field_name: str
    display_name: str
    affected_anchors: list[str] = Field(default_factory=list)
    reason: str
    can_extract_from_conversation: bool = True


class MigrationSummary(BaseModel):
    """Summary of migration plan for operator review."""

    # Counts by scenario type
    total_anchors: int = 0
    anchors_with_clean_graft: int = 0
    anchors_with_gap_fill: int = 0
    anchors_with_re_route: int = 0
    nodes_deleted: int = 0

    # Affected sessions (estimated)
    estimated_sessions_affected: int = 0
    sessions_by_anchor: dict[str, int] = Field(default_factory=dict)  # hash -> count

    # Operator warnings
    warnings: list[MigrationWarning] = Field(default_factory=list)

    # Data collection requirements
    fields_to_collect: list[FieldCollectionInfo] = Field(default_factory=list)
```

---

## Session Extensions

### PendingMigration

Marker on session indicating migration needed at next turn.

```python
class PendingMigration(BaseModel):
    """Session marker for pending migration."""
    target_version: int
    anchor_content_hash: str
    migration_plan_id: UUID
    marked_at: datetime = Field(default_factory=datetime.utcnow)
```

### StepVisit (Extended)

```python
class StepVisit(BaseModel):
    """Record of visiting a scenario step (extended for migration)."""
    step_id: UUID
    step_name: str  # For checkpoint description
    entered_at: datetime
    turn_number: int
    transition_reason: str | None = None  # "entry" | "transition" | "relocalize"
    confidence: float = 1.0

    # Migration/checkpoint support
    is_checkpoint: bool = False
    checkpoint_description: str | None = None
    step_content_hash: str | None = None  # For anchor matching
```

### Session (Extended Fields)

```python
class Session(BaseModel):
    """Session model with migration support fields."""
    # ... existing fields ...

    # Migration support (NEW)
    pending_migration: PendingMigration | None = None
    scenario_checksum: str | None = None  # For version validation

    # step_history already exists, StepVisit extended above
```

---

## Runtime Entities

### ReconciliationResult

Outcome of applying migration to a session.

```python
class ReconciliationAction(str, Enum):
    """Action to take after reconciliation."""
    CONTINUE = "continue"        # No migration needed, proceed normally
    TELEPORT = "teleport"        # Move to new step silently
    COLLECT = "collect"          # Collect missing data before continuing
    EXECUTE_ACTION = "execute_action"  # Execute required actions
    EXIT_SCENARIO = "exit_scenario"    # Exit scenario (no valid anchor)


class ReconciliationResult(BaseModel):
    """Result of pre-turn reconciliation."""
    action: ReconciliationAction

    # For TELEPORT
    target_step_id: UUID | None = None
    teleport_reason: str | None = None

    # For COLLECT
    collect_fields: list[str] = Field(default_factory=list)

    # For EXECUTE_ACTION
    execute_action_ids: list[UUID] = Field(default_factory=list)

    # User-facing message (if any)
    user_message: str | None = None

    # Checkpoint blocking
    blocked_by_checkpoint: bool = False
    checkpoint_warning: str | None = None

    # Audit/debug
    migration_scenario: str | None = None  # Which scenario was used
    anchor_hash: str | None = None
    reason: str | None = None
```

---

### GapFillResult

Result of attempting to retrieve data without asking user.

```python
class GapFillSource(str, Enum):
    """Source of gap-filled data."""
    PROFILE = "profile"
    SESSION = "session"
    EXTRACTION = "extraction"
    NOT_FOUND = "not_found"


class GapFillResult(BaseModel):
    """Result of gap fill attempt."""
    field_name: str
    filled: bool
    value: Any | None = None
    source: GapFillSource = GapFillSource.NOT_FOUND
    confidence: float = 1.0
    needs_confirmation: bool = False
    extraction_quote: str | None = None  # Source text if extracted
```

---

### CheckpointInfo

Information about a checkpoint in session history.

```python
class CheckpointInfo(BaseModel):
    """Information about a passed checkpoint."""
    step_id: UUID
    step_name: str
    checkpoint_description: str
    passed_at: datetime
```

---

## Audit Events

### MigrationAppliedEvent

Logged to AuditStore when migration is applied.

```python
class MigrationAppliedEvent(BaseModel):
    """Audit event for migration application."""
    event_type: str = "migration_applied"

    # Identifiers
    session_id: UUID
    tenant_id: UUID
    scenario_id: UUID
    plan_id: UUID

    # Version transition
    from_version: int
    to_version: int

    # What happened
    migration_scenario: str  # "clean_graft" | "gap_fill" | "re_route"
    anchor_hash: str
    step_before_id: UUID
    action_taken: str  # "teleport" | "collect" | "continue" | "exit"
    step_after_id: UUID | None = None

    # Gap fill details
    fields_gap_filled: dict[str, str] = Field(default_factory=dict)  # field -> source
    fields_collected: list[str] = Field(default_factory=list)  # Asked user

    # Checkpoint details
    blocked_by_checkpoint: bool = False
    checkpoint_id: UUID | None = None
    checkpoint_description: str | None = None

    # Timing
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## Configuration Models

### ScenarioMigrationConfig

Configuration for migration behavior (loaded from TOML).

```python
class DeploymentConfig(BaseModel):
    """Deployment phase configuration."""
    auto_mark_sessions: bool = True
    require_approval: bool = True


class GapFillConfig(BaseModel):
    """Gap fill configuration."""
    extraction_enabled: bool = True
    extraction_confidence_threshold: float = 0.85
    confirmation_threshold: float = 0.95
    max_conversation_turns: int = 20


class ReRoutingConfig(BaseModel):
    """Re-routing configuration."""
    enabled: bool = True
    notify_user: bool = True
    notification_template: str = "I have new instructions. Let me redirect our conversation."


class CheckpointConfig(BaseModel):
    """Checkpoint handling configuration."""
    block_teleport_past_checkpoint: bool = True
    log_checkpoint_blocks: bool = True


class RetentionConfig(BaseModel):
    """Retention configuration."""
    version_retention_days: int = 7
    plan_retention_days: int = 30


class LoggingConfig(BaseModel):
    """Migration logging configuration."""
    log_clean_grafts: bool = False
    log_gap_fills: bool = True
    log_re_routes: bool = True
    log_checkpoint_blocks: bool = True


class ScenarioMigrationConfig(BaseModel):
    """Root migration configuration."""
    enabled: bool = True
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    gap_fill: GapFillConfig = Field(default_factory=GapFillConfig)
    re_routing: ReRoutingConfig = Field(default_factory=ReRoutingConfig)
    checkpoints: CheckpointConfig = Field(default_factory=CheckpointConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

---

## Entity Relationships Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MigrationPlan                                  │
│  - id, tenant_id, scenario_id                                           │
│  - from_version, to_version                                             │
│  - status: PENDING → APPROVED → DEPLOYED                                │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐  │
│  │  TransformationMap   │    │  anchor_policies: dict[hash, Policy]  │  │
│  │  - anchors[]         │    │                                       │  │
│  │  - deleted_nodes[]   │    │  ┌────────────────────────────────┐  │  │
│  │  - new_node_ids[]    │    │  │  AnchorMigrationPolicy         │  │  │
│  └──────────┬───────────┘    │  │  - scope_filter: ScopeFilter   │  │  │
│             │                │  │  - update_downstream: bool     │  │  │
│             ▼                │  └────────────────────────────────┘  │  │
│  ┌──────────────────────┐    └──────────────────────────────────────┘  │
│  │ AnchorTransformation │                                               │
│  │ - anchor_content_hash│    ┌──────────────────────────────────────┐  │
│  │ - upstream_changes   │    │  MigrationSummary                     │  │
│  │ - downstream_changes │    │  - counts by scenario type            │  │
│  │ - migration_scenario │    │  - warnings[]                         │  │
│  └──────────────────────┘    │  - fields_to_collect[]                │  │
│                              └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              Session                                     │
│  - active_scenario_id, active_scenario_version                          │
│  - scenario_checksum (NEW)                                              │
│  - pending_migration: PendingMigration | None (NEW)                     │
│  - step_history: list[StepVisit]                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐    │
│  │  PendingMigration       │    │  StepVisit (extended)           │    │
│  │  - target_version       │    │  - step_id, step_name           │    │
│  │  - anchor_content_hash  │    │  - is_checkpoint (NEW)          │    │
│  │  - migration_plan_id    │    │  - checkpoint_description (NEW) │    │
│  │  - marked_at            │    │  - step_content_hash (NEW)      │    │
│  └─────────────────────────┘    └─────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## State Transitions

### MigrationPlan Status

```
         ┌──────────┐
         │  PENDING │
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         │
┌────────┐ ┌────────┐   │
│APPROVED│ │REJECTED│   │
└───┬────┘ └────────┘   │
    │                   │
    ▼                   │
┌────────┐              │
│DEPLOYED│              │
└───┬────┘              │
    │                   │
    ▼                   │
┌──────────┐            │
│SUPERSEDED│◄───────────┘  (when newer plan created)
└──────────┘
```

### Session Migration Flow

```
Customer inactive                     Customer returns
       │                                     │
       ▼                                     ▼
┌──────────────────┐                ┌────────────────────┐
│ Session marked   │                │ Pre-turn reconcile │
│ pending_migration│───────────────►│ - Load plan        │
└──────────────────┘                │ - Determine action │
                                    └─────────┬──────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
              ▼                               ▼                               ▼
      ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
      │  Clean Graft  │              │   Gap Fill    │              │   Re-Route    │
      │ Silent teleport│              │ Check sources │              │ Eval condition│
      └───────┬───────┘              └───────┬───────┘              └───────┬───────┘
              │                               │                               │
              │                    ┌──────────┴──────────┐                   │
              │                    │                     │                   │
              │                    ▼                     ▼                   ▼
              │           ┌─────────────┐       ┌─────────────┐     ┌─────────────┐
              │           │ Data found  │       │ Data needed │     │  Teleport   │
              │           │ → continue  │       │ → collect   │     │  (or block) │
              │           └──────┬──────┘       └──────┬──────┘     └──────┬──────┘
              │                  │                     │                   │
              └──────────────────┴─────────────────────┴───────────────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ Clear pending_migration │
                                    │ Update scenario_version │
                                    │ Log to AuditStore       │
                                    └─────────────────────────┘
```
