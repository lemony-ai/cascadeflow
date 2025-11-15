/**
 * Vercel Edge Functions Example
 *
 * Demonstrates using cascadeflow with Vercel Edge Runtime:
 * - Edge-optimized configuration
 * - Streaming responses (SSE)
 * - Environment variables
 * - API routes
 * - Deployment setup
 * - Global edge distribution
 *
 * This file shows the patterns - actual Vercel deployment uses api/ directory.
 *
 * Usage: npx tsx examples/nodejs/vercel-edge.ts
 */

console.log('\n╔═══════════════════════════════════════════════════════════════╗');
console.log('║        cascadeflow - Vercel Edge Functions Guide            ║');
console.log('╚═══════════════════════════════════════════════════════════════╝\n');

console.log('⚡ Vercel Edge Runtime Integration\n');

// ============================================================================
// Pattern 1: Project Structure
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 1: Project Structure');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Recommended directory structure:');
console.log(`
your-project/
├── api/
│   ├── query.ts           # Non-streaming endpoint
│   ├── stream.ts          # Streaming endpoint
│   └── health.ts          # Health check
├── lib/
│   └── cascadeflow.ts     # Shared agent config
├── vercel.json            # Vercel configuration
├── package.json
└── .env.local             # Local environment variables
`);

console.log('');

// ============================================================================
// Pattern 2: Edge Runtime Configuration
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 2: Edge Runtime Configuration');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('api/query.ts (Non-streaming):');
console.log(`
import { CascadeAgent } from '@cascadeflow/core';

// REQUIRED: Specify edge runtime
export const config = {
  runtime: 'edge',
};

// Initialize agent (executes at edge)
const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey: process.env.OPENAI_API_KEY,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      apiKey: process.env.OPENAI_API_KEY,
    },
  ],
});

export default async function handler(req: Request) {
  // CORS headers
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  try {
    const { query, maxTokens = 200 } = await req.json();

    if (!query || typeof query !== 'string') {
      return new Response(
        JSON.stringify({ error: 'Invalid query' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const result = await agent.run(query, { maxTokens });

    return new Response(
      JSON.stringify({
        content: result.content,
        cost: result.totalCost,
        model: result.modelUsed,
        cached: result.fromCache || false,
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'no-cache',
        },
      }
    );
  } catch (error) {
    console.error('Edge function error:', error);
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
`);

console.log('');

// ============================================================================
// Pattern 3: Streaming Edge Function
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 3: Streaming (Server-Sent Events)');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('api/stream.ts (Streaming):');
console.log(`
import { CascadeAgent, StreamEventType } from '@cascadeflow/core';

export const config = {
  runtime: 'edge',
};

const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey: process.env.OPENAI_API_KEY,
    },
  ],
});

export default async function handler(req: Request) {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  const { query } = await req.json();

  // Create ReadableStream for SSE
  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();

      try {
        for await (const event of agent.stream(query)) {
          let data: any = {};

          switch (event.type) {
            case StreamEventType.CHUNK:
              data = { type: 'chunk', content: event.content };
              break;

            case StreamEventType.DRAFT_DECISION:
              data = {
                type: 'decision',
                accepted: event.data.accepted,
                confidence: event.data.confidence,
              };
              break;

            case StreamEventType.SWITCH:
              data = {
                type: 'switch',
                from: event.data.fromModel,
                to: event.data.toModel,
              };
              break;

            case StreamEventType.COMPLETE:
              data = {
                type: 'complete',
                cost: event.data.result.totalCost,
                model: event.data.result.modelUsed,
              };
              break;
          }

          // Send SSE formatted data
          const sseData = \`data: \${JSON.stringify(data)}\\n\\n\`;
          controller.enqueue(encoder.encode(sseData));
        }

        controller.close();
      } catch (error) {
        const errorData = \`data: \${JSON.stringify({
          type: 'error',
          message: error instanceof Error ? error.message : 'Unknown error'
        })}\\n\\n\`;
        controller.enqueue(encoder.encode(errorData));
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
`);

