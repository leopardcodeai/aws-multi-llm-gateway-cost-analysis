import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    from src.config import Settings, GatewaySettings, ClassifierSettings, RouterSettings, RouterTierSettings, CacheSettings, CacheRedisSettings, CacheQdrantSettings, AuthSettings, ObservabilitySettings, ModelSettings, FallbackSettings

    monkeypatch.setattr("src.config.get_settings", lambda: Settings(
        gateway=GatewaySettings(),
        classifier=ClassifierSettings(),
        router=RouterSettings(tiers={
            "simple": RouterTierSettings(primary="meta.llama3-1-8b-instruct-v1:0", fallback="meta.llama3-8b-instruct-v1:0", provider="bedrock", max_tokens=4096, temperature=0.1),
            "medium": RouterTierSettings(primary="meta.llama3-1-70b-instruct-v1:0", fallback="meta.llama4-scout-17b-instruct-v1:0", provider="bedrock", max_tokens=8192, temperature=0.3),
            "complex": RouterTierSettings(primary="gpt-4o-mini", fallback="gpt-4o", final_fallback="anthropic.claude-3-5-sonnet-20241022-v2:0", provider="openai", max_tokens=16384, temperature=0.5),
        }),
        cache=CacheSettings(redis=CacheRedisSettings(), qdrant=CacheQdrantSettings()),
        auth=AuthSettings(),
        observability=ObservabilitySettings(),
        models=ModelSettings(),
        fallback=FallbackSettings(),
    ))