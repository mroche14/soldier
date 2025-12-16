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

4. **Brain**: Protocol for thinking units
   - Brain protocol for all thinking implementations
   - Supersede decision capability

5. **Toolbox**: Tool execution layer
   - Three-tier visibility (Catalog, Tenant-Available, Agent-Enabled)
   - Side effect tracking and idempotency
   - Gateway routing to providers

Key Architectural Principles:
- ACF owns WHEN and HOW (timing, coordination, safety)
- CognitivePipeline owns WHAT (decisions, semantics, behavior)
- AgentRuntime owns WHO (agent configuration, capabilities)
- Agenda owns PROACTIVE (scheduled, agent-initiated actions)
- Brain owns THINKING (processing logic, response generation)
- Toolbox owns TOOL EXECUTION (semantics, enforcement, audit)
"""

# ACF exports
from ruche.runtime.acf import (
    ACFEvent,
    ACFEventType,
    AccumulationHint,
    CommitPointTracker,
    FabricTurnContext,
    FabricTurnContextImpl,
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
from ruche.runtime.agent import (
    AgentCapabilities,
    AgentContext,
    AgentMetadata,
    AgentRuntime,
)

# Agenda exports (models from domain layer)
from ruche.domain.agenda import (
    ScheduledTask,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from ruche.runtime.agenda import (
    AgendaScheduler,
    TaskWorkflow,
)

# Brain exports
from ruche.runtime.brain import (
    Brain,
    SupersedeCapable,
    SupersedeDecision as BrainSupersede,
)

# Toolbox exports
from ruche.runtime.toolbox import (
    IdempotencyCache,
    PlannedToolExecution,
    ResolvedTool,
    SideEffectPolicy as ToolboxSideEffectPolicy,
    SideEffectRecord,
    ToolActivation,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionError,
    ToolGateway,
    ToolMetadata,
    ToolProvider,
    ToolResult,
    Toolbox,
)

__all__ = [
    # ACF - Core models
    "LogicalTurn",
    "LogicalTurnStatus",
    "FabricTurnContext",
    "FabricTurnContextImpl",
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
    "ACFEvent",
    "ACFEventType",
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
    # Brain
    "Brain",
    "SupersedeCapable",
    "BrainSupersede",
    # Toolbox
    "Toolbox",
    "ToolGateway",
    "ToolExecutionContext",
    "ToolDefinition",
    "ToolActivation",
    "PlannedToolExecution",
    "ToolResult",
    "ToolMetadata",
    "SideEffectRecord",
    "ToolboxSideEffectPolicy",
    "ResolvedTool",
    "ToolProvider",
    "ToolExecutionError",
    "IdempotencyCache",
]
