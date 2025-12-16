# Codex Docs vs Codebase State Report

**Generated:** 2025-12-16T08:37:05+04:00  
**Branch:** `main`  
**Git HEAD:** `fbc3f46e3027d1aac1168efbabbc601b9aea275e`  
**Working tree:** dirty (many modified/untracked files at time of capture)

This is a snapshot of the current documentation situation, with a focus on `docs/implementation/` and the broader `docs/` folder, plus a “docs vs codebase” mismatch audit.

---

## 1) Executive Summary (High-Signal Findings)

1. **There is no single, reliable “source of truth” entrypoint.**
   - Multiple overlapping planning/tracking systems exist (`docs/implementation/*`, `docs/focal_brain/IMPLEMENTATION_PLAN.md`, `docs/acf/*`, `docs/doc_skeleton.md`, plus `webdoc/`), and they disagree on what is canonical and what is current.

2. **Large parts of the docs reference code paths that no longer exist.**
   - This is the main reason the folder “feels messy”: readers can’t trust file-path references, and older plans are still presented as current.

3. **The docs build/sync tooling is out of date.**
   - `generate_docs.py` targets a non-existent `focal/` package, and `webdoc/docs/reference/` is generated for `focal.*`/legacy modules, not the current `ruche/` package.

4. **`docs/implementation/` mixes three distinct efforts (and their artifacts):**
   - (A) **Docs architecture / IA reorg** artifacts (how docs should be structured)
   - (B) **Docs vs codebase** audit artifacts (what’s stale / mismatched)
   - (C) **Implementation execution** artifacts (what to build, what’s done)
   - These are currently interleaved without clear “current vs archived” boundaries.

5. **Project naming evolution is a root cause of confusion (Soldier → Focal → Ruche platform).**
   - Several docs still implicitly assume “Focal = the whole project” instead of “FOCAL = one brain/mechanic within a broader agent platform”.

---

## 2) Current `docs/` Inventory (What Exists)

**Counts:**
- Total files under `docs/`: **129**
- Markdown files under `docs/`: **125**

**Top-level structure (directories):**
- `docs/acf/` (ACF architecture/specs; contains its own governance + “old/” archive)
- `docs/architecture/` (general architecture docs; some paths are stale)
- `docs/design/` (+ ADRs in `docs/design/decisions/`)
- `docs/development/`
- `docs/focal_brain/` (FOCAL brain spec + checklists + an “implementation plan”)
- `docs/implementation/` (planning + tracking + audits; the messy zone)
- `docs/reference/`, `docs/studies/`
- Several **top-level report-like files** (`ARCHITECTURE_READINESS_REPORT_V*.md`, etc.)

**Naming/organization pain points visible from the file system:**
- Versioned “report” documents live at `docs/` root rather than an explicit `docs/reports/` or `docs/archive/`.
- A small number of filenames contain spaces (e.g., `docs/agno_study1 copy.md`, `docs/Pipeline comparison evaluation.pdf`).

---

## 3) `docs/implementation/` State (What’s Inside + Why It Feels Mixed)

### 3.1 What the folder says it is
`docs/implementation/README.md` describes this folder as:
- “comprehensive plan to align the codebase with the architecture documentation”
- “START HERE: master-plan.md”
- “Status: ALL DECISIONS COMPLETE – READY FOR EXECUTION”

### 3.2 What the folder actually contains (grouped by lifecycle)

**A) Orchestration / planning (can become stale quickly):**
- `docs/implementation/master-plan.md`
- `docs/implementation/refactoring-plan.md`
- `docs/implementation/work-packages.md`
- `docs/implementation/subagent-protocol.md`

**B) Tracking / status (should reflect current reality):**
- `docs/implementation/IMPLEMENTATION_CHECKLIST.md` (quick status + checkbox truth table)
- `docs/implementation/tracking/overview.md`
- `docs/implementation/IMPLEMENTATION_WAVES.md`
- `docs/implementation/PARALLEL_WORK_TASKS.md`

**C) Audits / analyses / one-off reports:**
- `docs/implementation/gap-analysis.md`
- `docs/implementation/FOCAL_BRAIN_PHASE_COMPLIANCE_MATRIX.md`
- `docs/implementation/gemini_docs_analysis_2025-12-16.md`
- `docs/implementation/EVENT_MODEL_MIGRATION_PLAN.md`

