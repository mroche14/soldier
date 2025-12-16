# Prompt Blueprint: Voice Integration Study Agent

You are an agent tasked with producing an **exhaustive voice integration report** to connect:

- `sb_agent_hub` (SmartBeez Agent Hub) voice channel stack
- `soldier` (Ruche runtime + ACF + brains) voice turn processing + tool semantics

The output must be written into this folder as multiple markdown files (create them as needed), and must be **file-backed**: every claim should point to concrete files/paths in the repos, plus any relevant external vendor docs.

## Workspace context

- Current repo: `soldier` (cwd: `/home/marvin/Projects/soldier`)
- Adjacent repo: `sb_agent_hub` at `/home/marvin/Projects/sb_agent_hub`
- You may read both repos; prefer `rg` and `find` to locate relevant code and docs.

## Primary goal

Produce a voice-focused integration design that answers:

1) What is the current state of voice ingestion/streaming in `sb_agent_hub`?
2) What is the intended voice channel model in `soldier` (ACF + channel specs)?
3) What is the best provider choice and integration strategy for enterprise-grade voice (SIP/telephony, streaming ASR/TTS, barge-in, function calls, compliance)?
4) What is the recommended boundary between the repos for voice:
   - where does call/session state live?
   - who speaks provider webhooks?
   - how are transcripts turned into ACF messages/LogicalTurns?
   - how are tools executed and results fed back into the voice call?

## Deliverables (write these files)

Create the following files in `docs/Smartbeez_Voice_Integration_Study/`:

1) `01_current_state_sb_agent_hub_voice.md`
   - Inventory code paths, endpoints, data models, DB tables used for voice.
   - Key files to start:
     - `sb_agent_hub/3-backend/app/api/user/voice.py`
     - `sb_agent_hub/3-backend/app/services/voice_service.py`
     - `sb_agent_hub/docs/architecture/VOICE_CHANNEL_IMPLEMENTATION_GUIDE_V3.md`
     - any websocket voice support in `sb_agent_hub/3-backend/app/api/user/websocket.py`

2) `02_soldier_voice_requirements_acf_fit.md`
   - Extract voice-relevant semantics from soldier docs:
     - `docs/acf/architecture/ACF_ARCHITECTURE.md`
     - `docs/architecture/api-layer.md` (multimodal ingress envelope)
     - `docs/architecture/channel-gateway.md`
     - `docs/acf/architecture/topics/03-adaptive-accumulation.md` (message ≠ turn)
     - `docs/acf/architecture/topics/10-channel-capabilities.md`
   - Identify what soldier currently implements vs only specifies.

3) `03_provider_landscape_and_recommendation.md`
   - **Search the internet** for up-to-date provider capabilities and choose a recommended default:
     - Vapi
     - Bland.ai
     - Twilio (Voice)
     - Plivo
     - Vonage
     - Daily/LiveKit (if doing webRTC-style voice)
     - Any other serious enterprise option
   - Evaluate with an explicit rubric:
     - streaming ASR quality + languages
     - streaming TTS quality + voices
     - interruption/barge-in support
     - tool/function call support (and how it’s represented)
     - SIP / PSTN / phone number provisioning
     - webhooks reliability, retries, signatures
     - latency profile + SLAs
     - compliance: call recording, retention, data residency
     - pricing model + observability
   - Include links to vendor docs/pricing pages and summarize relevant constraints.

4) `04_integration_architecture_voice.md`
   - The target data flow for a voice call:
     - provider → sb_agent_hub webhooks/stream → soldier ingress → soldier response/events → sb_agent_hub → provider
   - Define concrete contracts:
     - voice event normalization schema (partial transcript vs final transcript vs tool-call events)
     - correlation IDs (tenant/org, agent, session/call, turn/run)
     - idempotency keys for provider retries
     - how “barge-in” maps to ACF supersede/absorb decisions
     - how tool calls are executed (soldier semantics vs sb_agent_hub execution)

5) `05_gap_list_and_mvp_plan_voice.md`
   - The smallest “working voice MVP” and the hardening plan.

6) `06_appendix_file_index_voice.md`
   - A path index of all reviewed files (soldier + sb_agent_hub) relevant to voice.

## Constraints / standards for the report

- Be exhaustive: scan both repos for `voice`, `vapi`, `twilio`, `sip`, `call`, `webhook`, `transcript`, `barge`, `interrupt`, `tts`, `asr`.
- Prefer documenting “what is real in code” vs “what is only in docs”.
- Do not invent new architecture patterns unless you mark them as “proposal”; align with soldier’s own boundaries: ChannelGateway/MessageRouter are intended to be external to the cognitive runtime.
- Include a “decisions required” section that points back to: `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md`.

## How to run the study (mechanical checklist)

1) File inventory:
   - `find /home/marvin/Projects/sb_agent_hub -maxdepth 4 -type f | rg -n "voice|vapi|twilio|sip|call|transcript"`
   - `find /home/marvin/Projects/soldier -maxdepth 4 -type f | rg -n "voice|audio|call|channel|webhook|turn|supersede"`
2) Read core voice docs in sb_agent_hub and soldier.
3) Identify the exact inbound events in sb_agent_hub voice webhook handling, and what is persisted.
4) Draft the target integration sequence and concrete request/response schema.
5) Do external provider research on the web; document sources and tradeoffs.

