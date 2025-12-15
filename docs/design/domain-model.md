# Domain Model

Python models for Focal's core entities using Pydantic. All models are designed for multi-tenancy and cache-friendly serialization.

## Design Principles

- **`tenant_id` everywhere**: Every entity has explicit tenant ownership
- **`agent_id` for config**: Configuration entities scoped to agent
- **`group_id` for memory**: Memory entities use composite key `{tenant_id}:{session_id}`
- **Timestamps**: `created_at`, `updated_at` on mutable entities
- **Soft delete**: `deleted_at` instead of hard deletes for audit
- **Embeddings**: Precomputed vectors stored alongside text

## Enums

```python
from enum import Enum

class Scope(str, Enum):
    """Rule and Template scoping levels."""
    GLOBAL = "global"      # Always evaluated
    SCENARIO = "scenario"  # Only when scenario is active
    STEP = "step"          # Only when in specific step

class TemplateMode(str, Enum):
    """How templates are used in response generation."""
    SUGGEST = "suggest"       # LLM can adapt the text
    EXCLUSIVE = "exclusive"   # Use exactly, bypass LLM entirely
    FALLBACK = "fallback"     # Use if LLM fails or violates rules

class VariableUpdatePolicy(str, Enum):
    """When to refresh variable values."""
    ON_EACH_TURN = "on_each_turn"
    ON_DEMAND = "on_demand"
    ON_SCENARIO_ENTRY = "on_scenario_entry"
    ON_SESSION_START = "on_session_start"

class Channel(str, Enum):
    """Communication channels."""
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBCHAT = "webchat"
    EMAIL = "email"
    VOICE = "voice"
    API = "api"

class SessionStatus(str, Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    IDLE = "idle"
    PROCESSING = "processing"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"
```

## Base Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4


class TenantScopedModel(BaseModel):
    """Base for all tenant-scoped entities."""
    tenant_id: UUID = Field(description="Owning tenant")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None  # Soft delete


class AgentScopedModel(TenantScopedModel):
    """Base for entities scoped to an agent."""
    agent_id: UUID = Field(description="Owning agent")
```

---

## Configuration Entities

### Agent

```python
class AgentSettings(BaseModel):
    """Agent-level configuration."""
    model: str = "openrouter/anthropic/claude-3-5-sonnet"
    temperature: float = 0.7
    max_tokens: int = 4096


class Agent(TenantScopedModel):
    """Top-level container for an AI agent."""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None

    # Base system prompt
    system_prompt: str | None = None

    # Versioning
    current_version: int = 0  # Last published version
    draft_version: int = 0    # Current working version

    # Brain routing (FOCAL 360 Agent Runtime)
    pipeline_type: str = "focal"  # "focal", "langgraph", "agno"
    pipeline_config: Dict[str, Any] = Field(default_factory=dict)

    # Configuration
    settings: AgentSettings = Field(default_factory=AgentSettings)
    enabled: bool = True

    class Config:
        # Redis cache key pattern
        cache_key_pattern = "{tenant_id}:{agent_id}"
