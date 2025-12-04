# Feature Specification: API CRUD Operations

**Feature Branch**: `001-api-crud`
**Created**: 2025-11-29
**Status**: Draft
**Input**: User description: "Implement CRUD API endpoints for agent configuration management based on phase 14"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Management (Priority: P1)

Platform administrators need to create, configure, and manage AI agents through a RESTful API. This allows non-developers to set up new conversational AI agents without code changes, enabling self-service agent creation and modification.

**Why this priority**: Agents are the top-level container for all other configuration entities (rules, scenarios, templates). Without agent management, no other CRUD operations are meaningful.

**Independent Test**: Can be fully tested by creating an agent via API, retrieving it, updating its settings, and deleting it. Delivers immediate value by enabling programmatic agent lifecycle management.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** they POST a new agent configuration, **Then** the system creates the agent and returns its unique identifier with 201 status
2. **Given** an existing agent, **When** an administrator requests its details, **Then** the system returns complete agent configuration including settings and stats
3. **Given** an existing agent, **When** an administrator updates its settings, **Then** the changes are persisted and the updated configuration is returned
4. **Given** an existing agent, **When** an administrator deletes it, **Then** the agent is soft-deleted and no longer accessible
5. **Given** multiple agents exist, **When** an administrator lists agents with pagination, **Then** the system returns a paginated list with total count

---

### User Story 2 - Rule Management (Priority: P1)

Content authors need to define behavioral rules that guide agent responses. Rules specify conditions (when to apply) and actions (how to behave), enabling dynamic agent behavior modification without redeployment.

**Why this priority**: Rules are the core mechanism for controlling agent behavior. They determine what the agent says and does in specific situations, making them essential for any functional agent.

**Independent Test**: Can be fully tested by creating rules for an agent, searching/filtering rules, updating rule priorities, and deleting obsolete rules. Delivers value by enabling behavior customization.

**Acceptance Scenarios**:

1. **Given** an authenticated user with an agent, **When** they create a new rule with condition and action text, **Then** the system stores the rule and automatically generates embeddings for semantic matching
2. **Given** an agent with multiple rules, **When** a user lists rules with scope filter, **Then** only rules matching the scope (global/scenario/step) are returned
3. **Given** an existing rule, **When** a user updates the condition text, **Then** the system recomputes the embedding to maintain search accuracy
4. **Given** multiple rules to modify, **When** a user submits a bulk operation request, **Then** all operations are processed and individual results are returned
5. **Given** an agent with rules, **When** a user searches by priority range, **Then** only rules within that priority range are returned

---

### User Story 3 - Scenario Management (Priority: P2)

Conversation designers need to create and manage multi-step conversational flows. Scenarios define structured journeys that guide users through specific processes (e.g., returns, onboarding, troubleshooting).

**Why this priority**: Scenarios provide structured conversation flows, which are important for complex interactions but not required for basic agent functionality (global rules can work without scenarios).

**Independent Test**: Can be fully tested by creating a scenario with multiple steps, defining transitions between steps, and verifying the complete flow structure. Delivers value by enabling structured conversation design.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they create a scenario with steps and transitions, **Then** the system stores the complete flow structure and auto-generates step IDs
2. **Given** an existing scenario, **When** a user adds a new step, **Then** the step is added and can be referenced in transitions
3. **Given** a scenario step, **When** a user updates its transitions, **Then** the navigation flow is updated accordingly
4. **Given** a scenario with multiple steps, **When** a user deletes a non-entry step, **Then** the step is removed and transitions pointing to it are flagged
5. **Given** an entry step, **When** a user attempts to delete it, **Then** the system prevents deletion and returns an error

---

### User Story 4 - Template Management (Priority: P2)

Content authors need to create pre-written response templates that ensure consistent messaging. Templates can be suggested to the agent, used exclusively, or as fallbacks when generation fails.

**Why this priority**: Templates improve response consistency and quality but agents can function with purely generated responses. Templates become more valuable as agents mature.

**Independent Test**: Can be fully tested by creating templates with variables, previewing with sample data, and verifying variable substitution. Delivers value by enabling controlled response content.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they create a template with variable placeholders, **Then** the system stores it and identifies the variables used
2. **Given** an existing template, **When** a user requests a preview with sample variables, **Then** the system renders the template and returns the substituted text
3. **Given** templates with different modes, **When** a user filters by mode (suggest/exclusive/fallback), **Then** only matching templates are returned
4. **Given** a template scoped to a step, **When** a user changes its scope, **Then** the template is re-scoped accordingly

