# Implementation Checklist Corrections

> **Purpose**: Consolidate and fix inconsistencies across the 11 phase checklists.
> **Issue**: Subagents generated checklists independently, creating divergent schemas and scope creep.

---

## 1. Customer Data Naming Consolidation

The existing `focal/customer_data/` module **IS** the CustomerDataStore implementation. It needs field additions and consistent usage, NOT parallel schemas.

### Canonical Name Mapping

| Old Name (profile/) | New Name (CustomerData) | Location | Action |
|---------------------|------------------------|----------|--------|
| `ProfileFieldDefinition` | `CustomerDataField` | `focal/customer_data/models.py` | **RENAME** + add `scope`, `persist` |
| `ProfileField` | `VariableEntry` | `focal/customer_data/models.py` | **RENAME** + add `history` |
| `CustomerProfile` | `CustomerDataStore` | `focal/customer_data/models.py` | **RENAME** |
| `ProfileStore` | `CustomerDataStoreInterface` | `focal/customer_data/store.py` | **RENAME** |
| `ProfileFieldSource` | `VariableSource` | `focal/customer_data/enums.py` | **RENAME** |

### Fields to ADD to Existing Models

**On `ProfileFieldDefinition` → `CustomerDataField`:**
```python
# ADD these fields (in customer_data/models.py)
scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"] = Field(
    default="IDENTITY",
    description="Persistence scope"
)
persist: bool = Field(
    default=True,
    description="If False, field is runtime-only (never persisted)"
)
```

**On `ProfileField` → `VariableEntry`:**
```python
# ADD this field
history: list[dict[str, Any]] = Field(
    default_factory=list,
    description="[{value, timestamp, source, confidence}, ...]"
)
```

### DELETE from Phase Checklists

Remove these duplicate model definitions:

| Checklist | Section | What to DELETE |
|-----------|---------|---------------|
| Phase 1 | §1.3 | `CustomerDataField` model creation (use renamed `ProfileFieldDefinition`) |
| Phase 1 | §1.4 | `CustomerDataStore` model creation (use renamed `CustomerProfile`) |
| Phase 1 | §1.4 | `VariableEntry` model creation (use renamed `ProfileField`) |
| Phase 2 | §2.1 | `CustomerDataField`, `VariableEntry`, `CustomerDataStore` models |
| Phase 3 | §1.1-1.4 | `VariableEntry`, `CustomerDataStore`, `CustomerSchemaMask` models |

### KEEP (New Models Not in `customer_data`)

These models ARE new and should be created:

| Model | Location | Phase |
|-------|----------|-------|
| `CustomerSchemaMask` | `focal/alignment/context/customer_schema_mask.py` | P2 |
| `CandidateVariableInfo` | `focal/alignment/context/situational_snapshot.py` | P2 |
| `SituationalSnapshot` | `focal/alignment/context/situational_snapshot.py` | P2 |
| `GlossaryItem` | `focal/alignment/models/glossary.py` | P1 |
| `TurnContext` | `focal/alignment/models/turn_context.py` | P1 |

---

## 2. Missing LLM Template Items

Gap analysis identified these hardcoded prompts NOT addressed in any checklist:

### Entity Extraction (memory/ingestion/entity_extractor.py)

**Add to Phase 11 or create new "Memory Ingestion Templates" section:**

- [ ] **Create entity_extraction.jinja2 template**
  - File: `focal/memory/ingestion/prompts/entity_extraction.jinja2`
  - Action: Extract 192-line inline prompt from `entity_extractor.py:45-237`
  - Details: Move hardcoded prompt to Jinja2 template

- [ ] **Create TemplateLoader for entity extraction**
  - File: `focal/memory/ingestion/entity_extractor.py`
  - Action: Modify to use Jinja2 loader instead of inline string

### Summarization (memory/ingestion/summarizer.py)

- [ ] **Create window_summary.jinja2 template**
  - File: `focal/memory/ingestion/prompts/window_summary.jinja2`
  - Action: Extract inline prompt

- [ ] **Create meta_summary.jinja2 template**
  - File: `focal/memory/ingestion/prompts/meta_summary.jinja2`
  - Action: Extract inline prompt

### Scenario Filter

- [ ] **Create scenario_filter.jinja2 template**
  - File: `focal/alignment/filtering/prompts/scenario_filter.jinja2`
  - Action: Currently `.txt` unused - implement LLM-based scenario filtering
  - Note: Gap analysis says "Deterministic only" - need to add LLM path

---

## 3. Scope Creep Removal

Remove these items from checklists (not in gap analysis, violates minimal implementation):

### Phase 1 - DELETE Sections 5 & 6

| Section | Title | Reason to Remove |
|---------|-------|------------------|
| §5.1 | Glossary Table Migration | Alembic migrations out of scope |
| §5.2 | Customer Data Fields Migration | Alembic migrations out of scope |
| §5.3 | PostgreSQL Store Implementations | Production stores out of scope |
| §6.1 | Glossary CRUD Endpoints | CRUD APIs out of scope |
| §6.2 | Customer Data Field CRUD Endpoints | CRUD APIs out of scope |

### Phase 4 - DELETE Intent Catalog

| Item | Reason to Remove |
|------|------------------|
| Intent table creation | Gap analysis says "NOT FOUND" - not blocking |
| Intent CRUD endpoints | Out of scope |
| Intent documentation | Out of scope |

