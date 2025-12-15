"""Unit tests for EnforcementValidator."""

from uuid import uuid4

import pytest

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.enforcement.validator import EnforcementValidator
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.models import Rule


class DummyConfigStore:
    """Mock config store for testing."""

    async def get_rules(self, **kwargs):
        """Return empty list of rules."""
        return []


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
    validator = EnforcementValidator(
        response_generator=DummyGenerator("ok"),
        agent_config_store=DummyConfigStore(),
    )
    result = await validator.validate(
        response="hello",
        snapshot=SituationSnapshot(
            message="hello",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        ),
        matched_rules=[],
        tenant_id=uuid4(),
        agent_id=uuid4(),
        hard_rules=[],
    )
    assert result.passed is True
    assert result.final_response == "hello"


@pytest.mark.asyncio
async def test_validator_detects_violation_and_regenerates() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="No secret",
        condition_text="Always",
        action_text="secret",
        is_hard_constraint=True,
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(
        response_generator=DummyGenerator("clean response"),
        agent_config_store=DummyConfigStore(),
    )
    result = await validator.validate(
        response="This contains secret",
        snapshot=SituationSnapshot(
            message="",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        ),
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
        hard_rules=[hard_rule],
    )

    assert result.regeneration_attempted is True
    # Final response uses regenerated since violation removed
    assert result.final_response == "clean response"


@pytest.mark.asyncio
async def test_validator_returns_original_on_regen_failure() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="No secret",
        condition_text="Always",
        action_text="secret",
        is_hard_constraint=True,
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    class FailingGenerator(ResponseGenerator):
        async def generate(self, *args, **kwargs):
            raise RuntimeError("fail")

    validator = EnforcementValidator(
        response_generator=FailingGenerator(None),
        agent_config_store=DummyConfigStore(),
    )
    result = await validator.validate(
        response="This contains secret",
        snapshot=SituationSnapshot(
            message="",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        ),
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
        hard_rules=[hard_rule],
    )

    assert result.passed is False
    assert result.final_response == "This contains secret"
