# cascadeflow TypeScript Examples

**Complete collection of TypeScript examples** demonstrating cascadeflow from basics to production deployment.

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Install cascadeflow
npm install @cascadeflow/core
# or with pnpm
pnpm add @cascadeflow/core

# 2. Install peer dependencies (choose your providers)
npm install openai @anthropic-ai/sdk groq-sdk

# 3. Set your API key
export OPENAI_API_KEY="sk-..."

# 4. Run your first example
npx tsx examples/nodejs/basic-usage.ts
```

**That's it!** You'll see cascading in action with cost savings.

---

## 🎯 Quick Reference - Find What You Need

| Example | What It Does | Complexity | Time | Best For |
|---------|--------------|------------|------|----------|
| **basic-usage.ts** | Learn cascading basics | ⭐ Easy | 5 min | First-time users |
| **streaming-text.ts** | Real-time streaming | ⭐⭐ Medium | 10 min | Interactive apps |
| **tool-execution.ts** | Function calling | ⭐⭐ Medium | 15 min | Agent builders |
| **agentic-multi-agent.ts** | Tool loops + multi-agent | ⭐⭐⭐ Advanced | 20 min | Agentic apps |
| **cost-tracking.ts** | Budget management | ⭐⭐ Medium | 15 min | Cost optimization |
| **multi-provider.ts** | Mix AI providers | ⭐⭐ Medium | 10 min | Multi-cloud |
| **express-integration.ts** | REST API server | ⭐⭐⭐ Advanced | 20 min | Production APIs |
| **browser-usage.ts** | Browser integration | ⭐⭐⭐ Advanced | 25 min | Frontend apps |
| **vercel-edge.ts** | Edge deployment | ⭐⭐⭐ Advanced | 20 min | Serverless/Edge |
| **deno-example.ts** | Deno runtime | ⭐⭐ Medium | 15 min | Deno Deploy |

**💡 Tip:** Start with `basic-usage.ts`, then explore based on your use case!

---

## 🔍 Find by Feature

**I want to...**
- **Stream responses?** → `streaming-text.ts`, `streaming-tools.ts`
- **Use tools/functions?** → `tool-execution.ts`, `agentic-multi-agent.ts`, `streaming-tools.ts`
- **Track costs?** → `cost-tracking.ts`, `user-profiles-workflows.ts`
- **Use multiple providers?** → `multi-provider.ts`, `router-integration.ts`, `free-models-cascade.ts`
- **Deploy to production?** → `express-integration.ts`, `vercel-edge.ts`
- **Use in browser?** → `browser-usage.ts`
- **Run locally?** → `multi-instance-ollama.ts`, `multi-instance-vllm.ts`
- **Use with Deno?** → `deno-example.ts`
- **Validate quality?** → `semantic-quality.ts`, `custom-validation.ts`, `quality-profiles.ts`
- **Rate limit requests?** → `rate-limiting-usage.ts`
- **Manage user tiers?** → `user-profiles-workflows.ts`

---

## 📋 Table of Contents

- [🌟 Core Examples](#-core-examples-6-examples---start-here) - Basic usage, streaming, quality validation
- [🔧 Tools & Functions](#-tools--functions-3-examples) - Tool calling, execution, and tool loops
- [💰 Cost Management](#-cost-management-3-examples) - Budgets and tracking
- [🏭 Production](#-production--integration-2-examples) - Deployment patterns
- [🌐 Browser & Runtime](#-browser--runtime-support-3-examples) - Browser, Deno, Edge
- [⚡ Advanced](#-advanced-patterns-3-examples) - Custom validation and rate limiting
- [🔌 Providers](#-provider-examples-5-examples) - Multi-provider, Groq, HuggingFace, Together, Ollama

---

## 📚 Examples by Category

<details open>
<summary><h3>🌟 Core Examples (6 examples) - Start Here</h3></summary>

Perfect for learning cascadeflow basics. Start with these!

#### 1. Basic Usage ⭐ **START HERE**
**File:** [`basic-usage.ts`](basic-usage.ts)
**Time:** 5 minutes
**What you'll learn:**
- How cascading works (cheap model → expensive model)
- Automatic quality-based routing
- Cost tracking and savings
- When drafts are accepted vs rejected

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
npx tsx examples/nodejs/basic-usage.ts
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

#### 2. Quality Validation ✅
**File:** [`semantic-quality.ts`](semantic-quality.ts)
**Time:** 10 minutes
**What you'll learn:**
- How quality validation works
- Automatic draft/verifier comparison
- Confidence scoring
- Quality thresholds

**Key concept:** See how cascadeflow validates drafts before accepting them!

---

#### 3. Multiple Validators 🔍
**File:** [`quality-profiles.ts`](quality-profiles.ts)
**Time:** 10 minutes
**What you'll learn:**
- Combine multiple validation strategies
- Length-based validation
- Keyword-based validation
- Custom validator composition

---

#### 4. Streaming Text Responses 🌊
**File:** [`streaming-text.ts`](streaming-text.ts)
**Time:** 10 minutes
**What you'll learn:**
- Real-time text streaming
- See cascade decisions in action
- Stream event types (CHUNK, SWITCH, COMPLETE)
- Performance metrics

**Key concept:** Watch the cascade happen in real-time!

---

#### 5. User Profiles 👤
**File:** [`user-profiles-workflows.ts`](user-profiles-workflows.ts)
**Time:** 10 minutes
**What you'll learn:**
- User tier management (FREE, PRO, ENTERPRISE)
- Per-tier model configurations
- User-specific routing
- Tier-based cost tracking

**Use cases:**
- SaaS applications with pricing tiers
- Multi-tenant systems
- User-specific features

---

#### 6. Cost Tracking Example 💰
**File:** [`cost-tracking.ts`](cost-tracking.ts)
**Time:** 15 minutes
**What you'll learn:**
- Real-time cost monitoring
- Per-query cost tracking
- Total cost accumulation
- Model usage statistics

**Features:**
- Query-level cost breakdown
- Cumulative cost tracking
- Model attribution
- Savings calculation

</details>

<details>
<summary><h3>🔧 Tools & Functions (3 examples)</h3></summary>

Learn how to use tools and functions with cascadeflow.

#### 1. Tool Execution ⭐
**File:** [`tool-execution.ts`](tool-execution.ts)
**Time:** 15 minutes
**What you'll learn:**
- Define OpenAI-compatible function tools
- Execute single and multiple tool calls
- Handle multi-step tool workflows
- Tool error handling and validation

**4 Tool Types Demonstrated:**
1. **Weather Tool** - Get current weather for locations
2. **Calculator Tool** - Perform mathematical calculations
3. **Search Tool** - Web search simulation
4. **Email Tool** - Send email notifications

**Key Patterns:**
```typescript
const weatherTool = {
  type: 'function' as const,
  function: {
    name: 'get_weather',
    description: 'Get current weather for a location',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string', description: 'City name' },
        unit: { type: 'string', enum: ['celsius', 'fahrenheit'] },
      },
      required: ['location'],
    },
  },
};

