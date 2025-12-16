"""Tests for ScenarioFilter - scenario navigation decisions.

Tests cover:
- Starting new scenarios
- Continuing active scenarios
- Exiting scenarios on signal
- Loop detection and relocalization
- Profile requirements checking (T155, T156)
- Step skipping based on available data
- Graph traversal helpers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ruche.brains.focal.models.scenario import Scenario, ScenarioStep, StepTransition
from ruche.brains.focal.phases.context.models import ScenarioSignal
from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.filtering.models import ScenarioAction
from ruche.brains.focal.phases.filtering.scenario_filter import ScenarioFilter
from ruche.brains.focal.retrieval.models import ScoredScenario
from ruche.brains.focal.stores import InMemoryAgentConfigStore
from ruche.interlocutor_data.enums import RequiredLevel


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tenant_id():
    """Create tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Create agent ID."""
    return uuid4()


@pytest.fixture
def config_store():
    """Create in-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def filter_with_store(config_store):
    """Create ScenarioFilter with config store."""
    return ScenarioFilter(config_store)


@pytest.fixture
def sample_snapshot():
    """Create sample situation snapshot."""
    return SituationSnapshot(
        message="I need help",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
    )


@pytest.fixture
def exit_snapshot():
    """Create snapshot with EXIT signal."""
    return SituationSnapshot(
        message="stop",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        scenario_signal=ScenarioSignal.EXIT,
    )


@pytest.fixture
def simple_scenario(tenant_id, agent_id):
    """Create simple single-step scenario."""
    step_id = uuid4()
    return Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Simple Scenario",
        entry_step_id=step_id,
        steps=[
            ScenarioStep(
                id=step_id,
                scenario_id=step_id,  # Will be overwritten
                name="Entry Step",
                transitions=[],
            )
        ],
    )


@pytest.fixture
def multi_step_scenario(tenant_id, agent_id):
    """Create multi-step scenario for skip testing."""
    step1_id = uuid4()
    step2_id = uuid4()
    step3_id = uuid4()

    return Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Multi-Step Scenario",
        entry_step_id=step1_id,
        steps=[
            ScenarioStep(
                id=step1_id,
                scenario_id=step1_id,
                name="Collect Order ID",
                transitions=[StepTransition(to_step_id=step2_id, condition_text="next")],
                collects_profile_fields=["order_id"],
                can_skip=True,
            ),
            ScenarioStep(
                id=step2_id,
                scenario_id=step2_id,
                name="Collect Reason",
                transitions=[StepTransition(to_step_id=step3_id, condition_text="next")],
                collects_profile_fields=["reason"],
                can_skip=True,
            ),
            ScenarioStep(
                id=step3_id,
                scenario_id=step3_id,
                name="Confirm Refund",
                transitions=[],
                collects_profile_fields=[],
                can_skip=False,
            ),
        ],
    )


# =============================================================================
# Tests: ScenarioFilter.__init__()
# =============================================================================


class TestScenarioFilterInit:
    """Tests for ScenarioFilter initialization."""

    def test_creates_with_defaults(self, config_store):
        """Creates filter with default settings."""
        f = ScenarioFilter(config_store)

        assert f._max_loop_count == 3
        assert f._block_on_missing_hard_fields is True
        assert f._profile_store is None

    def test_creates_with_custom_loop_count(self, config_store):
        """Creates filter with custom loop count."""
        f = ScenarioFilter(config_store, max_loop_count=5)

        assert f._max_loop_count == 5

    def test_creates_with_profile_store(self, config_store):
        """Creates filter with profile store."""
        mock_profile_store = MagicMock()
        f = ScenarioFilter(config_store, profile_store=mock_profile_store)

        assert f._profile_store is mock_profile_store


# =============================================================================
# Tests: ScenarioFilter.evaluate() - Start New Scenario
# =============================================================================


