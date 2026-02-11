/**
 * Tool Risk Gating Example (CascadeFlow + LangChain tools)
 *
 * Demonstrates:
 * - Tool calls can be accepted even with empty content
 * - HIGH/CRITICAL risk tool calls force verifier before returning a tool call
 *
 * Setup:
 *   export OPENAI_API_KEY="sk-..."
 *   pnpm -C packages/langchain-cascadeflow install
 *   npx tsx packages/langchain-cascadeflow/examples/tool-risk-gating.ts
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  if (!process.env.OPENAI_API_KEY) {
    console.log("Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'");
    process.exit(1);
  }

  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0.0 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0.0 });

  const cascade = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.95,
    // Use local pricing so we can show savings/costs without requiring LangSmith UI.
    costTrackingProvider: 'cascadeflow',
  });

  const tools = [
    {
      type: 'function',
      function: {
        name: 'get_weather',
        description: 'Read-only: get the current weather for a location.',
        parameters: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
        },
      },
    },
    {
      type: 'function',
      function: {
        name: 'delete_user',
        description: 'HIGH RISK: permanently deletes a user account (irreversible).',
        parameters: {
          type: 'object',
          properties: { user_id: { type: 'string' } },
          required: ['user_id'],
        },
      },
    },
  ];

  const toolCascade = (cascade as any).bindTools(tools);

  const lowRisk = await toolCascade.invoke(
    'Call the get_weather tool with location="Berlin". Return only the tool call.',
    { tags: ['example', 'tools', 'low-risk'] }
  );
  console.log('Low-risk tool_calls:', (lowRisk as any).tool_calls || (lowRisk as any).additional_kwargs?.tool_calls);
  console.log('Cascade metadata:', (lowRisk as any).response_metadata?.cascade);

  const highRisk = await toolCascade.invoke(
    'Call the delete_user tool with user_id="123". Return only the tool call.',
    { tags: ['example', 'tools', 'high-risk'] }
  );
  console.log('High-risk tool_calls:', (highRisk as any).tool_calls || (highRisk as any).additional_kwargs?.tool_calls);
  console.log('Cascade metadata:', (highRisk as any).response_metadata?.cascade);

  console.log('Last cascade stats:', toolCascade.getLastCascadeResult());
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
