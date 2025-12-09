# Customer Context Vault - Research Notes

Phase 0 research output for technical decisions and best practices.

---

## 1. Background Job Framework: Hatchet

### Decision
Use **Hatchet** for background job orchestration instead of Celery, rq, or similar.

### Rationale
1. **PostgreSQL-native**: Uses PostgreSQL as the queue backend, avoiding Redis dependency for job state (we already have PostgreSQL)
2. **Async Python support**: Native async/await support aligns with Focal's "Async Everywhere" constitution requirement
3. **Cron scheduling**: Built-in cron support for scheduled jobs (field expiry, orphan detection)
4. **Pydantic integration**: Works with Pydantic models for job inputs/outputs
5. **Horizontal scaling**: Workers can be deployed independently, no leader election issues
6. **MIT licensed**: Open source, self-hostable
7. **Retries & timeouts**: Built-in retry policies with exponential backoff

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| **Celery** | Redis-dependent for broker, complex configuration, overkill for our use case |
| **rq (Redis Queue)** | Adds Redis dependency for job state, not just caching |
| **APScheduler** | In-memory by default, not distributed, no PostgreSQL backend |
| **Dramatiq** | Less mature, smaller community |
| **Temporal** | Overkill for simple cron jobs, complex setup |

### Integration Pattern
```python
# focal/jobs/client.py
from hatchet_sdk import Hatchet

class HatchetClient:
    def __init__(self, config: HatchetConfig):
        self._hatchet = Hatchet(
            server_url=config.server_url,
            api_key=config.api_key.get_secret_value() if config.api_key else None,
        )

    def get_client(self) -> Hatchet:
        return self._hatchet

    async def health_check(self) -> bool:
        try:
            # Simple connectivity check
            return True
        except Exception:
            return False
```

### Graceful Degradation
When Hatchet is unavailable:
1. API continues serving requests (non-blocking)
2. Job submissions are logged and queued locally
3. Manual endpoint available for triggering expiry (`POST /admin/profiles/expire-stale`)

### References
- Hatchet Docs: https://docs.hatchet.run/
- GitHub: https://github.com/hatchet-dev/hatchet
- Python SDK: https://pypi.org/project/hatchet-sdk/

---

## 2. Lineage Traversal Strategy

### Decision
Use **recursive CTEs** in PostgreSQL for derivation chain traversal.

### Rationale
1. **Efficient**: Single query instead of N+1 queries for chain traversal
2. **Depth limiting**: Built-in `LIMIT` support prevents runaway recursion
3. **Cycle detection**: PostgreSQL's `CYCLE` clause prevents infinite loops
4. **Native**: No application-level recursion needed

### Implementation
```sql
WITH RECURSIVE derivation_chain AS (
    -- Base case: start from target item
    SELECT
        id, source_item_id, source_item_type, 0 AS depth
    FROM profile_fields
    WHERE id = :target_id

    UNION ALL

    -- Recursive case: follow source_item_id
    SELECT
        pf.id, pf.source_item_id, pf.source_item_type, dc.depth + 1
    FROM profile_fields pf
    INNER JOIN derivation_chain dc ON pf.id = dc.source_item_id
    WHERE dc.depth < 10  -- Max depth limit
)
SELECT * FROM derivation_chain;
```

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| **Application-level recursion** | N+1 queries, slow for deep chains |
| **Neo4j for lineage** | Over-engineering, additional dependency |
| **Pre-computed paths** | Complex to maintain on updates |

---

## 3. Cache Invalidation Strategy

### Decision
Use **write-through with TTL** for cache invalidation.

### Rationale
1. **Simple**: No pub/sub complexity
2. **Eventual consistency**: 30-minute TTL acceptable for profile data
3. **Explicit invalidation**: Mutations invalidate immediately
4. **Fallback**: Redis failures fall back to DB transparently

### Implementation
```python
async def update_field(self, field: ProfileField) -> UUID:
    # 1. Write to DB
    result = await self._backend.update_field(field)

    # 2. Invalidate cache (best-effort)
    try:
        await self._redis.delete(f"profile:{field.tenant_id}:{field.profile_id}")
    except RedisError:
        logger.warning("cache_invalidation_failed", field_id=str(field.id))

    return result
```

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| **Redis pub/sub** | Complexity, pods need to subscribe |
| **Cache-aside only** | Stale reads after direct DB updates |
| **No caching** | Performance regression (NFR-001) |

