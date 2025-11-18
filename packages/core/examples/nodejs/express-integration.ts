/**
 * cascadeflow - Express Integration Example (TypeScript)
 *
 * Production-ready Express integration with cascadeflow showing:
 * - RESTful API endpoints
 * - Streaming responses (SSE)
 * - Request validation
 * - Error handling
 * - Cost tracking per request
 * - Monitoring and logging
 * - Health checks
 *
 * What it demonstrates:
 * - Complete Express application with cascadeflow
 * - Streaming endpoint with Server-Sent Events
 * - Non-streaming endpoint for simple queries
 * - Request/response validation with Zod
 * - Error handling and validation
 * - Cost tracking and analytics
 * - Production-ready patterns
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - express
 *   - zod
 *   - OpenAI API key (or other providers)
 *
 * Setup:
 *   npm install @cascadeflow/core express zod
 *   export OPENAI_API_KEY="sk-..."
 *   npx tsx express-integration.ts
 *
 * Run:
 *   npx tsx express-integration.ts
 *   # Visit http://localhost:8000 for API information
 *
 * Test:
 *   # Non-streaming
 *   curl -X POST "http://localhost:8000/api/query" \
 *     -H "Content-Type: application/json" \
 *     -d '{"query": "What is TypeScript?", "max_tokens": 100}'
 *
 *   # Streaming
 *   curl -N "http://localhost:8000/api/query/stream?query=Explain%20AI&max_tokens=200"
 *
 *   # Stats
 *   curl "http://localhost:8000/api/stats"
 *
 * Documentation:
 *   📖 Express Guide: docs/guides/express.md
 *   📖 Production Guide: docs/guides/production.md
 *   📚 Examples README: examples/README.md
 */

import express, { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { CascadeAgent, StreamEventType } from '@cascadeflow/core';

// ═══════════════════════════════════════════════════════════════════════════
// ZOD SCHEMAS (Request/Response Validation)
// ═══════════════════════════════════════════════════════════════════════════

const QueryRequestSchema = z.object({
  query: z.string().min(1).max(2000).describe('User query text'),
  max_tokens: z.number().int().min(1).max(4000).default(100).optional().describe('Maximum tokens'),
  temperature: z.number().min(0).max(2).default(0.7).optional().describe('Sampling temperature'),
  force_direct: z.boolean().default(false).optional().describe('Skip cascade, use best model'),
});

type QueryRequest = z.infer<typeof QueryRequestSchema>;

interface QueryResponse {
  content: string;
  model_used: string;
  cost: number;
  latency_ms: number;
  cascaded: boolean;
  draft_accepted?: boolean;
  complexity?: string;
}

interface StatsResponse {
  total_queries: number;
  total_cost: number;
  avg_latency_ms: number;
  cascade_used_count: number;
  models_used: Record<string, number>;
  uptime_seconds: number;
}

interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  version: string;
  agent_initialized: boolean;
  providers_available: string[];
}

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════════════════

let agent: CascadeAgent | null = null;

const stats = {
  total_queries: 0,
  total_cost: 0.0,
  total_latency_ms: 0.0,
  cascade_used: 0,
  models_used: {} as Record<string, number>,
  start_time: new Date(),
};

// ═══════════════════════════════════════════════════════════════════════════
// EXPRESS APPLICATION
// ═══════════════════════════════════════════════════════════════════════════

const app = express();
const PORT = process.env.PORT || 8000;

// Middleware
app.use(express.json());

// Logging middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
  });
  next();
});

// ═══════════════════════════════════════════════════════════════════════════
// STARTUP / INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

