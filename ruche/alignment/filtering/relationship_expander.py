"""Relationship expansion for rule filtering.

Expands matched rules via depends_on, implies, and excludes relationships.
"""

from uuid import UUID

from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.models import Rule, RuleRelationship, RuleRelationshipKind
from ruche.alignment.stores import AgentConfigStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class RelationshipExpander:
    """Expands rule set via relationships after LLM filtering."""

    def __init__(self, config_store: AgentConfigStore):
        """Initialize the expander.

        Args:
            config_store: Store for retrieving rules and relationships
        """
        self._config_store = config_store

    async def expand(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        matched_rules: list[MatchedRule],
        max_depth: int = 2,
    ) -> list[MatchedRule]:
        """Expand matched rules via relationships.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            matched_rules: Rules that passed LLM filtering
            max_depth: Maximum relationship chain depth

        Returns:
            Expanded list of MatchedRule with derived rules included
        """
        if not matched_rules:
            return []

        # Get all relationships for this agent
        relationships = await self._config_store.get_rule_relationships(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        if not relationships:
            logger.debug("no_relationships_found", tenant_id=str(tenant_id), agent_id=str(agent_id))
            return matched_rules

        # Build relationship graph
        graph = self._build_graph(relationships)

        # Track rules to include/exclude
        included_rule_ids = {m.rule.id for m in matched_rules}
        excluded_rule_ids: set[UUID] = set()
        derived_rules: dict[UUID, tuple[Rule, str]] = {}

        # Expand via depends_on and implies
        for matched in matched_rules:
            await self._expand_from_rule(
                rule_id=matched.rule.id,
                graph=graph,
                included_rule_ids=included_rule_ids,
                excluded_rule_ids=excluded_rule_ids,
                derived_rules=derived_rules,
                depth=0,
                max_depth=max_depth,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

        # Apply exclusions
        for matched in matched_rules:
            self._apply_exclusions(
                rule_id=matched.rule.id,
                graph=graph,
                excluded_rule_ids=excluded_rule_ids,
            )

        # Remove excluded rules
        final_rules = [m for m in matched_rules if m.rule.id not in excluded_rule_ids]

        # Add derived rules
        for rule_id, (rule, reason) in derived_rules.items():
            if rule_id not in excluded_rule_ids:
                final_rules.append(
                    MatchedRule(
                        rule=rule,
                        match_score=1.0,
                        relevance_score=1.0,
                        reasoning=reason,
                    )
                )

        logger.info(
            "relationship_expansion_complete",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            original_count=len(matched_rules),
            expanded_count=len(final_rules),
            derived_count=len(derived_rules),
            excluded_count=len(excluded_rule_ids),
        )

        return final_rules

    def _build_graph(
        self,
        relationships: list[RuleRelationship],
    ) -> dict[UUID, list[tuple[UUID, RuleRelationshipKind]]]:
        """Build relationship graph as adjacency list."""
        graph: dict[UUID, list[tuple[UUID, RuleRelationshipKind]]] = {}
        for rel in relationships:
            if rel.source_rule_id not in graph:
                graph[rel.source_rule_id] = []
            graph[rel.source_rule_id].append((rel.target_rule_id, rel.kind))
        return graph

    async def _expand_from_rule(
        self,
        rule_id: UUID,
        graph: dict[UUID, list[tuple[UUID, RuleRelationshipKind]]],
        included_rule_ids: set[UUID],
        excluded_rule_ids: set[UUID],
        derived_rules: dict[UUID, tuple[Rule, str]],
        depth: int,
        max_depth: int,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Recursively expand via depends_on and implies."""
        if depth >= max_depth:
            return

        if rule_id not in graph:
            return

        for target_id, kind in graph[rule_id]:
            if kind not in [RuleRelationshipKind.DEPENDS_ON, RuleRelationshipKind.IMPLIES]:
                continue

            if target_id in included_rule_ids or target_id in derived_rules:
                continue

            if target_id in excluded_rule_ids:
                continue

            # Fetch target rule
            target_rule = await self._config_store.get_rule(tenant_id, target_id)
            if not target_rule or not target_rule.enabled:
                continue

            # Add to derived rules
            reason = f"Derived via {kind.value} from rule {rule_id}"
            derived_rules[target_id] = (target_rule, reason)

            logger.debug(
                "relationship_derived_rule",
                source_rule_id=str(rule_id),
                target_rule_id=str(target_id),
                kind=kind.value,
                depth=depth,
            )

            # Recurse
            await self._expand_from_rule(
                rule_id=target_id,
                graph=graph,
                included_rule_ids=included_rule_ids,
                excluded_rule_ids=excluded_rule_ids,
                derived_rules=derived_rules,
                depth=depth + 1,
                max_depth=max_depth,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

    def _apply_exclusions(
        self,
        rule_id: UUID,
        graph: dict[UUID, list[tuple[UUID, RuleRelationshipKind]]],
        excluded_rule_ids: set[UUID],
    ) -> None:
        """Apply exclusion relationships."""
        if rule_id not in graph:
            return

        for target_id, kind in graph[rule_id]:
            if kind == RuleRelationshipKind.EXCLUDES:
                excluded_rule_ids.add(target_id)
                logger.debug(
                    "relationship_excluded_rule",
                    source_rule_id=str(rule_id),
                    excluded_rule_id=str(target_id),
                )
