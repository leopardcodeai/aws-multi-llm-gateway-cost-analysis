import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from src.auth.auth import (
    hash_api_key,
    generate_api_key,
    create_tenant,
    get_tenant_by_key,
    check_quota,
    record_usage,
    is_model_allowed,
)


class TestAuth:
    def test_hash_api_key(self):
        key = "llmgw_test123"
        hashed = hash_api_key(key)
        assert len(hashed) == 64
        assert hash_api_key(key) == hashed

    def test_generate_api_key(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1.startswith("llmgw_")
        assert key1 != key2
        assert len(key1) > 20

    @pytest.mark.asyncio
    async def test_create_tenant(self, mock_dynamodb_table):
        mock_dynamodb_table.put_item = AsyncMock()

        api_key = await create_tenant("tenant-1", "Test Tenant", monthly_quota=50000)

        assert api_key.startswith("llmgw_")
        mock_dynamodb_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tenant_by_key(self, mock_dynamodb_table):
        mock_dynamodb_table.query = AsyncMock(
            return_value={
                "Items": [
                    {
                        "tenant_id": "tenant-1",
                        "api_key_hash": hash_api_key("llmgw_test"),
                        "name": "Test Tenant",
                        "monthly_quota": 100000,
                        "daily_quota": 1000,
                        "used_tokens_month": 5000,
                        "used_requests_day": 10,
                        "allowed_models": ["auto"],
                        "created_at": time.time(),
                    }
                ]
            }
        )

        tenant = await get_tenant_by_key("llmgw_test")

        assert tenant is not None
        assert tenant.tenant_id == "tenant-1"
        assert tenant.monthly_quota == 100000

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self, mock_dynamodb_table):
        mock_dynamodb_table.query = AsyncMock(return_value={"Items": []})

        tenant = await get_tenant_by_key("llmgw_invalid")

        assert tenant is None

    @pytest.mark.asyncio
    async def test_check_quota_ok(self):
        tenant = MagicMock()
        tenant.monthly_quota = 100000
        tenant.daily_quota = 1000
        tenant.used_tokens_month = 50000
        tenant.used_requests_day = 100

        ok, msg = await check_quota(tenant, 1000)
        assert ok is True
        assert msg == "OK"

    @pytest.mark.asyncio
    async def test_check_quota_exceeded_monthly(self):
        tenant = MagicMock()
        tenant.monthly_quota = 100000
        tenant.daily_quota = 1000
        tenant.used_tokens_month = 99500
        tenant.used_requests_day = 100

        ok, msg = await check_quota(tenant, 1000)
        assert ok is False
        assert "Monthly" in msg

    @pytest.mark.asyncio
    async def test_check_quota_exceeded_daily(self):
        tenant = MagicMock()
        tenant.monthly_quota = 100000
        tenant.daily_quota = 1000
        tenant.used_tokens_month = 50000
        tenant.used_requests_day = 1000

        ok, msg = await check_quota(tenant, 100)
        assert ok is False
        assert "Daily" in msg

    @pytest.mark.asyncio
    async def test_is_model_allowed_auto(self):
        tenant = MagicMock()
        tenant.allowed_models = ["auto"]

        result = await is_model_allowed(tenant, "gpt-4o")
        assert result is True

        result = await is_model_allowed(tenant, "any-model")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_model_allowed_specific(self):
        tenant = MagicMock()
        tenant.allowed_models = ["gpt-4o-mini", "meta.llama3-1-8b-instruct-v1:0"]

        result = await is_model_allowed(tenant, "gpt-4o-mini")
        assert result is True

        result = await is_model_allowed(tenant, "gpt-4o")
        assert result is False
