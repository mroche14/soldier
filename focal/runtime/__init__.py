"""Runtime layer for Focal.

The runtime layer provides infrastructure for executing conversational turns:

1. **ACF (Agent Conversation Fabric)**: Infrastructure for customer messages
   - Session mutex (single-writer rule)
   - Logical turns (message accumulation, boundaries)
   - Supersede coordination
   - Commit point tracking

2. **AgentRuntime**: Agent lifecycle and configuration caching
   - Load agent configurations
   - Cache execution contexts
   - Invalidate on config changes

3. **Agenda**: Proactive task execution (bypasses ACF)
   - Scheduled follow-ups and reminders
   - Maintenance tasks
   - Agent-initiated actions

Key Architectural Principles:
- ACF owns WHEN and HOW (timing, coordination, safety)
- CognitivePipeline owns WHAT (decisions, semantics, behavior)
- AgentRuntime owns WHO (agent configuration, capabilities)
- Agenda owns PROACTIVE (scheduled, agent-initiated actions)
"""

# ACF exports
from focal.runtime.acf import (
    AccumulationHint,
    CommitPointTracker,
    FabricEvent,
    FabricEventType,
    FabricTurnContext,
    LogicalTurn,
    LogicalTurnStatus,
    LogicalTurnWorkflow,
    MessageShape,
    PhaseArtifact,
    ScenarioStepRef,
    SessionMutex,
    SideEffect,
    SideEffectPolicy,
    SupersedeAction,
    SupersedeCoordinator,
    SupersedeDecision,
    TurnManager,
    UserCadenceStats,
    build_session_key,
    build_tool_idempotency_key,
)

# Agent exports
from focal.runtime.agent import (
    AgentCapabilities,
    AgentContext,
    AgentMetadata,
    AgentRuntime,
)

# Agenda exports
from focal.runtime.agenda import (
    AgendaScheduler,
    ScheduledTask,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
    TaskWorkflow,
)

__all__ = [
    # ACF - Core models
    "LogicalTurn",
    "LogicalTurnStatus",
    "FabricTurnContext",
    "AccumulationHint",
    "MessageShape",
    "UserCadenceStats",
    # ACF - Supersede
    "SupersedeAction",
    "SupersedeDecision",
    "PhaseArtifact",
    "SideEffect",
    "SideEffectPolicy",
    "ScenarioStepRef",
    # ACF - Events
    "FabricEvent",
    "FabricEventType",
    # ACF - Components
    "SessionMutex",
    "TurnManager",
    "SupersedeCoordinator",
    "CommitPointTracker",
    "LogicalTurnWorkflow",
    # ACF - Utilities
    "build_session_key",
    "build_tool_idempotency_key",
    # Agent
    "AgentRuntime",
    "AgentContext",
    "AgentMetadata",
    "AgentCapabilities",
    # Agenda
    "Task",
    "ScheduledTask",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "AgendaScheduler",
    "TaskWorkflow",
]
