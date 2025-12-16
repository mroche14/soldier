"""TimescaleDB implementation of AuditStore.

This is a placeholder for future implementation when time-series
optimization is required for audit data.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use when time-series queries are primary access pattern
- Use when data retention policies are complex
- Requires TimescaleDB 2.0+
"""


class TimescaleAuditStore:
    """TimescaleDB-backed audit store for time-series optimization.

    Future implementation will provide:
    - Automatic time-based partitioning (hypertables)
    - Built-in data retention policies
    - Continuous aggregates for dashboards
    - Compression for older data
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "TimescaleAuditStore not yet implemented. "
            "Use InMemoryAuditStore for development or PostgresAuditStore for production. "
            "TimescaleDB implementation is planned for time-series optimization."
        )
