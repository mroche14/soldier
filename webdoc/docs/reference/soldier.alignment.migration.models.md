<a id="focal.alignment.migration.models"></a>

# focal.alignment.migration.models

Migration models for scenario version transitions.

Defines MigrationPlan, TransformationMap, and related entities for
anchor-based migration between scenario versions.

<a id="focal.alignment.migration.models.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="focal.alignment.migration.models.MigrationPlanStatus"></a>

## MigrationPlanStatus Objects

```python
class MigrationPlanStatus(str, Enum)
```

Migration plan lifecycle status.

<a id="focal.alignment.migration.models.MigrationScenario"></a>

## MigrationScenario Objects

```python
class MigrationScenario(str, Enum)
```

Type of migration to apply at an anchor.

<a id="focal.alignment.migration.models.InsertedNode"></a>

## InsertedNode Objects

```python
class InsertedNode(BaseModel)
```

A node inserted between V1 and V2.

<a id="focal.alignment.migration.models.ForkBranch"></a>

## ForkBranch Objects

```python
class ForkBranch(BaseModel)
```

One branch of a fork.

<a id="focal.alignment.migration.models.NewFork"></a>

## NewFork Objects

```python
class NewFork(BaseModel)
```

A new fork (branching point) added in V2.

<a id="focal.alignment.migration.models.DeletedNode"></a>

## DeletedNode Objects

```python
class DeletedNode(BaseModel)
```

A node that existed in V1 but not in V2.

<a id="focal.alignment.migration.models.TransitionChange"></a>

## TransitionChange Objects

```python
class TransitionChange(BaseModel)
```

A modified transition between versions.

<a id="focal.alignment.migration.models.UpstreamChanges"></a>

## UpstreamChanges Objects

```python
class UpstreamChanges(BaseModel)
```

Changes upstream of an anchor (customer already passed through).

<a id="focal.alignment.migration.models.DownstreamChanges"></a>

## DownstreamChanges Objects

```python
class DownstreamChanges(BaseModel)
```

Changes downstream of an anchor (customer will encounter).

<a id="focal.alignment.migration.models.AnchorTransformation"></a>

## AnchorTransformation Objects

```python
class AnchorTransformation(BaseModel)
```

Changes around an anchor node between V1 and V2.

<a id="focal.alignment.migration.models.TransformationMap"></a>

## TransformationMap Objects

```python
class TransformationMap(BaseModel)
```

Complete analysis of changes between scenario versions.

<a id="focal.alignment.migration.models.TransformationMap.get_anchor_by_hash"></a>

#### get\_anchor\_by\_hash

```python
def get_anchor_by_hash(content_hash: str) -> AnchorTransformation | None
```

Find anchor transformation by content hash.

<a id="focal.alignment.migration.models.ScopeFilter"></a>

## ScopeFilter Objects

```python
class ScopeFilter(BaseModel)
```

Filter for which sessions are eligible for migration.

<a id="focal.alignment.migration.models.AnchorMigrationPolicy"></a>

## AnchorMigrationPolicy Objects

```python
class AnchorMigrationPolicy(BaseModel)
```

Migration policy for a specific anchor node.

<a id="focal.alignment.migration.models.MigrationWarning"></a>

## MigrationWarning Objects

```python
class MigrationWarning(BaseModel)
```

Warning for operator attention.

<a id="focal.alignment.migration.models.FieldCollectionInfo"></a>

## FieldCollectionInfo Objects

```python
class FieldCollectionInfo(BaseModel)
```

Information about a field that needs collection.

<a id="focal.alignment.migration.models.MigrationSummary"></a>

## MigrationSummary Objects

```python
class MigrationSummary(BaseModel)
```

Summary of migration plan for operator review.

<a id="focal.alignment.migration.models.MigrationPlan"></a>

## MigrationPlan Objects

```python
class MigrationPlan(BaseModel)
```

Pre-computed migration plan for scenario version transition.

<a id="focal.alignment.migration.models.ReconciliationAction"></a>

## ReconciliationAction Objects

```python
class ReconciliationAction(str, Enum)
```

Action to take after reconciliation.

<a id="focal.alignment.migration.models.ReconciliationResult"></a>

## ReconciliationResult Objects

```python
class ReconciliationResult(BaseModel)
```

Result of pre-turn reconciliation.

<a id="focal.alignment.migration.models.GapFillSource"></a>

## GapFillSource Objects

```python
class GapFillSource(str, Enum)
```

Source of gap-filled data.

<a id="focal.alignment.migration.models.GapFillResult"></a>

## GapFillResult Objects

```python
class GapFillResult(BaseModel)
```

Result of gap fill attempt.

<a id="focal.alignment.migration.models.CheckpointInfo"></a>

## CheckpointInfo Objects

```python
class CheckpointInfo(BaseModel)
```

Information about a passed checkpoint.

