# Store Interface Contracts

**Feature**: 009-production-stores-providers
**Date**: 2025-11-29

## Overview

This document defines the interface contracts that PostgreSQL and Redis store implementations must fulfill. All implementations must pass the existing contract tests.

## SessionStore Interface (Redis Implementation)

```python
class SessionStore(ABC):
    """Session storage with two-tier caching support."""

    @abstractmethod
    async def get(self, session_id: UUID) -> Session | None:
        """Get session by ID. Checks hot tier first, then persistent."""

    @abstractmethod
    async def save(self, session: Session) -> UUID:
        """Save session to hot tier. Updates last_activity_at."""

    @abstractmethod
    async def delete(self, session_id: UUID) -> bool:
        """Delete session from all tiers."""

    @abstractmethod
    async def get_by_channel(
        self,
        tenant_id: UUID,
        channel: Channel,
        user_channel_id: str,
    ) -> Session | None:
        """Get session by channel identity."""

    @abstractmethod
    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        status: SessionStatus | None = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for an agent."""

    @abstractmethod
    async def list_by_customer(
        self,
        tenant_id: UUID,
        customer_profile_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for a customer profile."""

    @abstractmethod
    async def find_sessions_by_step_hash(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None,
    ) -> list[Session]:
        """Find sessions at a specific step for migration."""
```

### Redis-Specific Methods (Extension)

```python
class RedisSessionStore(SessionStore):
    """Redis implementation with two-tier caching."""

    async def promote_to_hot(self, session_id: UUID) -> bool:
        """Promote session from persistent to hot tier."""

    async def demote_to_persistent(self, session_id: UUID) -> bool:
        """Demote session from hot to persistent tier."""

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
```

## ConfigStore Interface (PostgreSQL Implementation)

```python
class ConfigStore(ABC):
    """Configuration storage for agents, rules, scenarios, etc."""

    # Rule operations
    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None
    async def get_rules(self, tenant_id: UUID, agent_id: UUID, **filters) -> list[Rule]
    async def save_rule(self, rule: Rule) -> UUID
    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool
    async def vector_search_rules(
        self, query_embedding: list[float], tenant_id: UUID, agent_id: UUID, **kwargs
    ) -> list[tuple[Rule, float]]

    # Scenario operations
    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None
    async def get_scenarios(self, tenant_id: UUID, agent_id: UUID, **filters) -> list[Scenario]
    async def save_scenario(self, scenario: Scenario) -> UUID
    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool

    # Template operations
    async def get_template(self, tenant_id: UUID, template_id: UUID) -> Template | None
    async def get_templates(self, tenant_id: UUID, agent_id: UUID, **filters) -> list[Template]
    async def save_template(self, template: Template) -> UUID
    async def delete_template(self, tenant_id: UUID, template_id: UUID) -> bool

    # Variable operations
    async def get_variable(self, tenant_id: UUID, variable_id: UUID) -> Variable | None
    async def get_variables(self, tenant_id: UUID, agent_id: UUID) -> list[Variable]
    async def get_variable_by_name(self, tenant_id: UUID, agent_id: UUID, name: str) -> Variable | None
    async def save_variable(self, variable: Variable) -> UUID
    async def delete_variable(self, tenant_id: UUID, variable_id: UUID) -> bool

    # Agent operations
    async def get_agent(self, tenant_id: UUID, agent_id: UUID) -> Agent | None
    async def get_agents(self, tenant_id: UUID, **kwargs) -> tuple[list[Agent], int]
    async def save_agent(self, agent: Agent) -> UUID
    async def delete_agent(self, tenant_id: UUID, agent_id: UUID) -> bool

    # Tool activation operations
    async def get_tool_activation(self, tenant_id: UUID, agent_id: UUID, tool_id: str) -> ToolActivation | None
    async def get_tool_activations(self, tenant_id: UUID, agent_id: UUID) -> list[ToolActivation]
    async def save_tool_activation(self, activation: ToolActivation) -> UUID
    async def delete_tool_activation(self, tenant_id: UUID, agent_id: UUID, tool_id: str) -> bool

    # Migration operations
    async def get_migration_plan(self, tenant_id: UUID, plan_id: UUID) -> MigrationPlan | None
    async def get_migration_plan_for_versions(self, tenant_id: UUID, scenario_id: UUID, from_version: int, to_version: int) -> MigrationPlan | None
    async def save_migration_plan(self, plan: MigrationPlan) -> UUID
    async def list_migration_plans(self, tenant_id: UUID, **kwargs) -> list[MigrationPlan]
    async def delete_migration_plan(self, tenant_id: UUID, plan_id: UUID) -> bool
    async def archive_scenario_version(self, tenant_id: UUID, scenario: Scenario) -> None
    async def get_archived_scenario(self, tenant_id: UUID, scenario_id: UUID, version: int) -> Scenario | None
```