---

### User Story 5 - Variable Management (Priority: P3)

System integrators need to define dynamic context variables that are resolved at runtime. Variables connect agent behavior to external data sources like customer profiles or order systems.

**Why this priority**: Variables enable dynamic data injection but require tool integrations to be fully useful. Basic agent functionality works with static configurations.

**Independent Test**: Can be fully tested by defining a variable with update policy and cache settings. Delivers value by enabling dynamic context resolution.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they create a variable with a resolver tool reference, **Then** the variable definition is stored with its update policy
2. **Given** an existing variable, **When** a user updates the cache TTL, **Then** subsequent resolutions respect the new TTL
3. **Given** multiple variables, **When** a user lists them, **Then** all variable definitions are returned with their resolver information

---

### User Story 6 - Tool Activation Management (Priority: P3)

Integration administrators need to enable or disable tools for specific agents. Tools are defined externally but their activation and policy overrides are agent-specific.

**Why this priority**: Tool activation is a configuration concern that builds on existing tool definitions. Agents can work with default tool configurations initially.

**Independent Test**: Can be fully tested by enabling/disabling tools for an agent and overriding policy settings. Delivers value by enabling per-agent tool customization.

**Acceptance Scenarios**:

1. **Given** available tools in the system, **When** an administrator enables a tool for an agent, **Then** the tool becomes available for that agent's conversations
2. **Given** an enabled tool, **When** an administrator disables it, **Then** the tool is no longer used in new conversations
3. **Given** an enabled tool, **When** an administrator provides policy overrides, **Then** the overrides apply to that agent's tool usage

---

### User Story 7 - Publishing and Versioning (Priority: P2)

Platform operators need to publish configuration changes to make them live and roll back to previous versions if issues arise. This ensures controlled deployment of agent changes.

**Why this priority**: Publishing provides change control and safety, which is important for production environments but not strictly required for development/testing.

**Independent Test**: Can be fully tested by making changes, publishing them, verifying the version increment, and rolling back. Delivers value by enabling safe configuration deployment.

**Acceptance Scenarios**:

1. **Given** unpublished changes to an agent, **When** an operator checks publish status, **Then** the system shows pending changes summary
2. **Given** unpublished changes, **When** an operator publishes, **Then** changes become live and version increments
3. **Given** a published version with issues, **When** an operator rolls back to a previous version, **Then** the previous configuration is restored
4. **Given** a publish in progress, **When** an operator checks job status, **Then** the system shows progress through validation, compilation, and deployment stages

---

### Edge Cases

- Agent deletion is immediate regardless of active sessions; deleted agents stop responding instantly
- Bulk operations return partial success: each operation reports individual success/failure with error details; the batch continues processing even if some operations fail
- When a scenario step is deleted while active sessions are on it, sessions continue on cached step configuration until next transition; the step deletion does not interrupt ongoing conversations
- When embedding provider is temporarily unavailable during rule create/update, the rule is saved without embedding and queued for background retry with exponential backoff (max 3 retries over 15 minutes)
- When publishing fails mid-stage, the system automatically rolls back to the previous stable version and reports the failed stage with error details in the publish job status
- Circular transitions in scenarios are allowed (intentional loops); unreachable steps (not reachable from entry) are flagged as validation warnings on save but do not block creation
- When a template references a variable that doesn't exist, preview renders the literal placeholder (e.g., "{unknown_var}") and logs a warning; runtime substitution behaves the same way

## Requirements *(mandatory)*

### Functional Requirements

#### Agent Management
- **FR-001**: System MUST allow creation of agents with name, description, and optional settings
- **FR-002**: System MUST generate unique identifiers for new agents
- **FR-003**: System MUST track agent versions and increment on publish
- **FR-004**: System MUST support soft-delete for agents (set deleted_at timestamp)
- **FR-005**: System MUST validate agent names are non-empty and within length limits
- **FR-006**: System MUST track agent statistics (total sessions, turns, averages)

#### Rule Management
- **FR-007**: System MUST allow creation of rules with condition_text, action_text, scope, and priority
- **FR-008**: System MUST automatically compute embeddings when condition_text or action_text changes
- **FR-009**: System MUST support three scope levels: global, scenario, and step
- **FR-010**: System MUST support rule filtering by scope, scope_id, enabled status, and priority range
- **FR-011**: System MUST support bulk operations (create, update, delete) for rules
- **FR-012**: System MUST track max_fires_per_session and cooldown_turns for rules

