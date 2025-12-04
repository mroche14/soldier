<a id="soldier.api.app"></a>

# soldier.api.app

FastAPI application factory.

Creates and configures the FastAPI application with middleware,
exception handlers, and route registration.

<a id="soldier.api.app.create_app"></a>

#### create\_app

```python
def create_app() -> FastAPI
```

Create and configure the FastAPI application.

This factory function creates a fully configured FastAPI app with:
- CORS middleware
- Request context middleware
- Global exception handlers
- OpenTelemetry instrumentation
- All API routes registered

**Returns**:

  Configured FastAPI application

