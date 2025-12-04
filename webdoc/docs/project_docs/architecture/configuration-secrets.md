## Secrets Management

API keys and credentials require special handling. **Never commit secrets to TOML files.**

### Secret Resolution Order

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECRET RESOLUTION ORDER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Secret Manager (Production)                                  │
│     AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager    │
│     ↓ (if not found)                                            │
│                                                                  │
│  2. Environment Variables (Standard names)                       │
│     ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.                     │
│     ↓ (if not found)                                            │
│                                                                  │
│  3. Environment Variables (Soldier-prefixed)                     │
│     SOLDIER_PIPELINE__GENERATION__MODELS, etc.                  │
│     ↓ (if not found)                                            │
│                                                                  │
│  4. .env.local file (Development only, gitignored)              │
│     ↓ (if not found)                                            │
│                                                                  │
│  5. Error: Secret not configured                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Standard Environment Variable Names

Each provider type has conventional env var names that are auto-resolved by LiteLLM:

| Provider | Environment Variable | Notes |
|----------|---------------------|-------|
| **OpenRouter** | `OPENROUTER_API_KEY` | **Primary** - aggregates all providers with failover |
| **Anthropic** | `ANTHROPIC_API_KEY` | Claude models (direct) |
| **OpenAI** | `OPENAI_API_KEY` | GPT, Whisper, DALL-E, Embeddings, TTS |
| **Google** | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Gemini models |
| **Cohere** | `COHERE_API_KEY` | Embeddings, Rerank |
| **Voyage** | `VOYAGE_API_KEY` | Embeddings, Rerank |
| **Jina** | `JINA_API_KEY` | Rerank |
| **Deepgram** | `DEEPGRAM_API_KEY` | Speech-to-text |
| **AssemblyAI** | `ASSEMBLYAI_API_KEY` | Speech-to-text |
| **ElevenLabs** | `ELEVENLABS_API_KEY` | Text-to-speech |
| **Stability** | `STABILITY_API_KEY` | Image generation |
| **Replicate** | `REPLICATE_API_TOKEN` | Various models |
| **AWS** | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Bedrock, Polly, etc. |
| **Google Cloud** | `GOOGLE_APPLICATION_CREDENTIALS` | Vertex AI (service account) |
| **Azure** | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | Azure OpenAI |

**Recommended setup:**
1. Get an OpenRouter API key (primary, covers most models)
2. Add direct Anthropic + OpenAI keys (fallbacks for when OpenRouter is down)
3. Add specialty provider keys as needed (Deepgram for STT, ElevenLabs for TTS, etc.)

### Pydantic Secret Resolution

```python
# soldier/config/models/providers.py
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: str = "anthropic"
    model: str = "claude-3-haiku-20240307"

    # API key resolution:
    # 1. If set explicitly, use that value
    # 2. Otherwise, resolve from standard env var based on provider
    api_key: SecretStr | None = Field(
        default=None,
        description="API key. If None, resolved from env (e.g., ANTHROPIC_API_KEY)"
    )

    def get_api_key(self) -> str:
        """
        Resolve API key with fallback to standard env vars.

        Resolution order:
        1. Explicit api_key in config
        2. Standard env var for provider (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
        3. Raise error
        """
        import os

        # 1. Explicit config
        if self.api_key:
            return self.api_key.get_secret_value()

        # 2. Standard env var based on provider
        env_var_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "cohere": "COHERE_API_KEY",
            "voyage": "VOYAGE_API_KEY",
            "bedrock": None,  # Uses AWS credentials
            "vertex": None,   # Uses GCP credentials
        }

        env_var = env_var_map.get(self.provider)
        if env_var:
            value = os.getenv(env_var)
            if value:
                return value

        # 3. Error
        if env_var:
            raise ValueError(
                f"API key for {self.provider} not found. "
                f"Set {env_var} environment variable or providers.*.api_key in config."
            )
        else:
            # Provider uses implicit auth (AWS/GCP)
            return ""
```

### TOML Configuration (No Secrets)

TOML files should **never** contain actual secrets:

