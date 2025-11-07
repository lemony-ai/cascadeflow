# cascadeflow Examples

**Complete collection of examples** demonstrating cascadeflow from basics to production deployment.

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Install cascadeflow
pip install cascadeflow[all]

# 2. Set your API key
export OPENAI_API_KEY="sk-..."

# 3. Run your first example
python examples/basic_usage.py
```

**That's it!** You'll see cascading in action with cost savings.

---

## 🎯 Quick Reference - Find What You Need

| Example | What It Does | Complexity | Time | Best For |
|---------|--------------|------------|------|----------|
| **basic_usage.py** | Learn cascading basics | ⭐ Easy | 5 min | First-time users |
| **streaming_text.py** | Real-time streaming | ⭐⭐ Medium | 10 min | Interactive apps |
| **tool_execution.py** | Function calling | ⭐⭐ Medium | 15 min | Agent builders |
| **cost_tracking.py** | Budget management | ⭐⭐ Medium | 15 min | Cost optimization |
| **multi_provider.py** | Mix AI providers | ⭐⭐ Medium | 10 min | Multi-cloud |
| **reasoning_models.py** | o1, o3, Claude 3.7, DeepSeek-R1 | ⭐⭐ Medium | 10 min | Complex reasoning |
| **fastapi_integration.py** | REST API server | ⭐⭐⭐ Advanced | 20 min | Production APIs |
| **production_patterns.py** | Enterprise patterns | ⭐⭐⭐ Advanced | 30 min | Production deployment |
| **edge_device.py** | Edge AI (Jetson/Pi) | ⭐⭐⭐ Advanced | 20 min | Edge deployment |

**💡 Tip:** Start with `basic_usage.py`, then explore based on your use case!

---

## 🔍 Find by Feature

**I want to...**
- **Stream responses?** → `streaming_text.py`, `streaming_tools.py`
- **Use tools/functions?** → `tool_execution.py`, `streaming_tools.py`
- **Track costs?** → `cost_tracking.py`, `user_budget_tracking.py`, `integrations/litellm_cost_tracking.py`
- **Enforce budgets?** → `enforcement/basic_enforcement.py`, `enforcement/stripe_integration.py`
- **Use multiple providers?** → `multi_provider.py`, `integrations/litellm_providers.py`
- **Access DeepSeek/Gemini/Azure?** → `integrations/litellm_providers.py`
- **Deploy to production?** → `production_patterns.py`, `fastapi_integration.py`
- **Monitor in production?** → `integrations/opentelemetry_grafana.py`
- **Run locally/edge?** → `edge_device.py`, `integrations/local_providers_setup.py`, `ollama_cascade.py`, `vllm_cascade.py`, `multi_instance_ollama.py`, `multi_instance_vllm.py`
- **Use reasoning models?** → `reasoning_models.py`
- **Manage user budgets?** → `user_budget_tracking.py`, `profile_database_integration.py`
- **Integrate with Stripe?** → `enforcement/stripe_integration.py`
- **Add safety guardrails?** → `guardrails_usage.py`
- **Customize routing?** → `custom_cascade.py`, `multi_step_cascade.py`
- **Validate quality?** → `custom_validation.py`, `semantic_quality_domain_detection.py`

---

## 📋 Table of Contents

- [🌟 Core Examples](#-core-examples-6-examples---start-here) - Basic usage, streaming, tools
- [💰 Cost Management](#-cost-management--budgets-4-examples) - Budgets and tracking
- [🏭 Production](#-production--integration-5-examples) - Deployment patterns
- [🔌 Integrations](#-integrations-5-examples) - LiteLLM, OpenTelemetry, local providers
- [🛡️ Enforcement](#%EF%B8%8F-enforcement-2-examples) - Budget enforcement and Stripe
- [⚡ Advanced](#-advanced-patterns-6-examples) - Custom routing and validation
- [🌐 Edge](#-edge--local-deployment-3-examples) - Edge device deployment and multi-instance configurations

---

## 📚 Examples by Category

<details open>
<summary><h3>🌟 Core Examples (6 examples) - Start Here</h3></summary>

Perfect for learning cascadeflow basics. Start with these!

#### 1. Basic Usage ⭐ **START HERE**
**File:** [`basic_usage.py`](basic_usage.py)
**Time:** 5 minutes
**What you'll learn:**
- How cascading works (cheap model → expensive model)
- Automatic quality-based routing
- Cost tracking and savings
- When drafts are accepted vs rejected

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
python examples/basic_usage.py
```

