/**
 * Model Discovery Example
 *
 * Shows how to discover the best cascade pairs from YOUR existing LangChain models.
 * No hard-coded models - this works with whatever models YOU have configured!
 */

import {
  CascadeWrapper,
  discoverCascadePairs,
  findBestCascadePair,
  analyzeModel,
  compareModels,
  validateCascadePair,
} from '../src/index.js';
import { ChatOpenAI } from '@langchain/openai';

console.log('='.repeat(80));
console.log('MODEL DISCOVERY - Works with YOUR models!');
console.log('='.repeat(80));

// ============================================================================
// Setup: Create YOUR models (with YOUR API keys)
// ============================================================================
console.log('\nYOUR Models (configured with your own API keys):');
console.log('-'.repeat(80));

// These are YOUR models - could be OpenAI, Anthropic, local Ollama, etc.
const myModels = [
  new ChatOpenAI({ modelName: 'gpt-3.5-turbo' }),  // Your cheap model
  new ChatOpenAI({ modelName: 'gpt-4o-mini' }),    // Your fast model
  new ChatOpenAI({ modelName: 'gpt-4o' }),         // Your powerful model
  // Add more of YOUR models here:
  // new ChatAnthropic({ model: 'claude-3-haiku' }),
  // new ChatOllama({ model: 'llama2' }),
  // etc.
];

console.log(`You have ${myModels.length} models configured.`);

// ============================================================================
// Example 1: Discover Best Cascade Pairs
// ============================================================================
console.log('\n\n1. Discover Best Cascade Pairs from YOUR Models');
console.log('-'.repeat(80));

const suggestions = discoverCascadePairs(myModels);

console.log(`\nFound ${suggestions.length} valid cascade pairs:`);
suggestions.forEach(pair => {
  console.log(`\n#${pair.rank}:`);
  console.log(`  Drafter:  ${pair.analysis.drafterModel}`);
  console.log(`  Verifier: ${pair.analysis.verifierModel}`);
  console.log(`  Estimated savings: ${pair.analysis.estimatedSavings.toFixed(1)}%`);
  console.log(`  ${pair.analysis.recommendation}`);
});

// ============================================================================
// Example 2: Quick - Find Best Pair
// ============================================================================
console.log('\n\n2. Quick Way - Find Best Pair');
console.log('-'.repeat(80));

const best = findBestCascadePair(myModels);

if (best) {
  console.log('\nBest cascade configuration:');
  console.log(`Drafter:  ${best.analysis.drafterModel}`);
  console.log(`Verifier: ${best.analysis.verifierModel}`);
  console.log(`Savings:  ${best.estimatedSavings.toFixed(1)}%`);

  // Use it!
  const cascade = new CascadeWrapper({
    drafter: best.drafter,
    verifier: best.verifier,
  });

  const result = await cascade.invoke('What is TypeScript?');
  console.log(`\nResponse: ${result.content.substring(0, 150)}...`);

  const stats = cascade.getLastCascadeResult();
  console.log(`Model used: ${stats?.modelUsed}`);
  console.log(`Actual cost: $${stats?.totalCost.toFixed(6)}`);
  console.log(`Actual savings: ${stats?.savingsPercentage.toFixed(1)}%`);
} else {
  console.log('No valid cascade pairs found. Need at least 2 models with different costs.');
}

// ============================================================================
// Example 3: Analyze Individual Models
// ============================================================================
console.log('\n\n3. Analyze Your Individual Models');
console.log('-'.repeat(80));

myModels.forEach(model => {
  const analysis = analyzeModel(model);
  console.log(`\n${analysis.modelName} (${analysis.provider}):`);
  console.log(`  Tier: ${analysis.tier}`);
  if (analysis.estimatedCost) {
    console.log(`  Cost: $${analysis.estimatedCost.input}/$${analysis.estimatedCost.output} per 1M tokens`);
  } else {
    console.log(`  Cost: Unknown (add to MODEL_PRICING_REFERENCE if you know it)`);
  }
  console.log(`  ${analysis.recommendation}`);
});