async function initializeAgent() {
  console.log('🚀 Initializing cascadeflow agent...');

  const models = [];

  if (process.env.OPENAI_API_KEY) {
    models.push(
      {
        name: 'gpt-4o-mini',
        provider: 'openai' as const,
        cost: 0.00015,
      },
      {
        name: 'gpt-4o',
        provider: 'openai' as const,
        cost: 0.00625,
      }
    );
    console.log('✓ OpenAI models configured');
  }

  if (process.env.ANTHROPIC_API_KEY) {
    models.push({
      name: 'claude-sonnet-4-5-20250929',
      provider: 'anthropic' as const,
      cost: 0.003,
    });
    console.log('✓ Anthropic models configured');
  }

  if (process.env.GROQ_API_KEY) {
    models.unshift({
      name: 'llama-3.1-8b-instant',
      provider: 'groq' as const,
      cost: 0.0,
    });
    console.log('✓ Groq models configured');
  }

  if (models.length === 0) {
    throw new Error(
      'No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY'
    );
  }

  agent = new CascadeAgent({ models });
  stats.start_time = new Date();

  console.log(`✓ Agent initialized with ${models.length} models`);
  console.log(`✓ Service ready at http://localhost:${PORT}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// ENDPOINTS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Root endpoint with service information
 */
app.get('/', (req: Request, res: Response) => {
  res.json({
    service: 'cascadeflow API',
    version: '1.0.0',
    health: '/health',
    endpoints: {
      query: 'POST /api/query',
      stream: 'GET /api/query/stream',
      stats: 'GET /api/stats',
    },
  });
});

/**
 * Health check endpoint for monitoring
 */
app.get('/health', (req: Request, res: Response<HealthResponse>) => {
  const providers: string[] = [];

  if (process.env.OPENAI_API_KEY) providers.push('openai');
  if (process.env.ANTHROPIC_API_KEY) providers.push('anthropic');
  if (process.env.GROQ_API_KEY) providers.push('groq');

  res.json({
    status: agent !== null ? 'healthy' : 'unhealthy',
    version: '1.0.0',
    agent_initialized: agent !== null,
    providers_available: providers,
  });
});

/**
 * Non-streaming query endpoint
 *
 * Process a query and return the complete response.
 */
app.post('/api/query', async (req: Request, res: Response<QueryResponse>) => {
  try {
    // Validate request
    const request = QueryRequestSchema.parse(req.body);

    if (!agent) {
      return res.status(503).json({
        error: 'Agent not initialized',
      } as any);
    }

    console.log(`Processing query: ${request.query.substring(0, 50)}...`);

    // Run query
    const result = await agent.run(request.query, {
      maxTokens: request.max_tokens,
      temperature: request.temperature,
      forceDirect: request.force_direct,
    });

    // Update stats
    stats.total_queries += 1;
    stats.total_cost += result.totalCost;
    stats.total_latency_ms += result.latencyMs;

    if (result.cascaded) {
      stats.cascade_used += 1;
    }

    const model = result.modelUsed;
    stats.models_used[model] = (stats.models_used[model] || 0) + 1;

    console.log(
      `Query completed: ${model}, $${result.totalCost.toFixed(6)}, ${result.latencyMs.toFixed(0)}ms`
    );

    res.json({
      content: result.content,
      model_used: result.modelUsed,
      cost: result.totalCost,
      latency_ms: result.latencyMs,
      cascaded: result.cascaded || false,
      draft_accepted: result.draftAccepted,
      complexity: result.complexity,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return res.status(400).json({
        error: 'Validation error',
        details: error.issues,
      } as any);
    }

    console.error('Query failed:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Internal server error',
    } as any);
  }
});

/**
 * Streaming query endpoint (Server-Sent Events)
 *
 * Stream the response as it's being generated.
 */
app.get('/api/query/stream', async (req: Request, res: Response) => {
  try {
    const query = z.string().min(1).parse(req.query.query);
    const maxTokens = z.coerce.number().int().min(1).max(4000).default(100).parse(req.query.max_tokens);
    const temperature = z.coerce.number().min(0).max(2).default(0.7).parse(req.query.temperature);

    if (!agent) {
      return res.status(503).json({ error: 'Agent not initialized' });
    }

    console.log(`Starting stream for query: ${query.substring(0, 50)}...`);

    // Set SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');

    let totalCost = 0.0;
    let modelUsed: string | null = null;

    try {
      for await (const event of agent.stream(query, {
        maxTokens,
        temperature,
      })) {
        // Format as SSE
        const eventData = {
          type: event.type,
          content: event.content,
          data: event.data || {},
        };

        // Extract cost and model from complete event
        if (event.type === StreamEventType.COMPLETE) {
          const result = event.data?.result;
          if (result) {
            totalCost = result.totalCost || 0.0;
            modelUsed = result.modelUsed || 'unknown';
          }
        }

        res.write(`data: ${JSON.stringify(eventData)}\n\n`);
      }

      // Update stats
      stats.total_queries += 1;
      stats.total_cost += totalCost;
      if (modelUsed) {
        stats.models_used[modelUsed] = (stats.models_used[modelUsed] || 0) + 1;
      }

      console.log(`Stream completed: ${modelUsed}, $${totalCost.toFixed(6)}`);

      res.end();
    } catch (streamError) {
      console.error('Streaming failed:', streamError);
      const errorData = {
        type: 'error',
        content: streamError instanceof Error ? streamError.message : 'Stream error',
      };
      res.write(`data: ${JSON.stringify(errorData)}\n\n`);
      res.end();
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      return res.status(400).json({
        error: 'Validation error',
        details: error.issues,
      });
    }

    console.error('Stream setup failed:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Internal server error',
    });
  }
});

/**
 * Get API usage statistics
 */
app.get('/api/stats', (req: Request, res: Response<StatsResponse>) => {
  const uptime = (Date.now() - stats.start_time.getTime()) / 1000;
  const avgLatency =
    stats.total_queries > 0 ? stats.total_latency_ms / stats.total_queries : 0;

  res.json({
    total_queries: stats.total_queries,
    total_cost: stats.total_cost,
    avg_latency_ms: avgLatency,
    cascade_used_count: stats.cascade_used,
    models_used: stats.models_used,
    uptime_seconds: uptime,
  });
});

/**
 * Reset statistics (useful for testing)
 */
app.delete('/api/stats', (req: Request, res: Response) => {
  stats.total_queries = 0;
  stats.total_cost = 0.0;
  stats.total_latency_ms = 0.0;
  stats.cascade_used = 0;
  stats.models_used = {};
  stats.start_time = new Date();

  res.json({ message: 'Stats reset successfully' });
});

// ═══════════════════════════════════════════════════════════════════════════
// ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════════════

app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: err.message,
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// MAIN (Startup)
// ═══════════════════════════════════════════════════════════════════════════

async function main() {
  console.log('\n' + '='.repeat(70));
  console.log('🌊 cascadeflow Express Service');
  console.log('='.repeat(70));

  console.log('\n📚 Features:');
  console.log('   ✓ RESTful API endpoints');
  console.log('   ✓ Streaming responses (SSE)');
  console.log('   ✓ Request validation (Zod)');
  console.log('   ✓ Cost tracking');
  console.log('   ✓ Health checks');
  console.log('   ✓ Error handling');

  try {
    await initializeAgent();

    app.listen(PORT, () => {
      console.log('\n🔗 Endpoints:');
      console.log(`   • http://localhost:${PORT}/ - Service information`);
      console.log(`   • http://localhost:${PORT}/health - Health check`);
      console.log(`   • POST http://localhost:${PORT}/api/query - Non-streaming query`);
      console.log(`   • GET http://localhost:${PORT}/api/query/stream - Streaming query`);
      console.log(`   • GET http://localhost:${PORT}/api/stats - Usage statistics`);

      console.log('\n🚀 Server running!');
      console.log('=' + '='.repeat(70) + '\n');
    });
  } catch (error) {
    console.error('\n❌ Failed to start server:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n\n🛑 Shutting down cascadeflow service...');
  console.log(
    `Final stats: ${stats.total_queries} queries, $${stats.total_cost.toFixed(4)} total cost`
  );
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n\n🛑 Shutting down cascadeflow service...');
  console.log(
    `Final stats: ${stats.total_queries} queries, $${stats.total_cost.toFixed(4)} total cost`
  );
  process.exit(0);
});

// Run the server
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
