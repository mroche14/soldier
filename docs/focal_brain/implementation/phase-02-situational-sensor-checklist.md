# Phase 2: Situational Sensor Implementation Checklist

> **Reference Documents**:
> - `docs/focal_brain/README.md` - Sections 2 and 3.4
> - `docs/focal_brain/analysis/gap_analysis.md` - Phase 2 analysis
> - `CLAUDE.md` - LLM Task Pattern, Configuration System
>
> **Dependencies**:
> - **Requires**: Phase 1 (Context Loading) - TurnContext, InterlocutorDataStore, GlossaryItem
> - **Blocks**: Phase 3 (Customer Data Update) - Needs SituationalSnapshot with candidate_variables
>
> **Goal**: Implement schema-aware, glossary-aware context extraction that produces `SituationalSnapshot` with candidate variables for customer data updates.

---

## Overview

Phase 2 replaces the current basic `ContextExtractor` (which outputs `Context`) with a sophisticated **Situational Sensor** that:

1. **Shows LLM a masked view** of customer data schema (what fields exist, not their values)
2. **Provides domain glossary** for business-specific terminology
3. **Extracts candidate variables** from user messages with proper scoping
4. **Detects intent changes** and conversation evolution
5. **Outputs structured snapshot** that drives Phase 3 customer data updates

### Current State vs. Target

| Component | Current | Target |
|-----------|---------|--------|
| **Input to LLM** | Message + last 5 turns | Message + K turns + InterlocutorSchemaMask + GlossaryView |
| **Output Model** | `Context` (intent, entities, sentiment) | `SituationalSnapshot` (candidate_variables, intent evolution) |
| **Prompt Format** | `.txt` with `str.format()` | `.jinja2` with Jinja2 Environment |
| **Configuration** | Hardcoded K=5 | Configurable via `[brain.situational_sensor]` |
| **Variable Extraction** | None | Schema-aware extraction to `candidate_variables` |

---

## Phase 2.1: Core Models

> **IMPORTANT**: InterlocutorDataField, VariableEntry, and InterlocutorDataStore are renamed Profile models from Phase 1.
> Do NOT create duplicate models. These should already exist after Phase 1 renames.

### Prerequisites from Phase 1 (Already Complete)

- [x] **InterlocutorDataField** (renamed from ProfileFieldDefinition)
  - File: `ruche/domain/interlocutor/models.py`
  - Fields: `name`, `scope`, `persist`, `value_type`, etc.
  - Note: Use `name` field (not `key`) per existing convention

- [x] **VariableEntry** (renamed from ProfileField)
  - File: `ruche/domain/interlocutor/models.py`
  - Fields: `name`, `value`, `history`, `confidence`, etc.

- [x] **InterlocutorDataStore** (renamed from CustomerProfile)
  - File: `ruche/domain/interlocutor/models.py`
  - Contains: `fields: dict[str, VariableEntry]`

### New Models for Phase 2 (Create These)

- [x] **Create InterlocutorSchemaMask model**
  - File: `ruche/brains/focal/context/customer_schema_mask.py`
  - Action: Created (already existed from Phase 1)
  - **Implemented**: Model exists with `InterlocutorSchemaMaskEntry` and `InterlocutorSchemaMask`
  - Models:
    ```python
    class InterlocutorSchemaMaskEntry(BaseModel):
        scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
        type: str
        exists: bool  # True if InterlocutorDataStore has value for this key
        display_name: str | None = None

    class InterlocutorSchemaMask(BaseModel):
        """Privacy-safe view for LLM showing schema structure without actual values."""
        variables: dict[str, InterlocutorSchemaMaskEntry]

    def build_customer_schema_mask(
        interlocutor_data: InterlocutorDataStore,
        schema: list[InterlocutorDataField],
    ) -> InterlocutorSchemaMask:
        """Build mask from store and schema."""
        variables = {}
        for field_def in schema:
            variables[field_def.name] = InterlocutorSchemaMaskEntry(
                scope=field_def.scope,
                type=field_def.value_type,
                exists=field_def.name in interlocutor_data.fields,
                display_name=field_def.display_name,
            )
        return InterlocutorSchemaMask(variables=variables)
    ```

