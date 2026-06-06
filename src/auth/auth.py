import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass

import boto3
import structlog
from botocore.exceptions import ClientError

from src.config import get_settings

logger = structlog.get_logger()


def _get_auth_settings():
    return get_settings().auth


def _get_dynamodb_resource():
    auth_settings = _get_auth_settings()
    return boto3.resource("dynamodb", region_name=auth_settings.dynamodb_region)


def _get_table():
    dynamodb = _get_dynamodb_resource()
    auth_settings = _get_auth_settings()
    return dynamodb.Table(auth_settings.dynamodb_table)


@dataclass
class Tenant:
    tenant_id: str
    api_key_hash: str
    name: str
    monthly_quota: int
    daily_quota: int
    used_tokens_month: int
    used_requests_day: int
    allowed_models: list
    created_at: float
    expires_at: float | None = None


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    auth_settings = _get_auth_settings()
    return f"{auth_settings.api_key_prefix}{secrets.token_urlsafe(32)}"


async def create_tenant(
    tenant_id: str,
    name: str,
    monthly_quota: int | None = None,
    daily_quota: int | None = None,
    allowed_models: list | None = None,
) -> str:
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    now = time.time()
    auth_settings = _get_auth_settings()
    item = {
        "tenant_id": tenant_id,
        "api_key_hash": api_key_hash,
        "name": name,
        "monthly_quota": monthly_quota or auth_settings.default_quotas["monthly_tokens"],
        "daily_quota": daily_quota or auth_settings.default_quotas["daily_requests"],
        "used_tokens_month": 0,
        "used_requests_day": 0,
        "allowed_models": allowed_models or auth_settings.default_quotas["allowed_models"],
        "created_at": now,
        "expires_at": None,
        "month_start": int(now // (30 * 86400)) * (30 * 86400),
        "day_start": int(now // 86400) * 86400,
    }

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _get_table().put_item(
                Item=item, ConditionExpression="attribute_not_exists(tenant_id)"
            ),
        )
        logger.info("tenant_created", tenant_id=tenant_id)
        return api_key
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"Tenant {tenant_id} already exists")
        raise


async def get_tenant_by_key(api_key: str) -> Tenant | None:
    api_key_hash = hash_api_key(api_key)

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _get_table().query(
                IndexName="api_key_hash-index",
                KeyConditionExpression="api_key_hash = :hk",
                ExpressionAttributeValues={":hk": api_key_hash},
            ),
        )

        items = response.get("Items", [])
        if not items:
            return None

        item = items[0]
        return Tenant(
            tenant_id=item["tenant_id"],
            api_key_hash=item["api_key_hash"],
            name=item["name"],
            monthly_quota=item["monthly_quota"],
            daily_quota=item["daily_quota"],
            used_tokens_month=item.get("used_tokens_month", 0),
            used_requests_day=item.get("used_requests_day", 0),
            allowed_models=item.get("allowed_models", ["auto"]),
            created_at=item["created_at"],
            expires_at=item.get("expires_at"),
        )

    except Exception as e:
        logger.error("get_tenant_failed", error=str(e))
        return None


async def check_quota(tenant: Tenant, estimated_tokens: int) -> tuple[bool, str]:
    now = time.time()
    int(now // (30 * 86400)) * (30 * 86400)
    int(now // 86400) * 86400

    if tenant.used_tokens_month + estimated_tokens > tenant.monthly_quota:
        return False, "Monthly token quota exceeded"

    if tenant.used_requests_day >= tenant.daily_quota:
        return False, "Daily request quota exceeded"

    return True, "OK"


async def record_usage(tenant_id: str, tokens: int):
    now = time.time()
    month_start = int(now // (30 * 86400)) * (30 * 86400)
    day_start = int(now // 86400) * 86400

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _get_table().update_item(
                Key={"tenant_id": tenant_id},
                UpdateExpression="ADD used_tokens_month :tokens, used_requests_day :req SET month_start = :ms, day_start = :ds",
                ExpressionAttributeValues={
                    ":tokens": tokens,
                    ":req": 1,
                    ":ms": month_start,
                    ":ds": day_start,
                },
            ),
        )
    except Exception as e:
        logger.error("record_usage_failed", tenant_id=tenant_id, error=str(e))


async def is_model_allowed(tenant: Tenant, model: str) -> bool:
    if "auto" in tenant.allowed_models or "*" in tenant.allowed_models:
        return True
    return model in tenant.allowed_models
