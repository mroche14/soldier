<a id="soldier.api.models.bulk"></a>

# soldier.api.models.bulk

Bulk operation models for batch CRUD operations.

<a id="soldier.api.models.bulk.BulkOperation"></a>

## BulkOperation Objects

```python
class BulkOperation(BaseModel, Generic[T])
```

Single operation in a bulk request.

Represents one create, update, or delete operation to be
executed as part of a bulk request.

<a id="soldier.api.models.bulk.BulkRequest"></a>

## BulkRequest Objects

```python
class BulkRequest(BaseModel, Generic[T])
```

Request for bulk operations.

Contains a list of operations to execute in order.
Operations are processed individually - failure of one
does not prevent others from executing.

**Example**:

  {
- `"operations"` - [
- `{"action"` - "create", "data": {"name": "Rule 1", ...}},
- `{"action"` - "update", "id": "...", "data": {"priority": 10}},
- `{"action"` - "delete", "id": "..."}
  ]
  }

<a id="soldier.api.models.bulk.BulkResult"></a>

## BulkResult Objects

```python
class BulkResult(BaseModel, Generic[T])
```

Result of a single bulk operation.

Reports success or failure for each operation in the batch.

<a id="soldier.api.models.bulk.BulkResponse"></a>

## BulkResponse Objects

```python
class BulkResponse(BaseModel, Generic[T])
```

Response from a bulk operation request.

Contains individual results for each operation in the order
they were submitted. Some operations may succeed while others fail.

**Example**:

  {
- `"results"` - [
- `{"index"` - 0, "success": true, "data": {...}},
- `{"index"` - 1, "success": false, "error": "Not found"}
  ],
- `"successful"` - 1,
- `"failed"` - 1
  }

