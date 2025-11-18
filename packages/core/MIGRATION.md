# Migration Guide: Python → TypeScript

This guide helps you migrate from cascadeflow Python to TypeScript (Node.js/Browser).

---

## 🚀 Quick Start

### Python
```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
])

result = await agent.run("What is Python?")
print(result.content)
```

### TypeScript
```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
});

const result = await agent.run('What is TypeScript?');
console.log(result.content);
```

**Key Differences:**
- ✅ Use `import` instead of `from ... import`
- ✅ `new CascadeAgent({...})` with object parameter
- ✅ Models are plain objects, not `ModelConfig()` calls
- ✅ Use `console.log()` instead of `print()`

---

## 📦 Installation

### Python
```bash
pip install cascadeflow[all]
```

### TypeScript/Node.js
```bash
npm install @cascadeflow/core
# or
pnpm add @cascadeflow/core
# or
yarn add @cascadeflow/core
```

---

## 🔧 API Differences

### 1. Creating an Agent

#### Python
```python
from cascadeflow import CascadeAgent

agent = CascadeAgent(
    models=[...],
    quality={"threshold": 0.7},
    enable_caching=True
)
```

#### TypeScript
```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [...],
  quality: { threshold: 0.7 },
  caching: { enabled: true }
});
```

---

### 2. Running Queries

#### Python
```python
# Async
result = await agent.run("query", max_tokens=100)

# Sync (not recommended)
result = agent.run_sync("query")
```

#### TypeScript
```typescript
// Async (only option - Node.js is async)
const result = await agent.run('query', { maxTokens: 100 });

// Note: No sync version (Node.js is async-first)
```

**Parameter Naming:**
- Python: `max_tokens` (snake_case)
- TypeScript: `maxTokens` (camelCase)

---

### 3. User Profiles

#### Python
```python
from cascadeflow import createUserProfile

profile = createUserProfile(
    tier="PRO",
    userId="user123",
    customRequestsPerHour=500
)
```

#### TypeScript
```typescript
import { createUserProfile } from '@cascadeflow/core';

const profile = createUserProfile(
  'PRO',           // tier (first parameter)
  'user123',       // userId (second parameter)
  {                // options (third parameter)
    customRequestsPerHour: 500
  }
);
```

**⚠️ Important:** TypeScript uses positional parameters, not keyword arguments!

---

### 4. Streaming

#### Python
```python
from cascadeflow.streaming import StreamEventType

async for event in agent.stream("query"):
    if event.type == StreamEventType.CHUNK:
        print(event.content, end="", flush=True)
    elif event.type == StreamEventType.COMPLETE:
        print(f"\nCost: ${event.data['result']['total_cost']}")
```

#### TypeScript
```typescript
import { StreamEventType } from '@cascadeflow/core';

for await (const event of agent.stream('query')) {
  if (event.type === StreamEventType.CHUNK) {
    process.stdout.write(event.content);
  } else if (event.type === StreamEventType.COMPLETE) {
    console.log(`\nCost: $${event.data.result.totalCost}`);
  }
}
```

**Differences:**
- `for await...of` instead of `async for...in`
- `===` instead of `==` for comparison
- `process.stdout.write()` instead of `print(..., end="")`
- `event.data.result.totalCost` (camelCase) instead of `event.data['result']['total_cost']` (snake_case)

---

### 5. Rate Limiting

#### Python
```python
from cascadeflow import RateLimiter, createUserProfile

limiter = RateLimiter()
profile = createUserProfile(tier="FREE", userId="user")

# Check limit
await limiter.check_rate_limit(profile)

# Record request
await limiter.record_request(profile.userId, cost=0.01)

# Get stats
stats = await limiter.get_usage_stats(profile.userId)
print(f"Requests: {stats['hourly_requests']}")
```

#### TypeScript
```typescript
import { RateLimiter, createUserProfile } from '@cascadeflow/core';

const limiter = new RateLimiter();
const profile = createUserProfile('FREE', 'user');

// Check limit
await limiter.checkRateLimit(profile);

// Record request
await limiter.recordRequest(profile.userId, 0.01);

// Get stats
const stats = await limiter.getUsageStats(profile.userId);
console.log(`Requests: ${stats.hourlyRequests}`);
```

