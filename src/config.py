from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class GatewaySettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    timeout: int = 60
    max_request_size: int = 10485760
    debug: bool = False


class ClassifierSettings(BaseSettings):
    model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    region: str = "us-east-1"
    temperature: float = 0.0
    max_tokens: int = 10
    confidence_threshold: float = 0.7
    complexity_thresholds: dict = {
        "simple": 0.33,
        "medium": 0.66,
        "complex": 1.0,
    }


class RouterTierSettings(BaseSettings):
    primary: str
    fallback: str
    final_fallback: Optional[str] = None
    provider: str
    max_tokens: int
    temperature: float


class RouterSettings(BaseSettings):
    tiers: dict[str, RouterTierSettings]


class CacheRedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl: int = 86400
    key_prefix: str = "llmgw:cache:"


class CacheQdrantSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6333
    https: bool = False
    api_key: Optional[str] = None
    collection: str = "semantic_cache"
    vector_size: int = 384
    similarity_threshold: float = 0.92
    hnsw_ef: int = 128
    exact_match_boost: float = 1.0


class CacheSettings(BaseSettings):
    enabled: bool = True
    redis: CacheRedisSettings
    qdrant: CacheQdrantSettings


class AuthSettings(BaseSettings):
    enabled: bool = True
    api_key_prefix: str = "llmgw_"
    dynamodb_table: str = "llm-gateway-tenants"
    dynamodb_region: str = "us-east-1"
    default_quotas: dict = {
        "monthly_tokens": 100000,
        "daily_requests": 1000,
        "allowed_models": ["auto"],
    }
    rate_limit: dict = {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "burst": 10,
    }


class ObservabilitySettings(BaseSettings):
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    logging_level: str = "INFO"
    logging_format: str = "json"
    correlation_id_header: str = "X-Correlation-ID"
    dashboard_type: str = "streamlit"
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501
    tracing_enabled: bool = False
    tracing_sample_rate: float = 0.1


class ModelSettings(BaseSettings):
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"
    batch_size: int = 32


class FallbackSettings(BaseSettings):
    enabled: bool = True
    max_retries: int = 2
    retry_delay: float = 1.0
    timeout: float = 30.0
    low_confidence_threshold: float = 0.5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    classifier: ClassifierSettings = Field(default_factory=ClassifierSettings)
    router: RouterSettings = Field(default_factory=RouterSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    fallback: FallbackSettings = Field(default_factory=FallbackSettings)


@lru_cache
def get_settings() -> Settings:
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)
            return Settings(**yaml_config)
    return Settings()
