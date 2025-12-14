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

from ruche.alignment.models.agent import Agent, AgentSettings
from ruche.alignment.models.base import AgentScopedModel, TenantScopedModel
from ruche.alignment.models.context import Context, ExtractedEntities, UserIntent
from ruche.alignment.models.enums import Scope, TemplateResponseMode, VariableUpdatePolicy
from ruche.alignment.models.glossary import GlossaryItem
from ruche.alignment.models.intent import Intent, IntentCandidate, ScoredIntent
from ruche.alignment.models.publish import PublishJob, PublishStage
from ruche.alignment.models.rule import MatchedRule, Rule
from ruche.alignment.models.rule_relationship import RuleRelationship, RuleRelationshipKind
from ruche.alignment.models.scenario import Scenario, ScenarioStep, StepTransition
from ruche.alignment.models.template import Template
from ruche.alignment.models.tool_activation import ToolActivation
from ruche.alignment.models.tool_binding import ToolBinding
from ruche.alignment.models.turn_context import TurnContext
from ruche.alignment.models.turn_input import TurnInput
from ruche.alignment.models.variable import Variable

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
