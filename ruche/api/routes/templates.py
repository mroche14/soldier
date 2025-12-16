"""Template management endpoints."""

import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from ruche.brains.focal.models import Scope, Template, TemplateResponseMode
from ruche.api.dependencies import AgentConfigStoreDep
from ruche.api.exceptions import AgentNotFoundError, TemplateNotFoundError
from ruche.api.middleware.auth import TenantContextDep
from ruche.api.models.crud import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
)
from ruche.api.models.pagination import PaginatedResponse
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/templates")

# Pattern to extract variable names from templates: {variable_name}
VARIABLE_PATTERN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def _extract_variables(text: str) -> list[str]:
    """Extract variable names from template text."""
    return list(set(VARIABLE_PATTERN.findall(text)))


def _map_template_to_response(template: Template) -> TemplateResponse:
    """Map Template model to TemplateResponse."""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        text=template.content,
        mode=template.mode,
        scope=template.scope,
        scope_id=template.scope_id,
        conditions=template.conditions,
        variables_used=_extract_variables(template.content),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def _verify_agent_exists(
    config_store: AgentConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant."""
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


@router.get("", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mode: TemplateResponseMode | None = Query(default=None, description="Filter by mode"),
    scope: Scope | None = Query(default=None, description="Filter by scope"),
    sort_by: Literal["name", "created_at", "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> PaginatedResponse[TemplateResponse]:
    """List templates for an agent."""
    logger.debug(
        "list_templates_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    templates = await config_store.get_templates(
        tenant_context.tenant_id, agent_id, scope=scope
    )

    # Apply mode filter
    if mode is not None:
        templates = [t for t in templates if t.mode == mode]

    # Apply sorting
    reverse = sort_order == "desc"
    if sort_by == "name":
        templates = sorted(templates, key=lambda t: t.name.lower(), reverse=reverse)
    elif sort_by == "created_at":
        templates = sorted(templates, key=lambda t: t.created_at, reverse=reverse)
    elif sort_by == "updated_at":
        templates = sorted(templates, key=lambda t: t.updated_at, reverse=reverse)

    total = len(templates)
    paginated = templates[offset : offset + limit]
    items = [_map_template_to_response(t) for t in paginated]

    return PaginatedResponse[TemplateResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated) < total,
    )


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    agent_id: UUID,
    request: TemplateCreate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> TemplateResponse:
    """Create a new template."""
    logger.info(
        "create_template_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        name=request.name,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    template = Template(
        tenant_id=tenant_context.tenant_id,
        agent_id=agent_id,
        name=request.name,
        content=request.text,
        mode=request.mode,
        scope=request.scope,
        scope_id=request.scope_id,
        conditions=request.conditions,
    )

    await config_store.save_template(template)

    logger.info(
        "template_created",
        tenant_id=str(tenant_context.tenant_id),
        template_id=str(template.id),
    )

    return _map_template_to_response(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    agent_id: UUID,
    template_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> TemplateResponse:
    """Get a template by ID."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    template = await config_store.get_template(tenant_context.tenant_id, template_id)
    if template is None or template.agent_id != agent_id:
        raise TemplateNotFoundError(f"Template {template_id} not found")

    return _map_template_to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    agent_id: UUID,
    template_id: UUID,
    request: TemplateUpdate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> TemplateResponse:
    """Update a template."""
    logger.info(
        "update_template_request",
        tenant_id=str(tenant_context.tenant_id),
        template_id=str(template_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    template = await config_store.get_template(tenant_context.tenant_id, template_id)
    if template is None or template.agent_id != agent_id:
        raise TemplateNotFoundError(f"Template {template_id} not found")

    if request.name is not None:
        template.name = request.name
    if request.text is not None:
        template.content = request.text
    if request.mode is not None:
        template.mode = request.mode
    if request.scope is not None:
        template.scope = request.scope
    if request.scope_id is not None:
        template.scope_id = request.scope_id
    if request.conditions is not None:
        template.conditions = request.conditions

    template.touch()
    await config_store.save_template(template)

    logger.info("template_updated", template_id=str(template_id))

    return _map_template_to_response(template)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    agent_id: UUID,
    template_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> None:
    """Delete a template (soft delete)."""
    logger.info(
        "delete_template_request",
        tenant_id=str(tenant_context.tenant_id),
        template_id=str(template_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    template = await config_store.get_template(tenant_context.tenant_id, template_id)
    if template is None or template.agent_id != agent_id:
        raise TemplateNotFoundError(f"Template {template_id} not found")

    template.soft_delete()
    await config_store.save_template(template)

    logger.info("template_deleted", template_id=str(template_id))


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    agent_id: UUID,
    template_id: UUID,
    request: TemplatePreviewRequest,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> TemplatePreviewResponse:
    """Preview a template with variable substitution."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    template = await config_store.get_template(tenant_context.tenant_id, template_id)
    if template is None or template.agent_id != agent_id:
        raise TemplateNotFoundError(f"Template {template_id} not found")

    # Substitute variables
    rendered = template.content
    for name, value in request.variables.items():
        rendered = rendered.replace(f"{{{name}}}", value)

    return TemplatePreviewResponse(rendered=rendered)
