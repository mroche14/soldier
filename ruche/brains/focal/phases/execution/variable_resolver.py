"""Variable resolution helper."""

from string import Formatter
from typing import Any

from ruche.conversation.models.session import Session
from ruche.interlocutor_data.enums import ItemStatus
from ruche.domain.interlocutor.models import InterlocutorDataStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class VariableResolver:
    """Resolve variables in template strings and from multiple sources.

    Supports standard Python format string syntax: {variable_name}
    Unresolved variables are preserved as-is for later resolution.

    Resolution order:
    1. InterlocutorDataStore (active fields)
    2. Session variables
    """

    def resolve(self, template: str, variables: dict[str, Any]) -> str:
        """Resolve {var} placeholders in a template string.

        Unknown variables remain unchanged; double braces are preserved.

        Raises:
            TypeError: If template is not a string
        """
        if not isinstance(template, str):
            raise TypeError("template must be a string")

        formatter = Formatter()
        result_parts: list[str] = []

        for literal_text, field_name, format_spec, _conversion in formatter.parse(template):
            if literal_text:
                result_parts.append(literal_text)

            if field_name is None:
                continue

            if field_name in variables:
                value = variables[field_name]
                result_parts.append(format(value, format_spec or ""))
            else:
                # Preserve unresolved placeholder
                placeholder = "{" + field_name
                if format_spec:
                    placeholder += f":{format_spec}"
                placeholder += "}"
                result_parts.append(placeholder)

        return "".join(result_parts)

    async def resolve_variables(
        self,
        required_vars: set[str],
        customer_profile: InterlocutorDataStore,
        session: Session,
    ) -> tuple[dict[str, Any], set[str]]:
        """Resolve variables from InterlocutorDataStore and Session.

        Resolution order:
        1. InterlocutorDataStore.fields (active status only)
        2. Session.variables

        Args:
            required_vars: Set of variable names to resolve
            customer_profile: Customer data store
            session: Session state

        Returns:
            (known_vars, missing_vars): Resolved values and still-missing names
        """
        known_vars: dict[str, Any] = {}
        sources: dict[str, str] = {}

        # First: Resolve from InterlocutorDataStore (active fields only)
        for var_name in required_vars:
            if var_name in customer_profile.fields:
                entry = customer_profile.fields[var_name]
                # Only use active fields
                if entry.status == ItemStatus.ACTIVE:
                    known_vars[var_name] = entry.value
                    sources[var_name] = "customer_data"

        # Second: Resolve from Session variables (override if not yet found)
        for var_name in required_vars:
            if var_name not in known_vars and var_name in session.variables:
                known_vars[var_name] = session.variables[var_name]
                sources[var_name] = "session"

        # Compute missing variables
        missing_vars = required_vars - known_vars.keys()

        logger.info(
            "resolved_variables",
            required_count=len(required_vars),
            resolved_count=len(known_vars),
            missing_count=len(missing_vars),
            from_customer_data=sum(1 for s in sources.values() if s == "customer_data"),
            from_session=sum(1 for s in sources.values() if s == "session"),
        )

        return known_vars, missing_vars
