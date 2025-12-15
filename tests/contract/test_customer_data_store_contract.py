"""Contract tests for InterlocutorDataStoreInterface implementations.

These tests define the contract that ALL InterlocutorDataStoreInterface implementations must satisfy.
Each implementation (InMemory, PostgreSQL, etc.) should pass these tests.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ruche.conversation.models import Channel
from ruche.interlocutor_data.enums import (
    FallbackAction,
    ItemStatus,
    VariableSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
)
from ruche.interlocutor_data.models import (
    ChannelIdentity,
    InterlocutorDataStore,
    ProfileAsset,
    VariableEntry,
    InterlocutorDataField,
    ScenarioFieldRequirement,
)
from ruche.interlocutor_data.stores import InMemoryInterlocutorDataStore


class InterlocutorDataStoreInterfaceContract(ABC):
    """Contract tests for InterlocutorDataStoreInterface methods.

    All InterlocutorDataStoreInterface implementations must pass these tests.
    """

    @abstractmethod
    @pytest.fixture
    def store(self):
        """Return a InterlocutorDataStoreInterface implementation to test."""
        pass

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        return uuid4()

    @pytest.fixture
    def scenario_id(self):
        return uuid4()

    @pytest.fixture
    def sample_profile(self, tenant_id) -> InterlocutorDataStore:
        """Create a sample customer profile."""
        identity = ChannelIdentity(
            channel=Channel.WEBCHAT,
            channel_user_id="user123",
            primary=True,
        )
        return InterlocutorDataStore(
            tenant_id=tenant_id,
            channel_identities=[identity],
        )


# =============================================================================
# US1: Lineage Tracking Contract Tests
# =============================================================================


class LineageTrackingContract(InterlocutorDataStoreInterfaceContract):
    """Contract tests for US1: Lineage Tracking."""

    @pytest.mark.asyncio
    async def test_get_derivation_chain_single_item(
        self, store, sample_profile, tenant_id
    ):
        """Should return single-item chain for root field (no source)."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
            # No source_item_id = root item
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        chain = await store.get_derivation_chain(tenant_id, field.id, "profile_field")
        assert len(chain) == 1
        assert chain[0]["id"] == str(field.id)
        assert chain[0]["name"] == "email"
        assert chain[0]["type"] == "profile_field"

    @pytest.mark.asyncio
    async def test_get_derivation_chain_linked_items(
        self, store, sample_profile, tenant_id
    ):
        """Should return full chain for derived fields."""
        await store.save(sample_profile)

        # Create root field
        root_field = VariableEntry(
            name="id_document",
            value="uploaded",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, root_field)

        # Create derived field
        derived_field = VariableEntry(
            name="document_number",
            value="ABC123",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=root_field.id,
            source_item_type=SourceType.PROFILE_FIELD,
            source_metadata={"extraction_tool": "ocr"},
        )
        await store.update_field(
            tenant_id, sample_profile.id, derived_field, supersede_existing=False
        )

        chain = await store.get_derivation_chain(
            tenant_id, derived_field.id, "profile_field"
        )
        assert len(chain) == 2
        assert chain[0]["name"] == "id_document"  # Root first
        assert chain[1]["name"] == "document_number"  # Derived second

    @pytest.mark.asyncio
    async def test_get_derivation_chain_max_depth(
        self, store, sample_profile, tenant_id
    ):
        """Should limit chain traversal to max depth (10)."""
        await store.save(sample_profile)

        # Create chain of 15 linked fields
        prev_id = None
        field_ids = []
        for i in range(15):
            field = VariableEntry(
                name=f"field_{i}",
                value=f"value_{i}",
                value_type="string",
                source=VariableSource.SYSTEM_INFERRED,
                source_item_id=prev_id,
                source_item_type=SourceType.PROFILE_FIELD if prev_id else None,
            )
            await store.update_field(
                tenant_id, sample_profile.id, field, supersede_existing=False
            )
            field_ids.append(field.id)
            prev_id = field.id

        # Get chain from last item
        chain = await store.get_derivation_chain(
            tenant_id, field_ids[-1], "profile_field"
        )
        # Should be limited to 10 items max
        assert len(chain) <= 10

    @pytest.mark.asyncio
    async def test_get_derivation_chain_circular_reference(
        self, store, sample_profile, tenant_id
    ):
        """Should handle circular references without infinite loop."""
        await store.save(sample_profile)

        # Create field A
        field_a = VariableEntry(
            name="field_a",
            value="value_a",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
        )
        await store.update_field(
            tenant_id, sample_profile.id, field_a, supersede_existing=False
        )

        # Create field B pointing to A
        field_b = VariableEntry(
            name="field_b",
            value="value_b",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=field_a.id,
            source_item_type=SourceType.PROFILE_FIELD,
        )
        await store.update_field(
            tenant_id, sample_profile.id, field_b, supersede_existing=False
        )

        # Manually create circular reference (A points to B)
        # In real implementations this would be prevented, but we test the safeguard
        profile = await store.get_by_id(tenant_id, sample_profile.id)
        profile.fields["field_a"].source_item_id = field_b.id
        profile.fields["field_a"].source_item_type = SourceType.PROFILE_FIELD

        # Get chain - should terminate without infinite loop
        chain = await store.get_derivation_chain(tenant_id, field_b.id, "profile_field")
        assert len(chain) <= 10  # Should terminate

    @pytest.mark.asyncio
    async def test_get_derived_items_returns_all_derived(
        self, store, sample_profile, tenant_id
    ):
        """Should return all items derived from a source."""
        await store.save(sample_profile)

        # Create source field
        source_field = VariableEntry(
            name="id_document",
            value="uploaded",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, source_field)

        # Create multiple derived fields
        derived1 = VariableEntry(
            name="doc_number",
            value="123",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=source_field.id,
            source_item_type=SourceType.PROFILE_FIELD,
        )
        derived2 = VariableEntry(
            name="doc_type",
            value="passport",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=source_field.id,
            source_item_type=SourceType.PROFILE_FIELD,
        )
        await store.update_field(
            tenant_id, sample_profile.id, derived1, supersede_existing=False
        )
        await store.update_field(
            tenant_id, sample_profile.id, derived2, supersede_existing=False
        )

        derived = await store.get_derived_items(tenant_id, source_field.id)
        assert len(derived["fields"]) == 2
        names = {f.name for f in derived["fields"]}
        assert names == {"doc_number", "doc_type"}

    @pytest.mark.asyncio
    async def test_get_derived_items_empty_when_no_dependents(
        self, store, sample_profile, tenant_id
    ):
        """Should return empty lists when no items derived from source."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        derived = await store.get_derived_items(tenant_id, field.id)
        assert derived["fields"] == []
        assert derived["assets"] == []

    @pytest.mark.asyncio
    async def test_check_has_dependents_true(self, store, sample_profile, tenant_id):
        """Should return True when item has dependents."""
        await store.save(sample_profile)

        source_field = VariableEntry(
            name="source",
            value="source_value",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, source_field)

        derived_field = VariableEntry(
            name="derived",
            value="derived_value",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=source_field.id,
            source_item_type=SourceType.PROFILE_FIELD,
        )
        await store.update_field(
            tenant_id, sample_profile.id, derived_field, supersede_existing=False
        )

        has_deps = await store.check_has_dependents(tenant_id, source_field.id)
        assert has_deps is True

    @pytest.mark.asyncio
    async def test_check_has_dependents_false(self, store, sample_profile, tenant_id):
        """Should return False when item has no dependents."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="standalone",
            value="value",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        has_deps = await store.check_has_dependents(tenant_id, field.id)
        assert has_deps is False


