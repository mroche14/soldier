# Configuration Hierarchy

> **Topic**: Multi-level configuration from tenant down to step
> **Dependencies**: None (foundational)
> **Impacts**: All brain behavior, per-agent customization

---

## Overview

The **Configuration Hierarchy** enables tenant-specific customization without code changes. Each level can override the previous:

```
tenant defaults → agent overrides → scenario overrides → step overrides
```

### The Problem

Without hierarchy:
- Every agent uses same models, temperatures, timeouts
- Changing one agent's behavior requires code changes
- No way for tenants to customize their agents

### The Solution

Layered configuration that merges at runtime:

```python
# Final config = merge(tenant, agent, scenario, step)
final_model = step.model or scenario.model or agent.model or tenant.model or "claude-3-haiku"
```

---

## Configuration Levels

### Level 1: System Defaults (Code)

Pydantic model defaults - the absolute fallback:

```python
class PipelineConfig(BaseModel):
    """System defaults for brain behavior."""

    # Generation
    generation_model: str = "claude-3-haiku"
    generation_temperature: float = 0.7
    generation_max_tokens: int = 1024

    # Retrieval
    retrieval_top_k: int = 20
    rerank_top_k: int = 5

    # Timeouts
    llm_timeout_seconds: float = 30.0
    tool_timeout_seconds: float = 60.0

    # LogicalTurn (new)
    accumulation_window_ms: int = 800
    max_accumulation_window_ms: int = 3000
```

### Level 2: Environment Defaults (TOML)

`config/default.toml` - committed to repo:

```toml
[brain]
generation_model = "claude-3-haiku"
generation_temperature = 0.7

[brain.retrieval]
top_k = 20
rerank_top_k = 5

[brain.logical_turn]
accumulation_window_ms = 800
```

### Level 3: Environment Overrides (TOML)

`config/production.toml` - environment-specific:

```toml
[brain]
generation_model = "claude-3-sonnet"  # Better model in prod
llm_timeout_seconds = 45.0           # More tolerance in prod
```

### Level 4: Tenant Defaults (Database)

Stored in ConfigStore, loaded in P1.6:

```python
class TenantConfig(BaseModel):
    """Tenant-level configuration overrides."""

    tenant_id: UUID

    # Can override any brain setting
    generation_model: str | None = None
    generation_temperature: float | None = None

    # Tenant-specific features
    features_enabled: list[str] = []  # e.g., ["agenda", "multi_channel"]

    # Limits
    max_tools_per_turn: int = 5
    max_scenarios_active: int = 3
```

### Level 5: Agent Overrides (Database)

Per-agent customization:

```python
class AgentConfig(BaseModel):
    """Agent-level configuration overrides."""

    agent_id: UUID
    tenant_id: UUID

    # Model preferences for this agent
    generation_model: str | None = None
    generation_temperature: float | None = None

    # Agent personality
    system_prompt_additions: str | None = None

    # Behavior
    accumulation_window_ms: int | None = None  # Channel-like behavior
    confirmation_required_for_irreversible: bool = True

    # Feature flags
    abuse_detection_enabled: bool = True
    proactive_goals_enabled: bool = False
```

### Level 6: Scenario Overrides (Database)

Per-scenario fine-tuning (use sparingly):

```python
class ScenarioConfig(BaseModel):
    """Scenario-level configuration overrides."""

    scenario_id: UUID
    agent_id: UUID
    tenant_id: UUID

    # Scenario-specific model (rare)
    generation_model: str | None = None

    # Scenario behavior
    max_turns_in_scenario: int | None = None
    timeout_after_hours: float | None = None
```

### Level 7: Step Overrides (Inline)

Already exists in ScenarioStep:

```python
class ScenarioStep(BaseModel):
    # ... existing fields ...

    # Step-level overrides (already supported)
    model_override: str | None = None
    temperature_override: float | None = None
    max_tokens_override: int | None = None
```

---

## Configuration Resolution

```python
class ConfigResolver:
    """Resolves final configuration from all levels."""

    def __init__(
        self,
        system_defaults: PipelineConfig,
        toml_config: dict,
        config_store: ConfigStore,
    ):
        self._system = system_defaults
        self._toml = toml_config
        self._store = config_store

    async def resolve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        scenario_id: UUID | None = None,
        step_id: UUID | None = None,
    ) -> ResolvedConfig:
        """
        Resolve configuration through all levels.

        Order: system → toml → tenant → agent → scenario → step
        Later levels override earlier ones.
        """

        # Start with system defaults
        config = self._system.model_dump()

        # Apply TOML (default.toml + {env}.toml)
        config = self._deep_merge(config, self._toml)

        # Load and apply tenant config
        tenant_config = await self._store.get_tenant_config(tenant_id)
        if tenant_config:
            config = self._apply_overrides(config, tenant_config)

        # Load and apply agent config
        agent_config = await self._store.get_agent_config(tenant_id, agent_id)
        if agent_config:
            config = self._apply_overrides(config, agent_config)

        # Load and apply scenario config (if in scenario)
        if scenario_id:
            scenario_config = await self._store.get_scenario_config(
                tenant_id, scenario_id
            )
            if scenario_config:
                config = self._apply_overrides(config, scenario_config)

        # Step overrides applied at execution time (not here)

        return ResolvedConfig(**config)

    def _apply_overrides(self, base: dict, overrides: BaseModel) -> dict:
        """Apply non-None overrides to base config."""
        for key, value in overrides.model_dump().items():
            if value is not None and key in base:
                base[key] = value
        return base

    def _deep_merge(self, base: dict, overlay: dict) -> dict:
        """Recursively merge overlay into base."""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
```

