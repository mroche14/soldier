# Phase 9: Generation - Implementation Checklist

> **Reference Documents**:
> - `docs/focal_turn_pipeline/README.md` - Section on Phase 9 (P9.1-P9.5)
> - `docs/focal_turn_pipeline/analysis/gap_analysis.md` - Phase 9 gaps
> - `IMPLEMENTATION_PLAN.md` - Phase 10 (Alignment Pipeline - Execution & Generation)

---

## Phase Overview

**Goal**: Produce natural language responses using LLM, format for specific channels (WhatsApp, email, SMS), and determine semantic outcome categories.

**Current State**: Basic generation exists but missing:
- ResponsePlan input from Phase 8
- Semantic category output (KNOWLEDGE_GAP, OUT_OF_SCOPE, etc.)
- Channel-specific formatting
- TurnOutcome model with resolution determination

**Key Changes from Current Implementation**:
1. Generator now receives `ResponsePlan` (not just rules) from Phase 8
2. LLM outputs both response text AND semantic categories
3. Post-processing formats response for channel (WhatsApp, email, etc.)
4. `TurnOutcome` model tracks resolution and all categories

---

## 1. Models to Create/Update

### 1.1 OutcomeCategory Enum

- [x] **Create OutcomeCategory enum**
  - File: `focal/alignment/models/outcome.py`
  - Action: Create new file
  - **Implemented**: Already exists with all required categories (PIPELINE and GENERATION categories)
  - Details:
    ```python
    from enum import Enum

    class OutcomeCategory(str, Enum):
        """Semantic categories describing turn outcome.

        Categories are set by different pipeline phases:
        - PIPELINE categories: Set by Phases 7, 8, 10
        - GENERATION categories: Set by LLM in Phase 9
        """
        # Pipeline-set categories
        AWAITING_USER_INPUT = "AWAITING_USER_INPUT"  # Phase 8: Need info from user
        SYSTEM_ERROR = "SYSTEM_ERROR"                # Phase 7: Tool execution failed
        POLICY_RESTRICTION = "POLICY_RESTRICTION"    # Phase 10: Blocked by enforcement

        # LLM-set categories (from generation)
        KNOWLEDGE_GAP = "KNOWLEDGE_GAP"              # "I should know but don't"
        CAPABILITY_GAP = "CAPABILITY_GAP"            # "I can't do that action"
        OUT_OF_SCOPE = "OUT_OF_SCOPE"                # "Not what this business handles"
        SAFETY_REFUSAL = "SAFETY_REFUSAL"            # "Refusing for safety"
        ANSWERED = "ANSWERED"                         # Successfully answered
    ```

### 1.2 TurnOutcome Model

- [x] **Create TurnOutcome model**
  - File: `focal/alignment/models/outcome.py`
  - Action: Add to new file
  - **Implemented**: Already exists with resolution, categories, escalation_reason, blocking_rule_id
  - Details:
    ```python
    from pydantic import BaseModel, Field

    class TurnOutcome(BaseModel):
        """Final outcome of a turn with resolution and categories.

        Categories accumulate throughout the pipeline:
        - Phase 7 (Tool Execution): Appends SYSTEM_ERROR if tool failed
        - Phase 8 (Response Planning): Appends AWAITING_USER_INPUT if ASK mode
        - Phase 9 (Generation): LLM appends semantic categories
        - Phase 10 (Enforcement): Appends POLICY_RESTRICTION if blocked

        Resolution is determined in P9.5 based on categories and state.
        """
        resolution: str = Field(
            ...,
            description="Overall turn resolution: ANSWERED, PARTIAL, REDIRECTED, ERROR, BLOCKED"
        )
        categories: list[OutcomeCategory] = Field(
            default_factory=list,
            description="All semantic categories from pipeline and LLM"
        )

        # Additional metadata
        escalation_reason: str | None = Field(
            default=None,
            description="Reason if resolution is REDIRECTED"
        )
        blocking_rule_id: str | None = Field(
            default=None,
            description="Rule ID if resolution is BLOCKED"
        )
    ```