console.log('');

// ============================================================================
// Pattern 4: Shared Agent Configuration
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 4: Shared Agent Configuration');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('lib/cascadeflow.ts (Reusable config):');
console.log(`
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

// Centralized model configuration
export function getModels(): ModelConfig[] {
  const apiKey = process.env.OPENAI_API_KEY;

  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not configured');
  }

  return [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      apiKey,
    },
  ];
}

// Singleton agent instance (edge functions are cold-started)
let agent: CascadeAgent | null = null;

export function getAgent(): CascadeAgent {
  if (!agent) {
    agent = new CascadeAgent({
      models: getModels(),
      quality: { threshold: 0.7 },
      caching: { enabled: true },
    });
  }
  return agent;
}
`);

console.log('Usage in API routes:');
console.log(`
import { getAgent } from '../lib/cascadeflow';

export const config = { runtime: 'edge' };

export default async function handler(req: Request) {
  const agent = getAgent();
  const result = await agent.run('query');
  return new Response(JSON.stringify(result));
}
`);

console.log('');

// ============================================================================
// Pattern 5: vercel.json Configuration
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 5: Deployment Configuration');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('vercel.json:');
console.log(`
{
  "functions": {
    "api/**/*.ts": {
      "runtime": "edge"
    }
  },
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Access-Control-Allow-Origin",
          "value": "*"
        },
        {
          "key": "Access-Control-Allow-Methods",
          "value": "GET, POST, OPTIONS"
        },
        {
          "key": "Access-Control-Allow-Headers",
          "value": "Content-Type, Authorization"
        }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "/api/:path*"
    }
  ]
}
`);

console.log('');

// ============================================================================
// Pattern 6: Environment Variables
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 6: Environment Variables');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Local development (.env.local):');
console.log(`
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
`);

console.log('Set in Vercel Dashboard:');
console.log('   1. Go to Project Settings → Environment Variables');
console.log('   2. Add OPENAI_API_KEY');
console.log('   3. Set for Production, Preview, and Development');
console.log('   4. Deploy to apply changes');
console.log('');

console.log('Access in edge functions:');
console.log(`
export default async function handler(req: Request) {
  const apiKey = process.env.OPENAI_API_KEY;

  if (!apiKey) {
    return new Response('API key not configured', { status: 500 });
  }

  // Use apiKey...
}
`);

console.log('');

// ============================================================================
// Pattern 7: Client-Side Integration
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 7: Client-Side Integration');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Non-streaming client:');
console.log(`
async function queryEdgeFunction(query: string) {
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, maxTokens: 200 }),
  });

  if (!response.ok) {
    throw new Error(\`HTTP \${response.status}\`);
  }

  const data = await response.json();
  return data;
}

// Usage
const result = await queryEdgeFunction('What is Vercel Edge?');
console.log(result.content);
console.log(\`Cost: $\${result.cost}\`);
`);

console.log('Streaming client (EventSource):');
console.log(`
function streamFromEdge(query: string, onChunk: (chunk: string) => void) {
  return new Promise((resolve, reject) => {
    fetch('/api/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    }).then(async (response) => {
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'chunk') {
              onChunk(data.content);
            } else if (data.type === 'complete') {
              resolve(data);
            } else if (data.type === 'error') {
              reject(new Error(data.message));
            }
          }
        }
      }
    });
  });
}

// Usage
await streamFromEdge('Explain edge computing', (chunk) => {
  console.log(chunk);
});
`);

console.log('');

