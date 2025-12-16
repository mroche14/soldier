# Rating Scale (Docs vs Code)

This scale is used consistently in the per-repo reports.

## Docs maturity (`D0`–`D4`)

- `D0` — No meaningful docs
- `D1` — Notes / partial descriptions (not a spec)
- `D2` — Design doc exists, but not complete or not contract-level
- `D3` — Detailed spec/contracts and clear responsibilities
- `D4` — Comprehensive docs (spec + contracts + ops/runbooks + failure modes)

## Code maturity (`C0`–`C5`)

- `C0` — Not implemented (docs only)
- `C1` — Skeleton/stubs (interfaces, placeholders, `NotImplementedError`, heavy TODOs)
- `C2` — Partial implementation (some routes/services exist; not end-to-end or not hardened)
- `C3` — Implemented core behavior (works for main path; gaps remain)
- `C4` — Implemented + tests + reasonably integrated (local dev should work)
- `C5` — Production-grade (hardening, observability, security, scaling + runbooks aligned)

## “Wired” flag

Some code exists but isn’t connected end-to-end.

- `W0` — Not wired / unused
- `W1` — Partially wired (some flows)
- `W2` — End-to-end wired for primary flows
