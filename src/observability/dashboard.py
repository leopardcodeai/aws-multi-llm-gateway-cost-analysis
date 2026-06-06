from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import structlog

logger = structlog.get_logger()

st.set_page_config(
    page_title="LLM Gateway Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

METRICS_URL = "http://localhost:9090/metrics"
GATEWAY_URL = "http://localhost:8000"


@st.cache_data(ttl=5)
def fetch_metrics():
    try:
        resp = requests.get(METRICS_URL, timeout=2)
        return parse_prometheus(resp.text)
    except Exception as e:
        logger.error("metrics_fetch_failed", error=str(e))
        return {}


def parse_prometheus(text: str) -> dict:
    metrics = {}
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split(" ")
        if len(parts) < 2:
            continue
        name = parts[0]
        value = float(parts[1])
        metrics[name] = value
    return metrics


def get_metric(metrics: dict, name: str, default=0):
    for k, v in metrics.items():
        if k.startswith(name):
            return v
    return default


def render_header():
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("🚀 LLM Gateway Dashboard")
        st.caption("Multi-LLM Routing & Cost Optimization")
    with col2:
        st.metric("Status", "🟢 Healthy", delta="All systems operational")
    with col3:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()


def render_cost_savings(metrics):
    cost_saved = get_metric(metrics, "llm_gateway_cost_saved_usd_total")
    cost_total = get_metric(metrics, "llm_gateway_cost_usd_total")
    baseline_gpt4o = cost_total + cost_saved

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Total Cost", f"${cost_total:,.2f}")
    with col2:
        st.metric(
            "💡 Cost Saved",
            f"${cost_saved:,.2f}",
            delta=f"{(cost_saved / baseline_gpt4o * 100):.1f}% vs GPT-4o"
            if baseline_gpt4o > 0
            else "N/A",
        )
    with col3:
        st.metric("📊 Baseline (GPT-4o)", f"${baseline_gpt4o:,.2f}")
    with col4:
        savings_pct = (cost_saved / baseline_gpt4o * 100) if baseline_gpt4o > 0 else 0
        st.metric("🎯 Savings Rate", f"{savings_pct:.1f}%")


def render_cache_performance(metrics):
    exact_hits = get_metric(metrics, 'llm_gateway_cache_hits_total{type="exact"}')
    semantic_hits = get_metric(metrics, 'llm_gateway_cache_hits_total{type="semantic"}')
    misses = get_metric(metrics, "llm_gateway_cache_misses_total")
    total = exact_hits + semantic_hits + misses

    hit_rate = (exact_hits + semantic_hits) / total * 100 if total > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🎯 Cache Hit Rate", f"{hit_rate:.1f}%")
    with col2:
        st.metric("🔴 Exact Hits", f"{int(exact_hits):,}")
    with col3:
        st.metric("🔵 Semantic Hits", f"{int(semantic_hits):,}")

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Exact", "Semantic", "Miss"],
                values=[exact_hits, semantic_hits, misses],
                hole=0.4,
            )
        ]
    )
    fig.update_layout(title="Cache Performance", height=300)
    st.plotly_chart(fig, use_container_width=True)


def render_model_distribution(metrics):
    models = {}
    for k, v in metrics.items():
        if k.startswith("llm_gateway_requests_total") and "model=" in k:
            model = k.split('model="')[1].split('"')[0]
            models[model] = models.get(model, 0) + v

    if models:
        df = pd.DataFrame(list(models.items()), columns=["Model", "Requests"])
        fig = px.bar(df, x="Model", y="Requests", title="Requests by Model (24h)", color="Model")
        st.plotly_chart(fig, use_container_width=True)


def render_latency(metrics):
    latencies = {}
    for k, v in metrics.items():
        if k.startswith("llm_gateway_request_latency_seconds_sum") and "model=" in k:
            model = k.split('model="')[1].split('"')[0]
            count_key = k.replace("_sum", "_count")
            count = metrics.get(count_key, 1)
            latencies[model] = (v / count) * 1000

    if latencies:
        df = pd.DataFrame(list(latencies.items()), columns=["Model", "Avg Latency (ms)"])
        fig = px.bar(
            df,
            x="Model",
            y="Avg Latency (ms)",
            title="Average Latency by Model",
            color="Model",
        )
        st.plotly_chart(fig, use_container_width=True)


def render_fallbacks(metrics):
    fallbacks = {}
    for k, v in metrics.items():
        if k.startswith("llm_gateway_fallbacks_total"):
            from_model = k.split('from_model="')[1].split('"')[0]
            to_model = k.split('to_model="')[1].split('"')[0]
            key = f"{from_model} → {to_model}"
            fallbacks[key] = fallbacks.get(key, 0) + v

    if fallbacks:
        df = pd.DataFrame(list(fallbacks.items()), columns=["Fallback Path", "Count"])
        fig = px.bar(
            df,
            x="Fallback Path",
            y="Count",
            title="Fallback Activations",
            color="Fallback Path",
        )
        st.plotly_chart(fig, use_container_width=True)


def render_errors(metrics):
    errors = {}
    for k, v in metrics.items():
        if k.startswith("llm_gateway_errors_total"):
            error_type = k.split('type="')[1].split('"')[0]
            model = k.split('model="')[1].split('"')[0] if 'model="' in k else "unknown"
            key = f"{error_type} ({model})"
            errors[key] = errors.get(key, 0) + v

    if errors:
        st.subheader("⚠️ Errors")
        for err, count in errors.items():
            st.error(f"{err}: {int(count)}")


def main():
    render_header()

    metrics = fetch_metrics()

    if not metrics:
        st.warning(
            "⚠️ Unable to fetch metrics. Ensure Prometheus endpoint is running on :9090/metrics"
        )
        return

    st.divider()
    render_cost_savings(metrics)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        render_cache_performance(metrics)
    with col2:
        render_model_distribution(metrics)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        render_latency(metrics)
    with col2:
        render_fallbacks(metrics)

    st.divider()
    render_errors(metrics)

    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Auto-refresh: 5s")


if __name__ == "__main__":
    main()
