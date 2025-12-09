"""Tests for relationship expansion in rule filtering."""

import pytest
from uuid import uuid4

from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.filtering.relationship_expander import RelationshipExpander
from soldier.alignment.models import Rule, RuleRelationship, RuleRelationshipKind, Scope
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def config_store():
    """In-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def expander(config_store):
    """Relationship expander instance."""
    return RelationshipExpander(config_store)


@pytest.fixture
def base_rule(tenant_id, agent_id):
    """Create a base rule factory."""

    def _create(rule_id=None, name="Test Rule", enabled=True):
        return Rule(
            id=rule_id or uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name=name,
            description="Test description",
            condition_text="test condition",
            action_text="test action",
            scope=Scope.GLOBAL,
            priority=100,
            enabled=enabled,
        )

    return _create


class TestRelationshipExpander:
    """Test suite for RelationshipExpander."""

    async def test_expand_with_no_relationships_returns_original(
        self, expander, tenant_id, agent_id, base_rule
    ):
        """Test that expansion with no relationships returns original rules."""
        rule = base_rule()
        matched = MatchedRule(
            rule=rule,
            match_score=0.9,
            relevance_score=0.8,
            reasoning="Test match",
        )

        result = await expander.expand(tenant_id, agent_id, [matched], max_depth=2)

        assert len(result) == 1
        assert result[0].rule.id == rule.id

    async def test_expand_with_empty_list_returns_empty(self, expander, tenant_id, agent_id):
        """Test that expansion with empty list returns empty list."""
        result = await expander.expand(tenant_id, agent_id, [], max_depth=2)
        assert len(result) == 0

    async def test_build_graph_from_empty_relationships(self, expander):
        """Test graph building from empty relationships."""
        graph = expander._build_graph([])
        assert graph == {}

    async def test_build_graph_from_single_relationship(self, expander, tenant_id, agent_id):
        """Test graph building from single relationship."""
        rel = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=uuid4(),
            target_rule_id=uuid4(),
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        graph = expander._build_graph([rel])

        assert rel.source_rule_id in graph
        assert len(graph[rel.source_rule_id]) == 1
        assert graph[rel.source_rule_id][0] == (rel.target_rule_id, RuleRelationshipKind.DEPENDS_ON)

    async def test_build_graph_from_complex_relationships(self, expander, tenant_id, agent_id):
        """Test graph building from complex relationships."""
        rule1 = uuid4()
        rule2 = uuid4()
        rule3 = uuid4()

        relationships = [
            RuleRelationship(
                tenant_id=tenant_id,
                agent_id=agent_id,
                source_rule_id=rule1,
                target_rule_id=rule2,
                kind=RuleRelationshipKind.DEPENDS_ON,
            ),
            RuleRelationship(
                tenant_id=tenant_id,
                agent_id=agent_id,
                source_rule_id=rule1,
                target_rule_id=rule3,
                kind=RuleRelationshipKind.IMPLIES,
            ),
            RuleRelationship(
                tenant_id=tenant_id,
                agent_id=agent_id,
                source_rule_id=rule2,
                target_rule_id=rule3,
                kind=RuleRelationshipKind.EXCLUDES,
            ),
        ]

        graph = expander._build_graph(relationships)

        assert len(graph[rule1]) == 2
        assert len(graph[rule2]) == 1
        assert rule3 not in graph

    async def test_expand_via_depends_on_depth_1(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test expansion via DEPENDS_ON relationship (depth 1)."""
        # Create rules
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")

        # Save rules
        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)

        # Create relationship: A depends_on B
        rel = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        await config_store.save_rule_relationship(rel)

        # Expand from A
        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should include both A and B
        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids

        # Check derived rule has correct reasoning
        derived = [r for r in result if r.rule.id == rule_b.id][0]
        assert "depends_on" in derived.reasoning.lower()

    async def test_expand_via_implies_depth_1(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test expansion via IMPLIES relationship (depth 1)."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)

        # A implies B
        rel = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.IMPLIES,
        )
        await config_store.save_rule_relationship(rel)

        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids

    async def test_expand_via_depends_on_chain_depth_2(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test expansion via DEPENDS_ON chain (depth 2)."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")
        rule_c = base_rule(name="Rule C")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)
        await config_store.save_rule(rule_c)

        # A -> B -> C
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_b.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should include A, B, and C
        assert len(result) == 3
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids
        assert rule_c.id in rule_ids

    async def test_respect_max_depth_limit(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test that max_depth limit is respected."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")
        rule_c = base_rule(name="Rule C")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)
        await config_store.save_rule(rule_c)

        # A -> B -> C
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_b.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        # With max_depth=1, should only get A and B
        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=1)

        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids
        assert rule_c.id not in rule_ids

    async def test_exclude_via_excludes_relationship(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test exclusion via EXCLUDES relationship."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)

        # A excludes B
        rel = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.EXCLUDES,
        )
        await config_store.save_rule_relationship(rel)

        # Start with both A and B
        matched = [
            MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test A"),
            MatchedRule(rule=rule_b, match_score=0.85, relevance_score=0.75, reasoning="Test B"),
        ]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # B should be excluded
        assert len(result) == 1
        assert result[0].rule.id == rule_a.id

    async def test_exclude_overrides_depends_on(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test that EXCLUDES overrides DEPENDS_ON."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")
        rule_c = base_rule(name="Rule C")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)
        await config_store.save_rule(rule_c)

        # B depends_on C, but A excludes C
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_b.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.EXCLUDES,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        # Start with A and B
        matched = [
            MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test A"),
            MatchedRule(rule=rule_b, match_score=0.85, relevance_score=0.75, reasoning="Test B"),
        ]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should have A and B, but not C (excluded by A)
        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids
        assert rule_c.id not in rule_ids

    async def test_multiple_exclusions(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test multiple exclusions."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")
        rule_c = base_rule(name="Rule C")
        rule_d = base_rule(name="Rule D")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)
        await config_store.save_rule(rule_c)
        await config_store.save_rule(rule_d)

        # A excludes B and C
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.EXCLUDES,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.EXCLUDES,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        # Start with all rules
        matched = [
            MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test A"),
            MatchedRule(rule=rule_b, match_score=0.85, relevance_score=0.75, reasoning="Test B"),
            MatchedRule(rule=rule_c, match_score=0.8, relevance_score=0.7, reasoning="Test C"),
            MatchedRule(rule=rule_d, match_score=0.75, relevance_score=0.65, reasoning="Test D"),
        ]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should have A and D, but not B or C
        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_d.id in rule_ids
        assert rule_b.id not in rule_ids
        assert rule_c.id not in rule_ids

    async def test_disabled_rule_not_included(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test that disabled rules are not included in expansion."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B", enabled=False)

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)

        # A depends_on B (but B is disabled)
        rel = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        await config_store.save_rule_relationship(rel)

        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should only have A (B is disabled)
        assert len(result) == 1
        assert result[0].rule.id == rule_a.id

    async def test_handles_circular_dependencies(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test that circular dependencies don't cause infinite loops."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)

        # A -> B -> A (circular)
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_b.id,
            target_rule_id=rule_a.id,
            kind=RuleRelationshipKind.DEPENDS_ON,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should have both A and B without infinite loop
        assert len(result) == 2
        rule_ids = {r.rule.id for r in result}
        assert rule_a.id in rule_ids
        assert rule_b.id in rule_ids

    async def test_ignores_specializes_and_related_relationships(
        self, expander, config_store, tenant_id, agent_id, base_rule
    ):
        """Test that SPECIALIZES and RELATED relationships are ignored for expansion."""
        rule_a = base_rule(name="Rule A")
        rule_b = base_rule(name="Rule B")
        rule_c = base_rule(name="Rule C")

        await config_store.save_rule(rule_a)
        await config_store.save_rule(rule_b)
        await config_store.save_rule(rule_c)

        # A specializes B (should be ignored)
        # A related C (should be ignored)
        rel1 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_b.id,
            kind=RuleRelationshipKind.SPECIALIZES,
        )
        rel2 = RuleRelationship(
            tenant_id=tenant_id,
            agent_id=agent_id,
            source_rule_id=rule_a.id,
            target_rule_id=rule_c.id,
            kind=RuleRelationshipKind.RELATED,
        )
        await config_store.save_rule_relationship(rel1)
        await config_store.save_rule_relationship(rel2)

        matched = [MatchedRule(rule=rule_a, match_score=0.9, relevance_score=0.8, reasoning="Test")]
        result = await expander.expand(tenant_id, agent_id, matched, max_depth=2)

        # Should only have A (B and C not expanded)
        assert len(result) == 1
        assert result[0].rule.id == rule_a.id
