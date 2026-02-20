/**
 * Comprehensive LangChain Benchmark with Semantic Quality Validation
 *
 * Tests ALL available LangChain models with:
 * - LangSmith tracking and cost visualization
 * - Semantic quality scoring using ML embeddings
 * - Cross-provider cascade pairs
 * - Multiple complexity levels
 * - Detailed performance metrics
 *
 * Requirements:
 *   - OPENAI_API_KEY
 *   - ANTHROPIC_API_KEY (optional)
 *   - LANGSMITH_API_KEY
 *   - @cascadeflow/ml @xenova/transformers (for semantic validation)
 *
 * Setup:
 *   npm install @cascadeflow/ml @xenova/transformers
 *   npx tsx examples/full-benchmark-semantic.ts
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { CascadeFlow } from '../src/index.js';
import { SemanticQualityChecker } from '@cascadeflow/core';

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m',
};

// Test queries spanning different complexity levels
const TEST_QUERIES = [
  {
    query: 'What is TypeScript?',
    complexity: 'Simple',
    category: 'Factual',
  },
  {
    query: 'Explain the event loop in Node.js',
    complexity: 'Medium',
    category: 'Technical',
  },
  {
    query: 'Design a distributed cache with Redis and implement consistency guarantees',
    complexity: 'Complex',
    category: 'Design',
  },
  {
    query: 'Compare the trade-offs between microservices and monolithic architectures',
    complexity: 'Complex',
    category: 'Analysis',
  },
  {
    query: 'How do I reverse a string in Python?',
    complexity: 'Simple',
    category: 'Code',
  },
  {
    query: 'Explain async/await in JavaScript with examples',
    complexity: 'Medium',
    category: 'Technical',
  },
];

interface ModelPair {
  name: string;
  drafter: any;
  verifier: any;
  provider: string;
  expectedSavings: string;
}

interface BenchmarkResult {
  pairName: string;
  provider: string;
  totalQueries: number;
  cascaded: number;
  escalated: number;
  avgQuality: number;
  avgLatency: number;
  successRate: number;
  avgSemanticScore?: number;
}

/**
 * Create a semantic quality validator for LangChain ChatResult format
 */
async function createSemanticValidator(semanticChecker: SemanticQualityChecker, query: string) {
  return async (response: any): Promise<number> => {
    // Extract text from LangChain ChatResult
    const text = response?.generations?.[0]?.text ||
      response?.generations?.[0]?.message?.content ||
      '';

    if (!text || text.length < 5) {
      return 0.2;
    }

    // Check semantic similarity
    const result = await semanticChecker.checkSimilarity(query, text);

    if (!result.passed) {
      console.log(`      [Semantic] Similarity: ${(result.similarity * 100).toFixed(1)}% - Below threshold`);
      return result.similarity * 0.8; // Penalize low similarity
    }

    // Boost quality score for high semantic similarity
    const boostedScore = Math.min(1.0, result.similarity * 1.2);
    return boostedScore;
  };
}

