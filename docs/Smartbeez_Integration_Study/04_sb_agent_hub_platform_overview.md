# sb_agent_hub Platform Overview (Integration-Relevant)

## 1) Repo Shape (Monorepo)

At `/home/marvin/Projects/sb_agent_hub`:

- `0-frontend-landing/` — marketing + auth handoff
- `1-frontend-user/` — main user workspace UI (CopilotKit chat, agent dashboard, channels/tools pages)
- `2-frontend-admin/` — admin UI
- `3-backend/` — FastAPI backend (LangGraph agent runtime + APIs)
- `4-cluster/` — legacy cluster deployment artifacts
- `docs/` — extensive architecture + implementation tracking

## 2) “Runtime” as Implemented Today

### 2.1 LangGraph/LangChain centric agent execution

Primary runtime patterns:
- LangGraph agents (graph orchestration, tool calling)
- A service layer that loads agent config from Supabase and invokes an LLM through OpenRouter, OpenAI, Anthropic, etc.

Example service:
- `3-backend/app/services/agent_runtime_service.py`
  - Creates/records agent instances in DB
  - Keeps an in-memory `active_instances` map (practical, but not soldier’s “zero state” principle)

### 2.2 Webchat runtime via AG‑UI SSE

User frontend expects AG‑UI style streaming events (via CopilotKit runtimeUrl proxy).

Key files:
- `docs/COPILOTKIT_FINAL_ARCHITECTURE.md`
- `3-backend/app/api/user/ag_ui_langgraph.py` (AG‑UI streaming endpoint)

### 2.3 Voice provider integration (VAPI/Twilio)

Key files:
- `docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md`
- `3-backend/app/api/user/voice.py`
- `3-backend/app/services/voice_service.py`

Current state in code:
- VAPI webhook ingestion writes session/transcript/function-call records
- Tool “function-call” events are logged, but not yet routed into a shared tool execution gateway

## 3) “Control Plane” as Described in Docs

The strongest control-plane blueprint is:
- `docs/architecture/SMARTBEEZ_AGENT_PLATFORM_COMPLETE_ARCHITECTURE_V2.md`

Integration-relevant ideas from that document:
- Authoring specs compile into immutable manifests with revision hashes
- The compiler creates per-channel endpoints (dynamic routing)
- Tools are bound to connected accounts (scoped access), and execution is sandboxed

Even if some of this is not fully implemented yet, the conceptual model maps well onto soldier’s “external control plane mode” and ACF architecture.

## 4) Where sb_agent_hub Already Overlaps soldier’s Intended External Layers

From soldier’s own integration docs (`docs/architecture/kernel-agent-integration.md`):
- The **Control Plane** (Admin UI + publisher + config bundles)
- The **Channel Layer** (ChannelGateway + MessageRouter)

sb_agent_hub already has:
- UI + auth + org scoping
- A backend with endpoints that can act as “ChannelGateway” for webchat + voice
- A place to house the missing “MessageRouter” data (integration IDs, endpoint routing, phone number → tenant/agent)

So sb_agent_hub is a natural home for the pieces that soldier explicitly wants externalized.

