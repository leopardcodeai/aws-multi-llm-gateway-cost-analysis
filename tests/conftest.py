import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    from src.config import (
        AuthSettings,
        CacheQdrantSettings,
        CacheRedisSettings,
        CacheSettings,
        ClassifierSettings,
        FallbackSettings,
        GatewaySettings,
        ModelSettings,
        ObservabilitySettings,
        RouterSettings,
        RouterTierSettings,
        Settings,
    )

    mock_settings_obj = Settings(
        gateway=GatewaySettings(),
        classifier=ClassifierSettings(),
        router=RouterSettings(
            tiers={
                "simple": RouterTierSettings(
                    primary="meta.llama3-1-8b-instruct-v1:0",
                    fallback="meta.llama3-8b-instruct-v1:0",
                    provider="bedrock",
                    max_tokens=4096,
                    temperature=0.1,
                ),
                "medium": RouterTierSettings(
                    primary="meta.llama3-1-70b-instruct-v1:0",
                    fallback="meta.llama4-scout-17b-instruct-v1:0",
                    provider="bedrock",
                    max_tokens=8192,
                    temperature=0.3,
                ),
                "complex": RouterTierSettings(
                    primary="gpt-4o-mini",
                    fallback="gpt-4o",
                    final_fallback="anthropic.claude-3-5-sonnet-20241022-v2:0",
                    provider="openai",
                    max_tokens=16384,
                    temperature=0.5,
                ),
            }
        ),
        cache=CacheSettings(redis=CacheRedisSettings(), qdrant=CacheQdrantSettings()),
        auth=AuthSettings(),
        observability=ObservabilitySettings(),
        models=ModelSettings(),
        fallback=FallbackSettings(),
    )

    # Patch get_settings in all modules that use it
    monkeypatch.setattr("src.config.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.classifier.classifier.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.router.router.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.cache.cache.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.auth.auth.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.gateway.main.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.gateway.middleware.auth.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.gateway.middleware.rate_limit.get_settings", lambda: mock_settings_obj)
    monkeypatch.setattr("src.gateway.routes.chat.get_settings", lambda: mock_settings_obj)


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table for auth tests."""
    with patch("src.auth.auth._get_table") as mock_table:
        yield mock_table


@pytest.fixture
def mock_bedrock_runtime():
    """Mock Bedrock runtime for classifier and router tests."""
    with patch("src.classifier.classifier.bedrock_runtime") as mock_bedrock:
        yield mock_bedrock

    with patch("src.router.router.bedrock_runtime") as mock_bedrock:
        yield mock_bedrock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for router tests."""
    with patch("src.router.router._get_openai_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_redis():
    """Mock Redis for cache tests."""
    with patch("src.cache.cache.redis") as mock_redis:
        yield mock_redis


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant for cache tests."""
    with patch("src.cache.cache.AsyncQdrantClient") as mock_qdrant:
        yield mock_qdrant