**Differences:**
- Method names are camelCase: `check_rate_limit` → `checkRateLimit`
- Property names are camelCase: `hourly_requests` → `hourlyRequests`
- Use `new` keyword for classes

---

## 🎯 Common Patterns

### Pattern 1: Error Handling

#### Python
```python
try:
    result = await agent.run("query")
except Exception as e:
    print(f"Error: {e}")
```

#### TypeScript
```typescript
try {
  const result = await agent.run('query');
} catch (error) {
  console.error('Error:', error);
  // Type-safe error handling
  if (error instanceof Error) {
    console.log(error.message);
  }
}
```

---

### Pattern 2: Custom Validation

#### Python
```python
class MyValidator:
    def validate(self, response: str, query: str = "") -> dict:
        return {
            "passed": len(response) > 10,
            "score": 0.8,
            "reason": "Length check",
            "checks": {"min_length": True},
            "violations": []
        }

validator = MyValidator()
result = validator.validate("test response")
```

#### TypeScript
```typescript
interface ValidationResult {
  passed: boolean;
  score: number;
  reason: string;
  checks: Record<string, boolean>;
  violations: string[];
}

class MyValidator {
  validate(response: string, query: string = ''): ValidationResult {
    return {
      passed: response.length > 10,
      score: 0.8,
      reason: 'Length check',
      checks: { minLength: true },
      violations: []
    };
  }
}

const validator = new MyValidator();
const result = validator.validate('test response');
```

**Benefits of TypeScript:**
- ✅ Compile-time type checking
- ✅ IntelliSense/autocomplete
- ✅ Refactoring safety
- ✅ Better IDE support

---

### Pattern 3: Express/FastAPI Integration

#### Python (FastAPI)
```python
from fastapi import FastAPI
from cascadeflow import CascadeAgent

app = FastAPI()
agent = CascadeAgent(models=[...])

@app.post("/api/query")
async def query(request: dict):
    result = await agent.run(request["query"])
    return {"content": result.content, "cost": result.total_cost}
```

#### TypeScript (Express)
```typescript
import express from 'express';
import { CascadeAgent } from '@cascadeflow/core';

const app = express();
const agent = new CascadeAgent({ models: [...] });

app.post('/api/query', async (req, res) => {
  const result = await agent.run(req.body.query);
  res.json({ content: result.content, cost: result.totalCost });
});

app.listen(8000);
```

See `examples/nodejs/express-integration.ts` for complete example.

---

## 📊 Type System Comparison

### Python Type Hints
```python
from typing import Optional, Dict, List

def process(
    query: str,
    max_tokens: Optional[int] = None,
    metadata: Dict[str, str] = {}
) -> List[str]:
    return ["result"]
```

### TypeScript Types
```typescript
function process(
  query: string,
  maxTokens?: number,
  metadata: Record<string, string> = {}
): string[] {
  return ['result'];
}
```

**TypeScript Advantages:**
- ✅ Types enforced at compile-time (catches errors before runtime)
- ✅ Better IDE integration
- ✅ No runtime overhead
- ✅ Interfaces and generics

---

## 🌐 Environment-Specific Features

### TypeScript-Only Features

#### 1. Browser Support
```typescript
// Works in browser!
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [{ name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 }],
  apiKey: process.env.OPENAI_API_KEY // or from user input
});

// Use in React, Vue, etc.
```

#### 2. Deno Support
```typescript
import { CascadeAgent } from 'npm:@cascadeflow/core';

const agent = new CascadeAgent({...});
```

#### 3. Edge Runtime (Vercel, Cloudflare Workers)
```typescript
// Vercel Edge
export const config = { runtime: 'edge' };

export default async function handler(req: Request) {
  const agent = new CascadeAgent({...});
  const result = await agent.run('query');
  return new Response(JSON.stringify(result));
}
```

---

## 📝 Complete Example Comparison

