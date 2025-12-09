# Research: Alignment Pipeline

**Feature**: 004-alignment-pipeline
**Date**: 2025-11-28
**Status**: Complete

## Overview

This document consolidates research findings for implementing the Alignment Pipeline (Phases 6-11). All technical decisions are informed by the existing architecture documentation and codebase analysis.

---

## 1. Selection Strategies (Phase 6)

### Decision: Implement 5 selection strategies as documented

**Rationale**: The architecture docs (`docs/architecture/selection-strategies.md`) specify exactly which strategies to implement with clear algorithms and use cases.

**Alternatives Considered**:
- Fixed top-k only → Rejected: Too simplistic, doesn't adapt to query difficulty
- Learning-based adaptive selection → Rejected: Overcomplicated for v1, can add later
- Third-party library (e.g., faiss with auto-k) → Rejected: Need fine-grained control per strategy

**Implementation Details**:

| Strategy | Algorithm | Best For | Dependencies |
|----------|-----------|----------|--------------|
| **Elbow** | Relative score drop detection | Clear separations | None |
| **Adaptive-K** | Curvature analysis of score distribution | General use | numpy |
| **Entropy** | Shannon entropy of score probabilities | Ambiguous queries | scipy.stats |
| **Clustering** | DBSCAN on score space | Multi-topic queries | scikit-learn |
| **Fixed-K** | Simple top-k | Baseline/fallback | None |

**New Dependencies**:
```bash
uv add numpy scipy scikit-learn
```

---

## 2. Context Extraction (Phase 7)

### Decision: LLM-based extraction with embedding-only fallback

**Rationale**: The docs specify three modes (`llm`, `embedding_only`, `disabled`) to balance quality vs latency. LLM mode provides rich context (intent, entities, sentiment); embedding-only is faster but less detailed.

**Alternatives Considered**:
- Always use LLM → Rejected: Too slow/expensive for high-throughput scenarios
- Rule-based NER only → Rejected: Misses semantic nuance
- Fine-tuned small model → Rejected: Training overhead, maintenance burden

**Implementation Details**:

```python
class ContextExtractor:
    """Extract structured context from user messages."""

    async def extract(
        self,
        message: str,
        history: list[Turn],
        mode: Literal["llm", "embedding_only", "disabled"],
    ) -> Context:
        ...
```

**Prompt Template Location**: `focal/alignment/context/prompts/extract_intent.txt`

**Output Model** (already partially defined in `focal/alignment/models/context.py`):
- `user_intent: str` - Synthesized intent
- `entities: list[str]` - Extracted entities
- `sentiment: str | None` - Detected sentiment
- `topic: str | None` - Topic classification
- `scenario_signal: str | None` - start/continue/exit hint
- `embedding: list[float] | None` - Vector representation

---

## 3. Retrieval (Phase 8)

### Decision: Hierarchical scope-based retrieval with selection strategies

**Rationale**: Rules are scoped (GLOBAL → SCENARIO → STEP) and should be retrieved in priority order. Selection strategies dynamically choose how many to keep.

**Alternatives Considered**:
- Flat retrieval (all rules in one query) → Rejected: Misses scope semantics
- Strict scope (only current scope) → Rejected: Would miss global rules
- Pre-filtered candidate pools → Rejected: Reduces flexibility

**Implementation Details**:

```python
class RuleRetriever:
    """Retrieve candidate rules by scope and similarity."""

    async def retrieve(
        self,
        context: Context,
        session: Session,
        config: RetrievalConfig,
    ) -> list[ScoredRule]:
        # 1. Retrieve global rules
        # 2. Retrieve scenario-scoped rules (if in scenario)
        # 3. Retrieve step-scoped rules (if in step)
        # 4. Apply business filters (enabled, max_fires, cooldown)
        # 5. Apply selection strategy
        ...
```

**Reranking**: Optional step using RerankProvider (Cohere, CrossEncoder, etc.) to improve ordering before selection.

---

## 4. Filtering (Phase 9)

### Decision: Separate RuleFilter and ScenarioFilter classes

**Rationale**: Per architecture docs, these have distinct responsibilities:
- **RuleFilter**: "Which rules apply to this turn?" → Returns applicable rule indices
- **ScenarioFilter**: "Which step should we be in?" → Returns navigation action

**Alternatives Considered**:
- Single filter handling both → Rejected: Conflates concerns, harder to test
- Embedding-only filtering → Rejected: Misses semantic nuance for complex conditions
- No filtering (use all retrieved) → Rejected: Too much noise for generation

**Implementation Details**:

```python
class RuleFilter:
    """LLM-based rule relevance filtering."""

    async def filter(
        self,
        context: Context,
        candidates: list[Rule],
        session: Session,
    ) -> RuleFilterResult:
        # Returns: applicable_rule_indices, scenario_signal, reasoning
        ...

class ScenarioFilter:
    """Graph-aware scenario step navigation."""

    async def evaluate(
        self,
        context: Context,
        scenario: Scenario,
        current_step: ScenarioStep,
        session: Session,
    ) -> ScenarioFilterResult:
        # Returns: scenario_action, target_step_id, confidence, reasoning
        ...
```

**Scenario Actions**: `none`, `start`, `continue`, `transition`, `exit`, `relocalize`

**Re-localization**: Recovery mechanism when state is inconsistent. Uses embedding similarity to find best matching reachable step.

---

## 5. Execution & Generation (Phase 10)

### Decision: Sequential tool execution, then prompt building, then LLM generation

**Rationale**: Tools must complete before generation so their outputs can be included in the prompt. Template modes (EXCLUSIVE, SUGGEST, FALLBACK) handle different response strategies.

