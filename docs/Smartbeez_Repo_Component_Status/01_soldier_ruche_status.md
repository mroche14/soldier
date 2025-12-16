# `soldier` / Ruche — Component Implementation Status (Docs vs Code)

## Snapshot

**Main code root**: `ruche/`  
**Primary docs roots**: `docs/acf/architecture/`, `docs/architecture/`, `docs/focal_brain/` (index: `docs/doc_skeleton.md`)

Quick size signals (not “completeness”):
- API code: `ruche/api/` (~55 Python files)
- Runtime: `ruche/runtime/` (ACF ~11 files; toolbox ~5; channels ~6)
- Brain: `ruche/brains/focal/` (~99 files)
- Tests exist across runtime/API/brain: `tests/` (notably `tests/unit/runtime/*`, `tests/unit/brains/focal/*`)

## Component matrix (high level)

Legend: docs `D0–D4`, code `C0–C5`, wired `W0–W2` (see `docs/Smartbeez_Repo_Component_Status/00_rating_scale.md`).

| Component | What it is | Docs evidence | Code evidence | Tests evidence | Status (Docs/Code/Wired) | Notes (doc↔code drift / gaps) |
|---|---|---|---|---|---|---|
| API layer (HTTP) | FastAPI surface for chat + config entities | `docs/architecture/api-layer.md`, `docs/architecture/event-model.md` | `ruche/api/app.py`, `ruche/api/routes/turns.py`, `ruche/api/routes/*` | `tests/unit/api/*`, `tests/integration/api/*` | D2 / C3 / W2 | Main chat endpoint exists; streaming is present but has TODO for “actual streaming from AlignmentEngine” in `ruche/api/routes/turns.py`. |
| API layer (SSE streaming) | Token/done/error stream for chat | `docs/architecture/api-layer.md` | `ruche/api/routes/turns.py` (`/chat/stream`) | (covered indirectly by API tests) | D2 / C2 / W1 | SSE route exists; TODO indicates stream wiring is incomplete (`ruche/api/routes/turns.py`). |
| API layer (gRPC) | gRPC stubs for chat/memory/config | (limited) | `ruche/api/grpc/*` | (unknown/limited) | D0 / C1 / W0 | Generated stubs raise `NotImplementedError` (e.g. `ruche/api/grpc/chat_pb2_grpc.py`). |
| ACF (turn orchestration) | LogicalTurn workflow: mutex → accumulate → run → commit | `docs/acf/architecture/ACF_SPEC.md`, `docs/acf/architecture/topics/06-hatchet-integration.md` | `ruche/runtime/acf/workflow.py`, `ruche/runtime/acf/gateway.py` | `tests/unit/runtime/acf/*` | D3 / C3 / W2 | Core workflow wrapper exists; still uses explicit “acquire mutex” step in code (`ruche/runtime/acf/workflow.py`). |
| ACF scalability/concurrency strategy | Per-session serialization w/o Redis lock | `docs/architecture/ACF_SCALABILITY_ANALYSIS.md` | (not implemented in code yet) | (n/a) | D3 / C1 / W0 | Docs recommend Hatchet-native concurrency groups; code still uses explicit mutex acquisition. |
| Channels runtime (in-process) | Channel models + adapters (webchat etc.) | `docs/architecture/channel-gateway.md`, `docs/acf/architecture/topics/10-channel-capabilities.md` | `ruche/runtime/channels/gateway.py`, `ruche/runtime/channels/adapter.py`, `ruche/runtime/channels/adapters/*` | `tests/unit/runtime/channels/test_gateway.py` | D3 / C3 / W1 | “ChannelGateway” is designed as an external service, but this repo contains in-process channel adapter code (good for reference / local mode). |
| Event model + routing (ACFEvents) | Internal event capture + routing | `docs/architecture/event-model.md` | `ruche/runtime/acf/events.py`, `ruche/runtime/acf/event_router.py` | `tests/unit/runtime/acf/test_event_router.py` | D3 / C3 / W1 | EventRouter exists; external fanout (webhooks) isn’t wired by default (see Webhooks row). |
| Webhook system (external delivery) | Tenant webhook subscriptions + dispatcher | `docs/architecture/webhook-system.md` | `ruche/api/webhooks/*` | `tests/unit/api/webhooks/*` | D3 / C2 / W0 | Dispatcher exists but is not referenced outside `ruche/api/webhooks/*` (`rg` shows no external usage of `WebhookDispatcher`), so event→webhook delivery is not end-to-end wired. |
| Toolbox / ToolGateway (runtime tool execution) | Tool execution context + gateway abstraction | `docs/acf/architecture/TOOLBOX_SPEC.md`, `docs/acf/architecture/topics/04-side-effect-policy.md` | `ruche/runtime/toolbox/toolbox.py`, `ruche/runtime/toolbox/gateway.py`, `ruche/runtime/toolbox/context.py` | `tests/unit/runtime/toolbox/test_toolbox.py` | D3 / C3 / W1 | Core runtime classes exist; integration into the brain/tool binding is still a major convergence topic (see integration study). |
| FOCAL brain (alignment engine) | The cognitive engine pipeline | `docs/focal_brain/spec/*`, `docs/focal_brain/implementation/*` | `ruche/brains/focal/*` | `tests/unit/brains/focal/*`, `tests/integration/alignment/*` | D3 / C4 / W2 | Most “real engine” logic is here; strong code footprint + tests. |
| Stores (Config/Memory/Session/Audit/etc.) | Persistence interfaces + backends | `docs/design/decisions/001-storage-choice.md`, `docs/architecture/memory-layer.md` | `ruche/infrastructure/stores/*`, `ruche/conversation/stores/*`, `ruche/audit/stores/*`, `ruche/memory/stores/*` | `tests/unit/*/stores/*`, `tests/integration/stores/*` | D2 / C3 / W2 | Multiple backends exist (in-memory + Postgres + Redis, etc.); “production correctness” depends on which backend is used + migrations. |
| Observability | structured logs, tracing, metrics hooks | `docs/architecture/observability.md` | `ruche/observability/*` | `tests/unit/observability/*` | D2 / C3 / W2 | Present; need to validate end-to-end trace propagation through external gateways. |
| Jobs / background workflows | scheduled/durable tasks | (scattered: e.g. Hatchet mentions in docs) | `ruche/infrastructure/jobs/*` | `tests/unit/jobs/*` | D1 / C2 / W1 | Exists but is not the primary integration surface unless you choose Hatchet as the global orchestrator. |
| MCP server | tool/plugin exposure | (limited) | `ruche/api/mcp/*` | (unknown/limited) | D1 / C2 / W1 | Implemented as an API surface; contracts with external ToolHub need consolidation. |

