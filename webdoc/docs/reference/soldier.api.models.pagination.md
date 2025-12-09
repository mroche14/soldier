<a id="focal.api.models.pagination"></a>

# focal.api.models.pagination

Pagination models for list endpoints.

<a id="focal.api.models.pagination.PaginationParams"></a>

## PaginationParams Objects

```python
class PaginationParams(BaseModel)
```

Pagination parameters for list requests.

<a id="focal.api.models.pagination.PaginatedResponse"></a>

## PaginatedResponse Objects

```python
class PaginatedResponse(BaseModel, Generic[T])
```

Paginated response wrapper for list endpoints.

**Example**:

  {
- `"items"` - [...],
- `"total"` - 100,
- `"limit"` - 20,
- `"offset"` - 0,
- `"has_more"` - true
  }

<a id="focal.api.models.pagination.PaginatedResponse.items"></a>

#### items

List of items for this page.

<a id="focal.api.models.pagination.PaginatedResponse.create"></a>

#### create

```python
@classmethod
def create(cls, items: list[T], total: int, limit: int,
           offset: int) -> "PaginatedResponse[T]"
```

Create a paginated response with has_more computed automatically.

