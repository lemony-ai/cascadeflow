/**
 * Production Patterns for cascadeflow
 *
 * Demonstrates best practices for using cascadeflow in production:
 * - Error handling and retries
 * - Caching responses
 * - Rate limiting
 * - Monitoring and logging
 * - Cost tracking and budgets
 * - Failover strategies
 */

import { CascadeAgent } from '@cascadeflow/core';
import type { CascadeResult } from '@cascadeflow/core';

// ===================================================================
// Pattern 1: Error Handling with Retries
// ===================================================================

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  delay = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      lastError = error;
      console.error(`Attempt ${attempt}/${maxRetries} failed:`, error.message);

      if (attempt < maxRetries) {
        // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay * attempt));
      }
    }
  }

  throw lastError;
}

async function example1_ErrorHandling() {
  console.log('\n📝 Example 1: Error Handling with Retries\n');

  const agent = new CascadeAgent({
    models: [
      { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
      { name: 'claude-sonnet-4-5', provider: 'anthropic', cost: 0.003 },
    ],
  });

  try {
    const result = await withRetry(
      () => agent.run('What is the capital of France?'),
      3,  // Max 3 retries
      1000  // Start with 1s delay
    );

    console.log('✅ Success:', result.content);
    console.log(`Cost: $${result.totalCost.toFixed(6)}`);
  } catch (error: any) {
    console.error('❌ Failed after all retries:', error.message);
    // Log to monitoring service (e.g., Sentry, Datadog)
    // sendToMonitoring(error);
  }
}

// ===================================================================
// Pattern 2: Response Caching
// ===================================================================

class ResponseCache {
  private cache = new Map<string, { result: CascadeResult; timestamp: number }>();
  private ttl: number;

  constructor(ttlMinutes = 60) {
    this.ttl = ttlMinutes * 60 * 1000;
  }

  get(key: string): CascadeResult | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Check if expired
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.result;
  }

  set(key: string, result: CascadeResult): void {
    this.cache.set(key, { result, timestamp: Date.now() });
  }

  clear(): void {
    this.cache.clear();
  }
}

async function example2_Caching() {
  console.log('\n📝 Example 2: Response Caching\n');

  const agent = new CascadeAgent({
    models: [
      { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
      { name: 'claude-sonnet-4-5', provider: 'anthropic', cost: 0.003 },
    ],
  });

  const cache = new ResponseCache(60); // 60 minute TTL

  async function queryWithCache(query: string): Promise<CascadeResult> {
    // Check cache first
    const cached = cache.get(query);
    if (cached) {
      console.log('✅ Cache hit!');
      return cached;
    }

    console.log('❌ Cache miss, fetching...');
    const result = await agent.run(query);
    cache.set(query, result);
    return result;
  }

  // First call - cache miss
  const result1 = await queryWithCache('What is TypeScript?');
  console.log(`Cost: $${result1.totalCost.toFixed(6)}`);

  // Second call - cache hit (free!)
  const result2 = await queryWithCache('What is TypeScript?');
  console.log(`Cost: $${result2.totalCost.toFixed(6)}`);
}

// ===================================================================
// Pattern 3: Rate Limiting
// ===================================================================

class RateLimiter {
  private tokens: number;
  private maxTokens: number;
  private refillRate: number;
  private lastRefill: number;

  constructor(maxRequestsPerMinute: number) {
    this.maxTokens = maxRequestsPerMinute;
    this.tokens = maxRequestsPerMinute;
    this.refillRate = maxRequestsPerMinute / 60000; // tokens per ms
    this.lastRefill = Date.now();
  }

  async acquire(): Promise<void> {
    // Refill tokens based on time elapsed
    const now = Date.now();
    const elapsed = now - this.lastRefill;
    this.tokens = Math.min(
      this.maxTokens,
      this.tokens + elapsed * this.refillRate
    );
    this.lastRefill = now;

    // Wait if no tokens available
    if (this.tokens < 1) {
      const waitTime = (1 - this.tokens) / this.refillRate;
      await new Promise(resolve => setTimeout(resolve, waitTime));
      this.tokens = 0;
    } else {
      this.tokens -= 1;
    }
  }
}

async function example3_RateLimiting() {
  console.log('\n📝 Example 3: Rate Limiting\n');

  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    ],
  });

  const rateLimiter = new RateLimiter(10); // 10 requests per minute

  async function queryWithRateLimit(query: string): Promise<CascadeResult> {
    await rateLimiter.acquire();
    return agent.run(query);
  }

  console.log('Making 3 rate-limited requests...');
  const start = Date.now();

  for (let i = 1; i <= 3; i++) {
    await queryWithRateLimit(`Query ${i}`);
    console.log(`✅ Request ${i} completed (${Date.now() - start}ms)`);
  }
}

// ===================================================================
// Pattern 4: Cost Tracking and Budgets
// ===================================================================

class CostTracker {
  private totalCost = 0;
  private budget: number;
  private requests: Array<{ query: string; cost: number; timestamp: number }> = [];

  constructor(dailyBudget: number) {
    this.budget = dailyBudget;
  }

