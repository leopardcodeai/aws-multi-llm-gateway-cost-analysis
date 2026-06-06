from fastapi import APIRouter
from src.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "llm-gateway",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    checks = {
        "redis": "unknown",
        "qdrant": "unknown",
        "bedrock": "unknown",
        "openai": "unknown",
        "dynamodb": "unknown",
    }
    return {"status": "ready", "checks": checks}