## MemoryStore Interface (PostgreSQL Implementation)

```python
class MemoryStore(ABC):
    """Long-term memory storage with vector search."""

    # Episode operations
    async def add_episode(self, episode: Episode) -> UUID
    async def get_episode(self, tenant_id: UUID, episode_id: UUID) -> Episode | None
    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        *,
        customer_profile_id: UUID | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Episode, float]]
    async def text_search_episodes(
        self,
        query: str,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 10,
    ) -> list[Episode]
    async def delete_by_group(self, tenant_id: UUID, group_id: UUID) -> int

    # Entity operations
    async def add_entity(self, entity: Entity) -> UUID
    async def get_entities(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        entity_type: str | None = None,
        customer_profile_id: UUID | None = None,
    ) -> list[Entity]

    # Relationship operations
    async def add_relationship(self, relationship: Relationship) -> UUID
    async def traverse_from_entities(
        self,
        tenant_id: UUID,
        entity_ids: list[UUID],
        *,
        relationship_types: list[str] | None = None,
        max_depth: int = 2,
    ) -> list[Relationship]
```

## AuditStore Interface (PostgreSQL Implementation)

```python
class AuditStore(ABC):
    """Immutable audit log storage."""

    async def save_turn(self, turn: TurnRecord) -> UUID
    async def get_turn(self, tenant_id: UUID, turn_id: UUID) -> TurnRecord | None
    async def list_turns_by_session(
        self,
        tenant_id: UUID,
        session_id: UUID,
        *,
        limit: int = 100,
    ) -> list[TurnRecord]
    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[TurnRecord]
    async def save_event(self, event: AuditEvent) -> UUID
```

## ProfileStore Interface (PostgreSQL Implementation)

```python
class ProfileStore(ABC):
    """Customer profile storage."""

    async def get_by_customer_id(self, tenant_id: UUID, customer_id: UUID) -> CustomerProfile | None
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile | None
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile
    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
    ) -> None
    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
    ) -> UUID
    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_id: UUID,
        target_id: UUID,
    ) -> CustomerProfile
    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> ChannelIdentity
```

## Contract Test Requirements

All store implementations must pass:

1. **CRUD Operations**: Create, read, update, delete for all entity types
2. **Tenant Isolation**: Queries must never return data from other tenants
3. **Soft Delete**: Deleted items must not appear in normal queries
4. **Vector Search**: Similarity search must return correctly ordered results
5. **Pagination**: List operations must respect limit/offset parameters
6. **Concurrent Access**: No data corruption under concurrent writes

## Error Handling Contract

```python
class StoreError(Exception):
    """Base exception for store errors."""

class ConnectionError(StoreError):
    """Raised when store connection fails."""

class NotFoundError(StoreError):
    """Raised when requested entity not found."""

class ConflictError(StoreError):
    """Raised on unique constraint violation."""

class ValidationError(StoreError):
    """Raised on invalid data."""
```

All store methods must:
- Raise `ConnectionError` on infrastructure failures
- Raise `ConflictError` on duplicate key violations
- Never raise generic exceptions (wrap in `StoreError`)
- Log errors with structured context before raising