# =============================================================================
# US2: Status Management Contract Tests
# =============================================================================


class StatusManagementContract(InterlocutorDataStoreInterfaceContract):
    """Contract tests for US2: Status Management."""

    @pytest.mark.asyncio
    async def test_get_field_filters_by_active_status(
        self, store, sample_profile, tenant_id
    ):
        """Should return only active fields by default."""
        await store.save(sample_profile)

        # Add active field
        field = VariableEntry(
            name="email",
            value="active@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        result = await store.get_field(tenant_id, sample_profile.id, "email")
        assert result is not None
        assert result.status == ItemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_field_with_specific_status(
        self, store, sample_profile, tenant_id
    ):
        """Should filter by specified status."""
        await store.save(sample_profile)

        # Add and supersede field
        old_field = VariableEntry(
            name="email",
            value="old@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, old_field)

        new_field = VariableEntry(
            name="email",
            value="new@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, new_field)

        # Get superseded
        superseded = await store.get_field(
            tenant_id, sample_profile.id, "email", status=ItemStatus.SUPERSEDED
        )
        assert superseded is not None
        assert superseded.value == "old@example.com"
        assert superseded.status == ItemStatus.SUPERSEDED

    @pytest.mark.asyncio
    async def test_get_field_history_returns_all_statuses(
        self, store, sample_profile, tenant_id
    ):
        """Should return all field versions regardless of status."""
        await store.save(sample_profile)

        # Create multiple versions
        for i, value in enumerate(["first@ex.com", "second@ex.com", "third@ex.com"]):
            field = VariableEntry(
                name="email",
                value=value,
                value_type="email",
                source=VariableSource.USER_PROVIDED,
            )
            await store.update_field(tenant_id, sample_profile.id, field)

        history = await store.get_field_history(tenant_id, sample_profile.id, "email")
        assert len(history) == 3
        # Most recent first
        assert history[0].value == "third@ex.com"
        assert history[0].status == ItemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_update_field_marks_old_as_superseded(
        self, store, sample_profile, tenant_id
    ):
        """Should mark existing active field as superseded when updating."""
        await store.save(sample_profile)

        # Save first version
        old_field = VariableEntry(
            name="email",
            value="old@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        old_field_id = await store.update_field(tenant_id, sample_profile.id, old_field)

        # Save second version
        new_field = VariableEntry(
            name="email",
            value="new@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, new_field)

        # Verify old field is superseded
        history = await store.get_field_history(tenant_id, sample_profile.id, "email")
        superseded_fields = [f for f in history if f.status == ItemStatus.SUPERSEDED]
        assert len(superseded_fields) == 1
        assert superseded_fields[0].value == "old@example.com"
        assert superseded_fields[0].superseded_by_id == new_field.id

    @pytest.mark.asyncio
    async def test_expire_stale_fields_marks_expired(
        self, store, sample_profile, tenant_id
    ):
        """Should mark fields past expires_at as expired."""
        await store.save(sample_profile)

        # Add expired field
        field = VariableEntry(
            name="temp_code",
            value="123456",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        count = await store.expire_stale_fields(tenant_id)
        assert count == 1

        expired_field = await store.get_field(
            tenant_id, sample_profile.id, "temp_code", status=ItemStatus.EXPIRED
        )
        assert expired_field is not None
        assert expired_field.status == ItemStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_expire_stale_fields_ignores_non_expired(
        self, store, sample_profile, tenant_id
    ):
        """Should not expire fields with future expires_at."""
        await store.save(sample_profile)

        # Add non-expired field
        field = VariableEntry(
            name="valid_code",
            value="654321",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        count = await store.expire_stale_fields(tenant_id)
        assert count == 0

        active_field = await store.get_field(tenant_id, sample_profile.id, "valid_code")
        assert active_field is not None
        assert active_field.status == ItemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_mark_orphaned_items_marks_orphaned(
        self, store, sample_profile, tenant_id
    ):
        """Should mark items with deleted sources as orphaned."""
        await store.save(sample_profile)

        # Create source field
        source_field = VariableEntry(
            name="source",
            value="source_value",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, source_field)

        # Create derived field that references source
        derived_field = VariableEntry(
            name="derived",
            value="derived_value",
            value_type="string",
            source=VariableSource.SYSTEM_INFERRED,
            source_item_id=uuid4(),  # Non-existent source
            source_item_type=SourceType.PROFILE_FIELD,
        )
        await store.update_field(
            tenant_id, sample_profile.id, derived_field, supersede_existing=False
        )

        count = await store.mark_orphaned_items(tenant_id)
        assert count == 1

        orphaned = await store.get_field(
            tenant_id, sample_profile.id, "derived", status=ItemStatus.ORPHANED
        )
        assert orphaned is not None
        assert orphaned.status == ItemStatus.ORPHANED


# =============================================================================
# US3: Schema Definitions Contract Tests
# =============================================================================


class SchemaDefinitionsContract(InterlocutorDataStoreInterfaceContract):
    """Contract tests for US3: Schema-Driven Field Definitions."""

    @pytest.mark.asyncio
    async def test_save_field_definition(self, store, tenant_id, agent_id):
        """Should save and return field definition ID."""
        definition = InterlocutorDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            value_type="email",
        )
        def_id = await store.save_field_definition(definition)
        assert def_id == definition.id

    @pytest.mark.asyncio
    async def test_get_field_definition_by_name(self, store, tenant_id, agent_id):
        """Should retrieve field definition by name."""
        definition = InterlocutorDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            value_type="email",
        )
        await store.save_field_definition(definition)

        retrieved = await store.get_field_definition(tenant_id, agent_id, "email")
        assert retrieved is not None
        assert retrieved.name == "email"
        assert retrieved.display_name == "Email Address"

    @pytest.mark.asyncio
    async def test_get_field_definitions_for_agent(self, store, tenant_id, agent_id):
        """Should return all field definitions for an agent."""
        for name in ["email", "phone", "name"]:
            definition = InterlocutorDataField(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=name,
                display_name=name.title(),
                value_type="string",
            )
            await store.save_field_definition(definition)

        definitions = await store.get_field_definitions(tenant_id, agent_id)
        assert len(definitions) == 3
        names = {d.name for d in definitions}
        assert names == {"email", "phone", "name"}

    @pytest.mark.asyncio
    async def test_get_field_definitions_filters_disabled(
        self, store, tenant_id, agent_id
    ):
        """Should filter disabled definitions by default."""
        enabled_def = InterlocutorDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="enabled",
            display_name="Enabled Field",
            value_type="string",
            enabled=True,
        )
        disabled_def = InterlocutorDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="disabled",
            display_name="Disabled Field",
            value_type="string",
            enabled=False,
        )
        await store.save_field_definition(enabled_def)
        await store.save_field_definition(disabled_def)

        # Default: enabled only
        definitions = await store.get_field_definitions(tenant_id, agent_id)
        assert len(definitions) == 1
        assert definitions[0].name == "enabled"

        # Include disabled
        all_definitions = await store.get_field_definitions(
            tenant_id, agent_id, enabled_only=False
        )
        assert len(all_definitions) == 2

    @pytest.mark.asyncio
    async def test_save_scenario_requirement(self, store, tenant_id, agent_id, scenario_id):
        """Should save scenario requirement."""
        requirement = ScenarioFieldRequirement(
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
            field_name="email",
        )
        req_id = await store.save_scenario_requirement(requirement)
        assert req_id == requirement.id

    @pytest.mark.asyncio
    async def test_get_scenario_requirements(
        self, store, tenant_id, agent_id, scenario_id
    ):
        """Should retrieve requirements for a scenario."""
        for field_name in ["email", "phone"]:
            requirement = ScenarioFieldRequirement(
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                field_name=field_name,
            )
            await store.save_scenario_requirement(requirement)

        requirements = await store.get_scenario_requirements(tenant_id, scenario_id)
        assert len(requirements) == 2
        names = {r.field_name for r in requirements}
        assert names == {"email", "phone"}

    @pytest.mark.asyncio
    async def test_get_scenario_requirements_ordered_by_collection_order(
        self, store, tenant_id, agent_id, scenario_id
    ):
        """Should return requirements sorted by collection_order."""
        for i, field_name in enumerate(["third", "first", "second"]):
            requirement = ScenarioFieldRequirement(
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                field_name=field_name,
                collection_order=[2, 0, 1][i],  # third=2, first=0, second=1
            )
            await store.save_scenario_requirement(requirement)

        requirements = await store.get_scenario_requirements(tenant_id, scenario_id)
        names = [r.field_name for r in requirements]
        assert names == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_get_missing_fields_returns_unmet_requirements(
        self, store, sample_profile, tenant_id, agent_id, scenario_id
    ):
        """Should return requirements not satisfied by profile."""
        await store.save(sample_profile)

        # Create requirements
        for field_name in ["email", "phone"]:
            requirement = ScenarioFieldRequirement(
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                field_name=field_name,
                required_level=RequiredLevel.HARD,
            )
            await store.save_scenario_requirement(requirement)

        # Add only email to profile
        email_field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, email_field)

        # Refresh profile
        profile = await store.get_by_id(tenant_id, sample_profile.id)

        missing = await store.get_missing_fields(tenant_id, profile, scenario_id)
        assert len(missing) == 1
        assert missing[0].field_name == "phone"

    @pytest.mark.asyncio
    async def test_get_missing_fields_empty_when_all_satisfied(
        self, store, sample_profile, tenant_id, agent_id, scenario_id
    ):
        """Should return empty list when all requirements satisfied."""
        await store.save(sample_profile)

        # Create requirement
        requirement = ScenarioFieldRequirement(
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
            field_name="email",
        )
        await store.save_scenario_requirement(requirement)

        # Add email to profile
        email_field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, email_field)

        profile = await store.get_by_id(tenant_id, sample_profile.id)

        missing = await store.get_missing_fields(tenant_id, profile, scenario_id)
        assert len(missing) == 0

    @pytest.mark.asyncio
    async def test_delete_scenario_requirements(
        self, store, tenant_id, agent_id, scenario_id
    ):
        """Should delete requirements for a scenario."""
        # Create requirements
        for field_name in ["email", "phone"]:
            requirement = ScenarioFieldRequirement(
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                field_name=field_name,
            )
            await store.save_scenario_requirement(requirement)

        count = await store.delete_scenario_requirements(tenant_id, scenario_id)
        assert count == 2

        requirements = await store.get_scenario_requirements(tenant_id, scenario_id)
        assert len(requirements) == 0


# =============================================================================
# Concrete Test Classes for InMemoryInterlocutorDataStore
# =============================================================================


class TestInMemoryLineageTracking(LineageTrackingContract):
    """Run lineage tracking contract tests against InMemoryInterlocutorDataStore."""

    @pytest.fixture
    def store(self):
        return InMemoryInterlocutorDataStore()


class TestInMemoryStatusManagement(StatusManagementContract):
    """Run status management contract tests against InMemoryInterlocutorDataStore."""

    @pytest.fixture
    def store(self):
        return InMemoryInterlocutorDataStore()


class TestInMemorySchemaDefinitions(SchemaDefinitionsContract):
    """Run schema definitions contract tests against InMemoryInterlocutorDataStore."""

    @pytest.fixture
    def store(self):
        return InMemoryInterlocutorDataStore()
