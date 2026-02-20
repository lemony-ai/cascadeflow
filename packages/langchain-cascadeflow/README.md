# @cascadeflow/langchain

LangChain integration for CascadeFlow - Add intelligent cost optimization to your existing LangChain models without reconfiguration.

## Features

- 🔄 **Zero Code Changes** - Wrap your existing LangChain models, no refactoring needed
- 💰 **Automatic Cost Optimization** - Save 40-60% on LLM costs through intelligent cascading
- 🎯 **Quality-Based Routing** - Only escalate to expensive models when quality is insufficient
- 📊 **Full Visibility** - Track costs, quality scores, and cascade decisions
- 🔗 **Chainable** - All LangChain methods (`bind()`, `bindTools()`, etc.) work seamlessly
- 📈 **LangSmith Ready** - Automatic cost metadata injection for observability
- 🧭 **Domain Policies** - Per-domain threshold/routing overrides (`qualityThreshold`, `forceVerifier`, `directToVerifier`)
- 🔁 **CascadeAgent** - Built-in closed-loop tool agent for multi-turn execution with max-step protection

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
import { ChatAnthropic } from '@langchain/anthropic';
import { withCascade } from '@cascadeflow/langchain';

// Step 1: Configure your existing models (no changes needed!)
const drafter = new ChatOpenAI({
  model: 'gpt-5-mini',  // Fast, cheap model ($0.25/$2 per 1M tokens)
  temperature: 0.7
});

