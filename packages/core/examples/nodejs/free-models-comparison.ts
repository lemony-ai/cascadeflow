/**
 * Free & Ultra-Cheap Models: Grok Code Fast + MiniMax M2
 *
 * This example demonstrates using two of the most cost-effective models on OpenRouter:
 * 1. Grok Code Fast - 100% FREE (53.1% of OpenRouter traffic)
 * 2. MiniMax M2 - Ultra-cheap at $0.10 per 1M tokens (11.0% of traffic)
 *
 * Perfect for:
 * - Budget-conscious applications
 * - High-volume processing
 * - Learning and experimentation
 * - Prototyping without cost concerns
 * - Comparing different model outputs
 *
 * Cost Comparison:
 * - Grok Code Fast: $0 (FREE)
 * - MiniMax M2: $0.10 per 1M tokens (~$0.0001 per conversation)
 * - GPT-4o: $2.50-$10 per 1M tokens (25-100x more expensive)
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenRouter API key (get from https://openrouter.ai/keys)
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx free-models-comparison.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('💸 FREE & ULTRA-CHEAP MODELS COMPARISON');
  console.log('='.repeat(80));
  console.log();

  // Check for OpenRouter API key
  if (!process.env.OPENROUTER_API_KEY) {
    console.error('❌ OPENROUTER_API_KEY environment variable is required');
    console.error('');
    console.error('Get your API key: https://openrouter.ai/keys');
    console.error('Then run: export OPENROUTER_API_KEY="your-key"');
    process.exit(1);
  }

  console.log('🔑 API Key Status:');
  console.log('   ✅ OpenRouter API key found');
  console.log();

  console.log('🤖 Models Being Compared:');
  console.log();
  console.log('   1. Grok Code Fast (X.AI)');
  console.log('      • Cost: FREE (100% free!) 🎉');
  console.log('      • Traffic: 53.1% (most popular on OpenRouter)');
  console.log('      • Best for: Code generation, fast responses');
  console.log();
  console.log('   2. MiniMax M2');
  console.log('      • Cost: $0.10 per 1M tokens (~$0.0001/conversation) 💰');
  console.log('      • Traffic: 11.0% (highly trusted)');
  console.log('      • Best for: Multilingual, creative writing, balanced tasks');
  console.log();

  // ========================================================================
  // Example 1: Side-by-Side Code Generation
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 1: Code Generation Comparison');
  console.log('='.repeat(80));
  console.log();

  const codePrompt = 'Write a JavaScript function to debounce another function. Include comments.';
  console.log(`Prompt: "${codePrompt}"\n`);

  // Test with Grok Code Fast
  console.log('-'.repeat(80));
  console.log('🤖 GROK CODE FAST RESPONSE (FREE):');
  console.log('-'.repeat(80));

  const grokAgent = new CascadeAgent({
    models: [
      {
        name: 'x-ai/grok-code-fast-1',
        provider: 'openrouter',
        cost: 0, // FREE!
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  const start1 = Date.now();
  const grokResult = await grokAgent.run(codePrompt);
  const elapsed1 = Date.now() - start1;

  console.log(grokResult.content);
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Latency: ${elapsed1}ms`);
  console.log(`   Cost: FREE 🎉`);
  console.log();

  // Test with MiniMax M2
  console.log('-'.repeat(80));
  console.log('🤖 MINIMAX M2 RESPONSE ($0.10 per 1M tokens):');
  console.log('-'.repeat(80));

  const minimaxAgent = new CascadeAgent({
    models: [
      {
        name: 'minimax/minimax-m2',
        provider: 'openrouter',
        cost: 0.0001, // $0.10 per 1M tokens
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  const start2 = Date.now();
  const minimaxResult = await minimaxAgent.run(codePrompt);
  const elapsed2 = Date.now() - start2;

  console.log(minimaxResult.content);
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Latency: ${elapsed2}ms`);
  console.log(`   Cost: $${minimaxResult.totalCost.toFixed(6)} (~$0.0001)`);
  console.log();

  // ========================================================================
  // Example 2: Cascade Strategy (Grok → MiniMax)
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 2: Smart Cascade (Free → Ultra-Cheap)');
  console.log('='.repeat(80));
  console.log();

  console.log('Strategy: Try FREE Grok first, fall back to MiniMax if needed\n');

  const cascadeAgent = new CascadeAgent({
    models: [
      {
        name: 'x-ai/grok-code-fast-1',
        provider: 'openrouter',
        cost: 0, // FREE tier
        apiKey: process.env.OPENROUTER_API_KEY,
      },
      {
        name: 'minimax/minimax-m2',
        provider: 'openrouter',
        cost: 0.0001, // Ultra-cheap fallback
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  const cascadePrompts = [
    'What is binary search?',
    'Explain the difference between Promise.all() and Promise.race() in JavaScript.',
    'Write a function to find the longest palindromic substring in a string.',
  ];

  let totalCascadeCost = 0;
  const cascadeResults = [];

  for (let i = 0; i < cascadePrompts.length; i++) {
    const prompt = cascadePrompts[i];
    console.log(`Query ${i + 1}: "${prompt}"`);

    const start = Date.now();
    const result = await cascadeAgent.run(prompt);
    const elapsed = Date.now() - start;

    cascadeResults.push(result);
    totalCascadeCost += result.totalCost;

    console.log(`   ✅ Model used: ${result.modelUsed}`);
    console.log(`   ⚡ Latency: ${elapsed}ms`);
    console.log(`   💰 Cost: ${result.totalCost === 0 ? 'FREE' : `$${result.totalCost.toFixed(6)}`}`);
    console.log();
  }

  // ========================================================================
  // Example 3: Multilingual Comparison
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 3: Multilingual Capabilities');
  console.log('='.repeat(80));
  console.log();

  console.log('Testing: Generate a greeting in 3 languages (English, Spanish, Chinese)\n');

  const multilingualPrompt = 'Write a friendly greeting in English, Spanish, and Chinese. Just the greetings, one per line.';

  console.log('-'.repeat(80));
  console.log('🤖 GROK CODE FAST:');
  console.log('-'.repeat(80));

  const grokMulti = await grokAgent.run(multilingualPrompt);
  console.log(grokMulti.content);
  console.log(`Cost: FREE\n`);

  console.log('-'.repeat(80));
  console.log('🤖 MINIMAX M2:');
  console.log('-'.repeat(80));

  const minimaxMulti = await minimaxAgent.run(multilingualPrompt);
  console.log(minimaxMulti.content);
  console.log(`Cost: $${minimaxMulti.totalCost.toFixed(6)}\n`);

  // ========================================================================
  // Example 4: Batch Processing Simulation
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 4: Batch Processing Cost Analysis');
  console.log('='.repeat(80));
  console.log();

  console.log('Simulating 100 queries with both models...\n');

  // Simulate costs for 100 queries (using actual costs from our tests)
  const grok100Cost = 0; // Always free
  const minimax100Cost = minimaxResult.totalCost * 100;

  console.log('📊 Cost Comparison for 100 Queries:');
  console.log(`   Grok Code Fast: $0.00 (FREE)`);
  console.log(`   MiniMax M2: $${minimax100Cost.toFixed(4)}`);
  console.log();

  // Compare with expensive models (estimated)
  const gpt4Cost = 0.025 * 100; // Approx $0.025 per query
  const claudeCost = 0.030 * 100; // Approx $0.030 per query

  console.log('💰 Savings vs Premium Models (100 queries):');
  console.log(`   vs GPT-4o: Save $${gpt4Cost.toFixed(2)} (using Grok)`);
  console.log(`   vs Claude Sonnet: Save $${claudeCost.toFixed(2)} (using Grok)`);
  console.log();

  // ========================================================================
  // Summary
  // ========================================================================

  const grokUsage = cascadeResults.filter(r => r.modelUsed.includes('grok')).length;
  const minimaxUsage = cascadeResults.filter(r => r.modelUsed.includes('minimax')).length;

  console.log('='.repeat(80));
  console.log('📊 SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();

  console.log('🎯 Models Used:');
  console.log(`   Grok Code Fast: 2 direct queries + ${grokUsage}/3 cascade`);
  console.log(`   MiniMax M2: 2 direct queries + ${minimaxUsage}/3 cascade`);
  console.log();

  console.log('💰 Cost Breakdown:');
  console.log(`   Grok queries: $0.00 (FREE)`);
  console.log(`   MiniMax queries: $${(minimaxResult.totalCost + minimaxMulti.totalCost).toFixed(6)}`);
  console.log(`   Cascade total: $${totalCascadeCost.toFixed(6)}`);
  console.log(`   Grand total: $${(minimaxResult.totalCost + minimaxMulti.totalCost + totalCascadeCost).toFixed(6)}`);
  console.log();

  console.log('='.repeat(80));
  console.log('💡 KEY INSIGHTS');
  console.log('='.repeat(80));
  console.log();

  console.log('✅ Grok Code Fast (FREE):');
  console.log('   • 100% free, no limits with OpenRouter key');
  console.log('   • 53.1% of OpenRouter traffic (most popular)');
  console.log('   • Fast inference, great for code generation');
  console.log('   • Perfect for development and testing');
  console.log('   • Best choice for: Simple queries, code snippets, prototyping');
  console.log();

  console.log('✅ MiniMax M2 ($0.10 per 1M tokens):');
  console.log('   • Ultra-cheap: ~$0.0001 per conversation');
  console.log('   • 11.0% of OpenRouter traffic (trusted by users)');
  console.log('   • Strong multilingual capabilities');
  console.log('   • Good for: Diverse tasks, multilingual content, balanced quality');
  console.log('   • 25-100x cheaper than GPT-4o or Claude');
  console.log();

  console.log('🎯 Recommendation:');
  console.log('   • Use Grok Code Fast as default (it\'s FREE!)');
  console.log('   • Use MiniMax M2 for multilingual or when more balance needed');
  console.log('   • Cascade Grok → MiniMax for best cost optimization');
  console.log('   • Both are excellent for high-volume applications');
  console.log();

  console.log('💸 Cost Comparison (per 1M tokens):');
  console.log('   • Grok Code Fast: $0 (FREE)');
  console.log('   • MiniMax M2: $0.10 (ultra-cheap)');
  console.log('   • GPT-4o Mini: $0.15 (1.5x more than MiniMax)');
  console.log('   • GPT-4o: $2.50-$10 (25-100x more)');
  console.log('   • Claude Sonnet: $3-$15 (30-150x more)');
  console.log();

  console.log('🚀 Next Steps:');
  console.log('   • Try high-volume batch processing with Grok (FREE!)');
  console.log('   • Test multilingual capabilities with MiniMax');
  console.log('   • Compare output quality vs premium models');
  console.log('   • Experiment with different cascade strategies');
  console.log('   • Browse more free models: https://openrouter.ai/models');
  console.log();
}

main().catch(console.error);
