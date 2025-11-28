"""Tests for alignment domain models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from soldier.alignment.models import (
    Context,
    ExtractedEntities,
    MatchedRule,
    Rule,
    Scenario,
    ScenarioStep,
    Scope,
    StepTransition,
    Template,
    TemplateMode,
    UserIntent,
    Variable,
    VariableUpdatePolicy,
)


class TestRule:
    """Tests for Rule model."""

    def test_create_valid_rule(self) -> None:
        """Should create a valid rule with required fields."""
        rule = Rule(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Test Rule",
            condition_text="When user asks about refunds",
            action_text="Explain the refund policy",
        )
        assert rule.name == "Test Rule"
        assert rule.scope == Scope.GLOBAL
        assert rule.priority == 0
        assert rule.enabled is True

    def test_rule_priority_validation(self) -> None:
        """Should validate priority is between -100 and 100."""
        with pytest.raises(ValidationError):
            Rule(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="Test",
                condition_text="Test",
                action_text="Test",
                priority=150,
            )

        with pytest.raises(ValidationError):
            Rule(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="Test",
                condition_text="Test",
                action_text="Test",
                priority=-150,
            )

    def test_rule_name_min_length(self) -> None:
        """Should require name to be at least 1 character."""
        with pytest.raises(ValidationError):
            Rule(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="",
                condition_text="Test",
                action_text="Test",
            )

    def test_rule_with_embedding(self) -> None:
        """Should accept embedding vector."""
        rule = Rule(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Test Rule",
            condition_text="Test",
            action_text="Test",
            embedding=[0.1, 0.2, 0.3],
            embedding_model="test-model",
        )
        assert rule.embedding == [0.1, 0.2, 0.3]
        assert rule.embedding_model == "test-model"


class TestScenario:
    """Tests for Scenario model."""

    def test_create_valid_scenario(self) -> None:
        """Should create a valid scenario."""
        entry_step_id = uuid4()
        scenario = Scenario(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Test Scenario",
            entry_step_id=entry_step_id,
        )
        assert scenario.name == "Test Scenario"
        assert scenario.entry_step_id == entry_step_id
        assert scenario.version == 1
        assert scenario.enabled is True

    def test_scenario_with_steps(self) -> None:
        """Should create scenario with steps."""
        scenario_id = uuid4()
        step = ScenarioStep(
            scenario_id=scenario_id,
            name="Step 1",
            is_entry=True,
        )
        scenario = Scenario(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Test Scenario",
            entry_step_id=step.id,
            steps=[step],
        )
        assert len(scenario.steps) == 1
        assert scenario.steps[0].is_entry is True


class TestScenarioStep:
    """Tests for ScenarioStep model."""

    def test_create_valid_step(self) -> None:
        """Should create a valid step."""
        step = ScenarioStep(
            scenario_id=uuid4(),
            name="Welcome Step",
        )
        assert step.name == "Welcome Step"
        assert step.is_entry is False
        assert step.is_terminal is False

    def test_step_with_transitions(self) -> None:
        """Should create step with transitions."""
        target_id = uuid4()
        transition = StepTransition(
            to_step_id=target_id,
            condition_text="User confirms",
        )
        step = ScenarioStep(
            scenario_id=uuid4(),
            name="Step",
            transitions=[transition],
        )
        assert len(step.transitions) == 1
        assert step.transitions[0].to_step_id == target_id


class TestTemplate:
    """Tests for Template model."""

    def test_create_valid_template(self) -> None:
        """Should create a valid template."""
        template = Template(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Welcome Template",
            text="Hello {name}, how can I help you?",
        )
        assert template.name == "Welcome Template"
        assert template.mode == TemplateMode.SUGGEST

    def test_template_modes(self) -> None:
        """Should accept different modes."""
        for mode in TemplateMode:
            template = Template(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="Test",
                text="Test text",
                mode=mode,
            )
            assert template.mode == mode


class TestVariable:
    """Tests for Variable model."""

    def test_create_valid_variable(self) -> None:
        """Should create a valid variable."""
        variable = Variable(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="user_name",
            resolver_tool_id="get_user_name",
        )
        assert variable.name == "user_name"
        assert variable.update_policy == VariableUpdatePolicy.ON_DEMAND

    def test_variable_name_pattern(self) -> None:
        """Should validate variable name pattern."""
        with pytest.raises(ValidationError):
            Variable(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="Invalid Name",  # Has spaces and uppercase
                resolver_tool_id="test",
            )


class TestContext:
    """Tests for Context model."""

    def test_create_valid_context(self) -> None:
        """Should create a valid context."""
        context = Context(
            user_intent=UserIntent(primary="refund_request", confidence=0.95),
            entities=ExtractedEntities(entities={"order_id": ["12345"]}),
            raw_message="I want to return order 12345",
        )
        assert context.user_intent.primary == "refund_request"
        assert context.entities.entities["order_id"] == ["12345"]


class TestMatchedRule:
    """Tests for MatchedRule model."""

    def test_create_matched_rule(self) -> None:
        """Should create a matched rule."""
        rule = Rule(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Test",
            condition_text="Test",
            action_text="Test",
        )
        matched = MatchedRule(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            rule=rule,
            similarity_score=0.85,
            final_score=0.90,
            newly_fired=True,
        )
        assert matched.similarity_score == 0.85
        assert matched.newly_fired is True
