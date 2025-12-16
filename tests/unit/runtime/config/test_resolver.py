"""Unit tests for ConfigResolver resolution logic."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ruche.runtime.config.resolver import ConfigContext, ConfigResolver, ResolvedConfig


class MockConfigStore:
    """Mock ConfigStore for testing."""

    def __init__(self):
        self.tenant_configs = {}
        self.agent_configs = {}
        self.channel_configs = {}
        self.scenario_configs = {}
        self.step_configs = {}

    async def get_agent(self, tenant_id, agent_id):
        """Mock get_agent method."""
        return None  # Returns None to trigger default behavior


@pytest.fixture
def config_store() -> MockConfigStore:
    """Create mock config store."""
    return MockConfigStore()


@pytest.fixture
def resolver(config_store: MockConfigStore) -> ConfigResolver:
    """Create config resolver with mock store."""
    return ConfigResolver(config_store=config_store)


@pytest.fixture
def custom_resolver(config_store: MockConfigStore) -> ConfigResolver:
    """Create config resolver with custom platform defaults."""
    custom_defaults = ResolvedConfig(
        accumulation_window_ms=5000,
        temperature=0.5,
    )
    return ConfigResolver(config_store=config_store, platform_defaults=custom_defaults)


class TestResolvedConfig:
    """Tests for ResolvedConfig model."""

    def test_resolved_config_has_defaults(self) -> None:
        """ResolvedConfig has expected defaults."""
        config = ResolvedConfig()

        assert config.accumulation_window_ms == 3000
        assert config.max_response_length == 4096
        assert config.temperature == 0.7
        assert config.enable_memory_retrieval is True

    def test_resolved_config_accepts_overrides(self) -> None:
        """Can override default values."""
        config = ResolvedConfig(
            accumulation_window_ms=5000,
            temperature=0.5,
            enable_memory_retrieval=False,
        )

        assert config.accumulation_window_ms == 5000
        assert config.temperature == 0.5
        assert config.enable_memory_retrieval is False

    def test_resolved_config_extra_dict(self) -> None:
        """Extra field holds additional configuration."""
        config = ResolvedConfig(extra={"custom_flag": True, "custom_value": 42})

        assert config.extra["custom_flag"] is True
        assert config.extra["custom_value"] == 42

    def test_resolved_config_temperature_validation(self) -> None:
        """Temperature is validated."""
        with pytest.raises(Exception):
            ResolvedConfig(temperature=3.0)  # > 2.0


class TestConfigContext:
    """Tests for ConfigContext."""

    def test_config_context_creation(self) -> None:
        """Can create ConfigContext."""
        tenant_id = uuid4()
        agent_id = uuid4()

        ctx = ConfigContext(tenant_id=tenant_id, agent_id=agent_id)

        assert ctx.tenant_id == tenant_id
        assert ctx.agent_id == agent_id
        assert ctx.channel is None
        assert ctx.scenario_id is None
        assert ctx.step_id is None

    def test_config_context_with_optional_fields(self) -> None:
        """Optional fields can be set."""
        tenant_id = uuid4()
        agent_id = uuid4()
        scenario_id = uuid4()

        ctx = ConfigContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            scenario_id=scenario_id,
        )

        assert ctx.channel == "whatsapp"
        assert ctx.scenario_id == scenario_id


class TestMakeCacheKey:
    """Tests for cache key generation."""

    def test_make_cache_key_basic(self, resolver: ConfigResolver) -> None:
        """Basic cache key includes tenant and agent."""
        tenant_id = uuid4()
        agent_id = uuid4()
        ctx = ConfigContext(tenant_id=tenant_id, agent_id=agent_id)

        key = resolver._make_cache_key(ctx)

        assert str(tenant_id) in key
        assert str(agent_id) in key

    def test_make_cache_key_with_channel(self, resolver: ConfigResolver) -> None:
        """Cache key includes channel when present."""
        tenant_id = uuid4()
        agent_id = uuid4()
        ctx = ConfigContext(
            tenant_id=tenant_id, agent_id=agent_id, channel="whatsapp"
        )

        key = resolver._make_cache_key(ctx)

        assert "whatsapp" in key

    def test_make_cache_key_with_scenario(self, resolver: ConfigResolver) -> None:
        """Cache key includes scenario when present."""
        tenant_id = uuid4()
        agent_id = uuid4()
        scenario_id = uuid4()
        ctx = ConfigContext(
            tenant_id=tenant_id, agent_id=agent_id, scenario_id=scenario_id
        )

        key = resolver._make_cache_key(ctx)

        assert str(scenario_id) in key

    def test_make_cache_key_different_contexts_different_keys(
        self, resolver: ConfigResolver
    ) -> None:
        """Different contexts produce different keys."""
        ctx1 = ConfigContext(tenant_id=uuid4(), agent_id=uuid4())
        ctx2 = ConfigContext(tenant_id=uuid4(), agent_id=uuid4())

        key1 = resolver._make_cache_key(ctx1)
        key2 = resolver._make_cache_key(ctx2)

        assert key1 != key2


class TestResolve:
    """Tests for configuration resolution."""

    async def test_resolve_uses_platform_defaults(
        self, resolver: ConfigResolver
    ) -> None:
        """Resolution starts with platform defaults."""
        config = await resolver.resolve(tenant_id=uuid4(), agent_id=uuid4())

        assert config.accumulation_window_ms == 3000  # Platform default
        assert config.temperature == 0.7  # Platform default

    async def test_resolve_uses_custom_defaults(
        self, custom_resolver: ConfigResolver
    ) -> None:
        """Custom platform defaults are used."""
        config = await custom_resolver.resolve(tenant_id=uuid4(), agent_id=uuid4())

        assert config.accumulation_window_ms == 5000  # Custom default
        assert config.temperature == 0.5  # Custom default

    async def test_resolve_caches_result(self, resolver: ConfigResolver) -> None:
        """Resolution result is cached."""
        tenant_id = uuid4()
        agent_id = uuid4()

        config1 = await resolver.resolve(tenant_id, agent_id)
        config2 = await resolver.resolve(tenant_id, agent_id)

        assert config1 is config2  # Same object from cache

    async def test_resolve_skip_cache(self, resolver: ConfigResolver) -> None:
        """Can skip cache when requested."""
        tenant_id = uuid4()
        agent_id = uuid4()

        config1 = await resolver.resolve(tenant_id, agent_id, use_cache=True)
        config2 = await resolver.resolve(tenant_id, agent_id, use_cache=False)

        assert config1 is not config2  # Different objects

    async def test_resolve_different_contexts_separate_cache(
        self, resolver: ConfigResolver
    ) -> None:
        """Different contexts cached separately."""
        tenant_id = uuid4()
        agent_id1 = uuid4()
        agent_id2 = uuid4()

        config1 = await resolver.resolve(tenant_id, agent_id1)
        config2 = await resolver.resolve(tenant_id, agent_id2)

        assert config1 is not config2


class TestMergeConfig:
    """Tests for configuration merging."""

    def test_merge_config_overrides_base(self, resolver: ConfigResolver) -> None:
        """Override values replace base values."""
        base = {"temperature": 0.7, "max_response_length": 4096}
        override = {"temperature": 0.5}

        result = resolver._merge_config(base, override)

        assert result["temperature"] == 0.5
        assert result["max_response_length"] == 4096

    def test_merge_config_none_values_ignored(self, resolver: ConfigResolver) -> None:
        """None values in override don't replace base."""
        base = {"temperature": 0.7}
        override = {"temperature": None}

        result = resolver._merge_config(base, override)

        assert result["temperature"] == 0.7

    def test_merge_config_merges_extra_dict(self, resolver: ConfigResolver) -> None:
        """Extra dictionaries are merged."""
        base = {"extra": {"key1": "value1"}}
        override = {"extra": {"key2": "value2"}}

        result = resolver._merge_config(base, override)

        assert result["extra"]["key1"] == "value1"
        assert result["extra"]["key2"] == "value2"

    def test_merge_config_extra_override_replaces(
        self, resolver: ConfigResolver
    ) -> None:
        """Override extra values replace base."""
        base = {"extra": {"key": "old"}}
        override = {"extra": {"key": "new"}}

        result = resolver._merge_config(base, override)

        assert result["extra"]["key"] == "new"

    def test_merge_config_adds_new_fields(self, resolver: ConfigResolver) -> None:
        """New fields in override are added."""
        base = {"temperature": 0.7}
        override = {"max_response_length": 2048}

        result = resolver._merge_config(base, override)

        assert result["temperature"] == 0.7
        assert result["max_response_length"] == 2048


