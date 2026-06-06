import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
import time

from src.cache.cache import SemanticCache, CacheEntry


class TestSemanticCache:
    @pytest.fixture
    def cache(self):
        c = SemanticCache()
        c._initialized = True
        c.redis = AsyncMock()
        c.qdrant = AsyncMock()
        c.embedder = MagicMock()
        c.embedder.encode.return_value = [[0.1] * 384]
        return c

    @pytest.mark.asyncio
    async def test_exact_cache_hit(self, cache):
        entry = CacheEntry(
            response={"content": "cached response", "role": "assistant"},
            model="test-model",
            tokens=100,
            cost=0.001,
            timestamp=time.time(),
        )
        cache.redis.get.return_value = json.dumps(entry.__dict__)

        result = await cache.get_exact([{"role": "user", "content": "test prompt"}])

        assert result is not None
        assert result.model == "test-model"
        assert result.tokens == 100

    @pytest.mark.asyncio
    async def test_exact_cache_miss(self, cache):
        cache.redis.get.return_value = None

        result = await cache.get_exact([{"role": "user", "content": "test prompt"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_cache_hit(self, cache):
        entry = CacheEntry(
            response={"content": "semantic cached", "role": "assistant"},
            model="test-model",
            tokens=150,
            cost=0.002,
            timestamp=time.time(),
        )

        mock_hit = MagicMock()
        mock_hit.score = 0.95
        mock_hit.payload = entry.__dict__
        mock_hit.payload["response"] = entry.response
        mock_hit.payload["model"] = entry.model
        mock_hit.payload["tokens"] = entry.tokens
        mock_hit.payload["cost"] = entry.cost
        mock_hit.payload["timestamp"] = entry.timestamp

        cache.qdrant.search.return_value = [mock_hit]

        result = await cache.get_semantic([{"role": "user", "content": "similar prompt"}])

        assert result is not None
        assert result.model == "test-model"

    @pytest.mark.asyncio
    async def test_semantic_cache_miss_below_threshold(self, cache):
        mock_hit = MagicMock()
        mock_hit.score = 0.85
        mock_hit.payload = {"response": {}, "model": "test", "tokens": 100, "cost": 0.001, "timestamp": time.time()}

        cache.qdrant.search.return_value = [mock_hit]

        result = await cache.get_semantic([{"role": "user", "content": "different prompt"}], threshold=0.92)

        assert result is None

    @pytest.mark.asyncio
    async def test_normalize_prompt(self, cache):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello World"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        normalized = cache._normalize_prompt(messages)
        assert normalized == "hello world how are you?"

    def test_make_key(self, cache):
        key1 = cache._make_key("test prompt")
        key2 = cache._make_key("test prompt")
        key3 = cache._make_key("different prompt")

        assert key1 == key2
        assert key1 != key3
        assert key1.startswith("llmgw:cache:")