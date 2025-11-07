/**
 * cascadeflow - Multi-Provider Example (TypeScript/Node.js)
 *
 * Demonstrates using multiple AI providers in a cascade.
 *
 * This example shows:
 * - Mixing different providers (OpenAI, Anthropic, Groq)
 * - Provider-specific configurations
 * - Cross-provider cascading
 * - Cost optimization across providers
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - openai, @anthropic-ai/sdk, groq-sdk (peer dependencies)
 *   - API keys for each provider
 *
 * Setup:
 *   npm install @cascadeflow/core openai @anthropic-ai/sdk groq-sdk
 *   export OPENAI_API_KEY="your-key"
 *   export ANTHROPIC_API_KEY="your-key"
 *   export GROQ_API_KEY="your-key"
 *   npx tsx multi-provider.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('🌐 CASCADEFLOW - MULTI-PROVIDER EXAMPLE (TypeScript)');
  console.log('='.repeat(80));
  console.log();

  // Check for API keys
  const providers: { name: string; key: string }[] = [
    { name: 'OpenAI', key: 'OPENAI_API_KEY' },
    { name: 'Anthropic', key: 'ANTHROPIC_API_KEY' },
    { name: 'Groq', key: 'GROQ_API_KEY' },
  ];

  const available: string[] = [];
  const missing: string[] = [];

  for (const provider of providers) {
    if (process.env[provider.key]) {
      available.push(provider.name);
    } else {
      missing.push(provider.name);
    }
  }

  console.log('🔑 API Keys Status:');
  available.forEach((p) => console.log(`   ✅ ${p}`));
  missing.forEach((p) => console.log(`   ⏭️  ${p} (skipped - no API key)`));
  console.log();

  if (available.length === 0) {
    console.error('❌ At least one API key is required');
    process.exit(1);
  }

  // ========================================================================
  // STEP 1: Configure Multi-Provider Cascade
  // ========================================================================

  console.log('📋 Step 1: Configuring multi-provider cascade...\n');

  const models: ModelConfig[] = [];

  // Groq: Ultra-fast, free tier available
  if (process.env.GROQ_API_KEY) {
    models.push({
      name: 'llama-3.1-8b-instant',
      provider: 'groq',
      cost: 0.00005, // Very cheap
      apiKey: process.env.GROQ_API_KEY,
    });
  }

  // OpenAI: Cheap model
  if (process.env.OPENAI_API_KEY) {
    models.push({
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey: process.env.OPENAI_API_KEY,
    });
  }

  // Anthropic: Mid-tier
  if (process.env.ANTHROPIC_API_KEY) {
    models.push({
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001,
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  }

  // OpenAI: Premium model
  if (process.env.OPENAI_API_KEY) {
    models.push({
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      apiKey: process.env.OPENAI_API_KEY,
    });
  }

  const agent = new CascadeAgent({
    models,
    quality: {
      // Complexity-aware thresholds work across all providers
      confidenceThresholds: {
        simple: 0.5,      // Simple queries stay on cheap providers (Groq, mini)
        moderate: 0.65,   // Moderate queries may escalate to mid-tier
        hard: 0.75,    // Complex queries more likely to use premium
        expert: 0.85      // Expert queries escalate to best available model
      },
      requireMinimumTokens: 10,
    },
  });

  console.log(`   ✅ Configured ${models.length}-tier cascade:`);
  models.forEach((m, i) => {
    console.log(`      Tier ${i + 1}: ${m.name} (${m.provider}) - $${m.cost}/1K tokens`);
  });
  console.log();
  console.log('   🎯 Quality Strategy:');
  console.log('      - Complexity-aware routing across all providers');
  console.log('      - Simple queries stay on cheapest tier');
  console.log('      - Complex queries automatically escalate');
  console.log();

  // ========================================================================
  // STEP 2: Test Queries
  // ========================================================================

  console.log('📝 Step 2: Testing cross-provider routing...\n');

  const queries = [
    'What is the capital of France?',
    'Explain quantum computing in simple terms',
  ];

  for (const query of queries) {
    console.log('-'.repeat(80));
    console.log(`❓ Question: ${query}`);
    console.log();

    const result = await agent.run(query);

    console.log('✅ Result:');
    console.log(`   🤖 Model: ${result.modelUsed}`);
    console.log(`   🏢 Provider: ${models.find((m) => m.name === result.modelUsed)?.provider || 'unknown'}`);
    console.log(`   💰 Cost: $${result.totalCost.toFixed(6)}`);
    console.log(`   ⚡ Latency: ${result.latencyMs}ms`);
    console.log(`   📝 Response: ${result.content.substring(0, 100)}...`);
    console.log();
  }

  console.log('='.repeat(80));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ What You Learned:');
  console.log('   1. cascadeflow works seamlessly across providers');
  console.log('   2. You can mix OpenAI, Anthropic, Groq, and more');
  console.log('   3. Each provider has its own cost and quality profile');
  console.log('   4. TypeScript provides full type safety across all providers');
  console.log();
}

main().catch(console.error);
