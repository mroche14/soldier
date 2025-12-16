# Smartbeez ↔ Ruche (soldier) Integration Study

This folder contains an exhaustive, file-backed study of how `sb_agent_hub` (SmartBeez Agent Hub) can integrate with the `soldier` repo (Ruche runtime + FOCAL alignment brain), with a focus on the two most overlap-prone surfaces:

- **Tools**: ToolHub / ToolGateway / Toolbox
- **Channels**: ChannelGateway / MessageRouter + event routing (ACFEvents, webhooks, AG‑UI)

**Start here:**
- `docs/Smartbeez_Integration_Study/00_tracking.md` (what was reviewed + open questions + TODOs)
- `docs/Smartbeez_Integration_Study/06_integration_architecture_and_contracts.md` (recommended target architecture + contracts)
- `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md` (questions you need to answer to finalize the integration)
- `docs/Smartbeez_Integration_Study/10_kernel_agent_deep_dive.md` (3rd repo analysis: ToolHub + ChannelGateway + Redis-stream contracts)
- `docs/Smartbeez_Orchestration_Study/README.md` (cross-repo study: Hatchet/Restate/Celery/Redis/RabbitMQ and the minimum viable infra set)

## Document Index

- `docs/Smartbeez_Integration_Study/00_tracking.md` — Checklist + study log + open questions
- `docs/Smartbeez_Integration_Study/01_system_map.md` — How the two repos currently “think” about the platform (terminology + boundaries)
- `docs/Smartbeez_Integration_Study/02_soldier_tools_deep_dive.md` — Soldier Toolbox/ToolGateway: spec vs code, duplicates, drift, integration points
- `docs/Smartbeez_Integration_Study/03_soldier_channels_events_webhooks.md` — Soldier Channel/Event system: spec vs code, ACFEvent model, webhook status
- `docs/Smartbeez_Integration_Study/04_sb_agent_hub_platform_overview.md` — sb_agent_hub platform architecture: runtime, control plane, routing, persistence
- `docs/Smartbeez_Integration_Study/05_sb_agent_hub_channels_agui_voice.md` — sb_agent_hub channels: CopilotKit/AG‑UI streaming, WebSocket chat, voice webhooks
- `docs/Smartbeez_Integration_Study/06_integration_architecture_and_contracts.md` — Recommended integration architecture + concrete contracts
- `docs/Smartbeez_Integration_Study/07_gap_analysis_and_workplan.md` — Gap list + prioritized work plan to converge the repos
- `docs/Smartbeez_Integration_Study/08_appendix_file_index.md` — Exhaustive file index referenced by this study
- `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md` — Decision sheet (tables with options + justification + selection)
- `docs/Smartbeez_Integration_Study/10_kernel_agent_deep_dive.md` — kernel_agent deep dive (what to reuse, what conflicts, what to update)
- `docs/Smartbeez_Orchestration_Study/README.md` — Orchestration/messaging deep dive to resolve Celery/RabbitMQ/Restate/Hatchet/Redis choices
