"""Unit tests for VariableResolver."""

import pytest

from soldier.alignment.execution.variable_resolver import VariableResolver


@pytest.fixture
def resolver() -> VariableResolver:
    return VariableResolver()


@pytest.mark.parametrize(
    "template,variables,expected",
    [
        ("Hello {name}", {"name": "Alice"}, "Hello Alice"),
        ("{greeting} {name}", {"greeting": "Hi", "name": "Bob"}, "Hi Bob"),
        ("Hello {name}", {}, "Hello {name}"),
        ("Code: {{literal}}", {}, "Code: {literal}"),
        ("", {"name": "Alice"}, ""),
        ("Hello world", {"name": "Alice"}, "Hello world"),
    ],
)
def test_resolve_template(resolver: VariableResolver, template: str, variables: dict, expected: str) -> None:
    result = resolver.resolve(template, variables)
    assert result == expected


@pytest.mark.parametrize("invalid_input", [None, 123, ["list"], {"dict": "value"}])
def test_resolve_rejects_invalid_template_type(resolver: VariableResolver, invalid_input) -> None:
    with pytest.raises(TypeError):
        resolver.resolve(invalid_input, {})