**D) Duplicative protocol docs:**
- `docs/implementation/subagent-protocol.md` (draft)
- `docs/implementation/SUBAGENT_IMPLEMENTATION_PROTOCOL.md` (stricter, more complete)

### 3.3 Same files, categorized by “the three mixed efforts”

This matches your framing (docs architecture/IA reorg vs docs-vs-code analysis vs implementation execution):

**Docs architecture / IA reorg artifacts**
- `docs/implementation/refactoring-plan.md`
- `docs/implementation/master-plan.md`

**Docs vs codebase audit artifacts**
- `docs/implementation/gap-analysis.md`
- `docs/implementation/gemini_docs_analysis_2025-12-16.md`
- `docs/implementation/FOCAL_BRAIN_PHASE_COMPLIANCE_MATRIX.md`

**Implementation execution artifacts**
- `docs/implementation/IMPLEMENTATION_WAVES.md`
- `docs/implementation/PARALLEL_WORK_TASKS.md`
- `docs/implementation/IMPLEMENTATION_CHECKLIST.md` (best candidate for “single source of truth” status)
- `docs/implementation/EVENT_MODEL_MIGRATION_PLAN.md` (implementation plan for a specific migration)

### 3.4 Internal inconsistencies inside `docs/implementation/`

These are the kinds of contradictions that make the folder hard to trust:
- `docs/implementation/master-plan.md` frames WPs as future execution work.
- `docs/implementation/tracking/overview.md` claims “ALL WORK PACKAGES COMPLETE (9/9 WPs done)”.
- `docs/implementation/IMPLEMENTATION_CHECKLIST.md` is already the right shape to be “current truth”, but it currently coexists with older/parallel tracking styles.
- `docs/implementation/PARALLEL_WORK_TASKS.md` lists tasks as pending that `docs/implementation/IMPLEMENTATION_WAVES.md` later marks as complete (same day).
- `docs/implementation/gap-analysis.md` lists “current structure” folders that do not exist anymore (e.g., `ruche/alignment/`, `ruche/jobs/`, `ruche/providers/`).

Net: `docs/implementation/` currently reads like a **chronological scrapbook** of a fast refactor, but without explicit “ARCHIVED / SUPERSEDED BY” markers.

---

## 4) Docs vs Codebase Mismatch Audit (Concrete, Measurable)

This section highlights *high-impact* mismatches that block navigation and implementation.

### 4.1 Missing canonical pointers

- **Root `IMPLEMENTATION_PLAN.md` is missing**, but referenced widely.
  - Count of references across key docs (`docs/*`, `README.md`, `AGENTS.md`, `ruche/brains/focal/README.md`): **43**
  - Context note (your clarification): the “Implementation Plan” was originally **FOCAL-brain-only**, not platform-wide.
  - The brain-scoped plan exists at `docs/focal_brain/IMPLEMENTATION_PLAN.md`, but many entrypoints still expect a repo-root plan.
  - Impact: core workflow guidance keeps pointing to a file that isn’t present *and* the scope (brain vs platform) is unclear.

### 4.2 Stale code path references (docs point to removed/moved modules)

Measured by plain-text occurrences in `docs/`:

| Stale reference | Count | Reality in codebase |
|---|---:|---|
| `ruche/alignment` | 113 | directory is **missing** (FOCAL moved under `ruche/brains/focal/`) |
| `ruche/jobs` | 26 | directory is **missing** (Hatchet workflows live under `ruche/infrastructure/jobs/`) |
| `ruche/providers` | 30 | directory is **missing** (providers live under `ruche/infrastructure/providers/`) |
| `ruche/brains/focal/engine.py` | 48 | file is **deleted**; `ruche/brains/focal/pipeline.py` is the current entrypoint |
| `docs/focal_360` | 10 | directory is **missing** (renamed/replaced by `docs/acf/`) |

### 4.3 Terminology drift (customer vs interlocutor)

Occurrences in `docs/`:
- `customer_data`: **59**
- `interlocutor_data`: **257**

Decision note (your clarification): **`interlocutor` is canonical**; `customer` is deprecated legacy naming. Resolve the drift in Tier-1 docs and current plans; keep legacy terms only in archived/history docs where needed.

### 4.4 Stale “in-repo code docs” and doc tooling