```

### Scenario

```python
class Scenario(AgentScopedModel):
    """A multi-step conversational flow.

    Stored via ConfigStore interface.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None

    # Structure
    entry_step_id: UUID
    steps: List["ScenarioStep"] = []

    # Entry condition (for automatic activation)
    entry_condition_text: Optional[str] = None
    entry_condition_embedding: Optional[List[float]] = None

    # Versioning (for detecting edits during active sessions)
    version: int = 1                      # Incremented on each edit
    content_hash: Optional[str] = None    # SHA256 of serialized steps/transitions

    # Metadata
    tags: List[str] = []
    enabled: bool = True

    class Config:
        cache_key_pattern = "{tenant_id}:{agent_id}:scenarios"
        cache_ttl_seconds = 3600  # 1 hour


class StepTransition(BaseModel):
    """A possible transition between steps."""
    to_step_id: UUID
    condition_text: str  # Natural language: "Interlocutor provides order ID"
    condition_embedding: Optional[List[float]] = None
    priority: int = 0    # Higher priority evaluated first
    condition_fields: List[str] = []  # Profile fields used in condition evaluation


class ScenarioStep(BaseModel):
    """A single step within a Scenario."""
    id: UUID = Field(default_factory=uuid4)
    scenario_id: UUID
    name: str
    description: Optional[str] = None

    # Transitions to other steps
    transitions: List[StepTransition] = []

    # Step-scoped attachments
    template_ids: List[UUID] = []
    rule_ids: List[UUID] = []
    tool_ids: List[str] = []  # Tool IDs are strings (from ToolHub)

    # Flow markers
    is_entry: bool = False
    is_terminal: bool = False
    can_skip: bool = False  # Allow jumping past this step

    # Re-localization flags (see alignment-engine.md for details)
    reachable_from_anywhere: bool = False  # Can relocalize here from any step
    # Useful for "help", "start over", or recovery steps

    # Data collection (see scenario-update-methods.md for reconciliation)
    collects_profile_fields: List[str] = []  # Fields this step collects from user

    # Actions
    performs_action: bool = False       # Does this step perform a side effect?
    is_required_action: bool = False    # Must execute even if interlocutor skipped past

    # Checkpoints (irreversible actions - see scenario-update-methods.md)
    is_checkpoint: bool = False         # Once passed, can't teleport back
    checkpoint_description: Optional[str] = None  # "Order placed", "Payment processed"
```

### Rule

```python
class Rule(AgentScopedModel):
    """A behavioral policy: when X, then Y.

    Stored via ConfigStore interface. Implementations:
    - PostgresConfigStore (pgvector for embeddings)
    - MongoDBConfigStore (Atlas vector search)
    - MySQLConfigStore (external vector store)
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None

    # Condition and action (natural language)
    condition_text: str = Field(
        min_length=1,
        description="When this condition is true (e.g., 'user asks about refunds')"
    )
    action_text: str = Field(
        min_length=1,
        description="Do this action (e.g., 'check order status before answering')"
    )

    # Scoping
    scope: Scope = Scope.GLOBAL
    scope_id: Optional[UUID] = None  # scenario_id or step_id when scoped

    # Priority and activation
    priority: int = Field(default=0, ge=-100, le=100, description="Higher wins in conflicts")
    enabled: bool = True
    max_fires_per_session: int = Field(default=0, ge=0, description="0 = unlimited")
    cooldown_turns: int = Field(default=0, ge=0, description="Min turns between re-fire")

    # Enforcement
    is_hard_constraint: bool = False  # If True, must be satisfied or fallback

    # Attachments
    attached_tool_ids: List[str] = []       # Tool IDs from ToolHub
    attached_template_ids: List[UUID] = []

    # Precomputed embedding for matching
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None   # Track which model generated it

    class Config:
        cache_key_pattern = "{tenant_id}:{agent_id}:rules"
        cache_ttl_seconds = 3600
```

### Template

```python
class Template(AgentScopedModel):
    """Pre-written response text for critical points.

    Stored via ConfigStore interface.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)

    # Content with variable placeholders
    text: str = Field(
        min_length=1,
        description="Template text with placeholders like {user_name}, {order_id}"
    )

    # Behavior
    mode: TemplateMode = TemplateMode.SUGGEST

    # Scoping
    scope: Scope = Scope.GLOBAL
    scope_id: Optional[UUID] = None

    # Conditions for when to use (simple expression)
    conditions: Optional[str] = None  # e.g., "issue_type == 'refund'"

    class Config:
        cache_key_pattern = "{tenant_id}:{agent_id}:templates"
        cache_ttl_seconds = 3600

    def render(self, variables: Dict[str, Any]) -> str:
        """Render template with variable substitution."""
        result = self.text
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    @property
    def variables_used(self) -> List[str]:
        """Extract variable names from template."""
        import re
        return re.findall(r'\{(\w+)\}', self.text)
```

### Variable

```python
class Variable(AgentScopedModel):
    """A dynamic context value resolved at runtime.

    Stored via ConfigStore interface.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]*$", max_length=50)
    description: Optional[str] = None

    # Resolution
    resolver_tool_id: str  # Tool that computes the value
    update_policy: VariableUpdatePolicy = VariableUpdatePolicy.ON_DEMAND

    # Caching
    cache_ttl_seconds: int = Field(default=0, ge=0, description="0 = no cache")

    class Config:
        cache_key_pattern = "{tenant_id}:{agent_id}:variables"
        cache_ttl_seconds = 3600
