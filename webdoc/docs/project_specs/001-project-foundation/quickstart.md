# Quickstart: Project Foundation & Configuration System

**Date**: 2025-11-28
**Feature**: 001-project-foundation

## Prerequisites

- Python 3.11 or higher
- uv package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

## Initial Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd focal

# Install dependencies
uv sync

# Install dev dependencies
uv sync --dev
```

### 2. Verify Installation

```bash
# Check that the package is importable
uv run python -c "from focal.config import get_settings; print('OK')"

# Run tests
uv run pytest
```

## Configuration

### Environment Selection

Set the environment via `FOCAL_ENV`:

```bash
# Development (default)
export FOCAL_ENV=development

# Production
export FOCAL_ENV=production

# Test
export FOCAL_ENV=test
```

### Configuration Files

Configuration lives in `config/`:

```
config/
├── default.toml      # Base defaults (always loaded)
├── development.toml  # Development overrides
├── staging.toml      # Staging overrides
├── production.toml   # Production overrides
└── test.toml         # Test overrides (in-memory backends)
```

### Basic Configuration Example

```toml
# config/default.toml

[api]
host = "0.0.0.0"
port = 8000
workers = 4

[api.rate_limit]
enabled = true
requests_per_minute = 60

[storage.config]
backend = "postgres"

[storage.session]
backend = "redis"

[providers.llm.haiku]
provider = "anthropic"
model = "claude-3-haiku-20240307"

[providers.llm.sonnet]
provider = "anthropic"
model = "claude-sonnet-4-5-20250514"

[pipeline.generation]
llm_provider = "sonnet"
temperature = 0.7
```

### Environment Variable Overrides

Override any setting via environment variables:

```bash
# Format: FOCAL_{SECTION}__{KEY}
export FOCAL_API__PORT=9000
export FOCAL_DEBUG=true
export FOCAL_STORAGE__SESSION__BACKEND=redis
```

### Secrets

Store secrets in `.env` (never commit this file):

```bash
# Copy the template
cp .env.example .env

# Edit with your API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Using Configuration in Code

### Access Settings

```python
from focal.config import get_settings

# Get the singleton settings instance
settings = get_settings()

# Access values with full type safety
port = settings.api.port  # int
debug = settings.debug    # bool

# Access nested configuration
llm_config = settings.providers.llm.get("haiku")
if llm_config:
    model = llm_config.model
```

### Dependency Injection Pattern

```python
from focal.config import get_settings
from focal.config.models.pipeline import GenerationConfig

def create_generator(config: GenerationConfig):
    """Create a generator with injected configuration."""
    # Use config.llm_provider, config.temperature, etc.
    pass

# Usage
settings = get_settings()
generator = create_generator(settings.pipeline.generation)
```

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=focal --cov-report=html

# Run specific test file
uv run pytest tests/unit/config/test_loader.py

# Run tests in watch mode (with pytest-watch)
uv run ptw
```

### Code Quality

```bash
# Lint with ruff
uv run ruff check focal/ tests/

# Format with ruff
uv run ruff format focal/ tests/

# Type check with mypy
uv run mypy focal/
```

### Common Make Commands

```bash
make install    # Install dependencies
make test       # Run tests
make lint       # Run linting
make format     # Format code
make typecheck  # Run type checking
make all        # Run all checks
```

## Project Structure

```
focal/
├── config/              # TOML configuration files
├── focal/             # Main Python package
│   ├── alignment/       # Alignment engine
│   ├── memory/          # Long-term memory
│   ├── conversation/    # Session state
│   ├── audit/           # Audit logging
│   ├── observability/   # Logging, tracing
│   ├── providers/       # AI providers
│   ├── api/             # HTTP API
│   ├── config/          # Configuration loading
│   └── profile/         # Customer profiles
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── e2e/             # End-to-end tests
└── deploy/              # Deployment config
```

## Troubleshooting

### Configuration Not Loading

1. Check `FOCAL_ENV` is set correctly
2. Verify TOML syntax: `uv run python -c "import tomllib; tomllib.load(open('config/default.toml', 'rb'))"`
3. Check for validation errors in startup logs

### Import Errors

1. Ensure `uv sync` completed successfully
2. Check you're using the correct Python version: `python --version`
3. Verify the package is installed: `uv run pip list | grep focal`

### Environment Variables Not Applied

1. Verify prefix is `FOCAL_` (uppercase)
2. Use `__` for nesting (double underscore)
3. Check spelling matches configuration keys exactly

## Next Steps

After setup is complete:

1. **Phase 2**: Implement observability (logging, tracing, metrics)
2. **Phase 3**: Define domain models (rules, scenarios, sessions)
3. **Phase 4**: Implement store interfaces with in-memory backends
