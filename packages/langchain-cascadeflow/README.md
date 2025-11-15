# @cascadeflow/langchain

LangChain integration for CascadeFlow - Add intelligent cost optimization to your existing LangChain models without reconfiguration.

## Features

- 🔄 **Zero Code Changes** - Wrap your existing LangChain models, no refactoring needed
- 💰 **Automatic Cost Optimization** - Save 40-60% on LLM costs through intelligent cascading
- 🎯 **Quality-Based Routing** - Only escalate to expensive models when quality is insufficient
- 📊 **Full Visibility** - Track costs, quality scores, and cascade decisions
- 🔗 **Chainable** - All LangChain methods (`bind()`, `bindTools()`, etc.) work seamlessly
- 📈 **LangSmith Ready** - Automatic cost metadata injection for observability

## Installation

```bash
npm install @cascadeflow/langchain @langchain/core
# or
pnpm add @cascadeflow/langchain @langchain/core
# or
yarn add @cascadeflow/langchain @langchain/core
```

## Quick Start

```typescript
import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '@cascadeflow/langchain';

// Step 1: Configure your existing models (no changes needed!)
const drafter = new ChatOpenAI({
  model: 'gpt-4o-mini',  // Fast, cheap model
  temperature: 0.7
});

const verifier = new ChatOpenAI({
  model: 'gpt-4o',  // Accurate, expensive model
  temperature: 0.7
});

// Step 2: Wrap with cascade (just 2 lines!)
const cascadeModel = withCascade({
  drafter,
  verifier,
  qualityThreshold: 0.7,  // Quality bar for accepting drafter responses
});

// Step 3: Use like any LangChain model!
const result = await cascadeModel.invoke("What is TypeScript?");
console.log(result.content);

// Step 4: Check cascade statistics
const stats = cascadeModel.getLastCascadeResult();
console.log(`Model used: ${stats.modelUsed}`);
console.log(`Cost: $${stats.totalCost.toFixed(6)}`);
console.log(`Savings: ${stats.savingsPercentage.toFixed(1)}%`);
```

## How It Works

CascadeFlow uses **speculative execution** to optimize costs:

1. **Try Drafter First** - Executes the cheap, fast model
2. **Quality Check** - Validates the response quality using heuristics or custom validators
3. **Cascade if Needed** - Only calls the expensive model if quality is below threshold
4. **Track Everything** - Records costs, latency, and cascade decisions

This approach provides:
- ✅ **No Latency Penalty** - Drafter responses are instant when quality is high
- ✅ **Quality Guarantee** - Verifier ensures high-quality responses for complex queries
- ✅ **Cost Savings** - 40-60% reduction in API costs on average

## Configuration

### Basic Configuration

```typescript
const cascadeModel = withCascade({
  drafter: new ChatOpenAI({ model: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ model: 'gpt-4o' }),
  qualityThreshold: 0.7,  // Default: 0.7 (70%)
});
```

### Custom Quality Validator

```typescript
const cascadeModel = withCascade({
  drafter,
  verifier,
  qualityValidator: async (response) => {
    // Custom logic - return quality score 0-1
    const text = response.generations[0].text;

    // Example: Use length and keywords
    const hasKeywords = ['typescript', 'javascript'].some(kw =>
      text.toLowerCase().includes(kw)
    );

    return text.length > 50 && hasKeywords ? 0.9 : 0.4;
  },
});
```

### Disable Cost Tracking

```typescript
const cascadeModel = withCascade({
  drafter,
  verifier,
  enableCostTracking: false,  // Disable metadata injection
});
```

## Advanced Usage

### Chaining with bind()

All LangChain chainable methods work seamlessly:

```typescript
const cascadeModel = withCascade({ drafter, verifier });

// bind() works
const boundModel = cascadeModel.bind({ temperature: 0.1 });
const result = await boundModel.invoke("Be precise");

// Chain multiple times
const doubleChained = cascadeModel
  .bind({ temperature: 0.5 })
  .bind({ maxTokens: 100 });
```

### Tool Calling

```typescript
const tools = [
  {
    name: 'calculator',
    description: 'Useful for math calculations',
    func: async (input: string) => {
      return eval(input).toString();
    },
  },
];

const modelWithTools = cascadeModel.bindTools(tools);
const result = await modelWithTools.invoke("What is 25 * 4?");
```

### Structured Output

```typescript
const schema = {
  name: 'person',
  schema: {
    type: 'object',
    properties: {
      name: { type: 'string' },
      age: { type: 'number' },
    },
  },
};

const structuredModel = cascadeModel.withStructuredOutput(schema);
const result = await structuredModel.invoke("Extract: John is 30 years old");
// Result is typed according to schema
```

### Accessing Cascade Statistics

