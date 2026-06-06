from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import structlog

logger = structlog.get_logger()

REQUESTS_TOTAL = Counter(
    "llm_gateway_requests_total",
    "Total requests processed",
    ["model", "tier", "status", "cached"],
)

REQUEST_LATENCY = Histogram(
    "llm_gateway_request_latency_seconds",
    "Request latency in seconds",
    ["model", "tier"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

TOKENS_USED = Counter(
    "llm_gateway_tokens_total",
    "Total tokens used",
    ["model", "type"],
)

COST_USD = Counter(
    "llm_gateway_cost_usd_total",
    "Total cost in USD",
    ["model"],
)

COST_SAVED = Counter(
    "llm_gateway_cost_saved_usd_total",
    "Estimated cost saved vs GPT-4o baseline",
)

CACHE_HITS = Counter(
    "llm_gateway_cache_hits_total",
    "Cache hits",
    ["type"],
)

CACHE_MISSES = Counter(
    "llm_gateway_cache_misses_total",
    "Cache misses",
)

FALLBACKS = Counter(
    "llm_gateway_fallbacks_total",
    "Fallback activations",
    ["from_model", "to_model"],
)

ACTIVE_TENANTS = Gauge(
    "llm_gateway_active_tenants",
    "Number of active tenants",
)

QUOTA_USAGE = Gauge(
    "llm_gateway_quota_usage_percent",
    "Quota usage percentage",
    ["tenant_id", "quota_type"],
)

ERRORS = Counter(
    "llm_gateway_errors_total",
    "Total errors",
    ["type", "model"],
)


def record_request(model: str, tier: str, status: str, cached: bool, latency: float, tokens: int, cost: float, saved: float = 0):
    REQUESTS_TOTAL.labels(model=model, tier=tier, status=status, cached=str(cached).lower()).inc()
    REQUEST_LATENCY.labels(model=model, tier=tier).observe(latency)
    TOKENS_USED.labels(model=model, type="total").inc(tokens)
    COST_USD.labels(model=model).inc(cost)
    if saved > 0:
        COST_SAVED.inc(saved)


def record_cache_hit(cache_type: str):
    CACHE_HITS.labels(type=cache_type).inc()


def record_cache_miss():
    CACHE_MISSES.inc()


def record_fallback(from_model: str, to_model: str):
    FALLBACKS.labels(from_model=from_model, to_model=to_model).inc()


def record_error(error_type: str, model: str):
    ERRORS.labels(type=error_type, model=model).inc()


def setup_metrics(app):
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)