- [x] **GlossaryItem** (from Phase 1)
  - File: `ruche/brains/focal/models/glossary.py`
  - Note: Already exists from Phase 1
  - **Implemented**: Model exists with all required fields

### Situational Sensor Output Models

- [x] **Create CandidateVariableInfo model**
  - File: `ruche/brains/focal/context/situational_snapshot.py`
  - Action: Created new file
  - Model: `CandidateVariableInfo`
  - **Implemented**: Created with `value`, `scope`, `is_update` fields
    ```python
    class CandidateVariableInfo(BaseModel):
        value: Any
        scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
        is_update: bool = False  # True if updating existing value
    ```
  - Details: Extracted variable from user message with scoping metadata

- [x] **Create SituationalSnapshot model**
  - File: `ruche/brains/focal/context/situational_snapshot.py`
  - Action: Added to same file
  - Model: `SituationalSnapshot`
  - **Implemented**: Created with all fields from spec including `candidate_variables`
    ```python
    class SituationalSnapshot(BaseModel):
        # Language detection
        language: str  # ISO 639-1 code (e.g., "en", "es")

        # Intent evolution
        previous_intent_label: str | None
        intent_changed: bool
        new_intent_label: str | None
        new_intent_text: str | None

        # Conversation state
        topic_changed: bool
        tone: str  # "neutral", "frustrated", "excited", etc.
        frustration_level: Literal["low", "medium", "high"] | None = None

        # Situational understanding
        situation_facts: list[str] = []  # Mini rule-like statements

        # Customer data extraction (CRITICAL FOR PHASE 3)
        candidate_variables: dict[str, CandidateVariableInfo] = {}
    ```
  - Details: Complete situational understanding replacing current `Context` model

### Update Existing Models

- [x] **Update __init__.py exports**
  - File: `ruche/brains/focal/models/__init__.py`
  - Action: Not needed (models are in interlocutor_data/, not alignment/models/)
  - Details: `InterlocutorDataField`, `VariableEntry`, `InterlocutorDataStore` are in `ruche/domain/interlocutor/models.py`
  - **Implemented**: `InterlocutorSchemaMask` and `InterlocutorSchemaMaskEntry` exported from `ruche/brains/focal/context/__init__.py`

- [x] **Update context __init__.py exports**
  - File: `ruche/brains/focal/context/__init__.py`
  - Action: Modified
  - Details: Added exports for `SituationalSnapshot`, `CandidateVariableInfo`
  - **Implemented**: Both models exported in `__all__`

---

## Phase 2.2: Configuration

### Brain Configuration

- [x] **Add situational_sensor config section**
  - File: `config/default.toml`
  - Action: Modified
  - **Implemented**: Added `[brain.situational_sensor]` section with all required fields
  - Section: `[brain.situational_sensor]`
    ```toml
    [brain.situational_sensor]
    enabled = true
    model = "openrouter/openai/gpt-oss-120b"
    fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
    provider_order = ["cerebras", "groq", "google-vertex", "sambanova"]
    provider_sort = "latency"
    allow_fallbacks = true
    ignore_providers = []
    temperature = 0.0  # Deterministic for extraction
    max_tokens = 800
    history_turns = 5  # Configurable K (currently hardcoded)
    include_glossary = true
    include_schema_mask = true
    ```
  - Details: Configuration for situational sensor LLM task

### Pydantic Configuration Models