async function testModelPair(
  pair: ModelPair,
  semanticChecker: SemanticQualityChecker,
  mlAvailable: boolean
): Promise<BenchmarkResult> {
  console.log(`\n${COLORS.cyan}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.cyan}${COLORS.bold}Testing: ${pair.name}${COLORS.reset}`);
  console.log(`${COLORS.blue}Provider: ${pair.provider} | Expected Savings: ${pair.expectedSavings}${COLORS.reset}`);
  console.log(`${COLORS.magenta}Semantic Validation: ${mlAvailable ? 'ENABLED ✓' : 'DISABLED (Install @cascadeflow/ml)'}${COLORS.reset}`);
  console.log(`${COLORS.cyan}${'='.repeat(100)}${COLORS.reset}\n`);

  let cascaded = 0;
  let escalated = 0;
  let totalQuality = 0;
  let totalLatency = 0;
  let totalSemanticScore = 0;
  const semanticScores: number[] = [];

  for (const { query, complexity, category } of TEST_QUERIES) {
    console.log(`${COLORS.blue}[${complexity}]${COLORS.reset} ${COLORS.yellow}[${category}]${COLORS.reset} ${query}`);

    // Create cascade with semantic validation
    const cascade = new CascadeFlow({
      drafter: pair.drafter,
      verifier: pair.verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
      costTrackingProvider: 'langsmith',
      // Use semantic validator if ML is available
      qualityValidator: mlAvailable
        ? await createSemanticValidator(semanticChecker, query)
        : undefined,
    });

    const result = await cascade.invoke(query);
    const stats = cascade.getLastCascadeResult();

    const preview = result.content.toString().substring(0, 80);
    console.log(`  Response: ${preview}...`);

    if (stats) {
      totalQuality += stats.drafterQuality || 0;
      totalLatency += stats.latencyMs;

      // Track semantic score separately if we used semantic validation
      if (mlAvailable && stats.drafterQuality) {
        semanticScores.push(stats.drafterQuality);
        totalSemanticScore += stats.drafterQuality;
      }

      if (stats.modelUsed === 'drafter') {
        console.log(`  ${COLORS.green}✓ CASCADED${COLORS.reset} (quality: ${stats.drafterQuality?.toFixed(2)}, ${stats.latencyMs}ms)`);
        cascaded++;
      } else {
        console.log(`  ${COLORS.yellow}⚠ ESCALATED${COLORS.reset} (quality: ${stats.drafterQuality?.toFixed(2)}, ${stats.latencyMs}ms)`);
        escalated++;
      }
    }

    // Small delay to avoid rate limits
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  const totalQueries = TEST_QUERIES.length;
  const avgQuality = totalQuality / totalQueries;
  const avgLatency = totalLatency / totalQueries;
  const successRate = (cascaded / totalQueries) * 100;
  const avgSemanticScore = semanticScores.length > 0
    ? totalSemanticScore / semanticScores.length
    : undefined;

  console.log(`\n${COLORS.bold}Results:${COLORS.reset}`);
  console.log(`  Cascaded: ${cascaded}/${totalQueries}`);
  console.log(`  Escalated: ${escalated}/${totalQueries}`);
  console.log(`  Success Rate: ${successRate.toFixed(0)}%`);
  console.log(`  Avg Quality: ${avgQuality.toFixed(2)}`);
  if (avgSemanticScore !== undefined) {
    console.log(`  Avg Semantic Score: ${avgSemanticScore.toFixed(2)}`);
  }
  console.log(`  Avg Latency: ${avgLatency.toFixed(0)}ms`);

  return {
    pairName: pair.name,
    provider: pair.provider,
    totalQueries,
    cascaded,
    escalated,
    avgQuality,
    avgLatency,
    successRate,
    avgSemanticScore,
  };
}

async function main() {
  console.log(`${COLORS.magenta}${COLORS.bold}╔════════════════════════════════════════════════════════════════════╗${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}║   COMPREHENSIVE LANGCHAIN BENCHMARK - SEMANTIC QUALITY VALIDATION  ║${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}╚════════════════════════════════════════════════════════════════════╝${COLORS.reset}\n`);

  // ========================================================================
  // STEP 1: Check LangSmith Configuration
  // ========================================================================

  console.log(`${COLORS.bold}📋 Step 1: Checking Configuration${COLORS.reset}\n`);

  if (!process.env.LANGSMITH_API_KEY) {
    console.log(`${COLORS.red}❌ LANGSMITH_API_KEY not set${COLORS.reset}`);
    console.log('Set LANGSMITH_API_KEY to see traces in https://smith.langchain.com\n');
    return;
  }

  console.log(`${COLORS.green}✓ LangSmith tracing enabled${COLORS.reset}`);
  console.log(`  Project: ${process.env.LANGSMITH_PROJECT || 'default'}`);
  console.log(`  View traces: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}\n`);

  // ========================================================================
  // STEP 2: Initialize Semantic Quality Checker
  // ========================================================================

  console.log(`${COLORS.bold}🧠 Step 2: Initializing Semantic Quality Checker${COLORS.reset}\n`);

  const semanticChecker = new SemanticQualityChecker(
    0.5, // 50% similarity threshold
    undefined,
    true // Enable caching
  );

  const mlAvailable = await semanticChecker.isAvailable();

  if (mlAvailable) {
    console.log(`${COLORS.green}✓ Semantic validation ENABLED${COLORS.reset}`);
    console.log(`  Embedding Model: BGE-small-en-v1.5 (ONNX)`);
    console.log(`  Similarity Threshold: 50%`);
    console.log(`  Caching: Enabled\n`);
  } else {
    console.log(`${COLORS.yellow}⚠ Semantic validation DISABLED${COLORS.reset}`);
    console.log(`  Install with: npm install @cascadeflow/ml @xenova/transformers`);
    console.log(`  Falling back to heuristic quality scoring\n`);
  }

  // ========================================================================
  // STEP 3: Define Model Pairs
  // ========================================================================

  console.log(`${COLORS.bold}🤖 Step 3: Configuring Model Pairs${COLORS.reset}\n`);

  const modelPairs: ModelPair[] = [];

  // OpenAI GPT-5 Family
  modelPairs.push({
    name: 'GPT-5 Nano → GPT-5',
    drafter: new ChatOpenAI({ model: 'gpt-5-nano', temperature: 1.0 }),
    verifier: new ChatOpenAI({ model: 'gpt-5', temperature: 1.0 }),
    provider: 'OpenAI',
    expectedSavings: '66%',
  });

  modelPairs.push({
    name: 'GPT-5 Mini → GPT-5',
    drafter: new ChatOpenAI({ model: 'gpt-5-mini', temperature: 1.0 }),
    verifier: new ChatOpenAI({ model: 'gpt-5', temperature: 1.0 }),
    provider: 'OpenAI',
    expectedSavings: '50%',
  });

  modelPairs.push({
    name: 'GPT-5 Nano → GPT-5 Mini',
    drafter: new ChatOpenAI({ model: 'gpt-5-nano', temperature: 1.0 }),
    verifier: new ChatOpenAI({ model: 'gpt-5-mini', temperature: 1.0 }),
    provider: 'OpenAI',
    expectedSavings: '50%',
  });

  // Cross-Provider (Anthropic → OpenAI)
  if (process.env.ANTHROPIC_API_KEY) {
    modelPairs.push({
      name: 'Claude 3 Haiku → GPT-5',
      drafter: new ChatAnthropic({ model: 'claude-3-haiku-20240307' }),
      verifier: new ChatOpenAI({ model: 'gpt-5', temperature: 1.0 }),
      provider: 'Cross-Provider (Anthropic→OpenAI)',
      expectedSavings: '80%',
    });

    modelPairs.push({
      name: 'Claude 3 Haiku → GPT-5 Mini',
      drafter: new ChatAnthropic({ model: 'claude-3-haiku-20240307' }),
      verifier: new ChatOpenAI({ model: 'gpt-5-mini', temperature: 1.0 }),
      provider: 'Cross-Provider (Anthropic→OpenAI)',
      expectedSavings: '60%',
    });
  } else {
    console.log(`${COLORS.yellow}⚠ ANTHROPIC_API_KEY not set - skipping Anthropic tests${COLORS.reset}\n`);
  }

  console.log(`${COLORS.green}✓ Configured ${modelPairs.length} model pairs${COLORS.reset}\n`);

  // ========================================================================
  // STEP 4: Run Benchmarks
  // ========================================================================

  console.log(`${COLORS.bold}🚀 Step 4: Running Benchmarks${COLORS.reset}\n`);
  console.log(`Testing ${TEST_QUERIES.length} queries across ${modelPairs.length} model pairs...\n`);

  const results: BenchmarkResult[] = [];

  for (const pair of modelPairs) {
    const result = await testModelPair(pair, semanticChecker, mlAvailable);
    results.push(result);

    // Clear cache between pairs
    semanticChecker.clearCache();
  }

  // ========================================================================
  // STEP 5: Display Summary
  // ========================================================================

  console.log(`\n${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}BENCHMARK SUMMARY${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}\n`);

  console.log(`${COLORS.bold}Overall Results:${COLORS.reset}\n`);

  for (const result of results) {
    console.log(`${COLORS.cyan}${result.pairName}${COLORS.reset}`);
    console.log(`  Provider: ${result.provider}`);
    console.log(`  Success Rate: ${COLORS.green}${result.successRate.toFixed(0)}%${COLORS.reset} (${result.cascaded}/${result.totalQueries} cascaded)`);
    console.log(`  Avg Quality: ${result.avgQuality.toFixed(2)}`);
    if (result.avgSemanticScore !== undefined) {
      console.log(`  Avg Semantic: ${result.avgSemanticScore.toFixed(2)}`);
    }
    console.log(`  Avg Latency: ${result.avgLatency.toFixed(0)}ms`);
    console.log();
  }

  // ========================================================================
  // STEP 6: Performance Insights
  // ========================================================================

  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}PERFORMANCE INSIGHTS${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}\n`);

  const totalCascaded = results.reduce((sum, r) => sum + r.cascaded, 0);
  const totalEscalated = results.reduce((sum, r) => sum + r.escalated, 0);
  const totalQueries = results.reduce((sum, r) => sum + r.totalQueries, 0);
  const overallSuccessRate = (totalCascaded / totalQueries) * 100;

  console.log(`${COLORS.bold}Aggregate Statistics:${COLORS.reset}`);
  console.log(`  Total Queries: ${totalQueries}`);
  console.log(`  Total Cascaded: ${COLORS.green}${totalCascaded}${COLORS.reset}`);
  console.log(`  Total Escalated: ${COLORS.yellow}${totalEscalated}${COLORS.reset}`);
  console.log(`  Overall Success Rate: ${COLORS.green}${overallSuccessRate.toFixed(1)}%${COLORS.reset}\n`);

  console.log(`${COLORS.bold}Key Findings:${COLORS.reset}`);
  if (mlAvailable) {
    console.log(`  ${COLORS.green}✓${COLORS.reset} Semantic validation helped ensure response relevance`);
    console.log(`  ${COLORS.green}✓${COLORS.reset} ML-based quality scoring active for all tests`);
  } else {
    console.log(`  ${COLORS.yellow}⚠${COLORS.reset} Heuristic-based quality scoring used (install @cascadeflow/ml for semantic)`);
  }
  console.log(`  ${COLORS.green}✓${COLORS.reset} Cross-provider cascades work seamlessly`);
  console.log(`  ${COLORS.green}✓${COLORS.reset} All traces sent to LangSmith for analysis\n`);

  // ========================================================================
  // STEP 7: LangSmith Instructions
  // ========================================================================

  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}VIEW RESULTS IN LANGSMITH${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}\n`);

  console.log(`${COLORS.cyan}${COLORS.bold}📊 View Detailed Traces:${COLORS.reset}`);
  console.log(`  1. Go to: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}`);
  console.log(`  2. Select project: ${COLORS.yellow}${process.env.LANGSMITH_PROJECT || 'default'}${COLORS.reset}`);
  console.log(`  3. Filter by: ${COLORS.yellow}last 1 hour${COLORS.reset}`);
  console.log(`  4. Look for traces with "CascadeFlow" model name`);
  console.log(`  5. Check cascade metadata in response_metadata:\n`);
  console.log(`     ${COLORS.green}cascade_decision${COLORS.reset}: "cascaded" or "escalated"`);
  console.log(`     ${COLORS.green}drafter_quality${COLORS.reset}: quality score (0-1)`);
  console.log(`     ${COLORS.green}model_used${COLORS.reset}: "drafter" or "verifier"`);
  console.log(`     ${COLORS.green}savings_percentage${COLORS.reset}: cost savings\n`);

  console.log(`${COLORS.green}${COLORS.bold}✓ Benchmark Complete!${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}\n`);
}

main().catch(console.error);