### Python
```python
import asyncio
from cascadeflow import CascadeAgent, ModelConfig, RateLimiter, createUserProfile

async def main():
    # Create agent
    agent = CascadeAgent(models=[
        ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig("gpt-4o", provider="openai", cost=0.00625),
    ])

    # Create user profile
    profile = createUserProfile(tier="PRO", userId="user123")

    # Rate limiting
    limiter = RateLimiter()
    await limiter.check_rate_limit(profile)

    # Run query
    result = await agent.run("Explain quantum computing", max_tokens=200)

    # Record usage
    await limiter.record_request(profile.userId, result.total_cost)

    # Print results
    print(f"Response: {result.content[:100]}...")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Model: {result.model_used}")

if __name__ == "__main__":
    asyncio.run(main())
```

### TypeScript
```typescript
import { CascadeAgent, RateLimiter, createUserProfile } from '@cascadeflow/core';

async function main() {
  // Create agent
  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
    ],
  });

  // Create user profile
  const profile = createUserProfile('PRO', 'user123');

  // Rate limiting
  const limiter = new RateLimiter();
  await limiter.checkRateLimit(profile);

  // Run query
  const result = await agent.run('Explain quantum computing', { maxTokens: 200 });

  // Record usage
  await limiter.recordRequest(profile.userId, result.totalCost);

  // Print results
  console.log(`Response: ${result.content.substring(0, 100)}...`);
  console.log(`Cost: $${result.totalCost.toFixed(6)}`);
  console.log(`Model: ${result.modelUsed}`);
}

main().catch(console.error);
```

---

## 🔄 Quick Reference

| Feature | Python | TypeScript |
|---------|--------|------------|
| **Import** | `from cascadeflow import X` | `import { X } from '@cascadeflow/core'` |
| **Agent Init** | `CascadeAgent(models=[...])` | `new CascadeAgent({ models: [...] })` |
| **Parameter Style** | `snake_case` | `camelCase` |
| **Async Loop** | `async for x in y:` | `for await (const x of y)` |
| **Print** | `print(x)` | `console.log(x)` |
| **Dict Access** | `data['key']` or `data.key` | `data.key` |
| **Type Hints** | `Optional[str]` | `string \| undefined` or `string?` |
| **Error Handling** | `except Exception as e` | `catch (error)` |
| **String Format** | `f"Cost: ${cost}"` | `` `Cost: $${cost}` `` |
| **Classes** | `class X:` | `class X {` |
| **Methods** | `def method(self):` | `method() {` |

---

## 📚 Additional Resources

- **TypeScript Examples:** `packages/core/examples/nodejs/`
- **API Documentation:** (Coming soon - TypeDoc)
- **TypeScript Handbook:** https://www.typescriptlang.org/docs/
- **Node.js Async Guide:** https://nodejs.org/en/docs/guides/
- **Express Guide:** https://expressjs.com/

---

## 🆘 Common Issues

### Issue 1: `createUserProfile` signature error
**Python:**
```python
profile = createUserProfile(userId="user", tier="PRO")
```

**TypeScript (WRONG):**
```typescript
// ❌ This won't work!
const profile = createUserProfile({ userId: 'user', tier: 'PRO' });
```

**TypeScript (CORRECT):**
```typescript
// ✅ Use positional parameters
const profile = createUserProfile('PRO', 'user');
```

---

### Issue 2: Import paths
**Python:**
```python
from cascadeflow import CascadeAgent
from cascadeflow.streaming import StreamEventType
```

**TypeScript:**
```typescript
// ✅ Everything from main package
import { CascadeAgent, StreamEventType } from '@cascadeflow/core';
```

---

### Issue 3: Async/await required
**Python:**
```python
# Sync version exists
result = agent.run_sync("query")
```

**TypeScript:**
```typescript
// ❌ No sync version
const result = agent.run('query');  // Returns Promise, needs await

// ✅ Must use await
const result = await agent.run('query');
```

---

## ✅ Migration Checklist

- [ ] Install `@cascadeflow/core` package
- [ ] Change `from ... import` to `import { ... } from`
- [ ] Add `new` keyword to class instantiations
- [ ] Convert `snake_case` to `camelCase` for methods/properties
- [ ] Update parameter passing (keyword → object parameters)
- [ ] Change `print()` to `console.log()`
- [ ] Update string formatting (f-strings → template literals)
- [ ] Add type annotations (optional but recommended)
- [ ] Test with `npx tsx your-file.ts`
- [ ] Review TypeScript-specific features (browser, Deno, Edge)

---

**Need Help?** Check the examples in `packages/core/examples/nodejs/` for working code!
