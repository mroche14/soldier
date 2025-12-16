# `kernel_agent` — Component Implementation Status (Docs vs Code)

## Snapshot

**Repo root**: `/home/marvin/Projects/kernel_agent`  
**Primary structure**:
- Apps/services: `/home/marvin/Projects/kernel_agent/apps/*`
- Shared libs: `/home/marvin/Projects/kernel_agent/libs/*`
- Heavy docs: `/home/marvin/Projects/kernel_agent/docs/*` (notably `docs/target/*`, `docs/contracts/*`, `docs/patterns/*`)

Key observation: this repo contains **very strong “target architecture” and contracts**, and **some concrete service implementations**, but also **several apps that are docs-only or partially stubbed**.

## App/component matrix

Legend: docs `D0–D4`, code `C0–C5`, wired `W0–W2` (see `docs/Smartbeez_Repo_Component_Status/00_rating_scale.md`).

| Subproject / component | What it is | Docs evidence | Code evidence | Tests evidence | Status (Docs/Code/Wired) | Notes (doc↔code drift / gaps) |
|---|---|---|---|---|---|---|
| `apps/channel-gateway` | Webhook edge: verify/normalize/dedup → publish to bus; outbound worker | `/home/marvin/Projects/kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`, `/home/marvin/Projects/kernel_agent/docs/contracts/README.md` | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/main.py`, `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py` | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/tests/*` | D3 / C4 / W2 | Looks like the most “shippable” service here: structured logging + outbound worker + tests. |
| `apps/message-router` | Bus consumer/router (ChannelGateway → runtime) | `/home/marvin/Projects/kernel_agent/apps/message-router/message-router.md` | (no `src/` directory present) | (n/a) | D2 / C0 / W0 | Docs exist but there is no implementation code in this repo. |
| `apps/toolhub` | Tool execution service (NDJSON streaming) | `/home/marvin/Projects/kernel_agent/docs/target/architecture_v4_toolhub.md`, `/home/marvin/Projects/kernel_agent/docs/target/Execution Pattern Decision.md` | `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/services/execution.py`, `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/api/execution.py` | `/home/marvin/Projects/kernel_agent/apps/toolhub/tests/*` | D3 / C3 / W1 | Core execution orchestration exists; security/config hardening still TODO (e.g. auth token validation TODOs in API). |
| `apps/control-api` (control plane) | Admin/control API + publishing pipeline (compile → bundles → pointer swap) | `/home/marvin/Projects/kernel_agent/docs/target/architecture_v3.md`, `/home/marvin/Projects/kernel_agent/docs/patterns/outbox-pattern.md` | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/main.py`, `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py` | `/home/marvin/Projects/kernel_agent/apps/control-api/tests/*` | D3 / C2 / W1 | Publish pipeline is partially implemented; several components are explicitly TODO (e.g. outbox poller, Restate client decorator, pointer manager). See `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/outbox_poller.py`. |
| `apps/admin-panel` | Admin UI (frontend) | (various docs in `/home/marvin/Projects/kernel_agent/docs/*`) | `/home/marvin/Projects/kernel_agent/apps/admin-panel/src/*` | (frontend tests not assessed here) | D1 / C3 / W1 | UI exists; “product completeness” depends on backend endpoints and auth readiness. |
| `apps/console` | Console UI (frontend) | (various docs in `/home/marvin/Projects/kernel_agent/docs/*`) | `/home/marvin/Projects/kernel_agent/apps/console/src/*` | (frontend tests not assessed here) | D1 / C2 / W1 | Present as UI code; depends on service APIs. |
| `apps/admin-panel-api` | API for admin panel | (limited) | `/home/marvin/Projects/kernel_agent/apps/admin-panel-api/src/admin_panel_api/main.py` | `/home/marvin/Projects/kernel_agent/apps/admin-panel-api/tests/*` | D1 / C3 / W1 | Appears implemented as a service with tests, but not analyzed for business feature completeness. |
| `apps/parlant-adapter` | Adapter layer for Parlant-era runtime | `/home/marvin/Projects/kernel_agent/docs/target/Parlant Integration & Multi-Plane Architecture.md` | `/home/marvin/Projects/kernel_agent/apps/parlant-adapter/src/*` | (no tests directory content detected) | D2 / C2 / W0 | Exists, but your current direction moved away from Parlant; expect this to be legacy/obsolete. |
| `apps/parlant-server` | Parlant server bundle | (legacy docs) | `/home/marvin/Projects/kernel_agent/apps/parlant-server/*` (no `src/` detected) | (n/a) | D1 / C0 / W0 | Appears legacy; no current app code in `src/`. |
| `libs/messaging` (Redis Streams bus) | MessageBus protocol + Redis Streams implementation | `/home/marvin/Projects/kernel_agent/docs/contracts/README.md` | `/home/marvin/Projects/kernel_agent/libs/messaging/redis_bus.py`, `/home/marvin/Projects/kernel_agent/libs/messaging/factory.py` | `/home/marvin/Projects/kernel_agent/libs/messaging/tests/*` | D3 / C3 / W2 | Redis Streams implementation exists; factory explicitly raises `NotImplementedError` for some alternates (e.g. NATS JetStream). |
| Orchestration choice (Restate/Celery/RabbitMQ) | “Path A/B/C” decision framework | `/home/marvin/Projects/kernel_agent/docs/target/Execution Pattern Decision.md` | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py` + stubs in `/home/marvin/Projects/kernel_agent/libs/clients/restate/__init__.py` | (tests exist but coverage unclear) | D3 / C1 / W0 | Restate is a major architectural pillar in docs, but SDK integration is partially stubbed (decorators TODO in `/home/marvin/Projects/kernel_agent/libs/clients/restate/__init__.py`). |

## Subcomponent breakdown (apps)

### `apps/channel-gateway` (edge gateway)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) |
|---|---|---|---|
| Webhook routes | Meta + webchat ingestion endpoints | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py` | D3 / C4 / W2 |
| Verification | Signature verification + challenges | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/services/verification.py` | D3 / C3 / W2 |
| Deduplication | Event id dedupe | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/services/deduplication.py` | D3 / C3 / W2 |
| Normalization | Provider payload → canonical envelope | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/services/normalization/*` | D3 / C3 / W2 |
| Tenant/channel resolution | Resolve provider resource to tenant/agent/channel config | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/services/channel_resolver.py` | D3 / C3 / W2 |
| Message bus publish | Redis Streams publishing | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py` (publishes via bus) | D3 / C3 / W2 |
| Outbound worker + senders | Consume outbound subjects + send via providers | `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/workers/outbound.py`, `/home/marvin/Projects/kernel_agent/apps/channel-gateway/src/channel_gateway/services/senders/*` | D2 / C3 / W2 |

### `apps/toolhub` (tool execution service)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| Execution API | NDJSON streaming execution endpoint | `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/api/execution.py` | D3 / C3 / W1 | TODO: authorization validation exists as a comment in execution API. |
| Execution orchestration | Validation + provider dispatch + logging | `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/services/execution.py` | D3 / C3 / W1 | Implements tenant authorization checks via storage tables. |
| Providers registry | Provider selection for tool backends | `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/providers/*` | D2 / C2 / W1 | Completeness depends on provider implementations present. |
| Storage | Supabase-backed storage access | `/home/marvin/Projects/kernel_agent/apps/toolhub/src/toolhub/storage/*` | D2 / C2 / W1 | Relies on Supabase schemas; contract completeness must be validated. |

### `apps/control-api` (publish/control plane)

| Sub-area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| API routers | Admin endpoints | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/api/v1/*` | D2 / C2 / W1 | Some routes include TODOs for tool registry loading. |
| Publisher workflow | Publish orchestration stages | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py` | D3 / C2 / W1 | Implements staged retry logic, but several surrounding pieces remain TODO. |
| Outbox poller | Detect outbox events + trigger workflows | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/outbox_poller.py` | D2 / C2 / W0 | Code exists but includes TODO for “actual Restate workflow invocation”. |
| Compiler | DSL validation/compilation | `/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/compiler/*` | D2 / C1 / W0 | Contains explicit TODOs for compiler orchestrator and schema validator. |

## Subcomponent breakdown (libs)

- Message bus protocol + Redis Streams: `/home/marvin/Projects/kernel_agent/libs/messaging/redis_bus.py`
- Bus factory with stubs for alternates (e.g., NotImplemented): `/home/marvin/Projects/kernel_agent/libs/messaging/factory.py`
- Restate client wrapper is partially stubbed (decorators TODO): `/home/marvin/Projects/kernel_agent/libs/clients/restate/__init__.py`

## “Doc says X, code does Y” highlights (examples)

- **Message Router** is heavily documented but not implemented (no `src` in `apps/message-router/`).
- **Control-plane publish** is documented as Restate-driven and multi-stage; code exists but several pieces remain TODO (outbox poller, Restate invocation, pointer manager).
- **Transport contracts** (Redis Streams, envelope fields, ACK semantics) are unusually concrete and reusable, especially for the ChannelGateway boundary.
