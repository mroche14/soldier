"""Domain layer - Pure domain models.

This layer contains all domain models used throughout Focal:
- Interlocutor data (formerly customer data)
- Rules and scenarios
- Memory (episodes, entities, relationships)
- Glossary and templates
- Agenda (tasks and scheduling)

These are pure Pydantic models with no external dependencies.
Store implementations live in their respective modules (stores/).
"""

from ruche.domain.agenda import (
    ScheduledTask,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from ruche.domain.glossary import GlossaryItem
from ruche.domain.interlocutor import (
    Channel,
    ChannelIdentity,
    Consent,
    FallbackAction,
    InterlocutorChannelPresence,
    InterlocutorDataField,
    InterlocutorDataStore,
    InterlocutorSchemaMask,
    InterlocutorSchemaMaskEntry,
    ItemStatus,
    ProfileAsset,
    RequiredLevel,
    ScenarioFieldRequirement,
    SourceType,
    ValidationMode,
    VariableEntry,
    VariableSource,
    VerificationLevel,
)
from ruche.domain.memory import Entity, Episode, Relationship
from ruche.domain.rules import (
    AgentScopedModel,
    MatchedRule,
    Rule,
    Scope,
    TenantScopedModel,
    ToolBinding,
)
from ruche.domain.scenarios import Scenario, ScenarioInstance, ScenarioStep, StepTransition
from ruche.domain.templates import Template, TemplateResponseMode

__all__ = [
    # Base models
    "TenantScopedModel",
    "AgentScopedModel",
    # Agenda
    "Task",
    "ScheduledTask",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    # Interlocutor
    "InterlocutorDataStore",
    "InterlocutorDataField",
    "VariableEntry",
    "ProfileAsset",
    "Channel",
    "ChannelIdentity",
    "InterlocutorChannelPresence",
    "Consent",
    "VerificationLevel",
    "InterlocutorSchemaMask",
    "InterlocutorSchemaMaskEntry",
    "ScenarioFieldRequirement",
    "VariableSource",
    "ItemStatus",
    "SourceType",
    "RequiredLevel",
    "FallbackAction",
    "ValidationMode",
    # Rules
    "Rule",
    "MatchedRule",
    "Scope",
    "ToolBinding",
    # Scenarios
    "Scenario",
    "ScenarioStep",
    "StepTransition",
    "ScenarioInstance",
    # Memory
    "Episode",
    "Entity",
    "Relationship",
    # Glossary
    "GlossaryItem",
    # Templates
    "Template",
    "TemplateResponseMode",
]
