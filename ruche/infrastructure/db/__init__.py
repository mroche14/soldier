"""Database utilities for Focal.

This module contains:
- Connection pool management
- Store error hierarchy
- Alembic migrations
"""

from ruche.infrastructure.db.errors import (
    ConflictError,
    ConnectionError,
    NotFoundError,
    StoreError,
    ValidationError,
)

__all__ = [
    "StoreError",
    "ConnectionError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
]
