<a id="soldier.api.exceptions"></a>

# soldier.api.exceptions

API exception hierarchy for consistent error handling.

All API exceptions inherit from SoldierAPIError, which provides
status_code and error_code attributes used by the global exception
handler to generate consistent error responses.

<a id="soldier.api.exceptions.SoldierAPIError"></a>

## SoldierAPIError Objects

```python
class SoldierAPIError(Exception)
```

Base exception for all API errors.

Subclasses set status_code and error_code to define the HTTP response.
The global exception handler uses these to generate ErrorResponse.

<a id="soldier.api.exceptions.InvalidRequestError"></a>

## InvalidRequestError Objects

```python
class InvalidRequestError(SoldierAPIError)
```

Raised when request validation fails.

<a id="soldier.api.exceptions.TenantNotFoundError"></a>

## TenantNotFoundError Objects

```python
class TenantNotFoundError(SoldierAPIError)
```

Raised when tenant_id doesn't exist.

<a id="soldier.api.exceptions.AgentNotFoundError"></a>

## AgentNotFoundError Objects

```python
class AgentNotFoundError(SoldierAPIError)
```

Raised when agent_id doesn't exist for the tenant.

<a id="soldier.api.exceptions.SessionNotFoundError"></a>

## SessionNotFoundError Objects

```python
class SessionNotFoundError(SoldierAPIError)
```

Raised when session_id doesn't exist.

<a id="soldier.api.exceptions.RuleViolationError"></a>

## RuleViolationError Objects

```python
class RuleViolationError(SoldierAPIError)
```

Raised when a rule constraint is violated.

<a id="soldier.api.exceptions.ToolFailedError"></a>

## ToolFailedError Objects

```python
class ToolFailedError(SoldierAPIError)
```

Raised when a tool execution fails.

<a id="soldier.api.exceptions.RateLimitExceededError"></a>

## RateLimitExceededError Objects

```python
class RateLimitExceededError(SoldierAPIError)
```

Raised when tenant exceeds rate limit.

<a id="soldier.api.exceptions.LLMProviderError"></a>

## LLMProviderError Objects

```python
class LLMProviderError(SoldierAPIError)
```

Raised when LLM provider fails or is unavailable.

<a id="soldier.api.exceptions.RuleNotFoundError"></a>

## RuleNotFoundError Objects

```python
class RuleNotFoundError(SoldierAPIError)
```

Raised when rule_id doesn't exist for the agent.

<a id="soldier.api.exceptions.ScenarioNotFoundError"></a>

## ScenarioNotFoundError Objects

```python
class ScenarioNotFoundError(SoldierAPIError)
```

Raised when scenario_id doesn't exist for the agent.

<a id="soldier.api.exceptions.TemplateNotFoundError"></a>

## TemplateNotFoundError Objects

```python
class TemplateNotFoundError(SoldierAPIError)
```

Raised when template_id doesn't exist for the agent.

<a id="soldier.api.exceptions.VariableNotFoundError"></a>

## VariableNotFoundError Objects

```python
class VariableNotFoundError(SoldierAPIError)
```

Raised when variable_id doesn't exist for the agent.

<a id="soldier.api.exceptions.ToolActivationNotFoundError"></a>

## ToolActivationNotFoundError Objects

```python
class ToolActivationNotFoundError(SoldierAPIError)
```

Raised when tool activation doesn't exist for the agent.

<a id="soldier.api.exceptions.EntryStepDeletionError"></a>

## EntryStepDeletionError Objects

```python
class EntryStepDeletionError(SoldierAPIError)
```

Raised when attempting to delete a scenario's entry step.

<a id="soldier.api.exceptions.PublishInProgressError"></a>

## PublishInProgressError Objects

```python
class PublishInProgressError(SoldierAPIError)
```

Raised when a publish operation is already in progress.

<a id="soldier.api.exceptions.PublishFailedError"></a>

## PublishFailedError Objects

```python
class PublishFailedError(SoldierAPIError)
```

Raised when a publish operation fails.

<a id="soldier.api.exceptions.InvalidTransitionError"></a>

## InvalidTransitionError Objects

```python
class InvalidTransitionError(SoldierAPIError)
```

Raised when a scenario transition is invalid.

<a id="soldier.api.exceptions.PublishJobNotFoundError"></a>

## PublishJobNotFoundError Objects

```python
class PublishJobNotFoundError(SoldierAPIError)
```

Raised when a publish job doesn't exist.

