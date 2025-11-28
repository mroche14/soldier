# Feature Specification: Alignment Pipeline

**Feature Branch**: `004-alignment-pipeline`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Implement the Alignment Pipeline (Phases 6-11): A multi-step processing pipeline for the cognitive engine that extracts context from user messages, retrieves relevant rules/scenarios/memories using dynamic selection strategies, filters candidates using LLM-based judgment, executes tools from matched rules, generates responses, and integrates all components into a unified AlignmentEngine."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Process a Simple User Message (Priority: P1)

A conversation participant sends a text message to an AI agent. The system should understand the message, find any relevant behavioral rules, and generate an appropriate response that follows those rules.

**Why this priority**: This is the core value proposition - ensuring the AI agent responds appropriately to user messages by enforcing configured policies. Without this, there is no product.

**Independent Test**: Can be fully tested by sending a message to an agent with pre-configured rules and verifying the response follows those rules. Delivers immediate value by producing policy-compliant AI responses.

**Acceptance Scenarios**:

1. **Given** an agent with a rule "When user asks about returns, explain the 30-day return policy", **When** a user asks "Can I return my order?", **Then** the response includes information about the 30-day return policy.

2. **Given** an agent with no matching rules for the user's question, **When** a user asks an unrelated question, **Then** the system generates a helpful response without any rule-based constraints.

3. **Given** an agent with multiple rules where two could match, **When** a user sends an ambiguous message, **Then** the system selects the most relevant rules based on semantic similarity and context.

---

### User Story 2 - Navigate Multi-Step Conversational Flows (Priority: P2)

A user engages in a multi-step process (like a return request, onboarding, or support escalation). The system should track which step they're on, transition between steps based on their responses, and apply step-specific behaviors.

**Why this priority**: Multi-step flows are essential for complex business processes. This enables structured conversations beyond single Q&A exchanges.

**Independent Test**: Can be tested by simulating a complete flow (e.g., return process) and verifying correct step transitions and step-specific behaviors at each stage.

**Acceptance Scenarios**:

1. **Given** a "Return Process" scenario with steps "Identify Order" -> "Verify Eligibility" -> "Process Return", **When** a user says "I want to return my order", **Then** the system starts the scenario and prompts for order identification.

2. **Given** the user is in the "Identify Order" step, **When** the user provides a valid order number, **Then** the system transitions to "Verify Eligibility" and checks return policy.

3. **Given** the user is in a scenario step, **When** the user says something that doesn't match any transition, **Then** the system stays in the current step and continues the conversation.

4. **Given** the user is in a terminal step, **When** the step requirements are satisfied, **Then** the system exits the scenario gracefully.

---

### User Story 3 - Execute Tools Based on Matched Rules (Priority: P2)

When a rule matches that has attached tools (like "check order status" or "initiate return"), the system should execute those tools and incorporate the results into the response.

**Why this priority**: Tools enable the AI to take real actions and access external data, making it useful beyond just conversation.

**Independent Test**: Can be tested by configuring a rule with an attached tool, sending a matching message, and verifying the tool was executed and its result influenced the response.

**Acceptance Scenarios**:

1. **Given** a rule "When user asks about order status, check order database" with attached tool "check_order_status", **When** a user asks "Where is my order #12345?", **Then** the system executes the tool and includes the order status in the response.

2. **Given** a tool execution fails, **When** generating the response, **Then** the system handles the failure gracefully and provides a helpful message to the user.

3. **Given** multiple rules match with different tools, **When** processing the turn, **Then** all tools from matched rules are executed before generating the response.

---

### User Story 4 - Dynamically Select Relevant Results (Priority: P3)

When searching for rules, scenarios, or memories, the system should intelligently determine how many results to include based on the score distribution rather than using a fixed number.

**Why this priority**: Smart selection improves response quality by including all relevant items without noise, adapting to query difficulty.

**Independent Test**: Can be tested by comparing responses with fixed-k selection vs dynamic selection on queries with varying relevance distributions.

**Acceptance Scenarios**:

