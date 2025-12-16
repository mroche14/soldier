# Appendix: File Index (Traceability)

This appendix is a **file-backed index** of the main sources referenced by the integration study.

It is intentionally grouped by “surface” (tools, channels, events, auth, config) so you can jump from a conclusion in the report to the underlying spec/code quickly.

---

## A) soldier (Ruche) — Specs / Docs

### A.1 ACF + runtime architecture

- `docs/acf/architecture/ACF_ARCHITECTURE.md` — canonical architecture boundaries (ACF vs Agent vs Toolbox vs ChannelGateway)
- `docs/acf/architecture/ACF_SPEC.md` — detailed spec; includes contracts and examples
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md` — AgentRuntime/AgentContext/Brain + toolbox integration intent
- `docs/acf/architecture/LOGICAL_TURN_VISION.md` — “message ≠ turn” framing (LogicalTurn)
- `docs/acf/architecture/ACF_JUSTIFICATION.md` — rationale for ACF and design choices

### A.2 ACF deep topics (supporting docs)

- `docs/acf/architecture/topics/04-side-effect-policy.md` — tool side-effect classification semantics
- `docs/acf/architecture/topics/10-channel-capabilities.md` — ChannelPolicy as single source of truth
- `docs/acf/architecture/topics/12-idempotency.md` — 3-layer idempotency concept
- `docs/acf/architecture/topics/06-hatchet-integration.md` — durable orchestration expectations

### A.3 Tools / toolbox specification

- `docs/acf/architecture/TOOLBOX_SPEC.md` — Toolbox/ToolGateway/ToolHub boundary (discovery vs execution)
- `docs/focal_brain/implementation/phase-07-tool-execution-checklist.md` — tool execution checklist in the brain pipeline
- `docs/design/domain-model.md` — includes tool-related entities in the domain map

### A.4 Channels / routing / events / API layer

- `docs/architecture/channel-gateway.md` — external ChannelGateway responsibilities (normalize + identity resolution)
- `docs/architecture/api-layer.md` — intended ingress envelope (tenant/agent resolved upstream)
- `docs/architecture/event-model.md` — authoritative ACFEvent model and payload conventions
- `docs/architecture/webhook-system.md` — webhook subscription design (proposed)
- `docs/architecture/kernel-agent-integration.md` — multi-plane architecture (control plane + channel + cognitive + tool)
- `docs/architecture/architecture_reconsideration.md` — clarified decisions + ingress contract framing

---

## B) soldier (Ruche) — Implementation

### B.1 Current public API entry points (what sb_agent_hub can call today)

- `ruche/api/routes/turns.py` — `POST /v1/chat`, `POST /v1/chat/stream` (alignment-engine path)
- `ruche/api/models/chat.py` — `ChatRequest`/`ChatResponse` and stream event models
- `ruche/api/middleware/auth.py` — JWT auth requirement (`RUCHE_JWT_SECRET`)

### B.2 Runtime ACF (events, routing, orchestration primitives)

```text
ruche/runtime/acf/commit_point.py
ruche/runtime/acf/event_router.py
ruche/runtime/acf/events.py
ruche/runtime/acf/gateway.py
ruche/runtime/acf/models.py
ruche/runtime/acf/mutex.py
ruche/runtime/acf/supersede.py
ruche/runtime/acf/turn_manager.py
ruche/runtime/acf/workflow.py
```

### B.3 Runtime toolbox / ToolGateway (primary implementation)

```text
ruche/runtime/toolbox/context.py
ruche/runtime/toolbox/gateway.py
ruche/runtime/toolbox/models.py
ruche/runtime/toolbox/toolbox.py
```

### B.4 Runtime idempotency (separate interface)

```text
ruche/runtime/idempotency/cache.py
ruche/runtime/idempotency/models.py
```

### B.5 Runtime channels (outbound-focused, policy hooks)

```text
ruche/runtime/channels/adapter.py
ruche/runtime/channels/gateway.py
ruche/runtime/channels/models.py
ruche/runtime/channels/adapters/webchat.py
```

### B.6 Webhook subsystem (present, not wired to events)

```text
ruche/api/webhooks/models.py
ruche/api/webhooks/dispatcher.py
ruche/api/webhooks/routes.py
```

### B.7 MCP discovery API (present, placeholder ToolDefinition sourcing)

```text
ruche/api/mcp/server.py
ruche/api/mcp/handlers.py
```

### B.8 Duplicated / legacy “infrastructure” stacks (conflict with runtime)

```text
ruche/infrastructure/toolbox/toolbox.py
ruche/infrastructure/toolbox/gateway.py
ruche/infrastructure/toolbox/models.py
ruche/infrastructure/toolbox/policies.py
ruche/infrastructure/toolbox/providers/http.py
ruche/infrastructure/toolbox/providers/composio.py
ruche/infrastructure/toolbox/providers/internal.py

