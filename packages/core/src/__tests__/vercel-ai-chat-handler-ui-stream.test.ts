import { describe, it, expect, vi } from 'vitest';
import { createChatHandler } from '../vercel-ai/ui';
import { StreamEventType, type StreamEvent } from '../streaming';

// Force the UI-message-stream path by mocking the AI SDK exports that
// `VercelAI.createChatHandler` feature-detects at runtime.
vi.mock('ai', async () => {
  const actual = await vi.importActual<any>('ai');
  const encoder = new TextEncoder();

  return {
    ...actual,
    createUIMessageStream({ execute, onError }: any) {
      return new ReadableStream<any>({
        start(controller) {
          const writer = {
            write(chunk: any) {
              controller.enqueue(chunk);
            },
          };

          Promise.resolve()
            .then(() => execute({ writer }))
            .then(() => controller.close())
            .catch((err) => {
              controller.enqueue({ type: 'error', errorText: onError ? onError(err) : String(err) });
              controller.close();
            });
        },
      });
    },
    createUIMessageStreamResponse({ stream, status, statusText, headers }: any) {
      const byteStream = stream.pipeThrough(
        new TransformStream<any, Uint8Array>({
          transform(chunk, controller) {
            controller.enqueue(encoder.encode(`${JSON.stringify(chunk)}\n`));
          },
        })
      );
      return new Response(byteStream, {
        status: status ?? 200,
        statusText,
        headers: headers ?? { 'Content-Type': 'application/x-ndjson; charset=utf-8' },
      });
    },
  };
});

describe('VercelAI.createChatHandler (UI message stream)', () => {
  it('emits tool-input chunks when tool calls are present', async () => {
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

    const text = await new Response(res.body!).text();
    const chunks = text
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line));

    expect(chunks.some((c) => c.type === 'tool-input-start' && c.toolCallId === 'call_1')).toBe(true);
    expect(chunks.some((c) => c.type === 'tool-input-delta' && c.toolCallId === 'call_1')).toBe(true);
    expect(
      chunks.some(
        (c) =>
          c.type === 'tool-input-available' &&
          c.toolCallId === 'call_1' &&
          c.toolName === 'get_weather' &&
          c.input?.location === 'Paris'
      )
    ).toBe(true);
  });
});

