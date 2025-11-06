/**
 * Grok Code Fast Example - Free Tier via OpenRouter
 *
 * This example demonstrates using X.AI's Grok Code Fast model through OpenRouter.
 * Grok Code Fast is the most popular model on OpenRouter (53.1% of traffic) and
 * is completely FREE to use!
 *
 * Perfect for:
 * - Fast code generation
 * - Quick prototyping
 * - Learning and experimentation
 * - Cost-sensitive applications
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenRouter API key (get from https://openrouter.ai/keys)
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx grok-code-fast-example.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('⚡ GROK CODE FAST - FREE AI CODE GENERATION');
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

  console.log('🤖 Model: x-ai/grok-code-fast-1');
  console.log('   Provider: X.AI (via OpenRouter)');
  console.log('   Cost: FREE ✨');
  console.log('   Usage: 53.1% of all OpenRouter traffic (most popular!)');
  console.log('   Best for: Fast code generation, prototyping, quick answers');
  console.log();

  // ========================================================================
  // Example 1: Simple Code Generation
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 1: Simple Code Generation');
  console.log('='.repeat(80));
  console.log();

  const agent = new CascadeAgent({
    models: [
      {
        name: 'x-ai/grok-code-fast-1',
        provider: 'openrouter',
        cost: 0, // FREE!
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  console.log('Query: "Write a Python function to check if a number is prime"\n');

  const startTime1 = Date.now();
  const result1 = await agent.run(
    'Write a Python function to check if a number is prime. Include docstring and type hints.'
  );
  const elapsed1 = Date.now() - startTime1;

  console.log('✅ Response:');
  console.log('-'.repeat(80));
  console.log(result1.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Model: ${result1.modelUsed}`);
  console.log(`   Tokens: ${result1.promptTokens} in / ${result1.completionTokens} out`);
  console.log(`   Latency: ${elapsed1}ms`);
  console.log(`   Cost: FREE 💰`);
  console.log();

  // ========================================================================
  // Example 2: Code Explanation
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 2: Code Explanation');
  console.log('='.repeat(80));
  console.log();

  const codeToExplain = `
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)
`;

  console.log('Query: "Explain this code step by step"');
  console.log('Code:');
  console.log(codeToExplain);
  console.log();

  const startTime2 = Date.now();
  const result2 = await agent.run(
    `Explain this code step by step:\n\n${codeToExplain}\n\nProvide a clear explanation for beginners.`
  );
  const elapsed2 = Date.now() - startTime2;

  console.log('✅ Explanation:');
  console.log('-'.repeat(80));
  console.log(result2.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result2.promptTokens} in / ${result2.completionTokens} out`);
  console.log(`   Latency: ${elapsed2}ms`);
  console.log(`   Cost: FREE 💰`);
  console.log();

  // ========================================================================
  // Example 3: Algorithm Suggestions
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 3: Algorithm Suggestions');
  console.log('='.repeat(80));
  console.log();

  console.log('Query: "Suggest efficient algorithms for finding duplicates in a large dataset"\n');

  const startTime3 = Date.now();
  const result3 = await agent.run(
    'Suggest 3 efficient algorithms for finding duplicates in a large dataset. ' +
    'Include time complexity and when to use each.'
  );
  const elapsed3 = Date.now() - startTime3;

  console.log('✅ Suggestions:');
  console.log('-'.repeat(80));
  console.log(result3.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result3.promptTokens} in / ${result3.completionTokens} out`);
  console.log(`   Latency: ${elapsed3}ms`);
  console.log(`   Cost: FREE 💰`);
  console.log();

  // ========================================================================
  // Example 4: Quick Bug Fix
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 4: Quick Bug Fix');
  console.log('='.repeat(80));
  console.log();

  const buggyCode = `
function fetchData(url) {
  fetch(url)
    .then(response => response.json())
    .then(data => console.log(data))
}
`;

  console.log('Query: "Find and fix the bug in this code"');
  console.log('Buggy Code:');
  console.log(buggyCode);
  console.log();

  const startTime4 = Date.now();
  const result4 = await agent.run(
    `Find and fix the bug in this code:\n\n${buggyCode}\n\nExplain what was wrong and provide the corrected version.`
  );
  const elapsed4 = Date.now() - startTime4;

  console.log('✅ Bug Fix:');
  console.log('-'.repeat(80));
  console.log(result4.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result4.promptTokens} in / ${result4.completionTokens} out`);
  console.log(`   Latency: ${elapsed4}ms`);
  console.log(`   Cost: FREE 💰`);
  console.log();

  // ========================================================================
  // Summary
  // ========================================================================

  const totalTokens = result1.promptTokens + result1.completionTokens +
                      result2.promptTokens + result2.completionTokens +
                      result3.promptTokens + result3.completionTokens +
                      result4.promptTokens + result4.completionTokens;

  const totalTime = elapsed1 + elapsed2 + elapsed3 + elapsed4;

  console.log('='.repeat(80));
  console.log('📊 SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ Completed 4 code generation tasks');
  console.log(`   Total tokens used: ${totalTokens.toLocaleString()}`);
  console.log(`   Total time: ${totalTime}ms`);
  console.log(`   Total cost: FREE! 🎉`);
  console.log();
  console.log('💡 Why Grok Code Fast?');
  console.log('   • Completely FREE (no rate limits with OpenRouter key)');
  console.log('   • Fast inference (optimized for speed)');
  console.log('   • Most popular model on OpenRouter (53.1% traffic)');
  console.log('   • Great for learning and prototyping');
  console.log('   • Perfect for cost-sensitive applications');
  console.log();
  console.log('🚀 Next Steps:');
  console.log('   • Try more complex prompts');
  console.log('   • Mix with premium models for cascading');
  console.log('   • Browse other free models: https://openrouter.ai/models');
  console.log('   • Check OpenRouter rankings: https://openrouter.ai/rankings');
  console.log();
}

main().catch(console.error);
