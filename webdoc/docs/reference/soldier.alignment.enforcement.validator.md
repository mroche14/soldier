<a id="soldier.alignment.enforcement.validator"></a>

# soldier.alignment.enforcement.validator

Response enforcement for hard constraints.

<a id="soldier.alignment.enforcement.validator.EnforcementValidator"></a>

## EnforcementValidator Objects

```python
class EnforcementValidator()
```

Validate responses against hard constraint rules.

Hard constraints are rules that must be satisfied for every response.
When violations are detected, the validator can:
1. Attempt to regenerate the response with stronger instructions
2. Pass to FallbackHandler for template-based recovery

<a id="soldier.alignment.enforcement.validator.EnforcementValidator.__init__"></a>

#### \_\_init\_\_

```python
def __init__(response_generator: ResponseGenerator,
             max_retries: int = 1) -> None
```

Initialize the enforcement validator.

**Arguments**:

- `response_generator` - Generator for response regeneration
- `max_retries` - Maximum regeneration attempts on violation

<a id="soldier.alignment.enforcement.validator.EnforcementValidator.validate"></a>

#### validate

```python
async def validate(response: str, context: Context,
                   matched_rules: list[MatchedRule],
                   hard_rules: list[Rule]) -> EnforcementResult
```

Validate response against hard constraints.

**Arguments**:

- `response` - Generated response to validate
- `context` - User message context
- `matched_rules` - Rules that matched this turn
- `hard_rules` - Subset of rules that are hard constraints
  

**Returns**:

  EnforcementResult with validation status and final response

