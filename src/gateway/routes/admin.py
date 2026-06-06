from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import structlog

from src.auth.auth import create_tenant
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter()


class CreateTenantRequest(BaseModel):
    tenant_id: str
    name: str
    monthly_quota: Optional[int] = None
    daily_quota: Optional[int] = None
    allowed_models: Optional[List[str]] = None


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    monthly_quota: int
    daily_quota: int
    used_tokens_month: int
    used_requests_day: int
    allowed_models: List[str]
    api_key: Optional[str] = None


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant_endpoint(body: CreateTenantRequest):
    try:
        api_key = await create_tenant(
            tenant_id=body.tenant_id,
            name=body.name,
            monthly_quota=body.monthly_quota,
            daily_quota=body.daily_quota,
            allowed_models=body.allowed_models,
        )
        logger.info("tenant_created_via_api", tenant_id=body.tenant_id)
        return TenantResponse(
            tenant_id=body.tenant_id,
            name=body.name,
            monthly_quota=body.monthly_quota
            or settings.auth.default_quotas["monthly_tokens"],
            daily_quota=body.daily_quota
            or settings.auth.default_quotas["daily_requests"],
            used_tokens_month=0,
            used_requests_day=0,
            allowed_models=body.allowed_models
            or settings.auth.default_quotas["allowed_models"],
            api_key=api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("create_tenant_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create tenant")


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, request: Request):
    if (
        request.state.tenant.tenant_id != tenant_id
        and "admin" not in request.state.tenant.allowed_models
    ):
        raise HTTPException(status_code=403, detail="Not authorized")

    # This would need a get_tenant_by_id function
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/stats")
async def get_stats(request: Request):
    tenant = request.state.tenant
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "monthly_quota": tenant.monthly_quota,
        "daily_quota": tenant.daily_quota,
        "used_tokens_month": tenant.used_tokens_month,
        "used_requests_day": tenant.used_requests_day,
        "quota_usage_percent": {
            "monthly": (tenant.used_tokens_month / tenant.monthly_quota * 100)
            if tenant.monthly_quota > 0
            else 0,
            "daily": (tenant.used_requests_day / tenant.daily_quota * 100)
            if tenant.daily_quota > 0
            else 0,
        },
        "allowed_models": tenant.allowed_models,
    }
