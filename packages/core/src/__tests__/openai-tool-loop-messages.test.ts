import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OpenAIProvider } from '../providers/openai';
import type { ModelConfig } from '../config';

describe('OpenAIProvider tool loop message forwarding', () => {
  let cfg: ModelConfig;
  const fetchMock = vi.fn();

  beforeEach(() => {
    // Force OpenAIProvider to use fetch path (no real network, no SDK).
    vi.stubGlobal('window', {});

    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        model: 'gpt-4o-mini',
        choices: [
          {
            message: { role: 'assistant', content: 'ok' },
            finish_reason: 'stop',
          },
        ],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      }),
    });
    vi.stubGlobal('fetch', fetchMock as any);

    cfg = {
      name: 'gpt-4o-mini',
      provider: 'openai',
      apiKey: 'test-key',
      cost: 0,
      supportsTools: true,
    };
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('includes assistant tool_calls when present in message history', async () => {
    const provider = new OpenAIProvider(cfg);

    await provider.generate({
      model: cfg.name,
      messages: [
        {
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: 'call_1',
              type: 'function',
              function: { name: 'calculate', arguments: '{"expression":"2+2"}' },
            },
          ],
        },
        {
          role: 'tool',
          content: '{"result":4}',
          tool_call_id: 'call_1',
        },
        {
          role: 'user',
          content: 'Now explain the result briefly.',
        },
      ],
      tools: [
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
      ],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0]?.[1] as any;
    expect(init).toBeTruthy();

    const body = JSON.parse(init.body);
    const assistantMsg = body.messages.find((m: any) => m.role === 'assistant');
    expect(assistantMsg).toBeTruthy();
    expect(assistantMsg.tool_calls).toEqual([
      {
        id: 'call_1',
        type: 'function',
        function: { name: 'calculate', arguments: '{"expression":"2+2"}' },
      },
    ]);
  });
});
