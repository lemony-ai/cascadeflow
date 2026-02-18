# n8n Integration Guide

**Intelligent AI model cascading for n8n workflows with domain understanding.**

![cascadeflow Domain Routing](../../.github/assets/n8n-CF-domains.jpg)

This guide shows how to use cascadeflow in n8n workflows for intelligent AI model cascading with 40-85% cost savings.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Node 1: CascadeFlow (Model)](#node-1-cascadeflow-model)
4. [Node 2: CascadeFlow Agent](#node-2-cascadeflow-agent)
5. [Shared Features](#shared-features)
6. [Flow Visualization](#flow-visualization)
7. [Use Cases](#use-cases)
8. [Recommended Configurations](#recommended-configurations)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The **@cascadeflow/n8n-nodes-cascadeflow** package provides **two nodes** for n8n workflows:

| Node | Type | Use case |
|------|------|----------|
| **CascadeFlow (Model)** | Language Model sub-node | Drop-in replacement for any AI Chat Model. Wire into Basic LLM Chain, Chain, or any node that accepts a Language Model. |
| **CascadeFlow Agent** | Standalone agent node | Full agent with tool calling, memory, and multi-step reasoning. Wire directly into workflows like Chat Trigger → Agent → response. |

Both nodes share the same cascade engine: try a cheap drafter first, validate quality, escalate to a verifier only when needed. **40-85% cost savings.**

### What is Model Cascading?

Instead of always using expensive models:

```
Traditional: Every query → GPT-4o ($0.0025)
```

cascadeflow tries cheap models first:

```
cascadeflow:
  1. Try GPT-4o-mini ($0.00015) ← 70-80% stop here!
  2. Validate quality automatically
  3. If needed → GPT-4o ($0.0025)

Result: 50-85% cost savings
```

[n8n](https://n8n.io/) is a fair-code licensed workflow automation platform.

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

## Node 1: CascadeFlow (Model)

A **Language Model sub-node** (`ai_languageModel` output) that acts as a drop-in cascading wrapper around two models.

### When to use

- You want to plug cascadeflow into an existing chain or LLM node
- No tool calling or memory needed
- Works with: Basic LLM Chain, Chain, Question and Answer Chain, Summarization Chain, and any node that accepts a Language Model input

### Architecture

```
┌─────────────┐
│  Drafter    │ (e.g., Claude Haiku, GPT-4o-mini)
└──────┬──────┘
       │
       ├──────► ┌──────────────┐
       │        │  CascadeFlow │
       │        │  (Model)     │ ────► ┌──────────────┐
       │        └──────────────┘       │ Basic Chain  │
       │        Quality checks         │ Chain        │
       │        Cascades if needed     │ & more       │
       │                                └──────────────┘
┌──────┴──────┐
│  Verifier   │ (e.g., Claude Sonnet, GPT-4o)
└─────────────┘
```

### Inputs

| Port | Type | Required | Description |
|------|------|----------|-------------|
| Verifier | `ai_languageModel` | Yes | Powerful model used when drafter quality is too low |
| Drafter | `ai_languageModel` | Yes | Cheap/fast model tried first |
| Domain models | `ai_languageModel` | No | Appear when domain cascading is enabled |

### Output

| Port | Type | Description |
|------|------|-------------|
| Model | `ai_languageModel` | Language Model connection for downstream chain/LLM nodes |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Quality Threshold | 0.4 | Minimum quality score (0-1) to accept drafter response |
| Use Complexity Thresholds | true | Per-complexity confidence thresholds (trivial→expert) |
| Enable Alignment Scoring | true | Score query-response alignment for better validation |
| Enable Complexity Routing | true | Route complex queries directly to verifier |
| Enable Domain Cascading | false | Detect query domain and route to specialized models |

### Quick Start

```
┌──────────────────┐
│ When chat        │
│ message received │
└────────┬─────────┘
         │
         v
┌──────────────────┐       ┌──────────────────┐
│  OpenAI Model    │──────►│                  │
│  gpt-4o-mini     │       │  CascadeFlow     │       ┌──────────────────┐
└──────────────────┘       │  (Model)         │──────►│ Basic LLM Chain  │
                           │                  │       │                  │
┌──────────────────┐       │  Threshold: 0.4  │       └──────────────────┘
│  OpenAI Model    │──────►│                  │
│  gpt-4o          │       └──────────────────┘
└──────────────────┘
```

1. Add two **AI Chat Model** nodes (cheap drafter + powerful verifier)
2. Add **CascadeFlow (Model)** node and connect both models
3. Connect cascadeflow to a **Basic LLM Chain** or **Chain** node
4. Check the **Logs tab** on the downstream Chain node to see cascade decisions

---

## Node 2: CascadeFlow Agent

A **standalone agent node** (`main` in/out) with its own agent loop, tool calling, memory, and per-tool cascade/verifier routing.

### When to use

- You need tool calling with cascade-aware routing
- You want memory (conversation history) built in
- You want to wire directly into a workflow (Chat Trigger → Agent → response)
- You need per-tool routing rules (force verifier after specific tools)
- You need tool call validation (drafter tool calls verified before execution)

### Architecture

```
┌──────────────────┐
│ Chat Trigger     │
│ or any node      │
└────────┬─────────┘
         │ (main)
         v
┌──────────────────────────────────────────┐
│            CascadeFlow Agent             │
│                                          │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐│
│  │ Verifier│  │ Drafter │  │ Memory   ││
│  └────┬────┘  └────┬────┘  └────┬─────┘│
│       │            │            │       │
│  ┌────┴────────────┴────┐       │       │
│  │  Cascade Engine      │◄──────┘       │
│  │  + Agent Loop        │               │
│  └──────────┬───────────┘               │
│             │                           │
│  ┌──────────┴───────────┐               │
│  │  Tools               │               │
│  └──────────────────────┘               │
└──────────────────┬───────────────────────┘
                   │ (main)
                   v
┌──────────────────┐
│ Next node        │
│ (response, etc.) │
└──────────────────┘
```

### Inputs

| Port | Type | Required | Description |
|------|------|----------|-------------|
| (main) | `main` | Yes | Workflow items from upstream node (e.g., Chat Trigger) |
| Verifier | `ai_languageModel` | Yes | Powerful model for verification and escalation |
| Drafter | `ai_languageModel` | Yes | Cheap/fast model tried first |
| Memory | `ai_memory` | No | Chat memory (e.g., Window Buffer Memory) for conversation history |
| Tools | `ai_tool` | No | Up to 99 tools for the agent to call |
| Domain models | `ai_languageModel` | No | Appear when domain cascading is enabled |

### Output

| Port | Type | Description |
|------|------|-------------|
| Output | `main` | Workflow items with `output`, cascade metadata, and `trace` |

The output JSON for each item contains:

```json
{
  "output": "The agent's final response text",
  "model_used": "gpt-4o-mini",
  "domain": "code",
  "confidence": 0.85,
  "trace": [
    { "model_used": "gpt-4o-mini", "tool_calls": ["search"] },
    { "model_used": "gpt-4o", "tool_calls": [] }
  ]
}
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| System Message | (empty) | System prompt for the agent |
| Text | `{{ $json.chatInput }}` | User input message. Auto-wires with Chat Trigger. |
| Quality Threshold | 0.4 | Minimum quality score to accept drafter response |
| Use Complexity Thresholds | true | Per-complexity confidence thresholds |
| Enable Tool Call Validation | true | Validate drafter tool calls before execution; re-generate with verifier on failure |
| Max Tool Iterations | 3 | Maximum tool-call loop iterations |
| Tool Routing Rules | (none) | Per-tool routing overrides (cascade or force verifier) |
| Enable Domain Cascading | false | Domain-specific model routing |

### Quick Start

```
┌──────────────────┐
│ Chat Trigger     │
└────────┬─────────┘
         │
         v
┌──────────────────────────────────────────┐
│            CascadeFlow Agent             │
│                                          │
│  Claude Haiku ──► Drafter                │
│  Claude Sonnet ─► Verifier               │       ┌──────────────────┐
│  Window Buffer ─► Memory                 │──────►│  Respond to      │
│  HTTP Request ──► Tool                   │       │  Webhook         │
│  Calculator ────► Tool                   │       └──────────────────┘
└──────────────────────────────────────────┘
```

1. Add a **Chat Trigger** node
2. Add **CascadeFlow Agent** and connect it to the Chat Trigger
3. Connect AI Chat Model nodes to the **Drafter** and **Verifier** inputs
4. Optionally connect **Memory** (e.g., Window Buffer Memory) and **Tools**
5. Connect the Agent output to your response node
6. Check the Agent **Output tab** for cascade metadata and trace

### Tool Routing Rules

Override cascade behavior for specific tools:

| Routing | Behavior |
|---------|----------|
| **Cascade** (default) | Drafter generates tool calls, cascade validates |
| **Verifier** | After this tool executes, the verifier generates the final response |

Use verifier routing for high-stakes tools (e.g., database writes, payment APIs) where you want the powerful model to interpret results.

### Tool Call Validation

When enabled (default), the agent validates drafter-generated tool calls before executing them:
- JSON syntax check
- Schema validation
- Safety checks

If validation fails, tool calls are re-generated by the verifier model, preventing malformed or unsafe tool invocations.

---

## Shared Features

Both nodes share these capabilities:

### Cascade Flow

1. Query goes to cheap drafter model first
2. cascadeflow validates the response quality
3. If quality passes → return drafter response (fast + cheap)
4. If quality fails → escalate to verifier model (slower but accurate)

**Result:** 70-80% of queries accept the drafter, saving 40-85% on costs.

### Complexity Thresholds

When enabled (default), acceptance is driven by query complexity:

| Complexity | Default Threshold |
|------------|-------------------|
| Trivial | 0.25 |
| Simple | 0.40 |
| Moderate | 0.55 |
| Hard | 0.70 |
| Expert | 0.80 |

### Multi-Domain Cascading (Optional)

Both nodes support domain-specific cascading. Enable it in the node settings to automatically detect query domains and route to specialized models.

**Supported domains:**

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
| **Structured** | JSON, XML, structured output | "Generate a JSON schema..." |
| **RAG** | Retrieval-augmented generation | "Based on the document..." |
| **Conversation** | General chat, small talk | "How are you?", "Tell me about..." |
| **Tool** | Tool-oriented queries | "Search for...", "Calculate..." |
| **Summary** | Summarization tasks | "Summarize this article..." |
| **Translation** | Language translation | "Translate to French..." |
| **Multimodal** | Image/audio/video queries | "Describe this image..." |
| **General** | Catch-all domain | Everything else |

**Setup:**
1. Enable Domain Cascading in node settings
2. Toggle individual domains
3. Connect domain-specific models to the new input ports
4. Optionally enable domain verifiers to override the global verifier per domain

### Compatible AI Model Nodes

cascadeflow works with **any AI Chat Model node** in n8n:

- OpenAI Chat Model
- Anthropic Chat Model
- Ollama Chat Model
- Azure OpenAI Chat Model
- Google PaLM Chat Model
- AWS Bedrock Chat Model
- And any other LangChain-compatible chat model

You can even **mix providers**:
- Drafter: Ollama (local, free)
- Verifier: OpenAI (cloud, paid)

---

## Flow Visualization

### CascadeFlow (Model): Viewing Cascade Decisions

1. **Execute your workflow**
2. **Click on the downstream Chain node** (the node that receives the cascadeflow output)
3. **Navigate to the "Logs" tab** (not the Output tab)

### CascadeFlow Agent: Viewing Cascade Decisions

1. **Execute your workflow**
2. **Click on the CascadeFlow Agent node**
3. **Navigate to the "Output" tab** — cascade metadata and trace are in the output JSON

### What You'll See

#### When Drafter is Accepted (Fast Path)

```
CascadeFlow: Trying drafter model...
   Quality validation: confidence=0.85, method=heuristic
   Alignment: 0.82

   FLOW: DRAFTER ACCEPTED (FAST PATH)
   Query -> Drafter -> Quality Check -> Response
   Confidence: 0.85 (threshold: 0.70)
   Cost savings: ~93.8% (used cheap model)
```

#### When Escalated to Verifier (Slow Path)

```
CascadeFlow: Trying drafter model...
   Quality validation: confidence=0.62, method=heuristic

   FLOW: ESCALATED TO VERIFIER (SLOW PATH)
   Query -> Drafter -> Quality Check -> Verifier -> Response
   Confidence: 0.62 < 0.70 (threshold)
   Verifier completed successfully
```

### UI Visualization Note

Due to n8n's rendering, the Model sub-node always highlights the first connection as active (green), regardless of which model was actually used at runtime. **This does not affect functionality.** Check the Logs tab to see which model was actually used.

---

## Use Cases

### Use Case 1: Customer Support with Model Node

```
┌──────────────────┐
│ Webhook          │ <- Customer question
│ (POST /support)  │
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────┐
│  Claude Haiku ────┐                 │
│                   │  CascadeFlow    │       ┌──────────────────┐
│  Claude Sonnet ───┴─► (Model)       │──────►│  Basic Chain     │
└─────────────────────────────────────┘       └──────────────────┘
```

- 70% of support queries are simple → drafter accepted
- Average savings: 60%

### Use Case 2: Agent with Tools

```
┌──────────────────┐
│ Chat Trigger     │
└────────┬─────────┘
         │
         v
┌──────────────────────────────────────────┐
│            CascadeFlow Agent             │
│                                          │
│  GPT-4o-mini ──► Drafter                 │
│  GPT-4o ───────► Verifier                │       ┌──────────────────┐
│  Window Buffer ─► Memory                 │──────►│  Respond to      │
│  HTTP Request ──► Tool                   │       │  Webhook         │
│  SQL Query ─────► Tool (verifier route)  │       └──────────────────┘
└──────────────────────────────────────────┘
```

- Tool calls validated before execution
- SQL tool forced to verifier routing for safety
- Memory persists conversation history across turns

### Use Case 3: Code Review with Local Drafter

```
┌──────────────────┐
│ GitHub Trigger   │ <- New PR opened
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────┐
│  Ollama qwen2.5 ──┐                 │
│                   │  CascadeFlow    │       ┌──────────────────┐
│  GPT-4o ──────────┴─► (Model)       │──────►│  Basic Chain     │
└─────────────────────────────────────┘       │  (reviews code)  │
                                               └──────────────────┘
```

- Ollama runs locally (free, fast drafts)
- GPT-4o for complex code analysis
- Savings: ~99% on drafter calls

### Use Case 4: Multi-Domain Agent

```
┌──────────────────┐
│ Chat Trigger     │
└────────┬─────────┘
         │
         v
┌──────────────────────────────────────────┐
│            CascadeFlow Agent             │
│                                          │
│  Domain Cascading: ON                    │
│  Code domain ──► Codestral              │
│  Math domain ──► Qwen2.5-Math           │       ┌──────────────────┐
│  GPT-4o-mini ──► Drafter (general)       │──────►│  Response        │
│  GPT-4o ───────► Verifier                │       └──────────────────┘
│  Tools ─────────► Calculator, Search     │
└──────────────────────────────────────────┘
```

- Domain-specific models for code and math queries
- General cascade for everything else
- Full tool calling with cascade-aware routing

---

## Recommended Configurations

### Claude Haiku + GPT-4o (Recommended)

```
Drafter: claude-3-5-haiku-20241022
Verifier: gpt-4o
Savings: ~73% average
Best for: General purpose, coding, reasoning
```

### Anthropic Only (High Quality)

```
Drafter: claude-3-5-haiku-20241022
Verifier: claude-3-5-sonnet-20241022
Savings: ~70% average
```

### OpenAI Only (Good Balance)

```
Drafter: gpt-4o-mini
Verifier: gpt-4o
Savings: ~85% average
```

### Ultra Fast with Ollama (Local)

```
Drafter: ollama/qwen2.5:3b (local)
Verifier: gpt-4o (cloud)
Savings: ~99% on drafter calls (no API cost)
Note: Requires Ollama installed locally
```

---

## Best Practices

### 1. Choose the Right Node

- **CascadeFlow (Model):** Use when plugging into existing Chain/LLM nodes. No tool calling or memory.
- **CascadeFlow Agent:** Use when you need tool calling, memory, or want a standalone agent in your workflow.

### 2. Tune Quality Threshold Based on Logs

Start with the default complexity thresholds (enabled by default) and adjust if needed:

1. Run 10-20 test queries
2. Check confidence scores in Logs (Model) or Output (Agent)
3. Adjust:
   - **Too many escalations?** Lower threshold
   - **Quality issues?** Raise threshold
4. Monitor acceptance rate

### 3. Mix Providers for Best Results

You can connect models from different providers to both nodes. Use a cheap local model (Ollama) as drafter with a powerful cloud model (GPT-4o) as verifier for maximum savings.

### 4. Use Tool Routing Rules (Agent)

For high-stakes tools (database writes, payment APIs), set tool routing to **Verifier** so the powerful model interprets results. Use **Cascade** (default) for low-risk tools.

### 5. Monitor Long-Term Performance

Track these metrics:
- **Acceptance rate**: Should be 70-80%
- **Confidence scores**: Should cluster above your threshold
- **Latency**: Drafter should be <500ms
- **Cost savings**: Track per-request savings percentage

---

## Troubleshooting

### "Drafter model is required"

Make sure you've connected an AI Chat Model to the **Drafter** input port.

### "Verifier model is required"

Make sure you've connected an AI Chat Model to the **Verifier** input port.

### Not seeing cascade logs

- **CascadeFlow (Model):** Logs appear in the downstream Chain node's **Logs** tab, not the cascadeflow node itself.
- **CascadeFlow Agent:** Cascade metadata and trace are in the output JSON of the Agent node's **Output** tab.

### Always escalating to verifier

1. Try lowering the Quality Threshold (0.3-0.4)
2. Verify your drafter model is actually a cheaper/faster model
3. Check logs for the confidence scores being reported

### "This node cannot be connected"

- Use **CascadeFlow (Model)** with Chain/LLM nodes that accept Language Model inputs
- Use **CascadeFlow Agent** for standalone agent workflows with tool calling and memory

### Domain cascading not triggering

1. Verify **Enable Domain Cascading** is turned on in node settings
2. Check that the detected domain matches an **enabled** domain toggle
3. General queries (e.g., "What's the weather?") route to `general` — make sure the General domain is enabled if you want a domain model for those
4. Check logs for "Domain detected:" messages to see what domain was classified

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

## Learn More

- [cascadeflow GitHub](https://github.com/lemony-ai/cascadeflow)
- [Package README](../../packages/integrations/n8n/README.md)
- [n8n Documentation](https://docs.n8n.io/)
- [n8n Community](https://community.n8n.io/)
