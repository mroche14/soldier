"""Migration system for scenario version transitions.

This module provides anchor-based migration for safely updating scenarios
while customers have active sessions.
"""

from typing import Any

from soldier.alignment.migration.models import (
    AnchorMigrationPolicy,
    AnchorTransformation,
    CheckpointInfo,
    DeletedNode,
    DownstreamChanges,
    FieldCollectionInfo,
    ForkBranch,
    GapFillResult,
    GapFillSource,
    InsertedNode,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationScenario,
    MigrationSummary,
    MigrationWarning,
    NewFork,
    ReconciliationAction,
    ReconciliationResult,
    ScopeFilter,
    TransformationMap,
    TransitionChange,
    UpstreamChanges,
)


def _lazy_import_diff() -> dict[str, Any]:
    """Lazy import to avoid circular dependency."""
    from soldier.alignment.migration.diff import (
        compute_downstream_changes,
        compute_node_content_hash,
        compute_scenario_checksum,
        compute_transformation_map,
        compute_upstream_changes,
        determine_migration_scenario,
        find_anchor_nodes,
    )
    return {
        "compute_downstream_changes": compute_downstream_changes,
        "compute_node_content_hash": compute_node_content_hash,
        "compute_scenario_checksum": compute_scenario_checksum,
        "compute_transformation_map": compute_transformation_map,
        "compute_upstream_changes": compute_upstream_changes,
        "determine_migration_scenario": determine_migration_scenario,
        "find_anchor_nodes": find_anchor_nodes,
    }


def _lazy_import_planner() -> dict[str, Any]:
    """Lazy import to avoid circular dependency."""
    from soldier.alignment.migration.planner import MigrationDeployer, MigrationPlanner
    return {
        "MigrationDeployer": MigrationDeployer,
        "MigrationPlanner": MigrationPlanner,
    }

__all__ = [
    # Enums
    "MigrationPlanStatus",
    "MigrationScenario",
    "ReconciliationAction",
    "GapFillSource",
    # Core Models
    "MigrationPlan",
    "TransformationMap",
    "AnchorTransformation",
    "AnchorMigrationPolicy",
    "ScopeFilter",
    "MigrationSummary",
    "MigrationWarning",
    "FieldCollectionInfo",
    # Change Models
    "InsertedNode",
    "NewFork",
    "ForkBranch",
    "DeletedNode",
    "TransitionChange",
    "UpstreamChanges",
    "DownstreamChanges",
    # Runtime Models
    "ReconciliationResult",
    "GapFillResult",
    "CheckpointInfo",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for diff functions and planner to avoid circular imports."""
    diff_funcs = {
        "compute_node_content_hash",
        "compute_scenario_checksum",
        "find_anchor_nodes",
        "compute_upstream_changes",
        "compute_downstream_changes",
        "determine_migration_scenario",
        "compute_transformation_map",
    }
    planner_classes = {"MigrationPlanner", "MigrationDeployer"}

    if name in diff_funcs:
        imports = _lazy_import_diff()
        return imports[name]
    elif name in planner_classes:
        imports = _lazy_import_planner()
        return imports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
