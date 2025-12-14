"""Helpers for loading templates for matched rules."""

from uuid import UUID

from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.models import Template
from ruche.alignment.stores import AgentConfigStore


async def load_templates_for_rules(
    config_store: AgentConfigStore,
    tenant_id: UUID,
    matched_rules: list[MatchedRule],
) -> list[Template]:
    """Load templates referenced by matched rules."""
    if not matched_rules:
        return []

    seen: set[UUID] = set()
    templates: list[Template] = []

    for matched in matched_rules:
        for template_id in matched.rule.attached_template_ids:
            if template_id in seen:
                continue
            seen.add(template_id)
            template = await config_store.get_template(tenant_id, template_id)
            if template:
                templates.append(template)

    return templates
