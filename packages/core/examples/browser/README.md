# Browser Examples for cascadeflow

This directory contains examples for using cascadeflow in browser environments.

## Security Note

**NEVER expose API keys in browser code!** All examples use a backend proxy or edge function to securely handle API keys.

## Examples

### 1. Vercel Edge Function (`vercel-edge/`)

Deploy cascadeflow as a Vercel Edge Function for global, low-latency inference.

**Pros:**
- Global edge network (low latency)
- Serverless (no infrastructure)
- Easy deployment

**Cons:**
- Vendor lock-in (Vercel)
- Cold starts

### 2. Cloudflare Worker (`cloudflare-worker/`)

Run cascadeflow on Cloudflare's edge network.

**Pros:**
- Extremely fast (runs closest to user)
- Free tier available
- No cold starts

**Cons:**
- Limited execution time
- Cloudflare-specific API

### 3. Simple Express Backend (`express-backend/`)

Traditional Node.js/Express backend API.

**Pros:**
- Full control
- Can run anywhere (self-hosted)
- No vendor lock-in

**Cons:**
- Need to manage infrastructure
- Higher latency (single region)

### 4. Client-Side HTML (`simple-html/`)

Pure HTML/JS example that calls a backend API.

**Pros:**
- Simple to understand
- Works with any backend
- No build step needed

**Cons:**
- Still requires backend for API keys

## Quick Start

### Option 1: Vercel Edge Function (Recommended)

```bash
cd vercel-edge
npm install
vercel dev  # Test locally
vercel deploy  # Deploy to production
```

### Option 2: Express Backend

```bash
cd express-backend
npm install
npm start
# Open simple-html/index.html in browser
```

### Option 3: Cloudflare Worker

```bash
cd cloudflare-worker
npm install
npx wrangler dev  # Test locally
npx wrangler deploy  # Deploy to Cloudflare
```

## Usage Patterns

### Pattern 1: Edge Function (Serverless)

Best for: Public-facing apps, global users, low latency

```typescript
// Edge function handles everything
import { CascadeAgent } from '@cascadeflow/core';

export default async function handler(req: Request) {
  // Recommended: Claude Haiku + GPT-5
  const agent = new CascadeAgent({
    models: [
      { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008, apiKey: process.env.ANTHROPIC_API_KEY },
      { name: 'gpt-5', provider: 'openai', cost: 0.00125, apiKey: process.env.OPENAI_API_KEY }
    ]
  });

  const { query } = await req.json();
  const result = await agent.run(query);

  return Response.json(result);
}
```

### Pattern 2: Backend API + Frontend

Best for: Enterprise apps, existing backends, fine-grained control

```typescript
// Backend (Express)
app.post('/api/cascade', async (req, res) => {
  const agent = new CascadeAgent({ /* config */ });
  const result = await agent.run(req.body.query);
  res.json(result);
});

// Frontend (Browser)
const response = await fetch('/api/cascade', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'What is TypeScript?' })
});
const result = await response.json();
```

### Pattern 3: Direct Browser (Multi-Provider Support)

Best for: When you already have a proxy endpoint

All providers automatically work in browser through runtime detection:

```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'claude-3-5-haiku-20241022',
      provider: 'anthropic',
      cost: 0.0008,
      proxyUrl: '/api/anthropic-proxy'  // Your proxy endpoint
    },
    {
      name: 'gpt-5',
      provider: 'openai',
      cost: 0.00125,
      proxyUrl: '/api/openai-proxy'  // Your proxy endpoint
    }
  ]
});

const result = await agent.run('Hello!');
console.log(`Savings: ${result.savingsPercentage}%`);
```

**All 7 providers work in browser:**
OpenAI, Anthropic, Groq, Together AI, Ollama, HuggingFace, vLLM

## Environment Variables

All examples require:

```bash
OPENAI_API_KEY=sk-...
```

For Vercel:
```bash
vercel env add OPENAI_API_KEY
```

For Cloudflare:
```bash
npx wrangler secret put OPENAI_API_KEY
```

For Express:
```bash
# Create .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

## Cost Tracking in Browser

All examples return full CascadeResult:

```typescript
{
  content: "...",
  modelUsed: "gpt-4o-mini",
  totalCost: 0.000211,
  savingsPercentage: 97.8,
  cascaded: true,
  draftAccepted: true,
  // ... more fields
}
```

Display savings to users:

```javascript
document.getElementById('savings').textContent =
  `Saved ${result.savingsPercentage}% vs using ${result.verifierModel || 'best model'}`;
```
