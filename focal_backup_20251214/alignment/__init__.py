"""Alignment engine exports."""

from focal.alignment.context import (
    Context,  # Deprecated: use SituationSnapshot instead
    SituationSensor,
    SituationSnapshot,
    Turn,
)
from focal.alignment.enforcement import (
    ConstraintViolation,
    EnforcementResult,
    EnforcementValidator,
    FallbackHandler,
)
from focal.alignment.engine import AlignmentEngine
from focal.alignment.execution import (
    ToolExecutor,
    ToolResult,
    VariableResolution,
    VariableResolver,
)
from focal.alignment.filtering import (
    MatchedRule,
    RuleFilter,
    RuleFilterResult,
    ScenarioAction,
    ScenarioFilter,
    ScenarioFilterResult,
)
from focal.alignment.generation import PromptBuilder, ResponseGenerator
from focal.alignment.models import Rule, Template
from focal.alignment.result import AlignmentResult, PipelineStepTiming
from focal.alignment.retrieval import (
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
