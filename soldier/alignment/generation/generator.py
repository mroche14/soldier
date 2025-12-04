"""Response generation for alignment pipeline.

Generates responses using LLM with support for template modes.
"""

import re
import time

from soldier.alignment.context.models import Context, Turn
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.models import GenerationResult, TemplateMode
from soldier.alignment.generation.prompt_builder import PromptBuilder
from soldier.alignment.models import Template
from soldier.observability.logging import get_logger
from soldier.providers.llm import LLMExecutor, LLMMessage

logger = get_logger(__name__)


class ResponseGenerator:
    """Generate agent responses.

    Supports multiple generation modes:
    - LLM-based generation with context and rules
    - Template-based generation (EXCLUSIVE mode)
    - Suggested templates included in prompt (SUGGEST mode)
    """

    def __init__(
        self,
        llm_executor: LLMExecutor,
        prompt_builder: PromptBuilder | None = None,
        default_temperature: float = 0.7,
        default_max_tokens: int = 1024,
    ) -> None:
        """Initialize the response generator.

        Args:
            llm_executor: Executor for LLM generation
            prompt_builder: Builder for assembling prompts
            default_temperature: Default sampling temperature
            default_max_tokens: Default max tokens for response
        """
        self._llm_executor = llm_executor
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    async def generate(
        self,
        context: Context,
        matched_rules: list[MatchedRule],
        history: list[Turn] | None = None,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
        templates: list[Template] | None = None,
        variables: dict[str, str] | None = None,
    ) -> GenerationResult:
        """Generate a response to the user.

        Args:
            context: Extracted user context
            matched_rules: Rules that apply to this turn
            history: Conversation history
            tool_results: Results from tool execution
            memory_context: Retrieved memory context
            templates: Available templates for matched rules
            variables: Variables for template resolution

        Returns:
            GenerationResult with response and metadata
        """
        start_time = time.perf_counter()

        # Check for exclusive template mode
        exclusive_template = self._find_exclusive_template(matched_rules, templates)
        if exclusive_template:
            response = self._resolve_template(exclusive_template, variables or {})
            return GenerationResult(
                response=response,
                template_used=exclusive_template.id,
                template_mode=TemplateMode.EXCLUSIVE,
                generation_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Build prompt
        system_prompt = self._prompt_builder.build_system_prompt(
            matched_rules=matched_rules,
            context=context,
            tool_results=tool_results,
            memory_context=memory_context,
        )

        # Add suggested templates to prompt
        if templates:
            suggested = [t for t in templates if self._get_template_mode(t) == TemplateMode.SUGGEST]
            if suggested:
                system_prompt = self._add_template_suggestions(system_prompt, suggested)

        # Build messages
        messages = self._prompt_builder.build_messages(
            system_prompt=system_prompt,
            user_message=context.message,
            history=history,
        )

        # Convert to LLMMessage format
        llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

        # Generate response
        llm_response = await self._llm_executor.generate(
            messages=llm_messages,
            temperature=self._default_temperature,
            max_tokens=self._default_max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "response_generated",
            response_length=len(llm_response.content),
            elapsed_ms=elapsed_ms,
            model=llm_response.model,
        )

        # Extract token counts from usage (handles both TokenUsage and dict)
        prompt_tokens = 0
        completion_tokens = 0
        if llm_response.usage:
            if isinstance(llm_response.usage, dict):
                prompt_tokens = llm_response.usage.get("prompt_tokens", 0)
                completion_tokens = llm_response.usage.get("completion_tokens", 0)
            else:
                # TokenUsage model
                prompt_tokens = llm_response.usage.prompt_tokens
                completion_tokens = llm_response.usage.completion_tokens

        return GenerationResult(
            response=llm_response.content,
            model=llm_response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            generation_time_ms=elapsed_ms,
            prompt_preview=system_prompt[:200] if system_prompt else None,
        )

    def _find_exclusive_template(
        self,
        matched_rules: list[MatchedRule],
        templates: list[Template] | None,
    ) -> Template | None:
        """Find an exclusive template from matched rules."""
        if not templates:
            return None

        template_map = {t.id: t for t in templates}

        for matched in matched_rules:
            for template_id in matched.rule.attached_template_ids:
                if template_id in template_map:
                    template = template_map[template_id]
                    if self._get_template_mode(template) == TemplateMode.EXCLUSIVE:
                        return template

        return None

    def _get_template_mode(self, template: Template) -> TemplateMode:
        """Get the template mode, defaulting to SUGGEST."""
        if hasattr(template, "mode") and template.mode is not None:
            # Convert from model TemplateMode to generation TemplateMode
            mode_value = (
                template.mode.value if hasattr(template.mode, "value") else str(template.mode)
            )
            try:
                return TemplateMode(mode_value)
            except ValueError:
                return TemplateMode.SUGGEST
        return TemplateMode.SUGGEST

    def _resolve_template(
        self,
        template: Template,
        variables: dict[str, str],
    ) -> str:
        """Resolve template placeholders with variables."""
        content = template.text

        # Find all placeholders like {variable_name}
        placeholders = re.findall(r"\{(\w+)\}", content)

        for placeholder in placeholders:
            if placeholder in variables:
                content = content.replace(f"{{{placeholder}}}", variables[placeholder])

        return content

    def _add_template_suggestions(
        self,
        system_prompt: str,
        templates: list[Template],
    ) -> str:
        """Add template suggestions to the prompt."""
        if not templates:
            return system_prompt

        suggestions = [
            "",
            "## Suggested Response Templates",
            "You may use or adapt these templates:",
        ]

        for template in templates:
            suggestions.append(f"- {template.name}: {template.text[:200]}...")

        return system_prompt + "\n".join(suggestions)
