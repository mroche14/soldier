"""Customer data updater for Phase 3.

Handles mapping candidate variables from Situational Sensor to InterlocutorDataStore.
"""

from datetime import UTC, datetime
from typing import Any

from ruche.brains.focal.phases.context.situation_snapshot import CandidateVariableInfo
from ruche.brains.focal.phases.interlocutor.models import InterlocutorDataUpdate
from ruche.config.models.pipeline import InterlocutorDataUpdateConfig
from ruche.interlocutor_data.enums import VariableSource
from ruche.interlocutor_data.models import (
    InterlocutorDataField,
    InterlocutorDataStore,
    VariableEntry,
)
from ruche.interlocutor_data.validation import InterlocutorDataFieldValidator
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class ValidationResult:
    """Result of validation and coercion."""

    def __init__(self, is_valid: bool, coerced_value: Any | None = None, error: str | None = None):
        self.is_valid = is_valid
        self.coerced_value = coerced_value
        self.error = error


class InterlocutorDataUpdater:
    """Handles Phase 3 customer data updates.

    Takes candidate variables from P2 and updates InterlocutorDataStore in-memory.
    """

    def __init__(
        self,
        validator: InterlocutorDataFieldValidator,
        config: InterlocutorDataUpdateConfig | None = None,
    ):
        self._validator = validator
        self._config = config or InterlocutorDataUpdateConfig()
        self._logger = get_logger(__name__)

    async def update(
        self,
        customer_data_store: InterlocutorDataStore,
        candidate_variables: dict[str, CandidateVariableInfo],
        field_definitions: list[InterlocutorDataField],
    ) -> tuple[InterlocutorDataStore, list[InterlocutorDataUpdate]]:
        """Execute Phase 3 update flow.

        Returns:
            - Updated InterlocutorDataStore (in-memory)
            - List of persistent_updates to save at P11
        """
        # P3.1: Match candidates to field definitions
        matched_updates = self._match_candidates_to_fields(
            candidate_variables, field_definitions
        )

        # P3.2: Validate & coerce types
        validated_updates = await self._validate_and_coerce(matched_updates)

        # P3.3: Apply updates in memory
        self._apply_updates_in_memory(customer_data_store, validated_updates)

        # P3.4: Mark updates for persistence
        persistent_updates = self._mark_for_persistence(validated_updates)

        return customer_data_store, persistent_updates

    def _match_candidates_to_fields(
        self,
        candidate_variables: dict[str, CandidateVariableInfo],
        field_definitions: list[InterlocutorDataField],
    ) -> list[InterlocutorDataUpdate]:
        """P3.1: Match candidate keys to known field definitions.

        Returns:
            List of InterlocutorDataUpdate with matched definitions
        """
        updates: list[InterlocutorDataUpdate] = []
        definitions_by_name = {d.name: d for d in field_definitions}

        for name, candidate in candidate_variables.items():
            definition = definitions_by_name.get(name)

            if not definition:
                self._logger.warning(
                    "candidate_variable_no_definition",
                    name=name,
                    value=candidate.value,
                )
                continue

            updates.append(
                InterlocutorDataUpdate(
                    field_name=name,
                    field_definition=definition,
                    raw_value=candidate.value,
                    is_update=candidate.is_update,
                )
            )

        return updates

    async def _validate_and_coerce(
        self, updates: list[InterlocutorDataUpdate]
    ) -> list[InterlocutorDataUpdate]:
        """P3.2: Validate and type-coerce values.

        Uses InterlocutorDataFieldValidator to check types, regex, allowed_values.
        """
        for update in updates:
            result = self._validate_value(update.field_definition, update.raw_value)

            if result.is_valid:
                update.validated_value = result.coerced_value
            else:
                update.validation_error = result.error
                self._logger.warning(
                    "candidate_variable_validation_failed",
                    name=update.field_name,
                    raw_value=update.raw_value,
                    error=result.error,
                )

        return updates

    def _validate_value(
        self, field_definition: InterlocutorDataField, raw_value: Any
    ) -> ValidationResult:
        """Validate and coerce a value using InterlocutorDataFieldValidator."""
        # Create temporary VariableEntry for validation
        temp_entry = VariableEntry(
            name=field_definition.name,
            value=raw_value,
            value_type=field_definition.value_type,
            source=VariableSource.USER_PROVIDED,
            collected_at=utc_now(),
            updated_at=utc_now(),
        )

        errors = self._validator.validate_field(temp_entry, field_definition)

        if errors:
            error_messages = [e.message for e in errors]
            return ValidationResult(is_valid=False, error="; ".join(error_messages))

        # Type coercion
        coerced_value = self._coerce_type(raw_value, field_definition.value_type)
        return ValidationResult(is_valid=True, coerced_value=coerced_value)

    def _coerce_type(self, value: Any, value_type: str) -> Any:
        """Coerce value to expected type."""
        if value is None:
            return None

        try:
            if value_type == "number":
                if isinstance(value, (int, float)):
                    return value
                return float(value)
            elif value_type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1")
                return bool(value)
            elif value_type == "string":
                return str(value)
            else:
                # Other types (email, phone, date, json) - return as-is after validation
                return value
        except (ValueError, TypeError):
            return value

    def _apply_updates_in_memory(
        self,
        customer_data_store: InterlocutorDataStore,
        updates: list[InterlocutorDataUpdate],
    ) -> None:
        """P3.3: Mutate InterlocutorDataStore in-memory (no DB writes).

        Only applies updates with valid values.
        """
        for update in updates:
            if update.validation_error or update.validated_value is None:
                continue

            # Check if field exists for history tracking
            existing_entry = customer_data_store.fields.get(update.field_name)
            history = []
            if existing_entry:
                # Add current value to history
                history = existing_entry.history.copy()
                history.append({
                    "value": existing_entry.value,
                    "timestamp": existing_entry.updated_at.isoformat(),
                    "source": existing_entry.source.value if hasattr(existing_entry.source, "value") else str(existing_entry.source),
                    "confidence": existing_entry.confidence,
                })

                # Trim history if it exceeds max_history_entries
                if self._config.max_history_entries and len(history) > self._config.max_history_entries:
                    history = history[-self._config.max_history_entries:]

            entry = VariableEntry(
                name=update.field_name,
                value=update.validated_value,
                value_type=update.field_definition.value_type,
                source=VariableSource.LLM_EXTRACTED,  # From situation sensor extraction
                collected_at=utc_now(),
                updated_at=utc_now(),
                confidence=1.0,
                field_definition_id=update.field_definition.id,
                history=history,
            )

            customer_data_store.fields[update.field_name] = entry

            self._logger.info(
                "customer_variable_updated",
                name=update.field_name,
                scope=update.field_definition.scope,
                is_update=update.is_update,
            )

    def _mark_for_persistence(
        self,
        updates: list[InterlocutorDataUpdate],
    ) -> list[InterlocutorDataUpdate]:
        """P3.4: Filter updates that should be persisted at P11.

        Logic:
        - scope=SESSION: Never persist (in-memory only)
        - persist=False: Never persist (even IDENTITY/BUSINESS)
        - Otherwise: Persist
        """
        persistent = []

        for update in updates:
            if update.validation_error or update.validated_value is None:
                continue

            definition = update.field_definition

            # Skip SESSION scope (ephemeral)
            if definition.scope == "SESSION":
                continue

            # Skip if persist=False
            if not definition.persist:
                continue

            persistent.append(update)

        self._logger.info(
            "customer_data_persistence_marked",
            total_updates=len(updates),
            persistent_updates=len(persistent),
        )

        return persistent
