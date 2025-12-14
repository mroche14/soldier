"""ASA: Agent Setter Agent - Mechanic-Agnostic Meta-Agent.

The ASA module provides design-time validation and configuration assistance
for ANY CognitivePipeline implementation, regardless of which cognitive
mechanic it uses (alignment, ReAct, planner-executor, custom, etc.).

Key Components:
    - Validator: Tool and scenario validation, pipeline conformance tests
    - Suggester: Policy suggestions, edge case generation
    - Wizard: Configuration schema generation for UI wizards
    - CI: Deployment validation for continuous integration

Core Principle:
    ASA is mechanic-agnostic. It validates universal pipeline requirements
    and helps configure mechanic-specific settings through schema-driven
    workflows.
"""

from focal.asa.models import (
    ArtifactSchema,
    ConfigSchema,
    DeploymentValidationResult,
    Issue,
    ParameterSchema,
    PolicySuggestion,
    Severity,
    SideEffectPolicy,
    Suggestion,
    SuggestedRule,
    ValidationResult,
)
from focal.asa.suggester.edge_case_generator import EdgeCaseGenerator
from focal.asa.suggester.policy_suggester import PolicySuggester
from focal.asa.validator.pipeline_conformance import PipelineConformanceTests
from focal.asa.validator.scenario_validator import ScenarioValidator
from focal.asa.validator.tool_validator import ToolValidator
from focal.asa.wizard.schema_generator import SchemaGenerator

__all__ = [
    # Models
    "ArtifactSchema",
    "ConfigSchema",
    "DeploymentValidationResult",
    "Issue",
    "ParameterSchema",
    "PolicySuggestion",
    "Severity",
    "SideEffectPolicy",
    "Suggestion",
    "SuggestedRule",
    "ValidationResult",
    # Validators
    "PipelineConformanceTests",
    "ScenarioValidator",
    "ToolValidator",
    # Suggesters
    "EdgeCaseGenerator",
    "PolicySuggester",
    # Wizard
    "SchemaGenerator",
]