### 1.3 Update GenerationResult Model

- [x] **Add LLM categories to GenerationResult**
  - File: `focal/alignment/generation/models.py`
  - Action: Modify existing model
  - **Implemented**: GenerationResult already has llm_categories, channel_formatted, and channel fields
  - Details: Add fields:
    ```python
    from focal.alignment.models.outcome import OutcomeCategory

    class GenerationResult(BaseModel):
        # ... existing fields ...

        # New fields for Phase 9
        llm_categories: list[OutcomeCategory] = Field(
            default_factory=list,
            description="Semantic categories output by LLM"
        )
        channel_formatted: bool = Field(
            default=False,
            description="Whether response was formatted for specific channel"
        )
        channel: str | None = Field(
            default=None,
            description="Target channel if formatted (whatsapp, email, etc.)"
        )
    ```

### 1.4 ResponsePlan Model (Dependency from Phase 8)

- [x] **Verify ResponsePlan model exists (blocker)**
  - File: `focal/alignment/planning/models.py`
  - Action: Document dependency
  - **Implemented**: ResponsePlan exists with global_response_type, template_ids, must_include, must_avoid, etc.
  - Details: Generation will receive ResponsePlan input. If Phase 8 not implemented:
    - Create stub ResponsePlan with `response_type`, `contributions`, `must_include`, `must_avoid`
    - Or pass `None` and handle gracefully in generator
    - Mark as technical debt to integrate fully when Phase 8 is complete

---

## 2. Prompt Template Updates

### 2.1 Convert to Jinja2 Template

- [ ] **Convert system_prompt.txt to Jinja2**
  - File: `focal/alignment/generation/prompts/response_generator.jinja2`
  - Action: Create (rename from system_prompt.txt)
  - Details:
    - Convert from string formatting to Jinja2 syntax
    - Add ResponsePlan variables: `{{ response_plan.response_type }}`, `{{ response_plan.contributions }}`
    - Add semantic categories instruction:
    ```jinja2
    ## Response Format
    You must output a JSON object with two fields:

    {
      "response": "your natural language response here",
      "categories": ["ANSWERED"]  // or ["KNOWLEDGE_GAP"], ["OUT_OF_SCOPE"], etc.
    }

    ## Semantic Categories
    Include one or more of these categories if they apply:
    - ANSWERED: You successfully answered the question
    - KNOWLEDGE_GAP: You should know this but don't have the information
    - CAPABILITY_GAP: You cannot perform the requested action
    - OUT_OF_SCOPE: The request is outside your business domain
    - SAFETY_REFUSAL: You're refusing for safety/policy reasons

    {% if response_plan %}
    ## Response Guidance
    Response Type: {{ response_plan.response_type }}
    {% if response_plan.must_include %}
    Must Include: {{ response_plan.must_include | join(", ") }}
    {% endif %}
    {% if response_plan.must_avoid %}
    Must Avoid: {{ response_plan.must_avoid | join(", ") }}
    {% endif %}
    {% endif %}
    ```

### 2.2 Create Template Loader

- [ ] **Create Jinja2 template loader**
  - File: `focal/alignment/generation/template_loader.py`
  - Action: Create new file
  - Details:
    ```python
    import jinja2
    from pathlib import Path

    class TemplateLoader:
        """Loads and renders Jinja2 prompt templates."""

        def __init__(self):
            template_dir = Path(__file__).parent / "prompts"
            self.env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(template_dir)),
                autoescape=jinja2.select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True,
            )

        def render(self, template_name: str, **context) -> str:
            """Render a template with given context."""
            template = self.env.get_template(template_name)
            return template.render(**context)
    ```

### 2.3 Update PromptBuilder

- [ ] **Add ResponsePlan to PromptBuilder**
  - File: `focal/alignment/generation/prompt_builder.py`
  - Action: Modify
  - Details:
    - Add `response_plan` parameter to `build_system_prompt()`
    - Use TemplateLoader instead of reading .txt files
    - Pass ResponsePlan variables to template

