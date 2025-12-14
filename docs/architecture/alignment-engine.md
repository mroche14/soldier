# Alignment Engine

> **Note**: The alignment engine is the conceptual core of Focal's turn processing. The implementation class is `FocalCognitivePipeline` located in `ruche/brain/focal/pipeline.py`.

The alignment engine ensures Focal agents behave according to defined policies. It processes each turn through a multi-step pipeline, matching **Rules** for behavioral control and **Scenarios** for multi-step flows.

## Core Principle

> Shift from *hoping* the LLM follows instructions to *explicitly enforcing* them at runtime.

The engine doesn't just inject rules into a prompt—it takes control when needed:
- **Context extraction**: Understand what the user actually wants
- **Semantic matching**: Find relevant rules via vector search
- **LLM filtering**: Judge which rules actually apply
- **Deterministic tool execution**: Only when rule matches
- **Template responses**: Bypass the LLM entirely when needed
- **Post-generation validation**: Regenerate or fallback if constraints violated

---

## Full Turn Pipeline

The alignment engine is the **core** of Focal's turn processing, but operates on text. Multimodal input/output is handled by pre- and post-processing stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FULL TURN PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Multimodal Input (Audio / Image / Document / Text)                        │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  INPUT PROCESSING (Pre-Pipeline)                                       │ │
│  │                                                                         │ │
│  │  Audio ──► STT (Whisper/Deepgram) ──┐                                  │ │
│  │  Image ──► Vision LLM (Claude/GPT-4o) ──┼──► Unified Text Input        │ │
│  │  Document ──► Doc Parser (LlamaParse) ──┘                              │ │
│  │  Text ─────────────────────────────────►                               │ │
│  │                                                                         │ │
│  │  See configuration.md for STT/Vision/Document model configuration      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ╔════════════════════════════════════════════════════════════════════════╗ │
│  ║                     ALIGNMENT ENGINE (text-based)                       ║ │
│  ║  Context Extraction → Retrieval → Rerank → LLM Filter → Generate → ... ║ │
│  ║                          (see detailed diagram below)                   ║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  OUTPUT PROCESSING (Post-Pipeline)                                     │ │
│  │                                                                         │ │
│  │  Text Response ──► Text (default)                                      │ │
│  │  Text Response ──► TTS (ElevenLabs/OpenAI) ──► Audio                   │ │
│  │  Text Response ──► Image Gen (DALL-E) ──► Image (if requested)         │ │
│  │                                                                         │ │
│  │  Output modality matches input (voice in → voice out) or explicit      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│   Multimodal Output (Text / Audio / Image)                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Alignment Engine Pipeline (Detail)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ALIGNMENT ENGINE PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Text Input (from Input Processing)                                        │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  CONTEXT EXTRACTION                                                     │ │
│  │  "What does the user actually want?"                                   │ │
│  │                                                                         │ │
│  │  Input: message + conversation history                                 │ │
│  │  Output: user_intent, entities, sentiment, scenario_signal             │ │
│  │                                                                         │ │
│  │  Providers: LLMExecutor (Haiku) | EmbeddingProvider (fallback)         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  RETRIEVAL                                                              │ │
│  │  "What rules/scenarios might be relevant?"                             │ │
│  │                                                                         │ │
│  │  - Vector search rules by scope (global → scenario → step)             │ │
│  │  - Vector search scenarios for entry conditions                        │ │
│  │  - Vector search memory for context                                    │ │
│  │  - Apply business filters (enabled, cooldown, max fires)               │ │
│  │                                                                         │ │
│  │  Providers: EmbeddingProvider + ConfigStore + MemoryStore              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  RERANKING (optional)                                                   │ │
│  │  "Improve ordering of candidates"                                      │ │
│  │                                                                         │ │
│  │  Providers: RerankProvider (Cohere, Voyage, CrossEncoder)              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  LLM FILTERING                                                          │ │
│  │  "Which rules actually apply? Should scenario start/continue/exit?"    │ │
│  │                                                                         │ │
│  │  Input: context + candidate rules + current scenario state             │ │
│  │  Output: filtered rules + scenario decision                            │ │
│  │                                                                         │ │
│  │  Providers: LLMExecutor (Haiku - fast yes/no decisions)                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  TOOL EXECUTION                                                         │ │
│  │  "Run tools attached to matched rules"                                 │ │
│  │                                                                         │ │
│  │  Deterministic: tools only run if their rule matched                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  RESPONSE GENERATION                                                    │ │
│  │  "Generate the agent response"                                         │ │
│  │                                                                         │ │
│  │  - Check for EXCLUSIVE template (bypass LLM)                           │ │
│  │  - Build prompt with rules, memory, tools, scenario                    │ │
│  │  - Call LLM                                                            │ │
│  │                                                                         │ │
│  │  Providers: LLMExecutor (Sonnet - best quality)                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  ENFORCEMENT                                                            │ │
│  │  "Validate against hard constraints"                                   │ │
│  │                                                                         │ │
│  │  - Check hard constraint rules                                         │ │
│  │  - Regenerate if violation                                             │ │
│  │  - Fallback to template if still violating                             │ │
│  │                                                                         │ │
│  │  Providers: LLMExecutor (optional self-critique)                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│   Text Response (to Output Processing)                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Provider Interfaces

The alignment engine uses pluggable providers for each AI capability:

### LLMExecutor

```python
class LLMExecutor:
    """Unified LLM interface using Agno for model routing."""

    async def generate(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """Generate text completion with automatic fallback."""
        pass

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> tuple[BaseModel, LLMResponse]:
        """Generate structured output matching schema."""
        pass
```

**Model Routing**: Model strings drive routing to Agno backends:
| Model Prefix | Backend | Example |
|--------------|---------|---------|
| `openrouter/` | Agno OpenRouter | `openrouter/anthropic/claude-3-haiku` |
| `anthropic/` | Agno Claude | `anthropic/claude-sonnet-4-5-20250514` |
| `openai/` | Agno OpenAIChat | `openai/gpt-4o` |
| `groq/` | Agno Groq | `groq/llama-3.1-70b` |
| `mock/` | MockLLMProvider | `mock/test` (testing) |

### EmbeddingProvider

```python
class EmbeddingProvider(ABC):
    """Interface for embedding models."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimensions for this model."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        pass
```

**Implementations**:
| Provider | Models | Dimensions | Best For |
|----------|--------|------------|----------|
| `OpenAIEmbeddings` | text-embedding-3-small, text-embedding-3-large | 1536, 3072 | General use |
| `CohereEmbeddings` | embed-english-v3.0 | 1024 | Multilingual |
| `VoyageEmbeddings` | voyage-large-2 | 1024 | Code, retrieval |
| `SentenceTransformers` | all-MiniLM-L6-v2 | 384 | Local, fast |

