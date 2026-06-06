import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.auth.auth import get_tenant_by_key
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

PUBLIC_PATHS = ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth.enabled:
            return await call_next(request)

        if any(request.url.path.startswith(path) for path in PUBLIC_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing or invalid Authorization header",
                    "type": "auth_error",
                },
            )

        api_key = auth_header[7:]
        tenant = await get_tenant_by_key(api_key)

        if not tenant:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key", "type": "auth_error"},
            )

        if tenant.expires_at and tenant.expires_at < time.time():
            return JSONResponse(
                status_code=401,
                content={"detail": "API key expired", "type": "auth_error"},
            )

        request.state.tenant = tenant
        request.state.api_key = api_key

        return await call_next(request)
