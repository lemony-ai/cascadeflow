/**
 * cascadeflow - OpenRouter Example (TypeScript/Node.js)
 *
 * Demonstrates using OpenRouter as a unified gateway to 400+ models.
 *
 * This example shows:
 * - Single API key for multiple providers (OpenAI, Anthropic, Google, X.AI, etc.)
 * - Access to top-performing models from OpenRouter's 2025 rankings
 * - Cost optimization with free and paid models
 * - Model naming in provider/model format
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenRouter API key (get from https://openrouter.ai/keys)
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENROUTER_API_KEY="your-openrouter-key"
 *   npx tsx openrouter-example.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('🌐 CASCADEFLOW - OPENROUTER INTEGRATION EXAMPLE');
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

  // ========================================================================
  // STEP 1: Configure OpenRouter Cascade with Top Models
  // ========================================================================

  console.log('📋 Step 1: Configuring OpenRouter cascade with top 2025 models...\n');

  // Models ranked by 2025 usage and performance data
  // Source: https://openrouter.ai/rankings
  const models: ModelConfig[] = [
    // Tier 1: Free models for simple queries
    {
      name: 'deepseek/deepseek-chat',
      provider: 'openrouter',
      cost: 0, // FREE
      qualityThreshold: 0.6,
      apiKey: process.env.OPENROUTER_API_KEY,
    },
    {
      name: 'mistralai/devstral-small',
      provider: 'openrouter',
      cost: 0, // FREE
      qualityThreshold: 0.65,
      apiKey: process.env.OPENROUTER_API_KEY,
    },

    // Tier 2: Budget models for common tasks
    {
      name: 'meta-llama/llama-3.1-8b-instruct',
      provider: 'openrouter',
      cost: 0.00005, // $0.05 per 1M tokens
      qualityThreshold: 0.7,
      apiKey: process.env.OPENROUTER_API_KEY,
    },
    {
      name: 'google/gemini-2.5-flash',
      provider: 'openrouter',
      cost: 0.00015, // $0.15 per 1M tokens (1M context window!)
      qualityThreshold: 0.75,
      apiKey: process.env.OPENROUTER_API_KEY,
    },

    // Tier 3: Mid-range powerhouse
    {
      name: 'deepseek/deepseek-coder-v2',
      provider: 'openrouter',
      cost: 0.00027, // $0.27 per 1M tokens - "Nearly as good as premium"
      qualityThreshold: 0.8,
      apiKey: process.env.OPENROUTER_API_KEY,
    },

    // Tier 4: Premium models for complex tasks
    {
      name: 'openai/gpt-4o',
      provider: 'openrouter',
      cost: 0.0025, // $2.50 per 1M tokens
      qualityThreshold: 0.85,
      apiKey: process.env.OPENROUTER_API_KEY,
    },
    {
      name: 'anthropic/claude-4.5-sonnet-20250929',
      provider: 'openrouter',
      cost: 0.003, // $3 per 1M tokens (15.0% of traffic)
      qualityThreshold: 0.9,
      apiKey: process.env.OPENROUTER_API_KEY,
    },

    // Tier 5: Top performer for code and reasoning
    {
      name: 'anthropic/claude-opus-4',
      provider: 'openrouter',
      cost: 0.015, // $15 per 1M tokens - "World's best coding model"
      qualityThreshold: 0.95,
      apiKey: process.env.OPENROUTER_API_KEY,
    },
  ];

  const agent = new CascadeAgent({ models });

  console.log(`   ✅ Configured ${models.length}-tier cascade using OpenRouter:`);
  models.forEach((m, i) => {
    const costStr = m.cost === 0 ? 'FREE' : `$${m.cost}/1K tokens`;
    const provider = m.name.split('/')[0];
    console.log(`      Tier ${i + 1}: ${m.name.split('/')[1]} (${provider}) - ${costStr}`);
  });
  console.log();

  // ========================================================================
  // STEP 2: Test with Various Query Types
  // ========================================================================

  console.log('📝 Step 2: Testing OpenRouter with different query types...\n');

  const queries = [
    {
      question: 'What is 2+2?',
      description: 'Simple math (should use free tier)',
    },
    {
      question: 'Explain quantum entanglement in simple terms',
      description: 'Moderate complexity',
    },
    {
      question: 'Write a TypeScript function to implement a LRU cache with O(1) operations',
      description: 'Complex coding task',
    },
  ];

  for (let i = 0; i < queries.length; i++) {
    const { question, description } = queries[i];

    console.log('-'.repeat(80));
    console.log(`❓ Query ${i + 1}: ${description}`);
    console.log(`   "${question}"`);
    console.log();

    const result = await agent.run(question);

    const modelParts = result.modelUsed.split('/');
    const provider = modelParts[0] || 'unknown';
    const modelName = modelParts[1] || result.modelUsed;

    console.log('✅ Result:');
    console.log(`   🤖 Model: ${modelName}`);
    console.log(`   🏢 Provider: ${provider}`);
    console.log(`   💰 Cost: ${result.totalCost === 0 ? 'FREE' : `$${result.totalCost.toFixed(6)}`}`);
    console.log(`   💾 Tokens: ${result.promptTokens + result.completionTokens} (${result.promptTokens} in / ${result.completionTokens} out)`);
    console.log(`   ⚡ Latency: ${result.latencyMs}ms`);
    console.log(`   📝 Response (first 150 chars): ${result.content.substring(0, 150).replace(/\n/g, ' ')}...`);
    console.log();
  }

  // ========================================================================
  // STEP 3: Show Cost Comparison
  // ========================================================================

  console.log('='.repeat(80));
  console.log('💰 COST COMPARISON: OpenRouter vs Direct Providers');
  console.log('='.repeat(80));
  console.log();
  console.log('OpenRouter Benefits:');
  console.log('   ✅ One API key → 400+ models (no managing multiple keys)');
  console.log('   ✅ Free models available (DeepSeek, Mistral, etc.)');
  console.log('   ✅ Access premium models (Claude Opus 4, GPT-4o) without separate accounts');
  console.log('   ✅ Automatic fallbacks if a model is unavailable');
  console.log('   ✅ Pass-through pricing (no markup on model costs)');
  console.log('   ✅ Mix providers effortlessly for cost optimization');
  console.log();

  // ========================================================================
  // STEP 4: Available Models Info
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🌟 TOP OPENROUTER MODELS (2025)');
  console.log('='.repeat(80));
  console.log();

  const topModels = [
    {
      name: 'x-ai/grok-code-fast-1',
      traffic: '53.1%',
      cost: 'Free tier',
      note: 'Most popular by volume',
    },
    {
      name: 'anthropic/claude-opus-4',
      traffic: '—',
      cost: '$15/$75 per 1M',
      note: 'Best for coding',
    },
    {
      name: 'anthropic/claude-4.5-sonnet',
      traffic: '15.0%',
      cost: '$3/$15 per 1M',
      note: 'Balanced performance',
    },
    {
      name: 'google/gemini-2.5-flash',
      traffic: '—',
      cost: '$0.15/$0.60 per 1M',
      note: '1M context window',
    },
    {
      name: 'minimax/minimax-m2',
      traffic: '11.0%',
      cost: '$0.10/$0.10 per 1M',
      note: 'Value option',
    },
  ];

  console.log('Model                          Traffic   Cost              Notes');
  console.log('-'.repeat(80));
  topModels.forEach((model) => {
    const nameCol = model.name.padEnd(30);
    const trafficCol = model.traffic.padEnd(10);
    const costCol = model.cost.padEnd(18);
    console.log(`${nameCol}${trafficCol}${costCol}${model.note}`);
  });
  console.log();

  console.log('Browse all 400+ models: https://openrouter.ai/models');
  console.log();

  // ========================================================================
  // KEY TAKEAWAYS
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ What You Learned:');
  console.log('   1. OpenRouter provides unified access to 400+ models with one API key');
  console.log('   2. Model naming uses provider/model-name format (e.g., openai/gpt-4o)');
  console.log('   3. Mix free and paid models for optimal cost/quality tradeoff');
  console.log('   4. Access latest models (Claude 4, Gemini 2.5) without separate accounts');
  console.log('   5. CascadeFlow automatically routes to best model based on confidence');
  console.log();
  console.log('📚 Next Steps:');
  console.log('   - Try different models: https://openrouter.ai/models');
  console.log('   - Check rankings: https://openrouter.ai/rankings');
  console.log('   - Read docs: https://openrouter.ai/docs');
  console.log();
}

main().catch(console.error);