// ============================================================================
// Example 4: Compare Models
// ============================================================================
console.log('\n\n4. Compare and Rank Your Models');
console.log('-'.repeat(80));

const comparison = compareModels(myModels);

console.log('\nBest Drafter Candidates (cheap, fast):');
comparison.drafterCandidates.forEach((c, i) => {
  console.log(`  ${i + 1}. ${c.analysis.modelName} - ${c.analysis.tier}`);
});

console.log('\nBest Verifier Candidates (expensive, powerful):');
comparison.verifierCandidates.forEach((c, i) => {
  console.log(`  ${i + 1}. ${c.analysis.modelName} - ${c.analysis.tier}`);
});

// ============================================================================
// Example 5: Validate a Specific Pair
// ============================================================================
console.log('\n\n5. Validate a Specific Cascade Pair');
console.log('-'.repeat(80));

if (myModels.length >= 2) {
  const validation = validateCascadePair(myModels[0], myModels[myModels.length - 1]);

  console.log(`\nPair: ${myModels[0]._llmType()} → ${myModels[myModels.length - 1]._llmType()}`);
  console.log(`Valid: ${validation.valid}`);
  console.log(`Estimated savings: ${validation.estimatedSavings.toFixed(1)}%`);
  console.log(`Recommendation: ${validation.recommendation}`);

  if (validation.warnings.length > 0) {
    console.log('\nWarnings:');
    validation.warnings.forEach((w, i) => {
      console.log(`  ${i + 1}. ${w}`);
    });
  }
}

// ============================================================================
// Example 6: Filter by Requirements
// ============================================================================
console.log('\n\n6. Filter Cascade Pairs by Requirements');
console.log('-'.repeat(80));

// Only show pairs with at least 50% savings
const highSavingsPairs = discoverCascadePairs(myModels, {
  minSavings: 50,
});

console.log(`\nPairs with ≥50% savings: ${highSavingsPairs.length}`);
highSavingsPairs.forEach(pair => {
  console.log(`  - ${pair.analysis.drafterModel} → ${pair.analysis.verifierModel} (${pair.analysis.estimatedSavings.toFixed(1)}%)`);
});

// Only show pairs from the same provider
const sameProviderPairs = discoverCascadePairs(myModels, {
  requireSameProvider: true,
});

console.log(`\nSame-provider pairs: ${sameProviderPairs.length}`);
sameProviderPairs.forEach(pair => {
  console.log(`  - ${pair.analysis.drafterModel} → ${pair.analysis.verifierModel}`);
});

// ============================================================================
// Example 7: Real-World Usage Pattern
// ============================================================================
console.log('\n\n7. Real-World Usage Pattern');
console.log('-'.repeat(80));

console.log('\nTypical workflow:');
console.log('1. Configure YOUR LangChain models (with your API keys)');
console.log('2. Discover best cascade pairs');
console.log('3. Create cascade with best pair');
console.log('4. Use it just like a normal LangChain model!');

console.log('\nCode example:');
console.log(`
// Step 1: YOUR models
const myModels = [
  new ChatOpenAI({ model: 'gpt-4o-mini' }),  // configured with YOUR key
  new ChatOpenAI({ model: 'gpt-4o' }),       // configured with YOUR key
];

// Step 2: Find best pair
const best = findBestCascadePair(myModels);

// Step 3: Create cascade
const cascade = new CascadeWrapper({
  drafter: best.drafter,
  verifier: best.verifier,
});

// Step 4: Use it!
const result = await cascade.invoke('Your question');
`);

console.log('\n' + '='.repeat(80));
console.log('✓ Model discovery complete!');
console.log('  All analysis done on YOUR models - no hardcoded instances!');
console.log('='.repeat(80) + '\n');
