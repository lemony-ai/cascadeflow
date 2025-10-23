# n8n Integration Guide

This guide shows how to use CascadeFlow in n8n workflows for intelligent AI model cascading with 40-85% cost savings.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Use Cases](#use-cases)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The **n8n-nodes-cascadeflow** package brings CascadeFlow's intelligent model cascading to n8n workflows.

### What is Model Cascading?

Instead of always using expensive models:

```
Traditional: Every query → GPT-4o ($0.00625)
```

CascadeFlow tries cheap models first:

```
CascadeFlow:
  1. Try GPT-4o-mini ($0.00015) ← 70-80% stop here! ✅
  2. Validate quality
  3. If needed → GPT-4o ($0.00625)

Result: 50-85% cost savings
```

###Why Use CascadeFlow in n8n?

✅ **Massive Cost Savings** - 40-85% cheaper than direct API calls
✅ **Same Quality** - Automatic validation ensures quality
✅ **Easy Integration** - Drop-in replacement for AI nodes
✅ **Rich Metrics** - Track costs and savings in real-time
✅ **Tool Calling** - Full function calling support
✅ **Multi-Provider** - OpenAI, Anthropic, Groq, Together AI, Ollama, HuggingFace

---

## Installation

### Method 1: Community Nodes (Recommended)

1. Open n8n
2. Go to **Settings** > **Community Nodes**
3. Click **Install**
4. Enter: `n8n-nodes-cascadeflow`
5. Click **Install**
6. Restart n8n

### Method 2: Manual Installation

```bash
# In your n8n directory
npm install n8n-nodes-cascadeflow
```

### Method 3: Docker

Add to your Dockerfile before font installation:

```dockerfile
RUN cd /usr/local/lib/node_modules/n8n && npm install n8n-nodes-cascadeflow
```

---

## Quick Start

### Step 1: Add Credentials

1. Go to **Credentials** in n8n
2. Click **Add Credential**
3. Search for **CascadeFlow API**
4. Add your API keys (only for providers you'll use):
   - OpenAI API Key: `sk-...`
   - Anthropic API Key: `sk-ant-...`
   - Groq API Key: `gsk_...`
5. Save

### Step 2: Create Your First Workflow

```
Manual Trigger
    ↓
CascadeFlow Node
    ↓
Set Node (display result)
```

**CascadeFlow Node Configuration:**
- **Message**: `What is TypeScript?`
- **Draft Model**:
  - Provider: OpenAI
  - Model: `gpt-4o-mini`
  - Cost: `0.00015`
- **Verifier Model**:
  - Provider: OpenAI
  - Model: `gpt-4o`
  - Cost: `0.00625`
- **Output**: Full Metrics

### Step 3: Execute and View Results

Click **Execute Workflow** and see:

```json
{
  "content": "TypeScript is a superset of JavaScript...",
  "modelUsed": "gpt-4o-mini",
  "totalCost": 0.000211,
  "savingsPercentage": 97.8,
  "summary": {
    "saved": "97.8%",
    "cost": "$0.000211",
    "model": "gpt-4o-mini",
    "status": "✅ Draft accepted"
  }
}
```

**You just saved 97.8%!** 🎉

---

## Configuration

### Draft and Verifier Models

The cascade uses 2 models:

| Role | Purpose | Cost | Example |
|------|---------|------|---------|
| **Draft** | Fast, cheap first attempt | Low | gpt-4o-mini ($0.00015) |
| **Verifier** | High-quality fallback | High | gpt-4o ($0.00625) |

**How to choose:**

1. **Draft Model** - Cheapest model that's "good enough" most of the time
2. **Verifier Model** - Best quality model for when draft fails

### Quality Settings

- **Quality Threshold** (0-1): Minimum score to accept draft
  - `0.5` = Very permissive (more drafts accepted)
  - `0.7` = Balanced (default)
  - `0.9` = Very strict (fewer drafts accepted)
- **Require Validation**: Whether to check quality (recommended: `true`)

### Advanced Options

- **Max Tokens**: Maximum response length (default: 1000)
- **Temperature**: Creativity/randomness (0-2, default: 0.7)
- **System Prompt**: Instructions for the AI

### Output Modes

1. **Full Metrics** - All diagnostic data + summary
2. **Content Only** - Just the AI response text
3. **Metrics Summary** - Response + key metrics (cost, savings, model)

---

## Use Cases

### Use Case 1: Customer Support Automation

**Workflow:**
```
Webhook (customer email)
    ↓
CascadeFlow (generate response)
    ├─ Draft: claude-3-haiku
    └─ Verifier: claude-3-sonnet
    ↓
IF Node (check draftAccepted)
    ├─ true → Send email
    └─ false → Notify support team
```

**Why this works:**
- 70% of support queries are simple → draft accepted
- 30% complex → automatically escalated
- Average savings: 60%

**Configuration:**
```
Draft: claude-3-haiku ($0.00075)
Verifier: claude-3-sonnet ($0.009)
Quality Threshold: 0.75
```

---

### Use Case 2: Content Generation

**Workflow:**
```
Schedule (daily 9am)
    ↓
Code Node (generate topics)
    ↓
CascadeFlow (write blog post)
    ├─ Draft: gpt-4o-mini
    └─ Verifier: gpt-4o
    ↓
CascadeFlow (proofread)
    ↓
Notion (save to calendar)
```

**Why this works:**
- First pass uses cheap model
- Quality validation catches errors
- Only escalates for complex topics

**Savings:** $0.50 → $0.15 per article (70% savings)

---

### Use Case 3: Data Enrichment

**Workflow:**
```
Google Sheets (read contacts)
    ↓
Loop Over Items
    ↓
CascadeFlow (generate personalized message)
    ├─ Draft: groq/llama-3.1-8b-instant
    └─ Verifier: openai/gpt-4o
    ↓
Google Sheets (write back)
```

**Why this works:**
- Groq is ultra-fast and cheap for draft
- OpenAI for verification only when needed
- Process 1000 contacts for $3 instead of $62

**Configuration:**
```
Draft: llama-3.1-8b-instant ($0.00005)
Verifier: gpt-4o ($0.00625)
Quality Threshold: 0.7
Savings: 95%
```

---

### Use Case 4: Tool Calling

**Workflow:**
```
Manual Trigger
    ↓
CascadeFlow (Generate with Tools)
    Message: "What's the weather in Paris and London?"
    Tools: [get_weather, get_forecast]
    ↓
Function Node (execute tool calls)
    ↓
CascadeFlow (format results)
    ↓
Slack (send message)
```

**Tool Definition:**
```json
[
  {
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City name"
          }
        },
        "required": ["location"]
      }
    }
  }
]
```

**Output:**
```json
{
  "content": "",
  "toolCalls": [
    {
      "id": "call_abc123",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"Paris\"}"
      }
    },
    {
      "id": "call_def456",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"London\"}"
      }
    }
  ]
}
```

---

## Best Practices

### 1. Choose the Right Draft Model

**For speed:**
```
groq/llama-3.1-8b-instant ($0.00005)
- 500-1000 tokens/sec
- 95% cost savings
```

**For quality:**
```
openai/gpt-4o-mini ($0.00015)
- Better reasoning
- 75% cost savings
```

**For offline/privacy:**
```
ollama/llama3 ($0.00)
- Free
- Runs locally
```

### 2. Tune Quality Threshold

Start with `0.7` and adjust based on results:

- **Too many escalations?** Lower threshold (0.6)
- **Quality issues?** Raise threshold (0.8)
- **Monitor:** Track `draftAccepted` rate in metrics

### 3. Use Output Modes Wisely

- **Full Metrics** - During development/testing
- **Metrics Summary** - Production (balance data + performance)
- **Content Only** - When you only need the response

### 4. Handle Errors Gracefully

```
CascadeFlow
    ↓
IF Node (check for error)
    ├─ Has error → Retry or fallback
    └─ Success → Continue workflow
```

### 5. Track Costs Over Time

```
CascadeFlow
    ↓
Google Sheets (log metrics)
    Columns: timestamp, cost, savings%, model, query
```

Monthly analysis:
```sql
SELECT
  SUM(cost) as total_cost,
  AVG(savingsPercentage) as avg_savings,
  COUNT(*) as queries
FROM metrics
WHERE timestamp > NOW() - INTERVAL '30 days'
```

---

## Recommended Configurations

### OpenAI (Balanced)

```
Draft: gpt-4o-mini ($0.00015)
Verifier: gpt-4o ($0.00625)
Quality: 0.7
Expected Savings: 50-60%
```

### Anthropic (High Quality)

```
Draft: claude-3-haiku ($0.00075)
Verifier: claude-3-sonnet ($0.009)
Quality: 0.75
Expected Savings: 40-50%
```

### Groq (Ultra Fast & Cheap)

```
Draft: llama-3.1-8b-instant ($0.00005)
Verifier: llama-3.3-70b-versatile ($0.00059)
Quality: 0.65
Expected Savings: 70-80%
```

### Mixed (Best Value)

```
Draft: groq/llama-3.1-8b-instant ($0.00005)
Verifier: openai/gpt-4o ($0.00625)
Quality: 0.7
Expected Savings: 80-85%
```

### Budget (Free Draft)

```
Draft: ollama/llama3 ($0.00)
Verifier: groq/llama-3.1-70b-versatile ($0.00059)
Quality: 0.6
Expected Savings: 90-95%
```

---

## Troubleshooting

### "API key not found"

**Solution:** Check credentials:
1. Go to **Credentials** in n8n
2. Find **CascadeFlow API**
3. Ensure API key is set for the provider you're using
4. Test the credential

### "Quality threshold too strict"

**Symptom:** All queries escalate to verifier

**Solution:** Lower quality threshold:
- Current: `0.9` → Try: `0.7`
- Or use better draft model (e.g., gpt-4o-mini instead of gpt-3.5-turbo)

### "Tool calls not working"

**Checklist:**
- ✅ Using "Generate with Tools" operation (not "Generate Text")
- ✅ Tools JSON is valid
- ✅ Model supports tools (gpt-4o, claude-3-sonnet, etc.)
- ✅ Not using Ollama (doesn't support tools reliably)

### "High costs despite cascading"

**Debug:**
1. Check `draftAccepted` rate in output
   - Should be 70-80%
   - If low → quality threshold too strict OR draft model too weak
2. Verify model costs are correct
3. Check if you're using the right draft model

---

## Cost Calculator

Estimate your savings:

```
Traditional Cost (per 1000 queries):
  Always use GPT-4o: 1000 × $0.00625 = $6.25

CascadeFlow (70% draft acceptance):
  Draft (700): 700 × $0.00015 = $0.105
  Verifier (300): 300 × $0.00640 = $1.920
  Total: $2.025

Savings: $6.25 - $2.025 = $4.225 (67.6%)
```

**Your numbers:**
- Queries/month: _______
- Draft model cost: $_______
- Verifier model cost: $_______
- Expected draft acceptance: _______%

[Use our online calculator](https://cascadeflow.com/calculator)

---

## Advanced Patterns

### Pattern 1: Progressive Enhancement

```
CascadeFlow (draft: mini, verifier: 4o)
    ↓
IF (quality < 0.9)
    ↓
CascadeFlow (draft: 4o, verifier: claude-opus)
```

### Pattern 2: Batch Processing with Cost Limits

```
Google Sheets (read 1000 rows)
    ↓
Loop with Counter
    ↓
CascadeFlow
    ↓
Function (track cumulative cost)
    ↓
IF (cost > $10) → Stop loop
```

### Pattern 3: A/B Testing

```
Code (random 0 or 1)
    ↓
IF (random === 0)
    ├─ CascadeFlow (with cascading)
    └─ OpenAI (direct GPT-4o)
    ↓
Google Sheets (log for comparison)
```

---

## Examples Repository

Find more examples at: [github.com/lemony-ai/cascadeflow/examples/n8n/](https://github.com/lemony-ai/cascadeflow/tree/main/examples/n8n)

- Customer support automation
- Content generation pipeline
- Data enrichment workflows
- Tool calling examples
- Cost tracking dashboards

---

## Learn More

- [n8n Documentation](https://docs.n8n.io/)
- [CascadeFlow GitHub](https://github.com/lemony-ai/cascadeflow)
- [CascadeFlow Guides](../../README.md)
- [Community Forum](https://community.n8n.io/)

---

**Next Steps:**
- Install the node and try the Quick Start
- Experiment with different model configurations
- Share your workflows with the community!
