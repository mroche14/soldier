## Usage in Code

### Accessing Configuration

```python
from focal.config.settings import get_settings

# Get cached settings (loads once, reuses)
settings = get_settings()

# Access nested values
port = settings.api.port
generation_models = settings.pipeline.generation.models  # List of model strings
rule_strategy = settings.pipeline.retrieval.rule_selection.strategy

# Check environment
if settings.debug:
    print("Running in debug mode")
```

### Dependency Injection Pattern

```python
from fastapi import Depends

from focal.config.settings import Settings, get_settings
from focal.providers.litellm_provider import LiteLLMProvider


def get_generation_provider(settings: Settings = Depends(get_settings)):
    """Create LLM provider from pipeline step config."""
    return LiteLLMProvider.from_config(settings.pipeline.generation)


def get_filtering_provider(settings: Settings = Depends(get_settings)):
    """Create LLM provider for filtering step."""
    return LiteLLMProvider.from_config(settings.pipeline.llm_filtering)
```

### Creating Selection Strategies from Config

```python
from focal.config.models.selection import SelectionStrategyConfig
from focal.alignment.retrieval.selection import (
    SelectionStrategy,
    ElbowSelectionStrategy,
    AdaptiveKSelectionStrategy,
    EntropySelectionStrategy,
    ClusterSelectionStrategy,
    FixedKSelectionStrategy,
)


def create_selection_strategy(config: SelectionStrategyConfig) -> SelectionStrategy:
    """Factory function to create selection strategy from config."""

    match config.strategy:
        case "elbow":
            return ElbowSelectionStrategy(
                drop_threshold=config.drop_threshold,
                min_score=config.min_score,
            )
        case "adaptive_k":
            return AdaptiveKSelectionStrategy(
                alpha=config.alpha,
                min_score=config.min_score,
            )
        case "entropy":
            return EntropySelectionStrategy(
                low_entropy_k=config.low_entropy_k,
                medium_entropy_k=config.medium_entropy_k,
                high_entropy_k=config.high_entropy_k,
                min_score=config.min_score,
            )
        case "clustering":
            return ClusterSelectionStrategy(
                eps=config.eps,
                min_cluster_size=config.min_cluster_size,
                top_per_cluster=config.top_per_cluster,
                min_score=config.min_score,
            )
        case "fixed_k":
            return FixedKSelectionStrategy(
                k=config.k,
                min_score=config.min_score,
            )
        case _:
            raise ValueError(f"Unknown strategy: {config.strategy}")


# Usage
settings = get_settings()
rule_strategy = create_selection_strategy(settings.pipeline.retrieval.rule_selection)
memory_strategy = create_selection_strategy(settings.pipeline.retrieval.memory_selection)
```

---

## Configuration Validation

Pydantic validates all configuration at load time:

```python
from pydantic import ValidationError

try:
    settings = Settings.from_toml()
except ValidationError as e:
    print("Configuration error:")
    for error in e.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        print(f"  {loc}: {error['msg']}")
    raise SystemExit(1)
```

Example validation errors:

```
Configuration error:
  pipeline -> retrieval -> rule_selection -> alpha: Input should be greater than or equal to 0.5
  api -> port: Input should be less than or equal to 65535
  storage -> config -> backend: Input should be 'postgres', 'mongodb' or 'inmemory'
```

---

## Best Practices

### 1. No Hardcoded Values in Code

```python
# ❌ Bad: hardcoded values
class RuleRetriever:
    def __init__(self):
        self.top_k = 20
        self.min_score = 0.5

# ✅ Good: from config with defaults in Pydantic model
class RuleRetriever:
    def __init__(self, config: RetrievalConfig):
        self.top_k = config.max_k
        self.min_score = config.rule_selection.min_score
```

### 2. Secrets via Environment Variables

```toml
# ❌ Bad: secrets in TOML files
[providers.default_llm]
api_key = "sk-ant-..."

# ✅ Good: reference env var or leave empty
[providers.default_llm]
# api_key loaded from ANTHROPIC_API_KEY or FOCAL_PROVIDERS__DEFAULT_LLM__API_KEY
```

### 3. Environment-Specific Overrides Only

```toml
# default.toml: complete configuration
# development.toml: only differences from default
# production.toml: only differences from default
```

### 4. Validate Early

```python
# main.py
from focal.config.settings import get_settings

def main():
    # Validate config at startup, fail fast
    settings = get_settings()

    # Now safe to use settings throughout the application
    app = create_app(settings)
    app.run()
```

---

