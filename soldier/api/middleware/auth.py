"""JWT authentication middleware for API requests."""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from soldier.api.models.context import TenantContext
from soldier.observability.logging import get_logger

logger = get_logger(__name__)

# Security scheme for OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)


def get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    secret = os.environ.get("SOLDIER_JWT_SECRET")
    if not secret:
        raise RuntimeError("SOLDIER_JWT_SECRET environment variable not set")
    return secret


def get_jwt_algorithm() -> str:
    """Get JWT algorithm from environment."""
    return os.environ.get("SOLDIER_JWT_ALGORITHM", "HS256")


async def get_tenant_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> TenantContext:
    """Extract and validate tenant context from JWT token.

    This dependency validates the JWT and extracts tenant information
    for use throughout the request lifecycle.

    Args:
        request: The FastAPI request object
        credentials: Bearer token credentials from Authorization header

    Returns:
        TenantContext with tenant_id and optional user info

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    if credentials is None:
        logger.warning("auth_missing_token", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        secret = get_jwt_secret()
        algorithm = get_jwt_algorithm()

        payload = jwt.decode(token, secret, algorithms=[algorithm])

        # Extract required tenant_id
        tenant_id_str = payload.get("tenant_id")
        if not tenant_id_str:
            logger.warning("auth_missing_tenant_id", path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing tenant_id claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Build context from claims
        context = TenantContext(
            tenant_id=tenant_id_str,
            user_id=payload.get("sub"),
            roles=payload.get("roles", []),
            tier=payload.get("tier", "free"),
        )

        logger.debug(
            "auth_success",
            tenant_id=str(context.tenant_id),
            user_id=context.user_id,
        )

        return context

    except JWTError as e:
        logger.warning("auth_jwt_error", error=str(e), path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except ValidationError as e:
        logger.warning("auth_validation_error", error=str(e), path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


# Type alias for dependency injection
TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]
