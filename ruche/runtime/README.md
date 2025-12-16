# Focal Runtime Layer

The runtime layer provides infrastructure for executing conversational turns in a distributed, multi-tenant environment.

## Architecture

```
focal/runtime/
├── acf/              # Agent Conversation Fabric (customer message infrastructure)
├── agent/            # Agent lifecycle and configuration caching
└── agenda/           # Proactive task execution (bypasses ACF)
```

## ACF (Agent Conversation Fabric)

**Purpose**: Infrastructure for customer-initiated messages.

**Components**:
- `SessionMutex` - Distributed lock ensuring single-writer rule per conversation
- `TurnManager` - Adaptive accumulation for message boundary detection
- `SupersedeCoordinator` - Coordinates supersede decisions with pipeline
- `CommitPointTracker` - Tracks irreversible operations
- `LogicalTurnWorkflow` - Hatchet-based workflow orchestration (stub)

**Key Models**:
- `LogicalTurn` - Atomic unit of user intent (may contain multiple messages)
- `FabricTurnContext` - Aggregated context for turn processing
- `SupersedeDecision` - Pipeline's decision on handling new messages
- `ACFEvent` - Infrastructure events for observability

**Principles**:
- ACF owns WHEN and HOW (timing, coordination, safety)
- CognitivePipeline owns WHAT (decisions, semantics, behavior)
- Channel-agnostic (no AG-UI or protocol specifics)

## AgentRuntime

**Purpose**: Agent lifecycle, configuration caching, and invalidation.

**Components**:
- `AgentRuntime` - Loads and caches agent configurations
- `AgentContext` - Aggregated execution context (stores, config, capabilities)
- `AgentMetadata` - Runtime view of agent configuration
- `AgentCapabilities` - Feature flags for agent behavior

**Key Patterns**:
- Configuration loaded from ConfigStore
- Cached with hash-based invalidation
- Provides execution contexts to pipeline

## Agenda

**Purpose**: Proactive, scheduled agent actions that bypass ACF.

**Components**:
- `AgendaScheduler` - Polls and executes scheduled tasks
- `TaskWorkflow` - Executes tasks without session mutex
- `Task` - Scheduled task model (follow-ups, reminders, etc.)

**Key Distinction**:
- Agent-initiated (not customer messages)
- No session mutex needed
- Direct pipeline execution

## Integration Points

### With Pipeline
```python
# Pipeline receives AgentContext from AgentRuntime
context = await agent_runtime.get_context(tenant_id, agent_id)

# Pipeline processes LogicalTurn from ACF
result = await pipeline.process_logical_turn(
    turn=logical_turn,
    agent_context=context,
)

# Pipeline returns AccumulationHint for next turn
result.accumulation_hint  # Stored in session for next turn
```

### With Stores
```python
# AgentContext aggregates all stores
context.config_store
context.memory_store
context.profile_store
```

### With Hatchet (Future)
```python
# LogicalTurnWorkflow coordinates:
# 1. acquire_mutex
# 2. accumulate
# 3. run_pipeline
# 4. commit_and_respond
# 5. release_mutex (on_failure handler)
```

## Status

- **ACF Core Models**: Complete (LogicalTurn, events, supersede)
- **ACF Components**: Complete (mutex, turn manager, supersede coordinator)
- **ACF Workflow**: Stub (pending Hatchet integration)
- **AgentRuntime**: Complete (core functionality)
- **Agenda**: Complete models, stub workflows

## References

- [ACF Specification](../../docs/focal_360/architecture/ACF_SPEC.md)
- [Logical Turn Model](../../docs/focal_360/architecture/topics/01-logical-turn.md)
- [Session Mutex](../../docs/focal_360/architecture/topics/02-session-mutex.md)
- [Adaptive Accumulation](../../docs/focal_360/architecture/topics/03-adaptive-accumulation.md)
- [Hatchet Integration](../../docs/focal_360/architecture/topics/06-hatchet-integration.md)