- [x] **Create SituationalSensorConfig model**
  - File: `ruche/config/models/brain.py`
  - Action: Modified existing file
  - **Implemented**: Created `SituationalSensorConfig` class extending `OpenRouterConfigMixin`
  - Model:
    ```python
    class SituationalSensorConfig(BaseModel):
        enabled: bool = True
        model: str = "openrouter/openai/gpt-oss-120b"
        fallback_models: list[str] = ["anthropic/claude-3-5-haiku-20241022"]
        provider_order: list[str] = ["cerebras", "groq", "google-vertex", "sambanova"]
        provider_sort: str = "latency"
        allow_fallbacks: bool = True
        ignore_providers: list[str] = []
        temperature: float = 0.0
        max_tokens: int = 800
        history_turns: int = 5
        include_glossary: bool = True
        include_schema_mask: bool = True
    ```
  - Details: Pydantic model for type-safe configuration access

- [x] **Update PipelineConfig to include situational_sensor**
  - File: `ruche/config/models/brain.py`
  - Action: Modified
  - Details: Added `situational_sensor: SituationalSensorConfig` field to `PipelineConfig`
  - **Implemented**: Field added with `default_factory=SituationalSensorConfig`

---

## Phase 2.3: Jinja2 Template Infrastructure

### Template Loader

- [x] **Create Jinja2 template loader utility**
  - File: `ruche/brains/focal/context/template_loader.py`
  - Action: Created new file
  - Class: `TemplateLoader`
  - **Implemented**: Created with Jinja2 Environment configuration (trim_blocks, lstrip_blocks enabled)
    ```python
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from pathlib import Path

    class TemplateLoader:
        """Loads and renders Jinja2 templates for LLM tasks."""

        def __init__(self, templates_dir: Path):
            self.env = Environment(
                loader=FileSystemLoader(templates_dir),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True,
            )

        def render(self, template_name: str, **context) -> str:
            template = self.env.get_template(template_name)
            return template.render(**context)
    ```
  - Details: Centralized Jinja2 template loading following LLM Task Pattern

### Situational Sensor Prompt Template

- [x] **Create situational_sensor.jinja2 template**
  - File: `ruche/brains/focal/context/prompts/situational_sensor.jinja2`
  - Action: Created new file
  - **Implemented**: Full Jinja2 template with schema mask, glossary, conversation history, and JSON response format
  - Template structure:
    ```jinja2
    You are analyzing a customer conversation to extract situational context and customer data.

    # Customer Data Schema (Available Fields)
    {% if schema_mask %}
    The following customer data fields are defined for this agent:
    {% for key, entry in schema_mask.variables.items() %}
    - {{ key }}: {{ entry.type }} ({{ entry.scope }}) {% if entry.exists %}[HAS VALUE]{% else %}[EMPTY]{% endif %}
    {% endfor %}
    {% endif %}

    # Domain Glossary
    {% if glossary %}
    Business-specific terms:
    {% for term, item in glossary.items() %}
    - **{{ item.term }}**: {{ item.description }}
      {% if item.usage_notes %}Usage: {{ item.usage_notes }}{% endif %}
    {% endfor %}
    {% endif %}

    # Conversation History
    {% if conversation_window %}
    {% for turn in conversation_window %}
    {{ turn.role }}: {{ turn.content }}
    {% endfor %}
    {% endif %}

    # Current Message
    User: {{ message }}

    # Task
    Analyze this message and extract:
    1. Language detection (ISO 639-1 code)
    2. Intent evolution (has intent changed? what's the new intent?)
    3. Conversation state (topic change, tone, frustration)
    4. Candidate variables (extract values for schema fields from message)

    Respond with JSON matching this structure:
    {
      "language": "en",
      "previous_intent_label": "...",
      "intent_changed": true/false,
      "new_intent_label": "...",
      "new_intent_text": "...",
      "topic_changed": true/false,
      "tone": "neutral|frustrated|excited|etc",
      "frustration_level": "low|medium|high",
      "situation_facts": ["fact 1", "fact 2"],
      "candidate_variables": {
        "name": {
          "value": "...",
          "scope": "IDENTITY|BUSINESS|CASE|SESSION",
          "is_update": true/false
        }
      }
    }
    ```
  - Details: Full Jinja2 template with schema mask, glossary, and conversation context

---

## Phase 2.4: Situational Sensor Implementation

### Core Sensor Class