  async track(query: string, fn: () => Promise<CascadeResult>): Promise<CascadeResult> {
    if (this.totalCost >= this.budget) {
      throw new Error(`Budget exceeded: $${this.totalCost.toFixed(4)} / $${this.budget}`);
    }

    const result = await fn();
    this.totalCost += result.totalCost;
    this.requests.push({
      query,
      cost: result.totalCost,
      timestamp: Date.now(),
    });

    console.log(`💰 Cost: $${result.totalCost.toFixed(6)} | Total: $${this.totalCost.toFixed(4)} / $${this.budget}`);

    return result;
  }

  getStats() {
    return {
      totalCost: this.totalCost,
      requestCount: this.requests.length,
      averageCost: this.totalCost / this.requests.length,
      budgetUsed: (this.totalCost / this.budget) * 100,
      remainingBudget: this.budget - this.totalCost,
    };
  }
}

async function example4_CostTracking() {
  console.log('\n📝 Example 4: Cost Tracking and Budgets\n');

  const agent = new CascadeAgent({
    models: [
      { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
      { name: 'claude-sonnet-4-5', provider: 'anthropic', cost: 0.003 },
    ],
  });

  const tracker = new CostTracker(1.00); // $1 daily budget

  try {
    await tracker.track('Query 1', () => agent.run('What is AI?'));
    await tracker.track('Query 2', () => agent.run('Explain machine learning'));
    await tracker.track('Query 3', () => agent.run('What is deep learning?'));

    const stats = tracker.getStats();
    console.log('\n📊 Statistics:');
    console.log(`  Total requests: ${stats.requestCount}`);
    console.log(`  Total cost: $${stats.totalCost.toFixed(6)}`);
    console.log(`  Average cost: $${stats.averageCost.toFixed(6)}`);
    console.log(`  Budget used: ${stats.budgetUsed.toFixed(2)}%`);
    console.log(`  Remaining: $${stats.remainingBudget.toFixed(4)}`);
  } catch (error: any) {
    console.error('❌', error.message);
  }
}

// ===================================================================
// Pattern 5: Monitoring and Logging
// ===================================================================

class QueryLogger {
  log(event: string, data: any): void {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ${event}:`, JSON.stringify(data, null, 2));

    // In production, send to logging service:
    // - Datadog
    // - CloudWatch
    // - Logtail
    // - etc.
  }

  logRequest(query: string, options: any): void {
    this.log('REQUEST', { query, options });
  }

  logResponse(result: CascadeResult): void {
    this.log('RESPONSE', {
      modelUsed: result.modelUsed,
      cost: result.totalCost,
      latency: result.latencyMs,
      cascaded: result.cascaded,
      draftAccepted: result.draftAccepted,
      savings: result.savingsPercentage,
    });
  }

  logError(error: Error): void {
    this.log('ERROR', {
      message: error.message,
      stack: error.stack,
    });
  }
}

async function example5_Monitoring() {
  console.log('\n📝 Example 5: Monitoring and Logging\n');

  const agent = new CascadeAgent({
    models: [
      { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
      { name: 'claude-sonnet-4-5', provider: 'anthropic', cost: 0.003 },
    ],
  });

  const logger = new QueryLogger();

  const query = 'What is quantum computing?';
  logger.logRequest(query, { maxTokens: 100 });

  try {
    const result = await agent.run(query, { maxTokens: 100 });
    logger.logResponse(result);
    console.log('\n✅ Response:', result.content.substring(0, 100), '...');
  } catch (error: any) {
    logger.logError(error);
  }
}

// ===================================================================
// Pattern 6: Failover Strategy
// ===================================================================

async function example6_Failover() {
  console.log('\n📝 Example 6: Failover Strategy\n');

  // Primary cascade
  const primaryAgent = new CascadeAgent({
    models: [
      { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
      { name: 'claude-sonnet-4-5', provider: 'anthropic', cost: 0.003 },
    ],
  });

  // Fallback cascade (different providers)
  const fallbackAgent = new CascadeAgent({
    models: [
      { name: 'llama-4-scout', provider: 'groq', cost: 0.00011 },
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    ],
  });

  const query = 'Explain neural networks briefly';

  try {
    console.log('Trying primary cascade...');
    const result = await primaryAgent.run(query);
    console.log('✅ Primary cascade succeeded');
    console.log(`Cost: $${result.totalCost.toFixed(6)}`);
    console.log(`Response: ${result.content.substring(0, 100)}...`);
  } catch (error: any) {
    console.log('❌ Primary cascade failed:', error.message);
    console.log('Trying fallback cascade...');

    try {
      const result = await fallbackAgent.run(query);
      console.log('✅ Fallback cascade succeeded');
      console.log(`Cost: $${result.totalCost.toFixed(6)}`);
      console.log(`Response: ${result.content.substring(0, 100)}...`);
    } catch (fallbackError: any) {
      console.error('❌ Both cascades failed:', fallbackError.message);
      // Last resort: return cached response or error message
    }
  }
}

// ===================================================================
// Run All Examples
// ===================================================================

async function main() {
  console.log('🎯 cascadeflow Production Patterns\n');
  console.log('═══════════════════════════════════════════════════\n');

  await example1_ErrorHandling();
  await example2_Caching();
  await example3_RateLimiting();
  await example4_CostTracking();
  await example5_Monitoring();
  await example6_Failover();

  console.log('\n═══════════════════════════════════════════════════');
  console.log('✅ All examples completed!\n');
}

main().catch(console.error);
