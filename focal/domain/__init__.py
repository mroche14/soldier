"""Domain layer - Pure domain models.

This layer contains all domain models used throughout Focal:
- Interlocutor data (formerly customer data)
- Rules and scenarios
- Memory (episodes, entities, relationships)
- Glossary and templates

These are pure Pydantic models with no external dependencies.
Store implementations live in their respective modules (stores/).
"""

from focal.domain.glossary import GlossaryItem
from focal.domain.interlocutor import (
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
from focal.domain.memory import Entity, Episode, Relationship
from focal.domain.rules import (
    AgentScopedModel,
    MatchedRule,
    Rule,
    Scope,
    TenantScopedModel,
    ToolBinding,
)
from focal.domain.scenarios import Scenario, ScenarioInstance, ScenarioStep, StepTransition
from focal.domain.templates import Template, TemplateResponseMode

__all__ = [
    # Base models
    "TenantScopedModel",
    "AgentScopedModel",
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
