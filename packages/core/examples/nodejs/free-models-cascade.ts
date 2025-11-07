/**
 * Cascade Example: Grok Code Fast → MiniMax M2
 *
 * Demonstrates cascading between two cost-effective models via OpenRouter:
 * - Tier 1: x-ai/grok-code-fast-1 (FREE)
 * - Tier 2: minimax/minimax-m2 ($0.10 per 1M tokens)
 *
 * Shows how cascade routing works when quality thresholds aren't met.
 *
 * Requirements:
 *   - @cascadeflow/core
 *   - OPENROUTER_API_KEY environment variable
 *
 * Usage:
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx free-models-cascade.ts
 */

import { CascadeAgent } from '@cascadeflow/core';

async function main() {
  if (!process.env.OPENROUTER_API_KEY) {
    console.error('Error: OPENROUTER_API_KEY environment variable required');
    console.error('Get key from: https://openrouter.ai/keys');
    process.exit(1);
  }

  console.log('Cascade Configuration:');
  console.log('  Tier 1: x-ai/grok-code-fast-1 (free, complexity-aware thresholds)');
  console.log('  Tier 2: minimax/minimax-m2 ($0.10/1M tokens)');
  console.log('  Strategy: Lower thresholds to maximize free tier usage');
  console.log();

  // Configure 2-tier cascade
  const agent = new CascadeAgent({
    models: [
      {
        name: 'x-ai/grok-code-fast-1',
        provider: 'openrouter',
        cost: 0,
        apiKey: process.env.OPENROUTER_API_KEY,
      },
      {
        name: 'minimax/minimax-m2',
        provider: 'openrouter',
        cost: 0.0001, // $0.10 per 1M tokens
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
    quality: {
      // Lower thresholds for free tier - maximize free model usage
      confidenceThresholds: {
        simple: 0.35,     // Very lenient for simple queries (free model is fine)
        moderate: 0.5,    // Moderate leniency for comparisons
        hard: 0.65,    // More selective for complex queries
        expert: 0.75      // Escalate expert queries to paid tier
      },
      requireMinimumTokens: 5,
    },
  });

  // Test queries with varying complexity
  const queries = [
    {
      prompt: 'What is 2+2?',
      expected: 'Should use tier 1 (simple query)',
    },
    {
      prompt: 'Explain the difference between map() and flatMap() in JavaScript.',
      expected: 'May escalate to tier 2',
    },
    {
      prompt: 'Write a function to implement a LRU cache with O(1) operations.',
      expected: 'Likely escalates to tier 2',
    },
  ];

  const results = [];

  for (let i = 0; i < queries.length; i++) {
    const { prompt, expected } = queries[i];

    console.log(`Query ${i + 1}: ${prompt}`);
    console.log(`Expected: ${expected}`);

    const start = Date.now();
    const result = await agent.run(prompt);
    const elapsed = Date.now() - start;

    results.push(result);

    console.log('Result:');
    console.log(`  Model used: ${result.modelUsed}`);
    console.log(`  Cascaded: ${result.cascaded}`);
    console.log(`  Draft accepted: ${result.draftAccepted}`);
    console.log(`  Cost: $${result.totalCost.toFixed(6)}`);
    console.log(`  Latency: ${elapsed}ms`);
    console.log(`  Response length: ${result.content.length} chars`);

    if (result.savingsPercentage !== undefined) {
      console.log(`  Savings: ${result.savingsPercentage.toFixed(1)}%`);
    }

    console.log();
  }

  // Summary
  const grokCount = results.filter(r => r.modelUsed.includes('grok')).length;
  const minimaxCount = results.filter(r => r.modelUsed.includes('minimax')).length;
  const totalCost = results.reduce((sum, r) => sum + r.totalCost, 0);

  console.log('Session Summary:');
  console.log(`  Total queries: ${results.length}`);
  console.log(`  Grok (tier 1): ${grokCount}`);
  console.log(`  MiniMax (tier 2): ${minimaxCount}`);
  console.log(`  Total cost: $${totalCost.toFixed(6)}`);
  console.log(`  Cascade effectiveness: ${(grokCount / results.length * 100).toFixed(0)}% handled by tier 1`);
  console.log();
}

main().catch(console.error);
