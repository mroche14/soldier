<a id="soldier.api.middleware.auth"></a>

# soldier.api.middleware.auth

JWT authentication middleware for API requests.

<a id="soldier.api.middleware.auth.get_jwt_secret"></a>

#### get\_jwt\_secret

```python
def get_jwt_secret() -> str
```

Get JWT secret from environment.

<a id="soldier.api.middleware.auth.get_jwt_algorithm"></a>

#### get\_jwt\_algorithm

```python
def get_jwt_algorithm() -> str
```

Get JWT algorithm from environment.

<a id="soldier.api.middleware.auth.get_tenant_context"></a>

#### get\_tenant\_context

```python
async def get_tenant_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None,
                           Depends(security_scheme)]
) -> TenantContext
```

Extract and validate tenant context from JWT token.

This dependency validates the JWT and extracts tenant information
for use throughout the request lifecycle.

**Arguments**:

- `request` - The FastAPI request object
- `credentials` - Bearer token credentials from Authorization header
  

**Returns**:

  TenantContext with tenant_id and optional user info
  

**Raises**:

- `HTTPException` - 401 if token is missing, invalid, or expired

