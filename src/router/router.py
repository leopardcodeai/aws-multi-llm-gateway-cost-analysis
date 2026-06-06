import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Optional
import boto3
from botocore.config import Config
from openai import AsyncOpenAI
import structlog

from src.config import get_settings
from src.classifier.classifier import classify_complexity

logger = structlog.get_logger()
settings = get_settings()

BEDROCK_CONFIG = Config(
    region_name=settings.classifier.region,
    retries={"max_attempts": 3, "mode": "adaptive"},
)

bedrock_runtime = boto3.client("bedrock-runtime", config=BEDROCK_CONFIG)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@dataclass
class ModelResponse:
    content: str
    model: str
    provider: str
    tokens_used: int
    latency_ms: int
    cost_usd: float
    confidence: float = 1.0
    fallback_used: bool = False


TIER_MODELS = {
    "simple": settings.router.tiers["simple"],
    "medium": settings.router.tiers["medium"],
    "complex": settings.router.tiers["complex"],
}

MODEL_COSTS = {
    "meta.llama3-1-8b-instruct-v1:0": 0.00016,
    "meta.llama3-8b-instruct-v1:0": 0.00016,
    "meta.llama3-1-70b-instruct-v1:0": 0.00072,
    "meta.llama4-scout-17b-instruct-v1:0": 0.00012,
    "gpt-4o-mini": 0.15 / 1000,
    "gpt-4o": 5.00 / 1000,
    "anthropic.claude-3-5-sonnet-20241022-v2:0": 0.003,
}


async def invoke_bedrock(
    model_id: str, messages: list, max_tokens: int, temperature: float
) -> ModelResponse:
    start = time.perf_counter()

    body = {
        "anthropic_version": "bedrock-2023-05-31"
        if "anthropic" in model_id
        else "meta-llama",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    if "meta.llama" in model_id:
        body = {
            "prompt": format_llama_prompt(messages),
            "max_gen_len": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }

    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        ),
    )

    result = json.loads(response["body"].read())
    latency_ms = int((time.perf_counter() - start) * 1000)

    if "anthropic" in model_id:
        content = result["content"][0]["text"]
        tokens = result["usage"]["input_tokens"] + result["usage"]["output_tokens"]
    else:
        content = result["generation"]
        tokens = result.get("usage", {}).get("total_tokens", estimate_tokens(content))

    cost = tokens * MODEL_COSTS.get(model_id, 0.001) / 1000

    return ModelResponse(
        content=content,
        model=model_id,
        provider="bedrock",
        tokens_used=tokens,
        latency_ms=latency_ms,
        cost_usd=cost,
    )


async def invoke_openai(
    model_id: str, messages: list, max_tokens: int, temperature: float
) -> ModelResponse:
    start = time.perf_counter()

    response = await openai_client.chat.completions.create(
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens
    cost = (
        response.usage.prompt_tokens * MODEL_COSTS.get(model_id, 0)
        + response.usage.completion_tokens * MODEL_COSTS.get(model_id, 0) * 4
    ) / 1000

    return ModelResponse(
        content=content,
        model=model_id,
        provider="openai",
        tokens_used=tokens,
        latency_ms=latency_ms,
        cost_usd=cost,
    )


def format_llama_prompt(messages: list) -> str:
    prompt = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            prompt += f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{content}<|eot_id|>"
        elif role == "user":
            prompt += f"<|start_header_id|>user<|end_header_id|>\n{content}<|eot_id|>"
        elif role == "assistant":
            prompt += (
                f"<|start_header_id|>assistant<|end_header_id|>\n{content}<|eot_id|>"
            )
    prompt += "<|start_header_id|>assistant<|end_header_id|>\n"
    return prompt


def estimate_tokens(text: str) -> int:
    return len(text) // 4


async def route_request(
    messages: list,
    model: str = "auto",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ModelResponse:
    if model != "auto":
        return await invoke_specific_model(model, messages, temperature, max_tokens)

    last_user_msg = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    classification = await classify_complexity(last_user_msg)

    tier = classification["tier"]
    confidence = classification["confidence"]

    tier_config = TIER_MODELS[tier]
    primary_model = tier_config.primary
    fallback_model = tier_config.fallback
    final_fallback = tier_config.final_fallback
    provider = tier_config.provider

    logger.info(
        "routing_decision",
        tier=tier,
        confidence=confidence,
        primary=primary_model,
        fallback=fallback_model,
    )

    try:
        if provider == "bedrock":
            response = await invoke_bedrock(
                primary_model, messages, tier_config.max_tokens, tier_config.temperature
            )
        else:
            response = await invoke_openai(
                primary_model, messages, tier_config.max_tokens, tier_config.temperature
            )

        response.confidence = confidence
        return response

    except Exception as e:
        logger.warning("primary_model_failed", model=primary_model, error=str(e))
        return await try_fallback(
            messages, fallback_model, final_fallback, tier_config, confidence, str(e)
        )


async def try_fallback(
    messages: list,
    fallback: str,
    final_fallback: Optional[str],
    tier_config,
    confidence: float,
    error: str,
) -> ModelResponse:
    for attempt, model_id in enumerate([fallback, final_fallback]):
        if not model_id:
            continue

        try:
            logger.info("trying_fallback", attempt=attempt + 1, model=model_id)
            provider = "openai" if model_id.startswith("gpt") else "bedrock"

            if provider == "bedrock":
                response = await invoke_bedrock(
                    model_id, messages, tier_config.max_tokens, tier_config.temperature
                )
            else:
                response = await invoke_openai(
                    model_id, messages, tier_config.max_tokens, tier_config.temperature
                )

            response.fallback_used = True
            response.confidence = confidence * 0.8
            return response

        except Exception as e:
            logger.warning("fallback_failed", model=model_id, error=str(e))
            continue

    raise Exception(f"All models failed. Last error: {error}")


async def invoke_specific_model(
    model: str, messages: list, temperature: float, max_tokens: int
) -> ModelResponse:
    if model.startswith("gpt"):
        return await invoke_openai(model, messages, max_tokens, temperature)
    return await invoke_bedrock(model, messages, max_tokens, temperature)
