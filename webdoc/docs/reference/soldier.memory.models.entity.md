<a id="soldier.memory.models.entity"></a>

# soldier.memory.models.entity

Entity model for memory domain.

<a id="soldier.memory.models.entity.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="soldier.memory.models.entity.Entity"></a>

## Entity Objects

```python
class Entity(BaseModel)
```

Named thing in knowledge graph.

Entities represent real-world objects like people, orders,
products, etc. with temporal validity tracking.

