"""Tests for CustomerDataUpdater."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from focal.alignment.context.situation_snapshot import CandidateVariableInfo
from focal.alignment.customer.models import CustomerDataUpdate
from focal.alignment.customer.updater import CustomerDataUpdater
from focal.customer_data.models import (
    CustomerDataField,
    CustomerDataStore,
    VariableEntry,
)
from focal.customer_data.validation import CustomerDataFieldValidator
from focal.customer_data.enums import ValidationMode, VariableSource


def utc_now():
    return datetime.now(UTC)


@pytest.fixture
def validator():
    """CustomerDataFieldValidator instance."""
    return CustomerDataFieldValidator()


@pytest.fixture
def updater(validator):
    """CustomerDataUpdater instance."""
    return CustomerDataUpdater(validator)


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def customer_id():
    """Test customer ID."""
    return uuid4()


@pytest.fixture
def field_definitions(tenant_id, agent_id):
    """Sample field definitions."""
    return [
        CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
            scope="IDENTITY",
            persist=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="order_id",
            display_name="Order ID",
            value_type="string",
            scope="CASE",
            persist=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="temp_cart_total",
            display_name="Cart Total",
            value_type="number",
            scope="SESSION",
            persist=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="age",
            display_name="Age",
            value_type="number",
            scope="IDENTITY",
            persist=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
    ]


@pytest.fixture
def customer_data_store(tenant_id, customer_id):
    """Empty CustomerDataStore."""
    return CustomerDataStore(
        tenant_id=tenant_id,
        customer_id=customer_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


class TestMatchCandidatesToFields:
    """Tests for P3.1 - Match candidates to fields."""

    @pytest.mark.asyncio
    async def test_match_known_field(self, updater, field_definitions):
        """Test matching known field keys."""
        candidate_variables = {
            "email": CandidateVariableInfo(
                value="test@example.com",
                scope="IDENTITY",
                is_update=False,
            ),
        }

        updates = updater._match_candidates_to_fields(
            candidate_variables, field_definitions
        )

        assert len(updates) == 1
        assert updates[0].field_name == "email"
        assert updates[0].raw_value == "test@example.com"
        assert updates[0].is_update is False

    @pytest.mark.asyncio
    async def test_skip_unknown_field(self, updater, field_definitions):
        """Test unknown field keys are skipped."""
        candidate_variables = {
            "unknown_field": CandidateVariableInfo(
                value="test",
                scope="IDENTITY",
                is_update=False,
            ),
        }

        updates = updater._match_candidates_to_fields(
            candidate_variables, field_definitions
        )

        assert len(updates) == 0

    @pytest.mark.asyncio
    async def test_is_update_flag_propagation(self, updater, field_definitions):
        """Test is_update flag is propagated."""
        candidate_variables = {
            "email": CandidateVariableInfo(
                value="new@example.com",
                scope="IDENTITY",
                is_update=True,
            ),
        }

        updates = updater._match_candidates_to_fields(
            candidate_variables, field_definitions
        )

        assert len(updates) == 1
        assert updates[0].is_update is True


class TestValidateAndCoerce:
    """Tests for P3.2 - Validation & coercion."""

    @pytest.mark.asyncio
    async def test_valid_email_coerced(self, updater, field_definitions):
        """Test valid email is coerced."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="test@example.com",
                is_update=False,
            )
        ]

        validated = await updater._validate_and_coerce(updates)

        assert validated[0].validated_value == "test@example.com"
        assert validated[0].validation_error is None

    @pytest.mark.asyncio
    async def test_invalid_email_sets_error(self, updater, field_definitions):
        """Test invalid email sets validation_error."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="not-an-email",
                is_update=False,
            )
        ]

        validated = await updater._validate_and_coerce(updates)

        assert validated[0].validation_error is not None
        assert "Invalid email format" in validated[0].validation_error

    @pytest.mark.asyncio
    async def test_number_type_coercion(self, updater, field_definitions):
        """Test number type coercion."""
        age_field = field_definitions[3]  # age field
        updates = [
            CustomerDataUpdate(
                field_name="age",
                field_definition=age_field,
                raw_value="25",
                is_update=False,
            )
        ]

        validated = await updater._validate_and_coerce(updates)

        assert validated[0].validated_value == 25.0
        assert validated[0].validation_error is None


class TestApplyUpdatesInMemory:
    """Tests for P3.3 - Apply in-memory updates."""

    @pytest.mark.asyncio
    async def test_new_value_added(self, updater, customer_data_store, field_definitions):
        """Test new values added to CustomerDataStore."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="test@example.com",
                is_update=False,
                validated_value="test@example.com",
            )
        ]

        updater._apply_updates_in_memory(customer_data_store, updates)

        assert "email" in customer_data_store.fields
        assert customer_data_store.fields["email"].value == "test@example.com"

    @pytest.mark.asyncio
    async def test_existing_value_updated_with_history(
        self, updater, customer_data_store, field_definitions
    ):
        """Test existing values updated with history tracking."""
        # Add initial value
        customer_data_store.fields["email"] = VariableEntry(
            name="email",
            value="old@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
            collected_at=utc_now(),
            updated_at=utc_now(),
        )

        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="new@example.com",
                is_update=True,
                validated_value="new@example.com",
            )
        ]

        updater._apply_updates_in_memory(customer_data_store, updates)

        assert customer_data_store.fields["email"].value == "new@example.com"
        assert len(customer_data_store.fields["email"].history) == 1
        assert customer_data_store.fields["email"].history[0]["value"] == "old@example.com"

    @pytest.mark.asyncio
    async def test_invalid_updates_skipped(
        self, updater, customer_data_store, field_definitions
    ):
        """Test invalid updates are skipped."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="not-an-email",
                is_update=False,
                validation_error="Invalid email format",
            )
        ]

        updater._apply_updates_in_memory(customer_data_store, updates)

        assert "email" not in customer_data_store.fields

    @pytest.mark.asyncio
    async def test_all_scope_types_applied(
        self, updater, customer_data_store, field_definitions
    ):
        """Test all scope types (IDENTITY, BUSINESS, CASE, SESSION) are applied."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],  # IDENTITY
                raw_value="test@example.com",
                is_update=False,
                validated_value="test@example.com",
            ),
            CustomerDataUpdate(
                field_name="order_id",
                field_definition=field_definitions[1],  # CASE
                raw_value="ORDER123",
                is_update=False,
                validated_value="ORDER123",
            ),
            CustomerDataUpdate(
                field_name="temp_cart_total",
                field_definition=field_definitions[2],  # SESSION
                raw_value=99.99,
                is_update=False,
                validated_value=99.99,
            ),
        ]

        updater._apply_updates_in_memory(customer_data_store, updates)

        assert len(customer_data_store.fields) == 3
        assert customer_data_store.fields["email"].value == "test@example.com"
        assert customer_data_store.fields["order_id"].value == "ORDER123"
        assert customer_data_store.fields["temp_cart_total"].value == 99.99


