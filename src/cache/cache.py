import hashlib
import json
from dataclasses import dataclass

import redis.asyncio as redis
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from src.config import get_settings

logger = structlog.get_logger()


def _get_cache_settings():
    return get_settings().cache


def _get_model_settings():
    return get_settings().models


@dataclass
class CacheEntry:
    response: dict
    model: str
    tokens: int
    cost: float
    timestamp: float


class SemanticCache:
    def __init__(self):
        self.redis: redis.Redis | None = None
        self.qdrant: AsyncQdrantClient | None = None
        self.embedder: SentenceTransformer | None = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        cache_settings = _get_cache_settings()
        model_settings = _get_model_settings()

        self.redis = redis.Redis(
            host=cache_settings.redis.host,
            port=cache_settings.redis.port,
            db=cache_settings.redis.db,
            password=cache_settings.redis.password,
            decode_responses=True,
        )

        self.qdrant = AsyncQdrantClient(
            host=cache_settings.qdrant.host,
            port=cache_settings.qdrant.port,
            https=cache_settings.qdrant.https,
            api_key=cache_settings.qdrant.api_key,
        )

        self.embedder = SentenceTransformer(
            model_settings.embedding_model, device=model_settings.device
        )

        await self._ensure_collection()
        self._initialized = True
        logger.info("cache_initialized")

    async def _ensure_collection(self):
        collections = await self.qdrant.get_collections()
        names = [c.name for c in collections.collections]

        cache_settings = _get_cache_settings()
        if cache_settings.qdrant.collection not in names:
            await self.qdrant.create_collection(
                collection_name=cache_settings.qdrant.collection,
                vectors_config=VectorParams(
                    size=cache_settings.qdrant.vector_size,
                    distance=Distance.COSINE,
                    hnsw_config={"ef_construct": cache_settings.qdrant.hnsw_ef},
                ),
            )
            logger.info("qdrant_collection_created", collection=cache_settings.qdrant.collection)

    def _normalize_prompt(self, messages: list) -> str:
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        return " ".join(user_msgs).strip().lower()

    def _make_key(self, normalized: str) -> str:
        cache_settings = _get_cache_settings()
        return f"{cache_settings.redis.key_prefix}{hashlib.sha256(normalized.encode()).hexdigest()}"

    async def get_exact(self, messages: list) -> CacheEntry | None:
        if not _get_cache_settings().enabled or not self.redis:
            return None

        normalized = self._normalize_prompt(messages)
        key = self._make_key(normalized)

        try:
            data = await self.redis.get(key)
            if data:
                entry = CacheEntry(**json.loads(data))
                logger.debug("exact_cache_hit", key=key)
                return entry
        except Exception as e:
            logger.warning("redis_get_failed", error=str(e))

        return None

    async def set_exact(self, messages: list, entry: CacheEntry):
        if not _get_cache_settings().enabled or not self.redis:
            return

        normalized = self._normalize_prompt(messages)
        key = self._make_key(normalized)

        try:
            await self.redis.setex(
                key,
                _get_cache_settings().redis.ttl,
                json.dumps(entry.__dict__),
            )
        except Exception as e:
            logger.warning("redis_set_failed", error=str(e))

    async def get_semantic(
        self, messages: list, threshold: float | None = None
    ) -> CacheEntry | None:
        cache_settings = _get_cache_settings()
        if not cache_settings.enabled or not self.qdrant or not self.embedder:
            return None

        normalized = self._normalize_prompt(messages)
        threshold = threshold or cache_settings.qdrant.similarity_threshold

        try:
            embedding = self.embedder.encode([normalized])[0].tolist()

            results = await self.qdrant.search(
                collection_name=cache_settings.qdrant.collection,
                query_vector=embedding,
                limit=1,
                score_threshold=threshold,
                with_payload=True,
            )

            if results:
                hit = results[0]
                payload = hit.payload or {}
                if isinstance(payload, dict):
                    entry = CacheEntry(
                        response=payload.get("response", {}),
                        model=payload.get("model", ""),
                        tokens=payload.get("tokens", 0),
                        cost=payload.get("cost", 0.0),
                        timestamp=payload.get("timestamp", 0.0),
                    )
                    logger.debug("semantic_cache_hit", score=hit.score, threshold=threshold)
                    return entry

        except Exception as e:
            logger.warning("qdrant_search_failed", error=str(e))

        return None

    async def set_semantic(self, messages: list, entry: CacheEntry):
        cache_settings = _get_cache_settings()
        if not cache_settings.enabled or not self.qdrant or not self.embedder:
            return

        normalized = self._normalize_prompt(messages)

        try:
            embedding = self.embedder.encode([normalized])[0].tolist()

            point = PointStruct(
                id=hashlib.md5(normalized.encode()).hexdigest()[:16],
                vector=embedding,
                payload={
                    "prompt": normalized[:500],
                    "response": entry.response,
                    "model": entry.model,
                    "tokens": entry.tokens,
                    "cost": entry.cost,
                    "timestamp": entry.timestamp,
                },
            )

            await self.qdrant.upsert(
                collection_name=cache_settings.qdrant.collection,
                points=[point],
            )

        except Exception as e:
            logger.warning("qdrant_upsert_failed", error=str(e))

    async def close(self):
        if self.redis:
            await self.redis.close()
        if self.qdrant:
            await self.qdrant.close()


cache = SemanticCache()
