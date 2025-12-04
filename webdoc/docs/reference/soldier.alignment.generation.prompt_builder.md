<a id="soldier.alignment.generation.prompt_builder"></a>

# soldier.alignment.generation.prompt\_builder

Prompt building for response generation.

Assembles context, rules, memory, and tool results into prompts
for response generation.

<a id="soldier.alignment.generation.prompt_builder.PromptBuilder"></a>

## PromptBuilder Objects

```python
class PromptBuilder()
```

Build prompts for response generation.

Assembles all context into a structured prompt including:
- Active rules and their instructions
- User context and intent
- Memory/conversation history
- Tool execution results

<a id="soldier.alignment.generation.prompt_builder.PromptBuilder.__init__"></a>

#### \_\_init\_\_

```python
def __init__(system_template: str | None = None,
             max_history_turns: int = 10) -> None
```

Initialize the prompt builder.

**Arguments**:

- `system_template` - Optional custom system prompt template
- `max_history_turns` - Maximum history turns to include

<a id="soldier.alignment.generation.prompt_builder.PromptBuilder.build_system_prompt"></a>

#### build\_system\_prompt

```python
def build_system_prompt(matched_rules: list[MatchedRule],
                        context: Context,
                        tool_results: list[ToolResult] | None = None,
                        memory_context: str | None = None) -> str
```

Build the system prompt with all context.

**Arguments**:

- `matched_rules` - Rules that apply to this turn
- `context` - Extracted user context
- `tool_results` - Results from tool execution
- `memory_context` - Retrieved memory/episode context
  

**Returns**:

  Complete system prompt string

<a id="soldier.alignment.generation.prompt_builder.PromptBuilder.build_messages"></a>

#### build\_messages

```python
def build_messages(system_prompt: str,
                   user_message: str,
                   history: list[Turn] | None = None) -> list[dict[str, str]]
```

Build the message list for the LLM.

**Arguments**:

- `system_prompt` - System prompt to use
- `user_message` - Current user message
- `history` - Conversation history
  

**Returns**:

  List of message dicts with role and content

