"""Response generation for alignment pipeline.

Generates responses using LLM with support for template modes.
"""

import re
import time

from ruche.brains.focal.phases.context.models import Turn
from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.execution.models import ToolResult
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.generation.formatters import get_formatter
from ruche.brains.focal.phases.generation.models import GenerationResult
from ruche.brains.focal.models.enums import TemplateResponseMode
from ruche.brains.focal.phases.generation.parser import parse_llm_output
from ruche.brains.focal.phases.generation.prompt_builder import PromptBuilder
from ruche.brains.focal.models import Template
from ruche.brains.focal.phases.planning.models import ResponsePlan
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage

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
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        history: list[Turn] | None = None,
        tool_results: list[ToolResult] | None = None,
        memory_context: str | None = None,
        templates: list[Template] | None = None,
        variables: dict[str, str] | None = None,
        response_plan: ResponsePlan | None = None,
        glossary_items: list | None = None,
        channel: str = "web",
    ) -> GenerationResult:
        """Generate a response to the user.

        Args:
            snapshot: Situation snapshot
            matched_rules: Rules that apply to this turn
            history: Conversation history
            tool_results: Results from tool execution
            memory_context: Retrieved memory context
            templates: Available templates for matched rules
            variables: Variables for template resolution
            response_plan: Phase 8 response plan (optional)
            glossary_items: Domain-specific terminology (optional)
            channel: Target channel for formatting (whatsapp, email, sms, web)

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
                template_mode=TemplateResponseMode.EXCLUSIVE,
                generation_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Build prompt
        system_prompt = self._prompt_builder.build_system_prompt(
            matched_rules=matched_rules,
            snapshot=snapshot,
            tool_results=tool_results,
            memory_context=memory_context,
            response_plan=response_plan,
            glossary_items=glossary_items,
        )

        # Add suggested templates to prompt
        if templates:
            suggested = [t for t in templates if self._get_template_mode(t) == TemplateResponseMode.SUGGEST]
            if suggested:
                system_prompt = self._add_template_suggestions(system_prompt, suggested)

        # Build messages
        messages = self._prompt_builder.build_messages(
            system_prompt=system_prompt,
            user_message=snapshot.message,
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

        # Parse LLM output for structured categories
        response_text, llm_categories = parse_llm_output(llm_response.content)

        # Apply channel formatting
        formatter = get_formatter(channel)
        formatted_response = formatter.format(response_text)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "response_generated",
            response_length=len(formatted_response),
            elapsed_ms=elapsed_ms,
            model=llm_response.model,
            response_type=response_plan.global_response_type.value if response_plan else None,
            categories_count=len(llm_categories),
            categories=[c.value for c in llm_categories] if llm_categories else [],
            channel=channel,
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
            response=formatted_response,
            model=llm_response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            generation_time_ms=elapsed_ms,
            prompt_preview=system_prompt[:200] if system_prompt else None,
            llm_categories=llm_categories,
            channel_formatted=True,
            channel=channel,
        )

    def _find_exclusive_template(
        self,
        matched_rules: list[MatchedRule],
        templates: list[Template] | None,
    ) -> Template | None:
        """Find an exclusive template from matched rules."""
        if not templates:
            return None

        # Normalize template IDs to strings for comparison
        template_map = {str(t.id): t for t in templates}

        for matched in matched_rules:
            for template_id in matched.rule.attached_template_ids:
                # Normalize to string for comparison
                tid_str = str(template_id)
                if tid_str in template_map:
                    template = template_map[tid_str]
                    if self._get_template_mode(template) == TemplateResponseMode.EXCLUSIVE:
                        return template

        return None

    def _get_template_mode(self, template: Template) -> TemplateResponseMode:
        """Get the template mode, defaulting to SUGGEST."""
        if hasattr(template, "mode") and template.mode is not None:
            # Template.mode is already TemplateResponseMode
            if isinstance(template.mode, TemplateResponseMode):
                return template.mode
            # Handle string or other enum values
            mode_value = (
                template.mode.value if hasattr(template.mode, "value") else str(template.mode)
            )
            try:
                return TemplateResponseMode(mode_value.upper())
            except ValueError:
                return TemplateResponseMode.SUGGEST
        return TemplateResponseMode.SUGGEST

    def _resolve_template(
        self,
        template: Template,
        variables: dict[str, str],
    ) -> str:
        """Resolve template placeholders with variables."""
        content = template.content

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
            suggestions.append(f"- {template.name}: {template.content[:200]}...")

        return system_prompt + "\n".join(suggestions)
