"""Schema validation service for profile fields.

Validates profile fields against their definitions using configurable validation modes.
"""

import json
import re
from datetime import datetime
from typing import Any

from soldier.observability.logging import get_logger
from soldier.profile.enums import ValidationMode
from soldier.profile.models import ProfileField, ProfileFieldDefinition

logger = get_logger(__name__)


class ValidationError:
    """A single validation error."""

    def __init__(self, field_name: str, error_type: str, message: str):
        self.field_name = field_name
        self.error_type = error_type
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationError({self.field_name!r}, {self.error_type!r}, {self.message!r})"


class ProfileFieldValidator:
    """Service for validating profile fields against schema definitions.

    Supports multiple validation modes:
    - STRICT: Reject invalid values (returns errors)
    - WARN: Accept values but return warnings
    - DISABLED: Skip validation entirely
    """

    # Type validators mapped by value_type
    TYPE_VALIDATORS = {
        "string": "_validate_string",
        "email": "_validate_email",
        "phone": "_validate_phone",
        "date": "_validate_date",
        "number": "_validate_number",
        "boolean": "_validate_boolean",
        "json": "_validate_json",
    }

    def validate_field(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate a field against its definition.

        Args:
            field: The field to validate
            definition: The schema definition to validate against

        Returns:
            List of validation errors (empty if valid)
        """
        # Check validation mode
        if definition.validation_mode == ValidationMode.DISABLED:
            return []

        errors: list[ValidationError] = []

        # Type validation
        type_errors = self._validate_type(field, definition)
        errors.extend(type_errors)

        # Regex validation (if defined)
        if definition.validation_regex:
            regex_errors = self._validate_regex(field, definition)
            errors.extend(regex_errors)

        # Allowed values validation (if defined)
        if definition.allowed_values:
            allowed_errors = self._validate_allowed_values(field, definition)
            errors.extend(allowed_errors)

        # T171: Log validation failures
        if errors:
            logger.warning(
                "schema_validation_failed",
                field_name=field.name,
                error_count=len(errors),
                error_types=[e.error_type for e in errors],
                validation_mode=definition.validation_mode.value,
            )

        return errors

    def _validate_type(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate field value against expected type."""
        validator_name = self.TYPE_VALIDATORS.get(definition.value_type)
        if not validator_name:
            # Unknown type, skip validation
            return []

        validator = getattr(self, validator_name)
        return validator(field, definition)

    def _validate_string(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate string type."""
        if not isinstance(field.value, str):
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    f"Expected string, got {type(field.value).__name__}",
                )
            ]
        return []

    def _validate_email(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate email format."""
        if not isinstance(field.value, str):
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    f"Expected string for email, got {type(field.value).__name__}",
                )
            ]

        # Basic email regex (RFC 5322 simplified)
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, field.value):
            return [
                ValidationError(
                    field.name,
                    "format_error",
                    f"Invalid email format: {field.value}",
                )
            ]
        return []

    def _validate_phone(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate phone number format."""
        if not isinstance(field.value, str):
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    f"Expected string for phone, got {type(field.value).__name__}",
                )
            ]

        # Allow digits, spaces, hyphens, parentheses, and plus sign
        phone_pattern = r"^[\d\s\-\(\)\+]+$"
        if not re.match(phone_pattern, field.value):
            return [
                ValidationError(
                    field.name,
                    "format_error",
                    f"Invalid phone format: {field.value}",
                )
            ]

        # Minimum 7 digits
        digits_only = re.sub(r"\D", "", field.value)
        if len(digits_only) < 7:
            return [
                ValidationError(
                    field.name,
                    "format_error",
                    "Phone number must have at least 7 digits",
                )
            ]
        return []

    def _validate_date(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate date format (ISO 8601)."""
        if isinstance(field.value, datetime):
            return []

        if not isinstance(field.value, str):
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    f"Expected string or datetime for date, got {type(field.value).__name__}",
                )
            ]

        # Try parsing ISO 8601 formats
        date_formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
        for fmt in date_formats:
            try:
                datetime.strptime(field.value, fmt)
                return []
            except ValueError:
                continue

        return [
            ValidationError(
                field.name,
                "format_error",
                f"Invalid date format: {field.value}. Expected ISO 8601 (YYYY-MM-DD)",
            )
        ]

    def _validate_number(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate number type."""
        if isinstance(field.value, bool):
            # bool is subclass of int, but we don't want it
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    "Expected number, got boolean",
                )
            ]

        if isinstance(field.value, (int, float)):
            return []

        if isinstance(field.value, str):
            try:
                float(field.value)
                return []
            except ValueError:
                pass

        return [
            ValidationError(
                field.name,
                "type_error",
                f"Expected number, got {type(field.value).__name__}",
            )
        ]

    def _validate_boolean(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate boolean type."""
        if isinstance(field.value, bool):
            return []

        if isinstance(field.value, str):
            if field.value.lower() in ("true", "false", "yes", "no", "1", "0"):
                return []

        return [
            ValidationError(
                field.name,
                "type_error",
                f"Expected boolean, got {type(field.value).__name__}",
            )
        ]

    def _validate_json(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate JSON type."""
        if isinstance(field.value, (dict, list)):
            return []

        if isinstance(field.value, str):
            try:
                json.loads(field.value)
                return []
            except json.JSONDecodeError as e:
                return [
                    ValidationError(
                        field.name,
                        "format_error",
                        f"Invalid JSON: {e}",
                    )
                ]

        return [
            ValidationError(
                field.name,
                "type_error",
                f"Expected JSON object/array or string, got {type(field.value).__name__}",
            )
        ]

    def _validate_regex(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate field value against custom regex pattern."""
        if not definition.validation_regex:
            return []

        if not isinstance(field.value, str):
            return [
                ValidationError(
                    field.name,
                    "type_error",
                    "Regex validation requires string value",
                )
            ]

        try:
            pattern = re.compile(definition.validation_regex)
            if not pattern.match(field.value):
                return [
                    ValidationError(
                        field.name,
                        "regex_error",
                        f"Value does not match pattern: {definition.validation_regex}",
                    )
                ]
        except re.error as e:
            return [
                ValidationError(
                    field.name,
                    "config_error",
                    f"Invalid regex pattern in definition: {e}",
                )
            ]

        return []

    def _validate_allowed_values(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[ValidationError]:
        """Validate field value is in allowed values list."""
        if not definition.allowed_values:
            return []

        if field.value not in definition.allowed_values:
            return [
                ValidationError(
                    field.name,
                    "allowed_values_error",
                    f"Value '{field.value}' not in allowed values: {definition.allowed_values}",
                )
            ]

        return []
