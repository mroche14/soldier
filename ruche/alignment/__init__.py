"""Alignment engine exports."""

from ruche.alignment.context import (
    Context,  # Deprecated: use SituationSnapshot instead
    SituationSensor,
    SituationSnapshot,
    Turn,
)
from ruche.alignment.enforcement import (
    ConstraintViolation,
    EnforcementResult,
    EnforcementValidator,
    FallbackHandler,
)
from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.execution import (
    ToolExecutor,
    ToolResult,
    VariableResolution,
    VariableResolver,
)
from ruche.alignment.filtering import (
    MatchedRule,
    RuleFilter,
    RuleFilterResult,
    ScenarioAction,
    ScenarioFilter,
    ScenarioFilterResult,
)
from ruche.alignment.generation import PromptBuilder, ResponseGenerator
from ruche.alignment.models import Rule, Template
from ruche.alignment.result import AlignmentResult, PipelineStepTiming
from ruche.alignment.retrieval import (
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