### RerankProvider

```python
class RerankProvider(ABC):
    """Interface for reranking models."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[int]:
        """Rerank documents, return indices in order of relevance."""
        pass
```

**Implementations**:
| Provider | Models | Best For |
|----------|--------|----------|
| `CohereRerank` | rerank-english-v3.0 | General reranking |
| `VoyageRerank` | rerank-1 | Code, technical |
| `CrossEncoderRerank` | ms-marco-MiniLM | Local, fast |

---

## Rules

A **Rule** is a "when X, then Y" policy:

```
Condition: "Customer asks about refunds"
Action: "Check order status before answering, use empathetic tone"
```

### Rule Attributes

| Attribute | Purpose |
|-----------|---------|
| `id`, `name` | Identification |
| `condition_text` | Natural language "when" clause |
| `action_text` | Natural language "then" clause |
| `scope` | GLOBAL, SCENARIO, or STEP |
| `scope_id` | Which Scenario/Step (if scoped) |
| `priority` | Higher wins in conflicts |
| `enabled` | Active or disabled |
| `max_fires_per_session` | Limit activations (0 = unlimited) |
| `cooldown_turns` | Minimum turns between re-firing |
| `attached_tools` | Tools to execute when matched |
| `attached_templates` | Response templates to consider |
| `is_hard_constraint` | Must be validated post-generation |
| `embedding` | Precomputed vector of condition + action |

### Rule Model

> **Note:** This is a simplified model for illustration. The full model in [domain-model.md](../design/domain-model.md) includes additional fields: `embedding_model`, `created_at`, `updated_at`, `created_by`, and `tags`.

```python
class Rule(BaseModel):
    """A behavioral policy."""
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str
    description: str | None = None

    # Natural language policy
    condition_text: str      # "When the user asks about refunds"
    action_text: str         # "Check order status first, be empathetic"

    # Scoping
    scope: Scope             # GLOBAL | SCENARIO | STEP
    scope_id: UUID | None    # If SCENARIO or STEP

    # Behavior
    priority: int = 0
    enabled: bool = True
    max_fires_per_session: int = 0  # 0 = unlimited
    cooldown_turns: int = 0

    # Attachments
    attached_tool_ids: list[str] = []
    attached_template_ids: list[UUID] = []

    # Enforcement
    is_hard_constraint: bool = False

    # Precomputed for retrieval
    embedding: list[float] | None = None
    embedding_model: str | None = None  # e.g., "text-embedding-3-small"

    # Audit timestamps (see domain-model.md for full schema)
    # created_at: datetime
    # updated_at: datetime


class Scope(str, Enum):
    GLOBAL = "global"
    SCENARIO = "scenario"
    STEP = "step"
```

### Scope Hierarchy

```
GLOBAL ──────────────────────────────────────────────────────
   │
   │    Always evaluated. Safety rules, universal policies.
   │
SCENARIO ────────────────────────────────────────────────────
   │
   │    Only when that Scenario is active.
   │    Handle flow-specific behaviors.
   │
STEP ────────────────────────────────────────────────────────

        Only when in that specific Step.
        Most specific, highest default weight.
```

**Precedence**: More specific scope wins. STEP > SCENARIO > GLOBAL (when same priority).

---

## Scenarios

A **Scenario** is a multi-step conversational flow:

- Onboarding sequence
- Return/refund process
- KYC verification
- Support escalation path

### Scenario Structure

```
Scenario: "Return Process"
│
├── Step: "Identify Order" (entry)
│   ├── templates: ["ask_order_id"]
│   ├── rules: ["validate_order_format"]
│   └── transitions: → "Verify Eligibility"
│
├── Step: "Verify Eligibility"
│   ├── tools: [check_return_policy]
│   └── transitions: → "Process Return" | → "Deny Return"
│
├── Step: "Process Return"
│   ├── tools: [initiate_return]
│   └── transitions: → "Confirm" (terminal)
│
└── Step: "Deny Return" (terminal)
    └── templates: ["denial_explanation"]
```

### Scenario Models

```python
class Scenario(BaseModel):
    """A multi-step conversational flow."""
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str
    description: str | None = None

    # Structure
    entry_step_id: UUID
    steps: list[ScenarioStep] = []

    # Entry condition (for auto-start)
    entry_condition_text: str | None = None
    entry_condition_embedding: list[float] | None = None

    # Metadata
    enabled: bool = True
    tags: list[str] = []


class ScenarioStep(BaseModel):
    """A step within a scenario."""
    id: UUID
    scenario_id: UUID
    name: str
    description: str | None = None

    # Transitions to other steps
    transitions: list[StepTransition] = []

    # Scoped resources
    template_ids: list[UUID] = []
    rule_ids: list[UUID] = []
    tool_ids: list[str] = []

    # Markers
    is_entry: bool = False
    is_terminal: bool = False


class StepTransition(BaseModel):
    """A transition between steps."""
    to_step_id: UUID
    condition_text: str           # "User provides order ID"
    condition_embedding: list[float] | None = None
    priority: int = 0
```

### Scenario Decisions

The alignment engine makes these scenario decisions:

| Decision | When | Action |
|----------|------|--------|
| **Start** | No active scenario, message matches entry condition | Set active_scenario_id, active_step_id |
| **Continue** | In scenario, no transition matches | Stay in current step |
| **Transition** | In scenario, transition condition matches | Move to new step |
| **Relocalize** | State inconsistent or prolonged low confidence | Jump to best-matching reachable step |
| **Exit** | User intent indicates leaving, or terminal step | Clear active scenario |

---

## Scenario Navigation: The State Machine Model

Scenarios are **directed graphs** (state machines) where each step is a node and transitions are edges. The alignment engine must determine which step to transition to on each turn.

### Core Invariants

> **Primary Invariant**: At any time, a session is either:
> 1. **Not in a scenario** (`active_scenario_id = None`, `active_step_id = None`), or
> 2. **In exactly one scenario, at exactly one step** (`active_scenario_id` and `active_step_id` both set)
>
> **Transition Invariant**: The `active_step_id` can only change via:
> 1. **Edge transition** — following a `StepTransition` from the current step
> 2. **Re-localization** — recovery when state becomes inconsistent
> 3. **Scenario entry** — starting a new scenario (sets to `entry_step_id`)
> 4. **Scenario exit** — leaving the scenario (clears both IDs)
> 5. **Explicit API override** — administrative correction

