/**
 * Example: Router Integration
 *
 * Demonstrates the integrated routing system:
 * - PreRouter: Complexity-based routing decisions
 * - ToolRouter: Automatic tool capability filtering
 * - Router statistics and monitoring
 *
 * Run: npx tsx examples/nodejs/router-integration.ts
 */

import { CascadeAgent, createTool } from '@cascadeflow/core';
import { safeCalculateExpression } from './safe-math';

async function main() {
  console.log('🔀 Router Integration Example\n');

  const models = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai' as const,
      cost: 0.00015,
      supportsTools: true,
    },
    {
      name: 'gpt-4o',
      provider: 'openai' as const,
      cost: 0.00625,
      supportsTools: true,
    },
    {
      name: 'claude-3-5-haiku-20241022',
      provider: 'anthropic' as const,
      cost: 0.0008,
      supportsTools: false, // This model doesn't support tools
    },
  ];

  const agent = new CascadeAgent({
    models,
  });

  // ============================================================================
  // 1. PreRouter: Complexity-Based Routing
  // ============================================================================
  console.log('1️⃣  PreRouter: Complexity-Based Routing\n');

  console.log('Simple query (should cascade):');
  const simpleResult = await agent.run('What is 2 + 2?');
  console.log(`   Model: ${simpleResult.modelUsed}`);
  console.log(`   Draft accepted: ${simpleResult.draftAccepted}`);

  console.log('\nComplex query (might route direct):');
  const complexResult = await agent.run(
    'Explain the theoretical foundations of quantum computing including superposition, entanglement, and quantum gates, with references to recent research.'
  );
  console.log(`   Model: ${complexResult.modelUsed}`);
  console.log(`   Draft accepted: ${complexResult.draftAccepted}`);

  // ============================================================================
  // 2. ToolRouter: Automatic Tool Filtering
  // ============================================================================
  console.log('\n2️⃣  ToolRouter: Automatic Tool Filtering\n');

  const calculatorTool = createTool({
    name: 'calculator',
    description: 'Perform mathematical calculations',
    parameters: {
      type: 'object',
      properties: {
        expression: {
          type: 'string',
          description: 'Mathematical expression to evaluate',
        },
      },
      required: ['expression'],
    },
    function: async ({ expression }: { expression: string }) => {
      try {
        const result = safeCalculateExpression(expression);
        return `Result: ${result}`;
      } catch (error) {
        return `Error: ${error instanceof Error ? error.message : 'Calculation failed'}`;
      }
    },
  });

  console.log('Query with tools (auto-filters to tool-capable models):');
  const toolResult = await agent.run('Calculate 125 * 47', {
    tools: [calculatorTool.toOpenAIFormat()],
  });
  console.log(`   Model: ${toolResult.modelUsed}`);
  console.log(`   Supports tools: ${models.find((m) => m.name === toolResult.modelUsed)?.supportsTools}`);
  console.log(`   Note: claude-3-5-haiku was automatically excluded`);

  // ============================================================================
  // 3. Router Statistics
  // ============================================================================
  console.log('\n3️⃣  Router Statistics\n');

  const stats = agent.getRouterStats();

  console.log('PreRouter stats:');
  console.log(JSON.stringify(stats.preRouter, null, 2));

  console.log('\nToolRouter stats:');
  console.log(JSON.stringify(stats.toolRouter, null, 2));

  // ============================================================================
  // 4. Force Direct Routing
  // ============================================================================
  console.log('\n4️⃣  Force Direct Routing\n');

  console.log('Bypassing cascade with forceDirect:');
  const directResult = await agent.run('What is TypeScript?', {
    forceDirect: true,
  });
  console.log(`   Model: ${directResult.modelUsed}`);
  console.log(`   Draft accepted: ${directResult.draftAccepted}`);
  console.log(`   Note: Went straight to best model`);

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
