# Feature Specification: API Layer - Core

**Feature Branch**: `006-api-layer-core`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Implement HTTP API core layer including FastAPI application factory, middleware setup, route registration, exception handlers, API models for chat request/response and errors, core routes for chat processing and streaming, session management endpoints, health check and metrics endpoints, and authentication/rate limiting middleware"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Process Chat Message (Priority: P1)

An upstream service (channel gateway or message router) sends a user message to Focal for processing. The system processes the message through the alignment engine and returns a response with metadata about the turn.

**Why this priority**: This is the core functionality of Focal - processing conversational messages. Without this, the system has no purpose.

**Independent Test**: Can be fully tested by sending a POST request to `/v1/chat` with valid tenant_id, agent_id, channel, user_channel_id, and message, then verifying a response is returned with session_id, turn_id, and response text.

**Acceptance Scenarios**:

1. **Given** a valid chat request with tenant_id, agent_id, channel, user_channel_id, and message, **When** POST /v1/chat is called, **Then** return 200 OK with response text, session_id, turn_id, matched_rules, tools_called, tokens_used, and latency_ms
2. **Given** a chat request with optional session_id, **When** POST /v1/chat is called, **Then** continue the existing session rather than creating a new one
3. **Given** a chat request with Idempotency-Key header, **When** the same request is sent twice within 5 minutes, **Then** return the cached response without reprocessing
4. **Given** a chat request with unknown agent_id, **When** POST /v1/chat is called, **Then** return 400 Bad Request with error code AGENT_NOT_FOUND

---

### User Story 2 - Stream Chat Response (Priority: P1)

An upstream service requests a streaming response where tokens are delivered incrementally via Server-Sent Events (SSE) as the LLM generates them.

**Why this priority**: Streaming is essential for responsive user experiences in conversational interfaces where waiting for complete responses creates poor UX.

**Independent Test**: Can be tested by sending POST to `/v1/chat/stream` and verifying SSE events are received with type "token" containing incremental content, followed by a final "done" event with turn metadata.

**Acceptance Scenarios**:

1. **Given** a valid chat request, **When** POST /v1/chat/stream is called, **Then** return SSE stream with token events containing incremental response content
2. **Given** a streaming response in progress, **When** generation completes, **Then** send a final event with type "done" containing turn_id, matched_rules, and metadata
3. **Given** an error during streaming, **When** the error occurs, **Then** send an error event and close the stream gracefully

---

### User Story 3 - Health Check and Metrics (Priority: P2)

Operations teams need to monitor Focal's health status and collect Prometheus metrics for observability dashboards and alerting.

**Why this priority**: Essential for production operations but not required for core message processing functionality.

**Independent Test**: Can be tested by calling GET /health and GET /metrics endpoints and verifying appropriate responses.

**Acceptance Scenarios**:

1. **Given** the service is running and healthy, **When** GET /health is called, **Then** return 200 OK with health status details
2. **Given** a dependency is unhealthy, **When** GET /health is called, **Then** return degraded status indicating which component is affected
3. **Given** the service is running, **When** GET /metrics is called, **Then** return Prometheus-formatted metrics including request counts, latencies, and LLM token usage

---

### User Story 4 - Session Management (Priority: P2)

Upstream services need to retrieve session state, end sessions, and view session history for debugging and user context management.

**Why this priority**: Important for operational management and debugging but conversations can function without explicit session management.

**Independent Test**: Can be tested by creating a session via chat, then calling GET /v1/sessions/{id} to retrieve state, GET /v1/sessions/{id}/turns for history, and DELETE /v1/sessions/{id} to end it.

**Acceptance Scenarios**:

1. **Given** an existing session, **When** GET /v1/sessions/{session_id} is called, **Then** return session state including active_scenario_id, active_step_id, variables, and turn_count
2. **Given** an existing session, **When** GET /v1/sessions/{session_id}/turns is called with pagination, **Then** return paginated turn history with user messages and agent responses
3. **Given** an existing session, **When** DELETE /v1/sessions/{session_id} is called, **Then** end the session and return 204 No Content
4. **Given** an unknown session_id, **When** GET /v1/sessions/{session_id} is called, **Then** return 404 Not Found with error code SESSION_NOT_FOUND