## Subcomponent breakdown (more granular)

### `ruche/api/*` (HTTP + gRPC + MCP + webhooks)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| App factory + middleware wiring | FastAPI creation + middleware + error handling | `ruche/api/app.py` | D2 / C3 / W2 | Includes CORS, logging context, request context, rate limiting, OpenTelemetry instrumentation. |
| Routes (CRUD + chat) | HTTP endpoints for entities + chat | `ruche/api/routes/*`, `ruche/api/routes/turns.py` | D2 / C3 / W2 | Chat works for non-streaming; SSE streaming partially implemented (TODOs in `ruche/api/routes/turns.py`). |
| Middleware | auth context, logging context, rate limit, idempotency stubs | `ruche/api/middleware/*` | D2 / C3 / W2 | Idempotency middleware exists but end-to-end idempotency caching is TODO at route layer (`ruche/api/routes/turns.py`). |
| Webhooks (API + dispatcher) | subscription CRUD + HMAC signing + matcher | `ruche/api/webhooks/*` | D3 / C2 / W0 | Present but not wired to event emission (no external usage of `WebhookDispatcher`). |
| gRPC server + stubs | grpc server shell + generated stubs | `ruche/api/grpc/server.py`, `ruche/api/grpc/*_pb2_grpc.py` | D0 / C1 / W0 | Generated stubs raise `NotImplementedError` (e.g. `ruche/api/grpc/chat_pb2_grpc.py`). |
| MCP server | MCP endpoint surface | `ruche/api/mcp/server.py`, `ruche/api/mcp/handlers.py` | D1 / C2 / W1 | Exists; “what it exposes” vs ToolHub direction is an integration decision. |

### `ruche/runtime/*` (ACF + toolbox + channels + idempotency)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| `runtime/acf` | LogicalTurn workflow + event handling | `ruche/runtime/acf/workflow.py`, `ruche/runtime/acf/event_router.py`, `ruche/runtime/acf/events.py` | D3 / C3 / W2 | Core runtime orchestration exists; concurrency improvements are still doc-only (`docs/architecture/ACF_SCALABILITY_ANALYSIS.md`). |
| `runtime/toolbox` | Toolbox + ToolGateway + execution context | `ruche/runtime/toolbox/*` | D3 / C3 / W1 | Core runtime tool semantics exist; cross-repo “ToolHub vs Toolbox” is still an integration decision. |
| `runtime/channels` | in-process channel gateway/adapters | `ruche/runtime/channels/*` | D3 / C3 / W1 | Exists, but soldier’s own architecture docs describe this as an external layer. |
| `runtime/idempotency` | idempotency helpers | `ruche/runtime/idempotency/*` | D2 / C2 / W1 | Present; not consistently enforced at the API boundary yet. |

### `ruche/infrastructure/*` (stores/providers/db/jobs; “production wiring”)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| DB / migrations | DB plumbing and migrations | `ruche/infrastructure/db/*` | D1 / C2 / W1 | Exists; completeness depends on which stores are actually wired in the running app. |
| Stores | concrete store implementations (inmemory/postgres/etc.) | `ruche/infrastructure/stores/*`, `ruche/conversation/stores/*` | D2 / C3 / W2 | Strong surface; multiple backends exist, but production choice must be made. |
| Providers | LLM/embedding/rerank adapters | `ruche/infrastructure/providers/*` | D2 / C2 / W1 | Present; “provider completeness” depends on configuration and which providers are enabled. |
| Jobs/workflows | background workflows | `ruche/infrastructure/jobs/*` | D1 / C2 / W1 | Present but not the primary integration surface unless you converge on Hatchet globally. |
| Infra duplicates | “infrastructure layer” duplicates for channels/toolbox | `ruche/infrastructure/channels/*`, `ruche/infrastructure/toolbox/*` | D1 / C1 / W0 | The integration study already flags duplication; treat as “candidate for deletion or consolidation” once boundaries are decided. |

## Concrete “doc says X, code does Y” highlights (examples)

- **Streaming**: docs treat streaming as first-class; code has an SSE route but includes TODOs for “actual streaming” (`ruche/api/routes/turns.py`).
- **Idempotency**: docs/spec emphasize idempotency; API endpoint includes TODOs to implement idempotency caching (`ruche/api/routes/turns.py`).
- **Webhooks**: webhook system is documented and code exists, but it is not wired from the EventRouter (no usage of `WebhookDispatcher` outside `ruche/api/webhooks/*`).
- **Concurrency**: docs recommend Hatchet-native per-session concurrency (no Redis mutex); code still has an explicit “acquire mutex” step (`ruche/runtime/acf/workflow.py`).
