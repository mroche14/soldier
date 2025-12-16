# Tracking: Smartbeez ↔ Ruche Integration Study

**Scope focus**: Tools (ToolHub/ToolGateway/Toolbox) + Channels (ChannelGateway/MessageRouter) + Event routing (ACFEvent/Webhooks/AG‑UI).

**Repos**
- `soldier` (this repo): `/home/marvin/Projects/soldier`
- `sb_agent_hub`: `/home/marvin/Projects/sb_agent_hub`
- `kernel_agent`: `/home/marvin/Projects/kernel_agent`

## 1) What This Study Tries To Answer

- What is the **actual** current state in `soldier` for Toolbox + Channel/Event routing (spec vs code)?
- What exists (and what is missing) in `sb_agent_hub` for the same concerns?
- Where are the **duplications** and **semantic mismatches**?
- What’s the cleanest integration boundary so `sb_agent_hub` can use `soldier` as the runtime/cognitive layer?

## 2) Reviewed Sources (Checklist)

### 2.1 soldier — Toolbox / ToolGateway / Tooling

- [x] `docs/acf/architecture/ACF_ARCHITECTURE.md` (canonical ownership boundaries)
- [x] `docs/acf/architecture/TOOLBOX_SPEC.md`
- [x] `docs/acf/architecture/topics/04-side-effect-policy.md`
- [x] `docs/acf/architecture/topics/12-idempotency.md`
- [x] `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- [x] `docs/acf/architecture/ACF_SPEC.md` (tool/event/idempotency sections)
- [x] `ruche/runtime/toolbox/toolbox.py`
- [x] `ruche/runtime/toolbox/gateway.py`
- [x] `ruche/runtime/toolbox/context.py`
- [x] `ruche/runtime/toolbox/models.py`
- [x] `ruche/infrastructure/toolbox/*` (duplicate/stub)
- [x] `ruche/runtime/idempotency/*`
- [x] `ruche/api/mcp/server.py` + `ruche/api/mcp/handlers.py`
- [x] `tests/unit/runtime/toolbox/test_toolbox.py`
- [x] `ruche/brains/focal/models/tool_binding.py`
- [x] `docs/focal_brain/implementation/phase-07-tool-execution-checklist.md`
- [x] `docs/architecture/kernel-agent-integration.md` (tool layer integration framing)
- [x] `ruche/api/routes/turns.py` + `ruche/api/models/chat.py` (current ingress/stream contract)

### 2.2 soldier — ChannelGateway / MessageRouter / Events / Webhooks

- [x] `docs/architecture/channel-gateway.md`
- [x] `docs/acf/architecture/topics/10-channel-capabilities.md`
- [x] `docs/architecture/event-model.md`
- [x] `docs/architecture/webhook-system.md`
- [x] `docs/architecture/api-layer.md`
- [x] `docs/architecture/architecture_reconsideration.md` (MessageRouter ingress contract)
- [x] `ruche/runtime/channels/gateway.py`
- [x] `ruche/runtime/channels/adapter.py`
- [x] `ruche/runtime/channels/models.py`
- [x] `ruche/runtime/channels/adapters/webchat.py`
- [x] `ruche/infrastructure/channels/*` (duplicate/stub)
- [x] `ruche/runtime/acf/events.py`
- [x] `ruche/runtime/acf/event_router.py`
- [x] `ruche/api/webhooks/*` (models, dispatcher, routes)
- [x] `tests/unit/runtime/channels/test_gateway.py`
- [x] `tests/unit/runtime/acf/test_event_router.py`

### 2.3 sb_agent_hub — Docs + code relevant to tools/channels

- [x] `docs/architecture/SMARTBEEZ_AGENT_PLATFORM_COMPLETE_ARCHITECTURE_V2.md` (compiler/endpoints/tools blueprint)
- [x] `docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md`
- [x] `docs/architecture/ai_agent_hub_functional_technical_specification_v_3.md` (“Agent Runtime Gateway” concept)
- [x] `docs/COPILOTKIT_FINAL_ARCHITECTURE.md`
- [x] `docs/COPILOTKIT_AG_UI_IMPLEMENTATION.md`
- [x] `docs/COPILOTKIT_IMPLEMENTATION_COMPLETE.md` (tool routing concept)
- [x] `docs/architecture/AGENT_PLATFORM_DEEP_ANALYSIS_REPORT.md` (gaps + recommended structure)
- [x] `1-frontend-user/app/api/copilotkit/stream/route.ts` (frontend proxy: CopilotKit → backend AG‑UI)
- [x] `3-backend/app/api/user/ag_ui_langgraph.py` (AG‑UI SSE)
- [x] `3-backend/app/api/user/websocket.py` (WebSocket chat + voice WS)
- [x] `3-backend/app/api/user/voice.py` + `3-backend/app/services/voice_service.py` (voice webhook ingestion)
- [x] `3-backend/app/services/workflow_engine.py` + `3-backend/app/tasks/tool_tasks.py` (tool execution placeholders)
- [x] `3-backend/app/services/agent_runtime_service.py` (LangGraph runtime service)
- [x] `3-backend/app/api/shared/auth.py` + `3-backend/app/services/auth_service.py` (auth/tenant context)

### 2.4 kernel_agent — Docs + code relevant to tools/channels/router/control-plane

- [x] `README.md` (service map)
- [x] `docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md` (Redis Streams contract + interrupt protocol)
- [x] `docs/target/architecture_v3.md` + `docs/target/architecture_v4_toolhub.md` (multi-plane + ToolHub-centric architecture)
- [x] `docs/target/Parlant Integration & Multi-Plane Architecture.md` (historical Parlant brain framing)
- [x] `docs/target/Execution Pattern Decision.md` (tool façade A/B/C + sync/async)
- [x] `apps/toolhub/src/toolhub/api/execution.py` + `apps/toolhub/src/toolhub/services/execution.py` (NDJSON streaming execution)
- [x] `apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py` (webhook verification + dedup + publish to streams)
- [x] `apps/channel-gateway/src/channel_gateway/models/envelope.py` (canonical envelope)
- [x] `apps/channel-gateway/src/channel_gateway/services/channel_resolver.py` (Supabase lookup + Redis cache)
- [x] `apps/channel-gateway/src/channel_gateway/workers/outbound.py` (outbound worker via streams)
- [x] `apps/control-api/src/control_api/publisher/publish_workflow.py` + `bundle_writer.py` (publish pipeline + Redis bundles)

## 3) Key Findings (Short)

### 3.1 Convergence thesis

- `sb_agent_hub` already behaves like the **Control Plane + Channel Layer** (auth, UI, voice/webchat protocols).
- `soldier` already contains the **Runtime/Cognitive Layer** architecture (ACF + Brain + Toolbox + event model), but **not all of it is wired together** in code yet.

### 3.2 High-impact mismatches (must resolve to integrate)

- **Tool model mismatch**: `soldier` has *two* tool systems: brain-level `ToolActivation` (string tool IDs, “ToolHub-managed tools”) and runtime-level `ToolDefinition/ToolActivation` (UUID-based, Toolbox spec). They are not wired together.
- **Event emission mismatch**: runtime Toolbox code emits ad-hoc string event types (`TOOL_SIDE_EFFECT_*`) while ACF expects `ACFEvent` objects with `ACFEventType` values like `tool.executed`.
- **Side-effect policy mismatch**: Toolbox spec defines `PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE` while ACF code currently stores `REVERSIBLE/IDEMPOTENT/IRREVERSIBLE`.
- **ChannelPolicy source-of-truth mismatch**: specs say ChannelPolicy comes from ConfigStore and is shared by ACF/Agent/ChannelGateway; runtime code loads from adapter defaults and AgentRuntime returns empty policies.
- **Webhooks are present but not integrated**: `ruche/api/webhooks/*` exists, but nothing connects ACF’s EventRouter to the WebhookDispatcher yet.
- **sb_agent_hub’s tool integrations are mostly planned** (Composio/MCP mentioned) but still placeholders in code; however, the **AG‑UI/webchat** and **voice webhook ingestion** are real and working.

## 4) Open Questions (Need Decisions)

- Where is the **system of record** for ToolDefinitions? (sb_agent_hub DB vs soldier ConfigStore vs external ToolHub service)
- Does `sb_agent_hub` want to run **LangGraph brains** itself, or should LangGraph brains be hosted inside `soldier`’s Brain interface?
- For webchat: should **AG‑UI** be produced by `sb_agent_hub` (channel layer) by mapping soldier streaming/events, or should `soldier` expose an AG‑UI compatible endpoint directly?
- Should tool execution be **sync** (ToolGateway calls vendor APIs directly) or **async** (ToolGateway enqueues to sb_agent_hub workers / Restate / Celery) by default?

## 5) Study Outputs (Where to look)

- [x] Recommended integration architecture + concrete contracts: `docs/Smartbeez_Integration_Study/06_integration_architecture_and_contracts.md`
- [x] Gap list + “do this next” work plan: `docs/Smartbeez_Integration_Study/07_gap_analysis_and_workplan.md`
- [x] Exhaustive file index referenced by this study: `docs/Smartbeez_Integration_Study/08_appendix_file_index.md`
- [x] Decision questions to finalize integration: `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md`
- [x] kernel_agent deep dive and conflicts: `docs/Smartbeez_Integration_Study/10_kernel_agent_deep_dive.md`
- [x] Orchestration/messaging stack study (Celery/RabbitMQ/Restate/Hatchet/Redis): `docs/Smartbeez_Orchestration_Study/README.md`
