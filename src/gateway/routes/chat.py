import time
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

from src.router.router import route_request, ModelResponse
from src.cache.cache import cache, CacheEntry
from src.auth.auth import check_quota, record_usage, is_model_allowed
from src.observability.metrics import (
    record_request, record_cache_hit, record_cache_miss, record_error
)
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    tenant_id: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    cost_usd: float
    cached: bool = False
    tier: Optional[str] = None
    fallback_used: bool = False


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: Request, body: ChatCompletionRequest):
    start = time.perf_counter()
    tenant = request.state.tenant

    if not await is_model_allowed(tenant, body.model):
        raise HTTPException(status_code=403, detail=f"Model {body.model} not allowed for this tenant")

    estimated_tokens = sum(len(m.content) for m in body.messages) // 4 + body.max_tokens
    quota_ok, quota_msg = await check_quota(tenant, estimated_tokens)
    if not quota_ok:
        raise HTTPException(status_code=429, detail=quota_msg)

    if settings.cache.enabled:
        cached = await cache.get_exact([m.model_dump() for m in body.messages])
        if cached:
            record_cache_hit("exact")
            latency = (time.perf_counter() - start) * 1000
            record_request(
                model=cached.model, tier="cached", status="success", cached=True,
                latency=latency/1000, tokens=cached.tokens, cost=cached.cost,
                saved=estimate_savings(cached.model, cached.tokens)
            )
            return build_response(cached.response, cached.model, cached.tokens, cached.cost, True, "cached")

        cached = await cache.get_semantic([m.model_dump() for m in body.messages])
        if cached:
            record_cache_hit("semantic")
            latency = (time.perf_counter() - start) * 1000
            record_request(
                model=cached.model, tier="cached", status="success", cached=True,
                latency=latency/1000, tokens=cached.tokens, cost=cached.cost,
                saved=estimate_savings(cached.model, cached.tokens)
            )
            return build_response(cached.response, cached.model, cached.tokens, cached.cost, True, "cached")

    record_cache_miss()

    try:
        response: ModelResponse = await route_request(
            messages=[m.model_dump() for m in body.messages],
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )

        latency = (time.perf_counter() - start) * 1000
        saved = estimate_savings(response.model, response.tokens_used)

        record_request(
            model=response.model, tier=response.provider, status="success", cached=False,
            latency=latency/1000, tokens=response.tokens_used, cost=response.cost_usd, saved=saved
        )

        if response.fallback_used:
            from src.observability.metrics import record_fallback
            record_fallback("primary", response.model)

        entry = CacheEntry(
            response={"content": response.content, "role": "assistant"},
            model=response.model,
            tokens=response.tokens_used,
            cost=response.cost_usd,
            timestamp=time.time(),
        )

        await cache.set_exact([m.model_dump() for m in body.messages], entry)
        await cache.set_semantic([m.model_dump() for m in body.messages], entry)

        await record_usage(tenant.tenant_id, response.tokens_used)

        return build_response(
            {"content": response.content, "role": "assistant"},
            response.model,
            response.tokens_used,
            response.cost_usd,
            False,
            response.provider,
            response.fallback_used,
        )

    except Exception as e:
        logger.error("chat_completion_failed", error=str(e), tenant=tenant.tenant_id)
        record_error(type(e).__name__, body.model)
        latency = (time.perf_counter() - start) * 1000
        record_request(model=body.model, tier="error", status="error", cached=False, latency=latency/1000, tokens=0, cost=0)
        raise HTTPException(status_code=500, detail=f"Model inference failed: {str(e)}")


def build_response(content: dict, model: str, tokens: int, cost: float, cached: bool, tier: str, fallback_used: bool = False) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time() * 1000)}",
        created=int(time.time()),
        model=model,
        choices=[{
            "index": 0,
            "message": content,
            "finish_reason": "stop",
        }],
        usage={
            "prompt_tokens": tokens // 2,
            "completion_tokens": tokens // 2,
            "total_tokens": tokens,
        },
        cost_usd=round(cost, 6),
        cached=cached,
        tier=tier,
        fallback_used=fallback_used,
    )


def estimate_savings(model: str, tokens: int) -> float:
    gpt4o_cost = tokens * 5.0 / 1000
    model_costs = {
        "meta.llama3-1-8b-instruct-v1:0": 0.00016,
        "meta.llama3-8b-instruct-v1:0": 0.00016,
        "meta.llama3-1-70b-instruct-v1:0": 0.00072,
        "meta.llama4-scout-17b-instruct-v1:0": 0.00012,
        "gpt-4o-mini": 0.15 / 1000,
        "gpt-4o": 5.00 / 1000,
        "anthropic.claude-3-5-sonnet-20241022-v2:0": 0.003,
    }
    actual_cost = tokens * model_costs.get(model, 0.001) / 1000
    return max(0, gpt4o_cost - actual_cost)