---

## 3. Channel Formatting

### 3.1 Create Channel Formatter Interface

- [ ] **Create ChannelFormatter abstract class**
  - File: `focal/alignment/generation/formatters/__init__.py`
  - Action: Create new directory and file
  - Details:
    ```python
    from abc import ABC, abstractmethod

    class ChannelFormatter(ABC):
        """Formats responses for specific communication channels."""

        @abstractmethod
        def format(self, response: str) -> str:
            """Format response for the channel.

            Args:
                response: Raw LLM response

            Returns:
                Channel-formatted response
            """
            pass

        @property
        @abstractmethod
        def channel_name(self) -> str:
            """Name of the channel."""
            pass
    ```

### 3.2 WhatsApp Formatter

- [ ] **Implement WhatsAppFormatter**
  - File: `focal/alignment/generation/formatters/whatsapp.py`
  - Action: Create
  - Details:
    - Convert markdown to plain text
    - Replace `**bold**` with `*bold*` (WhatsApp syntax)
    - Split long messages (WhatsApp 4096 char limit)
    - Remove excessive line breaks

### 3.3 Email Formatter

- [ ] **Implement EmailFormatter**
  - File: `focal/alignment/generation/formatters/email.py`
  - Action: Create
  - Details:
    - Preserve markdown formatting
    - Add proper greeting/signature if not present
    - Handle HTML conversion if needed

### 3.4 SMS Formatter

- [ ] **Implement SMSFormatter**
  - File: `focal/alignment/generation/formatters/sms.py`
  - Action: Create
  - Details:
    - Strip all formatting
    - Enforce 160 character limit (split to multiple if needed)
    - Convert links to short URLs

### 3.5 Web/Slack Formatter (Default)

- [ ] **Implement DefaultFormatter**
  - File: `focal/alignment/generation/formatters/default.py`
  - Action: Create
  - Details:
    - Pass through markdown as-is
    - Minimal transformations

### 3.6 Formatter Factory

- [ ] **Create formatter factory**
  - File: `focal/alignment/generation/formatters/__init__.py`
  - Action: Add to existing file
  - Details:
    ```python
    def get_formatter(channel: str) -> ChannelFormatter:
        """Get formatter for channel name.

        Args:
            channel: Channel name (whatsapp, email, sms, web, slack)

        Returns:
            Appropriate formatter instance
        """
        formatters = {
            "whatsapp": WhatsAppFormatter(),
            "email": EmailFormatter(),
            "sms": SMSFormatter(),
            "web": DefaultFormatter(),
            "slack": DefaultFormatter(),
        }
        return formatters.get(channel.lower(), DefaultFormatter())
    ```

---

## 4. LLM Output Parsing

### 4.1 Structured Output Parser

- [ ] **Create LLM output parser**
  - File: `focal/alignment/generation/parser.py`
  - Action: Create
  - Details:
    ```python
    import json
    from pydantic import BaseModel, ValidationError
    from focal.alignment.models.outcome import OutcomeCategory
    from focal.observability.logging import get_logger

    logger = get_logger(__name__)

    class LLMOutput(BaseModel):
        """Structured output from generation LLM."""
        response: str
        categories: list[str] = []

    def parse_llm_output(raw_output: str) -> tuple[str, list[OutcomeCategory]]:
        """Parse LLM output into response and categories.

        Args:
            raw_output: Raw string from LLM

        Returns:
            (response_text, categories)

        Handles both JSON and plain text fallback.
        """
        # Try to parse as JSON first
        try:
            data = json.loads(raw_output)
            output = LLMOutput(**data)

            # Convert category strings to enum
            categories = []
            for cat_str in output.categories:
                try:
                    categories.append(OutcomeCategory(cat_str))
                except ValueError:
                    logger.warning("unknown_category", category=cat_str)

            return output.response, categories

        except (json.JSONDecodeError, ValidationError) as e:
            # Fallback: treat entire output as response
            logger.debug("llm_output_not_json", error=str(e))
            return raw_output, [OutcomeCategory.ANSWERED]
    ```