```toml
# config/default.toml
# ✅ CORRECT: No API keys in TOML

# Models are configured per step - API keys resolved from environment
[pipeline.generation]
models = [
    "openrouter/anthropic/claude-sonnet-4-5-20250514",  # Uses OPENROUTER_API_KEY
    "anthropic/claude-sonnet-4-5-20250514",            # Uses ANTHROPIC_API_KEY
    "openai/gpt-4o",                                   # Uses OPENAI_API_KEY
]
# LiteLLM automatically resolves API keys from standard env vars

[storage.config.postgres]
host = "localhost"
port = 5432
database = "soldier"
user = "soldier"
# password intentionally omitted - resolved from env var
```

```toml
# ❌ WRONG: Never embed secrets in TOML
# There's no place to put API keys anyway - models are just strings
# and LiteLLM handles auth via environment variables
```

### Development: Root .env File

For local development, use a single `.env` file at the **project root** (gitignored):

```
soldier/
├── .env                    # ← Secrets here (gitignored, NEVER commit)
├── .env.example            # ← Template without values (committed)
├── config/
│   ├── default.toml        # Non-secret config (committed)
│   └── development.toml    # Dev overrides (committed)
├── soldier/
│   └── ...
└── ...
```

**.env file (gitignored):**

```bash
# .env (NEVER commit this file)
# Copy from .env.example and fill in your values

# =============================================================================
# AI PROVIDERS - Primary (OpenRouter for aggregated access)
# =============================================================================

# OpenRouter (RECOMMENDED - single key for all providers with built-in failover)
# Get your key at https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# =============================================================================
# AI PROVIDERS - Direct APIs (fallbacks when OpenRouter is unavailable)
# =============================================================================

# Anthropic (Claude) - https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# OpenAI (GPT, Whisper, DALL-E, Embeddings, TTS) - https://platform.openai.com/
OPENAI_API_KEY=sk-xxxxx

# Google AI (Gemini) - https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=xxxxx

# =============================================================================
# AI PROVIDERS - Optional (for specific features)
# =============================================================================

# Cohere (Embeddings, Rerank) - https://dashboard.cohere.com/
COHERE_API_KEY=xxxxx

# Voyage (Embeddings, Rerank) - https://www.voyageai.com/
VOYAGE_API_KEY=xxxxx

# Deepgram (Speech-to-text) - https://console.deepgram.com/
DEEPGRAM_API_KEY=xxxxx

# AssemblyAI (Speech-to-text) - https://www.assemblyai.com/
ASSEMBLYAI_API_KEY=xxxxx

# ElevenLabs (Text-to-speech) - https://elevenlabs.io/
ELEVENLABS_API_KEY=xxxxx

# Stability (Image generation) - https://platform.stability.ai/
STABILITY_API_KEY=xxxxx

# Jina (Rerank) - https://jina.ai/
JINA_API_KEY=xxxxx

# =============================================================================
# DATABASES (local development)
# =============================================================================

SOLDIER_STORAGE__CONFIG__POSTGRES__PASSWORD=local_dev_password
SOLDIER_STORAGE__CONVERSATION__REDIS__PASSWORD=

# =============================================================================
# OPTIONAL OVERRIDES
# =============================================================================

# Override environment
SOLDIER_ENV=development

# Disable fallbacks for debugging (use only primary model)
# SOLDIER_PROVIDERS__LLM__QUALITY__FALLBACK_ON_ERROR=false
```

**.env.example file (committed as template):**

```bash
# .env.example - Copy to .env and fill in your values
# cp .env.example .env

# =============================================================================
# REQUIRED: At least OpenRouter OR direct provider keys
# =============================================================================

# Option 1: OpenRouter (RECOMMENDED - single key, built-in failover)
OPENROUTER_API_KEY=

# Option 2: Direct provider keys (used as fallbacks or standalone)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# =============================================================================
# OPTIONAL: Additional providers for specific features
# =============================================================================

# Embeddings & Rerank
COHERE_API_KEY=
VOYAGE_API_KEY=
JINA_API_KEY=

# Speech-to-Text
DEEPGRAM_API_KEY=
ASSEMBLYAI_API_KEY=

# Text-to-Speech
ELEVENLABS_API_KEY=

# Image Generation
STABILITY_API_KEY=

# =============================================================================
# DATABASES (local development)
# =============================================================================

SOLDIER_STORAGE__CONFIG__POSTGRES__PASSWORD=
SOLDIER_STORAGE__CONVERSATION__REDIS__PASSWORD=
```

