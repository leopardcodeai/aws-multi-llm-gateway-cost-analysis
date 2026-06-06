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
settings = get_settings()


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

        self.redis = redis.Redis(
            host=settings.cache.redis.host,
            port=settings.cache.redis.port,
            db=settings.cache.redis.db,
            password=settings.cache.redis.password,
            decode_responses=True,
        )

        self.qdrant = AsyncQdrantClient(
            host=settings.cache.qdrant.host,
            port=settings.cache.qdrant.port,
            https=settings.cache.qdrant.https,
            api_key=settings.cache.qdrant.api_key,
        )

        self.embedder = SentenceTransformer(
            settings.models.embedding_model, device=settings.models.device
        )

        await self._ensure_collection()
        self._initialized = True
        logger.info("cache_initialized")

    async def _ensure_collection(self):
        collections = await self.qdrant.get_collections()
        names = [c.name for c in collections.collections]

        if settings.cache.qdrant.collection not in names:
            await self.qdrant.create_collection(
                collection_name=settings.cache.qdrant.collection,
                vectors_config=VectorParams(
                    size=settings.cache.qdrant.vector_size,
                    distance=Distance.COSINE,
                    hnsw_config={"ef_construct": settings.cache.qdrant.hnsw_ef},
                ),
            )
            logger.info("qdrant_collection_created", collection=settings.cache.qdrant.collection)

    def _normalize_prompt(self, messages: list) -> str:
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        return " ".join(user_msgs).strip().lower()

    def _make_key(self, normalized: str) -> str:
        return f"{settings.cache.redis.key_prefix}{hashlib.sha256(normalized.encode()).hexdigest()}"

    async def get_exact(self, messages: list) -> CacheEntry | None:
        if not settings.cache.enabled or not self.redis:
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
        if not settings.cache.enabled or not self.redis:
            return

        normalized = self._normalize_prompt(messages)
        key = self._make_key(normalized)

        try:
            await self.redis.setex(
                key,
                settings.cache.redis.ttl,
                json.dumps(entry.__dict__),
            )
        except Exception as e:
            logger.warning("redis_set_failed", error=str(e))

    async def get_semantic(
        self, messages: list, threshold: float | None = None
    ) -> CacheEntry | None:
        if not settings.cache.enabled or not self.qdrant or not self.embedder:
            return None

        normalized = self._normalize_prompt(messages)
        threshold = threshold or settings.cache.qdrant.similarity_threshold

        try:
            embedding = self.embedder.encode([normalized])[0].tolist()

            results = await self.qdrant.search(
                collection_name=settings.cache.qdrant.collection,
                query_vector=embedding,
                limit=1,
                score_threshold=threshold,
                with_payload=True,
            )

            if results:
                hit = results[0]
                payload = hit.payload
                entry = CacheEntry(
                    response=payload["response"],
                    model=payload["model"],
                    tokens=payload["tokens"],
                    cost=payload["cost"],
                    timestamp=payload["timestamp"],
                )
                logger.debug("semantic_cache_hit", score=hit.score, threshold=threshold)
                return entry

        except Exception as e:
            logger.warning("qdrant_search_failed", error=str(e))

        return None

    async def set_semantic(self, messages: list, entry: CacheEntry):
        if not settings.cache.enabled or not self.qdrant or not self.embedder:
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
                collection_name=settings.cache.qdrant.collection,
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
