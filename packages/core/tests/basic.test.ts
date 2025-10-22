/**
 * Basic integration test for CascadeFlow TypeScript library
 *
 * This test validates:
 * - Package imports work correctly
 * - OpenAI provider initializes
 * - Cascade logic executes
 * - Real API calls work
 * - Cost tracking functions
 */

import { CascadeAgent } from '../src';

async function testBasicCascade() {
  console.log('🧪 Testing CascadeFlow TypeScript Library\n');

  // Check for API key
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('❌ OPENAI_API_KEY not found in environment');
    console.log('💡 Set it in .env file or export it:');
    console.log('   export OPENAI_API_KEY=sk-...\n');
    process.exit(1);
  }

  console.log('✅ OpenAI API key found');
  console.log(`   Key: ${apiKey.substring(0, 10)}...${apiKey.substring(apiKey.length - 4)}\n`);

  // Create agent with two-tier cascade
  console.log('📦 Creating CascadeAgent...');
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
        apiKey,
      },
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.00625,
        apiKey,
      },
    ],
  });

  console.log(`✅ Agent created with ${agent.getModelCount()} models`);
  console.log(`   Models: ${agent.getModels().map(m => m.name).join(' → ')}\n`);

  // Test 1: Simple query (should use draft model)
  console.log('🔍 Test 1: Simple query (expect draft model)');
  console.log('   Query: "What is TypeScript?"\n');

  const startTime = Date.now();
  const result1 = await agent.run('What is TypeScript?');
  const elapsed = Date.now() - startTime;

  console.log('📊 Result:');
  console.log(`   Model used: ${result1.modelUsed}`);
  console.log(`   Response: ${result1.content.substring(0, 100)}...`);
  console.log(`   Cost: $${result1.totalCost.toFixed(6)}`);
  console.log(`   Latency: ${elapsed}ms`);
  console.log(`   Cascaded: ${result1.cascaded ? 'Yes' : 'No'}`);
  console.log(`   Draft accepted: ${result1.draftAccepted ? 'Yes' : 'No'}`);

  if (result1.savingsPercentage !== undefined) {
    console.log(`   Savings: ${result1.savingsPercentage.toFixed(1)}%`);
  }

  console.log('');

  // Validate result
  if (!result1.content) {
    throw new Error('No content in response');
  }

  if (result1.totalCost <= 0) {
    throw new Error('Cost should be greater than 0');
  }

  console.log('✅ Test 1 passed!\n');

  // Summary
  console.log('═══════════════════════════════════════════');
  console.log('🎉 All tests passed!');
  console.log('═══════════════════════════════════════════');
  console.log(`Total cost: $${result1.totalCost.toFixed(6)}`);
  console.log(`Total time: ${elapsed}ms`);
  console.log('');
}

// Run tests
testBasicCascade()
  .then(() => {
    console.log('✅ Test suite completed successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n❌ Test failed:', error);
    process.exit(1);
  });
