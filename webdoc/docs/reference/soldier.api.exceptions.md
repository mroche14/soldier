<a id="focal.api.exceptions"></a>

# focal.api.exceptions

API exception hierarchy for consistent error handling.

All API exceptions inherit from FocalAPIError, which provides
status_code and error_code attributes used by the global exception
handler to generate consistent error responses.

<a id="focal.api.exceptions.FocalAPIError"></a>

## FocalAPIError Objects

```python
class FocalAPIError(Exception)
```

Base exception for all API errors.

Subclasses set status_code and error_code to define the HTTP response.
The global exception handler uses these to generate ErrorResponse.

<a id="focal.api.exceptions.InvalidRequestError"></a>

## InvalidRequestError Objects

```python
class InvalidRequestError(FocalAPIError)
```

Raised when request validation fails.

<a id="focal.api.exceptions.TenantNotFoundError"></a>

## TenantNotFoundError Objects

```python
class TenantNotFoundError(FocalAPIError)
```

Raised when tenant_id doesn't exist.

<a id="focal.api.exceptions.AgentNotFoundError"></a>

## AgentNotFoundError Objects

```python
class AgentNotFoundError(FocalAPIError)
```

Raised when agent_id doesn't exist for the tenant.

<a id="focal.api.exceptions.SessionNotFoundError"></a>

## SessionNotFoundError Objects

```python
class SessionNotFoundError(FocalAPIError)
```

Raised when session_id doesn't exist.

<a id="focal.api.exceptions.RuleViolationError"></a>

## RuleViolationError Objects

```python
class RuleViolationError(FocalAPIError)
```

Raised when a rule constraint is violated.

<a id="focal.api.exceptions.ToolFailedError"></a>

## ToolFailedError Objects

```python
class ToolFailedError(FocalAPIError)
```

Raised when a tool execution fails.

<a id="focal.api.exceptions.RateLimitExceededError"></a>

## RateLimitExceededError Objects

```python
class RateLimitExceededError(FocalAPIError)
```

Raised when tenant exceeds rate limit.

<a id="focal.api.exceptions.LLMProviderError"></a>

## LLMProviderError Objects

```python
class LLMProviderError(FocalAPIError)
```

Raised when LLM provider fails or is unavailable.

<a id="focal.api.exceptions.RuleNotFoundError"></a>

## RuleNotFoundError Objects

```python
class RuleNotFoundError(FocalAPIError)
```

Raised when rule_id doesn't exist for the agent.

<a id="focal.api.exceptions.ScenarioNotFoundError"></a>

## ScenarioNotFoundError Objects

```python
class ScenarioNotFoundError(FocalAPIError)
```

Raised when scenario_id doesn't exist for the agent.

<a id="focal.api.exceptions.TemplateNotFoundError"></a>

## TemplateNotFoundError Objects

```python
class TemplateNotFoundError(FocalAPIError)
```

Raised when template_id doesn't exist for the agent.

<a id="focal.api.exceptions.VariableNotFoundError"></a>

## VariableNotFoundError Objects

```python
class VariableNotFoundError(FocalAPIError)
```

Raised when variable_id doesn't exist for the agent.

<a id="focal.api.exceptions.ToolActivationNotFoundError"></a>

## ToolActivationNotFoundError Objects

```python
class ToolActivationNotFoundError(FocalAPIError)
```

Raised when tool activation doesn't exist for the agent.

<a id="focal.api.exceptions.EntryStepDeletionError"></a>

## EntryStepDeletionError Objects

```python
class EntryStepDeletionError(FocalAPIError)
```

Raised when attempting to delete a scenario's entry step.

<a id="focal.api.exceptions.PublishInProgressError"></a>

## PublishInProgressError Objects

```python
class PublishInProgressError(FocalAPIError)
```

Raised when a publish operation is already in progress.

<a id="focal.api.exceptions.PublishFailedError"></a>

## PublishFailedError Objects

```python
class PublishFailedError(FocalAPIError)
```

Raised when a publish operation fails.

<a id="focal.api.exceptions.InvalidTransitionError"></a>

## InvalidTransitionError Objects

```python
class InvalidTransitionError(FocalAPIError)
```

Raised when a scenario transition is invalid.

<a id="focal.api.exceptions.PublishJobNotFoundError"></a>

## PublishJobNotFoundError Objects

```python
class PublishJobNotFoundError(FocalAPIError)
```

Raised when a publish job doesn't exist.

