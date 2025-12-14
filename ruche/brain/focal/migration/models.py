"""Migration models for scenario version transitions.

Defines MigrationPlan, TransformationMap, and related entities for
anchor-based migration between scenario versions.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


# =============================================================================
# Enums (T004)
# =============================================================================


class MigrationPlanStatus(str, Enum):
    """Migration plan lifecycle status."""

    PENDING = "pending"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class MigrationScenario(str, Enum):
    """Type of migration to apply at an anchor."""

    CLEAN_GRAFT = "clean_graft"
    GAP_FILL = "gap_fill"
    RE_ROUTE = "re_route"


# =============================================================================
# Change Models (T007, T008)
# =============================================================================


class InsertedNode(BaseModel):
    """A node inserted between V1 and V2."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    node_id: UUID = Field(..., description="Step ID in new version")
    node_name: str = Field(..., description="Human-readable name")
    collects_fields: list[str] = Field(default_factory=list, description="Profile fields collected")
    has_rules: bool = Field(default=False, description="Has attached rules")
    is_required_action: bool = Field(default=False, description="Must execute action")
    is_checkpoint: bool = Field(default=False, description="Irreversible action")


class ForkBranch(BaseModel):
    """One branch of a fork."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    target_step_id: UUID = Field(..., description="Target step")
    target_step_name: str = Field(..., description="Target step name")
    condition_text: str = Field(..., description="Natural language condition")
    condition_fields: list[str] = Field(
        default_factory=list, description="Fields needed for evaluation"
    )


class NewFork(BaseModel):
    """A new fork (branching point) added in V2."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    fork_node_id: UUID = Field(..., description="Fork step ID")
    fork_node_name: str = Field(..., description="Fork step name")
    branches: list[ForkBranch] = Field(default_factory=list, description="Available branches")


class DeletedNode(BaseModel):
    """A node that existed in V1 but not in V2."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    node_id_v1: UUID = Field(..., description="Step ID in old version")
    node_name: str = Field(..., description="Step name")
    nearest_anchor_hash: str | None = Field(default=None, description="Anchor to relocate to")
    nearest_anchor_id_v2: UUID | None = Field(
        default=None, description="Step ID in V2 for relocation"
    )


class TransitionChange(BaseModel):
    """A modified transition between versions."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    from_step_id: UUID = Field(..., description="Source step")
    to_step_id_v1: UUID | None = Field(default=None, description="Old target (None if new)")
    to_step_id_v2: UUID | None = Field(default=None, description="New target (None if removed)")
    change_type: str = Field(..., description="added | removed | modified")


class UpstreamChanges(BaseModel):
    """Changes upstream of an anchor (customer already passed through)."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    inserted_nodes: list[InsertedNode] = Field(
        default_factory=list, description="Nodes added upstream"
    )
    removed_node_ids: list[UUID] = Field(default_factory=list, description="Nodes removed upstream")
    new_forks: list[NewFork] = Field(default_factory=list, description="Forks added upstream")
    modified_transitions: list[TransitionChange] = Field(
        default_factory=list, description="Transitions changed upstream"
    )


class DownstreamChanges(BaseModel):
    """Changes downstream of an anchor (customer will encounter)."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    inserted_nodes: list[InsertedNode] = Field(
        default_factory=list, description="Nodes added downstream"
    )
    removed_node_ids: list[UUID] = Field(
        default_factory=list, description="Nodes removed downstream"
    )
    new_forks: list[NewFork] = Field(default_factory=list, description="Forks added downstream")
    modified_transitions: list[TransitionChange] = Field(
        default_factory=list, description="Transitions changed downstream"
    )


# =============================================================================
# Anchor Transformation (T009)
# =============================================================================