**.gitignore entries:**

```gitignore
# Environment files with secrets
.env
.env.local
.env.*.local
*.env

# Keep the example template
!.env.example
```

### Loading .env at Startup

The `.env` file is loaded automatically at application startup:

```python
# soldier/config/loader.py
import os
from pathlib import Path

from dotenv import load_dotenv


def load_env_files():
    """
    Load environment files from project root.

    Resolution order (later overrides earlier):
    1. .env                    - Base secrets (gitignored)
    2. .env.{environment}      - Environment-specific (e.g., .env.test)
    3. .env.local              - Personal overrides (gitignored)
    """
    # Find project root (where .env lives)
    project_root = _find_project_root()

    env_files = [
        project_root / ".env",
        project_root / f".env.{get_environment()}",
        project_root / ".env.local",
    ]

    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file, override=True)


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git."""
    current = Path.cwd()

    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
        if (parent / ".git").exists():
            return parent

    return current


# Auto-load on import
load_env_files()
```

### Usage in Development

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Fill in your API keys
nano .env  # or use your preferred editor

# 3. Run the application (env vars are auto-loaded)
python -m soldier.api

# Or run tests
pytest
```

### IDE Integration

Most IDEs auto-detect `.env` at project root:

**VS Code** - Install "Python" extension, it auto-loads `.env`

**PyCharm** - Enable "EnvFile" plugin or set in Run Configuration:
- Run → Edit Configurations → Environment variables → Load from `.env`

**direnv** (shell-level):
```bash
# .envrc
dotenv
```

### Production: Secret Manager Integration

For production, integrate with a secret manager:

```python
# soldier/config/secrets.py
from abc import ABC, abstractmethod
from functools import lru_cache
import os


class SecretProvider(ABC):
    """Interface for secret providers."""

    @abstractmethod
    def get_secret(self, name: str) -> str | None:
        """Get a secret by name."""
        pass


class EnvSecretProvider(SecretProvider):
    """Get secrets from environment variables."""

    def get_secret(self, name: str) -> str | None:
        return os.getenv(name)


class AWSSecretsManagerProvider(SecretProvider):
    """Get secrets from AWS Secrets Manager."""

    def __init__(self, secret_prefix: str = "soldier/"):
        import boto3
        self.client = boto3.client("secretsmanager")
        self.prefix = secret_prefix

    def get_secret(self, name: str) -> str | None:
        try:
            response = self.client.get_secret_value(
                SecretId=f"{self.prefix}{name}"
            )
            return response["SecretString"]
        except self.client.exceptions.ResourceNotFoundException:
            return None


class VaultSecretProvider(SecretProvider):
    """Get secrets from HashiCorp Vault."""

    def __init__(self, vault_addr: str, vault_token: str, mount_point: str = "secret"):
        import hvac
        self.client = hvac.Client(url=vault_addr, token=vault_token)
        self.mount_point = mount_point

    def get_secret(self, name: str) -> str | None:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=name,
                mount_point=self.mount_point,
            )
            return response["data"]["data"].get("value")
        except Exception:
            return None


class ChainedSecretProvider(SecretProvider):
    """Try multiple providers in order."""

    def __init__(self, providers: list[SecretProvider]):
        self.providers = providers

    def get_secret(self, name: str) -> str | None:
        for provider in self.providers:
            value = provider.get_secret(name)
            if value is not None:
                return value
        return None


@lru_cache
def get_secret_provider() -> SecretProvider:
    """Get configured secret provider."""
    secret_backend = os.getenv("SOLDIER_SECRET_BACKEND", "env")

    if secret_backend == "env":
        return EnvSecretProvider()

    elif secret_backend == "aws":
        return ChainedSecretProvider([
            AWSSecretsManagerProvider(),
            EnvSecretProvider(),  # Fallback
        ])

    elif secret_backend == "vault":
        return ChainedSecretProvider([
            VaultSecretProvider(
                vault_addr=os.environ["VAULT_ADDR"],
                vault_token=os.environ["VAULT_TOKEN"],
            ),
            EnvSecretProvider(),  # Fallback
        ])

    else:
        return EnvSecretProvider()


def get_secret(name: str) -> str | None:
    """Get a secret by name using configured provider."""
    return get_secret_provider().get_secret(name)
