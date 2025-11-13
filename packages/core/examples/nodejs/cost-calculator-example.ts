/**
 * Cost Calculator Example
 *
 * Demonstrates how to use the CostCalculator to track and analyze
 * costs for cascade operations.
 */

import {
  CascadeAgent,
  CostCalculator,
  calculateCascadeCost,
  type CostCalculationFromTokensOptions,
} from '@cascadeflow/core';

async function main() {
  console.log('🧮 Cost Calculator Example\n');

  // Example 1: Calculate costs from a CascadeResult
  console.log('Example 1: Calculate from CascadeResult');
  console.log('─'.repeat(50));

  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
      },
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.005,
      },
    ],
    quality: {
      threshold: 0.64,
    },
  });

  const query = 'What is TypeScript?';
  const result = await agent.run(query);

  // Use convenience function
  const breakdown = calculateCascadeCost(result, query);

  console.log(`Query: "${query}"`);
  console.log(`\nCost Breakdown:`);
  console.log(`  Draft cost:    $${breakdown.draftCost.toFixed(6)}`);
  console.log(`  Verifier cost: $${breakdown.verifierCost.toFixed(6)}`);
  console.log(`  Total cost:    $${breakdown.totalCost.toFixed(6)}`);
  console.log(`  Bigonly cost:  $${breakdown.bigonlyCost.toFixed(6)}`);
  console.log(`  Cost saved:    $${breakdown.costSaved.toFixed(6)}`);
  console.log(`  Savings:       ${breakdown.savingsPercentage.toFixed(1)}%`);
  console.log(`\nToken Usage:`);
  console.log(`  Draft tokens:    ${breakdown.draftTokens}`);
  console.log(`  Verifier tokens: ${breakdown.verifierTokens}`);
  console.log(`  Total tokens:    ${breakdown.totalTokens}`);
  console.log(`\nCascade Status:`);
  console.log(`  Was cascaded:   ${breakdown.wasCascaded}`);
  console.log(`  Draft accepted: ${breakdown.draftAccepted}`);
  console.log(`\nMetadata:`, JSON.stringify(breakdown.metadata, null, 2));

  // Example 2: Calculate from raw token counts
  console.log('\n\nExample 2: Calculate from Token Counts');
  console.log('─'.repeat(50));

  const calculator = new CostCalculator();

  // Simulate a cascade where draft was accepted
  const tokenOptions1: CostCalculationFromTokensOptions = {
    draftOutputTokens: 150,
    verifierOutputTokens: 0, // Not called
    queryInputTokens: 20,
    draftAccepted: true,
    draftModel: 'gpt-4o-mini',
    verifierModel: 'gpt-4o',
    draftProvider: 'openai',
    verifierProvider: 'openai',
  };

  const breakdown1 = await calculator.calculateFromTokens(tokenOptions1);

  console.log('Scenario: Draft accepted (fast path)');
  console.log(`  Total cost:     $${breakdown1.totalCost.toFixed(6)}`);
  console.log(`  Cost saved:     $${breakdown1.costSaved.toFixed(6)}`);
  console.log(`  Savings:        ${breakdown1.savingsPercentage.toFixed(1)}%`);
  console.log(`  Draft tokens:   ${breakdown1.draftTokens}`);
  console.log(`  Verifier tokens: ${breakdown1.verifierTokens}`);

  // Simulate a cascade where draft was rejected
  const tokenOptions2: CostCalculationFromTokensOptions = {
    draftOutputTokens: 150,
    verifierOutputTokens: 200, // Called
    queryInputTokens: 20,
    draftAccepted: false,
    draftModel: 'gpt-4o-mini',
    verifierModel: 'gpt-4o',
    draftProvider: 'openai',
    verifierProvider: 'openai',
  };

  const breakdown2 = await calculator.calculateFromTokens(tokenOptions2);

  console.log('\nScenario: Draft rejected (slow path)');
  console.log(`  Total cost:     $${breakdown2.totalCost.toFixed(6)}`);
  console.log(`  Cost saved:     $${breakdown2.costSaved.toFixed(6)} (negative = wasted)`);
  console.log(`  Savings:        ${breakdown2.savingsPercentage.toFixed(1)}%`);
  console.log(`  Draft tokens:   ${breakdown2.draftTokens}`);
  console.log(`  Verifier tokens: ${breakdown2.verifierTokens}`);

  // Example 3: Token estimation
  console.log('\n\nExample 3: Token Estimation');
  console.log('─'.repeat(50));

  const texts = [
    'Hello',
    'What is TypeScript?',
    'Explain quantum computing in simple terms',
    'The quick brown fox jumps over the lazy dog',
  ];

  console.log('Token estimation from text:');
  for (const text of texts) {
    const tokens = CostCalculator.estimateTokens(text);
    console.log(`  "${text}"`);
    console.log(`    → ~${tokens} tokens\n`);
  }

  // Example 4: Cost comparison
  console.log('\nExample 4: Cost Comparison Across Models');
  console.log('─'.repeat(50));

  const comparisons = [
    {
      name: 'GPT-4o-mini → GPT-4o',
      draft: 'gpt-4o-mini',
      verifier: 'gpt-4o',
      provider: 'openai',
    },
    {
      name: 'Claude Haiku → Claude Sonnet',
      draft: 'claude-3-5-haiku-20241022',
      verifier: 'claude-3-5-sonnet-20241022',
      provider: 'anthropic',
    },
  ];

  for (const comp of comparisons) {
    const br = await calculator.calculateFromTokens({
      draftOutputTokens: 150,
      verifierOutputTokens: 0,
      queryInputTokens: 20,
      draftAccepted: true,
      draftModel: comp.draft,
      verifierModel: comp.verifier,
      draftProvider: comp.provider,
      verifierProvider: comp.provider,
    });

    console.log(`${comp.name}:`);
    console.log(`  Total cost: $${br.totalCost.toFixed(6)}`);
    console.log(`  Savings:    ${br.savingsPercentage.toFixed(1)}%\n`);
  }

  console.log('\n✅ Cost Calculator examples completed!');
}

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}
