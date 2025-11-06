/**
 * Cascade Example: Grok Code Fast → Claude 4.5 Sonnet
 *
 * Demonstrates cascading from free tier to premium tier:
 * - Tier 1: x-ai/grok-code-fast-1 (FREE)
 * - Tier 2: anthropic/claude-4.5-sonnet-20250929 ($3/$15 per 1M tokens)
 *
 * Shows cost optimization by using free model first, escalating only when needed.
 *
 * Requirements:
 *   - @cascadeflow/core
 *   - OPENROUTER_API_KEY environment variable
 *
 * Usage:
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx grok-claude-cascade.ts
 */

import { CascadeAgent } from '@cascadeflow/core';

async function main() {
  if (!process.env.OPENROUTER_API_KEY) {
    console.error('Error: OPENROUTER_API_KEY environment variable required');
    console.error('Get key from: https://openrouter.ai/keys');
    process.exit(1);
  }

  console.log('Cascade Configuration:');
  console.log('  Tier 1: x-ai/grok-code-fast-1 (free, threshold 0.7)');
  console.log('  Tier 2: anthropic/claude-4.5-sonnet-20250929 ($3/$15 per 1M tokens)');
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
        name: 'anthropic/claude-4.5-sonnet-20250929',
        provider: 'openrouter',
        cost: 0.003, // $3 input, $15 output per 1M tokens
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
    initialThreshold: 0.7,
  });

  // Test queries with varying complexity
  const queries = [
    {
      prompt: 'What is binary search?',
      expected: 'Should use tier 1 (simple explanation)',
    },
    {
      prompt: 'Explain the trade-offs between quicksort and mergesort.',
      expected: 'May escalate to tier 2',
    },
    {
      prompt: 'Design a distributed rate limiter with Redis. Include edge cases.',
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

    if (result.savingsPercentage !== undefined) {
      console.log(`  Savings: ${result.savingsPercentage.toFixed(1)}%`);
    }

    console.log();
  }

  // Summary
  const grokCount = results.filter(r => r.modelUsed.includes('grok')).length;
  const claudeCount = results.filter(r => r.modelUsed.includes('claude')).length;
  const totalCost = results.reduce((sum, r) => sum + r.totalCost, 0);

  // Calculate what it would cost if we used Claude for everything
  const claudeOnlyCost = claudeCount > 0
    ? (totalCost / claudeCount) * results.length
    : 0.009 * results.length; // Estimate

  const actualSavings = claudeOnlyCost > 0
    ? ((claudeOnlyCost - totalCost) / claudeOnlyCost) * 100
    : 0;

  console.log('Session Summary:');
  console.log(`  Total queries: ${results.length}`);
  console.log(`  Grok (tier 1): ${grokCount}`);
  console.log(`  Claude (tier 2): ${claudeCount}`);
  console.log(`  Total cost: $${totalCost.toFixed(6)}`);
  console.log(`  Claude-only cost: $${claudeOnlyCost.toFixed(6)}`);
  console.log(`  Savings: ${actualSavings.toFixed(1)}%`);
  console.log(`  Cascade effectiveness: ${(grokCount / results.length * 100).toFixed(0)}% handled by tier 1`);
  console.log();
}

main().catch(console.error);