class TestClearCache:
    """Tests for cache clearing."""

    async def test_clear_cache_removes_all_entries(
        self, resolver: ConfigResolver
    ) -> None:
        """Clear removes all cached configurations."""
        tenant_id = uuid4()
        agent_id = uuid4()

        await resolver.resolve(tenant_id, agent_id)
        assert len(resolver._cache) > 0

        resolver.clear_cache()
        assert len(resolver._cache) == 0


class TestInvalidate:
    """Tests for cache invalidation."""

    async def test_invalidate_tenant_removes_all_tenant_entries(
        self, resolver: ConfigResolver
    ) -> None:
        """Invalidating tenant removes all its cached configs."""
        tenant_id = uuid4()
        agent_id1 = uuid4()
        agent_id2 = uuid4()

        await resolver.resolve(tenant_id, agent_id1)
        await resolver.resolve(tenant_id, agent_id2)

        resolver.invalidate(tenant_id)

        assert len(resolver._cache) == 0

    async def test_invalidate_specific_agent(self, resolver: ConfigResolver) -> None:
        """Can invalidate specific agent config."""
        tenant_id = uuid4()
        agent_id1 = uuid4()
        agent_id2 = uuid4()

        await resolver.resolve(tenant_id, agent_id1)
        await resolver.resolve(tenant_id, agent_id2)

        resolver.invalidate(tenant_id, agent_id1)

        key1 = f"{tenant_id}:{agent_id1}"
        key2 = f"{tenant_id}:{agent_id2}"

        assert not any(k.startswith(key1) for k in resolver._cache.keys())
        assert any(k.startswith(key2) for k in resolver._cache.keys())

    async def test_invalidate_doesnt_affect_other_tenants(
        self, resolver: ConfigResolver
    ) -> None:
        """Invalidating one tenant doesn't affect others."""
        tenant_id1 = uuid4()
        tenant_id2 = uuid4()
        agent_id = uuid4()

        await resolver.resolve(tenant_id1, agent_id)
        await resolver.resolve(tenant_id2, agent_id)

        resolver.invalidate(tenant_id1)

        key2 = f"{tenant_id2}:{agent_id}"
        assert any(k.startswith(key2) for k in resolver._cache.keys())


