"""Configuration Resolver - Multi-level configuration resolution.

Resolves configuration at runtime by merging settings from:
1. Platform defaults
2. Tenant-level config
3. Agent-level config
4. Channel-level overrides
5. Scenario-level overrides
6. Step-level overrides

Later levels override earlier levels.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, Field

from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.infrastructure.stores.config.interface import ConfigStore

logger = get_logger(__name__)


class ResolvedConfig(BaseModel):
    """Fully resolved configuration for a specific context.

    All fields have defaults that can be overridden at any level.
    """
    # Message accumulation
    accumulation_window_ms: int = Field(
        default=3000,
        description="How long to wait for additional messages",
    )

    # Response limits
    max_response_length: int = Field(
        default=4096,
        description="Maximum response length in characters",
    )
    max_response_tokens: int = Field(
        default=1024,
        description="Maximum response tokens",
    )

    # Timeout settings
    processing_timeout_ms: int = Field(
        default=30000,
        description="Maximum time for turn processing",
    )
    tool_execution_timeout_ms: int = Field(
        default=10000,
        description="Maximum time for tool execution",
    )

    # LLM settings
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature",
    )

    # Feature flags
    enable_memory_retrieval: bool = Field(
        default=True,
        description="Whether to retrieve from memory store",
    )
    enable_rule_retrieval: bool = Field(
        default=True,
        description="Whether to retrieve matching rules",
    )
    enable_scenario_tracking: bool = Field(
        default=True,
        description="Whether to track scenario state",
    )

    # Additional settings as dict for flexibility
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration options",
    )


@dataclass
class ConfigContext:
    """Context for configuration resolution."""
    tenant_id: UUID
    agent_id: UUID
    channel: str | None = None
    scenario_id: UUID | None = None
    step_id: UUID | None = None


class ConfigResolver:
    """Multi-level configuration resolution.

    Merges configuration from multiple levels, with later levels
    overriding earlier levels.
    """

    def __init__(
        self,
        config_store: "ConfigStore",
        platform_defaults: ResolvedConfig | None = None,
    ):
        self._config_store = config_store
        self._platform_defaults = platform_defaults or ResolvedConfig()
        self._cache: dict[str, ResolvedConfig] = {}

    def _make_cache_key(self, ctx: ConfigContext) -> str:
        """Create cache key from context."""
        parts = [str(ctx.tenant_id), str(ctx.agent_id)]
        if ctx.channel:
            parts.append(ctx.channel)
        if ctx.scenario_id:
            parts.append(str(ctx.scenario_id))
        if ctx.step_id:
            parts.append(str(ctx.step_id))
        return ":".join(parts)

    async def resolve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str | None = None,
        scenario_id: UUID | None = None,
        step_id: UUID | None = None,
        use_cache: bool = True,
    ) -> ResolvedConfig:
        """Resolve configuration for the given context.

        Resolution order (later overrides earlier):
        1. Platform defaults
        2. Tenant-level config
        3. Agent-level config
        4. Channel-level overrides
        5. Scenario-level overrides
        6. Step-level overrides

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            channel: Optional channel for channel-specific config
            scenario_id: Optional scenario for scenario-specific config
            step_id: Optional step for step-specific config
            use_cache: Whether to use cached results

        Returns:
            Fully resolved configuration
        """
        ctx = ConfigContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=channel,
            scenario_id=scenario_id,
            step_id=step_id,
        )

        cache_key = self._make_cache_key(ctx)

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        logger.debug(
            "resolving_config",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            channel=channel,
        )

        # Start with platform defaults
        config_dict = self._platform_defaults.model_dump()

        # Layer 2: Tenant-level config
        tenant_config = await self._get_tenant_config(tenant_id)
        if tenant_config:
            config_dict = self._merge_config(config_dict, tenant_config)

        # Layer 3: Agent-level config
        agent_config = await self._get_agent_config(tenant_id, agent_id)
        if agent_config:
            config_dict = self._merge_config(config_dict, agent_config)

        # Layer 4: Channel-level config
        if channel:
            channel_config = await self._get_channel_config(
                tenant_id, agent_id, channel
            )
            if channel_config:
                config_dict = self._merge_config(config_dict, channel_config)

        # Layer 5: Scenario-level config
        if scenario_id:
            scenario_config = await self._get_scenario_config(
                tenant_id, scenario_id
            )
            if scenario_config:
                config_dict = self._merge_config(config_dict, scenario_config)

        # Layer 6: Step-level config
        if step_id:
            step_config = await self._get_step_config(
                tenant_id, scenario_id, step_id
            )
            if step_config:
                config_dict = self._merge_config(config_dict, step_config)

        resolved = ResolvedConfig(**config_dict)

        if use_cache:
            self._cache[cache_key] = resolved

        return resolved

    def _merge_config(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge override config into base config."""
        result = base.copy()
        for key, value in override.items():
            if value is not None:
                if key == "extra" and isinstance(value, dict):
                    result["extra"] = {**result.get("extra", {}), **value}
                else:
                    result[key] = value
        return result

    async def _get_tenant_config(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any] | None:
        """Get tenant-level configuration overrides.

        Tenant-level config provides default overrides for all agents
        within a tenant (e.g., organization-wide policies).

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary of config overrides, or None if no tenant config exists

        Note:
            Currently no tenant-level config storage exists in the database.
            This would require a new `tenant_configs` table with JSONB column.
        """
        return None

    async def _get_agent_config(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any] | None:
        """Get agent-level configuration.

        Extracts configuration from the agent's settings, including
        LLM model and generation parameters.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            Dictionary of config overrides from agent settings, or None if agent not found
        """
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if not agent or not agent.settings:
            return None

        config_dict: dict[str, Any] = {}

        if agent.settings.temperature is not None:
            config_dict["temperature"] = agent.settings.temperature

        if agent.settings.max_tokens is not None:
            config_dict["max_response_tokens"] = agent.settings.max_tokens

        return config_dict if config_dict else None

    async def _get_channel_config(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
    ) -> dict[str, Any] | None:
        """Get channel-specific configuration overrides.

        Channel config allows different behavior per communication channel
        (e.g., shorter responses for SMS, different timeout for voice).

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            channel: Channel identifier (e.g., 'whatsapp', 'slack', 'webchat')

        Returns:
            Dictionary of channel-specific config overrides, or None if no config exists

        Note:
            Channel-level config is not currently stored in the database.
            This would require either:
            1. A `channel_configs` table with JSONB config_overrides column
            2. Or expanding the `channel_bindings` table to include runtime config
        """
        return None

    async def _get_scenario_config(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
    ) -> dict[str, Any] | None:
        """Get scenario-level configuration overrides.

        Scenario config allows different behavior within specific conversational
        flows (e.g., stricter validation in checkout, longer timeout for support).

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario identifier

        Returns:
            Dictionary of scenario-specific config overrides, or None if no config exists

        Note:
            Scenario-level config is not currently stored in the database.
            This would require adding a `config_overrides` JSONB column to the
            `scenarios` table, or creating a separate `scenario_configs` table.
        """
        return None

    async def _get_step_config(
        self,
        tenant_id: UUID,
        scenario_id: UUID | None,
        step_id: UUID,
    ) -> dict[str, Any] | None:
        """Get step-level configuration overrides.

        Step config provides the most granular control, allowing different
        behavior at specific steps within a scenario (e.g., disable memory
        retrieval during payment collection).

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario identifier (optional, used for lookup optimization)
            step_id: Step identifier

        Returns:
            Dictionary of step-specific config overrides, or None if no config exists

        Note:
            Step-level config is not currently stored in the database.
            This would require adding a `config_overrides` field to the
            `ScenarioStep` model and storing it in the `scenarios` table's
            `steps` JSONB column, or creating a separate `step_configs` table.
        """
        return None

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()

    def invalidate(
        self,
        tenant_id: UUID,
        agent_id: UUID | None = None,
    ) -> None:
        """Invalidate cached config for tenant/agent."""
        prefix = str(tenant_id)
        if agent_id:
            prefix = f"{prefix}:{agent_id}"

        keys_to_remove = [
            k for k in self._cache.keys()
            if k.startswith(prefix)
        ]
        for key in keys_to_remove:
            del self._cache[key]
