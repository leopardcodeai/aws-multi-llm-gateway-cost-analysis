# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-06

### Added
- **API Gateway (FastAPI)**: Core reverse proxy implementation mirroring the OpenAI chat completions API format.
- **Intelligent LLM-based Complexity Classifier**: Utilizes Claude 3.5 Haiku to analyze prompt complexity and return a classification score.
- **Dynamic Multi-LLM Router**: Automatically routes queries depending on complexity score (Simple -> Llama-3.1-8B, Medium -> Llama-3.1-70B, Complex -> GPT-4o).
- **Dual-Layer Caching**:
  - Redis exact-match cache (SHA-256 keys).
  - Qdrant semantic-match cache (using embeddings and cosine similarity threshold > 0.92).
- **Resilience Fallback Chains**: Automatic retry/failover logic that automatically routes requests to the next tier if a provider is offline or errors out.
- **Multi-Tenant Administration**: DynamoDB auth layer supporting secure `llmgw_` prefixed API keys, tenant-level allowed models configuration, and monthly token quotas.
- **Real-Time Observability**: Prometheus endpoint logging request durations, cost metrics, and cache hit rates, with a custom Streamlit analytics dashboard.
- **AWS Infrastructure (Terraform)**: Declarative configuration for ECS, DynamoDB, ElastiCache (Redis), Secrets Manager, and IAM permissions.
