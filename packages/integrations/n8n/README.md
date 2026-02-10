<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../../.github/assets/CF_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset="../../../.github/assets/CF_logo_dark.svg">
  <img alt="cascadeflow Logo" src="../../../.github/assets/CF_logo_dark.svg" width="80%" style="margin: 20px auto;">
</picture>

# @cascadeflow/n8n-nodes-cascadeflow

[![npm version](https://img.shields.io/npm/v/@cascadeflow/n8n-nodes-cascadeflow?color=red&label=npm)](https://www.npmjs.com/package/@cascadeflow/n8n-nodes-cascadeflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![n8n](https://img.shields.io/badge/n8n-1.0+-orange.svg)](https://n8n.io/)

**<img src="../../../.github/assets/CF_n8n_color.svg" width="22" height="22" alt="n8n" style="vertical-align: middle;"/> n8n community node for cascadeflow**

</div>

**Intelligent AI model cascading for n8n workflows with domain understanding.**

![cascadeflow Domain Routing](../../../.github/assets/n8n-CF-domains.jpg)

This is an n8n community node that brings cascadeflow's intelligent AI model cascading to n8n workflows.

**cascadeflow** reduces LLM API costs by 40-85% by trying a cheap model first, validating quality, and only escalating to expensive models when needed.

[n8n](https://n8n.io/) is a fair-code licensed workflow automation platform.

## How It Works

The cascadeflow node is a **Language Model sub-node** that sits between your AI models and downstream n8n nodes (like Basic LLM Chain, Chain, or any node that accepts Language Model inputs):

![cascadeflow n8n Workflow](../../../.github/assets/n8n-CF.png)

**Architecture:**

```
┌─────────────┐
│  Drafter    │ (e.g., Claude Haiku, GPT-4o-mini)
│  AI Model   │
└──────┬──────┘
       │
       ├──────► ┌──────────────┐
       │        │  cascadeflow │
       │        │     Node     │ ────► ┌──────────────┐
       │        └──────────────┘       │ Basic Chain  │
       ├──────► Quality checks         │ Chain        │
       │        Cascades if needed     │ & more       │
       │                                └──────────────┘
┌──────┴──────┐
│  Verifier   │ (e.g., Claude Sonnet, GPT-4o)
│  AI Model   │
└─────────────┘
```

**Flow:**
1. Query goes to cheap drafter model first
2. cascadeflow validates the response quality
3. If quality passes → return drafter response (fast + cheap ✅)
4. If quality fails → escalate to verifier model (slower but accurate ⚠️)

**Result:** 70-80% of queries accept the drafter, saving 40-85% on costs.

> **ℹ️ Note:** Use **CascadeFlow (Model)** with n8n Chain/LLM nodes, and **CascadeFlow Agent** for agent workflows (tool calling + multi-step). The Agent node adds trace metadata and supports tool routing.

## Installation

Follow the [installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) in the n8n community nodes documentation.

### Community Nodes (Recommended)

1. Go to **Settings** > **Community Nodes**
2. Select **Install**
3. Enter `@cascadeflow/n8n-nodes-cascadeflow` in **Enter npm package name**
4. Agree to the risks and install

### Manual installation

To get started install the package in your n8n root directory:

```bash
npm install @cascadeflow/n8n-nodes-cascadeflow
```

For Docker-based deployments add the following line before the font installation command in your [n8n Dockerfile](https://github.com/n8n-io/n8n/blob/master/docker/images/n8n/Dockerfile):

```dockerfile
RUN cd /usr/local/lib/node_modules/n8n && npm install @cascadeflow/n8n-nodes-cascadeflow
```

## Quick Start

### Basic Setup

1. **Add two AI Chat Model nodes** (e.g., OpenAI Chat Model, Anthropic Chat Model, Ollama Chat Model)
   - Configure one as your **drafter** (cheap model like `gpt-4o-mini` or `claude-3-5-haiku-20241022`)
   - Configure one as your **verifier** (powerful model like `gpt-4o` or `claude-3-5-sonnet-20241022`)

2. **Add the cascadeflow node**
   - Connect the drafter model to the **Drafter** input
   - Connect the verifier model to the **Verifier** input
   - Optionally adjust the **Quality Threshold** (default: 0.4, and per-complexity thresholds are enabled by default)

3. **Connect to a Chain node**
   - The cascadeflow node outputs a Language Model connection
   - Connect it to nodes that accept AI models (Basic LLM Chain, Chain, etc.)
   - For agent workflows, use the **CascadeFlow Agent** node (connect tools to its `Tools` input).

### Example Workflow

```
┌──────────────────┐
│ When chat        │
│ message received │
└────────┬─────────┘
         │
         v
┌──────────────────┐       ┌──────────────────┐
│  OpenAI Model    │──────►│                  │
│  gpt-4o-mini     │       │  cascadeflow     │       ┌──────────────────┐
└──────────────────┘       │  Node            │──────►│ Basic LLM Chain  │
                           │                  │       │                  │
┌──────────────────┐       │  Threshold: 0.4  │       └──────────────────┘
│  OpenAI Model    │──────►│                  │
│  gpt-4o          │       └──────────────────┘
└──────────────────┘
```

## Configuration

### Node Parameters

#### Quality Threshold (0-1)

Controls how aggressively to accept drafter responses when **Use Complexity Thresholds** is disabled.

Defaults to **0.4** to match the `simple` tier in CascadeFlow's default per-complexity thresholds.

If you enable **Use Complexity Thresholds** (default), acceptance is driven by:
- trivial: 0.25
- simple: 0.4
- moderate: 0.55
- hard: 0.7
- expert: 0.8

Lower threshold = more cost savings, higher threshold = better quality assurance.

## Multi-Domain Cascading (Optional)

cascadeflow supports **intelligent domain-specific cascading** - automatically detecting the type of query and routing it to a specialized model for that domain.

### How It Works

1. **Enable Domain Cascading** in the node settings
2. **Toggle individual domains** you want to support
3. **Connect domain-specific models** to the new input ports that appear

When a query comes in, cascadeflow:
1. Detects the domain (e.g., "Write a Python function" → Code domain)
2. Routes to the specialized model for that domain (if connected)
3. Falls back to drafter → verifier cascade if no domain model is available

### Supported Domains

| Domain | Description | Example Queries |
|--------|-------------|-----------------|
| **Code** | Programming, debugging, code generation | "Write a Python function...", "Debug this code..." |
| **Math** | Mathematical reasoning, calculations, proofs | "Solve this equation...", "Prove that..." |
| **Data** | Data analysis, statistics, pandas/SQL | "Analyze this dataset...", "Write a SQL query..." |
| **Creative** | Creative writing, stories, poetry | "Write a short story...", "Compose a poem..." |
| **Legal** | Legal documents, contracts, regulations | "Draft a contract...", "Explain this law..." |
| **Medical** | Healthcare, medical knowledge, clinical | "What are the symptoms of...", "Explain this diagnosis..." |
| **Financial** | Finance, accounting, investment analysis | "Analyze this stock...", "Calculate ROI..." |
| **Science** | Scientific knowledge, research, experiments | "Explain quantum...", "How does photosynthesis..." |

### Setup Example

```
┌──────────────────┐
│  Claude Haiku    │──► Drafter (default cheap model)
└──────────────────┘
┌──────────────────┐
│  GPT-4o          │──► Verifier (default powerful model)
└──────────────────┘
┌──────────────────┐         ┌──────────────────┐
│  DeepSeek Coder  │──► Code │                  │
└──────────────────┘         │                  │
┌──────────────────┐         │   cascadeflow    │──► Chain
│  Qwen Math       │──► Math │      Node        │
└──────────────────┘         │                  │
┌──────────────────┐         │                  │
│  Claude Sonnet   │──► Legal│                  │
└──────────────────┘         └──────────────────┘
```

### When to Use Domain Cascading

- **Use it when**: You have domain-specific models that excel in certain areas (e.g., DeepSeek for code, specialized medical models)
- **Skip it when**: Your drafter/verifier combination handles all domains well enough

## Flow Visualization

### Viewing Cascade Decisions in Real-Time

cascadeflow provides detailed logging of every cascade decision in n8n's UI:

1. **Execute your workflow** with the cascadeflow node
2. **Click on the downstream Chain node** after execution (the node that receives cascadeflow output)
3. **Navigate to the "Logs" tab**

You'll see detailed flow information like:

```
🎯 cascadeflow: Trying drafter model...
   📊 Quality validation: confidence=0.85, method=heuristic
   🎯 Alignment: 0.82

┌─────────────────────────────────────────┐
│  ✅ FLOW: DRAFTER ACCEPTED (FAST PATH) │
└─────────────────────────────────────────┘
   Query → Drafter → Quality Check ✅ → Response
   ⚡ Fast & Cheap: Used drafter model only
   Confidence: 0.85 (threshold: 0.70)
   Quality score: 0.85
   Latency: 420ms
   💰 Cost savings: ~93.8% (used cheap model)
   📊 Stats: 7 drafter, 2 verifier
```

Or when escalating:

```
🎯 cascadeflow: Trying drafter model...
   📊 Quality validation: confidence=0.62, method=heuristic

┌────────────────────────────────────────────────┐
│  ⚠️  FLOW: ESCALATED TO VERIFIER (SLOW PATH)  │
└────────────────────────────────────────────────┘
   Query → Drafter → Quality Check ❌ → Verifier → Response
   🔄 Escalating: Drafter quality too low, using verifier
   Confidence: 0.62 < 0.70 (threshold)
   Reason: Simple check failed (confidence: 0.62 < 0.70)
   Drafter latency: 380ms
   🔄 Loading verifier model...
   ✅ Verifier completed successfully
   Verifier latency: 890ms
   Total latency: 1270ms (drafter: 380ms + verifier: 890ms)
   💰 Cost: Full verifier cost (0% savings this request)
   📊 Stats: 7 drafter (77.8%), 2 verifier
```

### What the Logs Show

- **Flow path taken**: Drafter accepted, escalated to verifier, or error fallback
- **Quality scores**: Confidence level and alignment scores
- **Latency breakdown**: Time spent on each model
- **Cost analysis**: Savings percentage for each request
- **Running statistics**: Acceptance rate across all requests

## Recommended Model Configurations

### ⭐ Best Overall: Claude Haiku + GPT-4o (Recommended)

```
Drafter: claude-3-5-haiku-20241022
Verifier: gpt-4o
Savings: ~73% average
Why: Haiku's fast, high-quality drafts + GPT-4o's reasoning
Use for: General purpose, coding, reasoning, complex queries
```

### Anthropic Only (High Quality)

```
Drafter: claude-3-5-haiku-20241022
Verifier: claude-3-5-sonnet-20241022
Savings: ~70% average
Why: Consistent Anthropic experience, excellent quality
```

### OpenAI Only (Good Balance)

```
Drafter: gpt-4o-mini
Verifier: gpt-4o
Savings: ~85% average
Why: Both models from same provider, great cost efficiency
```

### Ultra Fast with Ollama (Local)

```
Drafter: ollama/qwen2.5:3b (local)
Verifier: gpt-4o (cloud)
Savings: ~99% on drafter calls (no API cost)
Why: Local model for drafts, cloud for verification
Note: Requires Ollama installed locally
```

## Cost Savings Examples

**Example: Claude Haiku + GPT-4o**

| Scenario | Traditional (GPT-4o only) | cascadeflow (Haiku + GPT-4o) | Savings |
|----------|---------------------------|------------------------------|---------|
| Simple Q&A (75% acceptance) | $0.0025 | $0.0008 | 68% |
| Complex query (25% escalation) | $0.0025 | $0.0025 | 0% (correctly escalated) |
| **Average** | **$0.0025** | **$0.00115** | **54%** |

**Monthly savings (10,000 queries):**
- Traditional (GPT-4o only): $25.00
- cascadeflow (Haiku + GPT-4o): $11.50
- **You save: $13.50/month** (54% savings)

**Monthly savings (100,000 queries):**
- Traditional (GPT-4o only): $250.00
- cascadeflow (Haiku + GPT-4o): $115.00
- **You save: $135.00/month** (54% savings)

## Example Workflows

### Customer Support Bot

```
┌──────────────────┐
│ Webhook          │ ← Customer question
│ (POST /support)  │
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────┐
│  Claude Haiku ────┐                 │
│                   │  cascadeflow    │       ┌──────────────────┐
│  Claude Sonnet ───┴─► Node          │──────►│  Basic Chain     │
└─────────────────────────────────────┘       │  (responds)      │
                                               └──────┬───────────┘
                                                      │
                                                      v
                                               ┌──────────────────┐
                                               │  Send Response   │
                                               └──────────────────┘
```

### Content Generation

```
┌──────────────────┐
│ Schedule Trigger │ ← Daily at 9am
│ (Daily)          │
└────────┬─────────┘
         │
         v
┌────────────────────────────────────────┐
│  GPT-4o-mini ─────┐                    │
│                   │  cascadeflow       │       ┌──────────────────┐
│  GPT-4o ──────────┴─► Node             │──────►│  Basic Chain     │
└────────────────────────────────────────┘       │  (generates)     │
                                                  └──────┬───────────┘
                                                         │
                                                         v
                                                  ┌──────────────────┐
                                                  │  Save to Notion  │
                                                  └──────────────────┘
```

### Code Review Assistant

```
┌──────────────────┐
│ GitHub Trigger   │ ← New PR
│ (PR opened)      │
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────┐
│  Ollama qwen2.5 ──┐                 │
│                   │  cascadeflow    │       ┌──────────────────┐
│  GPT-4o ──────────┴─► Node          │──────►│  Basic Chain     │
└─────────────────────────────────────┘       │  (reviews code)  │
                                               └──────┬───────────┘
                                                      │
                                                      v
                                               ┌──────────────────┐
                                               │  Post Comment    │
                                               └──────────────────┘
```

## UI Visualization Note

⚠️ **Important:** Due to n8n's rendering conventions, the node visualization always highlights the **Drafter** connection as active (green), regardless of which model was actually used at runtime. This is because n8n highlights the first input in a sub-node's definition.

**This does not affect functionality** - the cascade logic works correctly. The drafter is always tried first, and the verifier is only loaded when needed.

**To see the actual cascade flow and which model was used:**

1. Execute your workflow
2. Click on the downstream Chain node after execution (the node that receives cascadeflow output)
3. Navigate to the **"Logs"** tab
4. You'll see detailed flow information showing:
   - Whether the drafter was accepted or escalated to verifier
   - Quality confidence scores and validation methods
   - Latency breakdown for each model
   - Cost savings percentage
   - Running statistics across all executions

The logs provide complete visibility into the cascade decision-making process, showing exactly which path was taken for each request.

> **ℹ️ Important:** If you need agent-style tool orchestration, use the **CascadeFlow Agent** node. It is designed for n8n agent flows and records a step-by-step trace in `response_metadata.cf.trace`.

## Compatibility

- **n8n version**: 1.0+
- **Works with any AI Chat Model node** in n8n:
  - OpenAI Chat Model
  - Anthropic Chat Model
  - Ollama Chat Model
  - Azure OpenAI Chat Model
  - Google PaLM Chat Model
  - And more...

## Troubleshooting

### Issue: "Drafter model is required"

**Solution:** Make sure you've connected an AI Chat Model to the **Drafter** input (second input, bottom position).

### Issue: "Verifier model is required"

**Solution:** Make sure you've connected an AI Chat Model to the **Verifier** input (first input, top position).

### Issue: Not seeing cascade logs

**Solution:**
1. Make sure your workflow has executed successfully
2. Click on the **Chain node that receives the cascadeflow output** (Basic LLM Chain, Chain, etc.)
3. Navigate to the **"Logs"** tab (not the "Output" tab)
4. The logs appear in the downstream node, not the cascadeflow node itself

### Issue: "This node cannot be connected" when connecting to AI Agent

**Solution:** Use the **CascadeFlow Agent** node for agent workflows. Use the **CascadeFlow (Model)** node for Chain/LLM workflows.
- ✅ Basic LLM Chain
- ✅ Chain
- ✅ Other nodes that accept Language Model connections
- ✅ CascadeFlow Agent (agent workflows)

### Issue: Always escalating to verifier

**Solution:**
1. Check your Quality Threshold setting (try lowering to 0.6-0.65)
2. Verify your drafter model is actually a cheaper/faster model
3. Check the logs to see the confidence scores being reported

## Resources

- [n8n community nodes documentation](https://docs.n8n.io/integrations/community-nodes/)
- [cascadeflow GitHub](https://github.com/lemony-ai/cascadeflow)
- [cascadeflow Documentation](https://github.com/lemony-ai/cascadeflow/blob/main/README.md)
- [Full n8n Integration Guide](https://github.com/lemony-ai/cascadeflow/blob/main/docs/guides/n8n_integration.md)

## License

[MIT](https://github.com/lemony-ai/cascadeflow/blob/main/LICENSE)

## Version History

### v0.6.7 (Latest)

- **Multi-domain cascading docs**: Added documentation for 8-domain intelligent cascading
- **Removed semantic validation**: Disabled ML-based semantic validation to prevent out-of-memory crashes
- **Shorter domain labels**: Domain input labels simplified (Code, Math, Data, etc.)

### v0.6.4

- **Individual domain toggles**: Replaced multi-select with individual boolean toggles for each domain
- **Dynamic input ports**: Domain model inputs appear dynamically as each domain is enabled

### v0.6.3

- **16-domain routing**: Support for intelligent routing across 16 specialized domains (code, math, data, creative, legal, medical, financial, science, and more)
- **Circuit breaker**: Added circuit breaker pattern for improved reliability
- **Domain-specific models**: Connect specialized models for different query types

### v0.5.0

- **Flow visualization in n8n Logs tab**: Detailed cascade flow logging with visual boxes
- **Real-time quality metrics**: Confidence scores, alignment scores, latency breakdown, and cost savings
- **Quality validator integration**: Integrated QualityValidator from @cascadeflow/core
- **Better cascade decisions**: Complexity-aware validation replacing naive length-based checks

### v0.4.x and earlier

- Initial releases as LangChain sub-node
- Support for any AI Chat Model in n8n
- Lazy verifier loading
- Quality threshold configuration
