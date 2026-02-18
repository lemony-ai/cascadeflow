import { describe, it, expect } from 'vitest';
import { processDataStream } from 'ai';
import { createChatHandler } from '../vercel-ai/ui';
import { StreamEventType, type StreamEvent } from '../streaming';

describe('VercelAI.createChatHandler', () => {
  it('converts AI SDK UI messages with `parts` into core messages', async () => {
    let receivedMessages: any[] = [];
    const agent = {
      async *stream(messages: any[]) {
        receivedMessages = messages;
        yield { type: StreamEventType.CHUNK, content: 'OK', data: {} } satisfies StreamEvent;
        yield {
          type: StreamEventType.COMPLETE,
          content: '',
          data: { result: { content: 'OK' } },
        } satisfies StreamEvent;
      },
      async run() {
        return { content: 'OK' };
      },
    } as any;

    const handler = createChatHandler(agent, { protocol: 'data' });
    const req = new Request('http://local/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        messages: [
          {
            role: 'user',
            parts: [{ type: 'text', text: 'Hello from parts' }],
          },
        ],
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    const res = await handler(req);
    expect(res.ok).toBe(true);
    expect(receivedMessages).toHaveLength(1);
    expect(receivedMessages[0]).toEqual({
      role: 'user',
      content: 'Hello from parts',
    });
  });

  it('preserves tool metadata fields from incoming messages', async () => {
    let receivedMessages: any[] = [];
    const agent = {
      async *stream(messages: any[]) {
        receivedMessages = messages;
        yield { type: StreamEventType.CHUNK, content: 'OK', data: {} } satisfies StreamEvent;
        yield {
          type: StreamEventType.COMPLETE,
          content: '',
          data: { result: { content: 'OK' } },
        } satisfies StreamEvent;
      },
      async run() {
        return { content: 'OK' };
      },
    } as any;

    const handler = createChatHandler(agent, { protocol: 'data' });
    const req = new Request('http://local/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        messages: [
          {
            role: 'assistant',
            content: '',
            tool_calls: [
              {
                id: 'call_1',
                type: 'function',
                function: {
                  name: 'lookup',
                  arguments: { q: 'abc' },
                },
              },
            ],
          },
          {
            role: 'tool',
            tool_call_id: 'call_1',
            name: 'lookup',
            content: 'tool-result',
          },
        ],
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    const res = await handler(req);
    expect(res.ok).toBe(true);
    expect(receivedMessages).toHaveLength(2);
    expect(receivedMessages[0]).toMatchObject({
      role: 'assistant',
      content: '',
      tool_calls: [
        {
          id: 'call_1',
          type: 'function',
          function: { name: 'lookup', arguments: JSON.stringify({ q: 'abc' }) },
        },
      ],
    });
    expect(receivedMessages[1]).toMatchObject({
      role: 'tool',
      tool_call_id: 'call_1',
      name: 'lookup',
      content: 'tool-result',
    });
  });

  it('streams data protocol compatible with @ai-sdk/react useChat default', async () => {
    // Minimal agent stub: yields CHUNK events and then COMPLETE.
    const agent = {
      async *stream() {
        yield { type: StreamEventType.CHUNK, content: 'Hello ', data: {} } satisfies StreamEvent;
        yield { type: StreamEventType.CHUNK, content: 'world', data: {} } satisfies StreamEvent;
        yield { type: StreamEventType.COMPLETE, content: '', data: { result: { content: 'Hello world' } } } satisfies StreamEvent;
      },
      async run() {
        return { content: 'Hello world' };
      },
    } as any;

    const handler = createChatHandler(agent, { protocol: 'data' });

    const req = new Request('http://local/api/chat', {
      method: 'POST',
      body: JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }),
      headers: { 'Content-Type': 'application/json' },
    });
    const res = await handler(req);

    expect(res.ok).toBe(true);
    expect(res.body).toBeTruthy();

    let finalContent = '';
    await processDataStream({
      stream: res.body!,
      onTextPart(value: string) {
        finalContent += value;
      },
    });

    expect(finalContent).toBe('Hello world');
  });

  it('streams tool call parts when tool calls are present (data protocol)', async () => {
    const agent = {
      async *stream() {
        yield {
          type: StreamEventType.CHUNK,
          content: '',
          data: {
            tool_calls: [
              {
                id: 'call_1',
                type: 'function',
                function: { name: 'get_weather', arguments: '{"location":' },
              },
            ],
          },
        } satisfies StreamEvent;
        yield {
          type: StreamEventType.CHUNK,
          content: '',
          data: {
            tool_calls: [
              {
                id: 'call_1',
                type: 'function',
                function: { name: 'get_weather', arguments: '{"location":"Paris"}' },
              },
            ],
          },
        } satisfies StreamEvent;
        yield {
          type: StreamEventType.COMPLETE,
          content: '',
          data: {
            result: {
              toolCalls: [
                {
                  id: 'call_1',
                  type: 'function',
                  function: { name: 'get_weather', arguments: '{"location":"Paris"}' },
                },
              ],
            },
          },
        } satisfies StreamEvent;
      },
      async run() {
        return { content: '' };
      },
    } as any;

    const handler = createChatHandler(agent, { protocol: 'data' });
    const req = new Request('http://local/api/chat', {
      method: 'POST',
      body: JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }),
      headers: { 'Content-Type': 'application/json' },
    });

    const res = await handler(req);
    expect(res.ok).toBe(true);
    expect(res.body).toBeTruthy();

    const starts: any[] = [];
    const deltas: any[] = [];
    const calls: any[] = [];

    await processDataStream({
      stream: res.body!,
      onToolCallStreamingStartPart(value: any) {
        starts.push(value);
      },
      onToolCallDeltaPart(value: any) {
        deltas.push(value);
      },
      onToolCallPart(value: any) {
        calls.push(value);
      },
    });

    expect(starts).toEqual([{ toolCallId: 'call_1', toolName: 'get_weather' }]);
    expect(deltas.length).toBeGreaterThanOrEqual(1);
    expect(calls).toEqual([
      { toolCallId: 'call_1', toolName: 'get_weather', args: { location: 'Paris' } },
    ]);
  });
});