class AnchorTransformation(BaseModel):
    """Changes around an anchor node between V1 and V2."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    anchor_content_hash: str = Field(..., description="SHA-256 truncated to 16 chars")
    anchor_name: str = Field(..., description="Human-readable name")
    anchor_node_id_v1: UUID = Field(..., description="Step ID in V1")
    anchor_node_id_v2: UUID = Field(..., description="Step ID in V2")
    upstream_changes: UpstreamChanges = Field(
        default_factory=UpstreamChanges, description="Changes upstream"
    )
    downstream_changes: DownstreamChanges = Field(
        default_factory=DownstreamChanges, description="Changes downstream"
    )
    migration_scenario: MigrationScenario = Field(..., description="Computed migration type")


# =============================================================================
# Transformation Map (T010)
# =============================================================================


class TransformationMap(BaseModel):
    """Complete analysis of changes between scenario versions."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    anchors: list[AnchorTransformation] = Field(
        default_factory=list, description="Anchor nodes with transformations"
    )
    deleted_nodes: list[DeletedNode] = Field(
        default_factory=list, description="Nodes deleted in V2"
    )
    new_node_ids: list[UUID] = Field(
        default_factory=list, description="Nodes added in V2 (not anchors)"
    )

    def get_anchor_by_hash(self, content_hash: str) -> AnchorTransformation | None:
        """Find anchor transformation by content hash."""
        for anchor in self.anchors:
            if anchor.anchor_content_hash == content_hash:
                return anchor
        return None


# =============================================================================
# Scope Filter and Policy (T005, T006)
# =============================================================================


class ScopeFilter(BaseModel):
    """Filter for which sessions are eligible for migration."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    include_channels: list[str] = Field(
        default_factory=list, description="Only these channels (empty = all)"
    )
    exclude_channels: list[str] = Field(default_factory=list, description="Skip these channels")
    include_current_nodes: list[str] = Field(
        default_factory=list, description="Only sessions at these nodes"
    )
    exclude_current_nodes: list[str] = Field(
        default_factory=list, description="Skip sessions at these nodes"
    )
    max_session_age_days: int | None = Field(
        default=None, description="Skip sessions older than N days"
    )
    min_session_age_days: int | None = Field(
        default=None, description="Skip sessions newer than N days"
    )
    custom_conditions: list[str] = Field(default_factory=list, description="Future: DSL conditions")


class AnchorMigrationPolicy(BaseModel):
    """Migration policy for a specific anchor node."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    anchor_content_hash: str = Field(..., description="Anchor identifier")
    anchor_name: str = Field(..., description="For display")
    scope_filter: ScopeFilter = Field(
        default_factory=ScopeFilter, description="Which sessions are eligible"
    )
    update_downstream: bool = Field(
        default=True, description="If True, graft new downstream from V2"
    )
    force_scenario: str | None = Field(default=None, description="Override migration scenario")


# =============================================================================
# Migration Summary (T011)
# =============================================================================


class MigrationWarning(BaseModel):
    """Warning for operator attention."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    severity: str = Field(..., description="info | warning | critical")
    anchor_name: str = Field(..., description="Affected anchor")
    message: str = Field(..., description="Warning text")
    affected_sessions_estimate: int = Field(default=0, description="Estimated affected sessions")


class FieldCollectionInfo(BaseModel):
    """Information about a field that needs collection."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    field_name: str = Field(..., description="Field identifier")
    display_name: str = Field(..., description="Human-readable name")
    affected_anchors: list[str] = Field(
        default_factory=list, description="Anchor names needing this field"
    )
    reason: str = Field(..., description="Why collection is needed")
    can_extract_from_conversation: bool = Field(
        default=True, description="Can be extracted from history"
    )


class MigrationSummary(BaseModel):
    """Summary of migration plan for operator review."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    total_anchors: int = Field(default=0, description="Total anchor count")
    anchors_with_clean_graft: int = Field(default=0, description="Clean graft count")
    anchors_with_gap_fill: int = Field(default=0, description="Gap fill count")
    anchors_with_re_route: int = Field(default=0, description="Re-route count")
    nodes_deleted: int = Field(default=0, description="Deleted node count")
    estimated_sessions_affected: int = Field(default=0, description="Total affected sessions")
    sessions_by_anchor: dict[str, int] = Field(
        default_factory=dict, description="hash -> session count"
    )
    warnings: list[MigrationWarning] = Field(default_factory=list, description="Operator warnings")
    fields_to_collect: list[FieldCollectionInfo] = Field(
        default_factory=list, description="Data collection requirements"
    )


# =============================================================================
# Migration Plan (T012)
# =============================================================================


class MigrationPlan(BaseModel):
    """Pre-computed migration plan for scenario version transition."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    scenario_id: UUID = Field(..., description="Target scenario")
    from_version: int = Field(..., description="Source version")
    to_version: int = Field(..., description="Target version")
    scenario_checksum_v1: str = Field(..., description="Hash of old scenario")
    scenario_checksum_v2: str = Field(..., description="Hash of new scenario")
    transformation_map: TransformationMap = Field(
        default_factory=TransformationMap, description="Graph diff result"
    )
    anchor_policies: dict[str, AnchorMigrationPolicy] = Field(
        default_factory=dict, description="Per-anchor policies"
    )
    summary: MigrationSummary = Field(
        default_factory=MigrationSummary, description="Operator summary"
    )
    status: MigrationPlanStatus = Field(
        default=MigrationPlanStatus.PENDING, description="Lifecycle status"
    )
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    created_by: str | None = Field(default=None, description="Creator identifier")
    approved_at: datetime | None = Field(default=None, description="Approval timestamp")
    approved_by: str | None = Field(default=None, description="Approver identifier")
    deployed_at: datetime | None = Field(default=None, description="Deployment timestamp")
    expires_at: datetime | None = Field(default=None, description="Auto-cleanup date")