### 4.2 Update Generator to Parse Output

- [ ] **Add parsing to ResponseGenerator.generate()**
  - File: `focal/alignment/generation/generator.py`
  - Action: Modify
  - Details:
    - Import parser
    - Parse LLM response: `response, categories = parse_llm_output(llm_response.content)`
    - Store categories in GenerationResult

---

## 5. Resolution Determination (P9.5)

### 5.1 Resolution Logic

- [ ] **Create resolution determiner**
  - File: `focal/alignment/generation/resolution.py`
  - Action: Create
  - Details:
    ```python
    from focal.alignment.models.outcome import OutcomeCategory, TurnOutcome

    def determine_resolution(
        categories: list[OutcomeCategory],
        response_type: str | None = None,
    ) -> str:
        """Determine turn resolution from categories and response type.

        Args:
            categories: All categories accumulated during pipeline
            response_type: From ResponsePlan (ASK, ANSWER, ESCALATE, etc.)

        Returns:
            Resolution: ANSWERED, PARTIAL, REDIRECTED, ERROR, BLOCKED
        """
        # Priority order (earlier wins)
        if OutcomeCategory.POLICY_RESTRICTION in categories:
            return "BLOCKED"

        if OutcomeCategory.SYSTEM_ERROR in categories:
            return "ERROR"

        if response_type == "ESCALATE":
            return "REDIRECTED"

        if OutcomeCategory.AWAITING_USER_INPUT in categories:
            return "PARTIAL"

        if OutcomeCategory.ANSWERED in categories:
            return "ANSWERED"

        # Default: if none of the above, consider it answered
        return "ANSWERED"
    ```

### 5.2 Build TurnOutcome

- [ ] **Create TurnOutcome builder**
  - File: `focal/alignment/generation/resolution.py`
  - Action: Add to existing file
  - Details:
    ```python
    def build_turn_outcome(
        categories: list[OutcomeCategory],
        response_type: str | None = None,
        escalation_reason: str | None = None,
        blocking_rule_id: str | None = None,
    ) -> TurnOutcome:
        """Build complete TurnOutcome from pipeline state.

        Args:
            categories: All categories from pipeline and LLM
            response_type: From ResponsePlan
            escalation_reason: If escalated, why
            blocking_rule_id: If blocked, which rule

        Returns:
            Complete TurnOutcome
        """
        resolution = determine_resolution(categories, response_type)

        return TurnOutcome(
            resolution=resolution,
            categories=categories,
            escalation_reason=escalation_reason,
            blocking_rule_id=blocking_rule_id,
        )
    ```

---

## 6. Generator Updates

### 6.1 Update ResponseGenerator.generate() Signature

- [ ] **Add new parameters to generate()**
  - File: `focal/alignment/generation/generator.py`
  - Action: Modify
  - Details: Add parameters:
    ```python
    async def generate(
        self,
        context: Context,
        matched_rules: list[MatchedRule],
        history: list[Turn] | None = None,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
        templates: list[Template] | None = None,
        variables: dict[str, str] | None = None,
        response_plan: ResponsePlan | None = None,  # NEW
        channel: str = "web",                        # NEW
    ) -> GenerationResult:
    ```

### 6.2 Update Generation Flow

- [ ] **Update generate() implementation**
  - File: `focal/alignment/generation/generator.py`
  - Action: Modify
  - Details:
    1. Pass `response_plan` to prompt builder
    2. Parse LLM output for categories: `response, llm_categories = parse_llm_output(llm_response.content)`
    3. Apply channel formatting: `formatter = get_formatter(channel)` → `formatted = formatter.format(response)`
    4. Return GenerationResult with `llm_categories`, `channel`, `channel_formatted=True`

---

## 7. Configuration Updates

### 7.1 Generation Config Enhancement

