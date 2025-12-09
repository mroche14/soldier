<a id="focal.alignment.generation.generator"></a>

# focal.alignment.generation.generator

Response generation for alignment pipeline.

Generates responses using LLM with support for template modes.

<a id="focal.alignment.generation.generator.ResponseGenerator"></a>

## ResponseGenerator Objects

```python
class ResponseGenerator()
```

Generate agent responses.

Supports multiple generation modes:
- LLM-based generation with context and rules
- Template-based generation (EXCLUSIVE mode)
- Suggested templates included in prompt (SUGGEST mode)

<a id="focal.alignment.generation.generator.ResponseGenerator.__init__"></a>

#### \_\_init\_\_

```python
def __init__(llm_provider: LLMProvider,
             prompt_builder: PromptBuilder | None = None,
             default_temperature: float = 0.7,
             default_max_tokens: int = 1024) -> None
```

Initialize the response generator.

**Arguments**:

- `llm_provider` - Provider for LLM generation
- `prompt_builder` - Builder for assembling prompts
- `default_temperature` - Default sampling temperature
- `default_max_tokens` - Default max tokens for response

<a id="focal.alignment.generation.generator.ResponseGenerator.generate"></a>

#### generate

```python
async def generate(
        context: Context,
        matched_rules: list[MatchedRule],
        history: list[Turn] | None = None,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
        templates: list[Template] | None = None,
        variables: dict[str, str] | None = None) -> GenerationResult
```

Generate a response to the user.

**Arguments**:

- `context` - Extracted user context
- `matched_rules` - Rules that apply to this turn
- `history` - Conversation history
- `tool_results` - Results from tool execution
- `memory_context` - Retrieved memory context
- `templates` - Available templates for matched rules
- `variables` - Variables for template resolution
  

**Returns**:

  GenerationResult with response and metadata

