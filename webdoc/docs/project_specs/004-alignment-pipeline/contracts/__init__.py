"""Contract specifications for the Alignment Pipeline.

These contracts define the interfaces and data models for Phases 6-11.
They serve as the specification for implementation.
"""

from contracts.alignment_engine import (
    AlignmentEngine,
    AlignmentResult,
    ConstraintViolation,
    EnforcementResult,
    GenerationResult,
    MatchedRule,
    PipelineStepTiming,
    ScenarioAction,
    ScenarioFilterResult,
    TemplateMode,
    ToolResult,
)
from contracts.context_extractor import (
    Context,
    ContextExtractor,
    ExtractedEntity,
    ScenarioSignal,
    Sentiment,
    Turn,
    Urgency,
)
from contracts.selection_strategy import (
    ScoredItem,
    SelectionResult,
    SelectionStrategy,
)

__all__ = [
    # Selection Strategy (Phase 6)
    "ScoredItem",
    "SelectionResult",
    "SelectionStrategy",
    # Context Extraction (Phase 7)
    "Context",
    "ContextExtractor",
    "ExtractedEntity",
    "ScenarioSignal",
    "Sentiment",
    "Turn",
    "Urgency",
    # Alignment Engine (Phase 11)
    "AlignmentEngine",
    "AlignmentResult",
    "ConstraintViolation",
    "EnforcementResult",
    "GenerationResult",
    "MatchedRule",
    "PipelineStepTiming",
    "ScenarioAction",
    "ScenarioFilterResult",
    "TemplateMode",
    "ToolResult",
]
