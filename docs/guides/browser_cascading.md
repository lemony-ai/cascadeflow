# Browser Cascading Guide

This guide shows how to use CascadeFlow in browser environments for client-side AI applications.

## Table of Contents

1. [Overview](#overview)
2. [Security First](#security-first)
3. [Architecture Patterns](#architecture-patterns)
4. [Quick Start](#quick-start)
5. [Examples](#examples)
6. [Production Deployment](#production-deployment)
7. [Cost Tracking](#cost-tracking)
8. [Best Practices](#best-practices)

---

## Overview

CascadeFlow's TypeScript library enables **browser-based AI applications** with the same 40-85% cost savings as the Python version.

### Why Browser Cascading?

✅ **Lower Latency** - Edge functions run globally, close to users
✅ **Better UX** - Real-time AI responses in web apps
✅ **Cost Savings** - Same cascade logic, 40-85% cheaper than direct API calls
✅ **Scalability** - Serverless auto-scaling for traffic spikes

### Supported Environments

| Environment | Status | Best For |
|-------------|--------|----------|
| Node.js 18+ | ✅ Production | Backend APIs, CLI tools |
| Vercel Edge | ✅ Production | Global web apps |
| Cloudflare Workers | ✅ Production | Ultra-low latency |
| Browser (direct) | ⚠️ With proxy | When you control the proxy |
| Deno | 🔜 Coming soon | Edge runtime |

---

## Security First

**⚠️ CRITICAL: Never expose API keys in browser code!**

```typescript
// ❌ NEVER DO THIS
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', apiKey: 'sk-...' }  // ❌ Exposed to users!
  ]
});
```

```typescript
// ✅ ALWAYS USE A BACKEND PROXY
const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      proxyUrl: '/api/cascade'  // ✅ API key stays on server
    }
  ]
});
```

### Why This Matters

- API keys in browser code can be stolen from DevTools
- Attackers can drain your OpenAI credits
- Keys can be scraped from bundled JavaScript

**Solution:** Always use a backend proxy or edge function.

---

## Architecture Patterns

### Pattern 1: Edge Function (Recommended)

**Best for:** Public web apps, global users, low latency

```
User Browser
    ↓
Edge Function (Vercel/Cloudflare)
    ├── CascadeFlow Logic
    └── API Key (secure)
    ↓
OpenAI API
```

**Pros:**
- Global distribution (runs close to users)
- No infrastructure management
- Auto-scaling
- Secure (API keys never exposed)

**Cons:**
- Vendor-specific (Vercel, Cloudflare)
- Cold starts (minimal with edge)

**Code:**
```typescript
// Edge function (api/chat.ts)
import { CascadeAgent } from '@cascadeflow/core';

export default async function handler(req: Request) {
  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY }
    ]
  });

  const { query } = await req.json();
  const result = await agent.run(query);

  return Response.json(result);
}
```

---

### Pattern 2: Backend API + Browser Client

**Best for:** Enterprise apps, existing backends, fine-grained control

```
User Browser
    ↓ fetch('/api/cascade')
Backend API (Express/Fastify)
    ├── CascadeFlow Logic
    └── API Key (secure)
    ↓
OpenAI API
```

**Pros:**
- Full control over infrastructure
- Can add custom auth, rate limiting
- Works with any backend framework

**Cons:**
- Need to manage servers
- Single region (higher latency for global users)

**Code:**
```typescript
// Backend (Express)
import { CascadeAgent } from '@cascadeflow/core';
import express from 'express';

const app = express();
app.use(express.json());

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY }
  ]
});

app.post('/api/cascade', async (req, res) => {
  const result = await agent.run(req.body.query);
  res.json(result);
});

app.listen(3000);
```

```javascript
// Frontend (Browser)
const response = await fetch('/api/cascade', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'What is TypeScript?' })
});

const result = await response.json();
console.log(`Saved ${result.savingsPercentage}%`);
```

---

### Pattern 3: Multi-Provider Browser Support

**Best for:** Using multiple AI providers in browser environments

All CascadeFlow providers automatically work in both Node.js and browser environments through runtime detection:

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// All providers work in browser automatically!
const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      proxyUrl: 'https://your-proxy.com/api/openai'  // Your proxy
    },
    {
      name: 'claude-3-haiku',
      provider: 'anthropic',
      cost: 0.00075,
      proxyUrl: 'https://your-proxy.com/api/anthropic'  // Your proxy
    }
  ]
});

const result = await agent.run('Hello!');
```

**Supported providers in browser:**
- ✅ OpenAI (automatic runtime detection)
- ✅ Anthropic (automatic runtime detection)
- ✅ Groq (automatic runtime detection)
- ✅ Together AI
- ✅ Ollama
- ✅ HuggingFace
- ✅ vLLM

---

## Quick Start

### 1. Install

```bash
npm install @cascadeflow/core openai
```

### 2. Choose Your Deployment

#### Option A: Vercel Edge Function (60 seconds)

```bash
# Clone example
git clone https://github.com/cascadeflow/examples
cd examples/browser/vercel-edge

# Set API key
vercel env add OPENAI_API_KEY

# Deploy
vercel deploy --prod
```

#### Option B: Express Backend (5 minutes)

```bash
# Create project
mkdir my-cascade-app && cd my-cascade-app
npm init -y
npm install @cascadeflow/core openai express dotenv

# Create .env
echo "OPENAI_API_KEY=sk-..." > .env

# Create server.js (see Pattern 2 above)

# Run
node server.js
```

---

## Examples

### Example 1: Simple Web App

**HTML:**
```html
<!DOCTYPE html>
<html>
<head>
  <title>CascadeFlow Demo</title>
</head>
<body>
  <textarea id="query" placeholder="Ask anything..."></textarea>
  <button onclick="ask()">Ask AI</button>
  <div id="result"></div>
  <div id="savings"></div>

  <script>
    async function ask() {
      const query = document.getElementById('query').value;

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      const result = await response.json();

      document.getElementById('result').textContent = result.content;
      document.getElementById('savings').textContent =
        `Saved ${result.savingsPercentage}% vs best model`;
    }
  </script>
</body>
</html>
```

**Edge Function (api/chat.ts):**
```typescript
import { CascadeAgent } from '@cascadeflow/core';

export const config = { runtime: 'edge' };

export default async function handler(req: Request) {
  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY }
    ]
  });

  const { query } = await req.json();
  const result = await agent.run(query);

  return Response.json(result);
}
```

---

### Example 2: React App

```tsx
import { useState } from 'react';

