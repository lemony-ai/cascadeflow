# Provider Comparison Guide

Complete guide to AI providers supported by cascadeflow and how to mix them effectively.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Supported Providers](#supported-providers)
3. [Provider Comparison](#provider-comparison)
4. [Mixing Providers](#mixing-providers)
5. [Cost Analysis](#cost-analysis)
6. [Setup Guide](#setup-guide)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

cascadeflow supports 7 AI providers, each with unique strengths. You can mix any combination of providers in a single cascade for optimal cost, speed, and quality.

### Why Mix Providers?

1. **Cost Optimization** - Start with free/cheap providers
2. **Quality Specialization** - Use best provider for each task
3. **High Availability** - Fallback if provider is down
4. **Speed Optimization** - Fast drafts, accurate verification
5. **Compliance** - Some providers better for regulated industries

---

## Supported Providers

### 1. OpenAI

**Models**: GPT-4o, GPT-4o-mini, GPT-4 Turbo

**Strengths:**
- ✅ Best overall quality
- ✅ Excellent tool/function calling
- ✅ Wide model selection
- ✅ Best for technical tasks
- ✅ 128K token context (GPT-4o)

**Weaknesses:**
- ❌ Most expensive ($0.00625/request for GPT-4o)
- ❌ Rate limits can be strict
- ❌ Slower than Groq

**Best For**: Code generation, technical Q&A, tool calling, general intelligence

**Setup:**
```bash
export OPENAI_API_KEY="sk-..."
```

```python
from cascadeflow import ModelConfig

model = ModelConfig(
    name="gpt-4o",
    provider="openai",
    cost=0.00625,  # Actual cost per 1M tokens
)
```

---

### 2. Anthropic (Claude)

**Models**: Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4.1

**Strengths:**
- ✅ Excellent reasoning ability
- ✅ Best for long context (200K tokens)
- ✅ Strong at analysis and writing
- ✅ Good for complex workflows
- ✅ More affordable than GPT-4o

**Weaknesses:**
- ❌ Mid-high cost ($0.003/request)
- ❌ Fewer model options
- ❌ Slower than Groq

**Best For**: Long document analysis, complex reasoning, writing tasks, research

**Setup:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
model = ModelConfig(
    name="claude-sonnet-4-5-20250929",
    provider="anthropic",
    cost=0.003,
)
```

---

### 3. Groq

**Models**: Llama 3.1 (8B, 70B), Llama 3.3 70B, Mixtral, DeepSeek, Qwen

**Strengths:**
- ✅ **Extremely fast** (8x faster than others)
- ✅ **FREE tier** available
- ✅ Good for simple queries
- ✅ Low latency (200-300ms)
- ✅ Multiple model options

**Weaknesses:**
- ❌ Limited context (8K tokens)
- ❌ Lower quality on complex tasks
- ❌ No logprobs support

**Best For**: Simple queries, high-volume applications, fast responses, cost-sensitive workloads

**Setup:**
```bash
export GROQ_API_KEY="gsk_..."
```

```python
model = ModelConfig(
    name="llama-3.1-8b-instant",
    provider="groq",
    cost=0.0,  # FREE!
)
```

---

### 4. Ollama (Local)

**Models**: Llama 3.2, Llama 3.1, Mistral, Phi, Qwen, etc.

**Strengths:**
- ✅ **FREE** (self-hosted)
- ✅ Privacy (data never leaves your machine)
- ✅ Works offline
- ✅ No rate limits
- ✅ Runs on consumer hardware

**Weaknesses:**
- ❌ Requires local setup
- ❌ Lower quality than cloud models
- ❌ Slower on CPU
- ❌ Limited context

**Best For**: Privacy-sensitive data, offline applications, development/testing, edge devices

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2

# Start server
ollama serve
```

```python
model = ModelConfig(
    name="llama3.2:1b",
    provider="ollama",
    cost=0.0,  # FREE (self-hosted)
)
```

**Auto-Discovery:**
```python
# List all installed models dynamically
from cascadeflow.providers.ollama import OllamaProvider

provider = OllamaProvider()
models = await provider.list_models()
# Returns: ['llama3.2:1b', 'mistral:7b', 'codellama:latest', ...]

# Use discovered models in cascade
for model_name in models:
    agent.models.append(ModelConfig(
        name=model_name,
        provider="ollama",
        cost=0.0
    ))
```

---

### 5. vLLM (Self-Hosted)

**Models**: Any HuggingFace model (Llama, Mistral, Qwen, etc.)

**Strengths:**
- ✅ Self-hosted (full control)
- ✅ Very cost-effective at scale
- ✅ High throughput
- ✅ Flexible model selection

**Weaknesses:**
- ❌ Requires infrastructure setup
- ❌ Needs GPU for good performance
- ❌ Maintenance overhead

**Best For**: High-volume production, cost optimization at scale, custom models

**Setup:**
```bash
# Start vLLM server
vllm serve meta-llama/Llama-3.2-3B-Instruct --port 8000
```

```python
model = ModelConfig(
    name="meta-llama/Llama-3.2-3B-Instruct",
    provider="vllm",
    cost=0.0001,  # Infrastructure costs
)
```

**Auto-Discovery:**
```python
# List all models served by vLLM
from cascadeflow.providers.vllm import VLLMProvider

provider = VLLMProvider(base_url="http://localhost:8000/v1")
models = await provider.list_models()
# Returns: ['meta-llama/Llama-3.2-3B-Instruct', ...]

# Dynamically configure cascade from available models
for model_name in models:
    agent.models.append(ModelConfig(
        name=model_name,
        provider="vllm",
        cost=0.0001
    ))
```

---

### 6. HuggingFace

**Models**: 100,000+ open-source models

**Strengths:**
- ✅ Massive model selection
- ✅ Free tier available
- ✅ Easy to try new models
- ✅ Community support

**Weaknesses:**
- ❌ Variable quality
- ❌ Slower inference
- ❌ Rate limits on free tier

**Best For**: Experimentation, specialized models, research

---

### 7. Together AI

**Models**: Llama 3.1, Mixtral, DeepSeek, Qwen, etc.

**Strengths:**
- ✅ Good performance
- ✅ Competitive pricing
- ✅ Multiple model options
- ✅ Fast inference

**Weaknesses:**
- ❌ Less known than others
- ❌ Smaller ecosystem

**Best For**: Cost-effective cloud inference, alternative to Groq

---

## Provider Comparison

### By Speed (Latency)

| Rank | Provider | Typical Latency | Notes |
|------|----------|----------------|-------|
| 1 | Groq | 200-300ms | 8x faster than others |
| 2 | Together | 400-600ms | Good speed |
| 3 | OpenAI | 600-1500ms | Varies by model |
| 4 | Anthropic | 800-1200ms | Consistent |
| 5 | HuggingFace | 1000-3000ms | Variable |
| 6 | Ollama | 500-5000ms | Depends on hardware |
| 7 | vLLM | 300-2000ms | Depends on setup |

### By Cost (Per Request)

| Rank | Provider | Typical Cost | Notes |
|------|----------|-------------|-------|
| 1 | Groq | $0.00 | FREE tier |
| 2 | Ollama | $0.00 | Self-hosted |
| 3 | vLLM | $0.0001 | Infrastructure costs |
| 4 | Together | $0.0002-0.001 | Competitive |
| 5 | OpenAI Mini | $0.00015 | GPT-4o-mini |
| 6 | HuggingFace | $0.0005 | Free tier available |
| 7 | Anthropic | $0.001-0.003 | Claude models |
| 8 | OpenAI | $0.00625 | GPT-4o premium |

### By Quality

| Rank | Provider | Quality Score | Best For |
|------|----------|--------------|----------|
| 1 | OpenAI GPT-4o | 0.95 | Complex tasks |
| 2 | Anthropic Claude Sonnet 4.5 | 0.92 | Reasoning |
| 3 | OpenAI GPT-4o-mini | 0.88 | General tasks |
| 4 | Groq Llama 3.3 70B | 0.85 | Simple tasks |
| 5 | Together | 0.82 | Basic queries |
| 6 | Groq Llama 3.1 8B | 0.78 | Very simple |
| 7 | Ollama | 0.70-0.80 | Development |

### By Context Length

| Provider | Model | Max Context | Best For |
|----------|-------|-------------|----------|
| Anthropic | Claude 3.5 | 200K tokens | Long documents |
| OpenAI | GPT-4o | 128K tokens | Large context |
| Groq | Llama 3.3 | 32K tokens | Medium context |
| Groq | Llama 3.1 | 8K tokens | Short context |
| Ollama | Varies | 2K-32K tokens | Local processing |

---

## Mixing Providers

### Pattern 1: Free-First Cascade

**Goal**: Maximum cost savings

```python
agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0),
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
])
```

**When**: High-volume applications (50K+ requests/month)  
**Savings**: 70-98% vs all-premium

---

### Pattern 2: Cross-Provider Drafter/Verifier

**Goal**: Quality assurance with cost savings

```python
agent = CascadeAgent(models=[
    # Fast drafter (Groq)
    ModelConfig("llama-3.1-70b-versatile", provider="groq", cost=0),
    
    # Premium verifier (Claude or GPT)
    ModelConfig("claude-sonnet-4-5-20250929", provider="anthropic", cost=0.003),
])
```

**When**: Quality-critical applications  
**Savings**: 60-80% vs all-premium

---

### Pattern 3: Specialization

**Goal**: Optimize quality for each task type

```python
# Technical tasks → OpenAI
# Writing tasks → Anthropic
# Simple tasks → Groq

agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b", provider="groq", cost=0),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
    ModelConfig("claude-sonnet-4-5-20250929", provider="anthropic", cost=0.003),
])
```

**When**: Diverse workload mix  
**Savings**: 40-70% vs all-premium

---

### Pattern 4: Reliability

**Goal**: High availability with redundancy

```python
# Multiple providers at same tier
agent = CascadeAgent(models=[
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("claude-3-5-haiku", provider="anthropic", cost=0.001),
    ModelConfig("llama-3.1-70b", provider="groq", cost=0),
])
```

**When**: Production systems with SLA requirements  
**Benefit**: Automatic fallback if provider down

---

## Cost Analysis

### Monthly Cost Comparison (100K requests)

| Strategy | Configuration | Monthly Cost | Savings |
|----------|--------------|--------------|---------|
| All Premium | GPT-4o only | $625 | 0% (baseline) |
| Single Provider | GPT-4o-mini only | $15 | 98% |
| Free-First | Groq→Mini→GPT-4o | $32 | 95% |
| Cross-Provider | Groq→Claude | $45 | 93% |
| Specialization | Mixed routing | $85 | 86% |
| All Free | Groq→Ollama | $0 | 100% |

### Real-World Distribution (Free-First Pattern)

Assuming: 100K total requests

```
Simple queries (50%):  50K × $0 (Groq) = $0
Moderate (30%):        30K × $0.00015 (GPT-4o-mini) = $4.50
Complex (15%):         15K × $0.00625 (GPT-4o) = $93.75
Very complex (5%):     5K × $0.00625 (GPT-4o) = $31.25

Total: $129.50/month (79% savings vs all-GPT-4o)
```

---

## Setup Guide

### Quick Setup

```bash
# 1. Install cascadeflow
pip install cascadeflow[all]

# 2. Set API keys (all optional)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."

# 3. Create agent
python examples/multi_provider.py
```

### Minimal Setup (1 Provider)

```python
# Works with just OpenAI
agent = CascadeAgent(models=[
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
])
```

### Recommended Setup (2 Providers)

```python
# Groq + OpenAI (best value)
agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
])
```

### Advanced Setup (3+ Providers)

```python
# Maximum flexibility
agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b", provider="groq", cost=0),
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("claude-3-5-sonnet", provider="anthropic", cost=0.003),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
])
```

---

## Best Practices

### 1. Start with Free Providers

```python
# Always try free first
models = []
if os.getenv("GROQ_API_KEY"):
    models.append(ModelConfig("llama-3.1-8b", provider="groq", cost=0))

# Then add paid
if os.getenv("OPENAI_API_KEY"):
    models.append(ModelConfig("gpt-4o", provider="openai", cost=0.00625))
```

### 2. Configure Fallbacks

```python
# Multiple providers for redundancy
models = [
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("claude-3-5-haiku", provider="anthropic", cost=0.001),  # Fallback
]
```

### 3. Monitor Costs

```python
result = await agent.run(query)
print(f"Cost: ${result.total_cost:.6f}")
print(f"Provider: {result.model_used}")
```

### 4. Use Provider Strengths

```python
# Code → OpenAI
# Writing → Anthropic
# Simple → Groq

if "code" in query.lower():
    force_provider = "openai"
elif "write" in query.lower():
    force_provider = "anthropic"
```

### 5. Set Appropriate Thresholds

```python
from cascadeflow import QualityConfig

# Configure quality validation thresholds
quality_config = QualityConfig(confidence_thresholds={'moderate': 0.85})
agent = CascadeAgent(
    models=models,
    quality_config=quality_config  # Higher thresholds = more cascades
)
```

---

## Troubleshooting

### Provider Not Available

**Issue**: Provider not detected

**Solution**:
```bash
# Check API key is set
echo $OPENAI_API_KEY

# Test provider connection
python -c "from cascadeflow.providers import OpenAIProvider; OpenAIProvider()"
```

### Cost Higher Than Expected

**Issue**: Cascading too much

**Solution**:
```python
# Lower quality threshold via QualityConfig
from cascadeflow import QualityConfig

quality_config = QualityConfig(confidence_thresholds={'moderate': 0.75})
agent = CascadeAgent(models=models, quality_config=quality_config)

# Or use force_direct for expensive queries
result = await agent.run(query, force_direct=True)
```

### Rate Limits Hit

**Issue**: Too many requests to one provider

**Solution**:
```python
# Add more providers for load distribution
models.append(ModelConfig("claude-3-5-haiku", provider="anthropic", cost=0.001))
```

### One Provider Failing

**Issue**: Provider API down or rate limited

**Solution**:
- Cascade automatically falls back to next provider
- Check logs to see which provider was used
- Configure more fallback options

---

## Using Additional Providers via LiteLLM

cascadeflow integrates with LiteLLM for:
- **Accurate cost tracking** across 100+ models
- **Access to additional providers** (DeepSeek, Google, and more)
- **Automatic pricing updates** (no manual maintenance)
- **Budget management** per user

### Supported Additional Providers

Through LiteLLM integration, you can access:

| Provider | Value Proposition | Example Models | API Key |
|----------|-------------------|----------------|---------|
| **DeepSeek** | 5-10x cheaper for code tasks | `deepseek-coder`, `deepseek-chat` | `DEEPSEEK_API_KEY` |
| **Google (Vertex AI)** | Enterprise GCP integration | `gemini-pro`, `gemini-1.5-flash` | `GOOGLE_API_KEY` |
| **Azure OpenAI** | Enterprise compliance (HIPAA/SOC2) | `azure/gpt-4`, `azure/gpt-4-turbo` | `AZURE_API_KEY` |
| **Fireworks AI** | Fast open model inference | `accounts/fireworks/models/llama-v3-70b` | `FIREWORKS_API_KEY` |
| **Cohere** | Specialized for search/RAG | `command`, `command-light` | `COHERE_API_KEY` |

### Quick Start with LiteLLM

```python
from cascadeflow.integrations.litellm import (
    LiteLLMCostProvider,
    calculate_cost,
    get_provider_info,
    SUPPORTED_PROVIDERS
)

# 1. Check if a provider is supported
info = get_provider_info("deepseek")
print(info.value_prop)
# Output: "Specialized code models, very cost-effective for coding tasks"

# 2. Calculate costs (use provider prefix for accurate pricing)
cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=500
)
print(f"Cost: ${cost:.6f}")

# 3. List all supported providers
for provider_name, info in SUPPORTED_PROVIDERS.items():
    print(f"{info.display_name}: {info.value_prop}")
```

### Using DeepSeek with cascadeflow

DeepSeek offers extremely cost-effective models specialized for coding tasks:

```bash
# Set up API key
export DEEPSEEK_API_KEY="sk-..."
```

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import calculate_cost

# Calculate cost for DeepSeek (use provider prefix)
deepseek_cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=1000
)

# Use in cascade (DeepSeek uses OpenAI-compatible API)
agent = CascadeAgent(models=[
    ModelConfig(
        name="deepseek-coder",
        provider="openai",  # Uses OpenAI-compatible API
        cost=deepseek_cost * 1000,  # Convert to per-1K token cost
        base_url="https://api.deepseek.com/v1",  # ✅ Each model gets its own provider instance
        api_key="sk-..."  # Optional: model-specific API key
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
        # No base_url → uses default OpenAI endpoint
    )
])

result = await agent.run("Write a Python function to merge two sorted lists")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Model: {result.model_used}")
```

**How base_url Works:**
- ✅ **Per-model provider instances**: Each `ModelConfig` with a `base_url` or `api_key` gets its own dedicated provider instance
- ✅ **Multi-instance support**: Run draft on one server, verifier on another (e.g., different GPUs, regions, or cloud providers)
- ✅ **Backwards compatible**: Models without `base_url` share the default provider instance
- ✅ **Flexible configuration**: Mix cloud APIs (OpenAI) with self-hosted (vLLM/Ollama) seamlessly

**Cost Savings:**
- DeepSeek-Coder: ~$0.00028/1K tokens
- GPT-4: ~$0.03/1K tokens
- **Savings: ~99% cheaper for code tasks!**

### Using Google Gemini with cascadeflow

Google's Gemini models offer excellent value, especially Gemini Flash:

```bash
# Set up API key
export GOOGLE_API_KEY="..."
```

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import calculate_cost

# Calculate cost for Gemini (use provider prefix)
gemini_cost = calculate_cost(
    model="gemini/gemini-1.5-flash",
    input_tokens=1000,
    output_tokens=1000
)

# Use in cascade
agent = CascadeAgent(models=[
    ModelConfig(
        name="gemini-1.5-flash",
        provider="openai",  # Use generic provider for now
        cost=gemini_cost * 1000,
        base_url="https://generativelanguage.googleapis.com/v1beta"
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
    )
])

result = await agent.run("Summarize this article: ...")
```

**Cost Savings:**
- Gemini 1.5 Flash: ~$0.000225/1K tokens
- GPT-4o: ~$0.0075/1K tokens
- **Savings: ~97% cheaper for simple tasks!**

### Cost Comparison

Here's how different providers compare for a typical task (1K input + 500 output tokens):

```python
from cascadeflow.integrations.litellm import LiteLLMCostProvider

cost_provider = LiteLLMCostProvider()

models = [
    ("gpt-4o", "OpenAI Premium"),
    ("gpt-4o-mini", "OpenAI Budget"),
    ("deepseek/deepseek-coder", "DeepSeek Code"),
    ("gemini/gemini-1.5-flash", "Google Budget"),
    ("anthropic/claude-3-5-sonnet-20241022", "Anthropic Premium"),
]

for model, label in models:
    cost = cost_provider.calculate_cost(
        model=model,
        input_tokens=1000,
        output_tokens=500
    )
    print(f"{label:20} ${cost:.6f}")
```

**Output:**
```
OpenAI Premium       $0.007500
OpenAI Budget        $0.000225
DeepSeek Code        $0.000280
Google Budget        $0.000225
Anthropic Premium    $0.010500
```

**💡 TIP:** Always use provider prefixes (e.g., `deepseek/deepseek-coder`, `anthropic/claude-3-5-sonnet-20241022`, `gemini/gemini-1.5-flash`) for accurate pricing from LiteLLM.

### Complete Example

See [`examples/integrations/litellm_providers.py`](../../examples/integrations/litellm_providers.py) for a comprehensive example that shows:

1. **Supported providers** - List all LiteLLM-supported providers
2. **Cost calculation** - Compare costs across providers
3. **Model pricing** - Get detailed pricing information
4. **Cost comparison** - Compare across different use cases
5. **Provider info** - Get provider capabilities dynamically
6. **Convenience functions** - Quick cost calculations
7. **API key status** - Check which keys are configured
8. **Real-world usage** - Integrate with cascadeflow agents

### Benefits of LiteLLM Integration

✅ **Accurate Cost Tracking**
- LiteLLM maintains up-to-date pricing for 100+ models
- No manual pricing updates needed
- Includes input/output token pricing
- Handles special pricing (batch, cached tokens)

✅ **Access More Providers**
- DeepSeek (code specialization, 5-10x cheaper)
- Google/Vertex AI (enterprise, 50-100x cheaper for simple tasks)
- Azure OpenAI (compliance, HIPAA/SOC2)
- Fireworks, Cohere, and more

✅ **Budget Management**
- Track spending per user
- Set budget limits
- Get alerts at thresholds
- Enforce budgets automatically

✅ **Zero Maintenance**
- Pricing automatically updated
- New models supported quickly
- Community-driven updates

### When to Use LiteLLM vs Native Providers

**Use Native Providers (Recommended):**
- OpenAI, Anthropic, Groq, Together, Ollama, vLLM, HuggingFace
- Best performance and feature support
- Direct integration, no extra layer
- Full streaming and tool calling support

**Use LiteLLM Integration:**
- DeepSeek (code tasks, extreme cost savings)
- Google/Gemini (simple tasks, ultra-cheap)
- Azure OpenAI (enterprise compliance)
- Other providers not yet in native list
- Need accurate cost tracking across providers

### Installation

```bash
# LiteLLM is included with cascadeflow[all]
pip install cascadeflow[all]

# Or install separately
pip install litellm
```

### Resources

- **Example**: [`examples/integrations/litellm_providers.py`](../../examples/integrations/litellm_providers.py)
- **Integration Code**: [`cascadeflow/integrations/litellm.py`](../../cascadeflow/integrations/litellm.py)
- **LiteLLM Docs**: https://docs.litellm.ai/docs/providers
- **Cost Tracking Guide**: [cost_tracking.md](cost_tracking.md)

---

## Next Steps

- **Examples**: See [`examples/multi_provider.py`](../../examples/multi_provider.py)
- **LiteLLM Example**: See [`examples/integrations/litellm_providers.py`](../../examples/integrations/litellm_providers.py)
- **Tools**: Read [Tool Guide](tools.md) for tool calling with providers
- **Cost Tracking**: Read [Cost Tracking Guide](cost_tracking.md)
- **API Reference**: Check provider-specific documentation

---

**Questions?** Open an issue on [GitHub](https://github.com/lemony-ai/cascadeflow/issues).