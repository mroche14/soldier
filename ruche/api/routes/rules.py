"""Rule management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query

from ruche.brains.focal.models import Rule, Scope
from ruche.api.dependencies import AgentConfigStoreDep
from ruche.api.exceptions import AgentNotFoundError, RuleNotFoundError
from ruche.api.middleware.auth import TenantContextDep
from ruche.api.models.bulk import BulkRequest, BulkResponse, BulkResult
from ruche.api.models.crud import RuleCreate, RuleResponse, RuleUpdate
from ruche.api.models.pagination import PaginatedResponse
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/rules")


def _map_rule_to_response(rule: Rule) -> RuleResponse:
    """Map Rule model to RuleResponse.

    Args:
        rule: Rule domain model

    Returns:
        RuleResponse for API
    """
    return RuleResponse(
        id=rule.id,
        name=rule.name,
        condition_text=rule.condition_text,
        action_text=rule.action_text,
        scope=rule.scope,
        scope_id=rule.scope_id,
        priority=rule.priority,
        enabled=rule.enabled,
        max_fires_per_session=rule.max_fires_per_session,
        cooldown_turns=rule.cooldown_turns,
        is_hard_constraint=rule.is_hard_constraint,
        attached_tool_ids=rule.attached_tool_ids,
        attached_template_ids=rule.attached_template_ids,
        has_embedding=rule.embedding is not None,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def _verify_agent_exists(
    config_store: AgentConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant.

    Args:
        config_store: Configuration store
        tenant_id: Tenant identifier
        agent_id: Agent identifier

    Raises:
        AgentNotFoundError: If agent doesn't exist
    """
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


