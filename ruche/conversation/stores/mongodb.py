"""MongoDB implementation of SessionStore.

This is a placeholder for future implementation when document-oriented
session storage is preferred.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when flexible session schema is needed
- Use when horizontal scaling is required
- Requires MongoDB 6.0+
"""


class MongoDBSessionStore:
    """MongoDB-backed session store for flexible document storage.

    Future implementation will provide:
    - Document-oriented session storage
    - Flexible schema for session state
    - TTL indexes for session expiration
    - Horizontal scaling via sharding
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "MongoDBSessionStore not yet implemented. "
            "Use InMemorySessionStore for development or RedisSessionStore for production. "
            "MongoDB implementation is planned for flexible session storage."
        )
