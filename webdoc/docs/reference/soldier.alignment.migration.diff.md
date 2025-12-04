<a id="soldier.alignment.migration.diff"></a>

# soldier.alignment.migration.diff

Graph diff and content hashing for scenario migration.

Implements anchor detection, upstream/downstream analysis, and
transformation map computation for migration plan generation.

<a id="soldier.alignment.migration.diff.compute_node_content_hash"></a>

#### compute\_node\_content\_hash

```python
def compute_node_content_hash(step: ScenarioStep) -> str
```

Compute semantic content hash for anchor identification.

Uses SHA-256 of JSON-serialized semantic attributes, truncated to 16 chars.

**Arguments**:

- `step` - Scenario step to hash
  

**Returns**:

  16-character hex hash string

<a id="soldier.alignment.migration.diff.compute_scenario_checksum"></a>

#### compute\_scenario\_checksum

```python
def compute_scenario_checksum(scenario: Scenario) -> str
```

Compute checksum for entire scenario for version validation.

**Arguments**:

- `scenario` - Scenario to compute checksum for
  

**Returns**:

  16-character hex hash string

<a id="soldier.alignment.migration.diff.find_anchor_nodes"></a>

#### find\_anchor\_nodes

```python
def find_anchor_nodes(
        v1: Scenario,
        v2: Scenario) -> list[tuple[ScenarioStep, ScenarioStep, str]]
```

Find anchor nodes that exist in both versions with same semantic content.

**Arguments**:

- `v1` - Old scenario version
- `v2` - New scenario version
  

**Returns**:

  List of (v1_step, v2_step, content_hash) tuples for matching anchors

<a id="soldier.alignment.migration.diff.compute_upstream_changes"></a>

#### compute\_upstream\_changes

```python
def compute_upstream_changes(v1: Scenario, v2: Scenario, anchor_id_v1: UUID,
                             anchor_id_v2: UUID) -> UpstreamChanges
```

Compute changes upstream of an anchor using reverse BFS.

**Arguments**:

- `v1` - Old scenario version
- `v2` - New scenario version
- `anchor_id_v1` - Anchor step ID in V1
- `anchor_id_v2` - Anchor step ID in V2
  

**Returns**:

  UpstreamChanges describing what changed upstream of the anchor

<a id="soldier.alignment.migration.diff.compute_downstream_changes"></a>

#### compute\_downstream\_changes

```python
def compute_downstream_changes(v1: Scenario, v2: Scenario, anchor_id_v1: UUID,
                               anchor_id_v2: UUID) -> DownstreamChanges
```

Compute changes downstream of an anchor using forward BFS.

**Arguments**:

- `v1` - Old scenario version
- `v2` - New scenario version
- `anchor_id_v1` - Anchor step ID in V1
- `anchor_id_v2` - Anchor step ID in V2
  

**Returns**:

  DownstreamChanges describing what changed downstream of the anchor

<a id="soldier.alignment.migration.diff.determine_migration_scenario"></a>

#### determine\_migration\_scenario

```python
def determine_migration_scenario(
        upstream: UpstreamChanges,
        _downstream: DownstreamChanges) -> MigrationScenario
```

Determine the migration scenario based on upstream/downstream changes.

**Arguments**:

- `upstream` - Changes upstream of the anchor
- `_downstream` - Changes downstream of the anchor (reserved for future use)
  

**Returns**:

  MigrationScenario indicating how to migrate sessions at this anchor

<a id="soldier.alignment.migration.diff.compute_transformation_map"></a>

#### compute\_transformation\_map

```python
def compute_transformation_map(v1: Scenario,
                               v2: Scenario) -> TransformationMap
```

Compute complete transformation map between scenario versions.

**Arguments**:

- `v1` - Old scenario version
- `v2` - New scenario version
  

**Returns**:

  TransformationMap with all anchors, deleted nodes, and new nodes