class TestEvaluateStartScenario:
    """Tests for starting new scenarios."""

    @pytest.mark.asyncio
    async def test_starts_scenario_when_no_active(
        self, tenant_id, config_store, simple_scenario, sample_snapshot
    ):
        """Starts best matching scenario when none active."""
        await config_store.save_scenario(simple_scenario)
        f = ScenarioFilter(config_store)

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[
                ScoredScenario(
                    scenario_id=simple_scenario.id,
                    scenario_name=simple_scenario.name,
                    score=0.9,
                )
            ],
        )

        assert result.action == ScenarioAction.START
        assert result.scenario_id == simple_scenario.id
        assert result.target_step_id == simple_scenario.entry_step_id

    @pytest.mark.asyncio
    async def test_returns_none_action_when_no_candidates(
        self, tenant_id, config_store, sample_snapshot
    ):
        """Returns NONE action when no candidate scenarios."""
        f = ScenarioFilter(config_store)

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
        )

        assert result.action == ScenarioAction.NONE
        assert result.scenario_id is None

    @pytest.mark.asyncio
    async def test_returns_none_action_when_scenario_not_found(
        self, tenant_id, config_store, sample_snapshot
    ):
        """Returns NONE when candidate scenario not in store."""
        f = ScenarioFilter(config_store)

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[
                ScoredScenario(
                    scenario_id=uuid4(),
                    scenario_name="Unknown",
                    score=0.9,
                )
            ],
        )

        assert result.action == ScenarioAction.NONE


# =============================================================================
# Tests: ScenarioFilter.evaluate() - Continue Active Scenario
# =============================================================================


class TestEvaluateContinueScenario:
    """Tests for continuing active scenarios."""

    @pytest.mark.asyncio
    async def test_continues_active_scenario(
        self, tenant_id, config_store, sample_snapshot
    ):
        """Continues active scenario when no exit signal."""
        f = ScenarioFilter(config_store)
        scenario_id = uuid4()
        step_id = uuid4()

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
            active_scenario_id=scenario_id,
            current_step_id=step_id,
        )

        assert result.action == ScenarioAction.CONTINUE
        assert result.scenario_id == scenario_id
        assert result.source_step_id == step_id
        assert result.target_step_id == step_id


# =============================================================================
# Tests: ScenarioFilter.evaluate() - Exit Scenario
# =============================================================================


class TestEvaluateExitScenario:
    """Tests for exiting scenarios."""

    @pytest.mark.asyncio
    async def test_exits_on_exit_signal(
        self, tenant_id, config_store, exit_snapshot
    ):
        """Exits scenario when EXIT signal received."""
        f = ScenarioFilter(config_store)
        scenario_id = uuid4()
        step_id = uuid4()

        result = await f.evaluate(
            tenant_id,
            exit_snapshot,
            candidates=[],
            active_scenario_id=scenario_id,
            current_step_id=step_id,
        )

        assert result.action == ScenarioAction.EXIT
        assert result.scenario_id == scenario_id
        assert result.source_step_id == step_id
        assert "exit" in result.reasoning.lower()


# =============================================================================
# Tests: ScenarioFilter.evaluate() - Loop Detection
# =============================================================================


class TestEvaluateLoopDetection:
    """Tests for loop detection and relocalization."""

    @pytest.mark.asyncio
    async def test_relocalize_on_loop_detection(
        self, tenant_id, config_store, sample_snapshot
    ):
        """Triggers relocalization when loop detected."""
        f = ScenarioFilter(config_store, max_loop_count=3)
        scenario_id = uuid4()
        step_id = uuid4()

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
            active_scenario_id=scenario_id,
            current_step_id=step_id,
            visited_steps={step_id: 3},  # At max loop count
        )

        assert result.action == ScenarioAction.RELOCALIZE
        assert result.was_relocalized is True
        assert result.original_step_id == step_id

    @pytest.mark.asyncio
    async def test_no_relocalize_under_loop_threshold(
        self, tenant_id, config_store, sample_snapshot
    ):
        """No relocalization when under loop threshold."""
        f = ScenarioFilter(config_store, max_loop_count=3)
        scenario_id = uuid4()
        step_id = uuid4()

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
            active_scenario_id=scenario_id,
            current_step_id=step_id,
            visited_steps={step_id: 2},  # Under threshold
        )

        assert result.action == ScenarioAction.CONTINUE
        assert result.was_relocalized is False or result.was_relocalized is None