```

---

## Memory Entities

### Episode

```python
class Episode(BaseModel):
    """An atomic unit of memory in the knowledge graph.

    Stored via MemoryStore interface. Implementations:
    - Neo4jMemoryStore (graph nodes)
    - MongoDBMemoryStore (documents)
    - PostgresMemoryStore (relational rows)
    - FalkorDBMemoryStore (Redis-based graph)
    """
    id: UUID = Field(default_factory=uuid4)

    # Isolation key: tenant_id:session_id
    group_id: str = Field(description="Composite key for tenant/session isolation")

    # Content
    content: str
    content_type: str = "message"  # message, event, document, summary

    # Source tracking
    source: str  # "user", "agent", "system", "external"
    source_metadata: Dict[str, Any] = {}

    # Temporal (bi-temporal model)
    occurred_at: datetime  # When it happened in the real world
    recorded_at: datetime = Field(default_factory=datetime.utcnow)  # When we learned it

    # Embedding for semantic search
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None

    # Extracted entities (post-processing fills this)
    entity_ids: List[UUID] = []

    @staticmethod
    def make_group_id(tenant_id: UUID, session_id: UUID) -> str:
        return f"{tenant_id}:{session_id}"
```

### Entity

```python
class Entity(BaseModel):
    """A named thing extracted from episodes (person, order, product).

    Stored via MemoryStore interface as graph nodes or documents.
    """
    id: UUID = Field(default_factory=uuid4)
    group_id: str

    # Identity
    name: str
    entity_type: str  # "person", "order", "product", "organization", etc.
    attributes: Dict[str, Any] = {}

    # Temporal validity (when was this true?)
    valid_from: datetime
    valid_to: Optional[datetime] = None  # None = still valid
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    # Embedding for semantic search
    embedding: Optional[List[float]] = None
```

### Relationship

```python
class Relationship(BaseModel):
    """A connection between two entities.

    Stored via MemoryStore interface as graph edges or references.
    """
    id: UUID = Field(default_factory=uuid4)
    group_id: str

    # Connection
    from_entity_id: UUID
    to_entity_id: UUID
    relation_type: str  # "ordered", "owns", "works_for", "related_to", etc.
    attributes: Dict[str, Any] = {}

    # Temporal validity
    valid_from: datetime
    valid_to: Optional[datetime] = None
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Session State

### Session

```python
class StepVisit(BaseModel):
    """Record of visiting a step in a scenario graph.

    Used for loop detection, back-tracking, re-localization, and audit trail.
    See alignment-engine.md "Scenario Navigation" for full algorithm.
    """
    step_id: UUID
    entered_at: datetime
    turn_number: int
    transition_reason: Optional[str] = None  # "transition:condition_text" | "relocalize" | "entry"
    confidence: float = 1.0  # Confidence of the navigation decision (0.0 - 1.0)


class Session(BaseModel):
    """Runtime state for a conversation session.

    Stored via SessionStore interface (two-tier):
    - Cache: Redis (TTL-based, fast access)
    - Persistent: PostgreSQL or MongoDB (long-term storage)

    On cache miss, session is loaded from persistent store.

    ## Scenario State Machine Invariants

    At any time, a session is either:
    1. Not in a scenario (active_scenario_id = None, active_step_id = None)
    2. In exactly one scenario, at exactly one step (both set)

    active_step_id can only change via:
    - Edge transition (following a StepTransition)
    - Re-localization (recovery mechanism)
    - Scenario entry (sets to entry_step_id)
    - Scenario exit (clears both IDs)
    - Explicit API override (admin correction)
    """
    session_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: UUID

    # Channel info
    channel: Channel
    channel_user_id: str  # Phone number, email, session token, etc.

    # Link to persistent interlocutor identity / InterlocutorDataStore
    # See interlocutor data architecture for full model
    interlocutor_id: UUID
    interlocutor_type: Literal["HUMAN", "AGENT", "SYSTEM", "BOT"] = "HUMAN"

    # Config version (soft-pin)
    config_version: int  # Which agent version this session uses

    # Scenario tracking (see alignment-engine.md for navigation algorithm)
    active_scenario_id: Optional[UUID] = None
    active_step_id: Optional[UUID] = None  # Current step within scenario
    active_scenario_version: Optional[int] = None  # Version when scenario was entered
    step_history: List[StepVisit] = []     # Last N visits (loop detection, audit)
    relocalization_count: int = 0          # Times relocalized in current scenario

    # Rule tracking
    rule_fires: Dict[str, int] = {}        # rule_id -> fire count
    rule_last_fire_turn: Dict[str, int] = {}  # rule_id -> turn number

    # Variables cache
    variables: Dict[str, Any] = {}
    variable_updated_at: Dict[str, datetime] = {}

    # Conversation metrics
    turn_count: int = 0
    status: SessionStatus = SessionStatus.ACTIVE

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Key pattern used by SessionStore cache
        cache_key_pattern = "session:{tenant_id}:{agent_id}:{interlocutor_id}:{channel}"

    # Bounded history to prevent unbounded growth
    MAX_STEP_HISTORY: ClassVar[int] = 50
```

