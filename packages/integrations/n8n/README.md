<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../../.github/assets/CF_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset="../../../.github/assets/CF_logo_dark.svg">
  <img alt="CascadeFlow Logo" src="../../../.github/assets/CF_logo_dark.svg" width="400">
</picture>

# n8n-nodes-cascadeflow

<img src="../../../.github/assets/CF_n8n_color.svg" width="24" height="24" alt="n8n"/> **n8n community node for CascadeFlow**

This is an n8n community node that brings CascadeFlow's intelligent AI model cascading to n8n workflows.

**CascadeFlow** reduces LLM API costs by 40-85% by trying a cheap model first, validating quality, and only escalating to expensive models when needed.

[n8n](https://n8n.io/) is a fair-code licensed workflow automation platform.

## Installation

Follow the [installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) in the n8n community nodes documentation.

### Community Nodes (Recommended)

1. Go to **Settings** > **Community Nodes**
2. Select **Install**
3. Enter `n8n-nodes-cascadeflow` in **Enter npm package name**
4. Agree to the risks and install

### Manual installation

To get started install the package in your n8n root directory:

```bash
npm install n8n-nodes-cascadeflow
```

For Docker-based deployments add the following line before the font installation command in your [n8n Dockerfile](https://github.com/n8n-io/n8n/blob/master/docker/images/n8n/Dockerfile):

```dockerfile
RUN cd /usr/local/lib/node_modules/n8n && npm install n8n-nodes-cascadeflow
```

## Operations

The CascadeFlow node supports these operations:

### Generate Text

Generate AI responses with intelligent cascading between draft and verifier models.

**How it works:**
1. Sends query to cheap draft model (e.g., Claude-3.5-Haiku or GPT-4o-mini)
2. Validates quality automatically
3. If quality passes → return draft (fast + cheap) ✅
4. If quality fails → escalate to verifier model (e.g., GPT-5) ⚠️

**Result:** 70-80% of queries accept the draft, saving 40-85% on costs.

### Generate with Tools

Same cascading logic but with tool calling support for function-based AI.

## Configuration

### Credentials

The node requires a CascadeFlow API credential with API keys for the providers you want to use:

- **OpenAI API Key** - For GPT models
- **Anthropic API Key** - For Claude models
- **Groq API Key** - For fast Llama inference
- **Together AI API Key** - For open-source models
- **HuggingFace API Key** - For HuggingFace models

You only need to provide keys for the providers you're actually using.

### Node Parameters

#### Required Parameters

- **Message**: The query or prompt to send to AI
- **Draft Model**: Configuration for the cheap model
  - Provider (OpenAI, Anthropic, Groq, etc.)
  - Model name (e.g., `claude-3-5-haiku-20241022`, `gpt-4o-mini`)
  - Cost per 1K tokens
- **Verifier Model**: Configuration for the expensive model
  - Provider
  - Model name (e.g., `gpt-5`, `claude-3-5-sonnet-20241022`)
  - Cost per 1K tokens

#### Optional Parameters

- **Quality Settings**
  - Quality Threshold (0-1): Minimum score to accept draft
  - Require Validation: Whether to validate before accepting
- **Advanced Options**
  - Max Tokens: Maximum tokens to generate
  - Temperature: Sampling temperature (0-2)
  - System Prompt: Optional system instructions
- **Output Mode**: What data to return
  - Full Metrics: All cascade diagnostics
  - Content Only: Just the AI response
  - Metrics Summary: Response + key metrics

## Example Workflows

### Basic Chat

```
Input: "What is TypeScript?"

CascadeFlow Node:
  Draft: gpt-4o-mini ($0.00015)
  Verifier: gpt-5 ($0.00125)

Output:
  content: "TypeScript is a superset of JavaScript..."
  modelUsed: "gpt-4o-mini"
  totalCost: 0.000211
  savingsPercentage: 83.2%
  draftAccepted: true
```

### Customer Support

```
Trigger: Webhook (customer question)
    ↓
CascadeFlow Node (draft: claude-3-haiku, verifier: claude-3-sonnet)
    ↓
IF Node (check if escalated)
    ├─ Yes → Send to human support
    └─ No → Send automated response
```

### Content Generation

```
Schedule: Daily at 9am
    ↓
Code Node: Generate topic ideas
    ↓
CascadeFlow Node: Generate blog post
    ↓
CascadeFlow Node: Proofread and edit
    ↓
Notion Node: Save to content calendar
```

### Tool Calling

```
CascadeFlow Node (Generate with Tools):
  Message: "What's the weather in Paris?"
  Tools: [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
          "type": "object",
          "properties": {
            "location": { "type": "string" }
          }
        }
      }
    }
  ]

Output:
  toolCalls: [
    {
      "id": "call_abc123",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"Paris\"}"
      }
    }
  ]
```

## Output Format

### Full Metrics (default)

```json
{
  "content": "AI response here...",
  "modelUsed": "gpt-4o-mini",
  "totalCost": 0.000211,
  "savingsPercentage": 97.8,
  "latencyMs": 820,
  "cascaded": true,
  "draftAccepted": true,
  "complexity": "simple",
  "routingStrategy": "cascade",
  "qualityScore": 0.89,
  "draftCost": 0.000211,
  "verifierCost": 0.0,
  "summary": {
    "saved": "97.8%",
    "cost": "$0.000211",
    "model": "gpt-4o-mini",
    "speed": "820ms",
    "status": "✅ Draft accepted"
  }
}
```

### Content Only

```json
{
  "content": "AI response here..."
}
```

### Metrics Summary

```json
{
  "content": "AI response here...",
  "modelUsed": "gpt-4o-mini",
  "totalCost": 0.000211,
  "savingsPercentage": 97.8,
  "cascaded": true,
  "draftAccepted": true,
  "latencyMs": 820
}
```

## Cost Savings Examples

**With GPT-5 (Recommended):**

| Use Case | Traditional GPT-5 Only | CascadeFlow (Haiku + GPT-5) | Savings |
|----------|------------------------|------------------------------|---------|
| Simple Q&A (70% of traffic) | $0.00125 | $0.0008 | 36% |
| Complex query (30% of traffic) | $0.00125 | $0.00125 | 0% (correctly escalated) |
| **Average** | **$0.00125** | **$0.00094** | **24.8%** |

**Monthly savings (10,000 queries):**
- Traditional (GPT-5 only): $12.50
- CascadeFlow (Haiku + GPT-5): $9.40
- **You save: $3.10/month** (25% savings)

**Monthly savings (100,000 queries):**
- Traditional (GPT-5 only): $125.00
- CascadeFlow (Haiku + GPT-5): $94.00
- **You save: $31.00/month** (25% savings)

**Note:** GPT-5 is already 50% cheaper input than GPT-4o. Cascading adds additional 25-30% savings on top!

## Recommended Model Configurations

### ⭐ Best Overall: Claude Haiku + GPT-5 (Recommended)

```
Draft: claude-3-5-haiku-20241022 ($0.0008)
Verifier: gpt-5 ($0.00125)
Savings: ~50-65%
Why: Haiku's fast, high-quality drafts + GPT-5's superior reasoning
Use for: Coding, reasoning, complex queries, agentic workflows
```

> **⚠️ Important:** GPT-5 requires OpenAI organization verification. Visit [OpenAI Settings](https://platform.openai.com/settings/organization/general) and verify your organization. The cascade works immediately (Claude handles 75% of queries), GPT-5 verification unlocks the remaining 25%.

### OpenAI Only (Good Balance)

```
Draft: gpt-4o-mini ($0.00015)
Verifier: gpt-5 ($0.00125)
Savings: ~50-60%
Why: GPT-5 is 50% cheaper input than GPT-4o, better performance
Note: GPT-5 excels at coding (75% vs 31%), reasoning, math
```

### Anthropic Only (High Quality)

```
Draft: claude-3-5-haiku-20241022 ($0.0008)
Verifier: claude-3-5-sonnet-20241022 ($0.003)
Savings: ~40-50%
Why: Consistent Anthropic experience, excellent quality
```

### Groq + GPT-5 (Ultra Fast + Best Quality)

```
Draft: groq/llama-3.1-8b-instant ($0.00005)
Verifier: gpt-5 ($0.00125)
Savings: ~75-85%
Why: Groq's instant speed + GPT-5's reasoning power
Note: Highest cost savings, best for high-volume workloads
```

### Legacy: GPT-4o (Not Recommended)

```
Draft: gpt-4o-mini ($0.00015)
Verifier: gpt-4o ($0.0025)
Savings: ~40-50%
Note: GPT-5 is cheaper and significantly better at coding/reasoning
```

## Compatibility

Tested with n8n version 1.0+

## Resources

- [n8n community nodes documentation](https://docs.n8n.io/integrations/community-nodes/)
- [CascadeFlow GitHub](https://github.com/lemony-ai/cascadeflow)
- [CascadeFlow Documentation](https://docs.lemony.ai/cascadeflow)

## License

[MIT](https://github.com/lemony-ai/cascadeflow/blob/main/LICENSE)

## Version history

### 1.0.0

- Initial release
- Support for OpenAI, Anthropic, Groq, Together AI, Ollama, HuggingFace
- Text generation with cascading
- Tool calling support
- Full metrics and cost tracking
