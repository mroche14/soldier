# Feature Specification: API Layer - CRUD Operations

**Feature Branch**: `007-api-layer-crud`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Implement configuration CRUD API endpoints for managing agents, rules, scenarios, templates, and variables. Includes RESTful endpoints with pagination, filtering, bulk operations, template preview, and publishing workflow"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Rules (Priority: P1)

A configuration administrator needs to create, read, update, and delete behavioral rules for an agent. This includes listing rules with filtering, creating new rules, updating existing rules, and performing bulk operations.

**Why this priority**: Rules are the primary mechanism for defining agent behavior. Without rule management, agents cannot be configured.

**Independent Test**: Can be fully tested by creating a rule via POST, retrieving it via GET, updating via PUT, listing with filters, and deleting via DELETE. Delivers the ability to configure agent behavior.

**Acceptance Scenarios**:

1. **Given** an agent exists, **When** POST /v1/agents/{id}/rules is called with valid rule data, **Then** create the rule, compute embedding automatically, and return 201 Created with the new rule
2. **Given** rules exist for an agent, **When** GET /v1/agents/{id}/rules is called with filters (scope, enabled, priority_gte), **Then** return paginated list matching the filters
3. **Given** a rule exists, **When** PUT /v1/agents/{id}/rules/{rule_id} is called with updated data, **Then** update the rule and recompute embedding if condition/action changed
4. **Given** a rule exists, **When** DELETE /v1/agents/{id}/rules/{rule_id} is called, **Then** soft-delete the rule and return 204 No Content
5. **Given** multiple rule operations, **When** POST /v1/agents/{id}/rules/bulk is called with create/update/delete operations, **Then** process all operations atomically and return results for each

---

### User Story 2 - Manage Agents (Priority: P1)

A tenant administrator needs to create and manage agents, which are the top-level containers for all configuration (rules, scenarios, templates).

**Why this priority**: Agents are required containers before any other configuration can be created. They are the root of the configuration hierarchy.

**Independent Test**: Can be tested by creating an agent via POST, retrieving via GET, listing agents, updating settings via PUT, and deleting via DELETE.

**Acceptance Scenarios**:

1. **Given** a tenant, **When** POST /v1/agents is called with name, description, and settings, **Then** create the agent and return 201 Created with the new agent
2. **Given** agents exist, **When** GET /v1/agents is called with optional filters (enabled, search), **Then** return paginated list of agents with basic stats
3. **Given** an agent exists, **When** GET /v1/agents/{id} is called, **Then** return full agent details including settings and usage statistics
4. **Given** an agent exists, **When** PUT /v1/agents/{id} is called with updated data, **Then** update the agent and return 200 OK
5. **Given** an agent exists, **When** DELETE /v1/agents/{id} is called, **Then** soft-delete the agent and all associated configuration

---

### User Story 3 - Manage Scenarios (Priority: P2)

A configuration administrator needs to create and manage multi-step conversational flows (scenarios) with steps and transitions between them.

**Why this priority**: Scenarios enable structured conversations but agents can function with just rules for simpler use cases.

**Independent Test**: Can be tested by creating a scenario with steps, updating steps and transitions, adding new steps, and deleting scenarios.

**Acceptance Scenarios**:

1. **Given** an agent exists, **When** POST /v1/agents/{id}/scenarios is called with name, entry_condition, and steps, **Then** create the scenario with auto-generated step IDs and return 201 Created
2. **Given** a scenario exists, **When** GET /v1/agents/{id}/scenarios/{scenario_id} is called, **Then** return the full scenario with all steps, transitions, and linked templates/rules/tools
3. **Given** a scenario exists, **When** POST /v1/agents/{id}/scenarios/{scenario_id}/steps is called, **Then** add a new step to the scenario
4. **Given** a step exists, **When** PUT /v1/agents/{id}/scenarios/{scenario_id}/steps/{step_id} is called, **Then** update the step including transitions and linked resources
5. **Given** a step exists, **When** DELETE /v1/agents/{id}/scenarios/{scenario_id}/steps/{step_id} is called and it's not the entry step, **Then** remove the step and return 204 No Content

---

### User Story 4 - Manage Templates (Priority: P2)

A configuration administrator needs to create and manage pre-written response templates that can be linked to rules or scenario steps.

**Why this priority**: Templates provide consistent, reusable responses but agents can generate responses without them.

**Independent Test**: Can be tested by creating a template, retrieving it, previewing with sample variables, updating, and deleting.

**Acceptance Scenarios**:

1. **Given** an agent exists, **When** POST /v1/agents/{id}/templates is called with text containing variables and mode, **Then** create the template and extract variable names
2. **Given** a template exists, **When** GET /v1/agents/{id}/templates/{template_id} is called, **Then** return the template with detected variables_used
3. **Given** a template exists, **When** POST /v1/agents/{id}/templates/{template_id}/preview is called with variable values, **Then** return the rendered template text
4. **Given** a template with invalid variable syntax, **When** preview is attempted, **Then** return validation error indicating the issue

