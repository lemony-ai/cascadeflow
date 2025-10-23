/**
 * CascadeFlow - Tool Calling Example (TypeScript/Node.js)
 *
 * Demonstrates how to use function/tool calling with CascadeFlow.
 *
 * This example shows:
 * - Defining tools with TypeScript types
 * - Passing tools to the cascade agent
 * - How CascadeFlow handles tool calls across tiers
 * - Type-safe tool definitions
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
 *   npx tsx tool-calling.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('🔧 CASCADEFLOW - TOOL CALLING EXAMPLE (TypeScript)');
  console.log('='.repeat(80));
  console.log();

  if (!process.env.OPENAI_API_KEY) {
    console.error('❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY="sk-..."');
    process.exit(1);
  }

  // ========================================================================
  // STEP 1: Define Tools
  // ========================================================================

  console.log('🔧 Step 1: Defining tools...\n');

  const tools = [
    {
      name: 'get_weather',
      description: 'Get the current weather for a location',
      parameters: {
        type: 'object',
        properties: {
          location: {
            type: 'string',
            description: 'City name, e.g., "San Francisco"',
          },
          unit: {
            type: 'string',
            enum: ['celsius', 'fahrenheit'],
            description: 'Temperature unit',
          },
        },
        required: ['location'],
      },
    },
    {
      name: 'calculate',
      description: 'Perform a mathematical calculation',
      parameters: {
        type: 'object',
        properties: {
          expression: {
            type: 'string',
            description: 'Mathematical expression to evaluate, e.g., "2 + 2"',
          },
        },
        required: ['expression'],
      },
    },
  ];

  console.log('   ✅ Defined 2 tools: get_weather, calculate');
  console.log();

  // ========================================================================
  // STEP 2: Configure Cascade with Tools
  // ========================================================================

  console.log('📋 Step 2: Configuring cascade with tools support...\n');

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

  console.log('   ✅ Cascade configured with tool calling enabled');
  console.log();

  // ========================================================================
  // STEP 3: Test Tool Calling
  // ========================================================================

  console.log('📝 Step 3: Testing queries that require tools...\n');

  const queries = [
    "What's the weather in San Francisco?",
    'Calculate 42 * 1337',
    "What's the weather in London and Paris?",
  ];

  for (const query of queries) {
    console.log('-'.repeat(80));
    console.log(`❓ Question: ${query}`);
    console.log();

    const result = await agent.run(query, { tools });

    console.log('✅ Result:');
    console.log(`   🤖 Model: ${result.modelUsed}`);
    console.log(`   💰 Cost: $${result.totalCost.toFixed(6)}`);

    if (result.toolCalls && result.toolCalls.length > 0) {
      console.log(`   🔧 Tool Calls: ${result.toolCalls.length}`);
      result.toolCalls.forEach((call, i) => {
        console.log(`      ${i + 1}. ${call.name}(${JSON.stringify(call.arguments)})`);
      });
    } else {
      console.log('   🔧 Tool Calls: None (answered directly)');
    }

    console.log(`   📝 Response: ${result.content.substring(0, 100)}...`);
    console.log();
  }

  console.log('='.repeat(80));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ What You Learned:');
  console.log('   1. How to define tools with TypeScript types');
  console.log('   2. How to pass tools to CascadeFlow');
  console.log('   3. Tool calls are automatically handled across cascade tiers');
  console.log('   4. Full type safety for tool definitions');
  console.log();
}

main().catch(console.error);
