# CascadeFlow Vercel Edge Function Example

Deploy CascadeFlow as a globally distributed edge function on Vercel for low-latency AI inference with 40-85% cost savings.

## Features

- ⚡ Global edge network (runs closest to users)
- 🔒 Secure (API keys never exposed to browser)
- 💰 Cost tracking (visualize savings in real-time)
- 🎨 Beautiful UI (responsive, modern design)
- 📦 Zero config (deploy in 60 seconds)

## Quick Start

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Set Environment Variables

```bash
# Add your OpenAI API key
vercel env add OPENAI_API_KEY
```

Or create `.env.local`:

```bash
OPENAI_API_KEY=sk-...
```

### 3. Test Locally

```bash
vercel dev
```

Open http://localhost:3000 in your browser.

### 4. Deploy to Production

```bash
vercel deploy --prod
```

## Project Structure

```
vercel-edge/
├── api/
│   └── chat.ts          Edge function (handles AI requests)
├── public/
│   └── index.html       Frontend UI
├── package.json
├── vercel.json          Vercel configuration
└── README.md
```

## How It Works

### Edge Function (`api/chat.ts`)

The edge function runs on Vercel's global network:

```typescript
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

### Frontend (`public/index.html`)

Simple fetch call to the edge function:

```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'What is TypeScript?' })
});

const result = await response.json();
console.log(`Saved ${result.savingsPercentage}%`);
```

## Customization

### Add More Models

Edit `api/chat.ts`:

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
    { name: 'o1-mini', provider: 'openai', cost: 0.003 },  // Add reasoning model
  ]
});
```

### Custom Quality Thresholds

```typescript
const agent = new CascadeAgent({
  models: [...],
  quality: {
    threshold: 0.8,  // Higher = more selective (fewer drafts accepted)
    requireValidation: true
  }
});
```

### Enable Tool Calling

```typescript
const result = await agent.run(query, {
  tools: [
    {
      type: 'function',
      function: {
        name: 'get_weather',
        description: 'Get current weather',
        parameters: {
          type: 'object',
          properties: {
            location: { type: 'string' }
          }
        }
      }
    }
  ]
});
```

## Cost Analysis

### Example Savings

| Scenario | Traditional Cost | CascadeFlow Cost | Savings |
|----------|------------------|------------------|---------|
| Simple query (200 tokens) | $0.00025 (GPT-5) | $0.00016 (Claude Haiku) | **36%** |
| Complex query (500 tokens) | $0.000625 (GPT-5) | $0.000625 (escalated) | **0%** (correct escalation) |
| Mixed (70% simple) | $0.0005 | $0.000299 | **40%** |

### Daily Usage Example

1000 queries/day:
- Traditional (GPT-5): $0.50/day = **$15.00/month**
- CascadeFlow (Claude Haiku + GPT-5): $0.30/day = **$9.00/month**
- **Savings: $6.00/month (40%)**

## Monitoring

### View Logs

```bash
vercel logs
```

### Analytics

Check Vercel dashboard for:
- Function execution time
- Error rates
- Bandwidth usage

## Production Checklist

- [ ] Set `OPENAI_API_KEY` in Vercel dashboard
- [ ] Update CORS settings in `api/chat.ts`
- [ ] Add rate limiting (use Vercel Edge Config)
- [ ] Monitor costs in OpenAI dashboard
- [ ] Set up error tracking (Sentry, etc.)

## Troubleshooting

### "OPENAI_API_KEY not found"

```bash
vercel env add OPENAI_API_KEY
vercel env pull  # Pull to local .env.local
```

### Edge function timeout

Increase timeout in `vercel.json`:

```json
{
  "functions": {
    "api/**/*.ts": {
      "maxDuration": 30
    }
  }
}
```

### CORS errors

Update `api/chat.ts`:

```typescript
headers: {
  'Access-Control-Allow-Origin': 'https://yourdomain.com',
  'Access-Control-Allow-Methods': 'POST',
  'Access-Control-Allow-Headers': 'Content-Type'
}
```

## Learn More

- [Vercel Edge Functions](https://vercel.com/docs/functions/edge-functions)
- [CascadeFlow Documentation](https://github.com/cascadeflow/cascadeflow)
- [OpenAI API Pricing](https://openai.com/api/pricing/)

## License

MIT
