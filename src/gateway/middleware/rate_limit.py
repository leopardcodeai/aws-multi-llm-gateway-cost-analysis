import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

request_counts: dict[str, int] = {}
window_starts: dict[str, float] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not hasattr(request.state, "tenant"):
            return await call_next(request)

        tenant_id = request.state.tenant.tenant_id
        now = time.time()

        minute_key = f"{tenant_id}:minute"
        hour_key = f"{tenant_id}:hour"

        if minute_key not in window_starts or now - window_starts[minute_key] >= 60:
            window_starts[minute_key] = now
            request_counts[minute_key] = 0

        if hour_key not in window_starts or now - window_starts[hour_key] >= 3600:
            window_starts[hour_key] = now
            request_counts[hour_key] = 0

        request_counts[minute_key] = request_counts.get(minute_key, 0) + 1
        request_counts[hour_key] = request_counts.get(hour_key, 0) + 1

        rpm_limit = settings.auth.rate_limit["requests_per_minute"]
        rph_limit = settings.auth.rate_limit["requests_per_hour"]

        if request_counts[minute_key] > rpm_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded (per minute)",
                    "type": "rate_limit_error",
                },
                headers={"Retry-After": "60"},
            )

        if request_counts[hour_key] > rph_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded (per hour)",
                    "type": "rate_limit_error",
                },
                headers={"Retry-After": "3600"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(rpm_limit)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, rpm_limit - request_counts[minute_key])
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(rph_limit)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(0, rph_limit - request_counts[hour_key])
        )

        return response