**Expected output:**
```
Query 1/8: What color is the sky?
   💚 Model: gpt-4o-mini only
   💰 Cost: $0.000014
   ✅ Draft Accepted

Query 6/8: Explain quantum entanglement...
   💚💛 Models: gpt-4o-mini + gpt-4o
   💰 Cost: $0.005006
   ❌ Draft Rejected

💰 TOTAL SAVINGS: 45% reduction
```

---

#### 2. Streaming Text Responses 🌊
**File:** [`streaming_text.py`](streaming_text.py)
**Time:** 10 minutes
**What you'll learn:**
- Real-time text streaming
- See cascade decisions in action
- Visual feedback with colors
- Performance metrics

**Key concept:** Watch the cascade happen in real-time!

---

#### 3. Tool Execution 🎯
**File:** [`tool_execution.py`](tool_execution.py)
**Time:** 15 minutes
**What you'll learn:**
- Function calling with tools
- Tool execution workflow
- Multi-turn conversations
- Error handling

**Important:** This shows actual tool EXECUTION, not just streaming tool calls.

---

#### 4. Multi-Provider Cascade 🌐
**File:** [`multi_provider.py`](multi_provider.py)
**Time:** 10 minutes
**What you'll learn:**
- Mix models from different providers
- OpenAI + Anthropic + Groq
- Provider-specific optimizations
- Cross-provider cost comparison

**Example setup:**
```python
agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b", "groq", cost=0.00005),         # Fast & cheap
    ModelConfig("gpt-4o", "openai", cost=0.00625),             # Quality
    ModelConfig("claude-3-5-sonnet", "anthropic", cost=0.003), # Reasoning
])
```

---

#### 5. Reasoning Models 🧠
**File:** [`reasoning_models.py`](reasoning_models.py)
**Time:** 10 minutes
**What you'll learn:**
- Use o1, o3-mini, Claude 3.7, DeepSeek-R1
- Extended thinking mode
- Chain-of-thought reasoning
- Auto-detection of reasoning capabilities

**Supported models:**
- OpenAI: o1, o1-mini, o3-mini
- Anthropic: claude-3-7-sonnet
- Ollama: deepseek-r1 (free local)
- vLLM: deepseek-r1 (self-hosted)

---

#### 6. Cost Tracking 💰
**File:** [`cost_tracking.py`](cost_tracking.py)
**Time:** 15 minutes
**What you'll learn:**
- Real-time cost monitoring
- Budget limits and warnings
- Per-model cost breakdown
- Cost optimization insights

**Features:**
- Budget alerts at 80% threshold
- Per-provider analysis
- Query-level cost tracking
- Savings calculation

</details>

<details>
<summary><h3>🔧 Tool & Function Calling (2 examples)</h3></summary>

Learn how to use tools and functions with cascadeflow.

#### Tool Execution
**File:** [`tool_execution.py`](tool_execution.py)
Complete tool workflow with `ToolExecutor` - actual execution, not just detection.

#### Streaming Tools
**File:** [`streaming_tools.py`](streaming_tools.py)
Watch tool calls form in real-time as JSON arrives.

**Key difference:**
- `tool_execution.py` = Complete workflow (detection + execution)
- `streaming_tools.py` = Just streaming detection

</details>

<details>
<summary><h3>💰 Cost Management & Budgets (4 examples)</h3></summary>

Track costs, manage budgets, and optimize spending.

#### 1. Cost Tracking
**File:** [`cost_tracking.py`](cost_tracking.py)
Real-time cost monitoring with budget limits.

#### 2. User Budget Tracking
**File:** [`user_budget_tracking.py`](user_budget_tracking.py)
Per-user budget enforcement and tracking.