function CascadeChat() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    const data = await response.json();
    setResult(data);
  }

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything..."
        />
        <button type="submit">Ask AI</button>
      </form>

      {result && (
        <div>
          <p>{result.content}</p>
          <p>💰 Saved {result.savingsPercentage}% vs best model</p>
          <p>⚡ {result.latencyMs}ms</p>
        </div>
      )}
    </div>
  );
}
```

---

### Example 3: Next.js API Route

```typescript
// app/api/cascade/route.ts
import { CascadeAgent } from '@cascadeflow/core';
import { NextRequest } from 'next/server';

export async function POST(req: NextRequest) {
  const { query } = await req.json();

  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY }
    ]
  });

  const result = await agent.run(query);

  return Response.json(result);
}
```

---

## Production Deployment

### Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Set environment variables
vercel env add OPENAI_API_KEY

# Deploy
vercel deploy --prod
```

**vercel.json:**
```json
{
  "functions": {
    "api/**/*.ts": {
      "maxDuration": 30
    }
  }
}
```

---

### Cloudflare Workers

```bash
# Install Wrangler
npm install -g wrangler

# Set secrets
wrangler secret put OPENAI_API_KEY

# Deploy
wrangler deploy
```

**wrangler.toml:**
```toml
name = "cascadeflow-worker"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[env.production]
vars = { ENVIRONMENT = "production" }
```

---

### Railway / Render / Fly.io

```bash
# Set environment variable
export OPENAI_API_KEY=sk-...

# Deploy (platform-specific)
railway up  # Railway
render deploy  # Render
fly deploy  # Fly.io
```

---

## Cost Tracking

### Display Savings to Users

