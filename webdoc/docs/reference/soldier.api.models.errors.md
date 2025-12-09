<a id="focal.api.models.errors"></a>

# focal.api.models.errors

Error response models for consistent API error handling.

<a id="focal.api.models.errors.ErrorCode"></a>

## ErrorCode Objects

```python
class ErrorCode(str, Enum)
```

Standardized error codes for API responses.

These codes provide machine-readable error identification across
all API endpoints.

<a id="focal.api.models.errors.ErrorCode.INVALID_REQUEST"></a>

#### INVALID\_REQUEST

Request validation failed (malformed JSON, missing fields, etc.).

<a id="focal.api.models.errors.ErrorCode.TENANT_NOT_FOUND"></a>

#### TENANT\_NOT\_FOUND

The specified tenant_id does not exist.

<a id="focal.api.models.errors.ErrorCode.AGENT_NOT_FOUND"></a>

#### AGENT\_NOT\_FOUND

The specified agent_id does not exist for this tenant.

<a id="focal.api.models.errors.ErrorCode.SESSION_NOT_FOUND"></a>

#### SESSION\_NOT\_FOUND

The specified session_id does not exist.

<a id="focal.api.models.errors.ErrorCode.RULE_VIOLATION"></a>

#### RULE\_VIOLATION

A rule constraint was violated during processing.

<a id="focal.api.models.errors.ErrorCode.TOOL_FAILED"></a>

#### TOOL\_FAILED

A tool execution failed during turn processing.

<a id="focal.api.models.errors.ErrorCode.LLM_ERROR"></a>

#### LLM\_ERROR

The LLM provider returned an error or was unavailable.

<a id="focal.api.models.errors.ErrorCode.RATE_LIMIT_EXCEEDED"></a>

#### RATE\_LIMIT\_EXCEEDED

The tenant has exceeded their rate limit.

<a id="focal.api.models.errors.ErrorCode.INTERNAL_ERROR"></a>

#### INTERNAL\_ERROR

An unexpected internal error occurred.

<a id="focal.api.models.errors.ErrorCode.RULE_NOT_FOUND"></a>

#### RULE\_NOT\_FOUND

The specified rule_id does not exist.

<a id="focal.api.models.errors.ErrorCode.SCENARIO_NOT_FOUND"></a>

#### SCENARIO\_NOT\_FOUND

The specified scenario_id does not exist.

<a id="focal.api.models.errors.ErrorCode.TEMPLATE_NOT_FOUND"></a>

#### TEMPLATE\_NOT\_FOUND

The specified template_id does not exist.

<a id="focal.api.models.errors.ErrorCode.VARIABLE_NOT_FOUND"></a>

#### VARIABLE\_NOT\_FOUND

The specified variable_id does not exist.

<a id="focal.api.models.errors.ErrorCode.TOOL_ACTIVATION_NOT_FOUND"></a>

#### TOOL\_ACTIVATION\_NOT\_FOUND

The specified tool activation does not exist.

<a id="focal.api.models.errors.ErrorCode.ENTRY_STEP_DELETION"></a>

#### ENTRY\_STEP\_DELETION

Cannot delete entry step without reassignment.

<a id="focal.api.models.errors.ErrorCode.PUBLISH_IN_PROGRESS"></a>

#### PUBLISH\_IN\_PROGRESS

A publish operation is already in progress for this agent.

<a id="focal.api.models.errors.ErrorCode.PUBLISH_FAILED"></a>

#### PUBLISH\_FAILED

The publish operation failed.

<a id="focal.api.models.errors.ErrorCode.INVALID_TRANSITION"></a>

#### INVALID\_TRANSITION

The scenario transition references an invalid step.

<a id="focal.api.models.errors.ErrorCode.PUBLISH_JOB_NOT_FOUND"></a>

#### PUBLISH\_JOB\_NOT\_FOUND

The specified publish job does not exist.

<a id="focal.api.models.errors.ErrorDetail"></a>

## ErrorDetail Objects

```python
class ErrorDetail(BaseModel)
```

Detailed error information for validation errors.

Provides field-level error details for request validation failures.

<a id="focal.api.models.errors.ErrorDetail.field"></a>

#### field

The field that caused the error, if applicable.

<a id="focal.api.models.errors.ErrorDetail.message"></a>

#### message

Human-readable error description.

<a id="focal.api.models.errors.ErrorBody"></a>

## ErrorBody Objects

```python
class ErrorBody(BaseModel)
```

Error body content for API error responses.

<a id="focal.api.models.errors.ErrorBody.code"></a>

#### code

Machine-readable error code.

<a id="focal.api.models.errors.ErrorBody.message"></a>

#### message

Human-readable error message.

<a id="focal.api.models.errors.ErrorBody.details"></a>

#### details

Additional error details for validation failures.

<a id="focal.api.models.errors.ErrorBody.turn_id"></a>

#### turn\_id

Turn ID if the error occurred during turn processing.

<a id="focal.api.models.errors.ErrorBody.rule_id"></a>

#### rule\_id

Rule ID if the error was caused by a rule violation.

<a id="focal.api.models.errors.ErrorResponse"></a>

## ErrorResponse Objects

```python
class ErrorResponse(BaseModel)
```

Standard error response format for all API errors.

All error responses follow this structure for consistency.

**Example**:

  {
- `"error"` - {
- `"code"` - "AGENT_NOT_FOUND",
- `"message"` - "Agent with ID xyz does not exist"
  }
  }