#### 3. User Profile Usage
**File:** [`user_profile_usage.py`](user_profile_usage.py)
User-specific routing and tier management.

#### 4. Profile Database Integration
**File:** [`profile_database_integration.py`](profile_database_integration.py)
Integrate user profiles with databases.

**Use cases:**
- SaaS applications with user tiers
- Multi-tenant systems
- Budget-aware routing
- Cost allocation by user

</details>

<details>
<summary><h3>🏭 Production & Integration (5 examples)</h3></summary>

Deploy cascadeflow to production with enterprise patterns.

#### 1. Production Patterns ⭐
**File:** [`production_patterns.py`](production_patterns.py)
**Time:** 30 minutes
**What you'll learn:**
- Error handling & retries
- Rate limiting
- Circuit breakers
- Caching
- Monitoring & alerting

**Enterprise features:**
- Exponential backoff
- Request throttling
- Failure detection
- Response caching
- Health checks

---

#### 2. FastAPI Integration
**File:** [`fastapi_integration.py`](fastapi_integration.py)
**Time:** 20 minutes
REST API deployment with Server-Sent Events (SSE).

**Endpoints:**
- `POST /api/query` - Non-streaming
- `GET /api/query/stream` - SSE streaming
- `GET /health` - Health check
- `GET /api/stats` - Statistics

---

#### 3. Batch Processing
**File:** [`batch_processing.py`](batch_processing.py)
Process multiple queries efficiently.

---

#### 4. Rate Limiting
**File:** [`rate_limiting_usage.py`](rate_limiting_usage.py)
Request throttling and queuing.

---

#### 5. Guardrails
**File:** [`guardrails_usage.py`](guardrails_usage.py)
Safety and content filtering.

</details>

<details>
<summary><h3>🔌 Integrations (5 examples)</h3></summary>

Access 10+ providers with accurate cost tracking, production monitoring, and local inference.

#### 1. LiteLLM Provider Integration ⭐
**File:** [`integrations/litellm_providers.py`](integrations/litellm_providers.py)
**Time:** 15 minutes
**What you'll learn:**
- Access DeepSeek, Google Gemini, Azure OpenAI, and 7 more providers
- Calculate accurate costs for 100+ models
- Compare costs across providers
- Integrate with CascadeAgent

**8 Complete Examples:**
1. List all supported providers
2. Cost calculation comparison
3. Model pricing details
4. Cost comparison across use cases
5. Provider information lookup
6. Convenience functions
7. API key status check
8. Real-world CascadeAgent integration

**Cost Savings:**
- DeepSeek: 95% cheaper than GPT-4o for code ($0.00028 vs $0.0075)
- Gemini Flash: 98% cheaper for simple tasks ($0.000225 vs $0.0075)
- Annual impact: Save $21,000-$28,500 per year

**Quick Example:**
```python
from cascadeflow.integrations.litellm import calculate_cost

cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=500
)
print(f"Cost: ${cost:.6f}")  # $0.000280 vs $0.007500 for GPT-4o
```

---

#### 2. LiteLLM Cost Tracking
**File:** [`integrations/litellm_cost_tracking.py`](integrations/litellm_cost_tracking.py)
Cost tracking with LiteLLM integration and provider validation.

---

#### 3. Local Providers Setup
**File:** [`integrations/local_providers_setup.py`](integrations/local_providers_setup.py)
**Time:** 15 minutes
Complete guide for Ollama and vLLM setup (local, network, remote scenarios).

---

#### 4. OpenTelemetry & Grafana
**File:** [`integrations/opentelemetry_grafana.py`](integrations/opentelemetry_grafana.py)
**Time:** 20 minutes
Production observability with OpenTelemetry, Prometheus, and Grafana.

**Features:**
- Cost metrics export
- Token usage tracking
- Latency histograms
- User-level analytics

---

#### 5. Provider Testing
**File:** [`integrations/test_all_providers.py`](integrations/test_all_providers.py)
Validate API keys and test all 10 providers.

**Documentation:** 📖 [`integrations/README.md`](integrations/README.md)

</details>

<details>
<summary><h3>🛡️ Enforcement (2 examples)</h3></summary>