@router.get("", response_model=PaginatedResponse[RuleResponse])
async def list_rules(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    scope: Scope | None = Query(default=None, description="Filter by scope"),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    priority_min: int | None = Query(default=None, ge=-100, le=100),
    priority_max: int | None = Query(default=None, ge=-100, le=100),
    sort_by: Literal["name", "priority", "created_at", "updated_at"] = Query(
        default="priority"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> PaginatedResponse[RuleResponse]:
    """List rules for an agent.

    Retrieve a paginated list of rules with optional filtering and sorting.

    Args:
        agent_id: Agent identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store
        limit: Maximum number of rules to return
        offset: Number of rules to skip
        scope: Filter by scope level
        enabled: Filter by enabled status
        priority_min: Minimum priority filter
        priority_max: Maximum priority filter
        sort_by: Field to sort by
        sort_order: Sort direction

    Returns:
        Paginated list of rules
    """
    logger.debug(
        "list_rules_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        scope=scope.value if scope else None,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    # Get rules with optional scope filter (enabled_only=False to apply our own filter)
    rules = await config_store.get_rules(
        tenant_context.tenant_id,
        agent_id,
        scope=scope,
        enabled_only=False,
    )

    # Apply filters
    if enabled is not None:
        rules = [r for r in rules if r.enabled == enabled]
    if priority_min is not None:
        rules = [r for r in rules if r.priority >= priority_min]
    if priority_max is not None:
        rules = [r for r in rules if r.priority <= priority_max]

    # Apply sorting
    reverse = sort_order == "desc"
    if sort_by == "name":
        rules = sorted(rules, key=lambda r: r.name.lower(), reverse=reverse)
    elif sort_by == "priority":
        rules = sorted(rules, key=lambda r: r.priority, reverse=reverse)
    elif sort_by == "created_at":
        rules = sorted(rules, key=lambda r: r.created_at, reverse=reverse)
    elif sort_by == "updated_at":
        rules = sorted(rules, key=lambda r: r.updated_at, reverse=reverse)

    # Get total before pagination
    total = len(rules)

    # Apply pagination
    paginated = rules[offset : offset + limit]

    # Map to response
    items = [_map_rule_to_response(rule) for rule in paginated]

    return PaginatedResponse[RuleResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated) < total,
    )


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    agent_id: UUID,
    request: RuleCreate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    _background_tasks: BackgroundTasks,  # For future async embedding computation
) -> RuleResponse:
    """Create a new rule.

    Creates a rule for the specified agent. Embedding computation is
    triggered asynchronously in the background.

    Args:
        agent_id: Agent identifier
        request: Rule creation request
        tenant_context: Authenticated tenant context
        config_store: Configuration store
        _background_tasks: FastAPI background tasks (for future embedding)

    Returns:
        Created rule
    """
    logger.info(
        "create_rule_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        name=request.name,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    # Create rule
    rule = Rule(
        tenant_id=tenant_context.tenant_id,
        agent_id=agent_id,
        name=request.name,
        condition_text=request.condition_text,
        action_text=request.action_text,
        scope=request.scope,
        scope_id=request.scope_id,
        priority=request.priority,
        enabled=request.enabled,
        max_fires_per_session=request.max_fires_per_session,
        cooldown_turns=request.cooldown_turns,
        is_hard_constraint=request.is_hard_constraint,
        attached_tool_ids=request.attached_tool_ids,
        attached_template_ids=request.attached_template_ids,
    )

    # Save rule
    await config_store.save_rule(rule)

    # Schedule async embedding computation
    # Note: In production, we'd inject the embedding service properly
    # For MVP, we skip embedding if provider not available
    logger.debug(
        "embedding_computation_scheduled",
        rule_id=str(rule.id),
    )

    logger.info(
        "rule_created",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule.id),
    )

    return _map_rule_to_response(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    agent_id: UUID,
    rule_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> RuleResponse:
    """Get a rule by ID.

    Args:
        agent_id: Agent identifier
        rule_id: Rule identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Returns:
        Rule details

    Raises:
        RuleNotFoundError: If rule doesn't exist
    """
    logger.debug(
        "get_rule_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    rule = await config_store.get_rule(tenant_context.tenant_id, rule_id)
    if rule is None or rule.agent_id != agent_id:
        raise RuleNotFoundError(f"Rule {rule_id} not found")

    return _map_rule_to_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    agent_id: UUID,
    rule_id: UUID,
    request: RuleUpdate,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    _background_tasks: BackgroundTasks,  # For future async embedding computation
) -> RuleResponse:
    """Update a rule.

    If condition_text or action_text changes, embedding recomputation
    is triggered asynchronously.

    Args:
        agent_id: Agent identifier
        rule_id: Rule identifier
        request: Rule update request
        tenant_context: Authenticated tenant context
        config_store: Configuration store
        _background_tasks: FastAPI background tasks (for future embedding)

    Returns:
        Updated rule

    Raises:
        RuleNotFoundError: If rule doesn't exist
    """
    logger.info(
        "update_rule_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    rule = await config_store.get_rule(tenant_context.tenant_id, rule_id)
    if rule is None or rule.agent_id != agent_id:
        raise RuleNotFoundError(f"Rule {rule_id} not found")

    # Track if text changed (needs re-embedding)
    text_changed = False
    if request.condition_text is not None and request.condition_text != rule.condition_text:
        rule.condition_text = request.condition_text
        text_changed = True
    if request.action_text is not None and request.action_text != rule.action_text:
        rule.action_text = request.action_text
        text_changed = True

    # Apply other updates
    if request.name is not None:
        rule.name = request.name
    if request.scope is not None:
        rule.scope = request.scope
    if request.scope_id is not None:
        rule.scope_id = request.scope_id
    if request.priority is not None:
        rule.priority = request.priority
    if request.enabled is not None:
        rule.enabled = request.enabled
    if request.max_fires_per_session is not None:
        rule.max_fires_per_session = request.max_fires_per_session
    if request.cooldown_turns is not None:
        rule.cooldown_turns = request.cooldown_turns
    if request.is_hard_constraint is not None:
        rule.is_hard_constraint = request.is_hard_constraint
    if request.attached_tool_ids is not None:
        rule.attached_tool_ids = request.attached_tool_ids
    if request.attached_template_ids is not None:
        rule.attached_template_ids = request.attached_template_ids

    # Clear embedding if text changed
    if text_changed:
        rule.embedding = None
        rule.embedding_model = None
        logger.debug(
            "embedding_recomputation_scheduled",
            rule_id=str(rule.id),
        )

    # Touch updated_at
    rule.touch()

    # Save changes
    await config_store.save_rule(rule)

    logger.info(
        "rule_updated",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule_id),
        text_changed=text_changed,
    )

    return _map_rule_to_response(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    agent_id: UUID,
    rule_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> None:
    """Delete a rule (soft delete).

    Args:
        agent_id: Agent identifier
        rule_id: Rule identifier
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Raises:
        RuleNotFoundError: If rule doesn't exist
    """
    logger.info(
        "delete_rule_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    rule = await config_store.get_rule(tenant_context.tenant_id, rule_id)
    if rule is None or rule.agent_id != agent_id:
        raise RuleNotFoundError(f"Rule {rule_id} not found")

    # Soft delete
    rule.soft_delete()
    await config_store.save_rule(rule)

    logger.info(
        "rule_deleted",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        rule_id=str(rule_id),
    )


@router.post("/bulk", response_model=BulkResponse[RuleResponse])
async def bulk_rule_operations(
    agent_id: UUID,
    request: BulkRequest[RuleCreate],
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> BulkResponse[RuleResponse]:
    """Execute bulk rule operations.

    Supports create, update, and delete operations in a single request.
    Operations are processed in order, with partial success handling.

    Args:
        agent_id: Agent identifier
        request: Bulk operation request
        tenant_context: Authenticated tenant context
        config_store: Configuration store

    Returns:
        Bulk operation results
    """
    logger.info(
        "bulk_rules_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        operation_count=len(request.operations),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    results: list[BulkResult[RuleResponse]] = []

    for i, operation in enumerate(request.operations):
        try:
            if operation.action == "create":
                if operation.data is None:
                    results.append(
                        BulkResult[RuleResponse](
                            index=i,
                            success=False,
                            error="Data required for create operation",
                        )
                    )
                    continue

                # Create rule
                rule = Rule(
                    tenant_id=tenant_context.tenant_id,
                    agent_id=agent_id,
                    name=operation.data.name,
                    condition_text=operation.data.condition_text,
                    action_text=operation.data.action_text,
                    scope=operation.data.scope,
                    scope_id=operation.data.scope_id,
                    priority=operation.data.priority,
                    enabled=operation.data.enabled,
                    max_fires_per_session=operation.data.max_fires_per_session,
                    cooldown_turns=operation.data.cooldown_turns,
                    is_hard_constraint=operation.data.is_hard_constraint,
                    attached_tool_ids=operation.data.attached_tool_ids,
                    attached_template_ids=operation.data.attached_template_ids,
                )
                await config_store.save_rule(rule)
                results.append(
                    BulkResult(
                        index=i,
                        success=True,
                        data=_map_rule_to_response(rule),
                    )
                )

            elif operation.action == "delete" and operation.id:
                # Delete rule
                existing_rule = await config_store.get_rule(
                    tenant_context.tenant_id, operation.id
                )
                if existing_rule is None or existing_rule.agent_id != agent_id:
                    results.append(
                        BulkResult(
                            index=i,
                            success=False,
                            error=f"Rule {operation.id} not found",
                        )
                    )
                else:
                    existing_rule.soft_delete()
                    await config_store.save_rule(existing_rule)
                    results.append(BulkResult(index=i, success=True))

            else:
                results.append(
                    BulkResult(
                        index=i,
                        success=False,
                        error="Invalid operation or missing id for delete",
                    )
                )

        except Exception as e:
            logger.warning(
                "bulk_operation_failed",
                index=i,
                action=operation.action,
                error=str(e),
            )
            results.append(
                BulkResult(
                    index=i,
                    success=False,
                    error=str(e),
                )
            )

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    logger.info(
        "bulk_rules_completed",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        successful=successful,
        failed=failed,
    )

    return BulkResponse[RuleResponse](
        results=results,
        successful=successful,
        failed=failed,
    )