1. **Given** a query that clearly matches 2 rules with high scores (0.95, 0.92) and several low-scoring rules (0.45, 0.40), **When** retrieving candidates, **Then** only the 2 high-scoring rules are selected.

2. **Given** a query where many rules have similar scores (0.78, 0.76, 0.75, 0.74), **When** retrieving candidates, **Then** more results are included to give the filtering step adequate context.

3. **Given** a query matching distinct topic clusters (e.g., "deploy" matches both AWS and Kubernetes rules), **When** using clustering selection, **Then** representatives from each topic cluster are included.

---

### User Story 5 - Enforce Hard Constraints on Responses (Priority: P3)

For critical policies (legal disclaimers, security rules, compliance requirements), the system should validate responses after generation and take corrective action if they violate constraints.

**Why this priority**: Hard constraints provide safety guarantees for high-stakes use cases where specific language must be used or avoided.

**Independent Test**: Can be tested by configuring a hard constraint rule and verifying responses are corrected or replaced when they would violate it.

**Acceptance Scenarios**:

1. **Given** a hard constraint rule "Never discuss competitor products by name", **When** the generated response mentions a competitor, **Then** the system regenerates the response without the mention.

2. **Given** regeneration still violates the constraint, **When** enforcement fails, **Then** the system uses a safe fallback template response.

3. **Given** multiple hard constraints, **When** validating a response, **Then** all constraints are checked and the response passes only if all are satisfied.

---

### User Story 6 - Use Pre-written Templates for Critical Responses (Priority: P3)

For certain situations (legal disclaimers, exact policy statements, error messages), the system should use exact pre-written text instead of generating responses, eliminating hallucination risk.

**Why this priority**: Templates provide deterministic responses for situations where exact wording matters.

**Independent Test**: Can be tested by triggering a rule with an exclusive template and verifying the exact template text is returned without LLM modification.

**Acceptance Scenarios**:

1. **Given** a rule with an "exclusive" template for legal disclaimers, **When** the rule matches, **Then** the exact template text is returned without LLM generation.

2. **Given** a template with variable placeholders like "{customer_name}", **When** returning the template, **Then** variables are resolved from session data.

3. **Given** a rule with a "suggest" template, **When** generating a response, **Then** the LLM may adapt the template text while preserving key information.

---

### Edge Cases

- What happens when no rules match at all? The system generates a helpful response using only the base agent configuration.
- What happens when the user's message is empty or only whitespace? Return an appropriate error indicating invalid input.
- What happens when a scenario step is deleted while a user is mid-flow? Re-localize to the nearest valid step or exit the scenario gracefully with a message.
- What happens when a tool takes too long to respond? Timeout after the configured duration and handle gracefully, either skipping the tool result or using cached data.
- What happens when the embedding service is unavailable? Gracefully degrade to rule-based matching or return an error if no fallback is possible.
- What happens when all retrieved rules have very low scores? Don't force irrelevant rules into the pipeline; proceed without rule-based constraints.

## Requirements *(mandatory)*

### Functional Requirements

**Selection Strategies (Phase 6)**
- **FR-001**: System MUST support multiple selection strategies for determining how many retrieval results to keep
- **FR-002**: System MUST support at least: elbow method (score drop detection), adaptive-k (curvature analysis), entropy-based (uncertainty measurement), clustering (topic grouping), and fixed-k (baseline)
- **FR-003**: Each selection strategy MUST be configurable with its specific parameters
- **FR-004**: Selection strategies MUST be usable for rules, scenarios, and memory retrieval independently

**Context Extraction (Phase 7)**
- **FR-005**: System MUST extract user intent from messages considering conversation history
- **FR-006**: System MUST support multiple extraction modes: full LLM-based, embedding-only (lightweight), and disabled (maximum speed)
- **FR-007**: System MUST extract entities mentioned in the message (order IDs, product names, etc.)
- **FR-008**: System MUST detect sentiment (positive, negative, neutral, frustrated)
- **FR-009**: System MUST provide scenario signals (start, continue, exit) as hints for navigation