Implement budget enforcement and cost controls for production SaaS applications.

#### 1. Basic Enforcement ⭐
**File:** [`enforcement/basic_enforcement.py`](enforcement/basic_enforcement.py)
**Time:** 10 minutes
**What you'll learn:**
- Configure budget limits per tier
- Use built-in enforcement callbacks
- Create custom callbacks
- Handle enforcement actions (ALLOW, WARN, BLOCK, DEGRADE)

**Built-in Callbacks:**
- `strict_budget_enforcement` - Block at 100%, warn at 80%
- `graceful_degradation` - Degrade to cheaper models at 90%
- `tier_based_enforcement` - Different policies per tier

**Quick Example:**
```python
from cascadeflow.telemetry import (
    BudgetConfig,
    CostTracker,
    EnforcementCallbacks,
    strict_budget_enforcement,
)

# Configure budgets
tracker = CostTracker(
    user_budgets={
        "free": BudgetConfig(daily=0.10),
        "pro": BudgetConfig(daily=1.0),
    }
)

# Set up enforcement
callbacks = EnforcementCallbacks()
callbacks.register(strict_budget_enforcement)

# Check before processing
action = callbacks.check(context)
if action == EnforcementAction.BLOCK:
    return {"error": "Budget exceeded. Please upgrade."}
```

---

#### 2. Stripe Integration
**File:** [`enforcement/stripe_integration.py`](enforcement/stripe_integration.py)
**Time:** 15 minutes
Real-world template for integrating with Stripe subscriptions.

**Features:**
- Map Stripe tiers to budgets
- Subscription-based enforcement
- Upgrade flow handling
- Tier-specific policies

**Documentation:** 📖 [`enforcement/README.md`](enforcement/README.md)

</details>

<details>
<summary><h3>⚡ Advanced Patterns (6 examples)</h3></summary>

Custom routing, validation, and specialized deployments.

#### 1. Custom Cascade Strategies
**File:** [`custom_cascade.py`](custom_cascade.py)
Domain-specific routing, time-based routing, budget-aware cascades.

#### 2. Custom Validation
**File:** [`custom_validation.py`](custom_validation.py)
Build custom quality validators for specific domains.

#### 3. Multi-Step Cascade
**File:** [`multi_step_cascade.py`](multi_step_cascade.py)
Complex multi-stage cascades.

#### 4. Semantic Quality Detection
**File:** [`semantic_quality_domain_detection.py`](semantic_quality_domain_detection.py)
ML-based domain and quality detection.

#### 5. Cost Forecasting & Anomaly Detection
**File:** [`cost_forecasting_anomaly_detection.py`](cost_forecasting_anomaly_detection.py)
Predict costs and detect unusual spending.

#### 6. vLLM Example
**File:** [`vllm_example.py`](vllm_example.py)
Self-hosted inference with vLLM.

</details>

<details>
<summary><h3>🌐 Edge & Local Deployment (5 examples)</h3></summary>

Run cascadeflow on edge devices with local inference, cascade to cloud, and multi-instance configurations.

#### 1. Edge Device Deployment
**File:** [`edge_device.py`](edge_device.py)
**Time:** 20 minutes
**What you'll learn:**
- Local inference with vLLM on Jetson/Raspberry Pi
- Automatic cascade to cloud for complex queries
- Zero-cost local processing
- Privacy-first architecture

**Hardware:**
- Nvidia Jetson (Thor, Orin, Xavier)
- Raspberry Pi 5
- 8GB+ RAM recommended

**Use cases:**
- Smart factories
- Healthcare devices (HIPAA)
- Retail kiosks
- Autonomous robots
- IoT gateways

**Cost savings:** 70% + privacy + lower latency

#### 2. Ollama Cascade
**File:** [`ollama_cascade.py`](ollama_cascade.py)
**Time:** 10 minutes

**What you'll learn:**
- Run Ollama model locally as draft (free inference)
- Automatically escalate to OpenAI gpt-4o for complex queries
- Test cascade logic with local + cloud providers
- 100% local for simple queries, cloud only when needed

