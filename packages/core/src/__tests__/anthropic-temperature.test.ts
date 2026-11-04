import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnthropicProvider } from '../providers/anthropic';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe.each(['sdk', 'fetch'] as const)('Anthropic temperature (%s)', (transport) => {
  it.each([
    ['claude-opus-4-7', false],
    ['claude-opus-4-8', false],
    ['claude-opus-5-5', false],
    ['claude-sonnet-5-5', false],
    ['claude-haiku-5-5', false],
    ['claude-fable-5', false],
    ['anthropic/CLAUDE-MYTHOS-5', false],
    ['claude-opus-4.7-latest', false],
    ['anthropic/claude_opus_4_7', false],
    ['claude-opus-4-6', true],
    ['claude-sonnet-4-5', true],
    ['custom-model', true],
  ] as const)('handles sampling for %s', async (model, supportsTemperature) => {
    const provider = new AnthropicProvider({
      name: model, provider: 'anthropic', apiKey: 'test', cost: 0, temperature: 0.2,
    });
    const payloads: Array<Record<string, unknown>> = [];
    const completion = {
      model, content: [{ type: 'text', text: 'ok' }],
      usage: { input_tokens: 1, output_tokens: 1 }, stop_reason: 'end_turn',
    };
    const events = [
      { type: 'content_block_delta', delta: { type: 'text_delta', text: 'ok' } },
      { type: 'message_stop' },
    ];
    const capture = (payload: Record<string, unknown>) => {
      payloads.push(payload);
      if (!supportsTemperature && 'temperature' in payload) {
        throw new Error('temperature not supported');
      }
    };
    provider['useSDK'] = transport === 'sdk';
    provider['client'] = {
      messages: {
        create: async (payload: Record<string, unknown>) => {
          capture(payload);
          return completion;
        },
        stream: async function* (payload: Record<string, unknown>) {
          capture(payload);
          yield* events;
        },
      },
    };
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
      capture(payload);
      return payload.stream
        ? new Response(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join(''))
        : new Response(JSON.stringify(completion));
    }));

    for (const temperature of [undefined, 0, 0.3]) {
      const request = { model, messages: [{ role: 'user' as const, content: 'hi' }], temperature };
      expect((await provider.generate(request)).content).toBe('ok');
      const chunks = [];
      for await (const chunk of provider.stream(request)) chunks.push(chunk.content);
      expect(chunks.join('')).toBe('ok');
      for (const payload of payloads.slice(-2)) {
        if (supportsTemperature) {
          expect(payload.temperature).toBe(temperature ?? 0.2);
        } else {
          expect(payload).not.toHaveProperty('temperature');
        }
      }
    }
  });
});
