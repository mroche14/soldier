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

    # CRUD routes for agent configuration management
    from soldier.api.routes.agents import router as agents_router
    from soldier.api.routes.migrations import router as migrations_router
    from soldier.api.routes.publish import router as publish_router
    from soldier.api.routes.rules import router as rules_router
    from soldier.api.routes.scenarios import router as scenarios_router
    from soldier.api.routes.templates import router as templates_router
    from soldier.api.routes.tools import router as tools_router
    from soldier.api.routes.variables import router as variables_router

    router.include_router(agents_router, tags=["Agents"])
    router.include_router(rules_router, tags=["Rules"])
    router.include_router(scenarios_router, tags=["Scenarios"])
    router.include_router(templates_router, tags=["Templates"])
    router.include_router(variables_router, tags=["Variables"])
    router.include_router(tools_router, tags=["Tools"])
    router.include_router(publish_router, tags=["Publishing"])
    router.include_router(migrations_router, tags=["Migrations"])

    logger.debug(
        "v1_router_created",
        routes=[
            "chat",
            "sessions",
            "agents",
            "rules",
            "scenarios",
            "templates",
            "variables",
            "tools",
            "publish",
            "migrations",
        ],
    )

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