**Prerequisites:**
```bash
# Start Ollama and pull model
ollama pull mistral:7b-instruct

# Set OpenAI API key
export OPENAI_API_KEY="sk-..."

# Run example
python examples/ollama_cascade.py
```

**Configuration:**
```python
agent = CascadeAgent(models=[
    ModelConfig(
        name="mistral:7b-instruct",
        provider="ollama",
        base_url="http://localhost:11434",
        quality_threshold=0.7,  # Accept if confidence >= 70%
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        quality_threshold=0.95,  # Very high quality
    ),
])
```

#### 3. vLLM Cascade
**File:** [`vllm_cascade.py`](vllm_cascade.py)
**Time:** 10 minutes

**What you'll learn:**
- Run vLLM model locally as draft (high-performance inference)
- Automatically escalate to OpenAI gpt-4o for complex queries
- PagedAttention and continuous batching benefits
- Same cascade pattern as Ollama but 10-24x faster

**Prerequisites:**
```bash
# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000

# Set OpenAI API key
export OPENAI_API_KEY="sk-..."

# Run example
python examples/vllm_cascade.py
```

**Use cases:**
- Local draft inference with cloud fallback
- Testing cascade behavior with self-hosted models
- Cost optimization (free local + paid cloud only when needed)

#### 4. Multi-Instance Ollama
**File:** [`multi_instance_ollama.py`](multi_instance_ollama.py)
**Time:** 15 minutes

**What you'll learn:**
- Run draft and verifier models on **separate Ollama instances** with different base URLs
- Multi-GPU configuration with Docker Compose
- Health checks and instance validation
- GPU resource isolation for optimal performance
- How the per-model provider architecture enables multi-instance setups

**Key Architecture Concept:**
cascadeflow's per-model provider instantiation allows each `ModelConfig` with a unique `base_url` to get its own dedicated provider instance. This enables:
- Draft model → connects to `http://localhost:11434`
- Verifier model → connects to `http://localhost:11435`
- No resource contention or GPU competition

**Use cases:**
- Multi-GPU systems (draft on GPU 0, verifier on GPU 1)
- Distributed inference across network
- Load balancing between instances
- Better fault isolation

**Setup:** See [Docker Compose guide](docker/multi-instance-ollama/)

#### 5. Multi-Instance vLLM
**File:** [`multi_instance_vllm.py`](multi_instance_vllm.py)
**Time:** 15 minutes

**What you'll learn:**
- Run draft and verifier models on **separate vLLM instances** with different base URLs
- High-performance inference with PagedAttention
- Kubernetes pod configuration
- Production-scale deployments
- Multi-instance architecture implementation

**Key Architecture Concept:**
Each model's `base_url` parameter creates a dedicated provider instance:
```python
# Draft model gets provider instance pointing to :8000
ModelConfig(name="drafter", provider="vllm", base_url="http://192.168.0.199:8000/v1")

# Verifier model gets provider instance pointing to :8001
ModelConfig(name="verifier", provider="vllm", base_url="http://192.168.0.199:8001/v1")
```

**Use cases:**
- GPU 0: Fast 7B model (200+ tokens/sec)
- GPU 1: Powerful 70B model (50+ tokens/sec)
- Kubernetes StatefulSets
- Load-balanced inference clusters

**Performance:** 10-24x faster than standard serving

