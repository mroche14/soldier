"""Pagination models for list endpoints."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list requests."""

    limit: int = Field(default=20, ge=1, le=100, description="Maximum items per page")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")
    sort: str | None = Field(
        default=None,
        description="Sort field and direction (e.g., 'name:asc', 'created_at:desc')",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper for list endpoints.

    Example:
        {
            "items": [...],
            "total": 100,
            "limit": 20,
            "offset": 0,
            "has_more": true
        }
    """

    items: list[T]
    """List of items for this page."""

    total: int = Field(..., ge=0, description="Total number of items across all pages")

    limit: int = Field(..., ge=1, description="Number of items requested per page")

    offset: int = Field(..., ge=0, description="Number of items skipped")

    has_more: bool = Field(
        default=False, description="Whether there are more items after this page"
    )

    @classmethod
    def create(
        cls, items: list[T], total: int, limit: int, offset: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response with has_more computed automatically."""
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(items)) < total,
        )
