<a id="soldier.alignment.models.rule"></a>

# soldier.alignment.models.rule

Rule models for alignment domain.

<a id="soldier.alignment.models.rule.Rule"></a>

## Rule Objects

```python
class Rule(AgentScopedModel)
```

Behavioral policy: when X, then Y.

Rules define agent behavior through natural language conditions
and actions. They can be scoped to global, scenario, or step level.

<a id="soldier.alignment.models.rule.Rule.validate_scope_id"></a>

#### validate\_scope\_id

```python
@field_validator("scope_id")
@classmethod
def validate_scope_id(cls, v: UUID | None,
                      info: ValidationInfo) -> UUID | None
```

Validate scope_id is set when scope requires it.

<a id="soldier.alignment.models.rule.MatchedRule"></a>

## MatchedRule Objects

```python
class MatchedRule(AgentScopedModel)
```

Rule that matched with scoring details.

