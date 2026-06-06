# 🚀 LLM Gateway — Multi-LLM Routing & Cost-Optimization Gateway

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Bedrock](https://img.shields.io/badge/Bedrock-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-6B46C1?style=for-the-badge&logo=qdrant&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)

[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge)](CONTRIBUTING.md)

</div>

---

## 🎯 The Problem

> **Enterprises adopting LLMs face three critical challenges:**
>
> | Challenge | Impact |
> |-----------|--------|
> | 💸 **Uncontrolled Costs** | GPT-4o at $5/1M tokens → $50K+/month at scale |
> | 🔒 **Vendor Lock-in** | Single provider dependency, no fallback |
> | ⚡ **Latency Variance** | No routing optimization for task complexity |

## 💡 The Solution

**LLM Gateway** intelligently routes every prompt to the optimal model — reducing costs **40-60%** while maintaining quality.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BEFORE vs AFTER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  BEFORE: Every prompt → GPT-4o          AFTER: Smart routing                │
│  💰 $5.00 / 1M tokens                     💰 $0.12-$2.50 / 1M tokens       │
│  🔒 Single vendor                         🔄 Multi-provider + fallback      │
│  ⏱️ Fixed latency                         ⚡ Optimized per task            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

### System Overview

```mermaid
flowchart TB
    subgraph Client["🌐 Client Layer"]
        A[Multi-Tenant Clients] --> B[API Keys / JWT]
    end

    subgraph Gateway["🚪 API Gateway (FastAPI)"]
        C[Auth & Rate Limiting] --> D[Request Validation]
        D --> E{Cache Check}
    end

    subgraph Cache["⚡ Semantic Cache Layer"]
        E -->|Exact Match| F[(Redis\nSHA256 Key)]
        E -->|Semantic Match| G[(Qdrant\nVector Search)]
        F -->|Hit| H[Return Cached Response]
        G -->|Hit > 0.92| H
    end

    subgraph Classifier["🧠 Complexity Classifier"]
        E -->|Miss| I[Bedrock: Claude 3.5 Haiku]
        I --> J{Complexity Score}
        J -->|Simple: 0-0.33| K[Route: Llama 3.1 8B]
        J -->|Medium: 0.34-0.66| L[Route: Llama 3.1 70B / Llama 4 Scout]
        J -->|Complex: 0.67-1.0| M[Route: GPT-4o-mini → GPT-4o]
    end

    subgraph Models["🤖 Model Execution Layer"]
        K --> N[(Bedrock: Llama 3.1 8B\n~$0.00016/1K)]
        L --> O[(Bedrock: Llama 3.1 70B\n~$0.00072/1K)]
        L --> P[(Bedrock: Llama 4 Scout\n~$0.00012/1K)]
        M --> Q[(OpenAI: GPT-4o-mini\n~$0.15/1M in)]
        M --> R[(OpenAI: GPT-4o\n~$5.00/1M in)]
    end

    subgraph Fallback["🔄 Fallback Chain"]
        N -->|Fail/Low Conf| S[Next Tier]
        O -->|Fail/Low Conf| S
        P -->|Fail/Low Conf| S
        Q -->|Fail/Low Conf| R
        R -->|Fail| T[Claude 3.5 Sonnet\n(Final Fallback)]
    end

    subgraph Observability["📊 Observability"]
        C --> U[Prometheus Metrics]
        H --> U
        N --> U
        O --> U
        P --> U
        Q --> U
        R --> U
        T --> U
        U --> V[Grafana / Streamlit Dashboard]
        V --> W[Real-time: Cost Savings, Latency, Cache Hit Rate, Error Rate]
    end

    style Client fill:#e3f2fd,stroke:#1976d2
    style Gateway fill:#fff3e0,stroke:#f57c00
    style Cache fill:#e8f5e9,stroke:#388e3c
    style Classifier fill:#fce4ec,stroke:#c2185b
    style Models fill:#f3e5f5,stroke:#7b1fa2
    style Fallback fill:#fff8e1,stroke:#fbc02d
    style Observability fill:#e0f2f1,stroke:#00796b
```

### Visual Architecture Diagram

![Architecture Diagram](diagrams/architecture.excalidraw)

