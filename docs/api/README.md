# cascadeflow API Reference

Complete API documentation for cascadeflow Python and TypeScript SDKs.

## 📚 Core Documentation

### Python API
- [CascadeAgent](./python/agent.md) - Main agent class for intelligent model cascading
- [ModelConfig](./python/config.md) - Model configuration and cascade settings
- [CascadeResult](./python/result.md) - Result object with diagnostics and metrics
- [Telemetry](./telemetry.md) - Cost tracking and telemetry

### TypeScript API

For complete TypeScript API documentation, see the [TypeScript Package README](../../packages/core/README.md).

**Quick Links:**
- [Installation & Quick Start](../../packages/core/README.md#installation)
- [Presets](../../packages/core/README.md#even-easier-use-presets-new-in-v011)
- [Features & Examples](../../packages/core/README.md#features)

## 🚀 Quick Reference

### Python

```python
from cascadeflow import CascadeAgent, ModelConfig

# Create agent
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
])

# Run query
result = await agent.run("What is Python?")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Savings: {result.cost_saved_percentage:.1f}%")
```

### TypeScript

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// Create agent
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
  ]
});

// Run query
const result = await agent.run('What is TypeScript?');
console.log(`Cost: $${result.totalCost.toFixed(6)}`);
console.log(`Savings: ${result.savingsPercentage}%`);
```

## 📖 API Structure

### Core Classes

| Class | Python | TypeScript | Description |
|-------|--------|------------|-------------|
| **CascadeAgent** | `cascadeflow.CascadeAgent` | `@cascadeflow/core.CascadeAgent` | Main agent for cascading |
| **ModelConfig** | `cascadeflow.ModelConfig` | `ModelConfig` interface | Model configuration |
| **CascadeResult** | `cascadeflow.CascadeResult` | `CascadeResult` interface | Query result with metrics |
| **QualityConfig** | `cascadeflow.QualityConfig` | `QualityConfig` interface | Quality validation settings |

### Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| **models** | `List[ModelConfig]` | Required | Models to cascade through (sorted by cost) |
| **quality.threshold** | `float` | 0.7 | Minimum quality score to accept (0-1) |
| **cascade.maxBudget** | `float` | None | Maximum cost per query in USD |
| **cascade.maxRetries** | `int` | 2 | Max retries per model on failure |
| **cascade.timeout** | `int` | 30 | Timeout per model in seconds |
| **cascade.trackCosts** | `bool` | True | Enable detailed cost tracking |

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| **content** | `str` | Generated response text |
| **model_used** | `str` | Model that produced final response |
| **total_cost** | `float` | Total cost in USD |
| **latency_ms** | `int` | Total latency in milliseconds |
| **cascaded** | `bool` | Whether cascade was used |
| **draft_accepted** | `bool` | If cascaded, was draft accepted |
| **quality_score** | `float` | Quality score (0-1) |
| **cost_saved** | `float` | Cost saved vs always using best model |
| **savings_percentage** | `float` | Savings as percentage |

## 🔧 Provider Support

cascadeflow supports 7+ AI providers out of the box:

| Provider | Status | Models Supported |
|----------|--------|------------------|
| **OpenAI** | ✅ Stable | GPT-4o, GPT-4o-mini, GPT-3.5-turbo, GPT-5 |
| **Anthropic** | ✅ Stable | Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku |
| **Groq** | ✅ Stable | Llama 3.1, Mixtral, Gemma |
| **Ollama** | ✅ Stable | All Ollama models (local deployment) |
| **vLLM** | ✅ Stable | Custom models (local/cloud deployment) |
| **Together** | ✅ Stable | 100+ open-source models |
| **Hugging Face** | ✅ Stable | Inference API models |

## 📊 Advanced Features

### Streaming

```python
# Python
async for event in agent.stream("Tell me a story"):
    if event.type == "content_delta":
        print(event.content, end="", flush=True)
```

```typescript
// TypeScript
for await (const event of agent.stream('Tell me a story')) {
  if (event.type === 'content_delta') {
    process.stdout.write(event.content);
  }
}
```

### Tool Calling

```python
# Python
tools = [{"name": "get_weather", "description": "Get weather", "parameters": {...}}]
result = await agent.run("What's the weather?", tools=tools)
```

```typescript
// TypeScript
const tools = [{ name: 'get_weather', description: 'Get weather', parameters: {...} }];
const result = await agent.run('What\'s the weather?', { tools });
```

### Presets

```python
# Python
from cascadeflow import PRESET_BEST_OVERALL, PRESET_ULTRA_FAST

agent = CascadeAgent.from_preset(PRESET_BEST_OVERALL)
```

```typescript
// TypeScript
import { CascadeAgent, PRESET_BEST_OVERALL } from '@cascadeflow/core';

const agent = new CascadeAgent(PRESET_BEST_OVERALL);
```

## 🔍 See Also

### User Guides
- [Quickstart Guide](../guides/quickstart.md) - Get started in 5 minutes
- [Provider Configuration](../guides/providers.md) - Configure AI providers
- [Presets Guide](../guides/presets.md) - Built-in preset configurations
- [Streaming Guide](../guides/streaming.md) - Streaming responses and events
- [Tools Guide](../guides/tools.md) - Function calling and tool execution
- [Custom Validation](../guides/custom_validation.md) - Quality validation and custom validators
- [Cost Tracking](../guides/cost_tracking.md) - Track and analyze API costs
- [Production Guide](../guides/production.md) - Best practices for production

### Examples
- [Python Examples](../../examples/) - Working Python code examples
- [TypeScript Examples](../../packages/core/examples/) - Working TypeScript code examples

## 💡 Need Help?

- 📖 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions) - Q&A and community support
- 🐛 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues) - Bug reports
- 📧 [Email Support](mailto:hello@lemony.ai) - Direct support
