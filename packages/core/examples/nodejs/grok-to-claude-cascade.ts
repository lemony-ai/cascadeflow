/**
 * Grok → Claude Cascade Example
 *
 * This example demonstrates the power of cascading from free Grok Code Fast
 * to premium Claude 4.5 Sonnet. This strategy can save up to 80% on costs
 * while maintaining high quality.
 *
 * Strategy:
 * 1. Try FREE Grok Code Fast first (53.1% of traffic, very capable)
 * 2. If confidence is low, escalate to Claude Sonnet (#1 for coding)
 * 3. Automatically optimize cost vs quality
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenRouter API key (get from https://openrouter.ai/keys)
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx grok-to-claude-cascade.ts
 */

import { CascadeAgent } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('💡 SMART CASCADE: FREE GROK → PREMIUM CLAUDE');
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

  console.log('🎯 Cascade Strategy:');
  console.log('   Tier 1: x-ai/grok-code-fast-1 (FREE, 70% threshold)');
  console.log('   Tier 2: anthropic/claude-4.5-sonnet (Premium, fallback)');
  console.log();
  console.log('💰 Expected Savings: 50-80% (most queries use free tier)');
  console.log();

  // Create 2-tier cascade
  const agent = new CascadeAgent({
    models: [
      {
        name: 'x-ai/grok-code-fast-1',
        provider: 'openrouter',
        cost: 0, // FREE!
        apiKey: process.env.OPENROUTER_API_KEY,
      },
      {
        name: 'anthropic/claude-4.5-sonnet-20250929',
        provider: 'openrouter',
        cost: 0.003, // $3/$15 per 1M tokens
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  console.log(`✅ Agent configured with ${agent.getModelCount()}-tier cascade\n`);

  // ========================================================================
  // Test 1: Simple Query (Expected: Grok FREE tier)
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🧪 TEST 1: Simple Query (Expect FREE Tier)');
  console.log('='.repeat(80));
  console.log();

  console.log('Query: "What is a binary search tree?"\n');

  const start1 = Date.now();
  const result1 = await agent.run('What is a binary search tree? Explain in 2-3 sentences.');
  const elapsed1 = Date.now() - start1;

  console.log('📊 Result:');
  console.log(`   Model used: ${result1.modelUsed}`);
  console.log(`   Response: ${result1.content.substring(0, 150)}...`);
  console.log(`   Cost: ${result1.totalCost === 0 ? 'FREE! 🎉' : `$${result1.totalCost.toFixed(6)}`}`);
  console.log(`   Latency: ${elapsed1}ms`);
  console.log(`   Cascaded: ${result1.cascaded ? 'Yes' : 'No'}`);

  if (result1.savingsPercentage !== undefined) {
    console.log(`   Savings: ${result1.savingsPercentage.toFixed(1)}%`);
  }

  console.log();

  // ========================================================================
  // Test 2: Moderate Query (May use either tier)
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🧪 TEST 2: Moderate Complexity');
  console.log('='.repeat(80));
  console.log();

  console.log('Query: "Write a function to reverse a linked list"\n');

  const start2 = Date.now();
  const result2 = await agent.run(
    'Write a TypeScript function to reverse a singly linked list in-place. Include type definitions.'
  );
  const elapsed2 = Date.now() - start2;

  console.log('📊 Result:');
  console.log(`   Model used: ${result2.modelUsed}`);
  console.log(`   Response length: ${result2.content.length} chars`);
  console.log(`   Cost: ${result2.totalCost === 0 ? 'FREE! 🎉' : `$${result2.totalCost.toFixed(6)}`}`);
  console.log(`   Latency: ${elapsed2}ms`);
  console.log(`   Cascaded: ${result2.cascaded ? 'Yes' : 'No'}`);

  if (result2.savingsPercentage !== undefined) {
    console.log(`   Savings: ${result2.savingsPercentage.toFixed(1)}%`);
  }

  console.log();
  console.log('Code:');
  console.log('-'.repeat(80));
  console.log(result2.content.substring(0, 500));
  if (result2.content.length > 500) console.log('...');
  console.log('-'.repeat(80));
  console.log();

  // ========================================================================
  // Test 3: Complex Query (May need premium tier)
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🧪 TEST 3: Complex Architecture Question');
  console.log('='.repeat(80));
  console.log();

  console.log('Query: "Design a rate limiter with distributed state"\n');

  const start3 = Date.now();
  const result3 = await agent.run(
    'Design a distributed rate limiter for a microservices architecture. ' +
    'Include algorithms, data structures, and scaling considerations. Be concise.'
  );
  const elapsed3 = Date.now() - start3;

  console.log('📊 Result:');
  console.log(`   Model used: ${result3.modelUsed}`);
  console.log(`   Response length: ${result3.content.length} chars`);
  console.log(`   Cost: ${result3.totalCost === 0 ? 'FREE! 🎉' : `$${result3.totalCost.toFixed(6)}`}`);
  console.log(`   Latency: ${elapsed3}ms`);
  console.log(`   Cascaded: ${result3.cascaded ? 'Yes' : 'No'}`);

  if (result3.savingsPercentage !== undefined) {
    console.log(`   Savings: ${result3.savingsPercentage.toFixed(1)}%`);
  }

  console.log();
  console.log('Design:');
  console.log('-'.repeat(80));
  console.log(result3.content.substring(0, 400));
  if (result3.content.length > 400) console.log('...');
  console.log('-'.repeat(80));
  console.log();

  // ========================================================================
  // Summary & Cost Analysis
  // ========================================================================

  const totalCost = result1.totalCost + result2.totalCost + result3.totalCost;
  const totalTime = elapsed1 + elapsed2 + elapsed3;

  // Calculate what it would cost if we used Claude for everything
  const claudeOnlyCost = 0.003; // Base cost estimate
  const potentialClaudeCost = claudeOnlyCost * 3; // 3 queries

  const actualSavings = totalCost === 0 ? 100 : ((potentialClaudeCost - totalCost) / potentialClaudeCost) * 100;

  console.log('='.repeat(80));
  console.log('📊 SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();

  console.log('🎯 Model Usage:');
  const grokCount = [result1, result2, result3].filter(r => r.modelUsed.includes('grok')).length;
  const claudeCount = [result1, result2, result3].filter(r => r.modelUsed.includes('claude')).length;
  console.log(`   Grok (FREE): ${grokCount}/3 queries (${(grokCount/3*100).toFixed(0)}%)`);
  console.log(`   Claude (Premium): ${claudeCount}/3 queries (${(claudeCount/3*100).toFixed(0)}%)`);
  console.log();

  console.log('💰 Cost Analysis:');
  console.log(`   Actual total cost: ${totalCost === 0 ? 'FREE!' : `$${totalCost.toFixed(6)}`}`);
  console.log(`   If Claude-only: ~$${potentialClaudeCost.toFixed(6)}`);
  console.log(`   Savings: ${actualSavings.toFixed(1)}% 🎉`);
  console.log();

  console.log('⚡ Performance:');
  console.log(`   Total time: ${totalTime}ms`);
  console.log(`   Avg per query: ${(totalTime/3).toFixed(0)}ms`);
  console.log();

  console.log('='.repeat(80));
  console.log('💡 KEY INSIGHTS');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ Cascade Effectiveness:');
  console.log('   • Simple queries → FREE tier (Grok)');
  console.log('   • Complex queries → Premium tier (Claude)');
  console.log('   • Automatic quality detection');
  console.log('   • Massive cost savings (50-80% typical)');
  console.log();
  console.log('🎯 Best Practices:');
  console.log('   1. Set quality threshold based on your needs (0.6-0.8)');
  console.log('   2. Start with free models, escalate as needed');
  console.log('   3. Monitor which tier is used most');
  console.log('   4. Adjust thresholds to optimize cost/quality');
  console.log();
  console.log('💰 Cost Optimization:');
  console.log('   • Grok handles ~70% of typical queries (FREE)');
  console.log('   • Claude handles remaining 30% (premium quality)');
  console.log('   • Result: 70%+ cost reduction with minimal quality loss');
  console.log();
  console.log('🚀 Try This:');
  console.log('   • Experiment with different quality thresholds');
  console.log('   • Add more tiers (DeepSeek, Gemini Flash)');
  console.log('   • Monitor savings over time');
  console.log('   • Use streaming for better UX');
  console.log();
}

main().catch(console.error);