**See also:** [Local Providers Guide - Multi-Instance Architecture](../docs/guides/local-providers.md#multi-instance-architecture-advanced) for comprehensive setup details

</details>

---

## 🎓 Learning Path

### Step 1: Basics (30 minutes)
1. ✅ Run `basic_usage.py` - Understand core concepts
2. ✅ Read the code comments - Learn patterns
3. ✅ Try different queries - See routing decisions

**Key concepts:**
- Cascading = cheap model first, escalate if needed
- Draft accepted = money saved ✅
- Draft rejected = quality ensured ✅

### Step 2: Real-Time Features (30 minutes)
1. ✅ Run `streaming_text.py` - See streaming
2. ✅ Run `tool_execution.py` - Learn tool usage
3. ✅ Read [Streaming Guide](../docs/guides/streaming.md)

**Key concepts:**
- Streaming requires 2+ models
- Event-based architecture
- Tool execution workflow

### Step 3: Cost Management (30 minutes)
1. ✅ Run `cost_tracking.py` - Learn budget tracking
2. ✅ Run `user_budget_tracking.py` - Per-user budgets
3. ✅ Read [Cost Tracking Guide](../docs/guides/cost_tracking.md)

**Key concepts:**
- Budget alerts at 80%
- Per-model breakdown
- Cost optimization

### Step 4: Production (1 hour)
1. ✅ Run `production_patterns.py` - Enterprise patterns
2. ✅ Run `fastapi_integration.py` - API deployment
3. ✅ Read [Production Guide](../docs/guides/production.md)

**Key concepts:**
- Error handling
- Rate limiting
- Monitoring

### Step 5: Customize (1 hour)
1. ✅ Run `custom_cascade.py` - Custom routing
2. ✅ Run `custom_validation.py` - Custom validators
3. ✅ Modify for your use case

---

## 🛠️ Running Examples

### Prerequisites

```bash
# Install with all dependencies
pip install cascadeflow[all]

# Or install specific providers
pip install cascadeflow[openai]
pip install cascadeflow[anthropic]
pip install cascadeflow[groq]
```

### Set API Keys

```bash
# OpenAI (most examples)
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Groq (free, fast)
export GROQ_API_KEY="gsk_..."

# Together AI
export TOGETHER_API_KEY="..."

# Hugging Face
export HF_TOKEN="hf_..."
```

### Run Examples

```bash
# From repository root
python examples/basic_usage.py
python examples/streaming_text.py
python examples/cost_tracking.py

# With custom config
python examples/multi_provider.py
```

---

## 🔧 Troubleshooting

<details>
<summary><b>API key errors</b></summary>

```bash
# Check if set
echo $OPENAI_API_KEY

# Set it
export OPENAI_API_KEY="sk-..."

# Windows
set OPENAI_API_KEY=sk-...
```
</details>

<details>
<summary><b>Import errors</b></summary>

```bash
# Install all dependencies
pip install cascadeflow[all]

# Or specific providers
pip install cascadeflow[openai]
```
</details>

<details>
<summary><b>Examples run but show errors</b></summary>

```bash
# Check Python version (3.9+ required)
python --version

# Reinstall
pip install --upgrade cascadeflow[all]
```
</details>

<details>
<summary><b>Streaming shows garbled output</b></summary>

Terminal may not support ANSI colors:
```bash
# Disable colors
TERM=dumb python examples/streaming_text.py
```
</details>

---

## 💡 Pro Tips

### 1. Start Simple
Begin with `basic_usage.py` before advanced examples.

### 2. Read the Code
All examples are heavily commented. Read through to understand patterns.

### 3. Key Concepts

**Streaming vs Execution:**
- `streaming_tools.py` = Watch tool calls form
- `tool_execution.py` = Actually execute tools
- Why separate? Gives you control over validation

**Cost Tracking:**
- Extract from `result.metadata`
- Use safe extraction: `getattr()` and `.get()`
- Track with `CostTracker` for budgets

**Quality Validation:**
- Draft accepted = cheap model only (saves money!)
- Draft rejected = both models called (ensures quality)
- Adjust thresholds based on use case

### 4. Watch Statistics

```python
result = await agent.run(query)

# Safe extraction
total_cost = getattr(result, 'total_cost', 0)
model_used = getattr(result, 'model_used', 'unknown')
cascaded = result.metadata.get('cascaded', False)
```

### 5. Use CostTracker

```python
from cascadeflow.telemetry import CostTracker

tracker = CostTracker(budget_limit=1.0, warn_threshold=0.8)

# Run queries
result = await agent.run(query)

# Track costs
tracker.add_cost(
    model=result.model_used,
    provider="openai",
    tokens=result.metadata.get('total_tokens', 0),
    cost=result.total_cost
)

# View summary
tracker.print_summary()
```

---

## 📖 Complete Documentation

### Getting Started Guides
- [Quick Start](../docs/guides/quickstart.md) - 5-minute introduction
- [Providers Guide](../docs/guides/providers.md) - Configure AI providers
- [Streaming Guide](../docs/guides/streaming.md) - Real-time responses
- [Tools Guide](../docs/guides/tools.md) - Function calling
- [Cost Tracking](../docs/guides/cost_tracking.md) - Budget management

### Advanced Guides
- [Production Guide](../docs/guides/production.md) - Enterprise deployment
- [Performance Guide](../docs/guides/performance.md) - Optimization
- [Custom Cascade](../docs/guides/custom_cascade.md) - Custom routing
- [Custom Validation](../docs/guides/custom_validation.md) - Quality control
- [Edge Devices](../docs/guides/edge_device.md) - Jetson/Pi deployment
- [Browser Cascading](../docs/guides/browser_cascading.md) - Edge/browser deployment
- [FastAPI Integration](../docs/guides/fastapi.md) - REST API
- [n8n Integration](../docs/guides/n8n_integration.md) - No-code automation

📚 **[View All Documentation →](../docs/)**

---

## 🤝 Contributing Examples

Have a great use case? Contribute an example!

### Template

```python
"""
Your Example - Brief Description

What it demonstrates:
- Feature 1
- Feature 2

Requirements:
- Dependency 1

Setup:
    pip install cascadeflow[all]
    export API_KEY="..."
    python examples/your_example.py

Expected Results:
    Description of output
"""

import asyncio
from cascadeflow import CascadeAgent, ModelConfig

async def main():
    print("=" * 80)
    print("YOUR EXAMPLE TITLE")
    print("=" * 80)

    # Your code here

    print("\nKEY TAKEAWAYS:")
    print("- Takeaway 1")
    print("- Takeaway 2")

if __name__ == "__main__":
    asyncio.run(main())
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

## 📞 Need Help?

### Documentation
📖 [Complete Guides](../docs/guides/)
🌊 [Streaming Guide](../docs/guides/streaming.md)
🛠️ [Tools Guide](../docs/guides/tools.md)
💰 [Cost Tracking Guide](../docs/guides/cost_tracking.md)
🏭 [Production Guide](../docs/guides/production.md)

### Community
💬 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions) - Ask questions
🐛 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues) - Report bugs
💡 Use "question" label for general questions

---

## 📊 Summary

### ✅ Available Examples (29 total)

**Core (6):** Basic usage, streaming text, tool execution, multi-provider, reasoning models, cost tracking

**Cost Management (4):** Cost tracking, user budgets, user profiles, database integration

**Production (5):** Production patterns, FastAPI, batch processing, rate limiting, guardrails

**Integrations (5):** LiteLLM providers, cost tracking, local setup, OpenTelemetry, provider testing

**Enforcement (2):** Basic enforcement, Stripe integration

**Advanced (7):** Custom cascade, custom validation, multi-step, semantic detection, forecasting, Ollama cascade, vLLM cascade

**Edge (5):** Edge device deployment, Ollama cascade, vLLM cascade, multi-instance Ollama, multi-instance vLLM

### 📚 Documentation Coverage

- ✅ **29 examples** (~6,000+ lines of code)
- ✅ **3 specialized READMEs** (integrations, enforcement, main)
- ✅ **10+ comprehensive guides** (~10,000 lines of docs)
- ✅ **~16,000+ lines total** of professional documentation
- ✅ **100% feature coverage**

### 🔑 Key Learnings

**Essential Concepts:**
- ✅ Draft accepted = money saved
- ✅ Draft rejected = quality ensured
- ✅ Streaming requires 2+ models
- ✅ Use universal tool format
- ✅ Extract costs from `result.metadata`
- ✅ Track budgets with `CostTracker`

**Production Ready:**
- ✅ Error handling
- ✅ Rate limiting
- ✅ Monitoring
- ✅ Budget management
- ✅ API deployment

---

**💰 Save 40-85% on AI costs with intelligent cascading!** 🚀

[View All Documentation](../docs/) • [Python Examples](../examples/) • [TypeScript Examples](../packages/core/examples/) • [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions)

