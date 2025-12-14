"""Bulk operation models for batch CRUD operations."""

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class BulkOperation(BaseModel, Generic[T]):
    """Single operation in a bulk request.

    Represents one create, update, or delete operation to be
    executed as part of a bulk request.
    """

    action: Literal["create", "update", "delete"] = Field(
        ..., description="Operation type"
    )

    id: UUID | None = Field(
        default=None, description="Entity ID (required for update/delete)"
    )

    data: T | None = Field(
        default=None, description="Entity data (required for create/update)"
    )


class BulkRequest(BaseModel, Generic[T]):
    """Request for bulk operations.

    Contains a list of operations to execute in order.
    Operations are processed individually - failure of one
    does not prevent others from executing.

    Example:
        {
            "operations": [
                {"action": "create", "data": {"name": "Rule 1", ...}},
                {"action": "update", "id": "...", "data": {"priority": 10}},
                {"action": "delete", "id": "..."}
            ]
        }
    """

    operations: list[BulkOperation[T]] = Field(
        ..., max_length=50, description="List of operations (max 50)"
    )


class BulkResult(BaseModel, Generic[T]):
    """Result of a single bulk operation.

    Reports success or failure for each operation in the batch.
    """

    index: int = Field(..., description="Index of operation in request")

    success: bool = Field(..., description="Whether the operation succeeded")

    data: T | None = Field(
        default=None, description="Created/updated entity data on success"
    )

    error: str | None = Field(
        default=None, description="Error message if operation failed"
    )


class BulkResponse(BaseModel, Generic[T]):
    """Response from a bulk operation request.

    Contains individual results for each operation in the order
    they were submitted. Some operations may succeed while others fail.

    Example:
        {
            "results": [
                {"index": 0, "success": true, "data": {...}},
                {"index": 1, "success": false, "error": "Not found"}
            ],
            "successful": 1,
            "failed": 1
        }
    """

    results: list[BulkResult[T]] = Field(..., description="Results for each operation")

    successful: int = Field(..., description="Count of successful operations")

    failed: int = Field(..., description="Count of failed operations")
