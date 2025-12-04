# Data Model: Alignment Pipeline

**Feature**: 004-alignment-pipeline
**Date**: 2025-11-28

## Overview

This document defines the data models for the Alignment Pipeline. Models follow the existing Pydantic patterns in the codebase.

---

## 1. Selection Strategy Models

### ScoredItem

Generic container for items with similarity scores.

```python
@dataclass
class ScoredItem(Generic[T]):
    """An item with its similarity score."""
    item: T
    score: float  # 0.0 to 1.0
```

### SelectionResult

Output from any selection strategy.

```python
@dataclass
class SelectionResult(Generic[T]):
    """Result of selection with metadata."""
    selected: list[ScoredItem[T]]
    cutoff_score: float  # Score threshold used
    method: str  # Strategy name
    metadata: dict[str, Any]  # Strategy-specific info
```

### SelectionStrategy (Interface)

```python
class SelectionStrategy(ABC):
    """Interface for dynamic k-selection."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier for logging."""
        pass

    @abstractmethod
    def select(
        self,
        items: list[ScoredItem[T]],
        max_k: int = 20,
        min_k: int = 1,
    ) -> SelectionResult[T]:
        """Select items based on score distribution."""
        pass
```

---

## 2. Context Models

### Context (extends existing)

The enriched understanding of a user message.

```python
class Context(BaseModel):
    """Extracted context from user message."""

    # Core fields
    message: str  # Original message
    embedding: list[float] | None = None  # Vector representation
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extracted fields (from LLM extraction)
    intent: str | None = None  # Synthesized user intent
    entities: list[ExtractedEntity] = Field(default_factory=list)
    sentiment: Sentiment | None = None
    topic: str | None = None
    urgency: Urgency = Urgency.NORMAL

    # Scenario navigation hints
    scenario_signal: ScenarioSignal | None = None

    # Conversation context
    turn_count: int = 0
    recent_topics: list[str] = Field(default_factory=list)
```

### ExtractedEntity

```python
class ExtractedEntity(BaseModel):
    """An entity extracted from the message."""

    type: str  # e.g., "order_id", "product_name", "date"
    value: str
    confidence: float = 1.0
```

### Sentiment (Enum)

```python
class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
```

### Urgency (Enum)

```python
class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
```

### ScenarioSignal (Enum)

```python
class ScenarioSignal(str, Enum):
    START = "start"      # User wants to begin a process
    CONTINUE = "continue"  # Normal flow continuation
    EXIT = "exit"        # User wants to leave/cancel
    UNKNOWN = "unknown"  # Unclear intent
```

---

## 3. Retrieval Models

### ScoredRule

```python
class ScoredRule(BaseModel):
    """A rule with its retrieval score."""

    rule: Rule
    score: float  # Similarity score
    source: RuleSource  # How it was retrieved
```

### RuleSource (Enum)

```python
class RuleSource(str, Enum):
    GLOBAL = "global"         # Global scope
    SCENARIO = "scenario"     # Scenario-scoped
    STEP = "step"            # Step-scoped
    DIRECT = "direct"        # Directly referenced
```

### RetrievalResult

```python
class RetrievalResult(BaseModel):
    """Result of the retrieval step."""

    rules: list[ScoredRule]
    scenarios: list[ScoredScenario]
    memory_episodes: list[ScoredEpisode]

    # Metadata
    retrieval_time_ms: float
    selection_metadata: dict[str, Any]  # Per-type selection info
```

---

## 4. Filtering Models

### MatchedRule

```python
class MatchedRule(BaseModel):
    """A rule determined to apply to the current turn."""

    rule: Rule
    match_score: float  # Original retrieval score
    relevance_score: float  # LLM-judged relevance
    reasoning: str  # Why it matches (for audit)
```

### RuleFilterResult

```python
class RuleFilterResult(BaseModel):
    """Result of rule filtering."""

    matched_rules: list[MatchedRule]
    rejected_rules: list[UUID]  # IDs of rules that didn't match
    scenario_signal: ScenarioSignal | None  # Detected from rules
    filter_time_ms: float
```

### ScenarioAction (Enum)

```python
class ScenarioAction(str, Enum):
    NONE = "none"            # No scenario action
    START = "start"          # Start a new scenario
    CONTINUE = "continue"    # Stay in current step
    TRANSITION = "transition"  # Move to new step
    EXIT = "exit"            # Exit scenario
    RELOCALIZE = "relocalize"  # Recovery to valid step
```

### ScenarioFilterResult

```python
class ScenarioFilterResult(BaseModel):
    """Result of scenario filtering/navigation."""

    action: ScenarioAction
    scenario_id: UUID | None = None
    source_step_id: UUID | None = None
    target_step_id: UUID | None = None
    confidence: float = 1.0
    reasoning: str = ""

    # For relocalization
    was_relocalized: bool = False
    original_step_id: UUID | None = None
```

---

## 5. Execution Models

### ToolResult