### Turn

```python
class ToolCall(BaseModel):
    """Record of a tool execution."""
    tool_id: str
    tool_name: str
    input: Dict[str, Any]
    output: Any
    success: bool
    error: Optional[str] = None
    latency_ms: int


class Turn(BaseModel):
    """A single conversation turn (request/response pair).

    Stored via AuditStore interface. Implementations:
    - PostgresAuditStore (BRIN indexes on timestamp)
    - MongoDBAuditStore (TTL + time indexes)
    """
    logical_turn_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    session_id: UUID
    turn_number: int

    # Input/Output
    user_message: str
    agent_response: str

    # Step snapshots (before and after)
    scenario_before: Optional[Dict[str, str]] = None  # {scenario_id, step_id}
    scenario_after: Optional[Dict[str, str]] = None

    # What happened during processing
    matched_rule_ids: List[UUID] = []
    tool_calls: List[ToolCall] = []
    template_ids_used: List[UUID] = []
    enforcement_triggered: bool = False
    enforcement_action: Optional[str] = None  # "regenerate", "fallback"

    # Metrics
    latency_ms: int
    tokens_used: int

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## Request/Response Models

### Chat Processing

```python
class ChatRequest(BaseModel):
    """Inbound message for processing."""
    tenant_id: UUID                        # Resolved upstream (channel-gateway)
    agent_id: UUID                         # Which agent to use
    channel: Channel                       # whatsapp, slack, webchat, etc.
    channel_user_id: str                   # User identifier on channel
    interlocutor_id: UUID | None = None    # Optional: internal interlocutor identifier (if already known upstream)
    interlocutor_type: Literal["HUMAN", "AGENT", "SYSTEM", "BOT"] = "HUMAN"
    session_id: Optional[UUID] = None      # If None, create new session
    message: str
    metadata: Dict[str, Any] = {}

    # For async processing
    callback_url: Optional[str] = None
    callback_secret: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from message processing."""
    response: str
    session_id: UUID
    logical_turn_id: UUID

    # Scenario info
    scenario: Optional[Dict[str, str]] = None  # {id, step}

    # Transparency (for debugging/audit)
    matched_rules: List[str] = []  # Rule IDs
    tools_called: List[str] = []   # Tool IDs

    # Metrics
    tokens_used: int
    latency_ms: int
```

### Envelope (External Platform Integration)

```python
class InboundEnvelope(BaseModel):
    """Message envelope from channel-gateway via message-router."""
    envelope_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: UUID
    channel: Channel
    channel_user_id: str
    interlocutor_id: UUID | None = None
    interlocutor_type: Literal["HUMAN", "AGENT", "SYSTEM", "BOT"] = "HUMAN"
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}

    # Routing info
    routed_at: Optional[datetime] = None
    coalesced_count: int = 0  # If messages were combined


class OutboundEnvelope(BaseModel):
    """Response envelope to channel-gateway."""
    envelope_id: UUID
    session_id: UUID
    logical_turn_id: UUID
    response: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}
```

---

## Runtime Models

### Scenario Filter Results

```python
class ScenarioFilterResult(BaseModel):
    """Output of the ScenarioFilter.

    See alignment-engine.md "Scenario Navigation" for the full algorithm.
    The ScenarioFilter is responsible for determining step transitions
    in graph-based scenarios.
    """
    scenario_action: str  # "none" | "start" | "continue" | "transition" | "exit" | "relocalize"
    target_scenario_id: Optional[UUID] = None  # Set if action is "start"
    target_step_id: Optional[UUID] = None  # Set if action is "start", "transition", or "relocalize"
    confidence: float  # 0.0 - 1.0
    reasoning: str

    # Recovery tracking
    relocalization_triggered: bool = False  # True if we had to recover from inconsistent state


class ScenarioFilterConfig(BaseModel):
    """Configuration for scenario step navigation.

    Controls thresholds, LLM adjudication, and re-localization behavior.
    """
    # Entry threshold (for starting a scenario)
    entry_threshold: float = 0.65        # Min score to enter a scenario

    # Transition thresholds (for moving between steps)
    transition_threshold: float = 0.65   # Min score to consider a transition
    sanity_threshold: float = 0.35       # If all below this, something's wrong
    min_margin: float = 0.1              # Required margin over runner-up for tie-break

    # LLM adjudication (used when multiple transitions match)
    llm_adjudication_enabled: bool = True
    model: str = "openrouter/anthropic/claude-3-haiku"  # Fast model for decisions

    # Loop detection
    max_loop_iterations: int = 5         # Max times to revisit same step
    loop_detection_window: int = 10      # Turns to look back for loop check

    # Re-localization (recovery when step is invalid or conversation drifts)
    relocalization_enabled: bool = True
    relocalization_threshold: float = 0.7       # Min score to accept relocalization
    relocalization_trigger_turns: int = 3       # Low-confidence turns before triggering
    max_relocalization_hops: int = 3            # Max graph distance from last good step
    max_relocalization_candidates: int = 10     # Max steps to evaluate

    # History
    step_history_size: int = 50          # Max step visits to retain

    # Scenario update strategy (see scenario-update-methods.md)
    update_strategy: str = "conservative"  # "conservative", "optimistic", "graph_aware"
```

### Rule Filter Results

```python
class RuleFilterDecision(BaseModel):
    """LLM rule filtering decision.

    Note: This is the RuleFilter output, separate from ScenarioFilter.
    RuleFilter only decides which rules apply - scenario navigation
    is handled by the dedicated ScenarioFilter.
    """
    applicable_rule_indices: List[int]  # 1-based indices from candidate list
    scenario_signal: Optional[str] = None  # Coarse hint: "start" | "exit" | None
    reasoning: str


class RuleFilterResult(BaseModel):
    """Result of rule filtering step."""
    matched_rules: List["MatchedRule"]
    scenario_signal: Optional[str] = None  # Passed to ScenarioFilter as hint
    reasoning: str


class RuleFilterConfig(BaseModel):
    """Configuration for rule filtering."""
    enabled: bool = True
    model: str = "openrouter/anthropic/claude-3-haiku"
    max_rules: int = 10  # Max rules to return
```

### Matched Rule

```python
class MatchedRule(BaseModel):
    """A Rule that matched the current turn, with scoring details."""
    rule: Rule
    similarity_score: float  # Vector similarity (0-1)
    bm25_score: float        # Keyword match score
    final_score: float       # Combined score after weighting
    newly_fired: bool        # First time this session?

    # Resolved attachments
    tools_to_execute: List[str] = []     # Tool IDs
    templates_to_consider: List[Template] = []
```

### Context for Response Composer

```python
class TurnContext(BaseModel):
    """All context assembled for response generation."""
    # Session
    session: Session
    message: str

    # Scenario
    active_scenario: Optional[Scenario] = None
    active_step: Optional[ScenarioStep] = None

    # Rules
    matched_rules: List[MatchedRule] = []

    # Memory
    memory_context: str = ""  # Formatted for prompt
    relevant_episodes: List[Episode] = []
    relevant_entities: List[Entity] = []

    # Variables (resolved)
    variables: Dict[str, Any] = {}

    # Tool outputs (pre-LLM)
    tool_outputs: Dict[str, Any] = {}

    # Conversation history
    recent_turns: List[Turn] = []
```

### Migration Plan Models

```python
class MigrationPlan(BaseModel):
    """Pre-computed migration plan for a scenario version transition.

    Generated when a scenario is updated. Contains instructions for
    what to do with interlocutors at each step of the old version.

    See scenario-update-methods.md for full details.
    """
    id: UUID = Field(default_factory=uuid4)
    scenario_id: UUID
    from_version: int
    to_version: int

    # Action for each step in the OLD version
    step_actions: Dict[UUID, "StepMigrationAction"] = {}

    # Summary for operator review
    summary: "MigrationSummary"

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    # Status
    status: str = "pending"  # "pending" | "approved" | "deployed" | "superseded"

    class Config:
        cache_key_pattern = "migration_plan:{scenario_id}:{from_version}:{to_version}"
        cache_ttl_seconds = 86400 * 30  # 30 days


class StepMigrationAction(BaseModel):
    """What to do for interlocutors at a specific step in the old version."""

    from_step_id: UUID
    from_step_name: str

    # Action type: "continue" | "collect" | "teleport" | "relocate" | "execute" | "exit"
    action: str

    # For action="collect"
    collect_fields: List[str] = []
    collect_reason: Optional[str] = None

    # For action="teleport"
    teleport_target_id: Optional[UUID] = None
    teleport_target_name: Optional[str] = None
    teleport_condition: Optional[str] = None  # Evaluated at runtime
    teleport_condition_fields: List[str] = []
    teleport_fallback_action: str = "continue"

    # For action="relocate"
    relocate_target_id: Optional[UUID] = None
    relocate_target_name: Optional[str] = None

    # Checkpoint protection
    blocked_by_checkpoints: List["CheckpointRef"] = []

    # For action="execute"
    execute_actions: List[UUID] = []

    # Human-readable explanation
    reason: str = ""


class CheckpointRef(BaseModel):
    """Reference to a checkpoint that might block teleportation."""
    step_id: UUID
    step_name: str
    checkpoint_description: str


class MigrationSummary(BaseModel):
    """Human-readable summary for operator review."""

    total_steps_in_old_version: int
    steps_unchanged: int = 0
    steps_needing_collection: int = 0
    steps_with_teleport: int = 0
    steps_deleted: int = 0
    steps_with_actions: int = 0

    estimated_sessions_affected: int = 0
    sessions_by_step: Dict[str, int] = {}

    warnings: List["MigrationWarning"] = []
    fields_to_collect: List["FieldCollectionInfo"] = []


class MigrationWarning(BaseModel):
    """Warning for operator review."""
    severity: str  # "info" | "warning" | "critical"
    step_name: str
    message: str


class FieldCollectionInfo(BaseModel):
    """Information about a field that needs collection."""
    field_name: str
    display_name: str
    affected_steps: List[str] = []
    reason: str
    can_extract_from_conversation: bool = True


class ReconciliationResult(BaseModel):
    """Result of applying migration plan to a session."""
    action: str  # "continue" | "teleport" | "collect" | "execute_action" | "exit_scenario"

    target_step_id: Optional[UUID] = None
    teleport_reason: Optional[str] = None

    collect_fields: List[str] = []
    execute_actions: List[UUID] = []

    user_message: Optional[str] = None

    blocked_by_checkpoint: bool = False
    checkpoint_warning: Optional[str] = None
```

---

## Cache Configuration (CacheStore Interface)

All caching is done via the `CacheStore` interface, allowing pluggable backends (Redis, Valkey, DragonflyDB, Memcached, etc.).

### Per-Entity TTL Strategy

```python
CACHE_CONFIG = {
    # Agent config: long TTL, invalidated via PubSubBroker
    "agent_bundle": {
        "key_pattern": "{tenant_id}:{agent_id}:v{version}",
        "ttl_seconds": 86400 * 30,  # 30 days
        "invalidation": "cfg-updated (via PubSubBroker)",
    },

    # Session cache: 1 hour TTL (persistent storage has no TTL)
    "session": {
        "key_pattern": "session:{tenant_id}:{agent_id}:{interlocutor_id}:{channel}",
        "ttl_seconds": 3600,  # 1 hour (reload from persistent on miss)
        "refresh_on_access": True,
    },

    # Embeddings: immutable, long cache
    "embedding": {
        "key_pattern": "emb:{hash(text)}:{model}",
        "ttl_seconds": 86400 * 7,  # 7 days
        "immutable": True,
    },

    # Rule match cache: short TTL (context changes)
    "rule_match": {
        "key_pattern": "match:{tenant_id}:{agent_id}:{hash(message)}",
        "ttl_seconds": 300,  # 5 minutes
        "optional": True,  # Can skip if miss
    },
}
```

### CacheStore Key Patterns

```python
# Sessions (via SessionStore, backed by CacheStore)
session:{tenant_id}:{agent_id}:{interlocutor_id}:{channel}

# Agent bundles (from Control Plane via CacheStore)
{tenant_id}:{agent_id}:cfg                    # Pointer to version
{tenant_id}:{agent_id}:v{version}:scenarios
{tenant_id}:{agent_id}:v{version}:rules
{tenant_id}:{agent_id}:v{version}:templates
{tenant_id}:{agent_id}:v{version}:tools
{tenant_id}:{agent_id}:v{version}:variables

# Migration plans (see scenario-update-methods.md)
migration_plan:{scenario_id}:{from_version}:{to_version}

# Archived scenario versions (for migration)
scenario_archive:{scenario_id}:v{version}

# Idempotency (via CacheStore)
idem:{tenant_id}:{agent_id}:{session_id}:{turn}:{op_hash}

# Rate limiting (via CacheStore)
rl:{tenant_id}:{endpoint}
```

### PubSubBroker Channels

```python
# Config invalidation (via PubSubBroker interface)
# Implementations: Redis Pub/Sub, NATS JetStream, RabbitMQ, Kafka
cfg-updated  # Payload: {tenant_id, agent_id, version}
```