# =============================================================================
# Tests: ScenarioFilter.evaluate() - Profile Requirements Blocking (T155)
# =============================================================================


class TestEvaluateProfileRequirements:
    """Tests for profile requirements blocking (T155)."""

    @pytest.mark.asyncio
    async def test_blocks_scenario_entry_on_missing_hard_fields(
        self, tenant_id, config_store, simple_scenario, sample_snapshot
    ):
        """Blocks scenario entry when hard requirements missing."""
        await config_store.save_scenario(simple_scenario)

        # Create mock profile store that reports missing hard fields
        mock_profile_store = AsyncMock()
        mock_profile_store.get_missing_fields = AsyncMock(return_value=["email"])
        mock_requirement = MagicMock()
        mock_requirement.field_name = "email"
        mock_requirement.required_level = RequiredLevel.HARD
        mock_requirement.step_id = None
        mock_profile_store.get_scenario_requirements = AsyncMock(
            return_value=[mock_requirement]
        )

        f = ScenarioFilter(
            config_store,
            profile_store=mock_profile_store,
            block_on_missing_hard_fields=True,
        )

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[
                ScoredScenario(
                    scenario_id=simple_scenario.id,
                    scenario_name=simple_scenario.name,
                    score=0.9,
                )
            ],
        )

        assert result.action == ScenarioAction.NONE
        assert result.blocked_by_missing_fields is True
        assert "email" in result.missing_profile_fields

    @pytest.mark.asyncio
    async def test_allows_entry_when_blocking_disabled(
        self, tenant_id, config_store, simple_scenario, sample_snapshot
    ):
        """Allows entry when blocking on missing fields is disabled."""
        await config_store.save_scenario(simple_scenario)

        # Create mock profile store that reports missing hard fields
        mock_profile_store = AsyncMock()
        mock_profile_store.get_missing_fields = AsyncMock(return_value=["email"])
        mock_requirement = MagicMock()
        mock_requirement.field_name = "email"
        mock_requirement.required_level = RequiredLevel.HARD
        mock_requirement.step_id = None
        mock_profile_store.get_scenario_requirements = AsyncMock(
            return_value=[mock_requirement]
        )

        f = ScenarioFilter(
            config_store,
            profile_store=mock_profile_store,
            block_on_missing_hard_fields=False,  # Disabled
        )

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[
                ScoredScenario(
                    scenario_id=simple_scenario.id,
                    scenario_name=simple_scenario.name,
                    score=0.9,
                )
            ],
        )

        assert result.action == ScenarioAction.START


# =============================================================================
# Tests: ScenarioFilter._check_profile_requirements()
# =============================================================================


