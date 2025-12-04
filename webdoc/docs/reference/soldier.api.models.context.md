<a id="soldier.api.models.context"></a>

# soldier.api.models.context

Request context models for middleware and observability.

<a id="soldier.api.models.context.TenantContext"></a>

## TenantContext Objects

```python
class TenantContext(BaseModel)
```

Tenant context extracted from authentication.

This is extracted from JWT claims by the auth middleware and made
available throughout request processing.

<a id="soldier.api.models.context.TenantContext.tenant_id"></a>

#### tenant\_id

Tenant identifier from JWT.

<a id="soldier.api.models.context.TenantContext.user_id"></a>

#### user\_id

Optional user identifier from JWT 'sub' claim.

<a id="soldier.api.models.context.TenantContext.roles"></a>

#### roles

User roles from JWT claims.

<a id="soldier.api.models.context.TenantContext.tier"></a>

#### tier

Tenant tier for rate limiting and feature gating.

<a id="soldier.api.models.context.RateLimitResult"></a>

## RateLimitResult Objects

```python
class RateLimitResult(BaseModel)
```

Result of a rate limit check.

Returned by the rate limiter to indicate whether a request is allowed
and to populate rate limit response headers.

<a id="soldier.api.models.context.RateLimitResult.allowed"></a>

#### allowed

Whether the request is within rate limits.

<a id="soldier.api.models.context.RateLimitResult.limit"></a>

#### limit

Maximum requests allowed in the window.

<a id="soldier.api.models.context.RateLimitResult.remaining"></a>

#### remaining

Remaining requests in the current window.

<a id="soldier.api.models.context.RateLimitResult.reset_at"></a>

#### reset\_at

When the rate limit window resets.

<a id="soldier.api.models.context.RequestContext"></a>

## RequestContext Objects

```python
class RequestContext(BaseModel)
```

Request context for observability and logging.

Bound at the start of each request and used to correlate logs,
traces, and metrics across the request lifecycle.

<a id="soldier.api.models.context.RequestContext.trace_id"></a>

#### trace\_id

OpenTelemetry trace ID.

<a id="soldier.api.models.context.RequestContext.span_id"></a>

#### span\_id

OpenTelemetry span ID.

<a id="soldier.api.models.context.RequestContext.tenant_id"></a>

#### tenant\_id

Tenant ID if authenticated.

<a id="soldier.api.models.context.RequestContext.agent_id"></a>

#### agent\_id

Agent ID if processing a chat request.

<a id="soldier.api.models.context.RequestContext.session_id"></a>

#### session\_id

Session ID if in a conversation.

<a id="soldier.api.models.context.RequestContext.turn_id"></a>

#### turn\_id

Turn ID if processing a message.

<a id="soldier.api.models.context.RequestContext.request_id"></a>

#### request\_id

Unique identifier for this request.

