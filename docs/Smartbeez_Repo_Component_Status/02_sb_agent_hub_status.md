# `sb_agent_hub` — Component Implementation Status (Docs vs Code)

## Snapshot

**Repo root**: `/home/marvin/Projects/sb_agent_hub`  
**Primary structure**:
- `0-frontend-landing/` (landing/marketing)
- `1-frontend-user/` (+ `1-frontend-user-vite/` alternative)
- `2-frontend-admin/`
- `3-backend/` (FastAPI backend)
- `4-cluster/` (Kubernetes/infra work)
- `docs/` (architecture, security, deployment, supabase)

Key observation: this repo is **heavy on product/UI/auth and platform scaffolding**, with **real AG‑UI / webchat / voice ingestion surfaces**, but **tool execution and “enterprise-grade runtime isolation” are still partially stubbed**.

## Subproject/component matrix

Legend: docs `D0–D4`, code `C0–C5`, wired `W0–W2` (see `docs/Smartbeez_Repo_Component_Status/00_rating_scale.md`).

| Subproject / component | What it is | Docs evidence | Code evidence | Tests evidence | Status (Docs/Code/Wired) | Notes (doc↔code drift / gaps) |
|---|---|---|---|---|---|---|
| `0-frontend-landing` | Landing site | (various marketing docs) | `/home/marvin/Projects/sb_agent_hub/0-frontend-landing/*` | (not assessed) | D0 / C3 / W1 | Implemented as a frontend; not a core integration surface. |
| `1-frontend-user` | End-user app (chat UI, CopilotKit/AG‑UI client patterns, auth context) | `/home/marvin/Projects/sb_agent_hub/docs/COPILOTKIT_*` | `/home/marvin/Projects/sb_agent_hub/1-frontend-user/app/*`, `/home/marvin/Projects/sb_agent_hub/1-frontend-user/contexts/AuthContext.tsx` | (not assessed) | D2 / C3 / W1 | Auth flow has explicit TODOs for “OAuth through backend for secure cookie handling” in `/home/marvin/Projects/sb_agent_hub/1-frontend-user/contexts/AuthContext.tsx`. |
| `2-frontend-admin` | Admin app (tenants/users/tools/etc) | `/home/marvin/Projects/sb_agent_hub/docs/architecture/*` | `/home/marvin/Projects/sb_agent_hub/2-frontend-admin/src/*` | (not assessed) | D2 / C3 / W1 | App exists but includes TODOs like “add authentication logic” in `/home/marvin/Projects/sb_agent_hub/2-frontend-admin/src/App.tsx`. |
| `3-backend` API (core) | FastAPI backend, user/admin separation, middleware | `/home/marvin/Projects/sb_agent_hub/docs/architecture/*`, `/home/marvin/Projects/sb_agent_hub/docs/security/*` | `/home/marvin/Projects/sb_agent_hub/3-backend/app/main.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/*` | `/home/marvin/Projects/sb_agent_hub/3-backend/tests/*` | D2 / C3 / W2 | Real API router structure exists; multiple “main_*” variants suggest experimentation (`main.py`, `main_complete_db.py`, etc.). |
| Webchat streaming (AG‑UI) | SSE endpoints for chat/agent streaming | `/home/marvin/Projects/sb_agent_hub/docs/COPILOTKIT_AG_UI_IMPLEMENTATION.md` | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/ag_ui_langgraph.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/agui.py` | (limited) | D2 / C3 / W2 | This is one of the more “real” runtime-facing surfaces in this repo. |
| WebSocket chat + voice WS | Realtime chat socket and voice websocket | `/home/marvin/Projects/sb_agent_hub/docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md` | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/websocket.py` | (limited) | D2 / C2 / W1 | Exists; production hardening depends on auth, backpressure, and message routing decisions. |
| Voice webhook ingestion | Provider webhooks → normalize/store/trigger | `/home/marvin/Projects/sb_agent_hub/docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md` | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/voice.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/voice_service.py` | (limited) | D2 / C2 / W1 | Explicit TODO for signature verification in `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/voice.py`. |
| “Workflow engine” (LangGraph) | Local orchestration/state machine layer | (some docs reference orchestration) | `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/workflow_engine.py` | (limited) | D1 / C2 / W1 | Significant code exists; tool execution and streaming are partly stubbed and provider integrations are TODO (e.g. Composio/MCP TODO in `workflow_engine.py`). |
| Agent runtime service | Executes agents / isolation concepts | (scattered docs) | `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/agent_runtime_service.py` | (limited) | D1 / C2 / W1 | Explicit TODOs for process/container/BYOA isolation in `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/agent_runtime_service.py`. |
| Tools (execution) | Tool model + execution backends | (many docs mention tools) | `/home/marvin/Projects/sb_agent_hub/3-backend/app/tools/base.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/tasks/tool_tasks.py` | (limited) | D2 / C1 / W0 | Tool execution is explicitly not implemented (`NotImplementedError` in `app/tools/base.py`; TODO in `app/tasks/tool_tasks.py`). |
| Background jobs (Celery) | Task queue + beat schedule | (docs mention infra) | `/home/marvin/Projects/sb_agent_hub/3-backend/app/core/celery_app.py`, `/home/marvin/Projects/sb_agent_hub/docker-compose.yml` | (limited) | D1 / C3 / W1 | Celery is configured with Redis broker/backend; “production semantics” depend on broker choice and idempotency patterns. |
| Cache / rate limiting | Redis cache and middleware | (some docs) | `/home/marvin/Projects/sb_agent_hub/3-backend/app/core/cache.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/middleware/rate_limiter.py` | (limited) | D1 / C2 / W1 | Rate limiter has TODOs for proper JWT extraction and tiered limits (`rate_limiter.py`). |
| `4-cluster` | K8s/cluster configuration + scripts | `/home/marvin/Projects/sb_agent_hub/4-cluster/docs/*` | `/home/marvin/Projects/sb_agent_hub/4-cluster/*` | (n/a) | D2 / C2 / W0 | Valuable infra artifacts exist; doesn’t guarantee app/runtime semantics are complete. |

## Backend breakdown (`3-backend/app/*`)

### API surface (`3-backend/app/api/*`)

| Area | What it contains | Code evidence | Status (Docs/Code/Wired) | Notes |
|---|---|---|---|---|
| User API | chat/AG‑UI/CopilotKit/voice/websocket/orgs/etc. | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/*` | D2 / C3 / W2 | Multiple “variants” exist (e.g. many `copilotkit_*.py` files); treat as experimentation that should be consolidated. |
| Admin API | tenants/users/billing/audit/system | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/admin/*` | D2 / C2 / W1 | Present; completeness depends on DB/schema wiring and auth hardening. |
| Shared API | shared auth + health | `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/shared/*` | D1 / C2 / W2 | Exists and wired into `main.py`. |

### Core services (`3-backend/app/services/*`)

Key implemented service modules include:
- Agent/runtime orchestration: `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/agent_runtime_service.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/workflow_engine.py`
- Voice and communications: `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/voice_service.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/communication_orchestrator.py`
- Auth/tenancy/platform: `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/auth_service.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/workos_service.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/supabase_service.py`
- Tooling scaffolding: `/home/marvin/Projects/sb_agent_hub/3-backend/app/services/workflow_service.py` (but execution remains incomplete; see tools section)

### Background tasks (`3-backend/app/tasks/*`)

- Celery tasks are organized by domain: `/home/marvin/Projects/sb_agent_hub/3-backend/app/tasks/*`
- Several task modules are placeholders with TODOs (e.g. deployments, tools, usage): `/home/marvin/Projects/sb_agent_hub/3-backend/app/tasks/deployment_tasks.py`, `/home/marvin/Projects/sb_agent_hub/3-backend/app/tasks/tool_tasks.py`

### Tools (`3-backend/app/tools/*`)

- Tool base class explicitly requires implementation: `/home/marvin/Projects/sb_agent_hub/3-backend/app/tools/base.py`
- “Tool modules” exist (analysis/api/database), but execution and provider integration are not complete: `/home/marvin/Projects/sb_agent_hub/3-backend/app/tools/*`

## “Doc says X, code does Y” highlights (examples)

- **Tool execution** is a core pillar in docs, but the backend explicitly raises `NotImplementedError` for tool execution (`/home/marvin/Projects/sb_agent_hub/3-backend/app/tools/base.py`), and Celery tool tasks are TODO (`/home/marvin/Projects/sb_agent_hub/3-backend/app/tasks/tool_tasks.py`).
- **Voice ingestion** exists in code, but security hardening is incomplete (TODO signature verification in `/home/marvin/Projects/sb_agent_hub/3-backend/app/api/user/voice.py`).
- **Runtime isolation / enterprise execution** is described as needed, but the AgentRuntimeService has TODOs for process/container/BYOA runtime (`/home/marvin/Projects/sb_agent_hub/3-backend/app/services/agent_runtime_service.py`).