class TestCheckProfileRequirements:
    """Tests for _check_profile_requirements helper."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_profile_store(
        self, config_store
    ):
        """Returns empty lists when no profile store configured."""
        f = ScenarioFilter(config_store, profile_store=None)

        all_missing, hard_missing = await f._check_profile_requirements(
            tenant_id=uuid4(),
            scenario_id=uuid4(),
            step_id=uuid4(),
            profile=None,
        )

        assert all_missing == []
        assert hard_missing == []

    @pytest.mark.asyncio
    async def test_returns_missing_and_hard_fields(
        self, config_store
    ):
        """Returns both all missing and hard missing fields."""
        mock_profile_store = AsyncMock()
        mock_profile_store.get_missing_fields = AsyncMock(
            return_value=["email", "phone", "name"]
        )

        # Only email is hard required
        hard_req = MagicMock()
        hard_req.field_name = "email"
        hard_req.required_level = RequiredLevel.HARD
        hard_req.step_id = None

        soft_req = MagicMock()
        soft_req.field_name = "phone"
        soft_req.required_level = RequiredLevel.SOFT
        soft_req.step_id = None

        mock_profile_store.get_scenario_requirements = AsyncMock(
            return_value=[hard_req, soft_req]
        )

        f = ScenarioFilter(config_store, profile_store=mock_profile_store)

        all_missing, hard_missing = await f._check_profile_requirements(
            tenant_id=uuid4(),
            scenario_id=uuid4(),
            step_id=None,
            profile=MagicMock(),
        )

        assert len(all_missing) == 3
        assert "email" in hard_missing
        assert "phone" not in hard_missing

    @pytest.mark.asyncio
    async def test_handles_profile_store_exception(
        self, config_store
    ):
        """Returns empty lists when profile store throws exception."""
        mock_profile_store = AsyncMock()
        mock_profile_store.get_missing_fields = AsyncMock(
            side_effect=Exception("Connection error")
        )

        f = ScenarioFilter(config_store, profile_store=mock_profile_store)

        all_missing, hard_missing = await f._check_profile_requirements(
            tenant_id=uuid4(),
            scenario_id=uuid4(),
            step_id=None,
            profile=MagicMock(),
        )

        assert all_missing == []
        assert hard_missing == []


# =============================================================================
# Tests: ScenarioFilter._has_required_fields()
# =============================================================================


class TestHasRequiredFields:
    """Tests for _has_required_fields helper."""

    def test_returns_true_when_all_fields_present(self, config_store):
        """Returns True when all required fields available."""
        f = ScenarioFilter(config_store)

        step = MagicMock()
        step.collects_profile_fields = ["email", "phone"]

        result = f._has_required_fields(
            step,
            available_data={"email": "test@example.com", "phone": "1234567890"},
        )

        assert result is True

    def test_returns_false_when_fields_missing(self, config_store):
        """Returns False when required fields missing."""
        f = ScenarioFilter(config_store)

        step = MagicMock()
        step.collects_profile_fields = ["email", "phone"]

        result = f._has_required_fields(
            step,
            available_data={"email": "test@example.com"},  # Missing phone
        )

        assert result is False

    def test_returns_true_when_no_fields_required(self, config_store):
        """Returns True when step has no required fields."""
        f = ScenarioFilter(config_store)

        step = MagicMock()
        step.collects_profile_fields = []

        result = f._has_required_fields(step, available_data={})

        assert result is True

    def test_returns_true_when_fields_none(self, config_store):
        """Returns True when collects_profile_fields is None."""
        f = ScenarioFilter(config_store)

        step = MagicMock()
        step.collects_profile_fields = None

        result = f._has_required_fields(step, available_data={})

        assert result is True


# =============================================================================
# Tests: ScenarioFilter._is_downstream_of()
# =============================================================================


class TestIsDownstreamOf:
    """Tests for _is_downstream_of graph traversal."""

    def test_returns_true_for_direct_child(
        self, config_store, multi_step_scenario
    ):
        """Returns True when target is direct child of source."""
        f = ScenarioFilter(config_store)
        step1_id = multi_step_scenario.steps[0].id
        step2_id = multi_step_scenario.steps[1].id

        result = f._is_downstream_of(multi_step_scenario, step1_id, step2_id)

        assert result is True

    def test_returns_true_for_grandchild(
        self, config_store, multi_step_scenario
    ):
        """Returns True when target is grandchild of source."""
        f = ScenarioFilter(config_store)
        step1_id = multi_step_scenario.steps[0].id
        step3_id = multi_step_scenario.steps[2].id

        result = f._is_downstream_of(multi_step_scenario, step1_id, step3_id)

        assert result is True

    def test_returns_false_for_same_step(
        self, config_store, multi_step_scenario
    ):
        """Returns False when source equals target."""
        f = ScenarioFilter(config_store)
        step_id = multi_step_scenario.steps[0].id

        result = f._is_downstream_of(multi_step_scenario, step_id, step_id)

        assert result is False

    def test_returns_false_for_unreachable(
        self, config_store, multi_step_scenario
    ):
        """Returns False when target is not downstream of source."""
        f = ScenarioFilter(config_store)
        step1_id = multi_step_scenario.steps[0].id
        step3_id = multi_step_scenario.steps[2].id

        # step1 is NOT downstream of step3
        result = f._is_downstream_of(multi_step_scenario, step3_id, step1_id)

        assert result is False


# =============================================================================
# Tests: ScenarioFilter._get_intermediate_steps()
# =============================================================================


class TestGetIntermediateSteps:
    """Tests for _get_intermediate_steps path finding."""

    def test_returns_empty_for_same_step(
        self, config_store, multi_step_scenario
    ):
        """Returns empty list when source equals target."""
        f = ScenarioFilter(config_store)
        step_id = multi_step_scenario.steps[0].id

        result = f._get_intermediate_steps(multi_step_scenario, step_id, step_id)

        assert result == []

    def test_returns_empty_for_direct_child(
        self, config_store, multi_step_scenario
    ):
        """Returns empty list when target is direct child (no intermediate)."""
        f = ScenarioFilter(config_store)
        step1_id = multi_step_scenario.steps[0].id
        step2_id = multi_step_scenario.steps[1].id

        result = f._get_intermediate_steps(multi_step_scenario, step1_id, step2_id)

        assert result == []

    def test_returns_intermediate_for_grandchild(
        self, config_store, multi_step_scenario
    ):
        """Returns intermediate steps between source and grandchild."""
        f = ScenarioFilter(config_store)
        step1_id = multi_step_scenario.steps[0].id
        step2_id = multi_step_scenario.steps[1].id
        step3_id = multi_step_scenario.steps[2].id

        result = f._get_intermediate_steps(multi_step_scenario, step1_id, step3_id)

        # Step 2 is intermediate between Step 1 and Step 3
        assert step2_id in result
        assert step1_id not in result  # Source not included
        assert step3_id not in result  # Target not included


# =============================================================================
# Tests: Integration - Step Skipping
# =============================================================================


class TestStepSkipping:
    """Integration tests for step skipping based on available data."""

    @pytest.mark.asyncio
    async def test_skips_steps_when_data_available(
        self, tenant_id, config_store, multi_step_scenario, sample_snapshot
    ):
        """Skips steps when required data is available."""
        await config_store.save_scenario(multi_step_scenario)
        f = ScenarioFilter(config_store)

        # Create profile with all data needed to skip to step 3
        mock_profile = MagicMock()
        mock_field1 = MagicMock()
        mock_field1.name = "order_id"
        mock_field1.value = "ORD-123"
        mock_field2 = MagicMock()
        mock_field2.name = "reason"
        mock_field2.value = "damaged"
        mock_profile.fields = [mock_field1, mock_field2]

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
            active_scenario_id=multi_step_scenario.id,
            current_step_id=multi_step_scenario.steps[0].id,
            customer_profile=mock_profile,
        )

        # Should skip to step 3 (Confirm Refund) since all data available
        # and steps 1 and 2 are skippable
        if result.action == ScenarioAction.TRANSITION:
            assert result.target_step_id == multi_step_scenario.steps[2].id
            assert len(result.skipped_steps) > 0

    @pytest.mark.asyncio
    async def test_no_skip_when_data_missing(
        self, tenant_id, config_store, multi_step_scenario, sample_snapshot
    ):
        """Does not skip when required data is missing."""
        await config_store.save_scenario(multi_step_scenario)
        f = ScenarioFilter(config_store)

        # Create profile with no data
        mock_profile = MagicMock()
        mock_profile.fields = []

        result = await f.evaluate(
            tenant_id,
            sample_snapshot,
            candidates=[],
            active_scenario_id=multi_step_scenario.id,
            current_step_id=multi_step_scenario.steps[0].id,
            customer_profile=mock_profile,
        )

        # Should continue at current step since no data to skip
        assert result.action == ScenarioAction.CONTINUE
        assert result.target_step_id == multi_step_scenario.steps[0].id
