"""Alignment domain models.

Contains all Pydantic models for the alignment engine:
- Agents for top-level configuration
- Rules for behavioral policies
- Scenarios for multi-step flows
- Templates for response text
- Variables for dynamic context
- ToolActivations for per-agent tool management
- PublishJobs for configuration versioning
- Context for extracted understanding
"""

from focal.alignment.models.agent import Agent, AgentSettings
from focal.alignment.models.base import AgentScopedModel, TenantScopedModel
from focal.alignment.models.context import Context, ExtractedEntities, UserIntent
from focal.alignment.models.enums import Scope, TemplateResponseMode, VariableUpdatePolicy
from focal.alignment.models.glossary import GlossaryItem
from focal.alignment.models.intent import Intent, IntentCandidate, ScoredIntent
from focal.alignment.models.publish import PublishJob, PublishStage
from focal.alignment.models.rule import MatchedRule, Rule
from focal.alignment.models.rule_relationship import RuleRelationship, RuleRelationshipKind
from focal.alignment.models.scenario import Scenario, ScenarioStep, StepTransition
from focal.alignment.models.template import Template
from focal.alignment.models.tool_activation import ToolActivation
from focal.alignment.models.tool_binding import ToolBinding
from focal.alignment.models.turn_context import TurnContext
from focal.alignment.models.turn_input import TurnInput
from focal.alignment.models.variable import Variable

__all__ = [
    # Base models
    "TenantScopedModel",
    "AgentScopedModel",
    # Agent models
    "Agent",
    "AgentSettings",
    # Enums
    "Scope",
    "TemplateResponseMode",
    "VariableUpdatePolicy",
    # Rule models
    "Rule",
    "MatchedRule",
    "RuleRelationship",
    "RuleRelationshipKind",
    # Scenario models
    "Scenario",
    "ScenarioStep",
    "StepTransition",
    # Template models
    "Template",
    # Variable models
    "Variable",
    # Tool activation models
    "ToolActivation",
    # Tool binding models
    "ToolBinding",
    # Publish models
    "PublishJob",
    "PublishStage",
    # Context models
    "Context",
    "UserIntent",
    "ExtractedEntities",
    # Turn models (Phase 1)
    "TurnInput",
    "TurnContext",
    "GlossaryItem",
    # Intent models (Phase 4)
    "Intent",
    "IntentCandidate",
    "ScoredIntent",
]