// Execute tools
function executeToolCall(toolName: string, args: any): any {
  switch (toolName) {
    case 'get_weather': return executeWeatherTool(args);
    case 'calculate': return executeCalculatorTool(args);
    // ...
  }
}
```

**5 Complete Examples:**
1. Single tool call (weather query)
2. Multiple tool calls in parallel
3. Multi-step workflow
4. Tool error handling
5. Tool validation patterns

---

#### 2. Streaming Tools 🔄
**File:** [`streaming-tools.ts`](streaming-tools.ts)
**Time:** 15 minutes
**What you'll learn:**
- Real-time streaming with tool calls
- Progressive tool execution
- Multi-tool workflows
- Stream event types (CHUNK, TOOL_CALL, COMPLETE)

**Key difference:**
- `tool-execution.ts` = Complete workflow with execution
- `streaming-tools.ts` = Streaming + real-time tool execution

**4 Scenarios Demonstrated:**
1. Simple weather query with streaming
2. Multi-step calculation workflow
3. Parallel tool calls
4. Complex tool orchestration

---

#### 3. Agentic + Multi-Agent Tool Loop 🤖
**File:** [`agentic-multi-agent.ts`](agentic-multi-agent.ts)
**Time:** 20 minutes
**What you'll learn:**
- Multi-turn tool loop (persist assistant `tool_calls` + tool results)
- Executing tools with `ToolExecutor`
- Multi-agent orchestration with an “agent-as-a-tool” (`delegate_to_researcher`)
- Message list best practices (system prompt + tool history)

**Key pattern (tool loop):**
```typescript
messages.push({ role: 'assistant', content: result.content ?? '', tool_calls: result.toolCalls });
messages.push({ role: 'tool', tool_call_id: call.id, content: JSON.stringify(toolOutput) });
```

</details>

<details>
<summary><h3>💰 Cost Management (3 examples)</h3></summary>

Track costs, manage budgets, and optimize spending.

#### 1. Cost Tracking Example
**File:** [`cost-tracking.ts`](cost-tracking.ts)
Real-time cost monitoring with per-query tracking.

#### 2. User Profiles
**File:** [`user-profiles-workflows.ts`](user-profiles-workflows.ts)
Per-tier cost management and routing.

#### 3. Multi-Provider Example
**File:** [`multi-provider.ts`](multi-provider.ts)
Cross-provider cost comparison and optimization.

**Use cases:**
- SaaS applications with user tiers
- Multi-tenant systems
- Budget-aware routing
- Cost allocation by user

</details>

<details>
<summary><h3>🏭 Production & Integration (2 examples)</h3></summary>

Deploy cascadeflow to production with enterprise patterns.

#### 1. Express Integration ⭐
**File:** [`express-integration.ts`](express-integration.ts)
**Time:** 20 minutes
**What you'll learn:**
- REST API deployment with Express
- Server-Sent Events (SSE) streaming
- Error handling and validation
- Health checks and statistics

**Endpoints:**
- `POST /api/query` - Non-streaming queries
- `GET /api/query/stream` - SSE streaming
- `GET /health` - Health check
- `GET /api/stats` - Server statistics

**Production Features:**
- Request validation
- Error handling
- CORS support
- Logging
- Health monitoring

---

#### 2. Rate Limiting Usage
**File:** [`rate-limiting-usage.ts`](rate-limiting-usage.ts)
**Time:** 15 minutes
**What you'll learn:**
- Request throttling
- Queue management
- Rate limit configuration
- Backpressure handling

</details>

<details>
<summary><h3>🌐 Browser & Runtime Support (3 examples)</h3></summary>

Run cascadeflow in browser, Deno, and Edge environments.

#### 1. Browser Usage Guide ⭐
**File:** [`browser-usage.ts`](browser-usage.ts)
**Time:** 25 minutes
**What you'll learn:**
- Webpack configuration (polyfills, DefinePlugin)
- Vite configuration (recommended)
- React integration with custom hooks
- Vue integration with composables
- Production backend proxy setup
- Streaming in browser

**Topics Covered:**
1. **Webpack Configuration** - Polyfills and environment handling
2. **Vite Configuration** - Modern bundler setup (recommended)
3. **React Integration** - `useCascadeflow` custom hook
4. **Vue Integration** - Composables pattern
5. **Production Proxy** - Secure API key handling
6. **Browser Streaming** - Async iterator patterns

**React Hook Example:**
```typescript
export function useCascadeflow() {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<string>('');
  const [cost, setCost] = useState<number>(0);

  const query = useCallback(async (text: string) => {
    setLoading(true);
    const result = await agent.run(text);
    setResponse(result.content);
    setCost(result.totalCost);
    setLoading(false);
  }, []);

  return { query, loading, response, cost };
}
```

**Security:**
- ⚠️ Never expose API keys in client code
- ✅ Use backend proxy for production
- ✅ Proper environment variable handling

---

#### 2. Deno Example 🦕
**File:** [`deno-example.ts`](deno-example.ts)
**Time:** 15 minutes
**What you'll learn:**
- NPM imports (`npm:@cascadeflow/core`)
- Environment variables (`Deno.env`)
- Permission model (`--allow-net`, `--allow-env`)
- Deno Deploy edge functions
- Streaming with Deno
- Testing with Deno

**Deno-Specific Patterns:**
```typescript
import { CascadeAgent } from 'npm:@cascadeflow/core';

