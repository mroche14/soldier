"""Fallback handler for enforcement failures."""

from ruche.alignment.enforcement.models import EnforcementResult
from ruche.alignment.models import Template
from ruche.alignment.models.enums import TemplateResponseMode


class FallbackHandler:
    """Provide fallback responses when enforcement fails.

    Used as a last resort when:
    1. Response violates hard constraints
    2. Regeneration attempts fail
    3. A safe fallback template is available
    """

    def select_fallback(
        self,
        templates: list[Template],
    ) -> Template | None:
        """Select a fallback template from available templates.

        Args:
            templates: Available templates for matched rules

        Returns:
            First template with FALLBACK mode, or None
        """
        for template in templates:
            if template.mode == TemplateResponseMode.FALLBACK:
                return template
        return None

    def apply_fallback(
        self,
        template: Template | None,
        original_result: EnforcementResult,
    ) -> EnforcementResult:
        """Apply fallback template to enforcement result.

        Args:
            template: Fallback template to use (or None)
            original_result: Result from enforcement validation

        Returns:
            Updated EnforcementResult with fallback applied
        """
        if template is None:
            return original_result

        return EnforcementResult(
            passed=True,
            violations=original_result.violations,
            regeneration_attempted=original_result.regeneration_attempted,
            regeneration_succeeded=original_result.regeneration_succeeded,
            fallback_used=True,
            fallback_template_id=template.id,
            final_response=template.text,
            enforcement_time_ms=getattr(original_result, "enforcement_time_ms", 0.0),
        )
