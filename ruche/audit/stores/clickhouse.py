"""ClickHouse implementation of AuditStore.

This is a placeholder for future implementation when high-volume
analytics queries are required on audit data.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when audit queries exceed 1M rows
- Use when real-time analytics are required
- Requires ClickHouse 23.0+
"""


class ClickHouseAuditStore:
    """ClickHouse-backed audit store for high-volume analytics.

    Future implementation will provide:
    - Columnar storage for efficient analytics
    - Real-time aggregation queries
    - Time-series partitioning for audit data
    - High-throughput ingestion
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "ClickHouseAuditStore not yet implemented. "
            "Use InMemoryAuditStore for development or PostgresAuditStore for production. "
            "ClickHouse implementation is planned for high-volume analytics requirements."
        )
