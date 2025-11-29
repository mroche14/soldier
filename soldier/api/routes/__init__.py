"""API route registration.

This module provides helper functions for registering API routers
with the FastAPI application.
"""

from fastapi import APIRouter, FastAPI

from soldier.observability.logging import get_logger

logger = get_logger(__name__)


def create_v1_router() -> APIRouter:
    """Create the v1 API router with all routes.

    Returns:
        APIRouter with all v1 routes registered
    """
    router = APIRouter(prefix="/v1")

    # Import and include route modules
    from soldier.api.routes.chat import router as chat_router
    from soldier.api.routes.sessions import router as sessions_router

    router.include_router(chat_router, tags=["Chat"])
    router.include_router(sessions_router, tags=["Sessions"])

    logger.debug("v1_router_created", routes=["chat", "sessions"])

    return router


def register_routes(app: FastAPI) -> None:
    """Register all routes with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Register v1 API routes
    v1_router = create_v1_router()
    app.include_router(v1_router)

    # Register health routes at root level
    from soldier.api.routes.health import router as health_router

    app.include_router(health_router, tags=["Health"])

    logger.info("routes_registered")