These are especially confusing because they look authoritative:
- `ruche/brains/focal/README.md` still shows `from focal...` imports and paths like `tests/mechanics/focal/`.
- `generate_docs.py` hardcodes `root_dir = Path("focal")`, but the code package is `ruche/` → docs generation is not aligned with the repo.
- `webdoc/docs/reference/` contains reference docs for `focal.*` modules and `webdoc/docs/project_docs/doc_skeleton.md` includes absolute paths from another workspace (`/home/marvin/Projects/focal/...`), indicating `webdoc/` is not reliably synced to this repo.

---

## 5) The “Three Tasks” You Suspect Are Mixed (Recommended Separation)

This matches your intuition: you actually have three distinct efforts.

### A) Docs Architecture / Information Architecture (IA) Reorg (structure + lifecycle)

Goal: make it obvious what is canonical, current, historical, and experimental.

Suggested actions:
- Create a single `docs/README.md` (or rename `docs/doc_skeleton.md` → `docs/README.md`) that states:
  - what’s Tier-1 canonical vs Tier-2 supporting vs Tier-3 historical (ACF already uses this idea)
  - where “current implementation tracking” lives
- Move “report-ish” files into explicit buckets:
  - `docs/reports/` for dated audits (read-only snapshots)
  - `docs/archive/` for superseded plans/reports
- Make `docs/implementation/` explicit about purpose/lifecycle, e.g.:
  - `docs/implementation/` (current execution truth: checklist + waves)
  - `docs/implementation/audit/` (docs-vs-code scans)
  - `docs/implementation/docs-reorg/` (docs architecture/IA work)
  - `docs/implementation/archive/` (superseded)
  - `docs/implementation/reports/` (dated reports/matrices)
  - `docs/implementation/protocols/` (subagent/execution protocols)

### B) Docs ↔ Codebase Analysis & Alignment Sweep (content correctness)

Goal: fix references so docs help navigation instead of fighting it.

Suggested actions:
- Fix all high-signal stale references:
  - `ruche/alignment/*` → `ruche/brains/focal/*` (or correct new locations)
  - `ruche/jobs/*` → `ruche/infrastructure/jobs/*`
  - `ruche/providers/*` → `ruche/infrastructure/providers/*`
  - `docs/focal_360/*` → `docs/acf/*`
  - `ruche/brains/focal/engine.py` → `ruche/brains/focal/pipeline.py` (and/or the new entrypoint you want)
- Replace deprecated terminology (`customer*`) with canonical terminology (`interlocutor*`) in Tier-1 docs and current plans; keep legacy terms only in archived/history docs where needed.
- Update “embedded” READMEs inside code (e.g., `ruche/brains/focal/README.md`) so the nearest docs to the code are accurate.

### C) Implementation Execution + Tooling (prevent drift)

Goal: stop reintroducing doc drift after the next refactor.

Suggested actions:
- Update docs generation tooling:
  - Make `generate_docs.py` target the current package (`ruche/`) and ensure it doesn’t emit absolute paths.
  - Decide whether `webdoc/` is authoritative; if yes, define a sync workflow from `docs/` → `webdoc/docs/project_docs/`.
- Add a lightweight “docs audit” script (even just a Makefile target) that fails on:
  - references to known-dead paths (`ruche/alignment`, `docs/focal_360`, etc.)
  - `mkdocs.yml` nav entries pointing at missing files

---

## 6) Suggested Target End-State (Minimal Disruption Version)

If you want to keep most existing paths stable, this is a low-churn target:

```
docs/
  README.md                  # canonical entrypoint + doc tiers
  acf/                       # keep as-is; already has governance
  focal_brain/               # keep as-is; update to current paths/terms
  architecture/              # keep as-is; reconcile with acf/ where overlapping
  design/
  development/
  implementation/
    audit/                   # docs-vs-code audits
    docs-reorg/              # docs architecture/IA work
    reports/                 # dated reports/matrices
    protocols/               # subagent/execution protocols
    archive/                 # obsolete/superseded plans
  studies/
  reference/
```

Key idea: **don’t delete history**, but make it impossible to mistake history for “current plan”.

---

## 6.1) Exact Reorganization Proposal (Minimal-Churn, Stepwise)

