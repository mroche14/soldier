"""Agent Conversation Fabric (ACF) - Infrastructure Layer.

ACF is pure infrastructure for managing conversational turns:
- Session mutex (single-writer rule)
- Logical turns (message accumulation, boundaries)
- Supersede coordination (facts, not decisions)
- Commit point tracking
- Fabric event emission

ACF is channel-agnostic and decision-agnostic. It provides the
infrastructure for CognitivePipeline to run safely in a distributed,
multi-tenant environment.

Key Principle: ACF owns WHEN and HOW (timing, coordination, safety).
CognitivePipeline owns WHAT (decisions, semantics, behavior).
"""

from ruche.runtime.acf.commit_point import CommitPointTracker
from ruche.runtime.acf.event_router import EventListener, EventRouter
from ruche.runtime.acf.events import ACFEvent, ACFEventType
from ruche.runtime.acf.gateway import (
    ActiveTurnIndex,
    RawMessage,
    TurnAction,
    TurnDecision,
    TurnGateway,
)
from ruche.runtime.acf.models import (
    AccumulationHint,
    FabricTurnContext,
    FabricTurnContextImpl,
    LogicalTurn,
    LogicalTurnStatus,
    MessageShape,
    PhaseArtifact,
    ScenarioStepRef,
    SideEffect,
    SideEffectPolicy,
    SupersedeAction,
    SupersedeDecision,
)
from ruche.runtime.acf.turn_manager import UserCadenceStats
from ruche.runtime.acf.mutex import SessionMutex, build_session_key
from ruche.runtime.acf.supersede import (
    SupersedeCoordinator,
    build_tool_idempotency_key,
)
from ruche.runtime.acf.turn_manager import TurnManager
from ruche.runtime.acf.workflow import LogicalTurnWorkflow

__all__ = [
    # Core models
    "LogicalTurn",
    "LogicalTurnStatus",
    "FabricTurnContext",
    "FabricTurnContextImpl",
    "AccumulationHint",
    "MessageShape",
    "UserCadenceStats",
    "RawMessage",
    # Supersede models
    "SupersedeAction",
    "SupersedeDecision",
    "PhaseArtifact",
    "SideEffect",
    "SideEffectPolicy",
    "ScenarioStepRef",
    # Events
    "ACFEvent",
    "ACFEventType",
    "EventListener",
    "EventRouter",
    # Gateway models
    "TurnAction",
    "TurnDecision",
    # Components
    "SessionMutex",
    "TurnManager",
    "SupersedeCoordinator",
    "CommitPointTracker",
    "LogicalTurnWorkflow",
    "TurnGateway",
    "ActiveTurnIndex",
    # Utilities
    "build_session_key",
    "build_tool_idempotency_key",
]
