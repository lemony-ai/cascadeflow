/**
 * cascadeflow - Basic Usage Example (TypeScript/Node.js)
 *
 * The simplest way to get started with cascadeflow in TypeScript.
 * This example demonstrates:
 * - Setting up a two-tier cascade (cheap → expensive)
 * - Processing queries with automatic quality-based routing
 * - Cost tracking and savings calculation
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - openai (peer dependency)
 *   - OpenAI API key
 *
 * Setup:
 *   npm install @cascadeflow/core openai
 *   export OPENAI_API_KEY="your-key-here"
 *   npx tsx basic-usage.ts
 *
 * What You'll Learn:
 *   1. How to configure a basic cascade
 *   2. How cascadeflow automatically routes queries
 *   3. How to track costs and savings
 *   4. TypeScript types for full IDE support
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('🌊 CASCADEFLOW - BASIC USAGE EXAMPLE (TypeScript)');
  console.log('='.repeat(80));
  console.log();

  // Check for API key
  if (!process.env.OPENAI_API_KEY) {
    console.error('❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY="sk-..."');
    process.exit(1);
  }

  // ========================================================================
  // STEP 1: Configure Your Cascade
  // ========================================================================

  console.log('📋 Step 1: Configuring cascade with two models...');
  console.log();

  const models: ModelConfig[] = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      qualityThreshold: 0.7,
      apiKey: process.env.OPENAI_API_KEY,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      qualityThreshold: 0.95,
      apiKey: process.env.OPENAI_API_KEY,
    },
  ];

  const agent = new CascadeAgent({ models });

  console.log('   ✅ Tier 1: gpt-4o-mini ($0.00015/1K tokens)');
  console.log('   ✅ Tier 2: gpt-4o ($0.00625/1K tokens)');
  console.log();

  // ========================================================================
  // STEP 2: Test with Different Query Types
  // ========================================================================

  console.log('📝 Step 2: Testing with various query types...\n');

  const queries = [
    'What is TypeScript?',
    'Explain the difference between type and interface in TypeScript',
    'Design a scalable architecture for a real-time collaborative editing system',
  ];

  let totalCost = 0;

  for (const query of queries) {
    console.log('-'.repeat(80));
    console.log(`❓ Question: ${query}`);
    console.log();

    const result = await agent.run(query);

    const icon = result.modelUsed.includes('mini') ? '💚' : '💛';

    console.log('✅ Result:');
    console.log(`   ${icon} Model: ${result.modelUsed}`);
    console.log(`   💰 Cost: $${result.totalCost.toFixed(6)}`);
    console.log(`   ⚡ Latency: ${result.latencyMs}ms`);

    if (result.cascaded) {
      if (result.draftAccepted) {
        console.log('   ✅ Draft accepted - verifier skipped!');
      } else {
        console.log('   ❌ Draft rejected - escalated to expensive model');
      }
    }

    console.log(`   📝 Response: ${result.content.substring(0, 100)}...`);
    console.log();

    totalCost += result.totalCost;
  }

  // ========================================================================
  // STEP 3: Show Savings
  // ========================================================================

  console.log('='.repeat(80));
  console.log('💰 COST ANALYSIS');
  console.log('='.repeat(80));
  console.log();
  console.log(`Total Cost: $${totalCost.toFixed(6)}`);
  console.log();
  console.log('🎉 cascadeflow automatically optimized your costs!');
  console.log();
}

main().catch(console.error);
