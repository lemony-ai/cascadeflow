import { describe, expect, it, vi } from 'vitest';
import { StreamEventType } from '../../streaming';
import { createChatHandler } from '../ui';

describe('Vercel AI UI handlers', () => {
  it('applies request overrides when policy is enabled and authorized', async () => {
    const run = vi.fn().mockResolvedValue({
      content: 'ok',
      toolCalls: [],
      hasToolCalls: false,
      routingStrategy: 'direct',
    });
    const agent = { run, stream: vi.fn() } as any;

    const handler = createChatHandler(agent, {
      stream: false,
      requestOverrides: {
        enabled: true,
        secret: 'secret-key',
      },
    });

    const req = new Request('http://localhost/api/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-cascadeflow-override-key': 'secret-key',
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: 'hi' }],
        cascadeflow: {
          overrides: { forceDirect: true, maxSteps: 9, userTier: 'pro' },
        },
      }),
    });

    const res = await handler(req);
    expect(res.status).toBe(200);
    expect(run).toHaveBeenCalledTimes(1);
    const runOptions = run.mock.calls[0][1];
    expect(runOptions.forceDirect).toBe(true);
    expect(runOptions.maxSteps).toBe(9);
    expect(runOptions.userTier).toBe('pro');
  });

  it('ignores request overrides when secret is invalid', async () => {
    const run = vi.fn().mockResolvedValue({
      content: 'ok',
      toolCalls: [],
      hasToolCalls: false,
      routingStrategy: 'direct',
    });
    const agent = { run, stream: vi.fn() } as any;

    const handler = createChatHandler(agent, {
      stream: false,
      forceDirect: false,
      requestOverrides: {
        enabled: true,
        secret: 'secret-key',
      },
    });

    const req = new Request('http://localhost/api/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-cascadeflow-override-key': 'wrong',
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: 'hi' }],
        cascadeflow: {
          overrides: { forceDirect: true, maxSteps: 9, userTier: 'pro' },
        },
      }),
    });

    await handler(req);
    expect(run).toHaveBeenCalledTimes(1);
    const runOptions = run.mock.calls[0][1];
    expect(runOptions.forceDirect).toBe(false);
    expect(runOptions.maxSteps).toBeUndefined();
    expect(runOptions.userTier).toBeUndefined();
  });

  it('executes buffered tool loops across multiple run() calls', async () => {
    const run = vi
      .fn()
      .mockResolvedValueOnce({
        content: '',
        toolCalls: [
          {
            id: 'call_1',
            type: 'function',
            function: { name: 'get_weather', arguments: '{"city":"Berlin"}' },
          },
        ],
        hasToolCalls: true,
        routingStrategy: 'cascade',
        draftAccepted: true,
      })
      .mockResolvedValueOnce({
        content: 'Weather in Berlin is sunny.',
        toolCalls: [],
        hasToolCalls: false,
        routingStrategy: 'cascade',
        draftAccepted: true,
      });

    const agent = { run, stream: vi.fn() } as any;
    const handler = createChatHandler(agent, {
      stream: false,
      maxSteps: 3,
      tools: [
        {
          type: 'function',
          function: {
            name: 'get_weather',
            description: 'Get weather',
            parameters: {
              type: 'object',
              properties: { city: { type: 'string' } },
            },
          },
        },
      ],
      toolHandlers: {
        async get_weather(args) {
          return { city: String(args.city), weather: 'sunny' };
        },
      },
    });

    const req = new Request('http://localhost/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: 'What is weather in Berlin?' }],
      }),
    });

    const res = await handler(req);
    const body = (await res.json()) as any;

    expect(run).toHaveBeenCalledTimes(2);
    const secondCallMessages = run.mock.calls[1][0];
    expect(secondCallMessages.some((m: any) => m.role === 'tool')).toBe(true);
    expect(body.content).toBe('Weather in Berlin is sunny.');
  });

  it('emits cascade decision data parts during streaming', async () => {
    async function* streamEvents() {
      yield {
        type: StreamEventType.ROUTING,
        content: '',
        data: { strategy: 'cascade', complexity: 'moderate' },
      };
      yield {
        type: StreamEventType.DRAFT_DECISION,
        content: '',
        data: { accepted: false, score: 0.2, reason: 'quality_failed' },
      };
      yield {
        type: StreamEventType.SWITCH,
        content: 'switching',
        data: { from_model: 'mini', to_model: 'pro' },
      };
      yield {
        type: StreamEventType.CHUNK,
        content: 'hello',
        data: {},
      };
      yield {
        type: StreamEventType.COMPLETE,
        content: '',
        data: { result: { content: 'hello', toolCalls: [] } },
      };
    }

    const agent = {
      run: vi.fn(),
      stream: vi.fn(() => streamEvents()),
    } as any;

    const handler = createChatHandler(agent, {
      protocol: 'data',
      emitCascadeEvents: true,
    });

    const req = new Request('http://localhost/api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: 'hello' }],
      }),
    });

    const res = await handler(req);
    const text = await res.text();
    expect(text).toContain('cascade-routing');
    expect(text).toContain('cascade-draft-decision');
    expect(text).toContain('cascade-switch');
  });
});