**Alternatives Considered**:
- Parallel tool execution with streaming → Rejected: Complexity for v1
- Tool-calling LLM (single round) → Rejected: Need deterministic control over which tools run
- Generation before tools → Rejected: Response can't incorporate tool results

**Implementation Details**:

```python
class ToolExecutor:
    """Execute tools from matched rules."""

    async def execute_all(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
        session: Session,
    ) -> list[ToolResult]:
        # Execute tools with timeout handling
        ...

class ResponseGenerator:
    """Generate agent responses."""

    async def generate(
        self,
        context: Context,
        matched_rules: list[MatchedRule],
        tool_results: list[ToolResult],
        memory_context: MemoryContext,
        session: Session,
    ) -> GenerationResult:
        # 1. Check for EXCLUSIVE template → return immediately
        # 2. Build prompt with rules, memory, tools, scenario
        # 3. Call LLM
        # 4. Return GenerationResult
        ...
```

**Template Modes**:
| Mode | Behavior |
|------|----------|
| `EXCLUSIVE` | Skip LLM, use exact template text |
| `SUGGEST` | Include in prompt, LLM can adapt |
| `FALLBACK` | Use when enforcement fails |

---

## 6. Enforcement (Phase 10 continued)

### Decision: Post-generation validation with regeneration and fallback chain

**Rationale**: Hard constraints must be enforced after generation. The chain is: validate → regenerate (once) → fallback template.

**Alternatives Considered**:
- Pre-generation constraint injection only → Rejected: No guarantee of compliance
- Multiple regeneration attempts → Rejected: Latency cost, diminishing returns
- Skip enforcement → Rejected: Critical for compliance use cases

**Implementation Details**:

```python
class EnforcementValidator:
    """Validate responses against hard constraints."""

    async def validate(
        self,
        response: str,
        hard_rules: list[Rule],
        context: Context,
    ) -> EnforcementResult:
        # 1. Check each hard constraint
        # 2. If violation: regenerate with stronger prompt
        # 3. If still violating: use fallback template
        ...
```

---

## 7. Engine Integration (Phase 11)

### Decision: Single AlignmentEngine class orchestrating all steps

**Rationale**: Centralized orchestration simplifies testing, logging, and configuration. Each step is optional and configurable.

**Alternatives Considered**:
- Pipeline pattern with middleware → Rejected: Over-abstracted for v1
- Event-driven with message queue → Rejected: Latency overhead, complexity
- Separate microservices per step → Rejected: Violates simplicity, adds network calls

**Implementation Details**:

```python
class AlignmentEngine:
    """Orchestrate the full alignment pipeline."""

    def __init__(
        self,
        config_store: ConfigStore,
        session_store: SessionStore,
        memory_store: MemoryStore,
        audit_store: AuditStore,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        rerank_provider: RerankProvider | None,
        settings: PipelineSettings,
    ):
        # Initialize all pipeline components
        ...

    async def process_turn(
        self,
        message: str,
        session: Session,
        agent_config: AgentConfig,
    ) -> AlignmentResult:
        # 1. Extract context
        # 2. Retrieve candidates (rules, scenarios, memory)
        # 3. Rerank (if enabled)
        # 4. Filter rules
        # 5. Filter scenario (if in scenario)
        # 6. Execute tools
        # 7. Generate response
        # 8. Enforce constraints
        # 9. Persist state
        # 10. Return result
        ...
```

---

## 8. Performance Considerations

### Latency Budget (target: <1s simple, <2s with tools)

| Step | Budget | Strategy |
|------|--------|----------|
| Context Extraction | 200ms | Use Haiku for speed |
| Retrieval | 50ms | Parallel queries, in-memory for dev |
| Reranking | 100ms | Optional, disable for speed |
| Rule Filter | 150ms | Use Haiku, batch if possible |
| Scenario Filter | 100ms | Embedding-first, LLM only if ambiguous |
| Tool Execution | 200ms | Configurable timeout |
| Generation | 500ms | Sonnet for quality |
| Enforcement | 50ms | Only if hard constraints present |
| Persist | 30ms | Async where possible |

### Concurrency Strategy

- Use asyncio for all I/O operations
- No shared mutable state between requests
- Session state loaded/saved per request
- Connection pooling for stores (production)

---

## 9. Dependencies Summary

### New Dependencies to Add

```bash
uv add numpy scipy scikit-learn
```

### Existing Dependencies Used

- `pydantic` - All models
- `structlog` - Logging
- `prometheus-client` - Metrics
- `opentelemetry-sdk` - Tracing

### Provider Dependencies (optional, per deployment)

- `anthropic` - Anthropic LLM
- `openai` - OpenAI LLM/Embeddings
- `cohere` - Cohere Rerank/Embeddings
- `sentence-transformers` - Local embeddings

---

## 10. Testing Strategy

### Unit Tests (80%)

- Each selection strategy with various score distributions
- Context extractor with mocked LLM
- Rule/scenario retrievers with in-memory stores
- Rule/scenario filters with mocked LLM
- Tool executor with mock tools
- Generator with mocked LLM
- Validator with mock constraints

### Integration Tests (15%)

- Full pipeline with mock providers
- Rule matching → filtering → generation flow
- Scenario entry → transition → exit flow
- Tool execution with mock external services

### Contract Tests

- `SelectionStrategyContract` - All strategies pass same interface tests
- Existing store contracts for retrieval testing

---

## Conclusion

All technical decisions align with the existing architecture documentation. No NEEDS CLARIFICATION items remain. The implementation can proceed to Phase 1 (data model and contracts).
