"""MongoDB implementation of AuditStore.

This is a placeholder for future implementation when document-oriented
storage is preferred for audit data.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when flexible schema is needed for audit events
- Use when horizontal scaling is required
- Requires MongoDB 6.0+
"""


class MongoAuditStore:
    """MongoDB-backed audit store for flexible document storage.

    Future implementation will provide:
    - Document-oriented storage for audit events
    - Flexible schema for varying event types
    - TTL indexes for automatic data expiration
    - Horizontal scaling via sharding
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "MongoAuditStore not yet implemented. "
            "Use InMemoryAuditStore for development or PostgresAuditStore for production. "
            "MongoDB implementation is planned for flexible audit event storage."
        )