class TestMarkForPersistence:
    """Tests for P3.4 - Mark for persistence."""

    @pytest.mark.asyncio
    async def test_session_scope_not_marked(self, updater, field_definitions):
        """Test SESSION scope NOT marked for persistence."""
        updates = [
            CustomerDataUpdate(
                field_name="temp_cart_total",
                field_definition=field_definitions[2],  # SESSION scope
                raw_value=99.99,
                is_update=False,
                validated_value=99.99,
            )
        ]

        persistent = updater._mark_for_persistence(updates)

        assert len(persistent) == 0

    @pytest.mark.asyncio
    async def test_persist_false_not_marked(self, updater, tenant_id, agent_id):
        """Test persist=False NOT marked for persistence."""
        field_def = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="temp_field",
            display_name="Temp Field",
            value_type="string",
            scope="IDENTITY",
            persist=False,  # Explicitly not persisted
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        updates = [
            CustomerDataUpdate(
                field_name="temp_field",
                field_definition=field_def,
                raw_value="test",
                is_update=False,
                validated_value="test",
            )
        ]

        persistent = updater._mark_for_persistence(updates)

        assert len(persistent) == 0

    @pytest.mark.asyncio
    async def test_identity_scope_marked(self, updater, field_definitions):
        """Test IDENTITY scope with persist=True ARE marked."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],  # IDENTITY, persist=True
                raw_value="test@example.com",
                is_update=False,
                validated_value="test@example.com",
            )
        ]

        persistent = updater._mark_for_persistence(updates)

        assert len(persistent) == 1
        assert persistent[0].field_name == "email"

    @pytest.mark.asyncio
    async def test_case_scope_marked(self, updater, field_definitions):
        """Test CASE scope with persist=True ARE marked."""
        updates = [
            CustomerDataUpdate(
                field_name="order_id",
                field_definition=field_definitions[1],  # CASE, persist=True
                raw_value="ORDER123",
                is_update=False,
                validated_value="ORDER123",
            )
        ]

        persistent = updater._mark_for_persistence(updates)

        assert len(persistent) == 1
        assert persistent[0].field_name == "order_id"

    @pytest.mark.asyncio
    async def test_validation_errors_not_marked(self, updater, field_definitions):
        """Test validation errors NOT marked for persistence."""
        updates = [
            CustomerDataUpdate(
                field_name="email",
                field_definition=field_definitions[0],
                raw_value="not-an-email",
                is_update=False,
                validation_error="Invalid email format",
            )
        ]

        persistent = updater._mark_for_persistence(updates)

        assert len(persistent) == 0


class TestFullUpdateFlow:
    """Integration tests for full update flow."""

    @pytest.mark.asyncio
    async def test_full_update_flow(
        self, updater, customer_data_store, field_definitions
    ):
        """Test full P3.1-P3.4 flow."""
        candidate_variables = {
            "email": CandidateVariableInfo(
                value="test@example.com",
                scope="IDENTITY",
                is_update=False,
            ),
            "order_id": CandidateVariableInfo(
                value="ORDER123",
                scope="CASE",
                is_update=False,
            ),
            "temp_cart_total": CandidateVariableInfo(
                value=99.99,
                scope="SESSION",
                is_update=False,
            ),
        }

        updated_store, persistent_updates = await updater.update(
            customer_data_store,
            candidate_variables,
            field_definitions,
        )

        # All 3 should be in memory
        assert len(updated_store.fields) == 3
        assert "email" in updated_store.fields
        assert "order_id" in updated_store.fields
        assert "temp_cart_total" in updated_store.fields

        # Only 2 should be marked for persistence (not SESSION scope)
        assert len(persistent_updates) == 2
        persistent_names = {u.field_name for u in persistent_updates}
        assert "email" in persistent_names
        assert "order_id" in persistent_names
        assert "temp_cart_total" not in persistent_names

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_updates(
        self, updater, customer_data_store, field_definitions
    ):
        """Test flow with mixed valid and invalid updates."""
        candidate_variables = {
            "email": CandidateVariableInfo(
                value="not-an-email",
                scope="IDENTITY",
                is_update=False,
            ),
            "order_id": CandidateVariableInfo(
                value="ORDER123",
                scope="CASE",
                is_update=False,
            ),
        }

        updated_store, persistent_updates = await updater.update(
            customer_data_store,
            candidate_variables,
            field_definitions,
        )

        # Only valid update should be in memory
        assert len(updated_store.fields) == 1
        assert "order_id" in updated_store.fields
        assert "email" not in updated_store.fields

        # Only valid update should be marked for persistence
        assert len(persistent_updates) == 1
        assert persistent_updates[0].field_name == "order_id"
