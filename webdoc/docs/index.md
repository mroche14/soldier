# Focal Documentation

Production-grade cognitive engine for business-aligned agents. API-first, multi-tenant, fully persistent—built to enforce policy, not just prompt.

## Why Focal
- Zero in-memory state: any pod can serve any request, everything goes through stores.
- Explicit policy alignment: scenarios, rules, templates, and enforcement sit in the turn pipeline.
- Pluggable by design: providers (LLM/embedding/rerank) and stores are interface-first.
- Hot-reloadable configuration: TOML + env overrides, validated with Pydantic.
- Deep observability: structured logs, metrics, tracing, and an immutable audit trail.

## What to read first
- Architecture overview → `project_docs/architecture/overview.md`
- Turn pipeline and alignment engine → `project_docs/design/turn-pipeline.md`, `project_docs/architecture/alignment-engine.md`
- Configuration model and loading → `project_docs/architecture/configuration-overview.md`, `project_docs/architecture/configuration-models.md`
- Vision and principles → `project_docs/vision.md`

## Primary journeys
- **Build and publish an agent**
  - Define scenarios/rules/templates: `project_docs/design/api-crud.md`, `project_specs/007-api-layer-crud/`
  - Configure providers and pipeline: `project_docs/architecture/configuration-models.md`, `project_docs/architecture/configuration-toml.md`
  - Publish and migrate safely: `project_docs/design/scenario-update-methods.md`, `project_specs/008-scenario-migration/`
- **Operate with reliability**
  - Observability: `project_docs/architecture/observability.md`
  - Enforcement and guardrails: `project_docs/architecture/alignment-engine.md`, `project_docs/design/turn-pipeline.md`
  - Audit and replay: `project_docs/architecture/memory-layer.md`, `project_docs/architecture/selection-strategies.md`
- **Extend the platform**
  - Implement new stores/providers: see API reference under Stores/Providers
  - Selection strategies and retrieval tweaks: `project_docs/architecture/selection-strategies.md`
  - External control plane integration: `project_docs/architecture/kernel-agent-integration.md`

## Quick start
```bash
# Install deps
uv sync

# Generate API reference and build docs
uv run python generate_docs.py
uv run python -m mkdocs build -f webdoc/mkdocs.yml

# Serve locally
uv run python -m mkdocs serve -f webdoc/mkdocs.yml -a 127.0.0.1:8001
```

## Reference map
- API: `project_docs/architecture/api-layer.md` and route pages under API Reference
- Alignment engine: `project_docs/architecture/alignment-engine.md`
- Memory layer: `project_docs/architecture/memory-layer.md`
- Configuration: `project_docs/architecture/configuration.md`
- Testing: `project_docs/development/testing-strategy.md`, `project_docs/development/unit-testing.md`