---

### User Story 5 - Rate Limiting (Priority: P3)

The system enforces per-tenant rate limits to prevent abuse and ensure fair resource allocation across tenants.

**Why this priority**: Important for production stability but core functionality works without rate limiting during initial development.

**Independent Test**: Can be tested by sending requests exceeding the rate limit and verifying 429 responses with appropriate rate limit headers.

**Acceptance Scenarios**:

1. **Given** a tenant has not exceeded their rate limit, **When** a request is made, **Then** include X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset headers
2. **Given** a tenant exceeds their rate limit, **When** a request is made, **Then** return 429 Too Many Requests with retry information
3. **Given** different tenant tiers (Free, Pro, Enterprise), **When** requests are made, **Then** enforce tier-appropriate rate limits

---

### Edge Cases

- What happens when the LLM provider is unavailable? Return 502 LLM_ERROR with graceful error message
- How does the system handle malformed JSON in request bodies? Return 400 INVALID_REQUEST with validation details
- What happens if a session expires during a request? Create a new session and continue processing
- How are concurrent requests to the same session handled? Process sequentially to maintain consistency
- What happens when Idempotency-Key cache storage is unavailable? Process request without idempotency protection and log warning

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a FastAPI application with configurable middleware and route registration
- **FR-002**: System MUST provide POST /v1/chat endpoint that processes messages and returns structured responses
- **FR-003**: System MUST provide POST /v1/chat/stream endpoint that streams responses via Server-Sent Events
- **FR-004**: System MUST provide GET /v1/sessions/{id} endpoint to retrieve session state
- **FR-005**: System MUST provide DELETE /v1/sessions/{id} endpoint to end sessions
- **FR-006**: System MUST provide GET /v1/sessions/{id}/turns endpoint with pagination for session history
- **FR-007**: System MUST provide GET /health endpoint for health checks
- **FR-008**: System MUST provide GET /metrics endpoint exposing Prometheus metrics
- **FR-009**: System MUST validate JWT tokens and extract tenant_id from authentication headers
- **FR-010**: System MUST enforce per-tenant rate limits with configurable tiers
- **FR-011**: System MUST return standard error responses with error code, message, and details
- **FR-012**: System MUST support idempotency via Idempotency-Key header with 5-minute cache for chat endpoints
- **FR-013**: System MUST bind request context (tenant_id, agent_id, session_id, turn_id, trace_id) for logging
- **FR-014**: System MUST propagate OpenTelemetry trace context through requests
- **FR-015**: System MUST handle exceptions globally and return appropriate HTTP status codes

### Key Entities

- **ChatRequest**: Message processing request with tenant_id, agent_id, channel, user_channel_id, message, optional session_id and metadata
- **ChatResponse**: Processing result with response text, session_id, turn_id, scenario state, matched_rules, tools_called, tokens_used, latency_ms
- **ErrorResponse**: Standard error format with code (enum), message, and optional details object
- **Session**: Conversation state including active scenario/step, variables, rule fires, turn count
- **Turn**: Single exchange with user_message, agent_response, matched_rules, tools_called, timing

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Chat endpoint API overhead is less than 100ms p95 (excluding LLM generation time)
- **SC-002**: Streaming endpoint delivers first token within 200ms of request receipt (excluding LLM time-to-first-token)
- **SC-003**: Health check endpoint responds within 10ms p99 under normal conditions
- **SC-004**: System handles at least 50 concurrent requests per tenant (Pro tier) without errors
- **SC-005**: Rate limiting accurately enforces per-tenant limits with less than 1% over-admission
- **SC-006**: All requests include complete observability context (trace_id, tenant_id, etc.) in logs
- **SC-007**: Error responses follow consistent format across all endpoints
- **SC-008**: Idempotent requests return identical responses for duplicate requests within cache window
