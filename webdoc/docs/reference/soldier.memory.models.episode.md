<a id="soldier.memory.models.episode"></a>

# soldier.memory.models.episode

Episode model for memory domain.

<a id="soldier.memory.models.episode.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="soldier.memory.models.episode.Episode"></a>

## Episode Objects

```python
class Episode(BaseModel)
```

Atomic unit of memory.

Episodes represent individual pieces of information stored
in the memory system, with bi-temporal attributes for
tracking when events occurred vs when they were recorded.

