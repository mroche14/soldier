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

from soldier.alignment.models.agent import Agent, AgentSettings
from soldier.alignment.models.base import AgentScopedModel, TenantScopedModel
from soldier.alignment.models.context import Context, ExtractedEntities, UserIntent
from soldier.alignment.models.enums import Scope, TemplateMode, VariableUpdatePolicy
from soldier.alignment.models.publish import PublishJob, PublishStage
from soldier.alignment.models.rule import MatchedRule, Rule
from soldier.alignment.models.scenario import Scenario, ScenarioStep, StepTransition
from soldier.alignment.models.template import Template
from soldier.alignment.models.tool_activation import ToolActivation
from soldier.alignment.models.variable import Variable

__all__ = [
    # Base models
    "TenantScopedModel",
    "AgentScopedModel",
    # Agent models
    "Agent",
    "AgentSettings",
    # Enums
    "Scope",
    "TemplateMode",
    "VariableUpdatePolicy",
    # Rule models
    "Rule",
    "MatchedRule",
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
    # Publish models
    "PublishJob",
    "PublishStage",
    # Context models
    "Context",
    "UserIntent",
    "ExtractedEntities",
]