```

### Kubernetes Secrets

For Kubernetes deployments, use secrets mounted as env vars:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: soldier
spec:
  template:
    spec:
      containers:
        - name: soldier
          image: soldier:latest
          envFrom:
            # Load all keys from secret as env vars
            - secretRef:
                name: soldier-api-keys
            - secretRef:
                name: soldier-db-credentials
          env:
            # Or load specific keys
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: soldier-api-keys
                  key: anthropic-api-key
```

```yaml
# k8s/secrets.yaml (apply separately, never commit actual values)
apiVersion: v1
kind: Secret
metadata:
  name: soldier-api-keys
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"  # Replaced by CI/CD
  OPENAI_API_KEY: "${OPENAI_API_KEY}"
  COHERE_API_KEY: "${COHERE_API_KEY}"
```

### Docker Compose (Development)

```yaml
# docker-compose.yml
services:
  soldier:
    image: soldier:latest
    env_file:
      - .env.local  # Gitignored file with secrets
    environment:
      - SOLDIER_ENV=development
      # Non-secret overrides
      - SOLDIER_API__PORT=8000
```

### Secret Rotation

For production, implement secret rotation:

```python
# soldier/config/secrets.py

class RotatingSecretProvider(SecretProvider):
    """
    Caches secrets with TTL for rotation support.

    Secrets are re-fetched after TTL expires, allowing
    rotation without restart.
    """

    def __init__(
        self,
        provider: SecretProvider,
        ttl_seconds: int = 300,  # 5 minutes
    ):
        self.provider = provider
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[str, float]] = {}

    def get_secret(self, name: str) -> str | None:
        import time

        now = time.time()

        # Check cache
        if name in self._cache:
            value, expires_at = self._cache[name]
            if now < expires_at:
                return value

        # Fetch fresh
        value = self.provider.get_secret(name)
        if value is not None:
            self._cache[name] = (value, now + self.ttl_seconds)

        return value

    def invalidate(self, name: str | None = None):
        """Invalidate cache for rotation."""
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()
```

### Summary: Best Practices

| Environment | Secret Storage | Loaded Via |
|-------------|---------------|------------|
| **Development** | `.env` at project root | python-dotenv (auto-loaded) |
| **CI/CD** | GitHub Secrets / GitLab CI Variables | Env vars in runner |
| **Staging** | AWS Secrets Manager / Vault | SDK + env fallback |
| **Production** | AWS Secrets Manager / Vault / K8s Secrets | SDK + env fallback |

**File Structure:**
```
soldier/
├── .env                 # Secrets (gitignored)
├── .env.example         # Template (committed)
├── config/
│   ├── default.toml     # Base config (committed, no secrets)
│   ├── development.toml # Dev overrides (committed)
│   └── production.toml  # Prod overrides (committed)
└── ...
```

**Rules:**
1. ✅ Use standard env var names (`ANTHROPIC_API_KEY`, not custom names)
2. ✅ Keep `.env` at project root for development
3. ✅ Commit `.env.example` as a template
4. ✅ Keep TOML files secret-free (safe to commit)
5. ✅ Use `SecretStr` in Pydantic (prevents logging)
6. ✅ Use secret manager in production
7. ❌ Never commit `.env` (add to `.gitignore`)
8. ❌ Never log or print API keys

---

## Environment Variable Overrides

Environment variables override TOML values using nested delimiter (`__`):

```bash
# Override API port
export SOLDIER_API__PORT=9000

# Override generation models (JSON array)
export SOLDIER_PIPELINE__GENERATION__MODELS='["anthropic/claude-3-haiku", "openai/gpt-4o-mini"]'

# Override storage credentials (secrets)
export SOLDIER_STORAGE__CONFIG__POSTGRES__PASSWORD=secret123
export SOLDIER_STORAGE__MEMORY__NEO4J__PASSWORD=secret456

# Override selection strategy
export SOLDIER_PIPELINE__RETRIEVAL__RULE_SELECTION__STRATEGY=entropy
export SOLDIER_PIPELINE__RETRIEVAL__RULE_SELECTION__LOW_ENTROPY_K=5

# Override generation timeout
export SOLDIER_PIPELINE__GENERATION__TIMEOUT_SECONDS=120
```

---