- [x] **Create SituationalSensor class**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Created new file
  - Class: `SituationalSensor`
  - **Implemented**: Created with all methods from spec (P2.1-P2.6), uses TemplateLoader for Jinja2 rendering
  - Methods:
    - `__init__(llm_executor, config)` - Note: template_loader created internally
    - `async sense(message, history, interlocutor_data_store, interlocutor_data_fields, glossary_items, previous_intent_label) -> SituationalSnapshot`
    - `_build_schema_mask(interlocutor_data_store, interlocutor_data_fields) -> InterlocutorSchemaMask` (P2.1)
    - `_build_glossary_view(glossary_items) -> dict[str, GlossaryItem]` (P2.2)
    - `_build_conversation_window(history) -> list[Turn]` (P2.3)
    - `async _call_sensor_llm(...) -> dict[str, Any]` (P2.4)
    - `_extract_json(content) -> dict[str, Any]` - Helper for JSON extraction
    - `_parse_snapshot(llm_output) -> SituationalSnapshot` (P2.5)
    - `_validate_language(language, message) -> str` (P2.6)
  - Details: Main class implementing all Phase 2 substeps

### P2.1: Build InterlocutorSchemaMask

- [x] **Implement _build_schema_mask method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Creates InterlocutorSchemaMaskEntry for each field, checks existence in InterlocutorDataStore.fields

### P2.2: Build Glossary View

- [x] **Implement _build_glossary_view method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Simply returns glossary dict (filtering already done by caller)

### P2.3: Build Conversation Window

- [x] **Implement _build_conversation_window method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Extracts last K turns using config.history_turns, handles K=0 case

### P2.4: Call Sensor LLM

- [x] **Implement _call_sensor_llm method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Renders Jinja2 template, calls LLMExecutor, extracts JSON from response (handles markdown code blocks)

### P2.5: Parse Snapshot

- [x] **Implement _parse_snapshot method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Parses LLM JSON into SituationalSnapshot, handles nested candidate_variables, provides defaults for optional fields

### P2.6: Validate Language

- [x] **Implement _validate_language method**
  - File: `ruche/brains/focal/context/situational_sensor.py`
  - Action: Implemented
  - **Implemented**: Validates ISO 639-1 format (2-letter alphabetic), defaults to "en" if invalid

---

## Phase 2.5: Integration with FocalBrain

### Update Engine to Use Situational Sensor

- [x] **Replace ContextExtractor with SituationalSensor**
  - File: `ruche/brains/focal/engine.py`
  - Action: Modified
  - Changes:
    - Updated imports to include `SituationalSensor` and `SituationalSnapshot`
    - Added `_situational_sensor` initialization in `__init__`
    - Modified `_extract_context()` to return tuple `(Context, SituationalSnapshot | None)`
    - Integrated situational sensor call with customer data loading
    - Updated call site in `_process_turn_impl` to unpack tuple
    - Added situational_snapshot to AlignmentResult construction
  - Details: Sensor runs when enabled, loads customer data/glossary/schema, calls sense()

- [x] **Update AlignmentResult model**
  - File: `ruche/brains/focal/result.py`
  - Action: Modified
  - Changes:
    - Added import for `SituationalSnapshot`
    - Added `situational_snapshot: SituationalSnapshot | None = None` field
    - Kept `context: Context | None` for backward compatibility
  - Details: Both Context and SituationalSnapshot are now in result model

### Load InterlocutorDataStore and Glossary in Phase 1

- [x] **Add InterlocutorDataStore loading to engine**
  - File: `ruche/brains/focal/engine.py`
  - Action: Modified in `_extract_context()` method
  - Logic:
    - Loads InterlocutorDataStore using `_interlocutor_data_loader.load()` for customer
    - Loads InterlocutorDataField definitions using `_static_config_loader.load_interlocutor_data_schema()`
    - Loads GlossaryItem dict using `_static_config_loader.load_glossary()`
    - Passes all three to `SituationalSensor.sense()`
  - Details: Loading happens within _extract_context when situational_sensor is enabled

---

