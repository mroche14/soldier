"""Unit tests for FallbackHandler."""

from uuid import uuid4

from soldier.alignment.enforcement.fallback import FallbackHandler
from soldier.alignment.enforcement.models import EnforcementResult
from soldier.alignment.generation.models import TemplateMode
from soldier.alignment.models import Template


def _template(mode: TemplateMode) -> Template:
    return Template(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name=f"{mode}-template",
        description=None,
        text="fallback text",
        scope="global",
        scope_id=None,
        mode=mode,
    )


def test_select_fallback_picks_mode_fallback() -> None:
    handler = FallbackHandler()
    templates = [
        _template(TemplateMode.SUGGEST),
        _template(TemplateMode.FALLBACK),
    ]

    selected = handler.select_fallback(templates)
    assert selected is not None
    assert selected.mode == TemplateMode.FALLBACK


def test_apply_fallback_updates_result() -> None:
    handler = FallbackHandler()
    template = _template(TemplateMode.FALLBACK)
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
