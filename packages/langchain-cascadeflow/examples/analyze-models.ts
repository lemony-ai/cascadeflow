/**
 * Model Analysis Example
 *
 * Demonstrates how to analyze and validate cascade configurations
 * using your existing LangChain model instances.
 */

import { ChatOpenAI } from '@langchain/openai';
import { analyzeCascadePair, suggestCascadePairs } from '../src/index.js';

async function main() {
  console.log('=== CascadeFlow Model Analysis Demo ===\n');

  // Example 1: Analyze a specific drafter/verifier pair
  console.log('--- Example 1: Analyze OpenAI Cascade Pair ---');

  const drafterOpenAI = new ChatOpenAI({ model: 'gpt-4o-mini' });
  const verifierOpenAI = new ChatOpenAI({ model: 'gpt-4o' });

  const analysis1 = analyzeCascadePair(drafterOpenAI, verifierOpenAI);

  console.log(`Drafter: ${analysis1.drafterModel}`);
  console.log(`Verifier: ${analysis1.verifierModel}`);
  console.log(`\nPricing (per 1M tokens):`);
  console.log(`  Drafter: $${analysis1.drafterCost.input} input / $${analysis1.drafterCost.output} output`);
  console.log(`  Verifier: $${analysis1.verifierCost.input} input / $${analysis1.verifierCost.output} output`);
  console.log(`\nEstimated Savings: ${analysis1.estimatedSavings.toFixed(1)}%`);
  console.log(`Configuration Valid: ${analysis1.valid ? '✅' : '❌'}`);
  console.log(`Recommendation: ${analysis1.recommendation}`);

  if (analysis1.warnings.length > 0) {
    console.log(`\nWarnings:`);
    analysis1.warnings.forEach(w => console.log(`  ⚠️  ${w}`));
  }
  console.log('\n');

  // Example 2: Detect misconfiguration (drafter more expensive than verifier)
  console.log('--- Example 2: Detect Misconfiguration ---');

  const expensiveDrafter = new ChatOpenAI({ model: 'gpt-4o' });
  const cheapVerifier = new ChatOpenAI({ model: 'gpt-4o-mini' });

  const analysis2 = analyzeCascadePair(expensiveDrafter, cheapVerifier);

  console.log(`Drafter: ${analysis2.drafterModel}`);
  console.log(`Verifier: ${analysis2.verifierModel}`);
  console.log(`Configuration Valid: ${analysis2.valid ? '✅' : '❌'}`);
  console.log(`Recommendation: ${analysis2.recommendation}`);

  if (analysis2.warnings.length > 0) {
    console.log(`\nWarnings:`);
    analysis2.warnings.forEach(w => console.log(`  ⚠️  ${w}`));
  }
  console.log('\n');

  // Example 3: Suggest optimal pairs from available models
  console.log('--- Example 3: Suggest Optimal Cascade Pairs ---');

  const availableModels = [
    new ChatOpenAI({ model: 'gpt-4o-mini' }),
    new ChatOpenAI({ model: 'gpt-4o' }),
    new ChatOpenAI({ model: 'gpt-3.5-turbo' }),
    new ChatOpenAI({ model: 'gpt-4-turbo' }),
  ];

  console.log(`Analyzing ${availableModels.length} available models...\n`);

  const suggestions = suggestCascadePairs(availableModels);

  console.log(`Found ${suggestions.length} viable cascade configurations:\n`);

  suggestions.slice(0, 5).forEach((suggestion, idx) => {
    const { drafter, verifier, analysis } = suggestion;
    console.log(`${idx + 1}. ${analysis.drafterModel} → ${analysis.verifierModel}`);
    console.log(`   Estimated Savings: ${analysis.estimatedSavings.toFixed(1)}%`);
    console.log(`   ${analysis.recommendation}`);
    console.log();
  });

  console.log('=== Analysis Complete ===');
  console.log('\n💡 Use analyzeCascadePair() to validate your cascade configuration');
  console.log('💡 Use suggestCascadePairs() to find optimal pairs from your models');
}

main().catch(console.error);