# =============================================================================
# Runtime Models (T045 - Phase 4)
# =============================================================================


class ReconciliationAction(str, Enum):
    """Action to take after reconciliation."""

    CONTINUE = "continue"
    TELEPORT = "teleport"
    COLLECT = "collect"
    EXECUTE_ACTION = "execute_action"
    EXIT_SCENARIO = "exit_scenario"


class ReconciliationResult(BaseModel):
    """Result of pre-turn reconciliation."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    action: ReconciliationAction = Field(..., description="Action to take")
    target_step_id: UUID | None = Field(default=None, description="For TELEPORT")
    teleport_reason: str | None = Field(default=None, description="Why teleporting")
    collect_fields: list[str] = Field(default_factory=list, description="For COLLECT")
    execute_action_ids: list[UUID] = Field(default_factory=list, description="For EXECUTE_ACTION")
    user_message: str | None = Field(default=None, description="User-facing message")
    blocked_by_checkpoint: bool = Field(default=False, description="Checkpoint blocking")
    checkpoint_warning: str | None = Field(default=None, description="Checkpoint block reason")
    migration_scenario: str | None = Field(default=None, description="Which scenario was used")
    anchor_hash: str | None = Field(default=None, description="Anchor identifier")
    reason: str | None = Field(default=None, description="Debug info")


# =============================================================================
# Field Resolution Models (T079 - Phase 8)
# =============================================================================


class ResolutionSource(str, Enum):
    """Source of resolved field data."""

    PROFILE = "profile"
    SESSION = "session"
    EXTRACTION = "extraction"
    NOT_FOUND = "not_found"


class FieldResolutionResult(BaseModel):
    """Result of field resolution attempt.

    Enhanced with:
    - field_definition reference for schema context
    - validation_errors for schema validation results
    - source_item_id/source_item_type for lineage tracking
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    field_name: str = Field(..., description="Field that was resolved")
    filled: bool = Field(..., description="Whether value was found")
    value: Any | None = Field(default=None, description="Resolved value")
    source: ResolutionSource = Field(
        default=ResolutionSource.NOT_FOUND, description="Where value came from"
    )
    confidence: float = Field(default=1.0, description="Extraction confidence")
    needs_confirmation: bool = Field(default=False, description="Requires user confirmation")
    extraction_quote: str | None = Field(default=None, description="Source text if extracted")

    # Schema integration (T152)
    field_definition_id: UUID | None = Field(
        default=None, description="Reference to CustomerDataField used"
    )

    # Validation results (T153)
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors from schema validation"
    )

    # Lineage tracking (T154)
    source_item_id: UUID | None = Field(
        default=None, description="ID of item this was derived from"
    )
    source_item_type: str | None = Field(
        default=None, description="Type of source item (profile_field, profile_asset, session, etc.)"
    )

    # Scenario requirement metadata (set by fill_scenario_requirements)
    required_level: str | None = Field(
        default=None, description="Requirement level: hard or soft"
    )
    fallback_action: str | None = Field(
        default=None, description="Fallback action: ask, skip, block, extract"
    )
    collection_order: int = Field(
        default=0, description="Order in which to collect if asking user"
    )


# =============================================================================
# Checkpoint Info
# =============================================================================


class CheckpointInfo(BaseModel):
    """Information about a passed checkpoint."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    step_id: UUID = Field(..., description="Checkpoint step")
    step_name: str = Field(..., description="Step name")
    checkpoint_description: str = Field(..., description="What was done")
    passed_at: datetime = Field(..., description="When checkpoint was passed")
