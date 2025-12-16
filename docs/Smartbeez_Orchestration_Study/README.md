# SmartBeez Orchestration Study (Hatchet / Restate / Celery / Redis / RabbitMQ)

This folder compares orchestration + messaging choices across:
- `soldier` (this repo): Hatchet-centric ACF runtime + toolbox + webhooks.
- `/home/marvin/Projects/sb_agent_hub`: Celery + Redis broker/backend.
- `/home/marvin/Projects/kernel_agent`: Restate-centric durable workflows + Redis Streams message bus contracts (and optional Celery/RabbitMQ workers).

**Goal**: clarify the *minimum viable infrastructure set* and the *single coherent direction* to finish the platform without duplicating orchestration layers.

## How to use this study

1. Start with `docs/Smartbeez_Orchestration_Study/01_requirements_and_use_cases.md`.
2. Review the comparisons in `docs/Smartbeez_Orchestration_Study/02_capability_matrix.md`.
3. Pick a “minimal stack” in `docs/Smartbeez_Orchestration_Study/03_minimal_stack_recommendations.md`.
4. Translate choices into concrete repo work in `docs/Smartbeez_Orchestration_Study/04_repo_alignment_and_migration.md`.
5. Review operational “gotchas” in `docs/Smartbeez_Orchestration_Study/05_operational_notes_and_pitfalls.md`.
6. Track progress in `docs/Smartbeez_Orchestration_Study/00_tracking.md`.

## Key upstream references (internet)

- Hatchet docs: https://docs.hatchet.run/
- Hatchet concurrency (GROUP_ROUND_ROBIN, CANCEL_IN_PROGRESS): https://docs.hatchet.run/home/concurrency
- Hatchet self-host example compose (includes RabbitMQ + Postgres): https://raw.githubusercontent.com/hatchet-dev/hatchet/main/docker-compose.yml
- Restate docs: https://docs.restate.dev/
- Restate README (Durable Execution, exactly-once semantics): https://raw.githubusercontent.com/restatedev/restate/main/README.md
- Celery brokers/backends overview: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html
- Redis Streams overview: https://redis.io/docs/latest/develop/data-types/streams/

## Cross-links

- Integration decision sheet (addendum): `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md`
