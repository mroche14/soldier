"""Unit tests for FallbackHandler."""

from uuid import uuid4

from focal.alignment.enforcement.fallback import FallbackHandler
from focal.alignment.enforcement.models import EnforcementResult
from focal.alignment.models import Template
from focal.alignment.models.enums import Scope, TemplateResponseMode


def _template(mode: TemplateResponseMode) -> Template:
    return Template(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name=f"{mode}-template",
        description=None,
        text="fallback text",
        scope=Scope.GLOBAL,
        scope_id=None,
        mode=mode,
    )


def test_select_fallback_picks_mode_fallback() -> None:
    handler = FallbackHandler()
    templates = [
        _template(TemplateResponseMode.SUGGEST),
        _template(TemplateResponseMode.FALLBACK),
    ]

    selected = handler.select_fallback(templates)
    assert selected is not None
    assert selected.mode == TemplateResponseMode.FALLBACK


def test_apply_fallback_updates_result() -> None:
    handler = FallbackHandler()
    template = _template(TemplateResponseMode.FALLBACK)
    original = EnforcementResult(
        passed=False,
        violations=[],
        regeneration_attempted=False,
        regeneration_succeeded=False,
        fallback_used=False,
        fallback_template_id=None,
        final_response="bad",
    )

    updated = handler.apply_fallback(template, original)
    assert updated.fallback_used is True
    assert updated.final_response == "fallback text"
    assert updated.fallback_template_id == template.id