```javascript
const result = await agent.run(query);

// Show savings
console.log(`💰 Saved ${result.savingsPercentage}%`);
console.log(`📊 Cost: $${result.totalCost.toFixed(6)}`);
console.log(`🎯 Model: ${result.modelUsed}`);

// Alert if cascade failed
if (!result.draftAccepted) {
  console.log('⚠️ Draft rejected, escalated to verifier');
}
```

### Aggregate Analytics

```typescript
// Track cumulative savings
let totalSaved = 0;
let totalCost = 0;

async function runWithTracking(query: string) {
  const result = await agent.run(query);

  totalCost += result.totalCost;
  totalSaved += result.costSaved || 0;

  console.log(`Total saved: $${totalSaved.toFixed(4)}`);
  console.log(`Total cost: $${totalCost.toFixed(4)}`);

  return result;
}
```

---

## Best Practices

### 1. Rate Limiting

Protect your API from abuse:

```typescript
// Simple in-memory rate limiter
const rateLimiter = new Map();

export default async function handler(req: Request) {
  const ip = req.headers.get('x-forwarded-for');
  const now = Date.now();

  if (rateLimiter.has(ip)) {
    const lastRequest = rateLimiter.get(ip);
    if (now - lastRequest < 1000) {  // 1 request per second
      return new Response('Rate limit exceeded', { status: 429 });
    }
  }

  rateLimiter.set(ip, now);

  // ... rest of handler
}
```

### 2. Error Handling

```typescript
export default async function handler(req: Request) {
  try {
    const agent = new CascadeAgent({ /* config */ });
    const result = await agent.run(query);
    return Response.json(result);
  } catch (error) {
    console.error('Cascade error:', error);
    return new Response(
      JSON.stringify({ error: 'Failed to process request' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
```

### 3. CORS Configuration

```typescript
export default async function handler(req: Request) {
  // Handle preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': 'https://yourdomain.com',
        'Access-Control-Allow-Methods': 'POST',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  const result = await agent.run(query);

  return new Response(JSON.stringify(result), {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': 'https://yourdomain.com',
    },
  });
}
```

### 4. Monitoring

```typescript
import * as Sentry from '@sentry/node';

export default async function handler(req: Request) {
  const startTime = Date.now();

  try {
    const result = await agent.run(query);

    // Log metrics
    Sentry.metrics.distribution('cascade.latency', Date.now() - startTime);
    Sentry.metrics.distribution('cascade.cost', result.totalCost);
    Sentry.metrics.distribution('cascade.savings', result.savingsPercentage);

    return Response.json(result);
  } catch (error) {
    Sentry.captureException(error);
    throw error;
  }
}
```

---

## Troubleshooting

### "API key not found"

**Solution:** Set environment variable in your deployment platform:

```bash
# Vercel
vercel env add OPENAI_API_KEY

# Cloudflare
wrangler secret put OPENAI_API_KEY

# Railway
railway variables set OPENAI_API_KEY=sk-...
```

### CORS Errors

**Solution:** Add proper CORS headers:

```typescript
headers: {
  'Access-Control-Allow-Origin': '*',  // Or specific domain
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
}
```

### Timeout Errors

**Solution:** Increase function timeout:

```json
// vercel.json
{
  "functions": {
    "api/**/*.ts": {
      "maxDuration": 60  // 60 seconds
    }
  }
}
```

### High Costs

**Solution:** Check cascade is working:

```typescript
const result = await agent.run(query);

if (result.draftAccepted) {
  console.log('✅ Draft accepted (cheap)');
} else {
  console.log('⚠️ Escalated to verifier (expensive)');
  console.log('Reason:', result.rejectionReason);
}
```

---

## Learn More

- [Complete Examples](../../packages/core/examples/browser/)
- [Vercel Edge Functions](https://vercel.com/docs/functions/edge-functions)
- [Cloudflare Workers](https://developers.cloudflare.com/workers/)
- [CascadeFlow API Reference](../api/)
- [Cost Optimization Guide](./cost_tracking.md)

---

**Next Steps:**
- Try the [Vercel Edge example](../../packages/core/examples/browser/vercel-edge/)
- Read the [Cost Tracking Guide](./cost_tracking.md)
- Explore [Production Patterns](./production.md)
