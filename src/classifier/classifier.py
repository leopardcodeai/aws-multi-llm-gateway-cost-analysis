import json

import boto3
import structlog
from botocore.config import Config

from src.config import get_settings

logger = structlog.get_logger()


def _get_classifier_settings():
    return get_settings().classifier


def _get_bedrock_config():
    classifier_settings = _get_classifier_settings()
    return Config(
        region_name=classifier_settings.region,
        retries={"max_attempts": 3, "mode": "adaptive"},
    )


BEDROCK_CONFIG = _get_bedrock_config()
bedrock_runtime = boto3.client("bedrock-runtime", config=BEDROCK_CONFIG)

CLASSIFIER_PROMPT = """Analyze the complexity of the following user prompt and classify it as SIMPLE, MEDIUM, or COMPLEX.

Classification criteria:
- SIMPLE: Factual lookup, classification, formatting, simple extraction, translation, basic Q&A
- MEDIUM: Multi-step reasoning, code generation, summarization, analysis, creative writing
- COMPLEX: Complex reasoning, architecture design, mathematical proofs, multi-agent coordination, novel problem solving

Return ONLY a JSON object with:
- "classification": "SIMPLE" | "MEDIUM" | "COMPLEX"
- "confidence": float between 0.0 and 1.0
- "reasoning": brief explanation

Prompt: {prompt}"""


async def classify_complexity(prompt: str) -> dict:
    try:
        classifier_settings = _get_classifier_settings()
        formatted_prompt = CLASSIFIER_PROMPT.format(prompt=prompt[:8000])

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": classifier_settings.max_tokens,
            "temperature": classifier_settings.temperature,
            "messages": [{"role": "user", "content": formatted_prompt}],
        }

        response = bedrock_runtime.invoke_model(
            modelId=classifier_settings.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        parsed = json.loads(content)
        classification = parsed["classification"].upper()
        confidence = float(parsed["confidence"])

        if classification not in ("SIMPLE", "MEDIUM", "COMPLEX"):
            raise ValueError(f"Invalid classification: {classification}")

        return {
            "tier": classification.lower(),
            "confidence": confidence,
            "reasoning": parsed.get("reasoning", ""),
        }

    except Exception as e:
        logger.error("classification_failed", error=str(e), prompt=prompt[:100])
        return {
            "tier": "medium",
            "confidence": 0.5,
            "reasoning": f"Fallback due to error: {str(e)}",
        }


def get_tier_for_score(score: float) -> str:
    thresholds = _get_classifier_settings().complexity_thresholds
    if score <= thresholds["simple"]:
        return "simple"
    elif score <= thresholds["medium"]:
        return "medium"
    return "complex"