---

### User Story 5 - Publish Configuration (Priority: P2)

A configuration administrator needs to publish configuration changes to make them live, view publish status, and rollback to previous versions if needed.

**Why this priority**: Publishing controls when changes take effect, enabling safe configuration updates without immediate impact.

**Independent Test**: Can be tested by making configuration changes, checking publish status, publishing, and rolling back.

**Acceptance Scenarios**:

1. **Given** unpublished changes exist, **When** GET /v1/agents/{id}/publish is called, **Then** return publish status showing current vs draft version and change summary
2. **Given** unpublished changes exist, **When** POST /v1/agents/{id}/publish is called, **Then** return 202 Accepted and begin async publish process
3. **Given** a publish is in progress, **When** GET /v1/agents/{id}/publish/{publish_id} is called, **Then** return stage-by-stage progress status
4. **Given** a published version, **When** POST /v1/agents/{id}/rollback is called with target_version, **Then** revert to the specified version

---

### User Story 6 - Manage Variables (Priority: P3)

A configuration administrator needs to define dynamic context variables that are resolved at runtime from tools or other sources.

**Why this priority**: Variables enable dynamic behavior but are an advanced feature not required for basic agent functionality.

**Independent Test**: Can be tested by creating a variable, listing variables, updating resolver configuration, and deleting.

**Acceptance Scenarios**:

1. **Given** an agent exists, **When** POST /v1/agents/{id}/variables is called with name, resolver_tool_id, and update_policy, **Then** create the variable definition
2. **Given** variables exist, **When** GET /v1/agents/{id}/variables is called, **Then** return list of variable definitions with their update policies
3. **Given** a variable exists, **When** PUT /v1/agents/{id}/variables/{id} is called, **Then** update the variable configuration

---

### Edge Cases

- What happens when deleting an agent with active sessions? Soft-delete the agent but allow active sessions to continue until they naturally end
- How does the system handle concurrent updates to the same resource? Use optimistic locking with version numbers and return 409 Conflict on stale updates
- What happens when deleting a scenario step that other steps transition to? Return validation error listing affected transitions
- What happens when a bulk operation partially fails? Return results for all operations indicating success/failure for each
- What happens when publishing with validation errors? Block publish and return list of validation errors

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide full CRUD endpoints for agents at /v1/agents
- **FR-002**: System MUST provide full CRUD endpoints for rules at /v1/agents/{id}/rules including bulk operations
- **FR-003**: System MUST provide full CRUD endpoints for scenarios at /v1/agents/{id}/scenarios
- **FR-004**: System MUST provide CRUD endpoints for scenario steps at /v1/agents/{id}/scenarios/{id}/steps
- **FR-005**: System MUST provide full CRUD endpoints for templates at /v1/agents/{id}/templates
- **FR-006**: System MUST provide template preview endpoint that renders templates with sample variables
- **FR-007**: System MUST provide CRUD endpoints for variables at /v1/agents/{id}/variables
- **FR-008**: System MUST support pagination (limit, offset) on all list endpoints
- **FR-009**: System MUST support filtering on list endpoints (scope, enabled, priority range, search)
- **FR-010**: System MUST support sorting on list endpoints with configurable sort fields and direction
- **FR-011**: System MUST return standard paginated response format with items, total, limit, offset, has_more
- **FR-012**: System MUST provide publish workflow endpoints (status, publish, rollback)
- **FR-013**: System MUST auto-compute embeddings when rules are created or when condition/action text changes
- **FR-014**: System MUST validate all input data and return structured validation errors
- **FR-015**: System MUST log all mutations with actor (from JWT) and timestamp for audit trail
- **FR-016**: System MUST use soft deletes for all resources (set deleted_at rather than removing records)
- **FR-017**: System MUST prevent deletion of entry steps without reassigning entry first

### Key Entities

- **Agent**: Top-level container with name, description, settings, version, and statistics about usage
- **Rule**: Behavioral policy with condition_text, action_text, scope, priority, attached tools and templates
- **Scenario**: Multi-step flow with entry_condition, steps with transitions, and linked resources per step
- **ScenarioStep**: Individual step with name, description, transitions, and linked template/rule/tool IDs
- **Template**: Pre-written response with text containing variable placeholders and rendering mode
- **Variable**: Dynamic context definition with resolver tool, update policy, and cache settings
- **PublishStatus**: Versioning state with current/draft versions, change summary, and publish history

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can create a complete agent configuration (agent, rules, scenarios, templates) in a single session
- **SC-002**: List endpoints return results within acceptable latency for typical page sizes
- **SC-003**: Bulk operations process large batches efficiently
- **SC-004**: Configuration changes do not affect live traffic until explicitly published
- **SC-005**: Rollback restores previous configuration state completely and correctly
- **SC-006**: All mutations are auditable with actor, timestamp, and change details
- **SC-007**: Validation errors provide clear, actionable feedback for resolution
- **SC-008**: Concurrent edits are handled gracefully with appropriate conflict detection
