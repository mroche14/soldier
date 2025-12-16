"""MongoDB implementation of MemoryStore.

This is a placeholder for future implementation when document-oriented
storage is preferred over PostgreSQL for memory operations.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when flexible schema is preferred over relational
- Use when horizontal scaling is required
- Requires MongoDB 6.0+ with Atlas Vector Search
"""

from ruche.memory.stores import MemoryStore


class MongoDBMemoryStore(MemoryStore):
    """MongoDB-backed memory store for flexible document storage.

    Future implementation will provide:
    - Document-oriented storage for episodes and entities
    - Atlas Vector Search for similarity queries
    - Flexible schema for evolving data models
    - Horizontal scaling via sharding
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "MongoDBMemoryStore not yet implemented. "
            "Use InMemoryMemoryStore for development or PostgresMemoryStore for production. "
            "MongoDB implementation is planned for horizontal scaling requirements."
        )
