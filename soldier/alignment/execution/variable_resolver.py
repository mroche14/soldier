"""Variable resolution helper."""

from string import Formatter
from typing import Any


class VariableResolver:
    """Resolve variables in template strings.

    Supports standard Python format string syntax: {variable_name}
    Unresolved variables are preserved as-is for later resolution.
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