**Retrieval (Phase 8)**
- **FR-010**: System MUST retrieve candidate rules using semantic similarity search
- **FR-011**: System MUST retrieve rules by scope hierarchy: global rules first, then scenario-scoped, then step-scoped
- **FR-012**: System MUST apply business filters: enabled status, max fires per session, cooldown between fires
- **FR-013**: System MUST retrieve relevant memory episodes when configured
- **FR-014**: System MUST support reranking of candidates using a dedicated reranker model (optional step)

**Filtering (Phase 9)**
- **FR-015**: System MUST use LLM-based filtering to judge which rules actually apply to the current context
- **FR-016**: Rule filtering MUST be separate from scenario filtering (different responsibilities)
- **FR-017**: Scenario filter MUST navigate the scenario graph: evaluate transitions, detect loops, handle re-localization
- **FR-018**: Scenario filter MUST support LLM adjudication when multiple transitions have similar scores
- **FR-019**: System MUST be able to recover from inconsistent scenario state (deleted step, version mismatch)

**Execution & Generation (Phase 10)**
- **FR-020**: System MUST execute tools attached to matched rules before generating response
- **FR-021**: Tool execution MUST respect configured timeouts
- **FR-022**: System MUST resolve variable placeholders from session and profile data
- **FR-023**: System MUST check for exclusive templates (bypass LLM entirely)
- **FR-024**: System MUST build prompts incorporating: matched rules, memory context, tool results, scenario state, and session variables
- **FR-025**: System MUST validate responses against hard constraint rules
- **FR-026**: System MUST support regeneration when constraints are violated
- **FR-027**: System MUST fall back to safe templates when regeneration fails

**Engine Integration (Phase 11)**
- **FR-028**: System MUST orchestrate all pipeline steps in the correct order
- **FR-029**: System MUST support enabling/disabling individual pipeline steps via configuration
- **FR-030**: System MUST log timing and metadata for each pipeline step
- **FR-031**: System MUST handle errors gracefully at each step without crashing the entire pipeline
- **FR-032**: System MUST persist session state, audit records, and memory after processing

### Key Entities

- **Context**: Extracted understanding of user message including intent, entities, sentiment, and embedding
- **SelectionResult**: Output of selection strategy including selected items, cutoff score, and metadata
- **MatchedRule**: A rule determined to apply to the current turn, with its match score
- **ScenarioFilterResult**: Decision about scenario navigation (start, continue, transition, exit, relocalize)
- **ToolResult**: Outcome of executing a tool including inputs, outputs, and success/failure status
- **GenerationResult**: The generated response with metadata about template usage and token consumption
- **EnforcementResult**: Validation outcome including whether constraints passed and any fallbacks used
- **AlignmentResult**: Complete result of processing a turn, aggregating all pipeline step outputs

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Processing a simple message (no scenario, no tools) completes in under 1 second with context extraction enabled
- **SC-002**: Processing a message with tool execution completes in under 2 seconds (excluding external tool latency)
- **SC-003**: Rule matching accuracy: relevant rules are selected at least 90% of the time when they exist
- **SC-004**: Scenario transitions occur correctly at least 95% of the time based on defined transition conditions
- **SC-005**: Hard constraint violations are detected and corrected 100% of the time
- **SC-006**: System handles 100 concurrent message processing requests without degradation
- **SC-007**: Pipeline step failures are logged with sufficient detail to diagnose issues
- **SC-008**: All pipeline configurations can be changed without code deployment (via configuration files)
- **SC-009**: Selection strategies reduce noise in retrieved results by at least 30% compared to fixed top-k

## Assumptions

- Existing store interfaces (ConfigStore, MemoryStore, SessionStore, AuditStore) are implemented and functional
- Provider interfaces (LLMProvider, EmbeddingProvider, RerankProvider) are implemented with at least mock versions
- Domain models for Rule, Scenario, Session, etc. are already defined
- Configuration system supports nested TOML configuration with environment overrides
- Observability infrastructure (logging, metrics, tracing) is in place