const apiKey = Deno.env.get('OPENAI_API_KEY');

Deno.serve(async (req: Request) => {
  const { query } = await req.json();
  const result = await agent.run(query);

  return new Response(JSON.stringify({
    content: result.content,
    cost: result.totalCost,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
```

**Key Differences:**
- No package.json or node_modules
- Native TypeScript support
- Secure by default (permissions)
- Web-standard APIs

---

#### 3. Vercel Edge Functions ⚡
**File:** [`vercel-edge.ts`](vercel-edge.ts)
**Time:** 20 minutes
**What you'll learn:**
- Edge runtime configuration
- Global distribution
- Streaming SSE patterns
- Environment variables
- Deployment workflow
- Performance optimization

**10 Patterns Covered:**
1. Project structure
2. Edge runtime config
3. Streaming SSE
4. Shared agent configuration
5. `vercel.json` setup
6. Environment variables
7. Client integration
8. Error handling
9. Deployment with GitHub Actions
10. Performance optimization

**Edge Runtime Configuration:**
```typescript
export const config = {
  runtime: 'edge',
};

export default async function handler(req: Request) {
  const { query } = await req.json();
  const result = await agent.run(query);

  return new Response(JSON.stringify({
    content: result.content,
    cost: result.totalCost,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
}
```

</details>

<details>
<summary><h3>⚡ Advanced Patterns (3 examples)</h3></summary>

Custom validation, rate limiting, and specialized configurations.

#### 1. Custom Validation
**File:** [`custom-validation.ts`](custom-validation.ts)
**Time:** 15 minutes
**What you'll learn:**
- Build custom quality validators
- Domain-specific validation
- Multiple validation strategies
- Validator composition

**4 Validator Types:**
1. **Length Validator** - Ensure minimum response length
2. **Keyword Validator** - Check for required keywords
3. **Format Validator** - Validate response structure
4. **Semantic Validator** - AI-based quality checks

---

#### 2. Rate Limiting Usage
**File:** [`rate-limiting-usage.ts`](rate-limiting-usage.ts)
Request throttling and queue management.

---

#### 3. Multiple Validators
**File:** [`quality-profiles.ts`](quality-profiles.ts)
Combine multiple validation strategies for robust quality control.

</details>

<details>
<summary><h3>🔌 Provider Examples (5 examples)</h3></summary>

Learn how to use different AI providers with cascadeflow.

#### 1. Multi-Provider Example ⭐
**File:** [`multi-provider.ts`](multi-provider.ts)
**Time:** 10 minutes
**What you'll learn:**
- Mix models from different providers
- OpenAI + Anthropic + Groq
- Provider-specific optimizations
- Cross-provider cost comparison

**Example setup:**
```typescript
const agent = new CascadeAgent({
  models: [
    {
      name: 'llama-3.1-8b-instant',
      provider: 'groq',
      cost: 0.00005,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
    },
    {
      name: 'claude-3-5-sonnet-20241022',
      provider: 'anthropic',
      cost: 0.003,
    },
  ],
});
```

---

#### 2. Groq Provider Example
**File:** [`free-models-cascade.ts`](free-models-cascade.ts)
**Time:** 10 minutes
Fast inference with Groq's LPU™ infrastructure.

**Features:**
- Ultra-low latency (300+ tokens/sec)
- Free tier available
- Llama 3.1 models
- Perfect for drafts

---

#### 3. HuggingFace Inference Example
**File:** [`free-models-cascade.ts`](free-models-cascade.ts)
**Time:** 10 minutes
Access HuggingFace hosted models.

---

#### 4. Together AI Example
**File:** [`free-models-cascade.ts`](free-models-cascade.ts)
**Time:** 10 minutes
Open-source models via Together AI.

---

#### 5. Ollama Example (Local)
**File:** [`free-models-cascade.ts`](free-models-cascade.ts)
**Time:** 15 minutes
Run models locally with Ollama.

**Use cases:**
- Privacy-first applications
- Zero API costs
- Offline operation
- Custom fine-tuned models

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.2:1b
ollama pull llama3.1:8b

# Run example
npx tsx examples/nodejs/free-models-cascade.ts
```

</details>

---

## 🎓 Learning Path

### Step 1: Basics (30 minutes)
1. ✅ Run `basic-usage.ts` - Understand core concepts
2. ✅ Read the code comments - Learn patterns
3. ✅ Try different queries - See routing decisions

**Key concepts:**
- Cascading = cheap model first, escalate if needed
- Draft accepted = money saved ✅
- Draft rejected = quality ensured ✅

### Step 2: Real-Time Features (30 minutes)
1. ✅ Run `streaming-text.ts` - See streaming
2. ✅ Run `tool-execution.ts` - Learn tool usage
3. ✅ Experiment with different tools

**Key concepts:**
- Streaming requires 2+ models
- Event-based architecture
- Tool execution workflow

### Step 3: Cost Management (30 minutes)
1. ✅ Run `cost-tracking.ts` - Learn cost tracking
2. ✅ Run `user-profiles-workflows.ts` - Per-tier management
3. ✅ Compare costs across providers

**Key concepts:**
- Per-query cost tracking
- Model attribution
- Cost optimization

### Step 4: Production (1 hour)
1. ✅ Run `express-integration.ts` - API deployment
2. ✅ Run `vercel-edge.ts` patterns - Edge deployment
3. ✅ Read `browser-usage.ts` - Frontend integration

**Key concepts:**
- Error handling
- Streaming SSE
- Production security

### Step 5: Customize (1 hour)
1. ✅ Run `custom-validation.ts` - Custom validators
2. ✅ Run `rate-limiting-usage.ts` - Request throttling
3. ✅ Modify for your use case

---

## 🛠️ Running Examples

### Prerequisites

```bash
# Install cascadeflow
npm install @cascadeflow/core
# or
pnpm add @cascadeflow/core

# Install peer dependencies (choose what you need)
npm install openai                # OpenAI
npm install @anthropic-ai/sdk     # Anthropic
npm install groq-sdk              # Groq
npm install @huggingface/inference # HuggingFace

# Or install all at once
npm install openai @anthropic-ai/sdk groq-sdk @huggingface/inference
```

### TypeScript Setup

Most examples use `tsx` for easy TypeScript execution:

```bash
# Install tsx globally (recommended)
npm install -g tsx

# Or use npx (no installation needed)
npx tsx examples/nodejs/basic-usage.ts
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

# HuggingFace
export HF_TOKEN="hf_..."
```

### Run Examples

```bash
# From repository root
npx tsx packages/core/examples/nodejs/basic-usage.ts
npx tsx packages/core/examples/nodejs/streaming-text.ts
npx tsx packages/core/examples/nodejs/tool-execution.ts

# Or navigate to examples directory
cd packages/core/examples/nodejs
npx tsx basic-usage.ts
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

# Windows (CMD)
set OPENAI_API_KEY=sk-...

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-..."
```
</details>

<details>
<summary><b>Import errors</b></summary>

```bash
# Install cascadeflow
npm install @cascadeflow/core

# Install peer dependencies
npm install openai @anthropic-ai/sdk groq-sdk

# Or use pnpm
pnpm add @cascadeflow/core openai @anthropic-ai/sdk groq-sdk
```
</details>

<details>
<summary><b>tsx not found</b></summary>

```bash
# Install tsx globally
npm install -g tsx

# Or use npx (no installation)
npx tsx examples/nodejs/basic-usage.ts

# Or use ts-node
npm install -g ts-node
ts-node examples/nodejs/basic-usage.ts
```
</details>

<details>
<summary><b>TypeScript errors</b></summary>

```bash
# Check TypeScript version (5.3+ required)
npx tsc --version

# Install TypeScript
npm install -D typescript

# Type check examples
npm run typecheck:examples
```
</details>

<details>
<summary><b>Module resolution errors</b></summary>

If you see errors like "Cannot find module '@cascadeflow/core'":

```bash
# Make sure you're in the right directory
cd packages/core

# Build the package first
npm run build

# Then run examples
npx tsx examples/nodejs/basic-usage.ts
```
</details>

---

## 💡 Pro Tips

### 1. Start Simple
Begin with `basic-usage.ts` before advanced examples.

### 2. Read the Code
All examples are heavily commented. Read through to understand patterns.

### 3. Key Concepts

**Streaming vs Execution:**
- `streaming-tools.ts` = Watch tool calls + execute in real-time
- `tool-execution.ts` = Complete tool workflow patterns
- Both demonstrate actual tool execution

**Cost Tracking:**
- Access via `result.totalCost`
- Per-model costs in `result.metadata`
- Use TypeScript types for safety

**Quality Validation:**
- Draft accepted = cheap model only (saves money!)
- Draft rejected = both models called (ensures quality)
- Adjust thresholds based on use case

### 4. Watch Statistics

```typescript
const result = await agent.run(query);

// TypeScript provides autocomplete!
console.log(`Cost: $${result.totalCost}`);
console.log(`Model: ${result.modelUsed}`);
console.log(`Cascaded: ${result.metadata.cascaded}`);
console.log(`Tokens: ${result.metadata.totalTokens}`);
```

### 5. Type Safety

TypeScript provides excellent autocomplete and type checking:

```typescript
import { CascadeAgent, ModelConfig, CascadeResult } from '@cascadeflow/core';

// Full type safety
const config: ModelConfig = {
  name: 'gpt-4o-mini',
  provider: 'openai',
  cost: 0.00015,
};

// Result types
const result: CascadeResult = await agent.run(query);
```

---

## 📖 Complete Documentation

### API Documentation
- [TypeScript API Docs](../../README.md) - Full API reference (TypeDoc)
- [Python API Docs](../../../../README.md) - Python API reference

### Migration Guide
- [Python → TypeScript Migration](../../MIGRATION.md) - Complete migration guide

### Getting Started Guides
- [Quick Start](../../../../docs/guides/quickstart.md) - 5-minute introduction
- [Providers Guide](../../../../docs/guides/providers.md) - Configure AI providers
- [Streaming Guide](../../../../docs/guides/streaming.md) - Real-time responses
- [Tools Guide](../../../../docs/guides/tools.md) - Function calling
- [Cost Tracking](../../../../docs/guides/cost_tracking.md) - Budget management

### Advanced Guides
- [Production Guide](../../../../docs/guides/production.md) - Enterprise deployment
- [Performance Guide](../../../../docs/guides/performance.md) - Optimization
- [Custom Cascade](../../../../docs/guides/custom_cascade.md) - Custom routing
- [Custom Validation](../../../../docs/guides/custom_validation.md) - Quality control
- [Browser Cascading](../../../../docs/guides/browser_cascading.md) - Browser deployment
- [n8n Integration](../../../../docs/guides/n8n_integration.md) - No-code automation

📚 **[View All Documentation →](../../../../docs/)**

---

## 🤝 Contributing Examples

Have a great use case? Contribute an example!

### Template

```typescript
/**
 * Your Example - Brief Description
 *
 * What it demonstrates:
 * - Feature 1
 * - Feature 2
 *
 * Requirements:
 * - @cascadeflow/core
 * - openai (or other providers)
 *
 * Setup:
 *     npm install @cascadeflow/core openai
 *     export OPENAI_API_KEY="sk-..."
 *     npx tsx examples/nodejs/your-example.ts
 *
 * Expected Results:
 *     Description of output
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('YOUR EXAMPLE TITLE');
  console.log('='.repeat(80));

  // Your code here

  console.log('\nKEY TAKEAWAYS:');
  console.log('- Takeaway 1');
  console.log('- Takeaway 2');
}

main().catch(console.error);
```

See [CONTRIBUTING.md](../../../../CONTRIBUTING.md) for guidelines.

---

## 📞 Need Help?

### Documentation
📖 [Complete Guides](../../../../docs/guides/)
🌊 [Streaming Guide](../../../../docs/guides/streaming.md)
🛠️ [Tools Guide](../../../../docs/guides/tools.md)
💰 [Cost Tracking Guide](../../../../docs/guides/cost_tracking.md)
🏭 [Production Guide](../../../../docs/guides/production.md)
🔄 [Migration Guide](../../MIGRATION.md)

### Community
💬 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions) - Ask questions
🐛 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues) - Report bugs
💡 Use "question" label for general questions

---

## 📊 Summary

### ✅ Available Examples (19 total)

**Core (6):** Basic usage, quality validation, multiple validators, streaming text, user profiles, cost tracking

**Tools (2):** Tool execution, streaming tools

**Cost Management (3):** Cost tracking, user profiles, multi-provider comparison

**Production (2):** Express integration, rate limiting

**Browser & Runtime (3):** Browser usage, Deno, Vercel Edge

**Advanced (3):** Custom validation, rate limiting, multiple validators

**Providers (5):** Multi-provider, Groq, HuggingFace, Together, Ollama

### 📚 Documentation Coverage

- ✅ **19 TypeScript examples** (~4,500+ lines of code)
- ✅ **Complete API documentation** (TypeDoc)
- ✅ **Migration guide** (Python → TypeScript)
- ✅ **Browser/Runtime guides** (React, Vue, Deno, Vercel Edge)
- ✅ **100% feature parity with Python**

### 🔑 Key Learnings

**Essential Concepts:**
- ✅ Draft accepted = money saved
- ✅ Draft rejected = quality ensured
- ✅ Streaming requires 2+ models
- ✅ Full TypeScript type safety
- ✅ Multiple runtime support (Node.js, Deno, Browser, Edge)

**Production Ready:**
- ✅ Express API integration
- ✅ Edge function deployment
- ✅ Browser integration (React, Vue)
- ✅ Error handling patterns
- ✅ Rate limiting
- ✅ Cost tracking

---

**💰 Save 40-85% on AI costs with intelligent cascading!** 🚀

[TypeScript API Docs](../../README.md) • [Python Examples](../../../../examples/) • [Migration Guide](../../MIGRATION.md) • [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions)