Keep intent retrieval as "future enhancement" note only.

---

## 4. Canonical File Paths

All checklists must use these paths:

### Models

| Model | Canonical Path |
|-------|---------------|
| `CustomerDataField` | `focal/customer_data/models.py` (renamed from ProfileFieldDefinition) |
| `VariableEntry` | `focal/customer_data/models.py` (renamed from ProfileField) |
| `CustomerDataStore` | `focal/customer_data/models.py` (renamed from CustomerProfile) |
| `CustomerSchemaMask` | `focal/alignment/context/customer_schema_mask.py` |
| `CandidateVariableInfo` | `focal/alignment/context/situational_snapshot.py` |
| `SituationalSnapshot` | `focal/alignment/context/situational_snapshot.py` |
| `GlossaryItem` | `focal/alignment/models/glossary.py` |
| `TurnContext` | `focal/alignment/models/turn_context.py` |
| `ResponsePlan` | `focal/alignment/planning/models.py` |
| `TurnOutcome` | `focal/alignment/models/outcome.py` |

### Templates

| Template | Canonical Path |
|----------|---------------|
| Situational Sensor | `focal/alignment/context/prompts/situational_sensor.jinja2` |
| Rule Filter | `focal/alignment/filtering/prompts/rule_filter.jinja2` |
| Scenario Filter | `focal/alignment/filtering/prompts/scenario_filter.jinja2` |
| Generation | `focal/alignment/generation/prompts/generation.jinja2` |
| Enforcement | `focal/alignment/enforcement/prompts/llm_judge.jinja2` |
| Entity Extraction | `focal/memory/ingestion/prompts/entity_extraction.jinja2` |
| Summarization | `focal/memory/ingestion/prompts/summarization.jinja2` |

### Stores

| Store | Canonical Path |
|-------|---------------|
| CustomerDataStore (interface) | `focal/customer_data/store.py` (renamed from ProfileStore) |
| InMemoryCustomerDataStore | `focal/customer_data/stores/inmemory.py` |
| PostgresCustomerDataStore | `focal/customer_data/stores/postgres.py` |

---

## 5. Field Naming Consistency

All models must use these field names:

| Field | Canonical Name | Type |
|-------|---------------|------|
| Field key | `name` | `str` (from ProfileFieldDefinition.name) |
| Tenant ID | `tenant_id` | `UUID` |
| Agent ID | `agent_id` | `UUID` |
| Customer ID | `customer_id` | `UUID` |
| Scope | `scope` | `Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]` |
| Persist flag | `persist` | `bool` |

**NOT**: `key`, `field_key`, `customer_key`, `str` for IDs

---

## 6. Checklist Update Summary

### Phase 1: Identification

- DELETE: §1.3 (CustomerDataField), §1.4 (CustomerDataStore, VariableEntry)
- DELETE: §5 (Database Migrations), §6 (API Routes)
- MODIFY: §1.2 (GlossaryItem) - keep, it's new
- ADD: Rename ProfileFieldDefinition → CustomerDataField with `scope`, `persist`

### Phase 2: Situational Sensor

- DELETE: §2.1 CustomerDataField, VariableEntry, CustomerDataStore models
- KEEP: §2.1 CustomerSchemaMask, CandidateVariableInfo (new models)
- KEEP: All Jinja2 template work

### Phase 3: Customer Data Update

- DELETE: §1.1-1.4 model creation (use renamed Profile models)
- MODIFY: §2 to reference existing ProfileFieldDefinition rename
- KEEP: Updater logic, persistence marking

### Phase 4: Retrieval & Selection

- DELETE: Intent catalog/table creation
- KEEP: Parallelization work (asyncio.gather)
- KEEP: Reranking config per object type

### Phase 5: Rule Selection

- ADD: scenario_filter.jinja2 template item

### Phase 9: Generation

- KEEP: All template work

### Phase 10: Enforcement

- KEEP: All template work
- KEEP: GLOBAL constraints fix
- KEEP: simpleeval integration

### Phase 11: Persistence

- ADD: Entity extraction template migration
- ADD: Summarization template migration

---

## 7. Implementation Order (Revised)

1. **Rename Profile → CustomerData** (foundation)
   - Rename classes in `focal/customer_data/models.py`
   - Add `scope`, `persist`, `history` fields
   - Update all imports across codebase

2. **Create new models** (Phase 1-2)
   - `CustomerSchemaMask`
   - `CandidateVariableInfo`
   - `SituationalSnapshot`
   - `GlossaryItem`
   - `TurnContext`

3. **Implement Jinja2 templates** (all phases)
   - Create `TemplateLoader` utility
   - Migrate all `.txt` prompts to `.jinja2`
   - Include entity extraction and summarization

4. **Implement pipeline logic** (Phases 2-10)
   - Situational Sensor
   - Customer Data Update
   - Response Planning (Phase 8)
   - Enforcement improvements

---

## 8. Verification Checklist

Before implementing, verify:

- [ ] All model definitions reference `focal/customer_data/models.py` (renamed)
- [ ] All field names use canonical naming (`name`, `tenant_id`, `customer_id`)
- [ ] All ID fields are `UUID`, not `str`
- [ ] No duplicate model definitions across phases
- [ ] No Alembic migrations in Phase 1
- [ ] No CRUD API routes in Phase 1
- [ ] Entity extraction template is addressed
- [ ] Summarization templates are addressed
- [ ] Scenario filter template is addressed
