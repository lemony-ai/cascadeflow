/**
 * LangGraph Multi-Agent Example (CascadeFlow + closed tool loops)
 *
 * Demonstrates (conceptually):
 * - A small multi-agent graph where sub-agents can call tools
 * - CascadeFlow high-risk tool policy (high-risk tool calls force verifier)
 * - Tool-safe streaming behavior when tools are bound
 *
 * Notes:
 * - This example depends on optional LangGraph packages. If you don't use LangGraph,
 *   skip this file. It is not required for @cascadeflow/langchain itself.
 *
 * Setup:
 *   export OPENAI_API_KEY="sk-..."
 *   pnpm -C packages/langchain-cascadeflow install
 *   npm i @langchain/langgraph
 *   npx tsx packages/langchain-cascadeflow/examples/langgraph-multi-agent.ts
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

// Import lazily so the package remains optional.
async function importLangGraph() {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return await import('@langchain/langgraph');
}

async function main() {
  if (!process.env.OPENAI_API_KEY) {
    console.log("Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'");
    process.exit(1);
  }

  const { StateGraph, END } = await importLangGraph();

  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0.2 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0.2 });

  // Shared cascade model; each agent can reuse it.
  const baseCascade = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    costTrackingProvider: 'langsmith',
  });

  // Example tools.
  // Keep descriptions accurate: tool risk classification uses name + description.
  const tools = [
    {
      name: 'get_weather',
      description: 'Read-only: get the current weather for a location.',
      parameters: {
        type: 'object',
        properties: { location: { type: 'string' } },
        required: ['location'],
      },
    },
    {
      name: 'delete_user',
      description: 'HIGH RISK: permanently deletes a user account (irreversible).',
      parameters: {
        type: 'object',
        properties: { user_id: { type: 'string' } },
        required: ['user_id'],
      },
    },
  ];

  // Binding tools enables tool-safe streaming + high-risk gating.
  const cascade = (baseCascade as any).bindTools(tools);

  type GraphState = {
    input: string;
    result?: string;
  };

  const planner = async (state: GraphState) => {
    const msg = await cascade.invoke(state.input, {
      tags: ['example', 'langgraph', 'planner'],
      metadata: { example: 'langgraph-multi-agent', agent: 'planner' },
    });
    return { ...state, result: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content) };
  };

  const graph = new StateGraph<GraphState>()
    .addNode('planner', planner)
    .addEdge('planner', END)
    .setEntryPoint('planner');

  const app = graph.compile();

  const out = await app.invoke({
    input: 'Plan steps to fetch weather for Berlin. If any destructive action is needed, propose it but do not execute.',
  });

  console.log(out.result);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

