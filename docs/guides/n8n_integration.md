# n8n Integration Guide

**Intelligent AI model cascading for n8n workflows with domain understanding.**

![cascadeflow Domain Routing](../../.github/assets/n8n-CF-domains.jpg)

This guide shows how to use cascadeflow in n8n workflows for intelligent AI model cascading with 40-85% cost savings.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Flow Visualization](#flow-visualization)
6. [Use Cases](#use-cases)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The **@cascadeflow/n8n-nodes-cascadeflow** package brings cascadeflow's intelligent model cascading to n8n workflows as a Language Model sub-node.

### What is Model Cascading?

Instead of always using expensive models:

```
Traditional: Every query → GPT-4o ($0.0025)
```

cascadeflow tries cheap models first:

```
cascadeflow:
  1. Try GPT-4o-mini ($0.00015) ← 70-80% stop here! ✅
  2. Validate quality automatically
  3. If needed → GPT-4o ($0.0025)

Result: 50-85% cost savings
```

### How It Works as a Sub-Node

cascadeflow is a **Language Model sub-node** that sits between your AI model nodes and downstream n8n nodes (like Basic LLM Chain, Chain, or any node that accepts Language Model inputs):

![cascadeflow n8n Workflow](../../.github/assets/n8n-CF.png)

**Architecture:**

```
┌─────────────┐
│  Drafter    │ (e.g., OpenAI gpt-4o-mini)
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
│  Verifier   │ (e.g., OpenAI gpt-4o)
│  AI Model   │
└─────────────┘
```

### Why Use cascadeflow in n8n?

✅ **Massive Cost Savings** - 40-85% cheaper than always using expensive models
✅ **Same Quality** - Automatic validation ensures quality
✅ **Easy Integration** - Works with any AI Chat Model in n8n
✅ **Rich Metrics** - Track cascade decisions in real-time via Logs
✅ **Flexible** - Use any combination of models from different providers
✅ **Universal** - Compatible with OpenAI, Anthropic, Ollama, Azure, Google, and more

> **ℹ️ Note:** Use **CascadeFlow (Model)** with n8n Chain/LLM nodes, and **CascadeFlow Agent** for agent workflows (tool calling + multi-step). The Agent node adds trace metadata and supports tool routing.

---

## Installation

### Method 1: Community Nodes (Recommended)

1. Open n8n
2. Go to **Settings** > **Community Nodes**
3. Click **Install**
4. Enter: `@cascadeflow/n8n-nodes-cascadeflow`
5. Click **Install**
6. Restart n8n

### Method 2: Manual Installation

```bash
# In your n8n directory
npm install @cascadeflow/n8n-nodes-cascadeflow
```

### Method 3: Docker

Add to your Dockerfile before font installation:

```dockerfile
RUN cd /usr/local/lib/node_modules/n8n && npm install @cascadeflow/n8n-nodes-cascadeflow
```

---

## Quick Start

### Step 1: Add Your AI Model Nodes

First, add and configure two AI Chat Model nodes in your workflow:

1. **Add a cheap model (Drafter)**:
   - Add an **OpenAI Chat Model** node
   - Configure with credentials
   - Set model: `gpt-4o-mini`
   - Don't connect to anything yet

2. **Add a powerful model (Verifier)**:
   - Add another **OpenAI Chat Model** node
   - Configure with credentials
   - Set model: `gpt-4o`
   - Don't connect to anything yet

### Step 2: Add cascadeflow Node

1. Search for cascadeflow in the node menu
2. Add it to your workflow
3. **Connect the models**:
   - Connect your cheap model (gpt-4o-mini) to the **Drafter** input (bottom)
   - Connect your powerful model (gpt-4o) to the **Verifier** input (top)
4. Set **Quality Threshold**: `0.7` (default)

### Step 3: Connect to a Chain Node

1. Add a **Basic LLM Chain** or **Chain** node
2. Connect the cascadeflow node to it (Model input)
3. Configure your chain as usual
4. For agent workflows, use the **CascadeFlow Agent** node (connect tools to its `Tools` input).

### Step 4: Execute and View Results

**Example Workflow:**

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

Click **Execute Workflow** and check the **Logs** tab to see the cascade decision!

---

## Configuration

### Node Inputs

The cascadeflow node has **two inputs** that accept AI Language Model connections:

| Input | Position | Purpose | Example |
|-------|----------|---------|---------|
| **Verifier** | Top (1st) | High-quality fallback model | gpt-4o, claude-3-5-sonnet |
| **Drafter** | Bottom (2nd) | Fast, cheap first-attempt model | gpt-4o-mini, claude-3-5-haiku |

**Important:** Both inputs are required. Connect AI Chat Model nodes to both inputs.

### Quality Threshold (0-1)

Controls how aggressively to accept drafter responses when **Use Complexity Thresholds** is disabled.

Defaults to **0.4** to match the `simple` tier in CascadeFlow's default per-complexity thresholds.

If you enable **Use Complexity Thresholds** (default), acceptance is driven by:
- trivial: 0.25
- simple: 0.4
- moderate: 0.55
- hard: 0.7
- expert: 0.8

Lower threshold = more cost savings, higher threshold = better quality assurance.

### Compatible AI Model Nodes

cascadeflow works with **any AI Chat Model node** in n8n:

- ✅ OpenAI Chat Model
- ✅ Anthropic Chat Model
- ✅ Ollama Chat Model
- ✅ Azure OpenAI Chat Model
- ✅ Google PaLM Chat Model
- ✅ AWS Bedrock Chat Model
- ✅ And any other LangChain-compatible chat model

You can even **mix providers**:
- Drafter: Ollama (local, free)
- Verifier: OpenAI (cloud, paid)

---

## Flow Visualization

### Viewing Cascade Decisions in Real-Time

cascadeflow provides detailed logging of every cascade decision directly in n8n's UI.

**To view cascade flow logs:**

1. **Execute your workflow** with the cascadeflow node
2. **Click on the downstream Chain node** (the node that receives the cascadeflow output, like Basic LLM Chain)
3. **Navigate to the "Logs" tab** (not the Output tab)

### What You'll See

#### When Drafter is Accepted (Fast Path)

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

#### When Escalated to Verifier (Slow Path)

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

### Metrics Shown in Logs

- **Flow path**: Drafter accepted, escalated, or error fallback
- **Quality scores**: Confidence level and alignment scores
- **Validation method**: Heuristic, logprobs, or semantic
- **Latency breakdown**: Time spent on each model
- **Cost analysis**: Savings percentage for each request
- **Running statistics**: Acceptance rate across all executions
- **Model used**: Which model generated the final response

### UI Visualization Note

⚠️ **Important:** Due to n8n's rendering conventions, the node visualization always highlights the **Drafter** connection as active (green), regardless of which model was actually used at runtime. This is because n8n highlights the first input in a sub-node's definition, and the Drafter is positioned first (bottom position, but first in the connection list).

**This does not affect functionality** - the cascade logic works correctly:
- The drafter is always tried first
- The verifier is only loaded and used when needed
- Quality validation happens automatically

**To see which model was actually used for each request:**
- Check the **Logs tab** as described above
- The logs show exactly which path was taken (drafter accepted vs. escalated to verifier)
- You'll see detailed metrics including which model generated the final response

The logs provide complete visibility into the cascade decision-making process, showing exactly which path was taken for each request.

> **ℹ️ Important:** If you need agent-style tool orchestration, use the **CascadeFlow Agent** node. It is designed for n8n agent flows and records a step-by-step trace in `response_metadata.cf.trace`.

---

## Use Cases

### Use Case 1: Customer Support Automation

**Workflow:**
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

**Why this works:**
- 70% of support queries are simple → drafter accepted
- 30% complex → automatically escalated
- Average savings: 60%

**Configuration:**
- Drafter: Claude 3.5 Haiku
- Verifier: Claude 3.5 Sonnet
- Quality Threshold (if complexity thresholds are disabled): 0.75

---

### Use Case 2: Content Generation Pipeline

**Workflow:**
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

**Why this works:**
- First draft uses cheap model
- Quality validation catches issues
- Only escalates for complex topics

**Savings:** $0.50 → $0.15 per article (70% savings)

---

### Use Case 3: Code Review Assistant

**Workflow:**
```
┌──────────────────┐
│ GitHub Trigger   │ ← New PR opened
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

**Why this works:**
- Ollama runs locally (free, fast drafts)
- GPT-4o for complex code analysis
- Process unlimited PRs with minimal cost

**Configuration:**
- Drafter: Ollama qwen2.5:3b (local, free)
- Verifier: GPT-4o (cloud)
- Quality Threshold (if complexity thresholds are disabled): 0.7
- Savings: ~99% on drafter calls

---

### Use Case 4: Data Enrichment

**Workflow:**
```
┌──────────────────┐
│ Google Sheets    │ ← Read contacts
│ (read rows)      │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ Loop Over Items  │
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────┐
│  GPT-4o-mini ─────┐                 │
│                   │  cascadeflow    │       ┌──────────────────┐
│  GPT-4o ──────────┴─► Node          │──────►│  Basic Chain     │
└─────────────────────────────────────┘       │  (enriches)      │
                                               └──────┬───────────┘
                                                      │
                                                      v
                                               ┌──────────────────┐
                                               │ Google Sheets    │
                                               │ (write back)     │
                                               └──────────────────┘
```

**Why this works:**
- Process 1000 contacts for $3 instead of $25
- Cheap model for simple enrichment
- Expensive model only when needed

---

## Best Practices

### 1. Choose the Right Model Combination

**For maximum savings:**
```
Drafter: Ollama qwen2.5:3b (local, free)
Verifier: GPT-4o (cloud)
Savings: ~99% on accepted drafts
```

**For best quality:**
```
Drafter: Claude 3.5 Haiku
Verifier: Claude 3.5 Sonnet
Savings: ~70% average
```

**For speed:**
```
Drafter: GPT-4o-mini
Verifier: GPT-4o
Savings: ~85% average
```

### 2. Tune Quality Threshold Based on Logs

Start with `0.7` and adjust based on what you see in the Logs:

1. Run 10-20 test queries
2. Check the Logs tab to see confidence scores
3. Adjust threshold:
   - **Too many escalations?** Lower threshold (0.6)
   - **Quality issues?** Raise threshold (0.8)
4. Monitor acceptance rate in the logs

### 3. Monitor Long-Term Performance

Track these metrics from the Logs:
- **Acceptance rate**: Should be 70-80%
- **Confidence scores**: Should cluster above your threshold
- **Latency**: Drafter should be <500ms
- **Cost savings**: Track per-request savings percentage

### 4. Mix Providers for Best Results

You can connect models from different providers:

```
┌──────────────────┐
│ Ollama Chat      │ ← Free, local
│ qwen2.5:3b       │
└────────┬─────────┘
         │
         ├──────► ┌──────────────┐
         │        │  cascadeflow │
         │        │     Node     │
         │        └──────────────┘
┌────────┴─────────┐
│ OpenAI Chat      │ ← Paid, cloud
│ gpt-4o           │
└──────────────────┘
```

### 5. Use Different Thresholds for Different Use Cases

If you disable **Use Complexity Thresholds**, you can tune **Quality Threshold** per workflow:
- **Customer support**: 0.75 (prioritize quality)
- **Content drafts**: 0.6 (prioritize speed/cost)
- **Code review**: 0.7 (balance)
- **Data enrichment**: 0.65 (volume optimization)

---

## Recommended Configurations

### ⭐ Best Overall: Claude Haiku + GPT-4o

```
Drafter: Claude 3.5 Haiku
Verifier: GPT-4o
Use Complexity Thresholds: enabled (default)
Expected Savings: ~73% average
Why: Haiku's fast drafts + GPT-4o's reasoning
```

### OpenAI Only (Good Balance)

```
Drafter: GPT-4o-mini
Verifier: GPT-4o
Use Complexity Thresholds: enabled (default)
Expected Savings: ~85% average
Why: Both from same provider, excellent efficiency
```

### Anthropic Only (High Quality)

```
Drafter: Claude 3.5 Haiku
Verifier: Claude 3.5 Sonnet
Quality Threshold: 0.75
Expected Savings: ~70% average
Why: Consistent Anthropic quality
```

### Ultra Cost-Effective (Ollama + Cloud)

```
Drafter: Ollama qwen2.5:3b (local, free)
Verifier: GPT-4o (cloud)
Use Complexity Thresholds: enabled (default)
Expected Savings: ~99% on accepted drafts
Note: Requires Ollama installed locally
```

---

## Troubleshooting

### Issue: "Drafter model is required"

**Solution:** Make sure you've connected an AI Chat Model to the **Drafter** input (bottom position).

### Issue: "Verifier model is required"

**Solution:** Make sure you've connected an AI Chat Model to the **Verifier** input (top position).

### Issue: Not seeing cascade logs

**Solution:**
1. Make sure your workflow executed successfully
2. Click on the **Chain node that receives the cascadeflow output** (Basic LLM Chain, Chain, etc.)
3. Navigate to the **"Logs"** tab (not the "Output" tab)
4. The logs appear in the downstream node, not in the cascadeflow node itself

### Issue: "This node cannot be connected" when connecting to AI Agent

**Solution:** Use the **CascadeFlow Agent** node for agent workflows. Use the **CascadeFlow (Model)** node for Chain/LLM workflows.
- ✅ Basic LLM Chain
- ✅ Chain
- ✅ Other nodes that accept Language Model connections
- ✅ CascadeFlow Agent (agent workflows)

### Issue: Always escalating to verifier

**Debug steps:**
1. Check the Logs tab to see confidence scores
2. If confidence scores are just below threshold, lower it slightly (e.g., 0.7 → 0.65)
3. Verify your drafter model is appropriate (not too weak)
4. Try a better drafter model (e.g., gpt-4o-mini instead of gpt-3.5-turbo)

### Issue: Verifier connection always shows green in UI

**This is expected behavior.** Due to n8n's rendering conventions, the Drafter connection is always highlighted. This does not affect functionality. Check the **Logs tab** to see which model was actually used for each request.

---

## Cost Savings Examples

### Example: Claude Haiku + GPT-4o

| Scenario | Traditional (GPT-4o only) | cascadeflow | Savings |
|----------|---------------------------|-------------|---------|
| Simple Q&A (75% acceptance) | $0.0025 | $0.0008 | 68% |
| Complex query (escalated) | $0.0025 | $0.0025 | 0% |
| **Average** | **$0.0025** | **$0.00115** | **54%** |

**Monthly savings (10,000 queries):**
- Traditional: $25.00
- cascadeflow: $11.50
- **You save: $13.50/month**

**Monthly savings (100,000 queries):**
- Traditional: $250.00
- cascadeflow: $115.00
- **You save: $135.00/month**

---

## Advanced Tips

### Tip 1: Chain Multiple cascadeflow Nodes

```
Input → cascadeflow (draft) → cascadeflow (review) → Output
```

Each stage benefits from cascading!

### Tip 2: Use Different Models for Different Stages

```
Stage 1 (Generate):
  Drafter: gpt-4o-mini
  Verifier: gpt-4o

Stage 2 (Review):
  Drafter: claude-haiku
  Verifier: claude-sonnet
```

### Tip 3: Combine with Caching

Some providers (like Anthropic) support prompt caching. Use cascadeflow with cached prompts for even more savings.

---

## Learn More

- [cascadeflow GitHub](https://github.com/lemony-ai/cascadeflow)
- [Package README](../../packages/integrations/n8n/README.md)
- [n8n Documentation](https://docs.n8n.io/)
- [n8n Community](https://community.n8n.io/)

---

**Next Steps:**
1. Install the node via Community Nodes
2. Try the Quick Start workflow
3. Check the Logs tab to see cascade decisions in action
4. Experiment with different model combinations
5. Share your workflows with the community!
