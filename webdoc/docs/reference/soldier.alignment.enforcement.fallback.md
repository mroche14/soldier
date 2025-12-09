<a id="focal.alignment.enforcement.fallback"></a>

# focal.alignment.enforcement.fallback

Fallback handler for enforcement failures.

<a id="focal.alignment.enforcement.fallback.FallbackHandler"></a>

## FallbackHandler Objects

```python
class FallbackHandler()
```

Provide fallback responses when enforcement fails.

Used as a last resort when:
1. Response violates hard constraints
2. Regeneration attempts fail
3. A safe fallback template is available

<a id="focal.alignment.enforcement.fallback.FallbackHandler.select_fallback"></a>

#### select\_fallback

```python
def select_fallback(templates: list[Template]) -> Template | None
```

Select a fallback template from available templates.

**Arguments**:

- `templates` - Available templates for matched rules
  

**Returns**:

  First template with FALLBACK mode, or None

<a id="focal.alignment.enforcement.fallback.FallbackHandler.apply_fallback"></a>

#### apply\_fallback

```python
def apply_fallback(template: Template | None,
                   original_result: EnforcementResult) -> EnforcementResult
```

Apply fallback template to enforcement result.

**Arguments**:

- `template` - Fallback template to use (or None)
- `original_result` - Result from enforcement validation
  

**Returns**:

  Updated EnforcementResult with fallback applied

