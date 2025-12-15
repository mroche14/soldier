"""Tests for base models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ruche.brains.focal.models.base import (
    AgentScopedModel,
    TenantScopedModel,
    utc_now,
)


class TestUtcNow:
    """Tests for utc_now helper."""

    def test_returns_utc_datetime(self) -> None:
        """Should return UTC timezone-aware datetime."""
        result = utc_now()
        assert result.tzinfo == UTC

    def test_returns_current_time(self) -> None:
        """Should return current time (within tolerance)."""
        before = datetime.now(UTC)
        result = utc_now()
        after = datetime.now(UTC)
        assert before <= result <= after


class TestTenantScopedModel:
    """Tests for TenantScopedModel base class."""

    def test_requires_tenant_id(self) -> None:
        """Should require tenant_id."""
        with pytest.raises(ValueError):
            TenantScopedModel()

    def test_accepts_tenant_id(self) -> None:
        """Should accept valid tenant_id."""
        tenant_id = uuid4()
        model = TenantScopedModel(tenant_id=tenant_id)
        assert model.tenant_id == tenant_id

    def test_auto_sets_created_at(self) -> None:
        """Should automatically set created_at."""
        model = TenantScopedModel(tenant_id=uuid4())
        assert model.created_at is not None
        assert model.created_at.tzinfo == UTC

    def test_auto_sets_updated_at(self) -> None:
        """Should automatically set updated_at."""
        model = TenantScopedModel(tenant_id=uuid4())
        assert model.updated_at is not None
        assert model.updated_at.tzinfo == UTC

    def test_deleted_at_defaults_to_none(self) -> None:
        """Should default deleted_at to None."""
        model = TenantScopedModel(tenant_id=uuid4())
        assert model.deleted_at is None

    def test_is_deleted_false_when_deleted_at_none(self) -> None:
        """Should report not deleted when deleted_at is None."""
        model = TenantScopedModel(tenant_id=uuid4())
        assert model.is_deleted is False

    def test_is_deleted_true_when_deleted_at_set(self) -> None:
        """Should report deleted when deleted_at is set."""
        model = TenantScopedModel(
            tenant_id=uuid4(),
            deleted_at=datetime.now(UTC),
        )
        assert model.is_deleted is True

    def test_ignores_unknown_fields(self) -> None:
        """Should ignore unknown fields (extra='ignore')."""
        model = TenantScopedModel(
            tenant_id=uuid4(),
            unknown_field="value",  # type: ignore
        )
        assert not hasattr(model, "unknown_field")


class TestAgentScopedModel:
    """Tests for AgentScopedModel base class."""

    def test_requires_tenant_id_and_agent_id(self) -> None:
        """Should require both tenant_id and agent_id."""
        with pytest.raises(ValueError):
            AgentScopedModel()

        with pytest.raises(ValueError):
            AgentScopedModel(tenant_id=uuid4())

    def test_accepts_tenant_and_agent_id(self) -> None:
        """Should accept valid tenant_id and agent_id."""
        tenant_id = uuid4()
        agent_id = uuid4()
        model = AgentScopedModel(tenant_id=tenant_id, agent_id=agent_id)
        assert model.tenant_id == tenant_id
        assert model.agent_id == agent_id

    def test_inherits_tenant_scoped_behavior(self) -> None:
        """Should inherit TenantScopedModel behavior."""
        model = AgentScopedModel(tenant_id=uuid4(), agent_id=uuid4())
        assert model.created_at is not None
        assert model.updated_at is not None
        assert model.deleted_at is None
        assert model.is_deleted is False
