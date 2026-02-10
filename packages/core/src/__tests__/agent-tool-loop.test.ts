import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CascadeAgent, ToolConfig, ToolExecutor, type Tool } from '../index';

describe('CascadeAgent tool loop (auto-execution)', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    // Force providers to take the fetch path (no SDK / no real network).
    vi.stubGlobal('window', {});

    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        model: 'gpt-4o-mini',
        choices: [
          {
            finish_reason: 'tool_calls',
            message: {
              role: 'assistant',
              content: null,
              tool_calls: [
                {
                  id: 'call_1',
                  type: 'function',
                  function: { name: 'calculate', arguments: '{"expression":"2+2"}' },
                },
              ],
            },
          },
        ],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      }),
    });

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        model: 'gpt-4o-mini',
        choices: [
          {
            finish_reason: 'stop',
            message: {
              role: 'assistant',
              content: 'The result is 4.',
            },
          },
        ],
        usage: { prompt_tokens: 12, completion_tokens: 6, total_tokens: 18 },
      }),
    });

    vi.stubGlobal('fetch', fetchMock as any);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('executes tools and continues until the model stops requesting tools', async () => {
    const tools: Tool[] = [
      {
        type: 'function',
        function: {
          name: 'calculate',
          description: 'Calculator',
          parameters: {
            type: 'object',
            properties: { expression: { type: 'string' } },
            required: ['expression'],
          },
        },
      },
    ];

    const executor = new ToolExecutor([
      new ToolConfig({
        name: 'calculate',
        description: 'Calculator',
        parameters: {
          type: 'object',
          properties: { expression: { type: 'string' } },
          required: ['expression'],
        },
        function: ({ expression }: { expression: string }) => {
          if (expression !== '2+2') {
            throw new Error(`unexpected expression: ${expression}`);
          }
          return { result: 4 };
        },
      }),
    ]);

    const agent = new CascadeAgent({
      models: [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0,
          supportsTools: true,
          apiKey: 'test-key',
        },
      ],
      toolExecutor: executor,
    });

    const result = await agent.run('Compute 2+2 and reply with the result.', {
      tools,
      maxSteps: 3,
    });

    expect(result.content).toBe('The result is 4.');
    expect(result.hasToolCalls).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Ensure the second request included the persisted tool loop message history.
    const secondInit = fetchMock.mock.calls[1]?.[1] as any;
    const body = JSON.parse(secondInit.body);
    const assistantWithToolCalls = body.messages.find((m: any) => m.role === 'assistant');
    const toolMsg = body.messages.find((m: any) => m.role === 'tool');

    expect(assistantWithToolCalls.tool_calls?.[0]?.id).toBe('call_1');
    expect(toolMsg.tool_call_id).toBe('call_1');
  });
});

