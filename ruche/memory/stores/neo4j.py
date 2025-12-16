"""Neo4j implementation of MemoryStore.

This is a placeholder for future implementation when graph traversal
performance becomes a bottleneck (>200ms for depth-2 traversals).

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when graph traversals exceed 200ms in PostgreSQL
- Use when depth > 3 traversals are required
- Requires Neo4j 5.0+ with vector search capabilities
"""

from ruche.memory.stores import MemoryStore


class Neo4jMemoryStore(MemoryStore):
    """Neo4j-backed memory store for high-performance graph operations.

    Future implementation will provide:
    - Native graph traversal for entities and relationships
    - Vector similarity search via Neo4j vector index
    - Cypher queries for complex graph patterns
    - Transaction support for consistency
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "Neo4jMemoryStore not yet implemented. "
            "Use InMemoryMemoryStore for development or PostgreSQL for production. "
            "Neo4j implementation is planned for when graph traversals exceed 200ms."
        )
