"""Tests for CustomerDataFieldValidator."""

from uuid import uuid4

import pytest

from ruche.customer_data.enums import VariableSource, ValidationMode
from ruche.customer_data.models import VariableEntry, CustomerDataField
from ruche.customer_data.validation import CustomerDataFieldValidator, ValidationError


@pytest.fixture
def validator():
    return CustomerDataFieldValidator()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


class TestTypeValidation:
    """Tests for type validation."""

    def test_string_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid string."""
        field = VariableEntry(
            name="name",
            value="John Doe",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="name",
            display_name="Name",
            value_type="string",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 0

    def test_string_validation_invalid(self, validator, tenant_id, agent_id):
        """Should reject non-string for string type."""
        field = VariableEntry(
            name="name",
            value=123,
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="name",
            display_name="Name",
            value_type="string",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "type_error"

    def test_email_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid email."""
        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 0

    def test_email_validation_invalid_format(self, validator, tenant_id, agent_id):
        """Should reject invalid email format."""
        field = VariableEntry(
            name="email",
            value="not-an-email",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "format_error"

    def test_phone_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid phone numbers."""
        valid_phones = [
            "+1 (555) 123-4567",
            "555-123-4567",
            "5551234567",
            "+44 20 7123 4567",
        ]
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="phone",
            display_name="Phone",
            value_type="phone",
        )

        for phone in valid_phones:
            field = VariableEntry(
                name="phone",
                value=phone,
                value_type="phone",
                source=VariableSource.USER_PROVIDED,
            )
            errors = validator.validate_field(field, definition)
            assert len(errors) == 0, f"Phone {phone} should be valid"

    def test_phone_validation_invalid(self, validator, tenant_id, agent_id):
        """Should reject invalid phone numbers."""
        field = VariableEntry(
            name="phone",
            value="abc",
            value_type="phone",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="phone",
            display_name="Phone",
            value_type="phone",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "format_error"

    def test_phone_validation_too_short(self, validator, tenant_id, agent_id):
        """Should reject phone numbers with too few digits."""
        field = VariableEntry(
            name="phone",
            value="123",
            value_type="phone",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="phone",
            display_name="Phone",
            value_type="phone",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert "at least 7 digits" in errors[0].message

    def test_date_validation_valid_iso(self, validator, tenant_id, agent_id):
        """Should accept valid ISO 8601 date formats."""
        valid_dates = [
            "2024-01-15",
            "2024-01-15T10:30:00",
            "2024-01-15T10:30:00Z",
        ]
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="dob",
            display_name="Date of Birth",
            value_type="date",
        )

        for date in valid_dates:
            field = VariableEntry(
                name="dob",
                value=date,
                value_type="date",
                source=VariableSource.USER_PROVIDED,
            )
            errors = validator.validate_field(field, definition)
            assert len(errors) == 0, f"Date {date} should be valid"

    def test_date_validation_invalid(self, validator, tenant_id, agent_id):
        """Should reject invalid date format."""
        field = VariableEntry(
            name="dob",
            value="15/01/2024",
            value_type="date",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="dob",
            display_name="Date of Birth",
            value_type="date",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "format_error"

    def test_number_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid numbers."""
        valid_numbers = [123, 45.67, "89", "12.34"]
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="age",
            display_name="Age",
            value_type="number",
        )

        for num in valid_numbers:
            field = VariableEntry(
                name="age",
                value=num,
                value_type="number",
                source=VariableSource.USER_PROVIDED,
            )
            errors = validator.validate_field(field, definition)
            assert len(errors) == 0, f"Number {num} should be valid"

    def test_number_validation_rejects_boolean(self, validator, tenant_id, agent_id):
        """Should reject boolean for number type."""
        field = VariableEntry(
            name="age",
            value=True,
            value_type="number",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="age",
            display_name="Age",
            value_type="number",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "type_error"

    def test_boolean_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid booleans."""
        valid_bools = [True, False, "true", "false", "yes", "no", "1", "0"]
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="consent",
            display_name="Consent",
            value_type="boolean",
        )

        for val in valid_bools:
            field = VariableEntry(
                name="consent",
                value=val,
                value_type="boolean",
                source=VariableSource.USER_PROVIDED,
            )
            errors = validator.validate_field(field, definition)
            assert len(errors) == 0, f"Boolean {val} should be valid"

    def test_json_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept valid JSON."""
        valid_json = [
            {"key": "value"},
            [1, 2, 3],
            '{"key": "value"}',
            "[1, 2, 3]",
        ]
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="metadata",
            display_name="Metadata",
            value_type="json",
        )

        for val in valid_json:
            field = VariableEntry(
                name="metadata",
                value=val,
                value_type="json",
                source=VariableSource.USER_PROVIDED,
            )
            errors = validator.validate_field(field, definition)
            assert len(errors) == 0, f"JSON {val} should be valid"

    def test_json_validation_invalid_string(self, validator, tenant_id, agent_id):
        """Should reject invalid JSON string."""
        field = VariableEntry(
            name="metadata",
            value="{invalid json}",
            value_type="json",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="metadata",
            display_name="Metadata",
            value_type="json",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "format_error"


class TestRegexValidation:
    """Tests for regex validation."""

    def test_regex_validation_valid(self, validator, tenant_id, agent_id):
        """Should accept value matching regex."""
        field = VariableEntry(
            name="code",
            value="ABC-123",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="code",
            display_name="Code",
            value_type="string",
            validation_regex=r"^[A-Z]{3}-\d{3}$",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 0

    def test_regex_validation_invalid(self, validator, tenant_id, agent_id):
        """Should reject value not matching regex."""
        field = VariableEntry(
            name="code",
            value="abc123",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="code",
            display_name="Code",
            value_type="string",
            validation_regex=r"^[A-Z]{3}-\d{3}$",
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "regex_error"

    def test_regex_validation_requires_string(self, validator, tenant_id, agent_id):
        """Should require string for regex validation."""
        field = VariableEntry(
            name="code",
            value=123,
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="code",
            display_name="Code",
            value_type="string",
            validation_regex=r"^\d+$",
        )

        errors = validator.validate_field(field, definition)
        # Should have type error (from string validation) and regex error
        assert any(e.error_type == "type_error" for e in errors)


class TestAllowedValuesValidation:
    """Tests for allowed_values validation."""

    def test_allowed_values_valid(self, validator, tenant_id, agent_id):
        """Should accept value in allowed values list."""
        field = VariableEntry(
            name="status",
            value="active",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="status",
            display_name="Status",
            value_type="string",
            allowed_values=["active", "inactive", "pending"],
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 0

    def test_allowed_values_invalid(self, validator, tenant_id, agent_id):
        """Should reject value not in allowed values list."""
        field = VariableEntry(
            name="status",
            value="unknown",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="status",
            display_name="Status",
            value_type="string",
            allowed_values=["active", "inactive", "pending"],
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 1
        assert errors[0].error_type == "allowed_values_error"


class TestValidationModes:
    """Tests for ValidationMode behaviors."""

    def test_strict_mode_returns_errors(self, validator, tenant_id, agent_id):
        """Should return errors in strict mode."""
        field = VariableEntry(
            name="email",
            value="invalid",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
            validation_mode=ValidationMode.STRICT,
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) > 0

    def test_warn_mode_returns_errors(self, validator, tenant_id, agent_id):
        """Should return errors in warn mode (for logging)."""
        field = VariableEntry(
            name="email",
            value="invalid",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
            validation_mode=ValidationMode.WARN,
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) > 0

    def test_disabled_mode_skips_validation(self, validator, tenant_id, agent_id):
        """Should skip validation in disabled mode."""
        field = VariableEntry(
            name="email",
            value="invalid",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            value_type="email",
            validation_mode=ValidationMode.DISABLED,
        )

        errors = validator.validate_field(field, definition)
        assert len(errors) == 0