// ============================================================================
// Pattern 8: Error Handling
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 8: Error Handling');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Robust error handling:');
console.log(`
export default async function handler(req: Request) {
  try {
    // Validate request
    if (req.method !== 'POST') {
      return new Response(
        JSON.stringify({ error: 'Method not allowed' }),
        { status: 405, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Parse body safely
    let body;
    try {
      body = await req.json();
    } catch {
      return new Response(
        JSON.stringify({ error: 'Invalid JSON' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Validate input
    if (!body.query || typeof body.query !== 'string') {
      return new Response(
        JSON.stringify({ error: 'Missing or invalid query' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Rate limiting check (implement your logic)
    // const allowed = await checkRateLimit(req.headers.get('x-forwarded-for'));
    // if (!allowed) return new Response('Rate limit exceeded', { status: 429 });

    // Execute query
    const agent = getAgent();
    const result = await agent.run(body.query);

    return new Response(JSON.stringify(result), {
      headers: { 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Edge function error:', error);

    // Don't expose internal errors to client
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
        requestId: crypto.randomUUID(), // For debugging
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
`);

console.log('');

// ============================================================================
// Pattern 9: Deployment
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 9: Deployment Steps');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('1. Install Vercel CLI:');
console.log('   npm install -g vercel\n');

console.log('2. Login to Vercel:');
console.log('   vercel login\n');

console.log('3. Link project:');
console.log('   vercel link\n');

console.log('4. Set environment variables:');
console.log('   vercel env add OPENAI_API_KEY\n');

console.log('5. Deploy to preview:');
console.log('   vercel\n');

console.log('6. Deploy to production:');
console.log('   vercel --prod\n');

console.log('Or use Git integration:');
console.log('   1. Push to GitHub');
console.log('   2. Import project in Vercel dashboard');
console.log('   3. Set environment variables');
console.log('   4. Deploy automatically on push\n');

// ============================================================================
// Pattern 10: Performance Optimization
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 10: Performance Optimization');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Edge-optimized patterns:');
console.log(`
// 1. Singleton agent (avoid re-initialization)
let agent: CascadeAgent | null = null;
export function getAgent() {
  if (!agent) agent = new CascadeAgent({...});
  return agent;
}

// 2. Enable caching
const agent = new CascadeAgent({
  models: [...],
  caching: { enabled: true, ttl: 3600 },
});

// 3. Response caching (Vercel)
export default async function handler(req: Request) {
  const result = await agent.run(query);

  return new Response(JSON.stringify(result), {
    headers: {
      'Cache-Control': 's-maxage=60, stale-while-revalidate=300',
    },
  });
}

// 4. Conditional requests
if (req.headers.get('if-none-match') === etag) {
  return new Response(null, { status: 304 });
}
`);

console.log('');

// ============================================================================
// Summary
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('📋 Vercel Edge Functions Summary');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('✅ Edge Runtime Advantages:');
console.log('   • Global distribution (low latency)');
console.log('   • Zero cold starts');
console.log('   • Automatic scaling');
console.log('   • Streaming support');
console.log('   • Cost-effective');
console.log('   • TypeScript native');
console.log('');

console.log('🎯 Key Patterns:');
console.log('   • Use `export const config = { runtime: "edge" }`');
console.log('   • Initialize agent outside handler (singleton)');
console.log('   • Use ReadableStream for SSE streaming');
console.log('   • Set environment variables in Vercel dashboard');
console.log('   • Handle CORS properly');
console.log('   • Implement error handling');
console.log('');

console.log('🚀 Deployment Checklist:');
console.log('   ✓ Create api/ directory with edge functions');
console.log('   ✓ Configure runtime: "edge"');
console.log('   ✓ Set up environment variables');
console.log('   ✓ Add vercel.json for configuration');
console.log('   ✓ Test locally with `vercel dev`');
console.log('   ✓ Deploy with `vercel --prod`');
console.log('');

console.log('📚 Resources:');
console.log('   • Vercel Edge: https://vercel.com/docs/functions/edge-functions');
console.log('   • Edge Runtime: https://edge-runtime.vercel.app/');
console.log('   • Examples: https://github.com/vercel/examples');
console.log('');

console.log('⚡ cascadeflow works perfectly with Vercel Edge!');
console.log('   Deploy globally with minimal latency and automatic scaling.\n');
