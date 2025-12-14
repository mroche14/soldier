"""Migration system for scenario version transitions.

This module provides anchor-based migration for safely updating scenarios
while customers have active sessions.
"""

from typing import Any

from ruche.alignment.migration.models import (
    AnchorMigrationPolicy,
    AnchorTransformation,
    CheckpointInfo,
    DeletedNode,
    DownstreamChanges,
    FieldCollectionInfo,
    FieldResolutionResult,
    ForkBranch,
    InsertedNode,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationScenario,
    MigrationSummary,
    MigrationWarning,
    NewFork,
    ReconciliationAction,
    ReconciliationResult,
    ResolutionSource,
    ScopeFilter,
    TransformationMap,
    TransitionChange,
    UpstreamChanges,
)


def _lazy_import_diff() -> dict[str, Any]:
    """Lazy import to avoid circular dependency."""
    from ruche.alignment.migration.diff import (
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
    from ruche.alignment.migration.planner import MigrationDeployer, MigrationPlanner

    return {
        "MigrationDeployer": MigrationDeployer,
        "MigrationPlanner": MigrationPlanner,
    }


def _lazy_import_executor() -> dict[str, Any]:
    """Lazy import to avoid circular dependency."""
    from ruche.alignment.migration.executor import MigrationExecutor

    return {
        "MigrationExecutor": MigrationExecutor,
    }


__all__ = [
    # Enums
    "MigrationPlanStatus",
    "MigrationScenario",
    "ReconciliationAction",
    "ResolutionSource",
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
    "FieldResolutionResult",
    "CheckpointInfo",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for diff functions, planner, and executor to avoid circular imports."""
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
    executor_classes = {"MigrationExecutor"}

    if name in diff_funcs:
        imports = _lazy_import_diff()
        return imports[name]
    elif name in planner_classes:
        imports = _lazy_import_planner()
        return imports[name]
    elif name in executor_classes:
        imports = _lazy_import_executor()
        return imports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
