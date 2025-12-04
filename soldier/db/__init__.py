"""Database utilities for Soldier.

This module contains:
- Connection pool management
- Store error hierarchy
- Alembic migrations
"""

from soldier.db.errors import (
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