---

## 4. Schema Validation Modes

### Decision
Support three validation modes: `strict`, `warn`, `disabled`.

### Rationale
1. **Migration path**: Start with `warn` in production, move to `strict`
2. **Development flexibility**: `disabled` for rapid prototyping
3. **Compliance**: `strict` for regulated environments

### Implementation
```python
class ValidationMode(str, Enum):
    STRICT = "strict"      # Reject invalid values
    WARN = "warn"          # Log warning, accept value
    DISABLED = "disabled"  # Skip validation entirely

class SchemaValidationService:
    def __init__(self, mode: ValidationMode = ValidationMode.WARN):
        self._mode = mode

    def validate_field(self, field: ProfileField, definition: ProfileFieldDefinition) -> list[str]:
        errors = self._run_validators(field, definition)

        if errors and self._mode == ValidationMode.STRICT:
            raise SchemaValidationError(errors)
        elif errors and self._mode == ValidationMode.WARN:
            logger.warning("schema_validation_failed", errors=errors)

        return errors
```

---

## 5. ProfileItemSchemaExtraction Confidence

### Decision
Use **LLM confidence scoring** with 0.8 threshold for human review flag.

### Rationale
1. **Automation**: Most extractions are high-confidence, no manual work
2. **Safety net**: Low-confidence extractions flagged for review
3. **Non-blocking**: Even flagged extractions don't block scenario execution

### Implementation
```python
class ExtractionResult(BaseModel):
    field_name: str
    confidence: float  # 0.0 to 1.0
    needs_human_review: bool = False

    @validator("needs_human_review", always=True)
    def set_review_flag(cls, v, values):
        return values.get("confidence", 0) < 0.8
```

### Prompt Strategy
```
Given this scenario/rule definition, identify the customer profile fields
that are referenced in conditions or required for execution.

For each field, provide:
- field_name: The profile field key (e.g., "date_of_birth", "email")
- confidence: Your confidence (0.0-1.0) that this field is actually required

Only include fields that are explicitly or implicitly required by the conditions.
```

---

## 6. Migration Strategy

### Decision
Use **incremental, reversible migrations** with sensible defaults.

### Rationale
1. **Zero downtime**: Add columns with defaults, backfill later
2. **Rollback safety**: All migrations have downgrade functions
3. **Data preservation**: New columns don't break existing data

### Migration Order
1. `006_profile_fields_enhancement.py` - Add columns to existing table
2. `007_profile_assets_enhancement.py` - Add columns to existing table
3. `008_profile_field_definitions.py` - Create new table (no data dependencies)
4. `009_scenario_field_requirements.py` - Create new table (no data dependencies)

### Default Values
| Column | Default | Why |
|--------|---------|-----|
| `status` | `'active'` | All existing fields are active |
| `source_item_id` | `NULL` | No lineage for existing data |
| `source_item_type` | `NULL` | Derived from source_item_id |
| `source_metadata` | `'{}'` | Empty dict is safe |

---

## 7. Testing Strategy for LLM Extraction

### Decision
Use **pytest-recording** to record and replay LLM responses in CI.

### Rationale
1. **Deterministic**: Tests don't depend on live LLM calls
2. **Cost-free CI**: No API costs for running tests
3. **Fast**: No network latency in tests

### Implementation
```python
@pytest.mark.vcr()
async def test_extraction_from_scenario():
    extractor = ProfileItemSchemaExtractor(llm_executor, config_store)
    scenario = ScenarioFactory.create(
        description="Check customer age and verify identity",
        conditions=["age >= 18", "identity_verified == true"]
    )

    requirements = await extractor.extract_requirements(scenario)

    assert any(r.field_name == "date_of_birth" for r in requirements)
    assert any(r.field_name == "identity_verified" for r in requirements)
```

---

## Summary of Key Decisions

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Background Jobs | Hatchet | PostgreSQL-native, async, cron support |
| Lineage Queries | Recursive CTEs | Single query, depth limiting |
| Cache Strategy | Write-through + TTL | Simple, eventually consistent |
| Validation | Three modes | Migration path, flexibility |
| Extraction | 0.8 confidence threshold | Automation with safety net |
| Migrations | Incremental, reversible | Zero downtime, rollback safe |
| LLM Tests | pytest-recording | Deterministic, cost-free |