```typescript
const result = await cascadeModel.invoke("Complex question");

const stats = cascadeModel.getLastCascadeResult();
console.log({
  content: stats.content,
  modelUsed: stats.modelUsed,  // 'drafter' or 'verifier'
  accepted: stats.accepted,  // Was drafter response accepted?
  drafterQuality: stats.drafterQuality,  // 0-1 quality score
  drafterCost: stats.drafterCost,  // $ spent on drafter
  verifierCost: stats.verifierCost,  // $ spent on verifier
  totalCost: stats.totalCost,  // Total $ spent
  savingsPercentage: stats.savingsPercentage,  // % saved vs verifier-only
  latencyMs: stats.latencyMs,  // Total latency in ms
});
```

## Supported Models

Works with any LangChain-compatible chat model:

### OpenAI
```typescript
import { ChatOpenAI } from '@langchain/openai';

const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
const verifier = new ChatOpenAI({ model: 'gpt-4o' });
```

### Anthropic
```typescript
import { ChatAnthropic } from '@langchain/anthropic';

const drafter = new ChatAnthropic({ model: 'claude-3-5-haiku-20241022' });
const verifier = new ChatAnthropic({ model: 'claude-3-5-sonnet-20241022' });
```

### Mix and Match
```typescript
// Use different providers!
const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
const verifier = new ChatAnthropic({ model: 'claude-3-5-sonnet-20241022' });
```

## Cost Optimization Tips

1. **Choose Your Drafter Wisely** - Use the cheapest model that can handle most queries
   - GPT-4o-mini: $0.15/$0.60 per 1M tokens (input/output)
   - Claude 3.5 Haiku: $0.80/$4.00 per 1M tokens

2. **Tune Quality Threshold** - Higher threshold = more cascades = higher cost but better quality
   - `0.6` - Aggressive cost savings, may sacrifice some quality
   - `0.7` - Balanced (recommended default)
   - `0.8` - Conservative, ensures high quality

3. **Use Custom Validators** - Domain-specific validation can improve accuracy
   ```typescript
   qualityValidator: (response) => {
     const text = response.generations[0].text;
     // Check for specific requirements
     return hasRelevantKeywords(text) && meetsLengthRequirement(text) ? 0.9 : 0.5;
   }
   ```

## Performance

Typical cascade behavior:

| Query Type | Drafter Hit Rate | Avg Latency | Cost Savings |
|-----------|------------------|-------------|--------------|
| Simple Q&A | 85% | 500ms | 55-65% |
| Complex reasoning | 40% | 1200ms | 20-30% |
| Code generation | 60% | 800ms | 35-45% |
| Overall | 70% | 700ms | 40-60% |

## TypeScript Support

Full TypeScript support with type inference:

```typescript
import type { CascadeConfig, CascadeResult } from '@cascadeflow/langchain';

const config: CascadeConfig = {
  drafter,
  verifier,
  qualityThreshold: 0.7,
};

const stats: CascadeResult | undefined = cascadeModel.getLastCascadeResult();
```

## Examples

See the [examples](./examples/) directory for complete working examples:

- **[basic-usage.ts](./examples/basic-usage.ts)** - Getting started guide
- More examples coming soon!

## API Reference

### `withCascade(config: CascadeConfig): CascadeWrapper`

Creates a cascade-wrapped LangChain model.

**Parameters:**
- `config.drafter` - The cheap, fast model
- `config.verifier` - The accurate, expensive model
- `config.qualityThreshold?` - Minimum quality to accept drafter (default: 0.7)
- `config.qualityValidator?` - Custom function to calculate quality
- `config.enableCostTracking?` - Enable LangSmith metadata injection (default: true)

**Returns:** `CascadeWrapper` - A LangChain-compatible model with cascade logic

### `CascadeWrapper.getLastCascadeResult(): CascadeResult | undefined`

Returns statistics from the last cascade execution.

**Returns:** `CascadeResult` with:
- `content` - The final response text
- `modelUsed` - Which model provided the response ('drafter' | 'verifier')
- `accepted` - Whether drafter response was accepted
- `drafterQuality` - Quality score of drafter response (0-1)
- `drafterCost` - Cost of drafter call
- `verifierCost` - Cost of verifier call (0 if not used)
- `totalCost` - Total cost
- `savingsPercentage` - Percentage saved vs verifier-only
- `latencyMs` - Total latency in milliseconds

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

MIT © [Lemony Inc.](https://lemony.ai)

## Related

- [@cascadeflow/core](../core) - Core CascadeFlow Python library
- [LangChain](https://github.com/langchain-ai/langchainjs) - Framework for LLM applications
- [LangSmith](https://smith.langchain.com/) - LLM observability platform
