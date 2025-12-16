"""DynamoDB implementation of SessionStore.

This is a placeholder for future implementation when AWS-native
session storage is required.

See docs/architecture/stub-files.md for implementation criteria and
docs/design/decisions/003-database-selection.md for requirements:
- Use for AWS-native deployments
- Use when global distribution is needed
- Requires DynamoDB with on-demand capacity
"""


class DynamoDBSessionStore:
    """DynamoDB-backed session store for AWS deployments.

    Future implementation will provide:
    - Single-digit millisecond latency
    - Global tables for multi-region
    - Auto-scaling capacity
    - TTL for session expiration
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "DynamoDBSessionStore not yet implemented. "
            "Use InMemorySessionStore for development or RedisSessionStore for production. "
            "DynamoDB implementation is planned for AWS-native deployments."
        )