```python
class ToolResult(BaseModel):
    """Outcome of executing a tool."""

    tool_name: str
    tool_id: UUID | None = None
    rule_id: UUID  # Rule that triggered this tool

    # Execution details
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None = None
    error: str | None = None

    # Status
    success: bool
    execution_time_ms: float
    timeout: bool = False
```

### VariableResolution

```python
class VariableResolution(BaseModel):
    """Result of variable resolution."""

    resolved_variables: dict[str, str]  # name -> value
    unresolved: list[str]  # Variables that couldn't be resolved
    sources: dict[str, str]  # name -> source (session, profile, tool, etc.)
```

---

## 6. Generation Models

### TemplateMode (Enum)

```python
class TemplateMode(str, Enum):
    EXCLUSIVE = "exclusive"  # Use exact template, skip LLM
    SUGGEST = "suggest"      # Include in prompt, LLM can adapt
    FALLBACK = "fallback"    # Use when enforcement fails
```

### GenerationResult

```python
class GenerationResult(BaseModel):
    """Result of response generation."""

    response: str  # The generated response

    # Template info
    template_used: UUID | None = None
    template_mode: TemplateMode | None = None

    # LLM details
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_time_ms: float = 0.0

    # Debug
    prompt_preview: str | None = None  # First N chars of prompt
```

---

## 7. Enforcement Models

### ConstraintViolation

```python
class ConstraintViolation(BaseModel):
    """A detected constraint violation."""

    rule_id: UUID
    rule_name: str
    violation_type: str  # e.g., "contains_prohibited", "missing_required"
    details: str
    severity: str = "hard"  # hard or soft
```

### EnforcementResult

```python
class EnforcementResult(BaseModel):
    """Result of enforcement validation."""

    passed: bool
    violations: list[ConstraintViolation] = Field(default_factory=list)

    # Remediation
    regeneration_attempted: bool = False
    regeneration_succeeded: bool = False
    fallback_used: bool = False
    fallback_template_id: UUID | None = None

    # Final response (may differ from generation)
    final_response: str
```

---

## 8. Pipeline Result Models

### PipelineStepTiming

```python
class PipelineStepTiming(BaseModel):
    """Timing info for a pipeline step."""

    step: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    skipped: bool = False
    skip_reason: str | None = None
```

### AlignmentResult

```python
class AlignmentResult(BaseModel):
    """Complete result of processing a turn through the alignment pipeline."""

    # Identifiers
    turn_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    tenant_id: UUID
    agent_id: UUID

    # Input
    user_message: str

    # Pipeline outputs
    context: Context
    retrieval: RetrievalResult
    matched_rules: list[MatchedRule]
    scenario_result: ScenarioFilterResult | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    generation: GenerationResult
    enforcement: EnforcementResult

    # Final output
    response: str  # The actual response to return

    # Metadata
    pipeline_timings: list[PipelineStepTiming] = Field(default_factory=list)
    total_time_ms: float = 0.0

    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 9. Entity Relationships

```
┌─────────────────┐
│  AlignmentResult│
└────────┬────────┘
         │
         ├───────────────┬───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
┌────────────┐   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│  Context   │   │  Retrieval  │  │  Generation │  │ Enforcement  │
│            │   │  Result     │  │  Result     │  │ Result       │
└────────────┘   └──────┬──────┘  └─────────────┘  └──────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌────────────┐  ┌─────────────┐  ┌────────────┐
│ ScoredRule │  │ScoredScenario│ │ScoredEpisode│
└──────┬─────┘  └─────────────┘  └────────────┘
       │
       ▼
┌────────────┐
│MatchedRule │
└──────┬─────┘
       │
       ▼
┌────────────┐
│ ToolResult │
└────────────┘
```

---

## 10. Configuration Models (extends existing)

### PipelineStepConfig

```python
class PipelineStepConfig(BaseModel):
    """Configuration for a single pipeline step."""

    enabled: bool = True
    provider: str | None = None  # For LLM-based steps
    timeout_ms: int = 5000
    retry_count: int = 0
```

### PipelineConfig (extends existing)

```python
class PipelineConfig(BaseModel):
    """Full pipeline configuration."""

    # Step configs
    context_extraction: ContextExtractionConfig
    retrieval: RetrievalConfig
    reranking: PipelineStepConfig
    rule_filtering: PipelineStepConfig
    scenario_filtering: PipelineStepConfig
    tool_execution: ToolExecutionConfig
    generation: GenerationConfig
    enforcement: EnforcementConfig

    # Selection strategies
    selection: SelectionStrategiesConfig
```

---

## Validation Rules

1. **Context.embedding**: Must be same dimensions as configured embedding model
2. **ScoredItem.score**: Must be between 0.0 and 1.0
3. **MatchedRule.relevance_score**: Must be between 0.0 and 1.0
4. **AlignmentResult.response**: Cannot be empty string
5. **ToolResult**: Must have either `outputs` or `error` (not both None)
6. **ScenarioFilterResult.target_step_id**: Required when action is TRANSITION or RELOCALIZE
