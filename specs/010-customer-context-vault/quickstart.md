# Customer Context Vault - Quickstart Guide

Get up and running with the enhanced CustomerProfile system.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector
- Redis 6+
- Hatchet (for background jobs)

## Installation

```bash
# Add new dependency
uv add hatchet-sdk

# Run migrations
alembic upgrade head
```

## Configuration

Add to `config/default.toml`:

```toml
[profile]
cache_enabled = true
cache_ttl_seconds = 1800  # 30 minutes
validation_mode = "warn"  # strict, warn, disabled

[profile.field_definitions_ttl_seconds]
default = 3600  # 1 hour

[jobs.hatchet]
server_url = "http://localhost:7077"
# api_key loaded from HATCHET_API_KEY env var
cron_expire_fields = "*/5 * * * *"
cron_detect_orphans = "*/15 * * * *"
worker_concurrency = 10
```

## Basic Usage

### 1. Define Profile Field Schemas

```python
from focal.profile import ProfileFieldDefinition

# Create field definition for email
email_def = ProfileFieldDefinition(
    tenant_id=tenant_id,
    agent_id=agent_id,
    name="email",
    display_name="Email Address",
    value_type="email",
    validation_regex=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    is_pii=True,
    collection_prompt="What is your email address?",
)

await profile_store.save_field_definition(email_def)
```

### 2. Define Scenario Requirements

```python
from focal.profile import ScenarioFieldRequirement, RequiredLevel, FallbackAction

# Require email for onboarding scenario
requirement = ScenarioFieldRequirement(
    tenant_id=tenant_id,
    agent_id=agent_id,
    scenario_id=onboarding_scenario_id,
    field_name="email",
    required_level=RequiredLevel.HARD,
    fallback_action=FallbackAction.ASK,
)

await profile_store.save_scenario_requirement(requirement)
```

### 3. Save Profile Fields with Lineage

```python
from focal.profile import ProfileField, ItemStatus, SourceType

# Field extracted from uploaded document
extracted_name = ProfileField(
    name="legal_name",
    value="John Smith",
    value_type="string",
    source=ProfileFieldSource.TOOL,
    # Lineage tracking
    source_item_id=uploaded_doc_id,  # ID of ProfileAsset
    source_item_type=SourceType.PROFILE_ASSET,
    source_metadata={"tool": "ocr_extractor", "confidence": 0.95},
    # Status
    status=ItemStatus.ACTIVE,
)

await profile_store.update_field(profile_id, extracted_name)
```

### 4. Query Derivation Chain

```python
# Find where a field value came from
chain = await profile_store.get_derivation_chain(
    tenant_id=tenant_id,
    item_id=field_id,
    item_type="profile_field",
)

# chain = [
#   {"id": "<asset_id>", "type": "profile_asset", "name": "id_card"},
#   {"id": "<field_id>", "type": "profile_field", "name": "legal_name"},
# ]
```

### 5. Check Missing Fields for Scenario

```python
# Find fields needed before entering scenario
missing = await profile_store.get_missing_fields(
    tenant_id=tenant_id,
    profile=profile,
    scenario_id=scenario_id,
)

for req in missing:
    print(f"Missing: {req.field_name} (required_level={req.required_level})")
```

### 6. Use GapFillService with Schema

```python
from focal.alignment.migration import GapFillService

gap_fill = GapFillService(
    profile_store=profile_store,
    session_store=session_store,
    llm_executor=llm_executor,
    schema_validator=schema_validator,
)

# Fill missing fields using schema-defined collection prompts
results = await gap_fill.fill_scenario_requirements(
    tenant_id=tenant_id,
    profile=profile,
    scenario_id=scenario_id,
    session=session,
)

for result in results:
    if result.filled:
        print(f"Filled {result.field_name} from {result.source}")
    else:
        print(f"Could not fill {result.field_name}: {result.validation_errors}")
```

## Background Jobs

### Start Hatchet Worker

```bash
# In development
uv run python -m focal.jobs.worker

# In production
docker run focal-worker
```

### Manual Expiry (Admin)

```bash
# Trigger immediate field expiry check
curl -X POST http://localhost:8000/admin/profiles/expire-stale \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Caching

### Check Cache Status

```python
from focal.profile.stores import CachedProfileStore

cached_store = CachedProfileStore(
    backend=postgres_store,
    redis=redis_client,
    ttl=1800,
)

# Cache is transparent - just use the store
profile = await cached_store.get_by_customer_id(tenant_id, customer_id)

# Force cache invalidation
await cached_store.invalidate_profile(tenant_id, customer_id)
```

### Redis Failure Handling

The cache automatically falls back to PostgreSQL when Redis is unavailable:

```python
# This still works even if Redis is down
profile = await cached_store.get_by_customer_id(tenant_id, customer_id)
# Logged: "redis_unavailable, falling_back_to_backend"
```

## Validation Modes

```python
from focal.profile import SchemaValidationService, ValidationMode

# Strict: Reject invalid values (production)
strict_validator = SchemaValidationService(mode=ValidationMode.STRICT)

# Warn: Log warnings but accept (migration period)
warn_validator = SchemaValidationService(mode=ValidationMode.WARN)

# Disabled: Skip validation (development)
dev_validator = SchemaValidationService(mode=ValidationMode.DISABLED)
```

## ProfileItemSchemaExtraction

### Automatic Extraction

Extraction runs automatically when scenarios/rules are created or updated:

```python
# This triggers extraction via Hatchet background job
await config_store.save_scenario(new_scenario)
# Background: ProfileItemSchemaExtractor analyzes conditions
# Background: ScenarioFieldRequirements are generated
```

### Manual Extraction

```python
from focal.profile import ProfileItemSchemaExtractor

extractor = ProfileItemSchemaExtractor(
    llm_executor=llm_executor,
    config_store=config_store,
    profile_store=profile_store,
)

# Extract requirements from scenario
requirements = await extractor.extract_requirements(scenario)

for req in requirements:
    if req.needs_human_review:
        print(f"Low confidence for {req.field_name}: review needed")
    await profile_store.save_scenario_requirement(req)
```

## Testing

```bash
# Run unit tests
uv run pytest tests/unit/profile/ -v

# Run contract tests
uv run pytest tests/contract/test_profile_store_contract.py -v

# Run integration tests (requires Docker)
docker compose up -d postgres redis hatchet
uv run pytest tests/integration/stores/test_postgres_profile.py -v

# Run performance tests
uv run pytest tests/performance/test_profile_performance.py -v --benchmark-json=benchmarks/profile.json
```

## Troubleshooting

### "Field validation failed"
Check that the value matches the `ProfileFieldDefinition.validation_regex` and `value_type`.

### "Cannot delete: has dependents"
The field/asset has derived items. Use `get_derived_items()` to find them, or use `force_delete=True` (admin only).

### "Cache hit rate below 80%"
Check Redis connectivity and ensure profile access patterns are consistent (same tenant/customer IDs).

### "Hatchet workflow failed"
Check Hatchet worker logs. Workflows are idempotent - safe to retry manually.
