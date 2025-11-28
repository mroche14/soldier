"""Prompt building for response generation.

Assembles context, rules, memory, and tool results into prompts
for response generation.
"""

from pathlib import Path

from soldier.alignment.context.models import Context, Turn
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"


class PromptBuilder:
    """Build prompts for response generation.

    Assembles all context into a structured prompt including:
    - Active rules and their instructions
    - User context and intent
    - Memory/conversation history
    - Tool execution results
    """

    def __init__(
        self,
        system_template: str | None = None,
        max_history_turns: int = 10,
    ) -> None:
        """Initialize the prompt builder.

        Args:
            system_template: Optional custom system prompt template
            max_history_turns: Maximum history turns to include
        """
        if system_template:
            self._system_template = system_template
        elif _SYSTEM_PROMPT_PATH.exists():
            self._system_template = _SYSTEM_PROMPT_PATH.read_text()
        else:
            self._system_template = self._default_template()

        self._max_history_turns = max_history_turns

    def _default_template(self) -> str:
        """Return a minimal default template."""
        return """You are a helpful AI assistant.
{rules_section}
{context_section}
{memory_section}
{tool_results_section}
Respond helpfully to the user."""

    def build_system_prompt(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
    ) -> str:
        """Build the system prompt with all context.

        Args:
            matched_rules: Rules that apply to this turn
            context: Extracted user context
            tool_results: Results from tool execution
            memory_context: Retrieved memory/episode context

        Returns:
            Complete system prompt string
        """
        rules_section = self._build_rules_section(matched_rules)
        context_section = self._build_context_section(context)
        memory_section = self._build_memory_section(memory_context)
        tool_results_section = self._build_tool_results_section(tool_results)

        return self._system_template.format(
            rules_section=rules_section,
            context_section=context_section,
            memory_section=memory_section,
            tool_results_section=tool_results_section,
        )

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[Turn] | None = None,
    ) -> list[dict[str, str]]:
        """Build the message list for the LLM.

        Args:
            system_prompt: System prompt to use
            user_message: Current user message
            history: Conversation history

        Returns:
            List of message dicts with role and content
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Add history
        if history:
            for turn in history[-self._max_history_turns :]:
                messages.append({"role": turn.role, "content": turn.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        return messages

    def _build_rules_section(self, matched_rules: list[MatchedRule]) -> str:
        """Build the rules section of the prompt."""
        if not matched_rules:
            return ""

        lines = ["## Active Rules", "Follow these instructions when responding:", ""]

        for i, matched in enumerate(matched_rules, 1):
            rule = matched.rule
            lines.append(f"{i}. **{rule.name}**")
            lines.append(f"   - When: {rule.condition_text}")
            lines.append(f"   - Then: {rule.action_text}")
            if rule.is_hard_constraint:
                lines.append("   - [!] This is a HARD CONSTRAINT - must be followed exactly")
            lines.append("")

        return "\n".join(lines)

    def _build_context_section(self, context: Context) -> str:
        """Build the context section of the prompt."""
        lines = ["## User Context"]

        if context.intent:
            lines.append(f"- Intent: {context.intent}")

        if context.sentiment:
            lines.append(f"- Sentiment: {context.sentiment.value}")

        if context.urgency.value != "normal":
            lines.append(f"- Urgency: {context.urgency.value}")

        if context.entities:
            entities_str = ", ".join(f"{e.type}={e.value}" for e in context.entities)
            lines.append(f"- Entities: {entities_str}")

        if len(lines) == 1:
            return ""  # No context to show

        return "\n".join(lines)

    def _build_memory_section(self, memory_context: str | None) -> str:
        """Build the memory section of the prompt."""
        if not memory_context:
            return ""

        return f"""## Relevant Memory
{memory_context}"""

    def _build_tool_results_section(
        self,
        tool_results: list[ToolResult] | None,
    ) -> str:
        """Build the tool results section of the prompt."""
        if not tool_results:
            return ""

        lines = ["## Tool Results", "Use this information in your response:", ""]

        for result in tool_results:
            if result.success:
                lines.append(f"- {result.tool_name}: {result.outputs}")
            else:
                lines.append(f"- {result.tool_name}: Failed - {result.error}")

        return "\n".join(lines)