## Phase 2.6: Store Interfaces for New Models

### ConfigStore Extensions

- [x] **Add GlossaryItem CRUD to ConfigStore interface**
  - File: `ruche/brains/focal/stores/agent_config_store.py`
  - Action: Already exists (Phase 1)
  - Methods:
    - `async get_glossary_items(tenant_id: UUID, agent_id: UUID, *, enabled_only: bool = True) -> list[GlossaryItem]`
    - `async save_glossary_item(item: GlossaryItem) -> UUID`
  - Details: Interface already has glossary methods from Phase 1

- [x] **Add InterlocutorDataField CRUD to ConfigStore interface**
  - File: `ruche/brains/focal/stores/agent_config_store.py`
  - Action: Already exists (Phase 1)
  - Methods:
    - `async get_interlocutor_data_fields(tenant_id: UUID, agent_id: UUID, *, enabled_only: bool = True) -> list[InterlocutorDataField]`
    - `async save_interlocutor_data_field(field: InterlocutorDataField) -> UUID`
  - Details: Interface already has interlocutor_data_field methods from Phase 1

### InMemory Implementations

- [x] **Implement glossary methods in InMemoryConfigStore**
  - File: `ruche/brains/focal/stores/inmemory.py`
  - Action: Already implemented (Phase 1)
  - Details: Lines 427-446, uses `_glossary_items` dict keyed by UUID

- [x] **Implement interlocutor_data_field methods in InMemoryConfigStore**
  - File: `ruche/brains/focal/stores/inmemory.py`
  - Action: Already implemented (Phase 1)
  - Details: Lines 448-467, uses `_interlocutor_data_fields` dict keyed by UUID

### InterlocutorDataStoreInterface Extensions

- [x] **Confirm core CRUD exists on InterlocutorDataStoreInterface**
  - File: `ruche/domain/interlocutor/store.py`
  - Action: Already exists (uses get_by_customer_id)
  - Methods:
    - `async get_by_customer_id(tenant_id: UUID, customer_id: UUID, *, include_history: bool = False) -> InterlocutorDataStore | None`
    - `async save(profile: InterlocutorDataStore) -> UUID`
  - Details: InterlocutorDataStoreInterface already manages InterlocutorDataStore (renamed from CustomerProfile in Phase 1)

- [x] **Implement in InMemoryInterlocutorDataStore**
  - File: `ruche/domain/interlocutor/stores/inmemory.py`
  - Action: Already implemented (Phase 1)
  - Details: Lines 48-127, fully functional CRUD for InterlocutorDataStore

---

## Phase 2.7: Testing

### Unit Tests for Models

- [x] **Test InterlocutorDataField, VariableEntry, InterlocutorDataStore**
  - File: `tests/unit/interlocutor_data/test_interlocutor_data_models.py`
  - Action: Already tested (Phase 1)
  - **Note**: These models exist in `ruche/domain/interlocutor/models.py` with existing comprehensive tests

- [x] **Test InterlocutorSchemaMask models**
  - File: `tests/unit/alignment/context/test_customer_schema_mask.py`
  - Action: Already exists from Phase 1
  - **Implemented**: Tests exist with 100% coverage of InterlocutorSchemaMask models

- [x] **Test GlossaryItem model**
  - File: `tests/unit/alignment/models/test_glossary.py`
  - Action: Already tested (Phase 1)
  - **Note**: GlossaryItem already has comprehensive tests from Phase 1

- [x] **Test SituationalSnapshot and CandidateVariableInfo**
  - File: `tests/unit/alignment/context/test_situational_snapshot.py`
  - Action: Created new file
  - **Implemented**: 10 tests covering all fields, scope validation, candidate_variables parsing
  - Tests:
    - Test all fields parse correctly
    - Test candidate_variables dict parsing
    - Test optional fields handle None
    - Test frustration_level validation
  - Coverage: 100%

### Unit Tests for Template Loader

