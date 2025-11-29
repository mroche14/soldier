"""Unit tests for EnforcementValidator."""

from uuid import uuid4

import pytest

from soldier.alignment.context.models import Context
from soldier.alignment.enforcement.validator import EnforcementValidator
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.models import Rule


class DummyGenerator(ResponseGenerator):
    """Stub generator that returns a fixed response."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def generate(self, *args, **kwargs):
        class Dummy:
            def __init__(self, content: str):
                self.response = content

        return Dummy(self._response)


@pytest.mark.asyncio
async def test_validator_passes_when_no_constraints() -> None:
    validator = EnforcementValidator(response_generator=DummyGenerator("ok"))
    result = await validator.validate(
        response="hello",
        context=Context(message="hello"),
        matched_rules=[],
        hard_rules=[],
    )
    assert result.passed is True
    assert result.final_response == "hello"


@pytest.mark.asyncio
async def test_validator_detects_violation_and_regenerates() -> None:
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="No secret",
        condition_text="Always",
        action_text="secret",
        is_hard_constraint=True,
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(response_generator=DummyGenerator("clean response"))
    result = await validator.validate(
        response="This contains secret",
        context=Context(message=""),
        matched_rules=[matched],
        hard_rules=[hard_rule],
    )

    assert result.regeneration_attempted is True
    # Final response uses regenerated since violation removed
    assert result.final_response == "clean response"


@pytest.mark.asyncio
async def test_validator_returns_original_on_regen_failure() -> None:
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="No secret",
        condition_text="Always",
        action_text="secret",
        is_hard_constraint=True,
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    class FailingGenerator(ResponseGenerator):
        async def generate(self, *args, **kwargs):
            raise RuntimeError("fail")

    validator = EnforcementValidator(response_generator=FailingGenerator(None))
    result = await validator.validate(
        response="This contains secret",
        context=Context(message=""),
        matched_rules=[matched],
        hard_rules=[hard_rule],
    )

    assert result.passed is False
    assert result.final_response == "This contains secret"
