## 5. LLM Task Configuration Pattern

Every LLM task in the pipeline follows a **consistent configuration pattern**: configuration in TOML + prompt template in Jinja2.

### 5.1 Configuration Structure

Each LLM task has its own section in `config/default.toml`:

```toml
[pipeline.{task_name}]
enabled = true
model = "openrouter/openai/gpt-4o-mini"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
provider_order = ["anthropic", "openai"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []
temperature = 0.7
max_tokens = 1024
timeout_ms = 5000
```

**Common fields across all LLM tasks:**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Enable/disable the task |
| `model` | `str` | Primary model (provider-prefixed) |
| `fallback_models` | `list[str]` | Fallback chain if primary fails |
| `provider_order` | `list[str]` | OpenRouter provider preference |
| `provider_sort` | `str` | Sorting strategy: `"latency"`, `"price"`, `"throughput"` |
| `allow_fallbacks` | `bool` | Allow providers not in `provider_order` |
| `ignore_providers` | `list[str]` | Providers to never use |
| `temperature` | `float` | Model temperature (0.0-1.0) |
| `max_tokens` | `int` | Maximum response tokens |
| `timeout_ms` | `int` | Request timeout in milliseconds |

### 5.2 Prompt Templates

Prompt templates are stored as Jinja2 files in a structured directory:

```
ruche/alignment/
├── situational/
│   └── prompts/
│       └── situational_sensor.jinja2
├── retrieval/
│   └── prompts/
│       ├── rule_filter.jinja2
│       └── scenario_filter.jinja2
├── generation/
│   └── prompts/
│       ├── response_generator.jinja2
│       └── response_planner.jinja2
└── enforcement/
    └── prompts/
        ├── llm_judge.jinja2
        └── relevance_check.jinja2
```

**Template naming convention:** `{task_name}.jinja2`

### 5.3 Template Variables

Templates receive a standardized context object:

```python
class LLMTaskContext(BaseModel):
    # Always available
    turn_context: TurnContext
    session_state: SessionState
    interlocutor_data: InterlocutorDataStore

    # Task-specific (passed by the task)
    task_inputs: dict[str, Any]

    # From config
    config: LLMTaskConfig
```

**Example template (`situational_sensor.jinja2`):**

```jinja2
You are analyzing a customer message to extract situational context.

## Customer Schema (values hidden for privacy)
{% for key, entry in interlocutor_schema_mask.variables.items() %}
- {{ key }}: {{ entry.type }} ({{ entry.scope }}) - {{ "has value" if entry.exists else "unknown" }}
{% endfor %}

## Recent History
{% for turn in history[-config.history_turns:] %}
{{ turn.role }}: {{ turn.content }}
{% endfor %}

## Current Message
{{ user_message }}

## Instructions
Extract:
1. Primary intent
2. Any candidate variable values mentioned
3. Tone and topic analysis
```

### 5.4 LLM Task Registry

Tasks are registered and discoverable:

| Task | Config Section | Template Path |
|------|----------------|---------------|
| Situational Sensor | `[pipeline.situational_sensor]` | `situational/prompts/situational_sensor.jinja2` |
| Rule Filter | `[pipeline.rule_filtering]` | `retrieval/prompts/rule_filter.jinja2` |
| Scenario Filter | `[pipeline.scenario_filtering]` | `retrieval/prompts/scenario_filter.jinja2` |
| Response Generation | `[pipeline.generation]` | `generation/prompts/response_generator.jinja2` |
| LLM Judge | `[pipeline.enforcement]` | `enforcement/prompts/llm_judge.jinja2` |
| Entity Extraction | `[pipeline.memory_ingestion.entity_extraction]` | `memory/prompts/entity_extraction.jinja2` |
| Summarization | `[pipeline.memory_ingestion.summarization.*]` | `memory/prompts/summarization.jinja2` |

---
