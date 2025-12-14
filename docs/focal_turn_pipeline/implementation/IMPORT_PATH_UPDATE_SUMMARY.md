# Phase Checklists Import Path Update Summary

## Date: 2025-01-15

## Files Updated

Updated 6 phase checklist files with new import paths following the focal mechanics reorganization:

1. `phase-01-identification-checklist.md`
2. `phase-02-situational-sensor-checklist.md`
3. `phase-03-customer-data-update-checklist.md`
4. `phase-04-retrieval-selection-checklist.md`
5. `phase-05-rule-selection-checklist.md`
6. `phase-06-scenario-orchestration-checklist.md`

## Replacements Applied

| Old Path/Name | New Path/Name | Count |
|---------------|---------------|-------|
| `focal/alignment/` | `focal/mechanics/focal/` | ~250 |
| `focal.alignment.` | `focal.mechanics.focal.` | ~50 |
| `focal/providers/` | `focal/infrastructure/providers/` | ~15 |
| `focal.providers.` | `focal.infrastructure.providers.` | ~10 |
| `focal/conversation/` | `focal/runtime/` | ~20 |
| `focal.conversation.` | `focal.runtime.` | ~10 |
| `focal/customer_data/` | `focal/domain/interlocutor/` | ~150 |
| `focal.customer_data.` | `focal.domain.interlocutor.` | ~30 |
| `AlignmentEngine` | `FocalCognitivePipeline` | ~30 |
| `CustomerDataStore` | `InterlocutorDataStore` | ~80 |
| `CustomerDataField` | `InterlocutorDataField` | ~60 |
| `CustomerSchemaMask` | `InterlocutorSchemaMask` | ~25 |

## Examples of Changes

### Module Paths
```diff
- File: `focal/alignment/models/turn_context.py`
+ File: `focal/mechanics/focal/models/turn_context.py`

- File: `focal/customer_data/models.py`
+ File: `focal/domain/interlocutor/models.py`

- File: `focal/conversation/models/session.py`
+ File: `focal/runtime/models/session.py`
```

### Class Names
```diff
- class TurnContext(BaseModel):
-     customer_data: CustomerDataStore
-     customer_data_fields: dict[str, CustomerDataField]

+ class TurnContext(BaseModel):
+     customer_data: InterlocutorDataStore
+     customer_data_fields: dict[str, InterlocutorDataField]
```

### Engine References
```diff
- **Add explicit customer resolution method to AlignmentEngine**
-   - File: `focal/alignment/engine.py`

+ **Add explicit customer resolution method to FocalCognitivePipeline**
+   - File: `focal/mechanics/focal/engine.py`
```

## Verification

All replacements were verified:
- ✅ 6 files successfully updated
- ✅ Backup files created (*.bak)
- ✅ No old paths remain in updated files
- ✅ All new paths use consistent naming

## Rollback Instructions

If needed, restore from backup files:
```bash
cd docs/focal_turn_pipeline/implementation
for file in *.bak; do
  mv "$file" "${file%.bak}"
done
```

## Next Steps

The phase checklist files now align with the new focal mechanics folder structure. When implementing features from these checklists:

1. Use the updated paths in `focal/mechanics/focal/` for alignment/cognitive pipeline code
2. Use `focal/domain/interlocutor/` for customer data models
3. Use `focal/infrastructure/providers/` for LLM/embedding/rerank providers
4. Use `focal/runtime/` for session/conversation management
5. Reference `FocalCognitivePipeline` instead of `AlignmentEngine`
6. Use `InterlocutorDataStore/InterlocutorDataField/InterlocutorSchemaMask` for customer data

