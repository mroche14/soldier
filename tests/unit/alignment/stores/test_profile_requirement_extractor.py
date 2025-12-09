"""Unit tests for CustomerDataRequirementExtractor.

Tests T135-T138: Extraction hooks on Scenario/Rule create/update.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from soldier.alignment.models import Rule, Scenario
from soldier.alignment.stores import CustomerDataRequirementExtractor


@pytest.fixture
def mock_config_store():
    """Create a mock ConfigStore."""
    store = AsyncMock()
    store.save_scenario.return_value = uuid4()
    store.save_rule.return_value = uuid4()
    return store


@pytest.fixture
def mock_hatchet_client():
    """Create a mock Hatchet client."""
    client = MagicMock()
    client.admin = MagicMock()
    client.admin.run_workflow = AsyncMock()
    return client


@pytest.fixture
def sample_scenario():
    """Create a sample scenario."""
    entry_step_id = uuid4()
    return Scenario(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Test Scenario",
        description="If customer is over 18 years old",
        entry_step_id=entry_step_id,
        entry_condition_text="age >= 18",
        steps=[],
    )


@pytest.fixture
def sample_rule():
    """Create a sample rule."""
    return Rule(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Test Rule",
        condition_text="customer.email is verified",
        action_text="proceed with verification",
    )


class TestScenarioExtractionHooks:
    """Tests for T135-T136: Scenario extraction hooks."""

    @pytest.mark.asyncio
    async def test_save_scenario_triggers_extraction(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_scenario,
    ):
        """T135: save_scenario triggers extraction workflow."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        await wrapper.save_scenario(sample_scenario)

        # Verify underlying store was called
        mock_config_store.save_scenario.assert_called_once_with(sample_scenario)

        # Verify extraction workflow was triggered
        mock_hatchet_client.admin.run_workflow.assert_called_once()
        call_args = mock_hatchet_client.admin.run_workflow.call_args
        assert call_args[0][0] == "extract-schema-requirements"
        assert call_args[1]["input"]["content_type"] == "scenario"
        assert call_args[1]["input"]["content_id"] == str(sample_scenario.id)

    @pytest.mark.asyncio
    async def test_update_scenario_triggers_extraction(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_scenario,
    ):
        """T136: update_scenario triggers extraction workflow."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        await wrapper.update_scenario(sample_scenario)

        # Verify underlying store was called
        mock_config_store.save_scenario.assert_called_once_with(sample_scenario)

        # Verify extraction workflow was triggered
        mock_hatchet_client.admin.run_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_scenario_without_hatchet(
        self,
        mock_config_store,
        sample_scenario,
    ):
        """Test save_scenario works without Hatchet client."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=None,  # No Hatchet
        )

        result = await wrapper.save_scenario(sample_scenario)

        # Verify underlying store was called
        mock_config_store.save_scenario.assert_called_once_with(sample_scenario)
        assert result == mock_config_store.save_scenario.return_value

    @pytest.mark.asyncio
    async def test_save_scenario_extraction_disabled(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_scenario,
    ):
        """Test extraction can be disabled."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
            extraction_enabled=False,
        )

        await wrapper.save_scenario(sample_scenario)

        # Verify underlying store was called
        mock_config_store.save_scenario.assert_called_once_with(sample_scenario)

        # Verify extraction was NOT triggered
        mock_hatchet_client.admin.run_workflow.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_scenario_extraction_failure_non_blocking(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_scenario,
    ):
        """Test extraction failure doesn't block save."""
        mock_hatchet_client.admin.run_workflow.side_effect = Exception("Hatchet error")

        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        # Should not raise despite Hatchet failure
        result = await wrapper.save_scenario(sample_scenario)

        # Verify save still succeeded
        mock_config_store.save_scenario.assert_called_once()
        assert result == mock_config_store.save_scenario.return_value