These invariants keep navigation **local** (we don't re-derive the step from scratch each turn) and **explainable** (every step change has a logged reason).

### Separation of Concerns: RuleFilter vs ScenarioFilter

The alignment engine uses **two distinct filters** rather than overloading one:

| Filter | Responsibility | Input | Output |
|--------|----------------|-------|--------|
| **RuleFilter** | Which rules apply to this turn? | Context, candidate rules, session | `applicable_rule_ids`, coarse `scenario_signal` |
| **ScenarioFilter** | Which step should we be in? | Context, current step, transitions, history | `scenario_action`, `target_step_id` |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FILTER SEPARATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Context Extraction                                                          │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  RULE FILTER                                                          │   │
│  │  "Which rules apply?"                                                 │   │
│  │                                                                        │   │
│  │  Input: context, candidate_rules, session_state                       │   │
│  │  Output:                                                               │   │
│  │    - applicable_rule_indices: [1, 3, 5]                               │   │
│  │    - scenario_signal: "start" | "continue" | "exit" | null            │   │
│  │      (coarse hint, not authoritative for step navigation)             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  SCENARIO FILTER (dedicated, graph-aware)                             │   │
│  │  "Which step should we transition to?"                                │   │
│  │                                                                        │   │
│  │  Input: context, current_step, outgoing_transitions, step_history     │   │
│  │  Output:                                                               │   │
│  │    - scenario_action: "continue" | "transition" | "exit" | "relocalize" │
│  │    - target_step_id: UUID (if transition/relocalize)                  │   │
│  │    - confidence: float                                                │   │
│  │    - reasoning: str                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  Response Generation (with matched rules + scenario context)                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ScenarioFilter Interface

```python
class ScenarioFilterResult(BaseModel):
    """Output of the ScenarioFilter."""
    scenario_action: str  # "none" | "start" | "continue" | "transition" | "exit" | "relocalize"
    target_scenario_id: UUID | None = None  # Set if action is "start"
    target_step_id: UUID | None = None  # Set if action is "start", "transition", or "relocalize"
    confidence: float  # 0.0 - 1.0
    reasoning: str
    relocalization_triggered: bool = False  # True if we had to recover


class ScenarioFilter(ABC):
    """Interface for scenario step navigation decisions."""

    @abstractmethod
    async def evaluate(
        self,
        context: Context,
        scenario: Scenario,
        current_step: ScenarioStep,
        session: Session,
        config: ScenarioFilterConfig,
    ) -> ScenarioFilterResult:
        """
        Determine the next step in the scenario graph.

        This is called only when session.active_scenario_id is set.
        """
        pass
```

---

## Local Transition Algorithm

The primary navigation algorithm only considers **outgoing edges from the current step**. This is efficient and predictable.

### Algorithm Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCENARIO FILTER PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: context, scenario, current_step, session                            │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 0: CONSISTENCY CHECK                                            │ │
│  │                                                                         │ │
│  │  If active_step_id not in scenario.steps → RELOCALIZE                  │ │
│  │  If scenario.version != session.active_scenario_version:               │ │
│  │    - If current step still exists → continue (log warning)             │ │
│  │    - If current step deleted → RELOCALIZE                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 1: RETRIEVE OUTGOING TRANSITIONS                                │ │
│  │                                                                         │ │
│  │  transitions = current_step.transitions                                │ │
│  │  If empty and is_terminal → EXIT                                       │ │
│  │  If empty and not terminal → CONTINUE (stay)                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 2: SEMANTIC SCORING                                             │ │
│  │                                                                         │ │
│  │  For each transition t:                                                │ │
│  │    score = cosine_similarity(context.embedding, t.condition_embedding) │ │
│  │                                                                         │ │
│  │  Filter by thresholds:                                                 │ │
│  │    - transition_threshold (0.65): consider for transition              │ │
│  │    - sanity_threshold (0.35): if ALL below this → maybe relocalize     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ├── All scores < sanity_threshold → check for RELOCALIZATION           │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 3: LLM ADJUDICATION (if enabled and multiple candidates)        │ │
│  │                                                                         │ │
│  │  Prompt ScenarioFilter LLM with:                                       │ │
│  │    - Current step name + description                                   │ │
│  │    - User intent from context                                          │ │
│  │    - Candidate transitions (condition_text, scores)                    │ │
│  │    - Recent conversation history (last K turns)                        │ │
│  │                                                                         │ │
│  │  Output: selected_transition or "stay" or "exit"                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 4: PRIORITY TIE-BREAKING (fallback)                             │ │
│  │                                                                         │ │
│  │  Sort candidates by:                                                   │ │
│  │    1. transition.priority (higher first)                               │ │
│  │    2. semantic_score (higher first)                                    │ │
│  │    3. definition_order (first defined wins)                            │ │
│  │                                                                         │ │
│  │  Select top if score sufficiently above runner-up (margin >= 0.1)      │ │
│  │  Otherwise: CONTINUE (stay, don't guess)                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STAGE 5: EXIT CHECK                                                   │ │
│  │                                                                         │ │
│  │  If current_step.is_terminal and no transition matched → EXIT          │ │
│  │  If context.scenario_signal == "exit" with high confidence → EXIT      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  Output: ScenarioFilterResult                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class TransitionCandidate(BaseModel):
    """A transition being evaluated for the current turn."""
    transition: StepTransition
    semantic_score: float
    to_step: ScenarioStep


async def evaluate_scenario(
    context: Context,
    scenario: Scenario,
    current_step: ScenarioStep,
    session: Session,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """
    Determine scenario navigation for this turn.

    This is the core ScenarioFilter implementation.
    """

    # Stage 0: Consistency check
    step_ids = {s.id for s in scenario.steps}

    if current_step is None or current_step.id not in step_ids:
        # Step no longer exists (scenario was edited) → relocalize
        return await relocalize_step(context, scenario, session, config)

    # Check for version mismatch (scenario edited since session entered it)
    if (session.active_scenario_version is not None and
        scenario.version != session.active_scenario_version):
        # Log warning - scenario changed mid-session
        logger.warning(
            "scenario_version_mismatch",
            scenario_id=scenario.id,
            session_version=session.active_scenario_version,
            current_version=scenario.version,
        )
        # Step still exists, so continue (but log for observability)

    # Stage 1: Get outgoing transitions
    transitions = current_step.transitions

    if not transitions:
        if current_step.is_terminal:
            return ScenarioFilterResult(
                scenario_action="exit",
                target_step_id=None,
                confidence=1.0,
                reasoning="Terminal step with no outgoing transitions",
            )
        else:
            return ScenarioFilterResult(
                scenario_action="continue",
                target_step_id=None,
                confidence=1.0,
                reasoning="No transitions defined, staying in step",
            )

    # Stage 2: Semantic scoring
    candidates: list[TransitionCandidate] = []
    max_score = 0.0

    for transition in transitions:
        if transition.condition_embedding is None:
            score = 1.0  # No embedding = always consider
        else:
            score = cosine_similarity(
                context.embedding,
                transition.condition_embedding
            )

        max_score = max(max_score, score)

        if score >= config.transition_threshold:
            to_step = scenario.get_step(transition.to_step_id)
            candidates.append(TransitionCandidate(
                transition=transition,
                semantic_score=score,
                to_step=to_step,
            ))

    # Check if we're completely lost (all scores below sanity threshold)
    if max_score < config.sanity_threshold:
        # No transition even remotely matches → consider relocalization
        if should_relocalize(session, config):
            return await relocalize_step(context, scenario, session, config)

    # No candidates above transition threshold → stay
    if not candidates:
        return ScenarioFilterResult(
            scenario_action="continue",
            target_step_id=None,
            confidence=1.0 - max_score,  # Lower confidence if close to threshold
            reasoning=f"No transition above threshold (best: {max_score:.2f})",
        )

    # Single clear candidate
    if len(candidates) == 1:
        return ScenarioFilterResult(
            scenario_action="transition",
            target_step_id=candidates[0].transition.to_step_id,
            confidence=candidates[0].semantic_score,
            reasoning=f"Single matching transition: {candidates[0].transition.condition_text}",
        )

    # Stage 3: LLM adjudication (multiple candidates)
    if config.llm_adjudication_enabled:
        llm_result = await llm_select_transition(
            context=context,
            current_step=current_step,
            candidates=candidates,
            session=session,
            llm_executor=llm_executor,
            config=config,
        )
        if llm_result.scenario_action != "uncertain":
            return llm_result

    # Stage 4: Priority tie-breaking
    candidates.sort(key=lambda c: (
        -c.transition.priority,
        -c.semantic_score,
        transitions.index(c.transition),
    ))

    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None

    # Only transition if clear winner (margin above runner-up)
    if runner_up and (best.semantic_score - runner_up.semantic_score) < config.min_margin:
        return ScenarioFilterResult(
            scenario_action="continue",
            target_step_id=None,
            confidence=0.5,
            reasoning=f"Ambiguous: {best.to_step.name} ({best.semantic_score:.2f}) vs "
                      f"{runner_up.to_step.name} ({runner_up.semantic_score:.2f})",
        )

    return ScenarioFilterResult(
        scenario_action="transition",
        target_step_id=best.transition.to_step_id,
        confidence=best.semantic_score,
        reasoning=f"Priority tie-break: {best.transition.condition_text}",
    )


async def llm_select_transition(
    context: Context,
    current_step: ScenarioStep,
    candidates: list[TransitionCandidate],
    session: Session,
    llm_executor: LLMExecutor,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """Use LLM to select between multiple candidate transitions."""

    options = "\n".join([
        f"{i+1}. \"{c.transition.condition_text}\" → {c.to_step.name}"
        f" (score: {c.semantic_score:.2f})"
        for i, c in enumerate(candidates)
    ])

    prompt = SCENARIO_FILTER_PROMPT.format(
        current_step_name=current_step.name,
        current_step_description=current_step.description or "(no description)",
        user_intent=context.user_intent,
        candidate_transitions=options,
        recent_history=format_recent_history(session, limit=3),
    )

    decision, _raw = await llm_executor.generate_structured(prompt, ScenarioLLMDecision)

    if decision.action == "stay":
        return ScenarioFilterResult(
            scenario_action="continue",
            target_step_id=None,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )
    elif decision.action == "exit":
        return ScenarioFilterResult(
            scenario_action="exit",
            target_step_id=None,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )
    elif decision.action == "transition" and decision.selected_index:
        if 1 <= decision.selected_index <= len(candidates):
            selected = candidates[decision.selected_index - 1]
            return ScenarioFilterResult(
                scenario_action="transition",
                target_step_id=selected.transition.to_step_id,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
            )

    # LLM uncertain
    return ScenarioFilterResult(
        scenario_action="uncertain",
        target_step_id=None,
        confidence=0.0,
        reasoning="LLM could not decide",
    )


class ScenarioLLMDecision(BaseModel):
    """Structured output from ScenarioFilter LLM.

    Note: LLM uses "stay" in its response, which gets mapped to
    ScenarioFilterResult.scenario_action="continue" for consistency
    with the internal enum. This is intentional - "stay" is more
    natural language for the prompt.
    """
    action: str  # "transition" | "stay" | "exit"
    selected_index: int | None  # 1-based, only if action="transition"
    confidence: float  # 0.0 - 1.0
    reasoning: str
```

### ScenarioFilter LLM Prompt

```
You are determining which step a conversation should move to in a multi-step flow.

## Current Step
Name: {current_step_name}
Description: {current_step_description}

## User's Intent
{user_intent}

## Recent Conversation
{recent_history}

## Possible Transitions
{candidate_transitions}

## Instructions
Decide one of:
1. TRANSITION to a specific next step (if user completed current step or explicitly requested)
2. STAY in current step (if user is asking questions or hasn't completed requirements)
3. EXIT the scenario (if user clearly wants to abandon this flow)

Rules:
- Only TRANSITION if the user's message clearly satisfies a transition condition
- If the user is asking questions about the current step → STAY
- If ambiguous between transitions → STAY (don't guess)
- EXIT only if user explicitly abandons ("never mind", "cancel", "forget it")

Respond in JSON:
{
  "action": "transition" | "stay" | "exit",
  "selected_index": 1,  // 1-based index if transitioning, null otherwise
  "confidence": 0.85,
  "reasoning": "User provided order ID #12345 which satisfies the 'order identified' condition"
}
```

---

## Re-localization: Recovering from Inconsistent State

Real-world scenarios require handling edge cases where the stored step becomes invalid:

- **Scenario edited** while session is active (step deleted, transitions changed)
- **User skips ahead** ("I already did KYC, just finalize the transfer")
- **Conversation drifts** and no transition matches for several turns
- **Bug or corruption** causes invalid `active_step_id`

Re-localization is a **recovery mechanism**, not the primary navigation path.

### When to Trigger Re-localization

```python
def should_relocalize(session: Session, config: ScenarioFilterConfig) -> bool:
    """Determine if re-localization should be attempted."""

    # 1. Step doesn't exist in current scenario
    if session.active_step_id not in current_scenario_step_ids:
        return True

    # 2. No transition has scored above sanity threshold for N turns
    low_confidence_turns = count_recent_low_confidence_turns(
        session.step_history,
        threshold=config.sanity_threshold,
        window=config.relocalization_trigger_turns,  # e.g., 3
    )
    if low_confidence_turns >= config.relocalization_trigger_turns:
        return True

    # 3. Explicit signal from context extraction
    if context.scenario_signal == "wrong_step":
        return True

    return False
```

### Re-localization Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RE-LOCALIZATION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Trigger: Consistency check failed OR prolonged low-confidence              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STEP 1: BUILD CANDIDATE SET                                           │ │
│  │                                                                         │ │
│  │  Candidates = union of:                                                │ │
│  │    - Steps reachable within N hops from last known good step           │ │
│  │    - Steps with reachable_from_anywhere=True                           │ │
│  │    - Steps with can_skip=True (if coming from earlier step)            │ │
│  │                                                                         │ │
│  │  Constraint: limit to max_relocalization_candidates (e.g., 10)         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STEP 2: SCORE CANDIDATES                                              │ │
│  │                                                                         │ │
│  │  For each candidate step s:                                            │ │
│  │    - Build descriptor: s.name + s.description + sample transition texts │ │
│  │    - Score = similarity(descriptor_embedding, recent_history_embedding) │ │
│  │                                                                         │ │
│  │  recent_history = last K turns of conversation                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  STEP 3: SELECT BEST MATCH                                             │ │
│  │                                                                         │ │
│  │  If best_score >= relocalization_threshold (e.g., 0.7):                │ │
│  │    - Verify reachability constraint is satisfied                       │ │
│  │    - Set active_step_id = best_step.id                                 │ │
│  │    - Log "scenario.relocalized" event                                  │ │
│  │  Else:                                                                 │ │
│  │    - Exit scenario (can't find valid step)                             │ │
│  │    - Log "scenario.exit_relocalization_failed"                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Re-localization Implementation

```python
async def relocalize_step(
    context: Context,
    scenario: Scenario,
    session: Session,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """
    Attempt to find the correct step when state is inconsistent.

    This is a recovery mechanism, not primary navigation.
    """

    # Step 1: Build candidate set with reachability constraints
    last_good_step_id = find_last_valid_step(session.step_history, scenario)
    candidates = build_relocalization_candidates(
        scenario=scenario,
        from_step_id=last_good_step_id,
        max_hops=config.max_relocalization_hops,  # e.g., 3
        max_candidates=config.max_relocalization_candidates,  # e.g., 10
    )

    if not candidates:
        # No valid candidates → exit scenario
        return ScenarioFilterResult(
            scenario_action="exit",
            target_step_id=None,
            confidence=1.0,
            reasoning="Re-localization failed: no reachable candidates",
            relocalization_triggered=True,
        )

    # Step 2: Score each candidate against recent conversation
    recent_history_text = format_recent_history(session, limit=5)
    history_embedding = await embed(recent_history_text)

    scored_candidates = []
    for step in candidates:
        descriptor = build_step_descriptor(step)
        descriptor_embedding = await embed(descriptor)
        score = cosine_similarity(history_embedding, descriptor_embedding)
        scored_candidates.append((step, score))

    scored_candidates.sort(key=lambda x: -x[1])
    best_step, best_score = scored_candidates[0]

    # Step 3: Apply threshold
    if best_score < config.relocalization_threshold:
        return ScenarioFilterResult(
            scenario_action="exit",
            target_step_id=None,
            confidence=best_score,
            reasoning=f"Re-localization failed: best match {best_step.name} "
                      f"scored {best_score:.2f} < threshold {config.relocalization_threshold}",
            relocalization_triggered=True,
        )

    return ScenarioFilterResult(
        scenario_action="relocalize",
        target_step_id=best_step.id,
        confidence=best_score,
        reasoning=f"Re-localized to {best_step.name} (score: {best_score:.2f})",
        relocalization_triggered=True,
    )


def build_relocalization_candidates(
    scenario: Scenario,
    from_step_id: UUID | None,
    max_hops: int,
    max_candidates: int,
) -> list[ScenarioStep]:
    """Build candidate steps for re-localization with reachability constraints."""

    candidates = set()

    # Always include steps reachable from anywhere
    for step in scenario.steps:
        if step.reachable_from_anywhere:
            candidates.add(step.id)

    # Include steps reachable within max_hops from last good step
    if from_step_id:
        reachable = find_reachable_steps(scenario, from_step_id, max_hops)
        candidates.update(reachable)

    # If no from_step, include entry step and its neighbors
    if not from_step_id:
        candidates.add(scenario.entry_step_id)
        entry_step = scenario.get_step(scenario.entry_step_id)
        for t in entry_step.transitions:
            candidates.add(t.to_step_id)

    # Convert to step objects and limit
    result = [scenario.get_step(sid) for sid in candidates if sid]
    return result[:max_candidates]


def build_step_descriptor(step: ScenarioStep) -> str:
    """Build a text descriptor for a step for embedding comparison."""
    parts = [step.name]
    if step.description:
        parts.append(step.description)
    # Include transition conditions as hints
    for t in step.transitions[:3]:  # Limit to avoid too much text
        parts.append(f"expects: {t.condition_text}")
    return " | ".join(parts)
```

### Reachability Constraints

To prevent chaotic jumps, re-localization is constrained:

```python
class ScenarioStep(BaseModel):
    # ... existing fields ...

    # Re-localization flags
    reachable_from_anywhere: bool = False  # Can relocalize here from any step
    # (useful for "help" or "start over" steps)


class ScenarioFilterConfig(BaseModel):
    """Configuration for scenario step navigation.

    Controls thresholds, LLM adjudication, and re-localization behavior.
    """
    # Entry threshold (for starting a scenario)
    entry_threshold: float = 0.65         # Min score to enter a scenario

    # Transition thresholds (for moving between steps)
    transition_threshold: float = 0.65    # Min score to consider a transition
    sanity_threshold: float = 0.35        # If all below this, something's wrong
    min_margin: float = 0.1               # Required margin over runner-up for tie-break

    # LLM adjudication (used when multiple transitions match)
    llm_adjudication_enabled: bool = True
    model: str = "openrouter/anthropic/claude-3-haiku-20240307"  # Fast model for decisions
    fallback_models: list[str] = []

    # Loop detection
    max_loop_iterations: int = 5          # Max times to revisit same step
    loop_detection_window: int = 10       # Turns to look back for loop check

    # Re-localization (recovery when step is invalid or conversation drifts)
    relocalization_enabled: bool = True
    relocalization_threshold: float = 0.7  # Min score to accept relocalization
    relocalization_trigger_turns: int = 3  # Low-confidence turns before triggering
    max_relocalization_hops: int = 3       # Max graph distance from last good step
    max_relocalization_candidates: int = 10  # Max steps to evaluate

    # History
    step_history_size: int = 50           # Max step visits to retain

    # Scenario update strategy (see scenario-update-methods.md)
    update_strategy: str = "conservative"  # "conservative", "optimistic", "graph_aware"
```

---

## Graph Patterns and Edge Cases

### Pattern 1: Branching (One-to-Many)

```
        ┌─────────┐
        │ Step A  │
        └────┬────┘
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐
│ B     │ │ C     │ │ D     │
└───────┘ └───────┘ └───────┘
```

**Resolution**: All transitions from A are scored. If multiple are above threshold, LLM adjudicates or priority breaks ties.

### Pattern 2: Convergence (Many-to-One)

```
┌───────┐ ┌───────┐ ┌───────┐
│ B     │ │ C     │ │ D     │
└───┬───┘ └───┬───┘ └───┬───┘
    │         │         │
    └─────────┼─────────┘
              ▼
         ┌─────────┐
         │  Step E │
         └─────────┘
```

**Resolution**: Session tracks `active_step_id`, so we always know which branch we're in. Only transitions from the current step are evaluated.

### Pattern 3: Loops (Cycles)

```
┌─────────┐
│ Step A  │◄────────┐
└────┬────┘         │
     │              │
     ▼              │
┌─────────┐         │
│ Step B  │─────────┘
└─────────┘ (retry)
```

**Resolution**: The back-transition has a `condition_text` like "Validation failed" or "User wants to retry". Loop detection prevents infinite cycles:

```python
def check_loop_limit(session: Session, step_id: UUID, config: ScenarioFilterConfig) -> bool:
    """Check if we've visited this step too many times."""
    recent_visits = [
        v for v in session.step_history[-config.loop_detection_window:]
        if v.step_id == step_id
    ]
    return len(recent_visits) < config.max_loop_iterations
```

### Pattern 4: User Skips Ahead

User says: "I already verified my identity last week, can we skip to the transfer?"

**Resolution**:
1. Normal transition evaluation fails (no direct edge)
2. Re-localization triggers (low confidence or explicit signal)
3. Re-localization finds "Transfer" step is reachable (within hop limit or has `can_skip=True`)
4. Session jumps to Transfer step with logged reason

### Pattern 5: Scenario Edited Mid-Session

Admin deletes "Step B" while user is in it.

**Resolution**:
1. Stage 0 consistency check detects `active_step_id` not in scenario
2. Re-localization triggers immediately
3. Finds best matching step from remaining steps
4. Session moves to new step or exits if no match

---

## Session State

```python
class StepVisit(BaseModel):
    """Record of visiting a step in a scenario graph."""
    step_id: UUID
    entered_at: datetime
    turn_number: int
    transition_reason: str | None  # "transition:condition_text" | "relocalize" | "entry"
    confidence: float  # Confidence of the navigation decision


class Session(BaseModel):
    # ... existing fields ...

    # Scenario tracking
    active_scenario_id: UUID | None = None
    active_step_id: UUID | None = None
    step_history: list[StepVisit] = []  # Last N visits (for loop detection, audit)

    # Relocalization tracking
    relocalization_count: int = 0  # Times relocalized in this scenario


# History is bounded to prevent unbounded growth
MAX_STEP_HISTORY = 50
```

---

## Configuration

```toml
[pipeline.scenario_filtering]
# Thresholds
transition_threshold = 0.65      # Min score to consider a transition
sanity_threshold = 0.35          # If all below this, something's wrong
min_margin = 0.1                 # Required margin over runner-up

# LLM settings
llm_adjudication_enabled = true
model = "openrouter/anthropic/claude-3-haiku-20240307"     # Fast model for decisions
fallback_models = ["anthropic/claude-3-haiku-20240307"]

# Loop detection
max_loop_iterations = 5          # Max times to revisit same step
loop_detection_window = 10       # Turns to look back

# Re-localization
relocalization_enabled = true
relocalization_threshold = 0.7
relocalization_trigger_turns = 3
max_relocalization_hops = 3
max_relocalization_candidates = 10

# History
step_history_size = 50
```

---

## Logging and Explainability

Every scenario navigation decision is logged:

```json
{
  "logical_turn_id": "abc123",
  "scenario_filter": {
    "scenario_id": "return_flow",
    "current_step": {"id": "verify_order", "name": "Verify Order"},

    "consistency_check": "passed",

    "transitions_evaluated": 3,
    "candidates_above_threshold": 2,
    "candidates": [
      {"to_step": "eligible", "condition": "Order is eligible", "score": 0.87},
      {"to_step": "not_found", "condition": "Order not found", "score": 0.42}
    ],

    "resolution_method": "single_candidate",
    "action": "transition",
    "target_step": {"id": "eligible", "name": "Eligible for Return"},

    "confidence": 0.87,
    "reasoning": "Single candidate above threshold: 'Order is eligible'",

    "relocalization_triggered": false,
    "loop_check": {"step_visits": 1, "limit": 5, "passed": true}
  }
}
```

For re-localization events:

```json
{
  "logical_turn_id": "def456",
  "scenario_filter": {
    "scenario_id": "kyc_flow",
    "current_step": {"id": "deleted_step", "name": null},

    "consistency_check": "failed_step_not_found",
    "relocalization_triggered": true,

    "relocalization": {
      "reason": "step_deleted",
      "candidates_evaluated": 5,
      "best_match": {"id": "identity_verified", "name": "Identity Verified", "score": 0.82},
      "hop_distance": 2,
      "accepted": true
    },

    "action": "relocalize",
    "target_step": {"id": "identity_verified", "name": "Identity Verified"},
    "confidence": 0.82,
    "reasoning": "Re-localized after step deletion"
  }
}
```

---

## Worked Example: Return Flow with Branch and Recovery

Consider this scenario graph:

```
┌─────────────────┐
│  Identify Order │ (entry)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Verify Order   │
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
┌───────┐ ┌────────┐ ┌─────────┐
│Eligible│ │Too Late│ │Not Found│
└───┬───┘ └───┬────┘ └────┬────┘
    │         │           │
    ▼         └─────┬─────┘
┌─────────┐         │
│ Process │         │
│ Return  │         │
└───┬─────┘         │
    │               │
    └───────┬───────┘
            ▼
    ┌───────────────┐
    │   Confirm     │ (terminal)
    └───────────────┘
```

**Turn 1**: User: "I want to return my order"
- No active scenario → RuleFilter signals "start"
- Entry condition matches "return_flow"
- Action: **Start scenario**, set step to "Identify Order"

**Turn 2**: User: "Order number is 12345"
- Current step: "Identify Order"
- Transition "User provides order ID" scores 0.91
- Action: **Transition** to "Verify Order"

**Turn 3**: User: "Yes that's correct"
- Current step: "Verify Order"
- Transitions: "Eligible" (0.72), "Too Late" (0.31), "Not Found" (0.28)
- Single candidate above threshold
- Action: **Transition** to "Eligible"

**Turn 4**: User: "Actually, can I just get store credit instead?"
- Current step: "Eligible"
- No transition matches (this is a question, not completion)
- Action: **Continue** (stay in "Eligible")

**Turn 5**: User: "OK proceed with the return"
- Current step: "Eligible"
- Transition "User confirms return" scores 0.88
- Action: **Transition** to "Process Return"

**Turn 6**: (Admin deletes "Process Return" step mid-conversation)
- Current step: "Process Return" (deleted!)
- Consistency check **fails**
- Re-localization triggered
- Candidates: "Confirm" (reachable), "Eligible" (1 hop back)
- Best match: "Confirm" (0.75)
- Action: **Relocalize** to "Confirm"
- Log: `scenario.relocalized` event

**Turn 7**: User: "Thanks, I got the confirmation email"
- Current step: "Confirm" (terminal)
- No transitions, terminal step
- Action: **Exit** scenario

---

## Scenario Updates and Customer Data Store

Scenario navigation becomes more complex when scenarios are updated while customers have active sessions (especially on long-lived channels like WhatsApp). Additionally, scenarios often need access to customer data collected in previous sessions or scenarios.

### Scenario Update Reconciliation

When a scenario is updated, active sessions are **reconciled** at the start of each turn. The system analyzes upstream changes and determines the appropriate action:

| Problem | Resolution |
|---------|------------|
| **Deleted step** | Relocate to nearest anchor from step history |
| **New upstream fork** | Evaluate fork condition, teleport if customer is on wrong branch |
| **New upstream data collection** | Gap fill (Profile → Extraction → Ask user) |
| **Skipped required action** | Execute action before continuing |
| **Checkpoint blocks teleport** | Log warning, continue (can't undo irreversible action) |

The reconciliation uses:
- **Anchors**: Steps that exist in both old and new versions
- **Gap fill**: Pull missing data from CustomerDataStore or extract from conversation
- **Checkpoints**: Steps marking irreversible actions (order placed, payment processed) that block teleportation
- **Topological ordering**: Evaluate upstream forks from entry toward current position

**See**: [Scenario Update Methods](../design/scenario-update-methods.md) for full algorithm and implementation.

### Customer Data Store Integration

The **CustomerDataStore** is a persistent, cross-session store of verified facts about a customer:

```python
# Customer provides email in Session 1 (returns scenario)
# Session 2 (support scenario) can access it without re-asking

customer_data = await customer_data_store.get_by_customer_id(tenant_id, customer_id)
email = customer_data.fields.get("email")

if email and email.verified:
    # Use existing verified email
    pass
else:
    # Need to collect/verify
    pass
```

This enables:
- **Gap fill during migration**: New steps requiring data can pull from InterlocutorDataStore
- **Cross-scenario continuity**: Data collected once is available everywhere
- **Verification persistence**: KYC status, verified phone/email survive across sessions

**See**: [Interlocutor Data](../design/customer-profile.md) for the full model.

---

## Templates

**Templates** are pre-written responses for critical points:

```python
class Template(BaseModel):
    """Pre-written response text."""
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str

    # Content with variable placeholders
    text: str  # "Hello {user_name}, your order {order_id} is..."

    # Mode
    mode: TemplateMode

    # Scoping
    scope: RuleScope
    scope_id: UUID | None = None

    # Optional conditions
    conditions: str | None = None  # "refund_status == 'approved'"


class TemplateMode(str, Enum):
    SUGGEST = "suggest"       # LLM can adapt the text
    EXCLUSIVE = "exclusive"   # Use exactly this text, bypass LLM
    FALLBACK = "fallback"     # Use if LLM fails or enforcement triggers
```

| Mode | Behavior |
|------|----------|
| `SUGGEST` | Include in prompt, LLM can adapt |
| `EXCLUSIVE` | Skip LLM entirely, use this exact text |
| `FALLBACK` | Use when enforcement fails or LLM errors |

Templates eliminate hallucination at critical points (legal disclaimers, exact policy statements, error messages).

---

## Context Extraction

The first step in the alignment pipeline extracts structured context from the user message.

### Why Context Extraction?

Raw messages lack context:
- "Yes" → Yes to what?
- "I want to cancel" → Cancel what?
- "That's not right" → What isn't right?

Context extraction synthesizes the message with conversation history to understand actual intent.

### Context Model

```python
class Context(BaseModel):
    """Extracted context from user message."""

    user_intent: str              # What the user wants (full sentence)
    embedding: list[float] | None # Vector representation

    # Extracted entities
    entities: list[str]           # ["order #12345", "laptop"]

    # Sentiment analysis
    sentiment: str | None         # "positive" | "negative" | "neutral" | "frustrated"

    # Topic classification
    topic: str | None             # "refund", "shipping", "product_info"

    # Hints for pipeline
    requires_tool: bool = False   # Likely needs external data

    # Scenario signals
    scenario_signal: str | None   # "start" | "continue" | "exit" | None
    target_scenario: str | None   # Scenario ID if starting
```

### Extraction Modes

| Mode | Provider | Speed | Quality | Use Case |
|------|----------|-------|---------|----------|
| `llm` | LLMExecutor | ~200ms | High | Production (recommended) |
| `embedding_only` | EmbeddingProvider | ~50ms | Medium | Cost-sensitive |
| `disabled` | None | ~0ms | Low | Maximum speed |

---

## LLM Filtering

After retrieval, an LLM judges which rules actually apply.

### Why LLM Filtering?

Vector search finds semantically similar rules, but similarity ≠ applicability:

```
User: "What's your return policy?"

Retrieved rules (by similarity):
1. "Customer asks about refunds" → Check order status  ✗ (no specific order)
2. "Customer asks about policies" → Explain policy     ✓ (correct)
3. "Customer wants to return" → Start return flow      ✗ (asking, not returning)
```

An LLM can distinguish between these cases.

### Rule Filter Decision

```python
class RuleFilterDecision(BaseModel):
    """LLM rule filtering decision.

    Note: This is the RuleFilter output, separate from ScenarioFilter.
    RuleFilter only decides which rules apply - scenario navigation
    is handled by the dedicated ScenarioFilter (see above).
    """
    applicable_rule_indices: list[int]  # 1-based indices
    scenario_signal: str | None         # Coarse hint: "start" | "exit" | None
    reasoning: str                      # Brief explanation


class RuleFilterResult(BaseModel):
    """Result of rule filtering."""
    matched_rules: list[MatchedRule]
    scenario_signal: str | None  # Passed to ScenarioFilter as hint
    reasoning: str
```

### Enabling/Disabling

```toml
[pipeline.rule_filtering]
enabled = true               # Set to false to skip
model = "openrouter/anthropic/claude-3-haiku-20240307" # Fast model for yes/no
fallback_models = ["anthropic/claude-3-haiku-20240307"]
batch_size = 5               # Batch size for filtering
```

When disabled, all retrieved rules (after reranking) are used.

---

## Tools

**Tools** are side-effect actions attached to Rules:

```python
class Tool(BaseModel):
    """An executable action."""
    id: str
    name: str
    description: str

    # Schema
    input_schema: dict       # JSON Schema for inputs
    output_schema: dict      # JSON Schema for outputs

    # Execution
    timeout_ms: int = 5000
    async_execution: bool = False

    # Access control
    tenant_ids: list[UUID] | None = None  # None = all tenants
```

**Key principle**: Tools are never free-floating. They only execute when their attached Rule matches.

```python
# Tool attached to rule
rule = Rule(
    condition_text="Customer asks about order status",
    action_text="Look up the order and report status",
    attached_tool_ids=["check_order_status"]
)
```

---

## Enforcement

After LLM generation, Focal validates compliance with hard constraint rules.

### Enforcement Flow

```
Response
    │
    ▼
┌─────────────────────────────┐
│  Check hard constraints     │
│  (rules with is_hard_constraint=True)
└─────────────────────────────┘
    │
    ├── All pass → Return response
    │
    ▼
┌─────────────────────────────┐
│  Regenerate with stronger   │
│  prompt emphasizing rule    │
└─────────────────────────────┘
    │
    ├── Passes → Return new response
    │
    ▼
┌─────────────────────────────┐
│  Use FALLBACK template      │
│  (guaranteed safe)          │
└─────────────────────────────┘
```

### Self-Critique (Optional)

LLM evaluates its own answer:

```python
if config.self_critique_enabled:
    critique, _raw = await llm.generate_structured(
        prompt=SELF_CRITIQUE_PROMPT.format(
            response=response,
            rules=[r.action_text for r in matched_rules]
        ),
        schema=CritiqueResult
    )

    if not critique.passed:
        response = await regenerate_with_feedback(response, critique.feedback)
```

---

## Configuration

### Per-Step Provider Configuration

```toml
# Context Extraction
[pipeline.context_extraction]
mode = "llm"                           # "llm" | "embedding_only" | "disabled"
model = "openrouter/anthropic/claude-3-haiku-20240307"
fallback_models = ["anthropic/claude-3-haiku-20240307"]
history_turns = 5                      # How much history to include

# Retrieval
[pipeline.retrieval]
embedding_provider = "default"
top_k_per_scope = 10                   # Candidates per scope level
include_memory = true

# Reranking
[pipeline.reranking]
enabled = true
rerank_provider = "default"
top_k = 10                             # Final candidates after rerank

# Rule Filtering
[pipeline.rule_filtering]
enabled = true
model = "openrouter/anthropic/claude-3-haiku-20240307"
fallback_models = ["anthropic/claude-3-haiku-20240307"]
batch_size = 5

# Response Generation
[pipeline.generation]
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"
fallback_models = ["anthropic/claude-sonnet-4-5-20250514", "openai/gpt-4o"]
temperature = 0.7
max_tokens = 1024

# Enforcement
[pipeline.enforcement]
enabled = true
self_critique_enabled = false
llm_judge_models = ["openrouter/anthropic/claude-3-haiku-20240307"]
max_retries = 1
```

### Deployment Profiles

**Minimal (Fastest)**
```toml
[pipeline.context_extraction]
mode = "disabled"

[pipeline.reranking]
enabled = false

[pipeline.rule_filtering]
enabled = false

[pipeline.generation]
model = "openrouter/anthropic/claude-3-haiku-20240307"

[pipeline.enforcement]
self_critique_enabled = false
```

**Balanced (Recommended)**
```toml
[pipeline.context_extraction]
mode = "llm"
model = "openrouter/anthropic/claude-3-haiku-20240307"

[pipeline.reranking]
enabled = true

[pipeline.rule_filtering]
enabled = true

[pipeline.generation]
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"
```

**Maximum Quality**
```toml
[pipeline.context_extraction]
mode = "llm"
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"

[pipeline.reranking]
enabled = true

[pipeline.rule_filtering]
enabled = true
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"

[pipeline.generation]
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"

[pipeline.enforcement]
self_critique_enabled = true
```

---

## Logging and Explainability

See [observability.md](./observability.md) for the overall logging, tracing, and metrics architecture. This section covers alignment engine-specific structured log output.

Every turn logs the full alignment decision:

```json
{
  "logical_turn_id": "abc123",
  "timestamp": "2025-01-15T10:30:00Z",
  "tenant_id": "tenant_1",
  "session_id": "session_456",

  "input": {
    "message": "I want a refund",
    "history_turns": 3
  },

  "context_extraction": {
    "user_intent": "Customer wants to return/refund a recent purchase",
    "entities": ["refund"],
    "sentiment": "neutral",
    "scenario_signal": "start"
  },

  "retrieval": {
    "rules_retrieved": 15,
    "scenarios_checked": 3,
    "memory_episodes": 5
  },

  "filtering": {
    "rules_before": 15,
    "rules_after": 3,
    "scenario_decision": "start",
    "scenario_target": "return_flow"
  },

  "matched_rules": [
    {"id": "rule_1", "name": "refund_check", "score": 0.92}
  ],

  "tools_called": [
    {"name": "check_order_status", "input": {"order_id": "12345"}, "output": {...}}
  ],

  "scenario": {
    "before": null,
    "after": {"id": "return_flow", "step": "identify_order"}
  },

  "generation": {
    "template_used": null,
    "llm_called": true,
    "tokens_used": 150
  },

  "enforcement": {
    "triggered": false
  },

  "output": "I found your order #12345. Let me check if it's eligible for a refund..."
}
```

This enables:
- "Why did the agent say X?" → Check matched_rules, generation
- "Why was this tool called?" → Rule attachment in matched_rules
- "How did we get to this step?" → scenario.before/after
- "Was context understood?" → context_extraction