const verifier = new ChatAnthropic({
  model: 'claude-sonnet-4-5',  // Accurate, expensive model ($3/$15 per 1M tokens)
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

// Optional: Enable LangSmith tracing (see traces at https://smith.langchain.com)
// Set LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING=true
// Your ChatOpenAI/ChatAnthropic models will appear in LangSmith with cascade metadata
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
  drafter: new ChatOpenAI({ model: 'gpt-5-mini' }),
  verifier: new ChatAnthropic({ model: 'claude-sonnet-4-5' }),
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

### Domain Policies

Use domain-specific routing rules without changing your chain code:

```typescript
const cascadeModel = withCascade({
  drafter,
  verifier,
  qualityThreshold: 0.7,
  domainPolicies: {
    finance: { qualityThreshold: 0.5 }, // Easier acceptance for finance queries
    medical: { forceVerifier: true }, // Always verify after drafting
    legal: { directToVerifier: true }, // Skip drafter entirely
  },
});

const legalCascade = cascadeModel.bind({
  metadata: { cascadeflow_domain: "legal" },
});

const result = await legalCascade.invoke("Review this contract clause");
```

## Advanced Usage

### Streaming Responses

CascadeFlow supports real-time streaming with optimistic drafter execution:

```typescript
const cascade = withCascade({
  drafter: new ChatOpenAI({ model: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ model: 'gpt-4o' }),
});

// Stream responses in real-time
const stream = await cascade.stream('Explain TypeScript');

for await (const chunk of stream) {
  process.stdout.write(chunk.content);
}
```

**How Streaming Works:**
1. **Optimistic Streaming (text-only)** - Drafter response streams immediately (user sees output in real-time)
2. **Quality Check** - After drafter completes, quality is validated
3. **Optional Cascade** - If quality is insufficient, verifier output is streamed; switch notices are off by default and can be enabled via metadata (`cascadeflow_emit_switch_message`)
4. **Tool-safe Streaming** - When tools are bound with `bindTools(...)`, output is buffered until final routing so tool-call deltas stay consistent

This provides the best user experience with no perceived latency for queries the drafter can handle.

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

### Agentic Tool Loops (`CascadeAgent`)

`CascadeAgent` adds a closed agent/tool loop with explicit max-step safety:

```typescript
import { CascadeAgent, withCascade } from '@cascadeflow/langchain';

const cascadeModel = withCascade({
  drafter,
  verifier,
  domainPolicies: {
    legal: { directToVerifier: true },
    medical: { forceVerifier: true },
  },
});

const agent = new CascadeAgent({
  model: cascadeModel.bindTools(tools),
  maxSteps: 6,
  toolHandlers: {
    calculator: async ({ expression }) => eval(expression).toString(),
  },
});

const run = await agent.run(
  [{ role: 'user', content: 'What is (25 * 4) + 10?' }],
  { systemPrompt: 'You are a precise calculator assistant.' }
);

console.log(run.status, run.steps, run.message.content);
```

Input can be a string, LangChain `BaseMessage[]`, or role/content message list for multi-turn conversations.

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

## LangSmith Integration

CascadeFlow works seamlessly with LangSmith for observability and cost tracking.

### What You'll See in LangSmith

When you enable LangSmith tracing, you'll see:

1. **Your Actual Chat Models** - ChatOpenAI, ChatAnthropic, etc. appear as separate traces
2. **Cascade Metadata** - Decision info attached to each response
3. **Token Usage & Costs** - Server-side calculation by LangSmith
4. **Nested Traces** - Parent CascadeFlow trace with child model traces

### Enabling LangSmith

```typescript
// Set environment variables
process.env.LANGSMITH_API_KEY = 'lsv2_pt_...';
process.env.LANGSMITH_PROJECT = 'your-project';
process.env.LANGSMITH_TRACING = 'true';

// Use CascadeFlow normally - tracing happens automatically
const cascade = withCascade({
  drafter: new ChatOpenAI({ model: 'gpt-5-mini' }),
  verifier: new ChatAnthropic({ model: 'claude-sonnet-4-5' }),
  costTrackingProvider: 'cascadeflow', // Default (local pricing)
});

const result = await cascade.invoke("Your query");
```

### Viewing Traces

In your LangSmith dashboard (https://smith.langchain.com):

- **For cascaded queries** - You'll see only the drafter model trace (e.g., ChatOpenAI with gpt-5-mini)
- **For escalated queries** - You'll see BOTH drafter AND verifier traces (e.g., ChatOpenAI gpt-5-mini + ChatAnthropic claude-sonnet-4-5)
- **Metadata location** - Click any trace → Outputs → response_metadata → cascade

### Example Metadata

```json
{
  "cascade": {
    "cascade_decision": "cascaded",
    "model_used": "drafter",
    "drafter_quality": 0.85,
    "savings_percentage": 66.7,
    "drafter_cost": 0,      // Calculated by LangSmith
    "verifier_cost": 0,     // Calculated by LangSmith
    "total_cost": 0         // Calculated by LangSmith
  }
}
```

**Note**: `costTrackingProvider: 'cascadeflow'` (default) computes costs locally using CascadeFlow's pricebook. If you use `costTrackingProvider: 'langsmith'`, costs are calculated server-side and shown in the LangSmith UI (local cost values will be $0).

See [docs/COST_TRACKING.md](./docs/COST_TRACKING.md) for more details on cost tracking options.

## Supported Models

Works with any LangChain-compatible chat model:

### OpenAI
```typescript
import { ChatOpenAI } from '@langchain/openai';

const drafter = new ChatOpenAI({ model: 'gpt-5-mini' });
const verifier = new ChatOpenAI({ model: 'gpt-5' });
```

### Anthropic
```typescript
import { ChatAnthropic } from '@langchain/anthropic';

const drafter = new ChatAnthropic({ model: 'claude-3-haiku-20240307' });
const verifier = new ChatAnthropic({ model: 'claude-sonnet-4-6' });
```

### Mix and Match (Recommended)
```typescript
// Use different providers for optimal cost/quality balance!
const drafter = new ChatOpenAI({ model: 'gpt-5-mini' });
const verifier = new ChatAnthropic({ model: 'claude-sonnet-4-6' });
```

## Cost Optimization Tips

1. **Choose Your Drafter Wisely** - Use the cheapest model that can handle most queries
   - GPT-5-mini: $0.25/$2.00 per 1M tokens (input/output)
   - GPT-4o-mini: $0.15/$0.60 per 1M tokens (input/output)
   - Claude 3 Haiku: $0.25/$1.25 per 1M tokens

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
- **[streaming-cascade.ts](./examples/streaming-cascade.ts)** - Real-time streaming with optimistic drafter execution
- **[lcel-pipeline.ts](./examples/lcel-pipeline.ts)** - LCEL runnable composition with CascadeFlow
- **[tool-risk-gating.ts](./examples/tool-risk-gating.ts)** - Tool-call acceptance + high-risk verifier gating
- **[langgraph-multi-agent.ts](./examples/langgraph-multi-agent.ts)** - Optional LangGraph multi-agent pattern

## API Reference

### `withCascade(config: CascadeConfig): CascadeFlow`

Creates a cascade-wrapped LangChain model.

**Parameters:**
- `config.drafter` - The cheap, fast model
- `config.verifier` - The accurate, expensive model
- `config.qualityThreshold?` - Minimum quality to accept drafter (default: 0.7)
- `config.qualityValidator?` - Custom function to calculate quality
- `config.enableCostTracking?` - Enable LangSmith metadata injection (default: true)
- `config.costTrackingProvider?` - `'cascadeflow'` (default, local pricing) or `'langsmith'` (server-side)
- `config.domainPolicies?` - Per-domain overrides: `qualityThreshold`, `forceVerifier`, `directToVerifier`

**Returns:** `CascadeFlow` - A LangChain-compatible model with cascade logic

### `new CascadeAgent(config: CascadeAgentConfig)`

Creates a closed-loop agent around a LangChain model (or directly from cascade config).

**Parameters:**
- `config.model?` - Any LangChain chat model (often `withCascade(...).bindTools(...)`)
- `config.cascade?` - Optional `CascadeConfig` used to create an internal `CascadeFlow`
- `config.maxSteps?` - Loop safety cap (default: `8`)
- `config.toolHandlers?` - Tool name to handler map

### `CascadeAgent.run(input, options?): Promise<CascadeAgentRunResult>`

Runs model/tool/model loops until completion or `maxSteps` is reached.

**Returns:** `CascadeAgentRunResult` with:
- `message` - Final `AIMessage`
- `messages` - Full message history (including tool messages)
- `steps` - Executed model turns
- `status` - `'completed' | 'max_steps_reached'`
- `toolCalls` - Collected tool calls across steps

### `CascadeFlow.getLastCascadeResult(): CascadeResult | undefined`

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
