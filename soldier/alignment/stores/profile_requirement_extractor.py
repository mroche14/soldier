"""CustomerDataRequirementExtractor - extracts customer data requirements from scenarios/rules.

Triggers CustomerDataSchemaExtraction workflow on Scenario/Rule create/update.
Non-blocking: extraction runs as background job via Hatchet.
"""

from typing import Any
from uuid import UUID

from soldier.alignment.models import Rule, Scenario
from soldier.alignment.stores.agent_config_store import AgentConfigStore
from soldier.jobs.workflows.schema_extraction import ExtractSchemaInput
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


class CustomerDataRequirementExtractor:
    """Extracts customer data field requirements from scenarios and rules.

    Implements T135-T138: Trigger extraction on Scenario/Rule create/update.

    Wraps an AgentConfigStore and triggers background extraction jobs
    when scenarios or rules are saved. Non-blocking: failures don't
    block the save operation.

    Usage:
        store = CustomerDataRequirementExtractor(
            config_store=InMemoryAgentConfigStore(),
            hatchet_client=hatchet,  # Optional
        )
        await store.save_scenario(scenario)  # Triggers extraction in background
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        hatchet_client: Any | None = None,
        extraction_enabled: bool = True,
    ) -> None:
        """Initialize the extractor.

        Args:
            config_store: The underlying AgentConfigStore to wrap
            hatchet_client: Hatchet client for triggering workflows (optional)
            extraction_enabled: Whether to enable extraction hooks
        """
        self._store = config_store
        self._hatchet = hatchet_client
        self._extraction_enabled = extraction_enabled

    # =========================================================================
    # SCENARIO OPERATIONS WITH HOOKS (T135, T136)
    # =========================================================================

    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Save scenario and trigger extraction (T135, T136).

        Args:
            scenario: Scenario to save

        Returns:
            Scenario ID
        """
        # First save the scenario
        scenario_id = await self._store.save_scenario(scenario)

        # Then trigger extraction in background (non-blocking)
        if self._extraction_enabled:
            await self._trigger_scenario_extraction(scenario, is_update=False)

        return scenario_id

    async def update_scenario(self, scenario: Scenario) -> UUID:
        """Update scenario and trigger re-extraction (T136).

        Args:
            scenario: Scenario to update

        Returns:
            Scenario ID
        """
        # Save the updated scenario
        scenario_id = await self._store.save_scenario(scenario)

        # Trigger re-extraction in background
        if self._extraction_enabled:
            await self._trigger_scenario_extraction(scenario, is_update=True)

        return scenario_id

    async def _trigger_scenario_extraction(
        self,
        scenario: Scenario,
        is_update: bool = False,
    ) -> None:
        """Trigger schema extraction for a scenario.

        Non-blocking: Dispatches to Hatchet if available, logs otherwise.
        """
        if not self._hatchet:
            logger.info(
                "schema_extraction_skipped_no_hatchet",
                scenario_id=str(scenario.id),
                is_update=is_update,
            )
            return

        try:
            # Build content text from scenario
            content_text = self._build_scenario_content(scenario)

            input_data = ExtractSchemaInput(
                tenant_id=str(scenario.tenant_id),
                agent_id=str(scenario.agent_id),
                content_id=str(scenario.id),
                content_type="scenario",
                content_text=content_text,
            )

            # Dispatch workflow (non-blocking)
            await self._hatchet.admin.run_workflow(
                "extract-schema-requirements",
                input={
                    "tenant_id": input_data.tenant_id,
                    "agent_id": input_data.agent_id,
                    "content_id": input_data.content_id,
                    "content_type": input_data.content_type,
                    "content_text": input_data.content_text,
                },
            )

            logger.info(
                "schema_extraction_triggered",
                content_type="scenario",
                content_id=str(scenario.id),
                is_update=is_update,
            )

        except Exception as e:
            # Non-blocking: log error but don't fail the save
            logger.warning(
                "schema_extraction_trigger_failed",
                content_type="scenario",
                content_id=str(scenario.id),
                error=str(e),
            )

    def _build_scenario_content(self, scenario: Scenario) -> str:
        """Build extractable content text from scenario."""
        parts = [
            f"Scenario: {scenario.name}",
            f"Description: {scenario.description or ''}",
        ]

        # Add entry condition if present
        if scenario.entry_condition_text:
            parts.append(f"Entry Condition: {scenario.entry_condition_text}")

        # Add step content
        if scenario.steps:
            for step in scenario.steps:
                if hasattr(step, "content"):
                    parts.append(f"Step: {step.content}")
                if hasattr(step, "condition"):
                    parts.append(f"Condition: {step.condition}")

        return "\n".join(parts)

    # =========================================================================
    # RULE OPERATIONS WITH HOOKS (T137, T138)
    # =========================================================================

    async def save_rule(self, rule: Rule) -> UUID:
        """Save rule and trigger extraction (T137, T138).

        Args:
            rule: Rule to save

        Returns:
            Rule ID
        """
        # First save the rule
        rule_id = await self._store.save_rule(rule)

        # Then trigger extraction in background (non-blocking)
        if self._extraction_enabled:
            await self._trigger_rule_extraction(rule, is_update=False)

        return rule_id

    async def update_rule(self, rule: Rule) -> UUID:
        """Update rule and trigger re-extraction (T138).

        Args:
            rule: Rule to update

        Returns:
            Rule ID
        """
        # Save the updated rule
        rule_id = await self._store.save_rule(rule)

        # Trigger re-extraction in background
        if self._extraction_enabled:
            await self._trigger_rule_extraction(rule, is_update=True)

        return rule_id

    async def _trigger_rule_extraction(
        self,
        rule: Rule,
        is_update: bool = False,
    ) -> None:
        """Trigger schema extraction for a rule.

        Non-blocking: Dispatches to Hatchet if available, logs otherwise.
        """
        if not self._hatchet:
            logger.info(
                "schema_extraction_skipped_no_hatchet",
                rule_id=str(rule.id),
                is_update=is_update,
            )
            return

        try:
            # Build content text from rule
            content_text = self._build_rule_content(rule)

            input_data = ExtractSchemaInput(
                tenant_id=str(rule.tenant_id),
                agent_id=str(rule.agent_id),
                content_id=str(rule.id),
                content_type="rule",
                content_text=content_text,
            )

            # Dispatch workflow (non-blocking)
            await self._hatchet.admin.run_workflow(
                "extract-schema-requirements",
                input={
                    "tenant_id": input_data.tenant_id,
                    "agent_id": input_data.agent_id,
                    "content_id": input_data.content_id,
                    "content_type": input_data.content_type,
                    "content_text": input_data.content_text,
                },
            )

            logger.info(
                "schema_extraction_triggered",
                content_type="rule",
                content_id=str(rule.id),
                is_update=is_update,
            )

        except Exception as e:
            # Non-blocking: log error but don't fail the save
            logger.warning(
                "schema_extraction_trigger_failed",
                content_type="rule",
                content_id=str(rule.id),
                error=str(e),
            )

    def _build_rule_content(self, rule: Rule) -> str:
        """Build extractable content text from rule."""
        parts = [
            f"Rule: {rule.name}",
        ]

        # Add condition text
        if rule.condition_text:
            parts.append(f"Condition: {rule.condition_text}")

        # Add action text if present
        if rule.action_text:
            parts.append(f"Action: {rule.action_text}")

        return "\n".join(parts)

    # =========================================================================
    # PASS-THROUGH METHODS (delegate to underlying store)
    # =========================================================================

    async def get_rule(self, tenant_id: UUID, rule_id: UUID) -> Rule | None:
        """Get a rule by ID (pass-through)."""
        return await self._store.get_rule(tenant_id, rule_id)

    async def get_rules(self, *args, **kwargs) -> list[Rule]:
        """Get rules for an agent (pass-through)."""
        return await self._store.get_rules(*args, **kwargs)

    async def delete_rule(self, tenant_id: UUID, rule_id: UUID) -> bool:
        """Delete a rule (pass-through)."""
        return await self._store.delete_rule(tenant_id, rule_id)

    async def vector_search_rules(self, *args, **kwargs) -> list[tuple[Rule, float]]:
        """Search rules by vector similarity (pass-through)."""
        return await self._store.vector_search_rules(*args, **kwargs)

    async def get_scenario(self, tenant_id: UUID, scenario_id: UUID) -> Scenario | None:
        """Get a scenario by ID (pass-through)."""
        return await self._store.get_scenario(tenant_id, scenario_id)

    async def get_scenarios(self, *args, **kwargs) -> list[Scenario]:
        """Get scenarios for an agent (pass-through)."""
        return await self._store.get_scenarios(*args, **kwargs)

    async def delete_scenario(self, tenant_id: UUID, scenario_id: UUID) -> bool:
        """Delete a scenario (pass-through)."""
        return await self._store.delete_scenario(tenant_id, scenario_id)

    # Delegate all other methods via __getattr__
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to underlying store."""
        return getattr(self._store, name)
