<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/assets/CF_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/assets/CF_logo_dark.svg">
  <img alt="cascadeflow Logo" src=".github/assets/CF_logo_dark.svg" width="533">
</picture>

# Smart AI model cascading for cost optimization

[![PyPI version](https://img.shields.io/pypi/v/cascadeflow?color=blue&label=Python)](https://pypi.org/project/cascadeflow/)
[![npm version](https://img.shields.io/npm/v/@cascadeflow/core?color=red&label=TypeScript)](https://www.npmjs.com/package/@cascadeflow/core)
[![n8n version](https://img.shields.io/npm/v/@cascadeflow/n8n-nodes-cascadeflow?color=orange&label=n8n)](https://www.npmjs.com/package/@cascadeflow/n8n-nodes-cascadeflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Downloads](https://static.pepy.tech/badge/cascadeflow)](https://pepy.tech/project/cascadeflow)
[![Tests](https://github.com/lemony-ai/cascadeflow/actions/workflows/test.yml/badge.svg)](https://github.com/lemony-ai/cascadeflow/actions/workflows/test.yml)
[![Python Docs](https://img.shields.io/badge/docs-Python-blue)](./docs/)
[![TypeScript Docs](https://img.shields.io/badge/docs-TypeScript-red)](./docs/)
[![X Follow](https://img.shields.io/twitter/follow/saschabuehrle?style=social)](https://x.com/saschabuehrle)
[![GitHub Stars](https://img.shields.io/github/stars/lemony-ai/cascadeflow?style=social)](https://github.com/lemony-ai/cascadeflow)

**[<img src=".github/assets/CF_python_color.svg" width="22" height="22" alt="Python" style="vertical-align: middle;"/> Python](#-python) • [<img src=".github/assets/CF_ts_color.svg" width="22" height="22" alt="TypeScript" style="vertical-align: middle;"/> TypeScript](#-typescript) • [<img src=".github/assets/CF_n8n_color.svg" width="22" height="22" alt="n8n" style="vertical-align: middle;"/> n8n](#-n8n-integration) • [📖 Docs](./docs/) • [💡 Examples](#examples)**

</div>

---

**Stop Bleeding Money on AI Calls. Cut Costs 30-65% in 3 Lines of Code.**

40-70% of text prompts and 20-60% of agent calls don't need expensive flagship models. You're overpaying every single day.

*cascadeflow fixes this with intelligent model cascading, available in Python and TypeScript.*

```python
pip install cascadeflow
```

```tsx
npm install @cascadeflow/core
```

---

## Why cascadeflow?

cascadeflow is an intelligent AI model cascading library that dynamically selects the optimal model for each query or tool call through speculative execution. It's based on the research that 40-70% of queries don't require slow, expensive flagship models, and domain-specific smaller models often outperform large general-purpose models on specialized tasks. For the remaining queries that need advanced reasoning, cascadeflow automatically escalates to flagship models if needed.

### Use Cases

Use cascadeflow for:

- **Cost Optimization.** Reduce API costs by 40-85% through intelligent model cascading and speculative execution with automatic per-query cost tracking.
- **Cost Control and Transparency.** Built-in telemetry for query, model, and provider-level cost tracking with configurable budget limits and programmable spending caps.
- **Low Latency & Speed Optimization**. Sub-2ms framework overhead with fast provider routing (Groq sub-50ms). Cascade simple queries to fast models while reserving expensive models for complex reasoning, achieving 2-10x latency reduction overall. (use preset `PRESET_ULTRA_FAST`)
- **Multi-Provider Flexibility.** Unified API across **`OpenAI`, `Anthropic`, `Groq`, `Ollama`, `vLLM`, `Together`, and `Hugging Face`** with automatic provider detection and zero vendor lock-in. Optional **`LiteLLM`** integration for 100+ additional providers.
- **Edge & Local-Hosted AI Deployment.** Use best of both worlds: handle most queries with local models (vLLM, Ollama), then automatically escalate complex queries to cloud providers only when needed.

> **ℹ️ Note:** SLMs (under 10B parameters) are sufficiently powerful for 60-70% of agentic AI tasks. [Research paper](https://www.researchgate.net/publication/392371267_Small_Language_Models_are_the_Future_of_Agentic_AI)

---

## How cascadeflow Works

cascadeflow uses **speculative execution with quality validation**:

1. **Speculatively executes** small, fast models first - optimistic execution ($0.15-0.30/1M tokens)
2. **Validates quality** of responses using configurable thresholds (completeness, confidence, correctness)
3. **Dynamically escalates** to larger models only when quality validation fails ($1.25-3.00/1M tokens)
4. **Learns patterns** to optimize future cascading decisions and domain specific routing

Zero configuration. Works with YOUR existing models (7 Providers currently supported).

In practice, 60-70% of queries are handled by small, efficient models (8-20x cost difference) without requiring escalation

**Result:** 40-85% cost reduction, 2-10x faster responses, zero quality loss.

```
┌─────────────────────────────────────────────────────────────┐
│                      cascadeflow Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Cascade Agent                                        │  │
│  │                                                       │  │
│  │  Orchestrates the entire cascade execution            │  │
│  │  • Query routing & model selection                    │  │
│  │  • Drafter -> Verifier coordination                   │  │
│  │  • Cost tracking & telemetry                          │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Domain Pipeline                                      │  │
│  │                                                       │  │
│  │  Automatic domain classification                      │  │
│  │  • Rule-based detection (CODE, MATH, DATA, etc.)      │  │
│  │  • Optional ML semantic classification                │  │
│  │  • Domain-optimized pipelines & model selection       │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Quality Validation Engine                            │  │
│  │                                                       │  │
│  │  Multi-dimensional quality checks                     │  │
│  │  • Length validation (too short/verbose)              │  │
│  │  • Confidence scoring (logprobs analysis)             │  │
│  │  • Format validation (JSON, structured output)        │  │
│  │  • Semantic alignment (intent matching)               │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Cascading Engine (<2ms overhead)                     │  │
│  │                                                       │  │
│  │  Smart model escalation strategy                      │  │
│  │  • Try cheap models first (speculative execution)     │  │
│  │  • Validate quality instantly                         │  │
│  │  • Escalate only when needed                          │  │
│  │  • Automatic retry & fallback                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Provider Abstraction Layer                           │  │
│  │                                                       │  │
│  │  Unified interface for 7+ providers                   │  │
│  │  • OpenAI • Anthropic • Groq • Ollama                 │  │
│  │  • Together • vLLM • HuggingFace • LiteLLM            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### <img src=".github/assets/CF_python_color.svg" width="24" height="24" alt="Python"/> Python

```python
pip install cascadeflow[all]
```

```python
from cascadeflow import CascadeAgent, ModelConfig

# Define your cascade - try cheap model first, escalate if needed
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),  # Draft model (~$0.375/1M tokens)
    ModelConfig(name="gpt-5", provider="openai", cost=0.00562),         # Verifier model (~$5.62/1M tokens)
])

# Run query - automatically routes to optimal model
result = await agent.run("What's the capital of France?")

print(f"Answer: {result.content}")
print(f"Model used: {result.model_used}")
print(f"Cost: ${result.total_cost:.6f}")
```

<details>
<summary><b>💡 Optional: Use ML-based Semantic Quality Validation</b></summary>

For advanced use cases, you can add ML-based semantic similarity checking to validate that responses align with queries.

**Step 1:** Install the optional ML package:

```bash
pip install cascadeflow[ml]  # Adds semantic similarity via FastEmbed (~80MB model)
```

**Step 2:** Use semantic quality validation:

```python
from cascadeflow.quality.semantic import SemanticQualityChecker

# Initialize semantic checker (downloads model on first use)
checker = SemanticQualityChecker(
    similarity_threshold=0.5,  # Minimum similarity score (0-1)
    toxicity_threshold=0.7     # Maximum toxicity score (0-1)
)

# Validate query-response alignment
query = "Explain Python decorators"
response = "Decorators are a way to modify functions using @syntax..."

result = checker.validate(query, response, check_toxicity=True)

print(f"Similarity: {result.similarity:.2%}")
print(f"Passed: {result.passed}")
print(f"Toxic: {result.is_toxic}")
```

**What you get:**
- 🎯 Semantic similarity scoring (query ↔ response alignment)
- 🛡️ Optional toxicity detection
- 🔄 Automatic model download and caching
- 🚀 Fast inference (~100ms per check)

**Full example:** See [semantic_quality_domain_detection.py](./examples/semantic_quality_domain_detection.py)

</details>

> **⚠️ GPT-5 Note:** GPT-5 streaming requires organization verification. Non-streaming works for all users. [Verify here](https://platform.openai.com/settings/organization/general) if needed (~15 min). Basic cascadeflow examples work without - GPT-5 is only called when needed (typically 20-30% of requests).

📖 **Learn more:** [Python Documentation](./docs/README.md) | [Quickstart Guide](./docs/guides/quickstart.md) | [Providers Guide](./docs/guides/providers.md)

### <img src=".github/assets/CF_ts_color.svg" width="24" height="24" alt="TypeScript"/> TypeScript

```bash
npm install @cascadeflow/core
```

```tsx
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

// Same API as Python!
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.000375 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
});

const result = await agent.run('What is TypeScript?');
console.log(`Model: ${result.modelUsed}`);
console.log(`Cost: $${result.totalCost}`);
console.log(`Saved: ${result.savingsPercentage}%`);
```

<details>
<summary><b>💡 Optional: ML-based Semantic Quality Validation</b></summary>

For advanced quality validation, enable ML-based semantic similarity checking to ensure responses align with queries.

**Step 1:** Install the optional ML packages:

```bash
npm install @cascadeflow/ml @xenova/transformers
```

**Step 2:** Enable semantic validation in your cascade:

```tsx
import { CascadeAgent, SemanticQualityChecker } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.000375 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
  quality: {
    threshold: 0.40,                    // Traditional confidence threshold
    requireMinimumTokens: 5,            // Minimum response length
    useSemanticValidation: true,        // Enable ML validation
    semanticThreshold: 0.5,             // 50% minimum similarity
  },
});

// Responses now validated for semantic alignment
const result = await agent.run('Explain TypeScript generics');
```

**Step 3:** Or use semantic validation directly:

```tsx
import { SemanticQualityChecker } from '@cascadeflow/core';

const checker = new SemanticQualityChecker();

if (await checker.isAvailable()) {
  const result = await checker.checkSimilarity(
    'What is TypeScript?',
    'TypeScript is a typed superset of JavaScript.'
  );

  console.log(`Similarity: ${(result.similarity * 100).toFixed(1)}%`);
  console.log(`Passed: ${result.passed}`);
}
```

**What you get:**
- 🎯 Query-response semantic alignment detection
- 🚫 Off-topic response filtering
- 📦 BGE-small-en-v1.5 embeddings (~40MB, auto-downloads)
- ⚡ Fast CPU inference (~50-100ms with caching)
- 🔄 Request-scoped caching (50% latency reduction)
- 🌐 Works in Node.js, Browser, and Edge Functions

**Example:** [semantic-quality.ts](./packages/core/examples/nodejs/semantic-quality.ts)

</details>

📖 **Learn more:** [TypeScript Documentation](./packages/core/) | [Quickstart Guide](./docs/guides/quickstart-typescript.md) | [Node.js Examples](./packages/core/examples/nodejs/) | [Browser/Edge Guide](./docs/guides/browser_cascading.md)

### 🔄 Migration Example

**Migrate in 5min from direct Provider implementation to cost savings and full cost control and transparency.**

#### Before (Standard Approach)

Cost: $0.000113, Latency: 850ms

```python
# Using expensive model for everything
result = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's 2+2?"}]
)
```

#### After (With cascadeflow)

Cost: $0.000007, Latency: 234ms

```python
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
])

result = await agent.run("What's 2+2?")
```

> **🔥 Saved:** $0.000106 (94% reduction), 3.6x faster

📊 **Learn more:** [Cost Tracking Guide](./docs/guides/cost_tracking.md) | [Production Best Practices](./docs/guides/production.md) | [Performance Optimization](./docs/guides/performance.md)

---

## <img src=".github/assets/CF_n8n_color.svg" width="24" height="24" alt="n8n"/> n8n Integration

Use cascadeflow in n8n workflows for no-code AI automation with automatic cost optimization!

### Installation

1. Open n8n
2. Go to **Settings** → **Community Nodes**
3. Search for: `@cascadeflow/n8n-nodes-cascadeflow`
4. Click **Install**

### Quick Example

Create a workflow:

```
Manual Trigger → cascadeflow Node → Set Node

```

Configure cascadeflow node:

- **Draft Model**: `gpt-4o-mini` ($0.000375)
- **Verifier Model**: `gpt-4o` ($0.00625)
- **Message**: Your prompt
- **Output**: Full Metrics

**Result:** 40-85% cost savings in your n8n workflows!

**Features:**

- ✅ Visual workflow integration
- ✅ Multi-provider support
- ✅ Cost tracking in workflow
- ✅ Tool calling support
- ✅ Easy debugging with metrics

🔌 **Learn more:** [n8n Integration Guide](./packages/integrations/n8n/) | [n8n Documentation](./docs/guides/n8n_integration.md)

---

## Resources

### Examples

**<img src=".github/assets/CF_python_color.svg" width="20" height="20" alt="Python" style="vertical-align: middle;"/> Python Examples:**

<details open>
<summary><b>Basic Examples</b> - Get started quickly</summary>

| Example | Description | Link |
|---------|-------------|------|
| **Basic Usage** | Simple cascade setup with OpenAI models | [View](./examples/basic_usage.py) |
| **Preset Usage** | Use built-in presets for quick setup | [View](./docs/guides/presets.md) |
| **Multi-Provider** | Mix multiple AI providers in one cascade | [View](./examples/multi_provider.py) |
| **Reasoning Models**  | Use reasoning models (o1/o3, Claude 3.7, DeepSeek-R1) | [View](./examples/reasoning_models.py) |
| **Tool Execution** | Function calling and tool usage | [View](./examples/tool_execution.py) |
| **Streaming Text** | Stream responses from cascade agents | [View](./examples/streaming_text.py) |
| **Cost Tracking** | Track and analyze costs across queries | [View](./examples/cost_tracking.py) |

</details>

<details>
<summary><b>Advanced Examples</b> - Production & customization</summary>

| Example | Description | Link |
|---------|-------------|------|
| **Production Patterns** | Best practices for production deployments | [View](./examples/production_patterns.py) |
| **FastAPI Integration** | Integrate cascades with FastAPI | [View](./examples/fastapi_integration.py) |
| **Streaming Tools** | Stream tool calls and responses | [View](./examples/streaming_tools.py) |
| **Batch Processing** | Process multiple queries efficiently | [View](./examples/batch_processing.py) |
| **Multi-Step Cascade** | Build complex multi-step cascades | [View](./examples/multi_step_cascade.py) |
| **Edge Device** | Run cascades on edge devices with local models | [View](./examples/edge_device.py) |
| **Ollama Cascade** | Ollama local draft + cloud verifier cascade | [View](./examples/ollama_cascade.py) |
| **vLLM Cascade** | vLLM local draft + cloud verifier cascade | [View](./examples/vllm_cascade.py) |
| **Multi-Instance Ollama** | Run draft/verifier on separate Ollama instances | [View](./examples/multi_instance_ollama.py) |
| **Multi-Instance vLLM** | Run draft/verifier on separate vLLM instances | [View](./examples/multi_instance_vllm.py) |
| **Custom Cascade** | Build custom cascade strategies | [View](./examples/custom_cascade.py) |
| **Custom Validation** | Implement custom quality validators | [View](./examples/custom_validation.py) |
| **User Budget Tracking** | Per-user budget enforcement and tracking | [View](./examples/user_budget_tracking.py) |
| **User Profile Usage** | User-specific routing and configurations | [View](./examples/user_profile_usage.py) |
| **Rate Limiting** | Implement rate limiting for cascades | [View](./examples/rate_limiting_usage.py) |
| **Guardrails** | Add safety and content guardrails | [View](./examples/guardrails_usage.py) |
| **Cost Forecasting** | Forecast costs and detect anomalies | [View](./examples/cost_forecasting_anomaly_detection.py) |
| **Semantic Quality Detection** | ML-based domain and quality detection | [View](./examples/semantic_quality_domain_detection.py) |
| **Profile Database Integration** | Integrate user profiles with databases | [View](./examples/profile_database_integration.py) |

</details>

**<img src=".github/assets/CF_ts_color.svg" width="20" height="20" alt="TypeScript" style="vertical-align: middle;"/> TypeScript Examples:**

<details open>
<summary><b>Basic Examples</b> - Get started quickly</summary>

| Example | Description | Link |
|---------|-------------|------|
| **Basic Usage** | Simple cascade setup (Node.js) | [View](./packages/core/examples/nodejs/basic-usage.ts) |
| **Tool Calling** | Function calling with tools (Node.js) | [View](./packages/core/examples/nodejs/tool-calling.ts) |
| **Multi-Provider** | Mix providers in TypeScript (Node.js) | [View](./packages/core/examples/nodejs/multi-provider.ts) |
| **Reasoning Models**  | Use reasoning models (o1/o3, Claude 3.7, DeepSeek-R1) | [View](./packages/core/examples/nodejs/reasoning-models.ts) |
| **Cost Tracking** | Track and analyze costs across queries | [View](./packages/core/examples/nodejs/cost-tracking.ts) |
| **Semantic Quality**  | ML-based semantic validation with embeddings | [View](./packages/core/examples/nodejs/semantic-quality.ts) |
| **Streaming** | Stream responses in TypeScript | [View](./packages/core/examples/streaming.ts) |

</details>

<details>
<summary><b>Advanced Examples</b> - Production & edge deployment</summary>

| Example | Description | Link |
|---------|-------------|------|
| **Production Patterns** | Production best practices (Node.js) | [View](./packages/core/examples/nodejs/production-patterns.ts) |
| **Ollama Cascade** | Ollama local draft + cloud verifier cascade | [View](./packages/core/examples/nodejs/ollama-cascade.ts) |
| **vLLM Cascade** | vLLM local draft + cloud verifier cascade | [View](./packages/core/examples/nodejs/vllm-cascade.ts) |
| **Multi-Instance Ollama** | Run draft/verifier on separate Ollama instances | [View](./packages/core/examples/nodejs/multi-instance-ollama.ts) |
| **Multi-Instance vLLM** | Run draft/verifier on separate vLLM instances | [View](./packages/core/examples/nodejs/multi-instance-vllm.ts) |
| **Browser/Edge** | Vercel Edge runtime example | [View](./packages/core/examples/browser/vercel-edge/) |

</details>

📂 **[View All Python Examples →](./examples/)** | **[View All TypeScript Examples →](./packages/core/examples/)**

### Documentation

<details open>
<summary><b>Getting Started</b> - Core concepts and basics</summary>

| Guide | Description | Link |
|-------|-------------|------|
| **Quickstart** | Get started with cascadeflow in 5 minutes | [Read](./docs/guides/quickstart.md) |
| **Providers Guide** | Configure and use different AI providers | [Read](./docs/guides/providers.md) |
| **Presets Guide** | Using and creating custom presets | [Read](./docs/guides/presets.md) |
| **Streaming Guide** | Stream responses from cascade agents | [Read](./docs/guides/streaming.md) |
| **Tools Guide** | Function calling and tool usage | [Read](./docs/guides/tools.md) |
| **Cost Tracking** | Track and analyze API costs | [Read](./docs/guides/cost_tracking.md) |

</details>

<details>
<summary><b>Advanced Topics</b> - Production, customization & integrations</summary>

| Guide | Description | Link |
|-------|-------------|------|
| **Production Guide** | Best practices for production deployments | [Read](./docs/guides/production.md) |
| **Performance Guide** | Optimize cascade performance and latency | [Read](./docs/guides/performance.md) |
| **Custom Cascade** | Build custom cascade strategies | [Read](./docs/guides/custom_cascade.md) |
| **Custom Validation** | Implement custom quality validators | [Read](./docs/guides/custom_validation.md) |
| **Edge Device** | Deploy cascades on edge devices | [Read](./docs/guides/edge_device.md) |
| **Browser Cascading** | Run cascades in the browser/edge | [Read](./docs/guides/browser_cascading.md) |
| **FastAPI Integration** | Integrate with FastAPI applications | [Read](./docs/guides/fastapi.md) |
| **n8n Integration** | Use cascadeflow in n8n workflows | [Read](./docs/guides/n8n_integration.md) |

</details>

📚 **[View All Documentation →](./docs/)**

---

## Features

| **Feature** | **Benefit**                                                                                                                            |
| --- |----------------------------------------------------------------------------------------------------------------------------------------|
| 🎯 **Speculative Cascading** | Tries cheap models first, escalates intelligently                                                                                      |
| 💰 **40-85% Cost Savings** | Research-backed, proven in production                                                                                                  |
| ⚡ **2-10x Faster** | Small models respond in <50ms vs 500-2000ms                                                                                            |
| ⚡ **Low Latency**  | Sub-2ms framework overhead, negligible performance impact                                                                              |
| 🔄 **Mix Any Providers**  | OpenAI, Anthropic, Groq, Ollama, vLLM, Together + LiteLLM (optional)                                                                   |
| 👤 **User Profile System**  | Per-user budgets, tier-aware routing, enforcement callbacks                                                                            |
| ✅ **Quality Validation**  | Automatic checks + semantic similarity (optional ML, ~80MB, CPU)                                                                       |
| 🎨 **Cascading Policies**  | Domain-specific pipelines, multi-step validation strategies                                                                            |
| 🧠 **Domain Understanding**  | Auto-detects code/medical/legal/math/structured data, routes to specialists                                                            |
| 🤖 **Drafter/Validator Pattern** | 20-60% savings for agent/tool systems                                                                                                  |
| 🔧 **Tool Calling Support**  | Universal format, works across all providers                                                                                           |
| 📊 **Cost Tracking**  | Built-in analytics + OpenTelemetry export (vendor-neutral)                                                                             |
| 🚀 **3-Line Integration** | Zero architecture changes needed                                                                                                       |
| 🏭 **Production Ready**  | Streaming, batch processing, tool handling, reasoning model support, caching, error recovery, anomaly detection |

---

## License

MIT ©  see [LICENSE](https://github.com/lemony-ai/cascadeflow/blob/main/LICENSE) file.

Free for commercial use. Attribution appreciated but not required.

---

## Contributing

We ❤️ contributions!

📝 [**Contributing Guide**](./CONTRIBUTING.md) - Python & TypeScript development setup

---

## Roadmap

- **Cascade Profiler** - Analyzes your AI API logs to calculate cost savings potential and generate optimized cascadeflow configurations automatically
- **User Tier Management** - Cost controls and limits per user tier with advanced routing
- **Semantic Quality Validators** - Optional lightweight local quality scoring (200MB CPU model, no external API calls)
- **Code Complexity Detection** - Dynamic cascading based on task complexity analysis
- **Domain Aware Cascading** - Multi-stage pipelines tailored to specific domains
- **Benchmark Reports** - Automated performance and cost benchmarking

---

## Support

- 📖 [**GitHub Discussions**](https://github.com/lemony-ai/cascadeflow/discussions) - Searchable Q&A
- 🐛 [**GitHub Issues**](https://github.com/lemony-ai/cascadeflow/issues) - Bug reports & feature requests
- 📧 [**Email Support**](mailto:hello@lemony.ai) - Direct support

---

## Citation

If you use cascadeflow in your research or project, please cite:

```bibtex
@software{cascadeflow2025,
  author = {Lemony Inc., Sascha Buehrle and Contributors},
  title = {cascadeflow: Smart AI model cascading for cost optimization},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/lemony-ai/cascadeflow}
}
```

**Ready to cut your AI costs by 40-85%?**

```bash
pip install cascadeflow
```

```bash
npm install @cascadeflow/core
```

[Read the Docs](./docs/) • [View Python Examples](./examples/) • [View TypeScript Examples](./packages/core/examples/) • [Join Discussions](https://github.com/lemony-ai/cascadeflow/discussions)

---

## About

**Built with ❤️ by [Lemony Inc.](https://lemony.ai/) and the cascadeflow Community**

One cascade. Hundreds of specialists.

New York | Zurich

**⭐ Star us on GitHub if cascadeflow helps you save money!**
