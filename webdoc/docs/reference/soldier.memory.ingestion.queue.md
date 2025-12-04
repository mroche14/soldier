<a id="soldier.memory.ingestion.queue"></a>

# soldier.memory.ingestion.queue

Task queue implementations for async memory ingestion.

<a id="soldier.memory.ingestion.queue.TaskQueue"></a>

## TaskQueue Objects

```python
class TaskQueue(ABC)
```

Abstract interface for task queue implementations.

<a id="soldier.memory.ingestion.queue.TaskQueue.enqueue"></a>

#### enqueue

```python
@abstractmethod
async def enqueue(job_type: str, **kwargs: Any) -> str
```

Enqueue a task.

**Arguments**:

- `job_type` - Type of job to execute
- `**kwargs` - Job parameters
  

**Returns**:

  Job ID

<a id="soldier.memory.ingestion.queue.TaskQueue.register"></a>

#### register

```python
@abstractmethod
def register(job_type: str, handler: Callable[..., Any]) -> None
```

Register a task handler.

**Arguments**:

- `job_type` - Type of job this handler processes
- `handler` - Async callable to process the job

<a id="soldier.memory.ingestion.queue.InMemoryTaskQueue"></a>

## InMemoryTaskQueue Objects

```python
class InMemoryTaskQueue(TaskQueue)
```

In-memory task queue for development and testing.

<a id="soldier.memory.ingestion.queue.InMemoryTaskQueue.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize in-memory task queue.

<a id="soldier.memory.ingestion.queue.InMemoryTaskQueue.register"></a>

#### register

```python
def register(job_type: str, handler: Callable[..., Any]) -> None
```

Register a task handler.

**Arguments**:

- `job_type` - Type of job this handler processes
- `handler` - Async callable to process the job

<a id="soldier.memory.ingestion.queue.InMemoryTaskQueue.enqueue"></a>

#### enqueue

```python
async def enqueue(job_type: str, **kwargs: Any) -> str
```

Enqueue a task.

**Arguments**:

- `job_type` - Type of job to execute
- `**kwargs` - Job parameters
  

**Returns**:

  Job ID

<a id="soldier.memory.ingestion.queue.RedisTaskQueue"></a>

## RedisTaskQueue Objects

```python
class RedisTaskQueue(TaskQueue)
```

Redis-based task queue for production (optional).

<a id="soldier.memory.ingestion.queue.RedisTaskQueue.__init__"></a>

#### \_\_init\_\_

```python
def __init__(redis_url: str = "redis://localhost:6379")
```

Initialize Redis task queue.

**Arguments**:

- `redis_url` - Redis connection URL

<a id="soldier.memory.ingestion.queue.RedisTaskQueue.register"></a>

#### register

```python
def register(job_type: str, handler: Callable[..., Any]) -> None
```

Register a task handler.

**Arguments**:

- `job_type` - Type of job this handler processes
- `handler` - Async callable to process the job

<a id="soldier.memory.ingestion.queue.RedisTaskQueue.enqueue"></a>

#### enqueue

```python
async def enqueue(job_type: str, **kwargs: Any) -> str
```

Enqueue a task to Redis queue.

**Arguments**:

- `job_type` - Type of job to execute
- `**kwargs` - Job parameters
  

**Returns**:

  Job ID