ruche/infrastructure/channels/gateway.py
ruche/infrastructure/channels/models.py
ruche/infrastructure/channels/adapters/simple_webchat.py
ruche/infrastructure/channels/adapters/agui_webchat.py
ruche/infrastructure/channels/adapters/twilio_whatsapp.py
ruche/infrastructure/channels/adapters/smtp_email.py
```

### B.9 Brain-level tool models (string tool IDs; “ToolHub-managed tools”)

- `ruche/brains/focal/models/tool_binding.py`
- `ruche/brains/focal/models/tool_activation.py`

### B.10 Tests relevant to the studied surfaces

```text
tests/unit/runtime/toolbox/test_toolbox.py
tests/unit/runtime/channels/test_gateway.py
tests/unit/runtime/acf/test_event_router.py
tests/unit/runtime/acf/test_turn_manager.py
tests/unit/runtime/idempotency/test_cache.py
tests/unit/runtime/test_brain_factory.py
```

---

## C) sb_agent_hub — Docs (Integration-Relevant)

### C.1 Platform blueprint (control plane + routing + tools intent)

- `sb_agent_hub/docs/architecture/SMARTBEEZ_AGENT_PLATFORM_COMPLETE_ARCHITECTURE_V2.md`
- `sb_agent_hub/docs/architecture/AGENT_PLATFORM_DEEP_ANALYSIS_REPORT.md`
- `sb_agent_hub/docs/architecture/ai_agent_hub_functional_technical_specification_v_3.md` (includes “Agent Runtime Gateway” for external runtimes)

### C.2 CopilotKit / AG‑UI architecture

- `sb_agent_hub/docs/COPILOTKIT_FINAL_ARCHITECTURE.md`
- `sb_agent_hub/docs/COPILOTKIT_AG_UI_IMPLEMENTATION.md`
- `sb_agent_hub/docs/COPILOTKIT_IMPLEMENTATION_COMPLETE.md`

### C.3 Voice architecture

- `sb_agent_hub/docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md`

---

## D) sb_agent_hub — Implementation

### D.1 Frontend proxy layer (CopilotKit → backend AG‑UI)

These files matter because they define what the browser expects, and how the frontend currently proxies to the backend:

```text
sb_agent_hub/1-frontend-user/app/api/copilotkit/route.ts
sb_agent_hub/1-frontend-user/app/api/copilotkit/stream/route.ts
```

### D.2 Backend AG‑UI streaming endpoint (current implementation)

- `sb_agent_hub/3-backend/app/api/user/ag_ui_langgraph.py` — AG‑UI SSE event stream (RUN_STARTED/TEXT_MESSAGE_CHUNK/…)

### D.3 Backend channel endpoints (websocket, voice)

```text
sb_agent_hub/3-backend/app/api/user/websocket.py
sb_agent_hub/3-backend/app/api/user/voice.py
```

### D.4 Tool-related code (current state: mostly placeholders)

```text
sb_agent_hub/3-backend/app/tools/base.py
sb_agent_hub/3-backend/app/tools/api_tools.py
sb_agent_hub/3-backend/app/tools/database_tools.py
sb_agent_hub/3-backend/app/tools/analysis_tools.py

sb_agent_hub/3-backend/app/tasks/tool_tasks.py
sb_agent_hub/3-backend/app/services/workflow_engine.py
```

### D.5 Auth / tenant scoping entry points (context for service-to-service boundary)

```text
sb_agent_hub/3-backend/app/api/shared/auth.py
sb_agent_hub/3-backend/app/services/auth_service.py
sb_agent_hub/3-backend/app/services/workos_service.py
```

---

## E) This Study’s Report Files (soldier)

```text
docs/Smartbeez_Integration_Study/README.md
docs/Smartbeez_Integration_Study/00_tracking.md
docs/Smartbeez_Integration_Study/01_system_map.md
docs/Smartbeez_Integration_Study/02_soldier_tools_deep_dive.md
docs/Smartbeez_Integration_Study/03_soldier_channels_events_webhooks.md
docs/Smartbeez_Integration_Study/04_sb_agent_hub_platform_overview.md
docs/Smartbeez_Integration_Study/05_sb_agent_hub_channels_agui_voice.md
docs/Smartbeez_Integration_Study/06_integration_architecture_and_contracts.md
docs/Smartbeez_Integration_Study/07_gap_analysis_and_workplan.md
docs/Smartbeez_Integration_Study/08_appendix_file_index.md
docs/Smartbeez_Integration_Study/09_integration_decision_questions.md
docs/Smartbeez_Integration_Study/10_kernel_agent_deep_dive.md
```

---

## F) kernel_agent (3rd Repo) — Key Sources Referenced

### F.1 Repo overview + principles

- `kernel_agent/README.md`
- `kernel_agent/docs/target/architecture_v3.md`
- `kernel_agent/docs/target/architecture_v4_toolhub.md`
- `kernel_agent/docs/target/Execution Pattern Decision.md`
- `kernel_agent/docs/target/Parlant Integration & Multi-Plane Architecture.md` (historical Parlant framing)

### F.2 Channel gateway + router contract

- `kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`
- `kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py`
- `kernel_agent/apps/channel-gateway/src/channel_gateway/models/envelope.py`
- `kernel_agent/apps/channel-gateway/src/channel_gateway/services/channel_resolver.py`
- `kernel_agent/apps/channel-gateway/src/channel_gateway/services/deduplication.py`
- `kernel_agent/apps/channel-gateway/src/channel_gateway/workers/outbound.py`

### F.3 ToolHub (catalog + activation + execution)

- `kernel_agent/docs/target/toolhub_architecture.md`
- `kernel_agent/apps/toolhub/src/toolhub/api/execution.py`
- `kernel_agent/apps/toolhub/src/toolhub/services/execution.py`
- `kernel_agent/apps/toolhub/src/toolhub/models/execution.py`

### F.4 Control plane publish workflow (Redis bundles + pointer)

- `kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py`
- `kernel_agent/apps/control-api/src/control_api/publisher/bundle_writer.py`
- `kernel_agent/apps/control-api/src/control_api/publisher/pointer_manager.py`
- `kernel_agent/apps/control-api/src/control_api/publisher/cache_invalidator.py`
- `kernel_agent/libs/clients/redis/keys.py`
- `kernel_agent/libs/core/idempotency.py`