---

## Integration with P1.6

```python
# In AlignmentEngine, during Phase 1.6

async def _load_config(self, turn_context: TurnContext) -> ResolvedConfig:
    """Load and resolve configuration for this turn."""

    config = await self._config_resolver.resolve(
        tenant_id=turn_context.tenant_id,
        agent_id=turn_context.agent_id,
        scenario_id=turn_context.active_scenario_id,
    )

    # Attach to context for use by all phases
    turn_context.resolved_config = config

    logger.info(
        "config_resolved",
        tenant_id=str(turn_context.tenant_id),
        agent_id=str(turn_context.agent_id),
        generation_model=config.generation_model,
        source_chain=config.resolution_chain,  # ["system", "toml", "agent"]
    )

    return config
```

---

## Configuration Caching

Avoid database hits on every turn:

```python
class CachedConfigStore:
    """Config store with TTL-based caching."""

    def __init__(
        self,
        store: ConfigStore,
        cache: Redis,
        ttl_seconds: int = 300,
    ):
        self._store = store
        self._cache = cache
        self._ttl = ttl_seconds

    async def get_agent_config(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentConfig | None:
        cache_key = f"config:agent:{tenant_id}:{agent_id}"

        # Try cache
        cached = await self._cache.get(cache_key)
        if cached:
            return AgentConfig.model_validate_json(cached)

        # Load from store
        config = await self._store.get_agent_config(tenant_id, agent_id)
        if config:
            await self._cache.setex(
                cache_key,
                self._ttl,
                config.model_dump_json(),
            )

        return config

    async def invalidate_agent_config(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Invalidate cache when config changes."""
        cache_key = f"config:agent:{tenant_id}:{agent_id}"
        await self._cache.delete(cache_key)
```

---

## Hot Reload (Future)

When config changes, invalidate caches:

```python
# Redis pub/sub for config changes
async def on_config_updated(event: ConfigUpdatedEvent):
    """Handle config update event."""

    if event.config_type == "agent":
        await cached_store.invalidate_agent_config(
            event.tenant_id,
            event.agent_id,
        )

    # Note: In-flight turns continue with old config
    # New turns pick up new config
```

---

## What Can Be Configured

### Per-Tenant

| Setting | Description | Default |
|---------|-------------|---------|
| `generation_model` | Default model for generation | claude-3-haiku |
| `max_tools_per_turn` | Limit tools executed | 5 |
| `features_enabled` | Feature flags | [] |

### Per-Agent

| Setting | Description | Default |
|---------|-------------|---------|
| `generation_model` | Model for this agent | (tenant) |
| `generation_temperature` | Creativity level | 0.7 |
| `accumulation_window_ms` | Turn accumulation time | 800 |
| `abuse_detection_enabled` | Enable abuse checks | true |
| `proactive_goals_enabled` | Enable agenda/goals | false |

### Per-Scenario

| Setting | Description | Default |
|---------|-------------|---------|
| `max_turns_in_scenario` | Timeout by turn count | null |
| `timeout_after_hours` | Timeout by time | null |

---

## Observability

### Logging Resolution Chain

```python
logger.info(
    "config_resolved",
    tenant_id=str(tenant_id),
    agent_id=str(agent_id),
    final_model=config.generation_model,
    resolution_chain=["system", "toml:production", "tenant", "agent"],
    overrides_applied={
        "generation_model": "agent",  # Which level set this
        "temperature": "tenant",
    },
)
```

### Metrics

```python
config_resolution_duration = Histogram(
    "config_resolution_duration_seconds",
    "Time to resolve configuration",
)

config_cache_hit_rate = Gauge(
    "config_cache_hit_rate",
    "Cache hit rate for config lookups",
    ["config_type"],
)
```

---

## Testing

```python
# Test: Agent config overrides tenant
async def test_agent_overrides_tenant():
    tenant_config = TenantConfig(
        tenant_id=tenant_id,
        generation_model="claude-3-haiku",
    )
    agent_config = AgentConfig(
        agent_id=agent_id,
        tenant_id=tenant_id,
        generation_model="claude-3-sonnet",  # Override
    )

    resolved = await resolver.resolve(tenant_id, agent_id)

    assert resolved.generation_model == "claude-3-sonnet"

# Test: None values don't override
async def test_none_doesnt_override():
    tenant_config = TenantConfig(
        tenant_id=tenant_id,
        generation_model="claude-3-haiku",
    )
    agent_config = AgentConfig(
        agent_id=agent_id,
        tenant_id=tenant_id,
        generation_model=None,  # No override
    )

    resolved = await resolver.resolve(tenant_id, agent_id)

    assert resolved.generation_model == "claude-3-haiku"  # From tenant
```

---

## Related Topics

- [01-logical-turn.md](01-logical-turn.md) - Accumulation window is configurable
- [04-side-effect-policy.md](04-side-effect-policy.md) - Confirmation requirements configurable
- [09-agenda.md](09-agenda.md) - Enabled via feature flags
