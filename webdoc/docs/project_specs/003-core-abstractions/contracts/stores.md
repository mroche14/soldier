# Store Interface Contracts

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This document defines the abstract interfaces for all storage backends. Each interface is implemented as a Python ABC (Abstract Base Class). All methods are async.

---

## ConfigStore

Storage for agent configuration: rules, scenarios, templates, variables.

### Interface

```python
class ConfigStore(ABC):
    """Source of truth for agent behavior configuration."""

    # ─── Rules ───────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_rules(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
        enabled_only: bool = True,
    ) -> list[Rule]:
        """Get rules for an agent, optionally filtered by scope."""

    @abstractmethod
    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None:
        """Get a single rule by ID."""

    @abstractmethod
    async def save_rule(self, rule: Rule) -> UUID:
        """Create or update a rule. Returns rule ID."""

    @abstractmethod
    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool:
        """Soft delete a rule. Returns True if existed."""

    @abstractmethod
    async def vector_search_rules(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
        limit: int = 10,
    ) -> list[tuple[Rule, float]]:
        """Find rules by vector similarity using cosine similarity.

        Returns (rule, score) pairs ordered by score descending.
        Score range: -1.0 to 1.0 (cosine similarity).
        """

    # ─── Scenarios ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_scenarios(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        enabled_only: bool = True,
    ) -> list[Scenario]:
        """Get all scenarios for an agent."""

    @abstractmethod
    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        """Get a scenario with its steps."""

    @abstractmethod
    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Create or update a scenario."""

    @abstractmethod
    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool:
        """Soft delete a scenario."""

    # ─── Templates ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_templates(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        scope: Scope | None = None,
        scope_id: UUID | None = None,
    ) -> list[Template]:
        """Get templates for an agent."""

    @abstractmethod
    async def get_template(self, tenant_id: UUID, template_id: UUID) -> Template | None:
        """Get a single template by ID."""

    @abstractmethod
    async def save_template(self, template: Template) -> UUID:
        """Create or update a template."""

    @abstractmethod
    async def delete_template(self, tenant_id: UUID, template_id: UUID) -> bool:
        """Soft delete a template."""

    # ─── Variables ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_variables(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Variable]:
        """Get variable definitions for an agent."""

    @abstractmethod
    async def get_variable(self, tenant_id: UUID, variable_id: UUID) -> Variable | None:
        """Get a single variable by ID."""

    @abstractmethod
    async def save_variable(self, variable: Variable) -> UUID:
        """Create or update a variable."""

    # ─── Agent Config ────────────────────────────────────────────────────────

    @abstractmethod
    async def get_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> Agent | None:
        """Get agent configuration."""

    @abstractmethod
    async def save_agent(self, agent: Agent) -> UUID:
        """Create or update agent configuration."""
```

### Contract Tests

| Test | Precondition | Action | Expected |
|------|--------------|--------|----------|
| `test_save_and_get_rule` | Empty store | Save rule, get by ID | Retrieved rule equals saved |
| `test_get_rules_by_scope` | Rules with different scopes | Get with scope filter | Only matching scope returned |
| `test_tenant_isolation_rules` | Rules for tenants A and B | Get for tenant A | Only tenant A rules |
| `test_vector_search_rules` | Rules with embeddings | Search with query vector | Ordered by similarity |
| `test_soft_delete_rule` | Saved rule | Delete rule | deleted_at set, not in queries |
| `test_save_and_get_scenario` | Empty store | Save scenario with steps | Full scenario retrieved |
| `test_save_and_get_template` | Empty store | Save template | Template retrieved |
| `test_save_and_get_variable` | Empty store | Save variable | Variable retrieved |

---

## MemoryStore

Storage for long-term memory: episodes, entities, relationships.

### Interface

```python
class MemoryStore(ABC):
    """Agent's knowledge graph - what it remembers from conversations."""

    # ─── Episodes ────────────────────────────────────────────────────────────

    @abstractmethod
    async def add_episode(self, episode: Episode) -> UUID:
        """Store an episode. Returns episode ID."""

    @abstractmethod
    async def get_episode(self, episode_id: UUID) -> Episode | None:
        """Get an episode by ID."""

    @abstractmethod
    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        group_id: str,
        limit: int = 10,
    ) -> list[tuple[Episode, float]]:
        """Find episodes by vector similarity using cosine similarity.

        Returns (episode, score) pairs ordered by score descending.
        Score range: -1.0 to 1.0 (cosine similarity per spec clarification).
        """

    @abstractmethod
    async def text_search_episodes(
        self,
        query: str,
        group_id: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Find episodes by full-text search (BM25 or substring)."""

    # ─── Entities ────────────────────────────────────────────────────────────

    @abstractmethod
    async def add_entity(self, entity: Entity) -> UUID:
        """Store an entity node. Returns entity ID."""

    @abstractmethod
    async def get_entity(self, entity_id: UUID) -> Entity | None:
        """Get an entity by ID."""

    @abstractmethod
    async def get_entities(
        self,
        group_id: str,
        entity_type: str | None = None,
    ) -> list[Entity]:
        """Get entities in a group, optionally filtered by type."""

    # ─── Relationships ───────────────────────────────────────────────────────

    @abstractmethod
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Store a relationship between entities. Returns relationship ID."""

    @abstractmethod
    async def get_relationships(
        self,
        group_id: str,
        entity_id: UUID | None = None,
        relation_type: str | None = None,
    ) -> list[Relationship]:
        """Get relationships, optionally filtered."""

    @abstractmethod
    async def traverse_from_entities(
        self,
        entity_ids: list[UUID],
        group_id: str,
        depth: int = 2,
    ) -> list[dict]:
        """Traverse graph from entities to find related context."""

    # ─── Cleanup ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all data for a group. Returns count deleted."""
```

