/* Real API smoke checks (developer-run).
 *
 * Runs a small set of calls against configured providers to validate:
 * - basic text completion
 * - tool-call generation + tool execution loop (direct tool loop)
 * - cost/acceptance fields are populated
 *
 * Usage (from repo root):
 *   set -a && source .env && set +a
 *   pnpm -C packages/core run real-api:smoke
 */

import { CascadeAgent, ToolConfig, ToolExecutor } from '../src/index.ts';
import type { Tool } from '../src/types.ts';

type Env = Record<string, string | undefined>;

function requireAny(env: Env, keys: string[]): void {
  if (!keys.some((k) => Boolean(env[k]))) {
    throw new Error(`Missing API keys: expected at least one of: ${keys.join(', ')}`);
  }
}

const env = process.env as Env;
requireAny(env, ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY']);

const getWeatherTool: Tool = {
  type: 'function',
  function: {
    name: 'get_weather',
    description: 'Get the weather for a location.',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string' },
      },
      required: ['location'],
    },
  },
};

async function main(): Promise<void> {
  const openaiKey = env.OPENAI_API_KEY;
  const anthropicKey = env.ANTHROPIC_API_KEY;

  if (openaiKey) {
    const toolExecutor = new ToolExecutor([
      new ToolConfig({
        name: 'get_weather',
        description: 'Get the weather for a location.',
        parameters: {
          type: 'object',
          properties: {
            location: { type: 'string' },
          },
          required: ['location'],
        },
        function: async ({ location }: { location?: string }) => ({
          location: location || 'unknown',
          forecast: 'sunny',
        }),
      }),
    ]);

    const agent = new CascadeAgent({
      models: [
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: openaiKey },
        { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: openaiKey },
      ],
    });

    const r1 = await agent.run('Return exactly: OK');
    if (!r1.content || !r1.content.includes('OK')) {
      throw new Error(`OpenAI smoke failed: unexpected content: ${JSON.stringify(r1.content)}`);
    }

    // Tool loop: direct path only (keeps this deterministic).
    const r2 = await agent.run("Call get_weather for location 'Paris'. Then respond with the result.", {
      tools: [getWeatherTool],
      forceDirect: true,
      maxSteps: 3,
      toolExecutor,
    });
    if (!r2.content || !/sunny/i.test(r2.content)) {
      throw new Error(`OpenAI tool-loop smoke failed: content=${JSON.stringify(r2.content)}`);
    }

    console.log(
      JSON.stringify(
        {
          provider: 'openai',
          text: { accepted: r1.draftAccepted, model: r1.modelUsed, cost: r1.totalCost },
          toolLoop: { accepted: r2.draftAccepted, model: r2.modelUsed, cost: r2.totalCost },
        },
        null,
        2
      )
    );
  }

  if (anthropicKey) {
    const agent = new CascadeAgent({
      models: [
        { name: 'claude-haiku-4-5-20251001', provider: 'anthropic', cost: 0.003, apiKey: anthropicKey },
        { name: 'claude-opus-4-5-20251101', provider: 'anthropic', cost: 0.045, apiKey: anthropicKey },
      ],
    });

    const r1 = await agent.run('Return exactly: OK');
    if (!r1.content || !r1.content.includes('OK')) {
      throw new Error(`Anthropic smoke failed: unexpected content: ${JSON.stringify(r1.content)}`);
    }

    console.log(
      JSON.stringify(
        {
          provider: 'anthropic',
          text: { accepted: r1.draftAccepted, model: r1.modelUsed, cost: r1.totalCost },
        },
        null,
        2
      )
    );
  }
}

main().catch((err) => {
  console.error(String(err?.stack ?? err));
  process.exit(1);
});
