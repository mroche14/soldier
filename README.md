# Soldier

Production-grade cognitive engine for conversational AI.

## Overview

Soldier is an API-first, multi-tenant, fully persistent architecture designed for horizontal scaling of conversational AI agents.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- uv package manager

### Installation

```bash
# Install dependencies
uv sync

# Install dev dependencies
uv sync --dev
```

### Verify Installation

```bash
# Check that the package is importable
uv run python -c "from soldier.config import get_settings; print('OK')"

# Run tests
uv run pytest
```

## Configuration

Configuration is loaded from TOML files in the `config/` directory:

```
config/
├── default.toml      # Base defaults
├── development.toml  # Development overrides
├── staging.toml      # Staging overrides
├── production.toml   # Production overrides
└── test.toml         # Test configuration
```

Set the environment via `SOLDIER_ENV`:

```bash
export SOLDIER_ENV=development  # or production, staging, test
```

Override any setting via environment variables with `SOLDIER_` prefix:

```bash
export SOLDIER_DEBUG=true
export SOLDIER_API__PORT=9000
```

## Development

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Lint
make lint

# Type check
make typecheck

# Format code
make format
```

## License

MIT
