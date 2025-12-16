# Gemini Docs Analysis Report

**Date:** 2025-12-16
**Status:** CRITICAL DISCREPANCY DETECTED

## 1. Executive Summary

A comprehensive audit of the `docs/` folder against the actual `ruche/` codebase reveals that the documentation (specifically `gap-analysis.md` and `master-plan.md`) is significantly out of sync with reality. The codebase is further ahead than the docs suggest in some areas (consolidation of providers and brain), but potentially broken in others (missing worker entry point).

## 2. Critical Findings: The "Ghost" Folders

The `docs/implementation/gap-analysis.md` report lists several folders as "Current Structure" which **do not exist** in the file system. This suggests a previous refactor was performed but the documentation was not updated, or the analysis was based on an outdated index.

| Folder | Status in Docs | Status in File System | Reality |
|--------|----------------|-----------------------|---------|
| `ruche/alignment/` | Listed as "Current" | ❌ **MISSING** | Code has already been consolidated into `ruche/brains/focal/`. |
| `ruche/providers/` | Listed as "Current" | ❌ **MISSING** | Code has already been consolidated into `ruche/infrastructure/providers/`. |
| `ruche/jobs/` | Listed as "Current" | ❌ **MISSING** | **CRITICAL**: The Hatchet worker entry point and workflows appear to be missing. |

## 3. Actual Codebase State

*   **FOCAL Brain:** The consolidation described in "WP-001" of the master plan appears **complete**. The logic resides in `ruche/brains/focal/`.
*   **ACF (Agent Conversation Fabric):** The core logic is present in `ruche/runtime/acf/`. The `workflow.py` file contains the `LogicalTurnWorkflow` class, but it is not currently wired to a running worker (due to missing `ruche/jobs/`).
*   **Providers:** The deduplication described in "WP-006" is **complete**. Implementations are correctly located in `ruche/infrastructure/providers/`.

## 4. Documentation Health Assessment

The `docs/` folder is cluttered and contains conflicting information:
*   **Obsolete Plans:** `gap-analysis.md` and `master-plan.md` describe tasks that are already done.
*   **Fragmentation:** Information is scattered across `docs/acf/`, `docs/focal_brain/`, and `docs/architecture/`.
*   **Mixed Terminology:** Docs still reference `alignment/` and `customer_data` while the code is moving toward `focal/` and `interlocutor`.

## 5. Recommendations

### Immediate Actions
1.  **Archive Obsolete Docs:** Move `gap-analysis.md`, `master-plan.md`, and other stale implementation docs to an `archive/` folder to prevent confusion.
2.  **Restore the Worker:** The `ruche/jobs/` directory is missing. We need to re-create the Hatchet worker entry point to allow the `LogicalTurnWorkflow` to run.
3.  **Run Tests:** Since `ruche/alignment` was deleted, we must run the test suite to ensure no imports are broken.

### Structural Refactor (Docs)
I recommend reorganizing the documentation to match the current reality:

```
docs/
├── archive/                  # Old reports and plans
├── architecture/             # Design specs (ACF, Brain, Stores)
├── implementation/           # LIVE implementation plans (not stale ones)
└── guides/                   # Developer guides
```

## 6. Conclusion

The "messy" state of the docs is due to them lagging behind a rapid refactoring phase. The code is structurally cleaner than the docs imply, but the missing `ruche/jobs` folder is a functional regression that needs immediate attention.