This is the concrete “what moves where” plan I’d apply to make the docs navigable fast, without rewriting content yet. The goal is to (1) separate *current* from *archive* and (2) put stable entrypoints in obvious places.

### 6.1.1) Create these directories (new)

```
docs/
  assets/
  reports/
    architecture-readiness/
  implementation/
    archive/
      2025-12-15/
    audit/
    docs-reorg/
    reports/
    protocols/
```

### 6.1.2) Make these entrypoints canonical (no moves required)

- `docs/acf/README.md` stays the ACF entrypoint (already strong, includes governance tiers).
- `docs/implementation/IMPLEMENTATION_CHECKLIST.md` becomes the canonical “current status” for platform implementation work (this is the checklist you added; it’s the right shape to be authoritative).
- `docs/implementation/README.md` should be rewritten so **Start Here = `IMPLEMENTATION_CHECKLIST.md`**, not `master-plan.md`.
- `docs/focal_brain/README.md` stays the FOCAL brain entrypoint (but should be explicit that it’s “brain-only”, not platform-wide).

### 6.1.3) Move `docs/implementation/` into lifecycle buckets (exact mapping)

**Keep at `docs/implementation/` root (current working set):**
- Keep: `docs/implementation/IMPLEMENTATION_CHECKLIST.md`
- Keep: `docs/implementation/IMPLEMENTATION_WAVES.md`
- Keep (optional): `docs/implementation/PARALLEL_WORK_TASKS.md` (if it remains “next actionable tasks”)
- Keep: `docs/implementation/README.md` (but rewrite it to reflect this structure)

**Move to `docs/implementation/protocols/` (only one canonical protocol):**
- Move: `docs/implementation/SUBAGENT_IMPLEMENTATION_PROTOCOL.md` → `docs/implementation/protocols/SUBAGENT_IMPLEMENTATION_PROTOCOL.md`

**Move to `docs/implementation/archive/2025-12-15/` (superseded planning artifacts):**
- Move: `docs/implementation/master-plan.md` → `docs/implementation/archive/2025-12-15/master-plan.md`
- Move: `docs/implementation/refactoring-plan.md` → `docs/implementation/archive/2025-12-15/refactoring-plan.md`
- Move: `docs/implementation/work-packages.md` → `docs/implementation/archive/2025-12-15/work-packages.md`
- Move: `docs/implementation/gap-analysis.md` → `docs/implementation/archive/2025-12-15/gap-analysis.md`
- Move: `docs/implementation/questions.md` → `docs/implementation/archive/2025-12-15/questions.md`
- Move: `docs/implementation/subagent-protocol.md` → `docs/implementation/archive/2025-12-15/subagent-protocol.md`
- Move: `docs/implementation/tracking/overview.md` → `docs/implementation/archive/2025-12-15/tracking-overview.md`
  - Then delete the now-empty folder `docs/implementation/tracking/` (or keep it only if you plan to continue WP-based tracking).

**Move to `docs/implementation/reports/` (dated analyses / audits):**
- Move: `docs/implementation/gemini_docs_analysis_2025-12-16.md` → `docs/implementation/reports/gemini_docs_analysis_2025-12-16.md`
- Move: `docs/implementation/FOCAL_BRAIN_PHASE_COMPLIANCE_MATRIX.md` → `docs/implementation/reports/FOCAL_BRAIN_PHASE_COMPLIANCE_MATRIX.md`
  - Alternative (better semantics): move into `docs/focal_brain/analysis/` instead, since it’s brain-scoped.
- Move: `docs/implementation/EVENT_MODEL_MIGRATION_PLAN.md` → `docs/implementation/reports/EVENT_MODEL_MIGRATION_PLAN.md`
  - Alternative (better semantics): move into `docs/acf/implementation/` or `docs/architecture/` depending on ownership.

### 6.1.3b) Optional: also separate by “the three mixed efforts” (stronger boundaries)

If you want `docs/implementation/` to explicitly reflect the three efforts you described (instead of only lifecycle buckets), use these destinations:

- Docs IA reorg: `docs/implementation/docs-reorg/`
- Docs vs code audit: `docs/implementation/audit/`
- Implementation execution: keep the execution truth at `docs/implementation/` root (checklist + waves)

### 6.1.4) Clean up the `docs/` root (exact mapping)

This removes the “cluttered root directory” feeling without losing anything.

