/**
 * LangSmith Tracing Example
 *
 * Demonstrates how CascadeFlow cost metadata appears in LangSmith traces
 * for observability and cost tracking.
 *
 * Prerequisites:
 * 1. Set OPENAI_API_KEY environment variable
 * 2. Set LANGSMITH_API_KEY environment variable
 * 3. Optionally set LANGSMITH_PROJECT (defaults to "default")
 *
 * Run:
 * OPENAI_API_KEY=xxx LANGSMITH_API_KEY=xxx npx tsx examples/langsmith-tracing.ts
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  console.log('=== CascadeFlow LangSmith Integration Demo ===\n');

  // Check for required API keys
  if (!process.env.OPENAI_API_KEY) {
    console.error('❌ OPENAI_API_KEY environment variable is required');
    process.exit(1);
  }

  if (!process.env.LANGSMITH_API_KEY) {
    console.warn('⚠️  LANGSMITH_API_KEY not set - tracing will be disabled');
    console.warn('   Set it to see cascade metadata in LangSmith!\n');
  } else {
    const project = process.env.LANGSMITH_PROJECT || 'default';
    console.log(`✅ LangSmith tracing enabled`);
    console.log(`   Project: ${project}`);
    console.log(`   View traces at: https://smith.langchain.com/\n`);
  }

  // Configure models
  const drafter = new ChatOpenAI({
    model: 'gpt-4o-mini',
    temperature: 0.7,
  });

  const verifier = new ChatOpenAI({
    model: 'gpt-4o',
    temperature: 0.7,
  });

  // Create cascade model with cost tracking enabled (default)
  const cascadeModel = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true, // This enables LangSmith metadata injection
  });

  console.log('Running test queries...\n');

  // Test 1: Simple query (likely to accept drafter)
  console.log('--- Test 1: Simple Query (High Quality) ---');
  const result1 = await cascadeModel.invoke('What is 2+2?');
  console.log(`Answer: ${result1.content}`);

  const stats1 = cascadeModel.getLastCascadeResult();
  if (stats1) {
    console.log(`Model used: ${stats1.modelUsed}`);
    console.log(`Quality score: ${stats1.drafterQuality?.toFixed(2)}`);
    console.log(`Total cost: $${stats1.totalCost.toFixed(6)}`);
    console.log(`Savings: ${stats1.savingsPercentage.toFixed(1)}%`);
  }
  console.log();

  // Test 2: Complex query (might cascade to verifier)
  console.log('--- Test 2: Complex Query (May Cascade) ---');
  const result2 = await cascadeModel.invoke(
    'Explain the key differences between TypeScript and JavaScript, focusing on type safety and development workflow.'
  );
  console.log(`Answer: ${result2.content.slice(0, 200)}...`);

  const stats2 = cascadeModel.getLastCascadeResult();
  if (stats2) {
    console.log(`Model used: ${stats2.modelUsed}`);
    console.log(`Quality score: ${stats2.drafterQuality?.toFixed(2)}`);
    console.log(`Total cost: $${stats2.totalCost.toFixed(6)}`);
    console.log(`Savings: ${stats2.savingsPercentage.toFixed(1)}%`);
  }
  console.log();

  // Test 3: Using with custom metadata and tags
  console.log('--- Test 3: With Custom LangSmith Tags ---');
  const result3 = await cascadeModel.invoke(
    'What are the benefits of using a cascade pattern for LLM cost optimization?',
    {
      tags: ['cascade-demo', 'cost-optimization'],
      metadata: {
        user_id: 'demo-user-123',
        session_id: 'demo-session-456',
        feature: 'cost-optimization-demo',
      },
    }
  );
  console.log(`Answer: ${result3.content.slice(0, 200)}...`);

  const stats3 = cascadeModel.getLastCascadeResult();
  if (stats3) {
    console.log(`Model used: ${stats3.modelUsed}`);
    console.log(`Quality score: ${stats3.drafterQuality?.toFixed(2)}`);
    console.log(`Total cost: $${stats3.totalCost.toFixed(6)}`);
    console.log(`Savings: ${stats3.savingsPercentage.toFixed(1)}%`);
  }
  console.log();

  // Test 4: Chain example with bind()
  console.log('--- Test 4: Chained with bind() ---');
  const boundModel = cascadeModel.bind({ temperature: 0.1 });
  const result4 = await boundModel.invoke('What is the capital of France?');
  console.log(`Answer: ${result4.content}`);

  const stats4 = cascadeModel.getLastCascadeResult();
  if (stats4) {
    console.log(`Model used: ${stats4.modelUsed}`);
    console.log(`Quality score: ${stats4.drafterQuality?.toFixed(2)}`);
    console.log(`Total cost: $${stats4.totalCost.toFixed(6)}`);
    console.log(`Savings: ${stats4.savingsPercentage.toFixed(1)}%`);
  }
  console.log();

  console.log('=== Demo Complete ===');
  if (process.env.LANGSMITH_API_KEY) {
    console.log('\n📊 Check LangSmith to see cascade metadata in traces:');
    console.log('   - drafterTokens: Input/output token counts from drafter');
    console.log('   - verifierTokens: Input/output token counts from verifier (if cascaded)');
    console.log('   - drafterCost: Cost of drafter call');
    console.log('   - verifierCost: Cost of verifier call');
    console.log('   - totalCost: Combined cost');
    console.log('   - savingsPercentage: Cost savings vs using verifier only');
    console.log('   - modelUsed: Which model provided the final response');
    console.log('   - accepted: Whether drafter response was accepted');
    console.log('   - drafterQuality: Quality score (0-1)');
  }
}

main().catch(console.error);