#### Scenario Management
- **FR-013**: System MUST allow creation of scenarios with steps and transitions
- **FR-014**: System MUST auto-generate step IDs when not provided
- **FR-015**: System MUST validate that entry_step_id points to a valid step
- **FR-016**: System MUST prevent deletion of entry steps without reassignment
- **FR-017**: System MUST validate transition references point to existing steps
- **FR-018**: System MUST support tagging scenarios for organization

#### Template Management
- **FR-019**: System MUST allow creation of templates with text containing variable placeholders
- **FR-020**: System MUST identify and store list of variables used in template text
- **FR-021**: System MUST support three template modes: suggest, exclusive, fallback
- **FR-022**: System MUST provide template preview with variable substitution
- **FR-023**: System MUST support template scoping (global, scenario, step)

#### Variable Management
- **FR-024**: System MUST allow creation of variables with resolver_tool_id and update_policy
- **FR-025**: System MUST support configurable cache TTL for variable values
- **FR-026**: System MUST support update policies: on_session_start, on_demand, periodic

#### Tool Activation
- **FR-027**: System MUST allow enabling/disabling tools for specific agents
- **FR-028**: System MUST support policy overrides (e.g., timeout) when enabling tools
- **FR-029**: System MUST track enable/disable timestamps

#### Publishing
- **FR-030**: System MUST track unpublished changes since last publish
- **FR-031**: System MUST provide publish status with change summary
- **FR-032**: System MUST support version rollback to previous configurations
- **FR-033**: System MUST report publish job progress through stages

#### Common API Patterns
- **FR-034**: System MUST support pagination with limit, offset, and total count
- **FR-035**: System MUST support sorting by specified fields and directions
- **FR-036**: System MUST return consistent error responses with code, message, and details
- **FR-037**: System MUST validate JWT authentication for all endpoints
- **FR-038**: System MUST extract tenant_id from JWT claims
- **FR-039**: System MUST scope all queries by tenant_id to prevent data leakage

### Key Entities

- **Agent**: Top-level container for conversational AI configuration; has name, description, enabled status, settings, and version tracking
- **Rule**: Behavioral policy with condition (when) and action (how); has scope, priority, and optional tool/template attachments
- **Scenario**: Multi-step conversational flow; contains ordered steps with transitions defining navigation
- **ScenarioStep**: Individual state in a scenario; has name, transitions, and attached templates/rules/tools
- **Template**: Pre-written response text with variable placeholders; has mode (suggest/exclusive/fallback) and scope
- **Variable**: Dynamic context definition; references resolver tool and defines caching/update policy
- **ToolActivation**: Per-agent tool enablement status with optional policy overrides
- **PublishJob**: Tracks publish operation progress through validation, compilation, and deployment stages

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All CRUD operations complete within 500ms under normal load (excludes embedding computation)
- **SC-002**: System handles 100 concurrent configuration API requests without error rate increase
- **SC-003**: Bulk operations process 50 rules in a single request within 5 seconds
- **SC-004**: Template preview renders within 100ms regardless of template complexity
- **SC-005**: Publish operations complete all stages within 30 seconds for agents with up to 100 rules
- **SC-006**: Rollback operations restore previous configuration within 10 seconds
- **SC-007**: 100% of API endpoints return appropriate error codes with actionable error messages
- **SC-008**: Zero cross-tenant data exposure in all API responses (tenant isolation verified)
- **SC-009**: All list endpoints support pagination and return accurate total counts
- **SC-010**: Embedding recomputation for updated rules completes asynchronously without blocking the API response

## Clarifications

### Session 2025-11-29

- Q: What happens when deleting an agent that has active sessions? → A: Agent deletion is immediate; the agent stops responding to all sessions.

## Assumptions

- JWT authentication infrastructure is already in place (implemented in Phase 13)
- ConfigStore interface and in-memory implementation exist (implemented in Phase 4)
- Embedding provider interface and factory exist (implemented in Phase 5)
- Domain models for Rule, Scenario, Template, Variable exist (implemented in Phase 3)
- Rate limiting middleware is already implemented (implemented in Phase 13)
- Audit logging infrastructure captures all mutations automatically
- Agent statistics (FR-006) are computed on-demand from AuditStore turn records; no separate stats storage required
