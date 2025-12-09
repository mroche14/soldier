"""Alignment engine exports."""

from soldier.alignment.context import (
    Context,  # Deprecated: use SituationSnapshot instead
    SituationSensor,
    SituationSnapshot,
    Turn,
)
from soldier.alignment.enforcement import (
    ConstraintViolation,
    EnforcementResult,
    EnforcementValidator,
    FallbackHandler,
)
from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.execution import (
    ToolExecutor,
    ToolResult,
    VariableResolution,
    VariableResolver,
)
from soldier.alignment.filtering import (
    MatchedRule,
    RuleFilter,
    RuleFilterResult,
    ScenarioAction,
    ScenarioFilter,
    ScenarioFilterResult,
)
from soldier.alignment.generation import PromptBuilder, ResponseGenerator
from soldier.alignment.models import Rule, Template
from soldier.alignment.result import AlignmentResult, PipelineStepTiming
from soldier.alignment.retrieval import (
    RuleReranker,
    RuleRetriever,
    ScenarioRetriever,
    SelectionStrategy,
)

__all__ = [
    "AlignmentEngine",
    "AlignmentResult",
    "PipelineStepTiming",
    # Context
    "Context",  # Deprecated: use SituationSnapshot instead
    "SituationSensor",
    "SituationSnapshot",
    "Turn",
    # Filtering
    "MatchedRule",
    "RuleFilter",
    "RuleFilterResult",
    "ScenarioFilter",
    "ScenarioAction",
    "ScenarioFilterResult",
    # Generation
    "PromptBuilder",
    "ResponseGenerator",
    # Enforcement
    "EnforcementValidator",
    "EnforcementResult",
    "ConstraintViolation",
    "FallbackHandler",
    # Execution
    "ToolExecutor",
    "ToolResult",
    "VariableResolver",
    "VariableResolution",
    # Retrieval
    "RuleRetriever",
    "RuleReranker",
    "ScenarioRetriever",
    "SelectionStrategy",
    # Models
    "Rule",
    "Template",
]