- [ ] **Add channel formatting config**
  - File: `config/default.toml`
  - Action: Modify
  - Details: Add to `[pipeline.generation]` section:
    ```toml
    [pipeline.generation]
    enabled = true
    model = "openrouter/anthropic/claude-sonnet-4-5-20250514"
    fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
    temperature = 0.7
    max_tokens = 1024
    timeout_ms = 10000

    # Structured output for categories
    structured_output = true

    # Channel formatting
    [pipeline.generation.channels]
    whatsapp_max_length = 4096
    sms_max_length = 160
    email_add_signature = true
    ```

### 7.2 Configuration Model

- [ ] **Update GenerationConfig model**
  - File: `focal/config/models/pipeline.py`
  - Action: Modify
  - Details: Add fields:
    ```python
    class GenerationConfig(BaseModel):
        # ... existing fields ...

        structured_output: bool = True
        channels: dict[str, Any] = Field(default_factory=dict)
    ```

---

## 8. Integration with AlignmentEngine

### 8.1 Update Engine to Pass ResponsePlan

- [ ] **Pass ResponsePlan from Phase 8 to Generation**
  - File: `focal/alignment/engine.py`
  - Action: Modify
  - Details:
    - After Phase 8 (Response Planning), extract `response_plan`
    - Pass to `response_generator.generate(response_plan=response_plan)`
    - If Phase 8 not implemented, pass `None`

### 8.2 Accumulate Categories Throughout Pipeline

- [ ] **Track categories in AlignmentResult**
  - File: `focal/alignment/result.py`
  - Action: Modify
  - Details:
    - Add `outcome_categories: list[OutcomeCategory] = []` to AlignmentResult
    - Phase 7: Append SYSTEM_ERROR if tool failed
    - Phase 8: Append AWAITING_USER_INPUT if ASK mode
    - Phase 9: Append LLM categories
    - Phase 10: Append POLICY_RESTRICTION if blocked

### 8.3 Build TurnOutcome in Engine

- [ ] **Create TurnOutcome after enforcement**
  - File: `focal/alignment/engine.py`
  - Action: Modify
  - Details:
    - After Phase 10 (Enforcement), call `build_turn_outcome()`
    - Store in AlignmentResult
    - Include in TurnRecord

---

## 9. Tests Required

### 9.1 Unit Tests - Models

- [ ] **Test OutcomeCategory enum**
  - File: `tests/unit/alignment/models/test_outcome.py`
  - Action: Create
  - Tests:
    - Enum values are correct strings
    - Can convert from string to enum

- [ ] **Test TurnOutcome model**
  - File: `tests/unit/alignment/models/test_outcome.py`
  - Action: Add to file
  - Tests:
    - Valid construction with all fields
    - Categories list is mutable
    - Optional fields can be None

### 9.2 Unit Tests - Formatters

- [ ] **Test WhatsAppFormatter**
  - File: `tests/unit/alignment/generation/formatters/test_whatsapp.py`
  - Action: Create
  - Tests:
    - Converts markdown bold to WhatsApp format
    - Splits messages exceeding 4096 chars
    - Removes excessive whitespace

- [ ] **Test EmailFormatter**
  - File: `tests/unit/alignment/generation/formatters/test_email.py`
  - Action: Create
  - Tests:
    - Preserves markdown
    - Adds greeting if missing

- [ ] **Test SMSFormatter**
  - File: `tests/unit/alignment/generation/formatters/test_sms.py`
  - Action: Create
  - Tests:
    - Strips all formatting
    - Enforces 160 char limit
    - Handles multi-part messages

### 9.3 Unit Tests - Parser

- [ ] **Test LLM output parser**
  - File: `tests/unit/alignment/generation/test_parser.py`
  - Action: Create
  - Tests:
    - Parses valid JSON with categories
    - Handles malformed JSON (fallback to plain text)
    - Converts unknown categories gracefully
    - Handles empty categories list

### 9.4 Unit Tests - Resolution