- [x] **Test TemplateLoader**
  - File: `tests/unit/alignment/context/test_template_loader.py`
  - Action: Created new file
  - **Implemented**: 10 tests covering template loading, rendering, and error handling
  - Tests:
    - Test template loading from directory
    - Test Jinja2 rendering with context
    - Test missing template error handling
    - Test conditionals, loops, dict variables
    - Test trim_blocks and lstrip_blocks behavior
    - Test rendering actual situational_sensor.jinja2 template
  - Coverage: 100%

### Unit Tests for Situational Sensor

- [x] **Test SituationalSensor._build_schema_mask**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Created new file
  - **Implemented**: 3 tests covering exists flag, empty store, privacy protection
  - Tests:
    - Test mask shows exists=True for populated fields
    - Test mask shows exists=False for empty fields
    - Test no actual values exposed in mask
  - Coverage: 100%

- [x] **Test SituationalSensor._build_glossary_view**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 2 tests covering glossary view building and empty case
  - Coverage: 100%

- [x] **Test SituationalSensor._build_conversation_window**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 4 tests covering configurable K, truncation, empty history, K=0 case
  - Coverage: 100%

- [x] **Test SituationalSensor._parse_snapshot**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 3 tests covering valid JSON, missing fields, candidate_variables parsing
  - Coverage: 100%

- [x] **Test SituationalSensor._validate_language**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 3 tests covering valid codes, uppercase conversion, invalid code handling
  - Coverage: 100%

- [x] **Test SituationalSensor._extract_json**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 5 tests covering markdown code blocks, plain blocks, raw JSON, error cases
  - Coverage: 100%

### Integration Tests with Mocked LLM

- [x] **Test full SituationalSensor.sense() flow**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Included in same file (async test class)
  - **Implemented**: 1 comprehensive test with mocked LLM executor
  - Tests:
    - Mock LLM to return valid JSON
    - Test full sense() call with all inputs
    - Verify SituationalSnapshot contains expected data
  - Coverage: Full flow

- [x] **Test SituationalSensor with empty inputs**
  - File: `tests/unit/alignment/context/test_situational_sensor.py`
  - Action: Added to same file
  - **Implemented**: 1 test with empty InterlocutorDataStore, no glossary, no history
  - Coverage: Edge cases

### Store Contract Tests

- [x] **Test ConfigStore glossary methods**
  - File: `tests/unit/alignment/stores/test_inmemory_config.py`
  - Action: Modified existing file
  - Tests:
    - test_save_and_get_glossary_items - saves and retrieves items
    - test_get_glossary_items_tenant_isolation - tenant isolation
    - test_get_glossary_items_enabled_only - enabled filtering
  - **Implemented**: Added TestGlossaryOperations class with 3 tests

- [x] **Test ConfigStore interlocutor_data_fields methods**
  - File: `tests/unit/alignment/stores/test_inmemory_config.py`
  - Action: Added to same file
  - Tests:
    - test_save_and_get_interlocutor_data_fields - saves and retrieves fields
    - test_get_interlocutor_data_fields_tenant_isolation - tenant isolation
    - test_get_interlocutor_data_fields_enabled_only - enabled filtering
  - **Implemented**: Added TestInterlocutorDataFieldOperations class with 3 tests

- [x] **Test InterlocutorDataStoreInterface CRUD methods**
  - File: `tests/unit/interlocutor_data/stores/test_inmemory_interlocutor_data.py`
  - Action: Already comprehensively tested (Phase 1)
  - Tests:
    - test_save_and_get_by_id - CRUD operations
    - test_get_by_customer_id - lookup by customer_id
    - test_get_by_channel_identity - channel identity resolution
  - **Note**: InterlocutorDataStoreInterface methods already tested with InterlocutorDataStore model

---

## Phase 2.8: Configuration Tests

- [x] **Test SituationalSensorConfig loading from TOML**
  - File: `tests/unit/config/test_models.py`
  - Action: Modified existing file
  - Tests:
    - test_defaults - verify all default values
    - test_history_turns_must_be_non_negative - validation
    - test_max_tokens_must_be_positive - validation
    - test_temperature_range - validation
    - test_custom_model - model override
    - test_disabling_features - glossary/schema_mask flags
    - test_embedded_in_pipeline_config - integration with PipelineConfig
  - **Implemented**: Added TestSituationalSensorConfig class with 7 tests