class TestLayerGetters:
    """Tests for individual config layer getter methods."""

    async def test_get_tenant_config_returns_none(
        self, resolver: ConfigResolver
    ) -> None:
        """Tenant-level config not yet implemented."""
        result = await resolver._get_tenant_config(uuid4())
        assert result is None

    async def test_get_channel_config_returns_none(
        self, resolver: ConfigResolver
    ) -> None:
        """Channel-level config not yet implemented."""
        result = await resolver._get_channel_config(
            tenant_id=uuid4(), agent_id=uuid4(), channel="whatsapp"
        )
        assert result is None

    async def test_get_scenario_config_returns_none(
        self, resolver: ConfigResolver
    ) -> None:
        """Scenario-level config not yet implemented."""
        result = await resolver._get_scenario_config(
            tenant_id=uuid4(), scenario_id=uuid4()
        )
        assert result is None

    async def test_get_step_config_returns_none(self, resolver: ConfigResolver) -> None:
        """Step-level config not yet implemented."""
        result = await resolver._get_step_config(
            tenant_id=uuid4(), scenario_id=uuid4(), step_id=uuid4()
        )
        assert result is None


class TestIntegration:
    """Integration tests for ConfigResolver."""

    async def test_resolve_all_layers(self, resolver: ConfigResolver) -> None:
        """Full resolution with all context layers."""
        tenant_id = uuid4()
        agent_id = uuid4()
        scenario_id = uuid4()
        step_id = uuid4()

        config = await resolver.resolve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel="whatsapp",
            scenario_id=scenario_id,
            step_id=step_id,
        )

        assert isinstance(config, ResolvedConfig)

    async def test_resolve_minimal_context(self, resolver: ConfigResolver) -> None:
        """Resolution works with minimal context."""
        config = await resolver.resolve(tenant_id=uuid4(), agent_id=uuid4())

        assert isinstance(config, ResolvedConfig)
        assert config.accumulation_window_ms > 0

    async def test_cache_hit_performance(self, resolver: ConfigResolver) -> None:
        """Cached resolution doesn't call config store."""
        tenant_id = uuid4()
        agent_id = uuid4()

        await resolver.resolve(tenant_id, agent_id)

        config = await resolver.resolve(tenant_id, agent_id, use_cache=True)

        assert isinstance(config, ResolvedConfig)