- [ ] **Test resolution determiner**
  - File: `tests/unit/alignment/generation/test_resolution.py`
  - Action: Create
  - Tests:
    - POLICY_RESTRICTION → BLOCKED
    - SYSTEM_ERROR → ERROR
    - ESCALATE response type → REDIRECTED
    - AWAITING_USER_INPUT → PARTIAL
    - ANSWERED → ANSWERED
    - Empty categories → ANSWERED (default)

- [ ] **Test TurnOutcome builder**
  - File: `tests/unit/alignment/generation/test_resolution.py`
  - Action: Add to file
  - Tests:
    - Builds complete TurnOutcome with all fields
    - Includes escalation_reason when redirected
    - Includes blocking_rule_id when blocked

### 9.5 Unit Tests - Generator

- [ ] **Test ResponseGenerator with categories**
  - File: `tests/unit/alignment/generation/test_generator.py`
  - Action: Modify existing tests
  - Tests:
    - Parses LLM JSON output correctly
    - Extracts categories from LLM response
    - Applies channel formatting
    - Handles ResponsePlan input
    - Falls back gracefully when LLM doesn't return JSON

### 9.6 Integration Tests

- [ ] **Test full generation flow with categories**
  - File: `tests/integration/alignment/test_generation_flow.py`
  - Action: Create
  - Tests:
    - End-to-end: prompt → LLM → parse → format → TurnOutcome
    - Mock LLM returns JSON with categories
    - Different channels produce different formats
    - Categories accumulate through pipeline phases

---

## 10. Documentation Updates

### 10.1 Update CLAUDE.md

- [ ] **Document Phase 9 implementation**
  - File: `CLAUDE.md`
  - Action: Modify
  - Details:
    - Add section on channel formatters
    - Document TurnOutcome model usage
    - Note ResponsePlan dependency from Phase 8

### 10.2 Update API Documentation

- [ ] **Document channel parameter**
  - File: API route files
  - Action: Modify
  - Details:
    - Add `channel` field to ChatRequest
    - Document supported channels: whatsapp, email, sms, web, slack

---

## Dependencies

### Blockers (Must Complete First)
- **Phase 8 (Response Planning)**: Generation receives `ResponsePlan` input
  - If Phase 8 not implemented, create stub ResponsePlan or pass None
  - Mark as technical debt for full integration later

### Enables (Can Complete After)
- **Phase 10 (Enforcement)**: Uses TurnOutcome model to track violations
- **Phase 11 (Persistence)**: Stores TurnOutcome in TurnRecord

---

## Implementation Order

1. **Models** (1.1-1.4) - Foundation
2. **Parser & Resolution** (4.1-4.2, 5.1-5.2) - Core logic
3. **Channel Formatters** (3.1-3.6) - Output transformation
4. **Prompt Templates** (2.1-2.3) - LLM task updates
5. **Generator Updates** (6.1-6.2) - Wire everything together
6. **Configuration** (7.1-7.2) - Enable/configure features
7. **Engine Integration** (8.1-8.3) - Connect to pipeline
8. **Tests** (9.1-9.6) - Validate implementation

---

## Success Criteria

- [ ] LLM outputs structured JSON with response + categories
- [ ] Parser extracts semantic categories from LLM output
- [ ] Channel formatters adapt responses for WhatsApp, email, SMS
- [ ] TurnOutcome model tracks resolution and all categories
- [ ] Categories accumulate through pipeline phases (7, 8, 9, 10)
- [ ] Resolution determined correctly based on categories
- [ ] All unit tests pass with >85% coverage
- [ ] Integration tests validate end-to-end flow

---

## Notes

- **Jinja2 Migration**: All prompt templates should use Jinja2 (not `.txt` with `str.format()`)
- **Async All the Way**: All LLM calls and formatting should be async
- **Graceful Degradation**: If LLM doesn't return JSON, fall back to plain text with ANSWERED category
- **Channel Default**: Default to "web" channel if not specified
- **ResponsePlan Stub**: If Phase 8 not ready, create minimal stub or pass None and handle gracefully
