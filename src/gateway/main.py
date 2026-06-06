from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.gateway.middleware.auth import AuthMiddleware
from src.gateway.middleware.logging import LoggingMiddleware
from src.gateway.middleware.rate_limit import RateLimitMiddleware
from src.gateway.routes import admin, chat, health
from src.observability.metrics import setup_metrics

logger = structlog.get_logger()


def _get_gateway_settings():
    return get_settings().gateway


def _get_debug_mode():
    return get_settings().gateway.debug


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_llm_gateway", version="0.1.0")
    setup_metrics(app)
    yield
    logger.info("shutting_down_llm_gateway")


app = FastAPI(
    title="LLM Gateway",
    description="Multi-LLM Routing & Cost-Optimization Gateway",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _get_debug_mode() else None,
    redoc_url="/redoc" if _get_debug_mode() else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/v1", tags=["chat"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": "internal_error"},
    )


if __name__ == "__main__":
    import uvicorn

    gateway_settings = _get_gateway_settings()
    uvicorn.run(
        "src.gateway.main:app",
        host=gateway_settings.host,
        port=gateway_settings.port,
        workers=gateway_settings.workers,
        reload=gateway_settings.debug,
    )