class TestRuleExtractionHooks:
    """Tests for T137-T138: Rule extraction hooks."""

    @pytest.mark.asyncio
    async def test_save_rule_triggers_extraction(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_rule,
    ):
        """T137: save_rule triggers extraction workflow."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        await wrapper.save_rule(sample_rule)

        # Verify underlying store was called
        mock_config_store.save_rule.assert_called_once_with(sample_rule)

        # Verify extraction workflow was triggered
        mock_hatchet_client.admin.run_workflow.assert_called_once()
        call_args = mock_hatchet_client.admin.run_workflow.call_args
        assert call_args[0][0] == "extract-schema-requirements"
        assert call_args[1]["input"]["content_type"] == "rule"
        assert call_args[1]["input"]["content_id"] == str(sample_rule.id)

    @pytest.mark.asyncio
    async def test_update_rule_triggers_extraction(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_rule,
    ):
        """T138: update_rule triggers extraction workflow."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        await wrapper.update_rule(sample_rule)

        # Verify underlying store was called
        mock_config_store.save_rule.assert_called_once_with(sample_rule)

        # Verify extraction workflow was triggered
        mock_hatchet_client.admin.run_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_rule_without_hatchet(
        self,
        mock_config_store,
        sample_rule,
    ):
        """Test save_rule works without Hatchet client."""
        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=None,
        )

        result = await wrapper.save_rule(sample_rule)

        mock_config_store.save_rule.assert_called_once_with(sample_rule)
        assert result == mock_config_store.save_rule.return_value

    @pytest.mark.asyncio
    async def test_save_rule_extraction_failure_non_blocking(
        self,
        mock_config_store,
        mock_hatchet_client,
        sample_rule,
    ):
        """Test extraction failure doesn't block save."""
        mock_hatchet_client.admin.run_workflow.side_effect = Exception("Hatchet error")

        wrapper = CustomerDataRequirementExtractor(
            config_store=mock_config_store,
            hatchet_client=mock_hatchet_client,
        )

        # Should not raise despite Hatchet failure
        result = await wrapper.save_rule(sample_rule)

        mock_config_store.save_rule.assert_called_once()
        assert result == mock_config_store.save_rule.return_value


class TestPassThroughMethods:
    """Tests for pass-through method delegation."""

    @pytest.mark.asyncio
    async def test_get_scenario_delegates(self, mock_config_store):
        """Test get_scenario delegates to underlying store."""
        wrapper = CustomerDataRequirementExtractor(config_store=mock_config_store)
        tenant_id = uuid4()
        scenario_id = uuid4()

        await wrapper.get_scenario(tenant_id, scenario_id)

        mock_config_store.get_scenario.assert_called_once_with(tenant_id, scenario_id)

    @pytest.mark.asyncio
    async def test_get_rule_delegates(self, mock_config_store):
        """Test get_rule delegates to underlying store."""
        wrapper = CustomerDataRequirementExtractor(config_store=mock_config_store)
        tenant_id = uuid4()
        rule_id = uuid4()

        await wrapper.get_rule(tenant_id, rule_id)

        mock_config_store.get_rule.assert_called_once_with(tenant_id, rule_id)

    @pytest.mark.asyncio
    async def test_delete_scenario_delegates(self, mock_config_store):
        """Test delete_scenario delegates to underlying store."""
        wrapper = CustomerDataRequirementExtractor(config_store=mock_config_store)
        tenant_id = uuid4()
        scenario_id = uuid4()

        await wrapper.delete_scenario(tenant_id, scenario_id)

        mock_config_store.delete_scenario.assert_called_once_with(tenant_id, scenario_id)


class TestContentBuilding:
    """Tests for content text building."""

    def test_scenario_content_includes_name_and_description(self, sample_scenario):
        """Test scenario content text includes name and description."""
        wrapper = CustomerDataRequirementExtractor(config_store=AsyncMock())
        content = wrapper._build_scenario_content(sample_scenario)

        assert sample_scenario.name in content
        assert sample_scenario.description in content

    def test_scenario_content_includes_entry_condition(self, sample_scenario):
        """Test scenario content text includes entry condition."""
        wrapper = CustomerDataRequirementExtractor(config_store=AsyncMock())
        content = wrapper._build_scenario_content(sample_scenario)

        assert sample_scenario.entry_condition_text in content

    def test_rule_content_includes_name_and_condition(self, sample_rule):
        """Test rule content text includes name and condition."""
        wrapper = CustomerDataRequirementExtractor(config_store=AsyncMock())
        content = wrapper._build_rule_content(sample_rule)

        assert sample_rule.name in content
        assert sample_rule.condition_text in content