**Move architecture readiness versions into a single folder:**
- Move: `docs/ARCHITECTURE_READINESS_REPORT_v1.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_v1.md`
- Move: `docs/ARCHITECTURE_READINESS_REPORT_V2.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_V2.md`
- Move: `docs/ARCHITECTURE_READINESS_REPORT_V3.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_V3.md`
- Move: `docs/ARCHITECTURE_READINESS_REPORT_V4.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_V4.md`
- Move: `docs/ARCHITECTURE_READINESS_REPORT_V5.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_V5.md`
- Move: `docs/ARCHITECTURE_READINESS_REPORT_V6.md` → `docs/reports/architecture-readiness/ARCHITECTURE_READINESS_REPORT_V6.md`

**Move binary assets into `docs/assets/`:**
- Move: `docs/pic.png` → `docs/assets/pic.png`
- Move: `docs/Pipeline comparison evaluation.pdf` → `docs/assets/Pipeline comparison evaluation.pdf`

**Move one-off studies to `docs/studies/` (and remove “copy” naming):**
- Move: `docs/agno_study1.md` → `docs/studies/agno/agno_study1.md`
- Move: `docs/agno_study1 copy.md` → `docs/studies/agno/agno_study1_copy.md` (or delete if truly redundant)

### 6.1.5) After moves: update links + add “archived/superseded” banners

1. Update `docs/implementation/README.md` to point at the checklist.
2. Add a one-line banner to archived docs (top of file):
   - `> **ARCHIVED**: Superseded by docs/implementation/IMPLEMENTATION_CHECKLIST.md (YYYY-MM-DD)`
3. Run a path fix sweep:
   - Replace `ruche/alignment` → `ruche/brains/focal` (as appropriate)
   - Replace `ruche/jobs` → `ruche/infrastructure/jobs`
   - Replace `ruche/providers` → `ruche/infrastructure/providers`
   - Replace `docs/focal_360` → `docs/acf`
   - Replace `ruche/brains/focal/engine.py` → `ruche/brains/focal/pipeline.py`
   - Replace deprecated terminology (`customer*`) → canonical (`interlocutor*`) in current (non-archived) docs

---

## 7) Next Steps (Practical, High-Leverage)

If you want the fastest cleanup impact:
1. **Pick the canonical entrypoints**:
   - docs: `docs/README.md` (new) + `docs/acf/README.md` (already strong)
   - implementation tracking: one file that is “current”
2. **Decide what the repo-level “plan” pointer is**:
   - If you keep `IMPLEMENTATION_PLAN.md` at repo root, make it a *platform-level index* (and clearly point to the brain-scoped plan under `docs/focal_brain/`).
   - Otherwise, update `AGENTS.md`/`README.md` and any other entrypoints to stop referencing a non-existent root plan.
3. **Archive/supersede stale plans** in `docs/implementation/` with explicit banners like:
   - “SUPERSEDED BY: … (date)”
4. **Fix the top 5 path mismatches** (table above).
5. **Decide what `webdoc/` is** (authoritative site vs historical artifact), then align tooling accordingly.

---

## Addendum: Scope Clarification (Soldier → Focal → Platform)

You clarified after the initial scan:
- The repo started as **Soldier**, then became **Focal** (as a reference to the “alignment pipeline/brain”).
- It has since expanded into a broader **agent platform** (ACF/runtime/tools/providers/etc.), where FOCAL is one component.

Recommended doc action from this clarification:
- Treat `docs/focal_brain/IMPLEMENTATION_PLAN.md` as **FOCAL-brain-scoped** (rename or banner it as such), and introduce a separate **platform-level** entrypoint/plan (even a short index) that points to `docs/acf/` + platform architecture docs + current execution tracking.

---

## Appendix: Evidence Commands Used (selected)

- `find docs -type f | wc -l` → 129  
- `find docs -type f -name '*.md' | wc -l` → 125  
- `rg -o "ruche/alignment" docs | wc -l` → 113  
- `rg -o "ruche/jobs" docs | wc -l` → 26  
- `rg -o "ruche/providers" docs | wc -l` → 30  
- `rg -o "docs/focal_360" docs | wc -l` → 10  
- `rg -o "ruche/brains/focal/engine\\.py" docs | wc -l` → 48  
- `test -f IMPLEMENTATION_PLAN.md` → missing  
