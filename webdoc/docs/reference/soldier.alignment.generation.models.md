<a id="focal.alignment.generation.models"></a>

# focal.alignment.generation.models

Generation models for alignment pipeline.

Contains models for response generation with template support.

<a id="focal.alignment.generation.models.TemplateMode"></a>

## TemplateMode Objects

```python
class TemplateMode(str, Enum)
```

How a template should be used in generation.

<a id="focal.alignment.generation.models.TemplateMode.EXCLUSIVE"></a>

#### EXCLUSIVE

Use exact template, skip LLM

<a id="focal.alignment.generation.models.TemplateMode.SUGGEST"></a>

#### SUGGEST

Include in prompt, LLM can adapt

<a id="focal.alignment.generation.models.TemplateMode.FALLBACK"></a>

#### FALLBACK

Use when enforcement fails

<a id="focal.alignment.generation.models.GenerationResult"></a>

## GenerationResult Objects

```python
class GenerationResult(BaseModel)
```

Result of response generation.

