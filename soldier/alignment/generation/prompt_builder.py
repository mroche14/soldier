"""Prompt building for response generation.

Assembles context, rules, memory, and tool results into prompts
for response generation.
"""

from pathlib import Path

from soldier.alignment.context.models import Turn
from soldier.alignment.context.situation_snapshot import SituationSnapshot
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.planning.models import ResponsePlan

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
        snapshot: SituationSnapshot,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
        response_plan: ResponsePlan | None = None,
        glossary_items: list | None = None,
    ) -> str:
        """Build the system prompt with all context.

        Args:
            matched_rules: Rules that apply to this turn
            snapshot: Situation snapshot
            tool_results: Results from tool execution
            memory_context: Retrieved memory/episode context
            response_plan: Phase 8 response plan (optional)
            glossary_items: Domain-specific terminology (optional)

        Returns:
            Complete system prompt string
        """
        rules_section = self._build_rules_section(matched_rules)
        context_section = self._build_context_section(snapshot)
        memory_section = self._build_memory_section(memory_context)
        tool_results_section = self._build_tool_results_section(tool_results)
        glossary_section = self._build_glossary_section(glossary_items)
        response_plan_section = self._build_response_plan_section(response_plan)

        prompt = self._system_template.format(
            rules_section=rules_section,
            context_section=context_section,
            memory_section=memory_section,
            tool_results_section=tool_results_section,
        )

        # Append glossary section if present
        if glossary_section:
            prompt += "\n\n" + glossary_section

        # Append response plan section if present
        if response_plan_section:
            prompt += "\n\n" + response_plan_section

        return prompt

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

    def _build_context_section(self, snapshot: SituationSnapshot) -> str:
        """Build the context section of the prompt."""
        lines = ["## User Context"]

        # Use canonical intent if available, fall back to new_intent_label
        intent = snapshot.canonical_intent_label or snapshot.new_intent_label
        if intent:
            lines.append(f"- Intent: {intent}")

        # Include tone (e.g., frustrated, excited, neutral)
        if snapshot.tone and snapshot.tone != "neutral":
            lines.append(f"- Tone: {snapshot.tone}")

        # Include frustration level if detected
        if snapshot.frustration_level:
            lines.append(f"- Frustration Level: {snapshot.frustration_level}")

        if snapshot.sentiment:
            lines.append(f"- Sentiment: {snapshot.sentiment.value}")

        if snapshot.urgency.value != "normal":
            lines.append(f"- Urgency: {snapshot.urgency.value}")

        if snapshot.topic:
            lines.append(f"- Topic: {snapshot.topic}")

        if snapshot.candidate_variables:
            vars_str = ", ".join(f"{k}={v.value}" for k, v in snapshot.candidate_variables.items())
            lines.append(f"- Extracted data: {vars_str}")

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

    def _build_glossary_section(self, glossary_items: list | None) -> str:
        """Build the glossary section of the prompt."""
        if not glossary_items:
            return ""

        lines = ["## Domain Terminology"]
        lines.append("Use these terms and definitions when responding:")
        lines.append("")

        for item in glossary_items:
            # Handle both GlossaryItem objects and dicts
            if hasattr(item, "term"):
                term = item.term
                definition = item.definition
            else:
                term = item.get("term", "")
                definition = item.get("definition", "")

            if term and definition:
                lines.append(f"**{term}**: {definition}")

        return "\n".join(lines)

    def _build_response_plan_section(
        self,
        response_plan: ResponsePlan | None,
    ) -> str:
        """Build the response plan section of the prompt."""
        if not response_plan:
            return ""

        lines = ["## Response Plan"]

        # Add response type guidance
        lines.append(f"- Response Type: {response_plan.global_response_type.value}")

        # Add bullet points from scenarios
        if response_plan.bullet_points:
            lines.append("")
            lines.append("Key points to address:")
            for point in response_plan.bullet_points:
                lines.append(f"  - {point}")

        # Add must include constraints
        if response_plan.must_include:
            lines.append("")
            lines.append("MUST include:")
            for item in response_plan.must_include:
                lines.append(f"  - {item}")

        # Add must avoid constraints
        if response_plan.must_avoid:
            lines.append("")
            lines.append("MUST NOT mention:")
            for item in response_plan.must_avoid:
                lines.append(f"  - {item}")

        return "\n".join(lines)
