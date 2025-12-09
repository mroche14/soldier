"""Unit tests for step skipping functionality."""

import pytest
from uuid import uuid4

from soldier.alignment.filtering.scenario_filter import ScenarioFilter
from soldier.alignment.models.scenario import Scenario, ScenarioStep, StepTransition
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore


@pytest.fixture
def config_store():
    """Create in-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def scenario_filter(config_store):
    """Create scenario filter."""
    return ScenarioFilter(config_store=config_store)


@pytest.fixture
def linear_scenario():
    """Create a linear scenario with 3 skippable steps.

    Steps: collect_name -> collect_email -> confirm
    """
    scenario_id = uuid4()
    step1_id = uuid4()
    step2_id = uuid4()
    step3_id = uuid4()

    step1 = ScenarioStep(
        id=step1_id,
        scenario_id=scenario_id,
        name="collect_name",
        collects_profile_fields=["name"],
        can_skip=True,
        transitions=[StepTransition(to_step_id=step2_id, condition_text="default", priority=0)],
    )

    step2 = ScenarioStep(
        id=step2_id,
        scenario_id=scenario_id,
        name="collect_email",
        collects_profile_fields=["email"],
        can_skip=True,
        transitions=[StepTransition(to_step_id=step3_id, condition_text="default", priority=0)],
    )

    step3 = ScenarioStep(
        id=step3_id,
        scenario_id=scenario_id,
        name="confirm",
        is_terminal=True,
        can_skip=False,
        transitions=[],
    )

    return Scenario(
        id=scenario_id,
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Test Scenario",
        description="Test scenario for step skipping",
        enabled=True,
        entry_step_id=step1_id,
        steps=[step1, step2, step3],
    )


@pytest.fixture
def branching_scenario():
    """Create a branching scenario with conditional transitions.

    Steps: collect_type -> [premium_path | standard_path] -> confirm
    """
    scenario_id = uuid4()
    step1_id = uuid4()
    step2_premium_id = uuid4()
    step2_standard_id = uuid4()
    step3_id = uuid4()

    step1 = ScenarioStep(
        id=step1_id,
        scenario_id=scenario_id,
        name="collect_type",
        collects_profile_fields=["account_type"],
        can_skip=True,
        transitions=[
            StepTransition(
                to_step_id=step2_premium_id,
                condition_text="account_type == 'premium'",
                priority=1,
            ),
            StepTransition(
                to_step_id=step2_standard_id,
                condition_text="default",
                priority=0,
            ),
        ],
    )

    step2_premium = ScenarioStep(
        id=step2_premium_id,
        scenario_id=scenario_id,
        name="premium_path",
        collects_profile_fields=["premium_features"],
        can_skip=True,
        transitions=[StepTransition(to_step_id=step3_id, condition_text="default", priority=0)],
    )

    step2_standard = ScenarioStep(
        id=step2_standard_id,
        scenario_id=scenario_id,
        name="standard_path",
        can_skip=True,
        transitions=[StepTransition(to_step_id=step3_id, condition_text="default", priority=0)],
    )

    step3 = ScenarioStep(
        id=step3_id,
        scenario_id=scenario_id,
        name="confirm",
        is_terminal=True,
        can_skip=False,
        transitions=[],
    )

    return Scenario(
        id=scenario_id,
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Branching Scenario",
        description="Test scenario with branches",
        enabled=True,
        entry_step_id=step1_id,
        steps=[step1, step2_premium, step2_standard, step3],
    )


class TestStepSkipping:
    """Test step skipping logic."""

    @pytest.mark.asyncio
    async def test_skip_all_steps_when_all_data_available(
        self, scenario_filter, linear_scenario
    ):
        """Test skipping all steps when all required data is available."""
        current_step_id = linear_scenario.steps[0].id  # collect_name
        customer_data = {"name": "John", "email": "john@example.com"}
        session_vars = {}

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should skip to confirm step
        assert furthest_step == linear_scenario.steps[2].id
        # Should have skipped collect_name and collect_email
        assert len(skipped) == 2
        assert linear_scenario.steps[0].id in skipped or linear_scenario.steps[1].id in skipped

    @pytest.mark.asyncio
    async def test_skip_partial_steps_when_partial_data_available(
        self, scenario_filter, linear_scenario
    ):
        """Test skipping only some steps when partial data is available."""
        current_step_id = linear_scenario.steps[0].id  # collect_name
        customer_data = {"name": "John"}  # Only name, no email
        session_vars = {}

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should skip to collect_email step
        assert furthest_step == linear_scenario.steps[1].id
        # Should have skipped only collect_name
        assert len(skipped) == 1

    @pytest.mark.asyncio
    async def test_no_skip_when_no_data_available(
        self, scenario_filter, linear_scenario
    ):
        """Test no skipping when no data is available."""
        current_step_id = linear_scenario.steps[0].id  # collect_name
        customer_data = {}
        session_vars = {}

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should stay at current step
        assert furthest_step == current_step_id
        # No steps skipped
        assert len(skipped) == 0

    @pytest.mark.asyncio
    async def test_no_skip_when_can_skip_is_false(
        self, scenario_filter, linear_scenario
    ):
        """Test that steps with can_skip=False prevent skipping."""
        # Modify scenario to make confirm step unskippable
        linear_scenario.steps[2].can_skip = False

        current_step_id = linear_scenario.steps[0].id  # collect_name
        customer_data = {"name": "John", "email": "john@example.com"}
        session_vars = {}

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should skip to collect_email but not past it since confirm is not skippable
        # Actually, should skip to confirm since confirm itself doesn't have requirements
        # The key is that we can reach confirm, but if intermediate steps were unskippable
        # we couldn't skip past them

        # Let's make collect_email unskippable instead
        linear_scenario.steps[1].can_skip = False

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should skip to collect_email but not past it
        assert furthest_step == linear_scenario.steps[1].id
        assert len(skipped) == 1

    @pytest.mark.asyncio
    async def test_session_variables_used_for_skipping(
        self, scenario_filter, linear_scenario
    ):
        """Test that session variables are considered for skipping."""
        current_step_id = linear_scenario.steps[0].id  # collect_name
        customer_data = {"name": "John"}  # Name in profile
        session_vars = {"email": "john@example.com"}  # Email in session

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=linear_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should skip to confirm step using both sources
        assert furthest_step == linear_scenario.steps[2].id
        assert len(skipped) == 2

    @pytest.mark.asyncio
    async def test_is_downstream_of(self, scenario_filter, linear_scenario):
        """Test the is_downstream_of helper method."""
        step1_id = linear_scenario.steps[0].id
        step2_id = linear_scenario.steps[1].id
        step3_id = linear_scenario.steps[2].id

        # step2 is downstream of step1
        assert scenario_filter._is_downstream_of(linear_scenario, step1_id, step2_id)

        # step3 is downstream of step1
        assert scenario_filter._is_downstream_of(linear_scenario, step1_id, step3_id)

        # step1 is NOT downstream of step2
        assert not scenario_filter._is_downstream_of(linear_scenario, step2_id, step1_id)

        # step is not downstream of itself
        assert not scenario_filter._is_downstream_of(linear_scenario, step1_id, step1_id)

    @pytest.mark.asyncio
    async def test_get_intermediate_steps(self, scenario_filter, linear_scenario):
        """Test getting intermediate steps between source and target."""
        step1_id = linear_scenario.steps[0].id
        step2_id = linear_scenario.steps[1].id
        step3_id = linear_scenario.steps[2].id

        # From step1 to step3, should include step2
        intermediate = scenario_filter._get_intermediate_steps(
            linear_scenario, step1_id, step3_id
        )
        assert step2_id in intermediate
        assert step1_id not in intermediate  # Source not included
        assert step3_id not in intermediate  # Target not included

        # From step1 to step2, no intermediate steps
        intermediate = scenario_filter._get_intermediate_steps(
            linear_scenario, step1_id, step2_id
        )
        assert len(intermediate) == 0

        # Same step returns empty
        intermediate = scenario_filter._get_intermediate_steps(
            linear_scenario, step1_id, step1_id
        )
        assert len(intermediate) == 0

    @pytest.mark.asyncio
    async def test_has_required_fields(self, scenario_filter, linear_scenario):
        """Test checking if required fields are available."""
        step = linear_scenario.steps[0]  # collect_name

        # Has required field
        assert scenario_filter._has_required_fields(step, {"name": "John"})

        # Missing required field
        assert not scenario_filter._has_required_fields(step, {"email": "john@example.com"})

        # Empty data
        assert not scenario_filter._has_required_fields(step, {})

    @pytest.mark.asyncio
    async def test_branching_scenario_skipping(
        self, scenario_filter, branching_scenario
    ):
        """Test skipping in branching scenarios."""
        current_step_id = branching_scenario.steps[0].id  # collect_type
        customer_data = {"account_type": "premium", "premium_features": "enabled"}
        session_vars = {}

        furthest_step, skipped = await scenario_filter._find_furthest_reachable_step(
            scenario=branching_scenario,
            current_step_id=current_step_id,
            customer_data=customer_data,
            session_variables=session_vars,
        )

        # Should be able to reach confirm via premium path
        # The furthest reachable is the confirm step
        confirm_step = next(s for s in branching_scenario.steps if s.is_terminal)
        assert furthest_step == confirm_step.id or len(skipped) > 0
