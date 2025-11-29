"""Graph diff and content hashing for scenario migration.

Implements anchor detection, upstream/downstream analysis, and
transformation map computation for migration plan generation.
"""

import hashlib
import json
from collections import defaultdict
from uuid import UUID

from soldier.alignment.migration.models import (
    AnchorTransformation,
    DeletedNode,
    DownstreamChanges,
    ForkBranch,
    InsertedNode,
    MigrationScenario,
    NewFork,
    TransformationMap,
    UpstreamChanges,
)
from soldier.alignment.models import Scenario, ScenarioStep


def compute_node_content_hash(step: ScenarioStep) -> str:
    """Compute semantic content hash for anchor identification.

    Uses SHA-256 of JSON-serialized semantic attributes, truncated to 16 chars.

    Args:
        step: Scenario step to hash

    Returns:
        16-character hex hash string
    """
    hash_input = {
        "name": step.name,
        "description": step.description or "",
        "rule_ids": sorted(str(r) for r in step.rule_ids),
        "collects_profile_fields": sorted(step.collects_profile_fields),
        "is_checkpoint": step.is_checkpoint,
        "checkpoint_description": step.checkpoint_description or "",
        "performs_action": step.performs_action,
    }
    serialized = json.dumps(hash_input, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def compute_scenario_checksum(scenario: Scenario) -> str:
    """Compute checksum for entire scenario for version validation.

    Args:
        scenario: Scenario to compute checksum for

    Returns:
        16-character hex hash string
    """
    hash_input = {
        "name": scenario.name,
        "version": scenario.version,
        "entry_step_id": str(scenario.entry_step_id),
        "steps": [
            {
                "id": str(step.id),
                "name": step.name,
                "transitions": [
                    {
                        "to_step_id": str(t.to_step_id),
                        "condition_text": t.condition_text,
                        "priority": t.priority,
                    }
                    for t in sorted(step.transitions, key=lambda t: str(t.to_step_id))
                ],
            }
            for step in sorted(scenario.steps, key=lambda s: str(s.id))
        ],
    }
    serialized = json.dumps(hash_input, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def find_anchor_nodes(
    v1: Scenario,
    v2: Scenario,
) -> list[tuple[ScenarioStep, ScenarioStep, str]]:
    """Find anchor nodes that exist in both versions with same semantic content.

    Args:
        v1: Old scenario version
        v2: New scenario version

    Returns:
        List of (v1_step, v2_step, content_hash) tuples for matching anchors
    """
    # Build hash maps for both versions
    v1_by_hash: dict[str, ScenarioStep] = {}
    for step in v1.steps:
        content_hash = compute_node_content_hash(step)
        v1_by_hash[content_hash] = step

    v2_by_hash: dict[str, ScenarioStep] = {}
    for step in v2.steps:
        content_hash = compute_node_content_hash(step)
        v2_by_hash[content_hash] = step

    # Find matching anchors
    anchors = []
    for content_hash, v1_step in v1_by_hash.items():
        if content_hash in v2_by_hash:
            v2_step = v2_by_hash[content_hash]
            anchors.append((v1_step, v2_step, content_hash))

    return anchors


def _build_adjacency_list(
    scenario: Scenario,
) -> tuple[dict[UUID, list[UUID]], dict[UUID, ScenarioStep]]:
    """Build forward adjacency list and step map for scenario."""
    adj: dict[UUID, list[UUID]] = defaultdict(list)
    step_map: dict[UUID, ScenarioStep] = {}

    for step in scenario.steps:
        step_map[step.id] = step
        for transition in step.transitions:
            adj[step.id].append(transition.to_step_id)

    return dict(adj), step_map


def _build_reverse_adjacency_list(scenario: Scenario) -> dict[UUID, list[UUID]]:
    """Build reverse adjacency list for upstream traversal."""
    reverse: dict[UUID, list[UUID]] = defaultdict(list)

    for step in scenario.steps:
        for transition in step.transitions:
            reverse[transition.to_step_id].append(step.id)

    return dict(reverse)


def compute_upstream_changes(
    v1: Scenario,
    v2: Scenario,
    anchor_id_v1: UUID,
    anchor_id_v2: UUID,
) -> UpstreamChanges:
    """Compute changes upstream of an anchor using reverse BFS.

    Args:
        v1: Old scenario version
        v2: New scenario version
        anchor_id_v1: Anchor step ID in V1
        anchor_id_v2: Anchor step ID in V2

    Returns:
        UpstreamChanges describing what changed upstream of the anchor
    """
    # Get all nodes reachable upstream in both versions
    v1_upstream = _find_upstream_nodes(v1, anchor_id_v1)
    v2_upstream = _find_upstream_nodes(v2, anchor_id_v2)

    # Build step maps for reference
    v1_step_map = {s.id: s for s in v1.steps}
    v2_step_map = {s.id: s for s in v2.steps}

    # Build content hash maps to identify same nodes across versions
    v1_hash_to_id: dict[str, UUID] = {}
    for step_id in v1_upstream:
        step = v1_step_map.get(step_id)
        if step:
            v1_hash_to_id[compute_node_content_hash(step)] = step_id

    v2_hash_to_id: dict[str, UUID] = {}
    for step_id in v2_upstream:
        step = v2_step_map.get(step_id)
        if step:
            v2_hash_to_id[compute_node_content_hash(step)] = step_id

    # Find inserted nodes (in V2 upstream but not in V1 by content hash)
    inserted_nodes = []
    new_forks = []
    for step_id in v2_upstream:
        step = v2_step_map.get(step_id)
        if not step:
            continue
        content_hash = compute_node_content_hash(step)
        if content_hash not in v1_hash_to_id:
            inserted_nodes.append(
                InsertedNode(
                    node_id=step.id,
                    node_name=step.name,
                    collects_fields=step.collects_profile_fields,
                    has_rules=len(step.rule_ids) > 0,
                    is_required_action=step.is_required_action,
                    is_checkpoint=step.is_checkpoint,
                )
            )
            # Check if it's a fork (multiple outgoing transitions)
            if len(step.transitions) > 1:
                branches = [
                    ForkBranch(
                        target_step_id=t.to_step_id,
                        target_step_name=v2_step_map.get(t.to_step_id, ScenarioStep(
                            scenario_id=v2.id, name="Unknown"
                        )).name,
                        condition_text=t.condition_text,
                        condition_fields=t.condition_fields,
                    )
                    for t in step.transitions
                ]
                new_forks.append(
                    NewFork(
                        fork_node_id=step.id,
                        fork_node_name=step.name,
                        branches=branches,
                    )
                )

    # Find removed nodes (in V1 upstream but not in V2 by content hash)
    removed_node_ids = []
    for step_id in v1_upstream:
        step = v1_step_map.get(step_id)
        if not step:
            continue
        content_hash = compute_node_content_hash(step)
        if content_hash not in v2_hash_to_id:
            removed_node_ids.append(step_id)

    return UpstreamChanges(
        inserted_nodes=inserted_nodes,
        removed_node_ids=removed_node_ids,
        new_forks=new_forks,
        modified_transitions=[],  # TODO: Implement transition diff
    )


def _find_upstream_nodes(scenario: Scenario, target_id: UUID) -> set[UUID]:
    """Find all nodes upstream of target using reverse BFS."""
    reverse_adj = _build_reverse_adjacency_list(scenario)

    visited: set[UUID] = set()
    queue = [target_id]
    upstream: set[UUID] = set()

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        for predecessor in reverse_adj.get(current, []):
            if predecessor not in visited:
                upstream.add(predecessor)
                queue.append(predecessor)

    return upstream


def compute_downstream_changes(
    v1: Scenario,
    v2: Scenario,
    anchor_id_v1: UUID,
    anchor_id_v2: UUID,
) -> DownstreamChanges:
    """Compute changes downstream of an anchor using forward BFS.

    Args:
        v1: Old scenario version
        v2: New scenario version
        anchor_id_v1: Anchor step ID in V1
        anchor_id_v2: Anchor step ID in V2

    Returns:
        DownstreamChanges describing what changed downstream of the anchor
    """
    # Get all nodes reachable downstream in both versions
    v1_downstream = _find_downstream_nodes(v1, anchor_id_v1)
    v2_downstream = _find_downstream_nodes(v2, anchor_id_v2)

    # Build step maps for reference
    v1_step_map = {s.id: s for s in v1.steps}
    v2_step_map = {s.id: s for s in v2.steps}

    # Build content hash maps to identify same nodes across versions
    v1_hash_to_id: dict[str, UUID] = {}
    for step_id in v1_downstream:
        step = v1_step_map.get(step_id)
        if step:
            v1_hash_to_id[compute_node_content_hash(step)] = step_id

    v2_hash_to_id: dict[str, UUID] = {}
    for step_id in v2_downstream:
        step = v2_step_map.get(step_id)
        if step:
            v2_hash_to_id[compute_node_content_hash(step)] = step_id

    # Find inserted nodes
    inserted_nodes = []
    new_forks = []
    for step_id in v2_downstream:
        step = v2_step_map.get(step_id)
        if not step:
            continue
        content_hash = compute_node_content_hash(step)
        if content_hash not in v1_hash_to_id:
            inserted_nodes.append(
                InsertedNode(
                    node_id=step.id,
                    node_name=step.name,
                    collects_fields=step.collects_profile_fields,
                    has_rules=len(step.rule_ids) > 0,
                    is_required_action=step.is_required_action,
                    is_checkpoint=step.is_checkpoint,
                )
            )
            # Check if it's a fork
            if len(step.transitions) > 1:
                branches = [
                    ForkBranch(
                        target_step_id=t.to_step_id,
                        target_step_name=v2_step_map.get(t.to_step_id, ScenarioStep(
                            scenario_id=v2.id, name="Unknown"
                        )).name,
                        condition_text=t.condition_text,
                        condition_fields=t.condition_fields,
                    )
                    for t in step.transitions
                ]
                new_forks.append(
                    NewFork(
                        fork_node_id=step.id,
                        fork_node_name=step.name,
                        branches=branches,
                    )
                )

    # Find removed nodes
    removed_node_ids = []
    for step_id in v1_downstream:
        step = v1_step_map.get(step_id)
        if not step:
            continue
        content_hash = compute_node_content_hash(step)
        if content_hash not in v2_hash_to_id:
            removed_node_ids.append(step_id)

    return DownstreamChanges(
        inserted_nodes=inserted_nodes,
        removed_node_ids=removed_node_ids,
        new_forks=new_forks,
        modified_transitions=[],
    )


def _find_downstream_nodes(scenario: Scenario, source_id: UUID) -> set[UUID]:
    """Find all nodes downstream of source using forward BFS."""
    adj, _ = _build_adjacency_list(scenario)

    visited: set[UUID] = set()
    queue = [source_id]
    downstream: set[UUID] = set()

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        for successor in adj.get(current, []):
            if successor not in visited:
                downstream.add(successor)
                queue.append(successor)

    return downstream


def determine_migration_scenario(
    upstream: UpstreamChanges,
    _downstream: DownstreamChanges,
) -> MigrationScenario:
    """Determine the migration scenario based on upstream/downstream changes.

    Args:
        upstream: Changes upstream of the anchor
        _downstream: Changes downstream of the anchor (reserved for future use)

    Returns:
        MigrationScenario indicating how to migrate sessions at this anchor
    """
    has_upstream_forks = len(upstream.new_forks) > 0

    has_upstream_data_collection = any(
        len(node.collects_fields) > 0 for node in upstream.inserted_nodes
    )

    # Re-route: New upstream fork that may redirect customer
    if has_upstream_forks:
        return MigrationScenario.RE_ROUTE

    # Gap fill: New upstream nodes that collect data
    if has_upstream_data_collection:
        return MigrationScenario.GAP_FILL

    # Clean graft: Only downstream changes (or no changes)
    return MigrationScenario.CLEAN_GRAFT


def compute_transformation_map(
    v1: Scenario,
    v2: Scenario,
) -> TransformationMap:
    """Compute complete transformation map between scenario versions.

    Args:
        v1: Old scenario version
        v2: New scenario version

    Returns:
        TransformationMap with all anchors, deleted nodes, and new nodes
    """
    # Find anchor nodes
    anchors_raw = find_anchor_nodes(v1, v2)

    # Compute transformations for each anchor
    anchor_transformations = []
    for v1_step, v2_step, content_hash in anchors_raw:
        upstream = compute_upstream_changes(v1, v2, v1_step.id, v2_step.id)
        downstream = compute_downstream_changes(v1, v2, v1_step.id, v2_step.id)
        migration_scenario = determine_migration_scenario(upstream, downstream)

        anchor_transformations.append(
            AnchorTransformation(
                anchor_content_hash=content_hash,
                anchor_name=v1_step.name,
                anchor_node_id_v1=v1_step.id,
                anchor_node_id_v2=v2_step.id,
                upstream_changes=upstream,
                downstream_changes=downstream,
                migration_scenario=migration_scenario,
            )
        )

    # Find deleted nodes (in V1 but not matching any anchor)
    anchor_hashes = {a.anchor_content_hash for a in anchor_transformations}
    deleted_nodes = []
    for step in v1.steps:
        content_hash = compute_node_content_hash(step)
        if content_hash not in anchor_hashes:
            # Find nearest anchor for relocation suggestion
            nearest_anchor = _find_nearest_anchor(
                step.id, v1, anchor_transformations
            )
            nearest_hash = nearest_anchor.anchor_content_hash if nearest_anchor else None
            nearest_v2_id = nearest_anchor.anchor_node_id_v2 if nearest_anchor else None

            deleted_nodes.append(
                DeletedNode(
                    node_id_v1=step.id,
                    node_name=step.name,
                    nearest_anchor_hash=nearest_hash,
                    nearest_anchor_id_v2=nearest_v2_id,
                )
            )

    # Find new nodes (in V2 but not matching any V1 content hash)
    v1_hashes = {compute_node_content_hash(s) for s in v1.steps}
    new_node_ids = [
        step.id
        for step in v2.steps
        if compute_node_content_hash(step) not in v1_hashes
    ]

    return TransformationMap(
        anchors=anchor_transformations,
        deleted_nodes=deleted_nodes,
        new_node_ids=new_node_ids,
    )


def _find_nearest_anchor(
    step_id: UUID,
    scenario: Scenario,
    anchors: list[AnchorTransformation],
) -> AnchorTransformation | None:
    """Find nearest anchor using BFS from deleted node."""
    if not anchors:
        return None

    anchor_v1_ids = {a.anchor_node_id_v1 for a in anchors}
    adj, _ = _build_adjacency_list(scenario)
    reverse_adj = _build_reverse_adjacency_list(scenario)

    # BFS in both directions to find nearest anchor
    visited: set[UUID] = set()
    queue = [step_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        if current in anchor_v1_ids:
            # Found an anchor
            for anchor in anchors:
                if anchor.anchor_node_id_v1 == current:
                    return anchor

        # Add neighbors (both directions)
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)
        for neighbor in reverse_adj.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)

    # No anchor found, return first anchor as fallback
    return anchors[0] if anchors else None
