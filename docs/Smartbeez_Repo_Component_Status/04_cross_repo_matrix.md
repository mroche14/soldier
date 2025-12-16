# Cross-Repo Component Matrix (Docs vs Code)

This file compares the **same conceptual components** across:
- `soldier` (Ruche/FOCAL runtime)
- `sb_agent_hub` (product/UI/auth + backend)
- `kernel_agent` (ChannelGateway/ToolHub/Control‑API prototypes + contracts)

For per-repo detail, see:
- `docs/Smartbeez_Repo_Component_Status/01_soldier_ruche_status.md`
- `docs/Smartbeez_Repo_Component_Status/02_sb_agent_hub_status.md`
- `docs/Smartbeez_Repo_Component_Status/03_kernel_agent_status.md`

Legend: docs `D0–D4`, code `C0–C5`, wired `W0–W2` (see `docs/Smartbeez_Repo_Component_Status/00_rating_scale.md`).

## Matrix

| Conceptual component | soldier (Ruche) | sb_agent_hub | kernel_agent | Notes / conflicts to resolve |
|---|---|---|---|---|
| Cognitive runtime / brain | D3/C4/W2 (`docs/focal_brain/*`, `ruche/brains/focal/*`) | D1/C2/W1 (LangGraph engine in backend) | D2/C0/W0 (Parlant-era framing mostly) | Your stated direction is “FOCAL is the brain”; that makes soldier the canonical cognitive layer. |
| Turn orchestration (session‑serialized) | D3/C3/W2 (`docs/acf/architecture/*`, `ruche/runtime/acf/*`) | D0/C0/W0 | D1/C0/W0 | soldier has the only real “LogicalTurn” orchestration model. |
| ChannelGateway (webhook edge) | D3/C3/W1 (specs + in-process adapters) | D2/C2/W1 (voice/websocket endpoints) | D3/C4/W2 (`apps/channel-gateway`) | kernel_agent has the most concrete edge service (dedup, signature verify, publish to streams). sb_agent_hub has working endpoints but fewer explicit transport contracts. |
| MessageRouter (bus consumer/backpressure) | D2/C1/W0 (described as external) | D1/C1/W0 | D2/C0/W0 (docs only) | This is the biggest “missing service”: documented across repos but not implemented cleanly anywhere. |
| Message bus transport | D2/C? (docs mention streams; code varies) | D1/C1 (HTTP+Redis+Celery; no explicit bus) | D3/C3 (Redis Streams bus in libs + contracts) | kernel_agent’s Redis Streams contract is the most reusable/explicit. |
| Tool execution runtime (Toolbox/ToolGateway) | D3/C3/W1 (`docs/acf/architecture/TOOLBOX_SPEC.md`, `ruche/runtime/toolbox/*`) | D2/C1/W0 (explicit `NotImplementedError` in tools base) | D3/C3/W1 (`apps/toolhub`) | soldier has strong *semantics*; kernel_agent has a concrete *toolhub service*; sb_agent_hub has scaffolding but not execution. |
| Control plane publish pipeline (bundles/pointers) | D2/C1/W0 (described in docs; not a finished service) | D2/C2/W1 (various admin/backend pieces) | D3/C2/W1 (publish workflow partially implemented) | Decide whether soldier absorbs kernel_agent’s publish pattern or sb_agent_hub becomes the control plane and publishes to soldier. |
| Orchestration engine (Hatchet/Restate/Celery) | Hatchet-first (ACF workflows) | Celery+Redis today | Restate-first in docs; partial in code | See `docs/Smartbeez_Orchestration_Study/README.md` for the “minimum viable set” choice. |
| Auth/tenancy (end-user + S2S) | D2/C3/W2 (JWT middleware) | D3/C3/W2 (Supabase/auth focus) | D2/C2/W1 (various) | Likely: sb_agent_hub is the SoT for tenancy + mints internal JWT for soldier. |
| UI (end-user + admin) | D0/C0/W0 | D2/C3/W2 (large UI footprint) | D1/C3/W1 (admin-panel/console) | sb_agent_hub is the clear product/UI surface; kernel_agent UI seems prototype/parallel. |

## Practical reading (what’s “real” where)

- Most “real cognitive engine” behavior lives in soldier (FOCAL + ACF).
- Most “real product UX/auth” lives in sb_agent_hub.
- The cleanest “reference implementation” of a scalable ChannelGateway + Redis Streams contract is in kernel_agent.

## Immediate conclusion for your question (docs vs code)

Across all three repos, the most common pattern is:
- **Docs are often ahead of code** for boundary services (MessageRouter, durable publish, async tool orchestration).
- **Code is strongest** where it had to work locally for demos (FOCAL brain in soldier, UI/auth in sb_agent_hub, channel-gateway service in kernel_agent).