---

## Phase 2.9: Documentation Updates

- [x] **Update CLAUDE.md with Phase 2 patterns**
  - File: `CLAUDE.md`
  - Action: Modified
  - Details: Added "FOCAL Brain Patterns (Phase 2+)" section documenting:
    - Jinja2 Template Pattern for LLM Tasks - template loader usage, location conventions
    - InterlocutorDataStore Pattern - runtime values vs schema definitions, access patterns
    - Schema Mask Pattern for Privacy - never expose actual values to LLMs
    - Glossary Usage Pattern - loading and passing to templates
    - SituationalSnapshot Pattern - replaces basic Context with candidate variables
  - **Implemented**: ~95 lines of documentation with code examples

- [x] **Update doc_skeleton.md**
  - File: `docs/doc_skeleton.md`
  - Action: Modified
  - Details: Added entries for focal turn brain documentation:
    - `docs/focal_brain/README.md` - overview of 11-phase brain
    - `docs/focal_brain/spec/brain.md` - detailed phase specifications
    - `docs/focal_brain/spec/data_models.md` - complete data models
    - `docs/focal_brain/spec/configuration.md` - TOML configuration
    - `docs/focal_brain/spec/llm_task_configuration.md` - LLM task patterns
  - **Implemented**: 5 new documentation entries with summaries

---

## Success Criteria

When Phase 2 is complete:

1. ✅ **SituationalSnapshot model** exists with `candidate_variables` field
2. ✅ **InterlocutorSchemaMask** builds privacy-safe view for LLM
3. ✅ **GlossaryView** provides domain terminology to LLM
4. ✅ **Jinja2 template** renders with schema mask + glossary + conversation
5. ✅ **SituationalSensor.sense()** returns complete snapshot
6. ✅ **FocalBrain** uses SituationalSensor instead of ContextExtractor
7. ✅ **All tests pass** with 85%+ coverage
8. ✅ **Configuration** loaded from `[brain.situational_sensor]`
9. ✅ **Phase 3** can consume `candidate_variables` for customer data updates

---

## Dependencies

### Python Packages (Already Installed)
- `jinja2` - Template rendering (likely already installed with FastAPI)
- `pydantic` - Model validation (already in project)
- `langdetect` - Optional for language validation (add if needed: `uv add langdetect`)

### Blocks Phase 3
Phase 3 (Customer Data Update) **cannot be implemented** until Phase 2 is complete because it requires:
- `SituationalSnapshot.candidate_variables` as input
- `InterlocutorDataField` schema definitions
- `InterlocutorDataStore` runtime storage

---

## Estimated Effort

| Task Category | Estimated Time |
|--------------|----------------|
| Models (2.1) | 2-3 hours |
| Configuration (2.2) | 1 hour |
| Templates (2.3) | 2 hours |
| Sensor Implementation (2.4) | 4-5 hours |
| Engine Integration (2.5) | 2 hours |
| Store Extensions (2.6) | 2-3 hours |
| Unit Tests (2.7) | 4-5 hours |
| Integration Tests (2.7) | 2-3 hours |
| Documentation (2.9) | 1 hour |
| **Total** | **20-25 hours** |

---

## Implementation Order

Recommended implementation sequence:

1. **Models First** (2.1) - Foundation for everything else
2. **Configuration** (2.2) - Needed for sensor initialization
3. **Template Loader** (2.3) - Core infrastructure
4. **Situational Sensor** (2.4) - Core implementation
5. **Store Extensions** (2.6) - Needed for engine integration
6. **Engine Integration** (2.5) - Wire everything together
7. **Tests** (2.7) - Validate implementation
8. **Documentation** (2.9) - Final polish

Follow this order to minimize rework and ensure each component builds on the previous.