> **Open in [Excalidraw](https://excalidraw.com/#json=...) to edit/view interactively**

---

## ✨ Key Features

| Feature | Description | Tech |
|---------|-------------|------|
| 🧠 **LLM-Based Classification** | Claude 3.5 Haiku analyzes prompt complexity | AWS Bedrock |
| 🎯 **Tiered Routing** | Simple→Llama 8B, Medium→Llama 70B/Scout, Complex→GPT-4o | Custom Router |
| ⚡ **Dual-Layer Cache** | Redis (exact) + Qdrant (semantic, cosine >0.92) | Redis + Qdrant |
| 🔄 **Auto-Fallback** | Failure/low confidence → next tier automatically | Resilience Patterns |
| 👥 **Multi-Tenant** | API keys, per-tenant quotas, model allowlists | DynamoDB + FastAPI |
| 📊 **Real-Time Dashboard** | Cost savings, latency, cache hits, error rates | Streamlit / Grafana |
| 💰 **Cost Attribution** | Per-tenant, per-model, per-request tracking | Prometheus + DynamoDB |
| 🔐 **Zero-Secrets Code** | All credentials via AWS Secrets Manager / IAM | AWS Best Practices |

---

## 📊 Expected Results

| Metric | Target |
|--------|--------|
| **Cost Reduction** | 40-60% vs GPT-4o-only baseline |
| **Cache Hit Rate** | 25-40% (exact + semantic) |
| **P99 Latency Overhead** | <50ms |
| **Fallback Success Rate** | >99.9% |
| **Classification Accuracy** | >92% (validated on benchmark) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- AWS Account with Bedrock access (Claude Haiku, Llama models)
- OpenAI API Key
- Redis & Qdrant (local or managed)
- Docker (optional)

### Installation

```bash
# Clone the repo
git clone https://github.com/leopardcodeai/llm-gateway.git
cd llm-gateway

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

```yaml
# config.yaml
gateway:
  host: "0.0.0.0"
  port: 8000
  workers: 4

classifier:
  model: "anthropic.claude-3-5-haiku-20241022-v1:0"
  region: "us-east-1"
  confidence_threshold: 0.7

router:
  tiers:
    simple:
      primary: "meta.llama3-1-8b-instruct-v1:0"
      fallback: "meta.llama3-8b-instruct-v1:0"
    medium:
      primary: "meta.llama3-1-70b-instruct-v1:0"
      fallback: "meta.llama4-scout-17b-instruct-v1:0"
    complex:
      primary: "gpt-4o-mini"
      fallback: "gpt-4o"
      final_fallback: "anthropic.claude-3-5-sonnet-20241022-v2:0"

cache:
  redis:
    host: "localhost"
    port: 6379
    ttl: 86400
  qdrant:
    host: "localhost"
    port: 6333
    collection: "semantic_cache"
    similarity_threshold: 0.92

auth:
  dynamodb_table: "llm-gateway-tenants"
  default_quota: 100000  # tokens/month
```

### Run Locally

```bash
# Start dependencies
docker-compose up -d redis qdrant

# Run gateway
uvicorn src.gateway.main:app --reload --host 0.0.0.0 --port 8000

# Run dashboard (separate terminal)
streamlit run src/observability/dashboard.py
```

### Test the Gateway

```bash
# Simple classification task → Routes to Llama 8B (~$0.16/1M)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer llmgw_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Classify this sentiment: I love this product!"}],
    "temperature": 0
  }'

# Complex reasoning → Routes to GPT-4o
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer llmgw_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Design a distributed system for real-time analytics..."}],
    "temperature": 0.3
  }'
```

---

## 📁 Project Structure

```
llm-gateway/
├── src/
│   ├── gateway/          # FastAPI app, routes, middleware
│   ├── classifier/       # Complexity classification (Bedrock)
│   ├── router/           # Model routing logic + fallback
│   ├── cache/            # Redis + Qdrant cache layer
│   ├── auth/             # Multi-tenant auth, quotas
│   ├── observability/    # Metrics, dashboard, logging
│   └── models/           # Pydantic schemas, model configs
├── tests/                # Unit + integration tests
├── infra/                # Terraform for AWS resources
├── diagrams/             # Architecture diagrams (Excalidraw, Mermaid)
├── docs/                 # Documentation
├── docker-compose.yml    # Local dev stack
├── requirements.txt
├── config.yaml
└── .env.example
```

---

## 🏗️ Infrastructure (Terraform)

```hcl
# infra/main.tf - Key resources
resource "aws_bedrock_model_invocation_role" "gateway" {
  name = "llm-gateway-bedrock-role"
  # Permissions for Haiku, Llama models
}

resource "aws_dynamodb_table" "tenants" {
  name           = "llm-gateway-tenants"
  hash_key       = "tenant_id"
  billing_mode   = "PAY_PER_REQUEST"
  ttl { attribute_name = "expires_at", enabled = true }
}

resource "aws_secretsmanager_secret" "openai_key" {
  name = "llm-gateway/openai-api-key"
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "llm-gateway-cache"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_clusters   = 2
}
```

Deploy:
```bash
cd infra
terraform init
terraform plan
terraform apply
```

---

## 📈 Dashboard Preview

### Streamlit Dashboard (Real-Time)

```
┌────────────────────────────────────────────────────────────────┐
│  💰 COST SAVINGS: $2,847.32 / $5,000 baseline (43% reduction)  │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│  Cache Hit   │  Avg Latency │  Error Rate  │  Active Tenants  │
│    34.2%     │    245ms     │    0.02%     │       12         │
├──────────────┼──────────────┼──────────────┼──────────────────┤
│  Model Distribution (last 24h)                                    │
│  ████████████ Llama 8B (38%)     ████████ Llama 70B (22%)       │
│  ████████████ Llama 4 Scout (15%) ██████ GPT-4o-mini (18%)       │
│  ████ GPT-4o (7%)                                                   │
└────────────────────────────────────────────────────────────────┘
```

Launch: `streamlit run src/observability/dashboard.py`

---

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires AWS creds)
pytest tests/integration -v

# Load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

---

## 🔐 Security

- **Zero credentials in code** — All secrets via AWS Secrets Manager / IAM roles
- **API keys** — Prefixed (`llmgw_`), hashed in DynamoDB, rotatable
- **Rate limiting** — Per-tenant, per-model, configurable
- **Audit logging** — All requests/responses to S3 (encrypted)
- **Network** — VPC endpoints for Bedrock, no public internet for models

---

## 🤝 Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Commit changes: `git commit -m 'feat: add amazing feature'`
4. Push: `git push origin feat/amazing-feature`
5. Open a PR

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **AWS Bedrock** for managed Llama & Claude models
- **Qdrant** for vector search
- **FastAPI** for the async web framework
- **Excalidraw** for architecture diagrams

---

<div align="center">

**Built with ❤️ by AI Engineers for AI Engineers**

[⭐ Star this repo](https://github.com/leopardcodeai/llm-gateway) • [🐛 Report Bug](https://github.com/leopardcodeai/llm-gateway/issues) • [💡 Request Feature](https://github.com/leopardcodeai/llm-gateway/issues/new)

</div>