### Contract Tests

| Test | Precondition | Action | Expected |
|------|--------------|--------|----------|
| `test_add_and_get_episode` | Empty store | Add episode, get by ID | Episode retrieved |
| `test_vector_search_episodes` | Episodes with embeddings | Search with query | Ordered by similarity |
| `test_text_search_episodes` | Episodes with content | Text search | Matching episodes returned |
| `test_group_isolation_episodes` | Episodes in groups A and B | Search in group A | Only group A episodes |
| `test_add_and_get_entity` | Empty store | Add entity, get by ID | Entity retrieved |
| `test_get_entities_by_type` | Entities of different types | Get by type | Only matching type |
| `test_add_relationship` | Two entities | Add relationship | Relationship stored |
| `test_traverse_from_entities` | Entity graph | Traverse depth 2 | Related entities found |
| `test_delete_by_group` | Data in group | Delete group | All data removed, count returned |

---

## SessionStore

Two-tier storage for conversation state.

### Interface

```python
class SessionStore(ABC):
    """Runtime state for active conversations."""

    @abstractmethod
    async def get(self, session_id: UUID) -> Session | None:
        """Get session by ID."""

    @abstractmethod
    async def get_by_channel(
        self,
        tenant_id: UUID,
        channel: Channel,
        user_channel_id: str,
    ) -> Session | None:
        """Get session by channel identity."""

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save session state."""

    @abstractmethod
    async def delete(self, session_id: UUID) -> bool:
        """Delete session. Returns True if existed."""

    @abstractmethod
    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: SessionStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Session]:
        """List sessions for an agent."""

    @abstractmethod
    async def list_by_customer(
        self,
        tenant_id: UUID,
        customer_profile_id: UUID,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for a customer profile."""
```

### Contract Tests

| Test | Precondition | Action | Expected |
|------|--------------|--------|----------|
| `test_save_and_get` | Empty store | Save session, get by ID | Session retrieved |
| `test_get_by_channel` | Saved session | Get by channel identity | Session found |
| `test_update_session` | Existing session | Modify and save | Changes persisted |
| `test_delete_session` | Existing session | Delete | Not retrievable |
| `test_list_by_agent` | Multiple sessions | List by agent | Correct sessions returned |
| `test_list_by_status` | Sessions with statuses | List with status filter | Only matching status |
| `test_list_by_customer` | Sessions for customer | List by profile ID | Customer's sessions |

---

## AuditStore

Append-only storage for audit trail.

### Interface

```python
class AuditStore(ABC):
    """Immutable audit trail - what happened."""

    @abstractmethod
    async def save_turn(self, turn: TurnRecord) -> None:
        """Save a turn record."""

    @abstractmethod
    async def get_turn(self, turn_id: UUID) -> TurnRecord | None:
        """Get a turn by ID."""

    @abstractmethod
    async def list_turns_by_session(
        self,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turns for a session in chronological order."""

    @abstractmethod
    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        agent_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turns for a tenant with optional filters."""

    @abstractmethod
    async def save_event(self, event: AuditEvent) -> None:
        """Save an audit event."""

    @abstractmethod
    async def list_events(
        self,
        tenant_id: UUID,
        event_type: str | None = None,
        session_id: UUID | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """List audit events with filters."""
```

### Contract Tests

| Test | Precondition | Action | Expected |
|------|--------------|--------|----------|
| `test_save_and_get_turn` | Empty store | Save turn, get by ID | Turn retrieved |
| `test_list_turns_by_session` | Multiple turns | List by session | Chronological order |
| `test_list_turns_by_tenant` | Turns for tenants | List by tenant | Only tenant's turns |
| `test_list_turns_time_range` | Turns over time | List with time filter | Only in range |
| `test_save_and_list_events` | Empty store | Save events, list | Events retrieved |
| `test_list_events_by_type` | Events of types | List by type | Only matching type |
| `test_immutability` | Saved turn | Attempt modify | Operation not supported |

---

## ProfileStore

Storage for customer profiles.

### Interface

```python
class ProfileStore(ABC):
    """Persistent customer profile storage."""

    @abstractmethod
    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
    ) -> CustomerProfile | None:
        """Get profile by customer ID."""

    @abstractmethod
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile | None:
        """Find profile by channel identity."""

    @abstractmethod
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile:
        """Get existing or create new profile for channel identity."""

    @abstractmethod
    async def save(self, profile: CustomerProfile) -> UUID:
        """Save profile. Returns profile ID."""

    @abstractmethod
    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
    ) -> None:
        """Update a single profile field."""

    @abstractmethod
    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
    ) -> UUID:
        """Attach an asset to the profile. Returns asset ID."""

    @abstractmethod
    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        channel_identity: ChannelIdentity,
    ) -> None:
        """Link a new channel identity to an existing profile."""

    @abstractmethod
    async def merge_profiles(
        self,
        tenant_id: UUID,
        primary_id: UUID,
        secondary_id: UUID,
    ) -> CustomerProfile:
        """Merge two profiles. Returns merged profile."""
```

### Contract Tests

| Test | Precondition | Action | Expected |
|------|--------------|--------|----------|
| `test_get_or_create_new` | Empty store | Get or create | New profile created |
| `test_get_or_create_existing` | Existing profile | Get or create same channel | Existing returned |
| `test_get_by_channel_identity` | Profile with channel | Get by channel | Profile found |
| `test_update_field` | Existing profile | Update field | Field updated |
| `test_add_asset` | Existing profile | Add asset | Asset attached |
| `test_link_channel` | Existing profile | Link new channel | Channel added |
| `test_merge_profiles` | Two profiles | Merge | Fields combined |
| `test_tenant_isolation` | Profiles for A and B | Get for A | Only A's profiles |
