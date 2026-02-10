/**
 * Agentic + Multi-Agent Example
 *
 * Demonstrates:
 * - Multi-turn tool loop (persist assistant tool_calls + tool results)
 * - Multi-agent orchestration (agent-as-a-tool delegation)
 * - Tool-capable model filtering + tool cascade routing
 *
 * Usage:
 *   export OPENAI_API_KEY="sk-..."
 *   npx tsx examples/nodejs/agentic-multi-agent.ts
 */

import {
  CascadeAgent,
  ToolCall,
  ToolConfig,
  ToolExecutor,
  type Message,
  type Tool,
} from '@cascadeflow/core';

function safeCalculate(expression: string): { expression: string; result?: number; error?: string } {
  try {
    const expr = expression
      .replace(/sqrt\(([^)]+)\)/g, 'Math.sqrt($1)')
      .replace(/pow\(([^,]+),([^)]+)\)/g, 'Math.pow($1,$2)')
      .replace(/abs\(([^)]+)\)/g, 'Math.abs($1)');

    // Minimal validation to avoid code injection in an example.
    if (!/^[\d\s+\-*/().,Math]+$/.test(expr)) {
      return { expression, error: 'Invalid expression' };
    }

    // eslint-disable-next-line no-eval
    const result = eval(expr);
    return { expression, result };
  } catch (e) {
    return { expression, error: e instanceof Error ? e.message : String(e) };
  }
}

async function runToolLoop(params: {
  agent: CascadeAgent;
  messages: Message[];
  tools: Tool[];
  executor: ToolExecutor;
  maxTurns?: number;
}): Promise<{ final: Message[] }> {
  const { agent, tools, executor } = params;
  const maxTurns = params.maxTurns ?? 6;
  const messages: Message[] = [...params.messages];

  for (let turn = 0; turn < maxTurns; turn++) {
    const result = await agent.run(messages, { tools, maxTokens: 600 });

    console.log(`\n[turn=${turn + 1}] model=${result.modelUsed} cost=$${result.totalCost.toFixed(6)}`);

    const assistantMsg: Message = { role: 'assistant', content: result.content ?? '' };
    if (result.toolCalls && result.toolCalls.length > 0) {
      assistantMsg.tool_calls = result.toolCalls;
      console.log(`  tool_calls=${result.toolCalls.length}`);
    }
    messages.push(assistantMsg);

    if (!result.toolCalls || result.toolCalls.length === 0) {
      console.log('\nFinal answer:\n');
      console.log(result.content);
      return { final: messages };
    }

    for (const raw of result.toolCalls) {
      const call = ToolCall.fromOpenAI(raw as any);
      const toolResult = await executor.execute(call);

      messages.push({
        role: 'tool',
        tool_call_id: call.id,
        content: JSON.stringify(toolResult.success ? toolResult.result : { error: toolResult.error }),
      });
    }
  }

  throw new Error(`Tool loop exceeded maxTurns=${maxTurns}`);
}

async function main() {
  console.log('\n' + '='.repeat(80));
  console.log('🤖 CASCADEFLOW - AGENTIC + MULTI-AGENT EXAMPLE (TypeScript)');
  console.log('='.repeat(80) + '\n');

  if (!process.env.OPENAI_API_KEY) {
    console.error('❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY="sk-..."');
    process.exit(1);
  }

  const researchAgent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
    ],
    quality: { threshold: 0.7 },
  });

  const mainAgent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, supportsTools: true },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625, supportsTools: true },
    ],
    quality: { threshold: 0.7 },
  });

  // Tool implementations (what actually runs in your app).
  const toolConfigs = [
    new ToolConfig({
      name: 'calculate',
      description: 'Perform a mathematical calculation (supports sqrt(), pow(), abs())',
      parameters: {
        type: 'object',
        properties: { expression: { type: 'string', description: 'Math expression' } },
        required: ['expression'],
      },
      function: async ({ expression }: { expression: string }) => safeCalculate(expression),
    }),
    new ToolConfig({
      name: 'search_web',
      description: 'Search the web (stub example that returns fake results)',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Search query' },
          num_results: { type: 'number', description: 'Number of results (1-5)' },
        },
        required: ['query'],
      },
      function: async ({ query, num_results }: { query: string; num_results?: number }) => {
        const n = Math.max(1, Math.min(5, num_results ?? 3));
        return {
          query,
          results: Array.from({ length: n }).map((_, i) => ({
            title: `Result ${i + 1} for "${query}"`,
            url: `https://example.com/${i + 1}`,
            snippet: `Stub snippet about ${query}`,
          })),
        };
      },
    }),
    new ToolConfig({
      name: 'delegate_to_researcher',
      description: 'Ask the research agent for a focused explanation or summary',
      parameters: {
        type: 'object',
        properties: { question: { type: 'string', description: 'Research question' } },
        required: ['question'],
      },
      function: async ({ question }: { question: string }) => {
        const res = await researchAgent.run(
          [
            { role: 'system', content: 'You are a concise research assistant. Answer in 2-4 sentences.' },
            { role: 'user', content: question },
          ],
          { maxTokens: 250 }
        );
        return { answer: res.content, model: res.modelUsed, cost: res.totalCost };
      },
    }),
  ];

  const executor = new ToolExecutor(toolConfigs);

  // Tool schemas (what you send to the model).
  const tools: Tool[] = toolConfigs.map((t) => ({
    type: 'function',
    function: {
      name: t.name,
      description: t.description,
      parameters: t.parameters,
    },
  }));

  const messages: Message[] = [
    {
      role: 'system',
      content:
        'You are an agent. Use tools when they help.\n' +
        '- Use calculate for any arithmetic.\n' +
        '- Use delegate_to_researcher for explanations you are unsure about.\n' +
        'When you have enough information, answer clearly and briefly.',
    },
    {
      role: 'user',
      content:
        'Compute sqrt(144) * 5 using the calculate tool, then ask the researcher to explain why the result is correct. ' +
        'Return the final answer with the calculation and the explanation.',
    },
  ];

  await runToolLoop({
    agent: mainAgent,
    messages,
    tools,
    executor,
    maxTurns: 6,
  });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

