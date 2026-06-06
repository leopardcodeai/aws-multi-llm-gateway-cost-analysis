from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.gateway.routes import chat, health, admin
from src.gateway.middleware.auth import AuthMiddleware
from src.gateway.middleware.rate_limit import RateLimitMiddleware
from src.gateway.middleware.logging import LoggingMiddleware
from src.observability.metrics import setup_metrics
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


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
    docs_url="/docs" if settings.gateway.debug else None,
    redoc_url="/redoc" if settings.gateway.debug else None,
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

    uvicorn.run(
        "src.gateway.main:app",
        host=settings.gateway.host,
        port=settings.gateway.port,
        workers=settings.gateway.workers,
        reload=settings.gateway.debug,
    )
