"""FastAPI application factory.

Creates and configures the FastAPI application with middleware,
exception handlers, and route registration.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import ValidationError

from soldier.api.dependencies import get_settings
from soldier.api.exceptions import SoldierAPIError
from soldier.api.middleware.context import RequestContextMiddleware
from soldier.api.middleware.rate_limit import RateLimitMiddleware
from soldier.api.models.errors import ErrorBody, ErrorCode, ErrorDetail, ErrorResponse
from soldier.api.routes import register_routes
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    This factory function creates a fully configured FastAPI app with:
    - CORS middleware
    - Request context middleware
    - Global exception handlers
    - OpenTelemetry instrumentation
    - All API routes registered

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Soldier API",
        description="Production-grade cognitive engine for conversational AI",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request context middleware
    app.add_middleware(RequestContextMiddleware)

    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.api.rate_limit.enabled,
        exclude_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
    )

    # Register exception handlers
    _register_exception_handlers(app)

    # Register routes
    register_routes(app)

    # Add OpenTelemetry instrumentation
    if settings.observability.tracing.enabled:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("opentelemetry_instrumentation_enabled")

    logger.info(
        "app_created",
        debug=settings.debug,
        cors_origins=settings.api.cors_origins,
    )

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Args:
        app: FastAPI application
    """

    @app.exception_handler(SoldierAPIError)
    async def soldier_api_error_handler(
        request: Request, exc: SoldierAPIError
    ) -> JSONResponse:
        """Handle SoldierAPIError and its subclasses."""
        logger.warning(
            "api_error",
            error_code=exc.error_code.value,
            message=exc.message,
            path=request.url.path,
        )

        error_body = ErrorBody(
            code=exc.error_code,
            message=exc.message,
        )

        # Add rule_id if available (for RuleViolationError)
        if hasattr(exc, "rule_id") and exc.rule_id:
            error_body.rule_id = exc.rule_id

        response = ErrorResponse(error=error_body)

        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI request validation errors."""
        logger.warning(
            "validation_error",
            errors=exc.errors(),
            path=request.url.path,
        )

        details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            details.append(ErrorDetail(field=field, message=error["msg"]))

        error_body = ErrorBody(
            code=ErrorCode.INVALID_REQUEST,
            message="Request validation failed",
            details=details,
        )

        response = ErrorResponse(error=error_body)

        return JSONResponse(
            status_code=400,
            content=response.model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.warning(
            "pydantic_validation_error",
            errors=exc.errors(),
            path=request.url.path,
        )

        details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            details.append(ErrorDetail(field=field, message=error["msg"]))

        error_body = ErrorBody(
            code=ErrorCode.INVALID_REQUEST,
            message="Data validation failed",
            details=details,
        )

        response = ErrorResponse(error=error_body)

        return JSONResponse(
            status_code=400,
            content=response.model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(
            "unexpected_error",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
        )

        error_body = ErrorBody(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
        )

        response = ErrorResponse(error=error_body)

        return JSONResponse(
            status_code=500,
            content=response.model_dump(),
        )

    logger.debug("exception_handlers_registered")


# Create the app instance for uvicorn
app = create_app()
