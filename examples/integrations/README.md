# cascadeflow Integrations

This directory contains production-ready integration examples for cascadeflow with third-party services and tools.

## 📋 Table of Contents

- [LiteLLM Integration](#-litellm-integration) - Access 10+ providers with automatic cost tracking
- [Paygentic Integration](#-paygentic-integration) - Usage event reporting and billing lifecycle helpers
- [Local Providers](#-local-providers-setup) - Ollama and vLLM configuration examples
- [OpenTelemetry & Grafana](#-opentelemetry--grafana) - Production observability and metrics
- [Provider Testing](#-provider-testing) - Validate API keys and provider configuration

---

## 🚀 LiteLLM Integration

**Files:** [`litellm_providers.py`](litellm_providers.py) | [`litellm_cost_tracking.py`](litellm_cost_tracking.py)

Access 10+ AI providers with automatic cost tracking and accurate pricing from LiteLLM's database.

### Quick Start

```bash
# Install dependencies
pip install cascadeflow[all]

# Run the comprehensive demo (no API keys required for cost info)
python examples/integrations/litellm_providers.py

# Or run the cost tracking demo
python examples/integrations/litellm_cost_tracking.py
```

### Supported Providers

| Provider | Value Proposition | Cost Savings vs GPT-4o |
|----------|-------------------|------------------------|
| **OpenAI** | Industry standard, most reliable | Baseline |
| **Anthropic** | Best reasoning, strong safety | Similar cost |
| **DeepSeek** | Code specialization | **95%** cheaper |
| **Google Gemini** | Ultra-cheap, fast | **98%** cheaper |
| **Groq** | Ultra-fast inference | 90% cheaper |
| **Together AI** | Open models, cost-effective | 85% cheaper |
| **Hugging Face** | Community models, flexible | Varies |
| **Azure OpenAI** | Enterprise compliance | Same as OpenAI |
| **Ollama** | Local, private | **100%** (free) |
| **vLLM** | Self-hosted, high throughput | **100%** (free) |

### Usage Example

```python
from cascadeflow.integrations.litellm import calculate_cost, get_provider_info
from cascadeflow import CascadeAgent, ModelConfig

# Get provider information
info = get_provider_info("deepseek")
print(f"Value: {info.value_prop}")
# Output: "Specialized code models, very cost-effective for coding tasks"

# Calculate costs (use provider prefix for accurate pricing)
deepseek_cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=500
)
print(f"DeepSeek cost: ${deepseek_cost:.6f}")
# Output: DeepSeek cost: $0.000280

gpt4_cost = calculate_cost(
    model="gpt-4o",
    input_tokens=1000,
    output_tokens=500
)
print(f"GPT-4o cost: ${gpt4_cost:.6f}")
# Output: GPT-4o cost: $0.007500

savings = ((gpt4_cost - deepseek_cost) / gpt4_cost) * 100
print(f"Savings: {savings:.1f}%")
# Output: Savings: 96.3%
```

### Integration with CascadeAgent

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import calculate_cost

# Create cascade with DeepSeek (95% cheaper than GPT-4o for code!)
agent = CascadeAgent(models=[
    ModelConfig(
        name="deepseek-coder",
        provider="openai",  # DeepSeek uses OpenAI-compatible API
        cost=calculate_cost("deepseek/deepseek-coder", 1000, 1000) * 1000,
        base_url="https://api.deepseek.com/v1"
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
    )
])

result = await agent.run("Write a Python function to merge sorted lists")
print(f"Cost: ${result.total_cost:.6f}")
```

### API Keys (Optional)

The examples work without API keys for cost information. To test actual API calls:

```bash
# DeepSeek (95% cheaper for code)
export DEEPSEEK_API_KEY="sk-..."

# Google/Vertex AI (98% cheaper for simple tasks)
export GOOGLE_API_KEY="..."

# Azure OpenAI (enterprise compliance)
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://your-resource.openai.azure.com"

# Groq (ultra-fast, free tier available)
export GROQ_API_KEY="..."

# Together AI (cost-effective open models)
export TOGETHER_API_KEY="..."

# Hugging Face (community models)
export HF_TOKEN="..."
```

### Cost Savings Examples

**Annual Impact for 1M tokens/month:**
- GPT-4o only: $30,000/year
- With DeepSeek/Gemini cascade: $1,500-$9,000/year
- **Savings: $21,000-$28,500/year (70-95%)**

---

## 💳 Paygentic Integration

**File:** [`paygentic_usage.py`](paygentic_usage.py)

Opt-in example for reporting cascade usage to Paygentic.

### Quick Start

```bash
export PAYGENTIC_API_KEY="..."
export PAYGENTIC_MERCHANT_ID="..."
export PAYGENTIC_BILLABLE_METRIC_ID="..."

python examples/integrations/paygentic_usage.py
```

### What It Shows

- Explicit `PaygenticClient` setup (no default auto-enable)
- Usage event reporting based on proxy-style token/cost output
- Safe integration behavior: billing instrumentation remains decoupled from core request execution
- Python proxy wrapper supports `delivery_mode="background"` (default), `sync`, or `durable_outbox`

---

## 🏠 Local Providers Setup

**File:** [`local_providers_setup.py`](local_providers_setup.py)

Complete guide for setting up Ollama and vLLM in various deployment scenarios.

### Quick Start - Local Ollama

```bash
# 1. Install Ollama
# Download from: https://ollama.ai/download

# 2. Start Ollama (auto-starts on macOS/Windows)
ollama serve

# 3. Pull a model
ollama pull llama3.2

# 4. Run the example
python examples/integrations/local_providers_setup.py
```

### Scenarios Covered

1. **Local Installation** (localhost:11434) - Default setup
2. **Network Deployment** - Ollama on another machine
3. **Remote Server** - With authentication
4. **vLLM Setup** - Self-hosted inference server

### Usage with CascadeAgent

```python
from cascadeflow import CascadeAgent, ModelConfig

# Local Ollama (100% free, full privacy)
agent = CascadeAgent(models=[
    ModelConfig(
        name="llama3.2",
        provider="ollama",
        cost=0.0,  # Free!
        base_url="http://localhost:11434"  # Optional, this is default
    ),
    ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.000375
    )
])

result = await agent.run("What is Python?")
```

---

## 📊 OpenTelemetry & Grafana

**File:** [`opentelemetry_grafana.py`](opentelemetry_grafana.py)

Production-grade observability with OpenTelemetry, Prometheus, and Grafana.

### Quick Start

```bash
# 1. Install dependencies
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# 2. Start observability stack
cd examples/integrations
docker-compose up -d

# 3. Run example
python opentelemetry_grafana.py

# 4. View metrics in Grafana
# Open http://localhost:3000 (admin/admin)
```

### Docker Stack Includes

- **OpenTelemetry Collector** - `localhost:4318` (OTLP HTTP)
- **Prometheus** - `localhost:9090` (metrics storage)
- **Grafana** - `localhost:3000` (visualization)

### Metrics Exported

**Cost Metrics:**
- `cascadeflow.cost.total` - Total cost in USD
- Dimensions: `user.id`, `user.tier`, `model.name`, `provider.name`

**Token Metrics:**
- `cascadeflow.tokens.input` - Input tokens consumed
- `cascadeflow.tokens.output` - Output tokens generated

**Latency Metrics:**
- `cascadeflow.latency` - Request latency histogram

### Example Grafana Queries

```promql
# Cost by User Tier
sum by (user_tier) (rate(cascadeflow_cost_total[5m]))

# Tokens by Model
sum by (model_name) (rate(cascadeflow_tokens_input[5m]))
+ sum by (model_name) (rate(cascadeflow_tokens_output[5m]))

# P95 Latency by Provider
histogram_quantile(0.95,
  sum by (provider_name, le) (rate(cascadeflow_latency_bucket[5m]))
)

# Top 10 Users by Cost
topk(10, sum by (user_id) (rate(cascadeflow_cost_total[5m])))
```

### Integration Code

```python
from cascadeflow.integrations.otel import (
    OpenTelemetryExporter,
    cascadeflowMetrics,
    MetricDimensions
)

# Initialize exporter
exporter = OpenTelemetryExporter(
    endpoint="http://localhost:4318",
    service_name="my-app",
    environment="production"
)

# Record metrics after each query
metrics = cascadeflowMetrics(
    cost=response.cost,
    tokens_input=response.metadata["prompt_tokens"],
    tokens_output=response.metadata["completion_tokens"],
    latency_ms=response.latency_ms,
    dimensions=MetricDimensions(
        user_id=user.id,
        user_tier=user.tier,
        model=response.model,
        provider=response.provider
    )
)

exporter.record(metrics)
```

### Production Deployment

**Environment Variables:**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="cascadeflow-prod"
export ENVIRONMENT="production"
export OTEL_ENABLED="true"
```

**Supported Platforms:**
- AWS CloudWatch
- Datadog
- Grafana Cloud
- New Relic
- Any OpenTelemetry-compatible service

---

## 🧪 Provider Testing

**File:** [`test_all_providers.py`](test_all_providers.py)

Comprehensive test suite to validate API keys and provider configuration.

### Quick Start

```bash
# Run the test suite
python examples/integrations/test_all_providers.py
```

### What It Tests

1. **LiteLLM Installation** - Checks if LiteLLM is available
2. **API Key Status** - Shows which providers are configured
3. **Provider Validation** - Tests provider availability
4. **Cost Calculations** - Verifies cost calculation for each provider
5. **Configuration Template** - Generates .env template

### Example Output

```
================================================================================
API Key Status Check
================================================================================

✓ CONFIGURED PROVIDERS (7):

  ✓ OpenAI                    (OPENAI_API_KEY)
  ✓ Anthropic Claude          (ANTHROPIC_API_KEY)
  ✓ Groq                      (GROQ_API_KEY)
  ✓ DeepSeek                  (DEEPSEEK_API_KEY)
  ...

✗ MISSING API KEYS (3):

  ✗ Azure OpenAI              (needs AZURE_API_KEY)
  ✗ Google (Vertex AI)        (needs GOOGLE_API_KEY)
  ...

================================================================================
Cost Calculation Tests
================================================================================

  ✓ OpenAI          | gpt-4                          | $0.006000
  ✓ DeepSeek        | deepseek/deepseek-coder        | $0.000028
  ✓ Google          | gemini/gemini-pro              | $0.000087
  ...
```

---

## 📁 Files Overview

| File | Purpose | API Keys Required |
|------|---------|-------------------|
| `litellm_providers.py` | Comprehensive LiteLLM demo with 8 examples | No (for cost info) |
| `litellm_cost_tracking.py` | Cost tracking and provider validation | No (for cost info) |
| `paygentic_usage.py` | Usage event reporting to Paygentic (opt-in, fail-open) | Yes |
| `local_providers_setup.py` | Ollama and vLLM setup guide | No |
| `opentelemetry_grafana.py` | Production observability example | No |
| `test_all_providers.py` | API key validation and testing | Optional |
| `docker-compose.yml` | OpenTelemetry + Prometheus + Grafana stack | No |
| `otel-collector-config.yaml` | OpenTelemetry Collector configuration | No |
| `prometheus.yml` | Prometheus scrape configuration | No |
| `grafana-datasource.yml` | Grafana datasource configuration | No |

---

## 🎯 Use Cases

### 1. Cost Optimization
**Goal:** Reduce AI costs by 70-95%

**Solution:** Use LiteLLM integration to access cheaper providers
- Run `litellm_providers.py` to see cost comparisons
- Integrate DeepSeek for code ($0.00028 vs $0.0075 for GPT-4o)
- Integrate Gemini Flash for simple queries ($0.000225 vs $0.0075)

### 2. Privacy & Compliance
**Goal:** Keep data on-premises

**Solution:** Use local providers
- Run `local_providers_setup.py` for Ollama setup
- 100% free, zero network requests
- Full control over data

### 3. Production Monitoring
**Goal:** Track costs, latency, and usage in production

**Solution:** OpenTelemetry + Grafana
- Run `docker-compose up -d` to start stack
- Integrate `opentelemetry_grafana.py` code
- Monitor metrics in real-time

### 4. Provider Testing
**Goal:** Validate API keys before deployment

**Solution:** Run provider tests
- Run `test_all_providers.py`
- See which providers are configured
- Get cost estimates without API calls

---

## 🔧 Troubleshooting

### "Import error: No module named litellm"
```bash
pip install litellm
# Or
pip install cascadeflow[all]
```

### "OpenTelemetry not installed"
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

### "Metrics not appearing in Grafana"
1. Check OpenTelemetry Collector logs: `docker-compose logs otel-collector`
2. Verify metrics: `curl http://localhost:8889/metrics`
3. Check Prometheus targets: http://localhost:9090 → Status → Targets

### "Provider prefix for accurate pricing"
Always use provider prefixes for LiteLLM:
- ✅ `deepseek/deepseek-coder` (not `deepseek-coder`)
- ✅ `anthropic/claude-3-5-sonnet-20241022` (not `claude-3-5-sonnet`)
- ✅ `gemini/gemini-1.5-flash` (not `gemini-1.5-flash`)

---

## 📚 Related Documentation

- **Provider Guide:** [docs/guides/providers.md](../../docs/guides/providers.md)
- **Cost Tracking:** [docs/guides/cost_tracking.md](../../docs/guides/cost_tracking.md)
- **Paygentic Guide:** [docs/guides/paygentic_integration.md](../../docs/guides/paygentic_integration.md)
- **Production Guide:** [docs/guides/production.md](../../docs/guides/production.md)

---

## 🚀 Next Steps

1. **Try LiteLLM:** `python examples/integrations/litellm_providers.py`
2. **Try Paygentic usage reporting:** `python examples/integrations/paygentic_usage.py`
3. **Setup local providers:** `python examples/integrations/local_providers_setup.py`
4. **Test your API keys:** `python examples/integrations/test_all_providers.py`
5. **Add monitoring:** Follow OpenTelemetry section above

---

**💰 Start saving on AI costs today!** 🚀
