"""FOCAL Brain domain and pipeline models.

Contains all Pydantic models for the FOCAL alignment brain:

Domain Models:
- Agents for top-level configuration
- Rules for behavioral policies
- Scenarios for multi-step flows
- Templates for response text
- Variables for dynamic context
- ToolActivations for per-agent tool management
- PublishJobs for configuration versioning

Pipeline Models:
- TurnContext for aggregated turn state
- SituationSnapshot for extracted understanding
- ResponsePlan for generation planning
- EnforcementResult for constraint validation
- AlignmentResult for final pipeline output
"""

# Base models
from ruche.brains.focal.models.base import AgentScopedModel, TenantScopedModel

# Agent models
from ruche.brains.focal.models.agent import Agent, AgentSettings

# Enums
from ruche.brains.focal.models.enums import Scope, TemplateResponseMode, VariableUpdatePolicy

# Rule models
from ruche.brains.focal.models.rule import MatchedRule, Rule
from ruche.brains.focal.models.rule_relationship import RuleRelationship, RuleRelationshipKind

# Scenario models
from ruche.brains.focal.models.scenario import Scenario, ScenarioStep, StepTransition

# Template models
from ruche.brains.focal.models.template import Template

# Variable models
from ruche.brains.focal.models.variable import Variable

# Tool models
from ruche.brains.focal.models.tool_activation import ToolActivation
from ruche.brains.focal.models.tool_binding import ToolBinding

# Publish models
from ruche.brains.focal.models.publish import PublishJob, PublishStage

# Context models (legacy Phase 1)
from ruche.brains.focal.models.context import Context, ExtractedEntities, UserIntent

# Turn models
from ruche.brains.focal.models.turn_input import TurnInput
from ruche.brains.focal.models.turn_context import TurnContext
from ruche.brains.focal.models.glossary import GlossaryItem

# Intent models (Phase 4)
from ruche.brains.focal.models.intent import Intent, IntentCandidate, ScoredIntent

# Pipeline models
from ruche.brains.focal.models.situational_snapshot import SituationSnapshot
from ruche.brains.focal.models.response_plan import ResponsePlan
from ruche.brains.focal.models.enforcement_result import EnforcementResult
from ruche.brains.focal.models.pipeline_result import AlignmentResult, PipelineStepTiming

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
    # Tool models
    "ToolActivation",
    "ToolBinding",
    # Publish models
    "PublishJob",
    "PublishStage",
    # Context models (legacy)
    "Context",
    "UserIntent",
    "ExtractedEntities",
    # Turn models
    "TurnInput",
    "TurnContext",
    "GlossaryItem",
    # Intent models
    "Intent",
    "IntentCandidate",
    "ScoredIntent",
    # Pipeline models
    "SituationSnapshot",
    "ResponsePlan",
    "EnforcementResult",
    "AlignmentResult",
    "PipelineStepTiming",
]
