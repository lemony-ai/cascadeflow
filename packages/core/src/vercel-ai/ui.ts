import type { CascadeAgent } from '../agent';
import { StreamEventType } from '../streaming';
import type { Message } from '../types';

export type VercelAIStreamProtocol = 'data' | 'text';

export interface VercelAIChatHandlerOptions {
  /**
   * Streaming protocol expected by the client.
   * - `data`: Vercel AI SDK "UI message stream" SSE protocol (default for `useChat`)
   * - `text`: plain text streaming
   */
  protocol?: VercelAIStreamProtocol;

  /**
   * Disable streaming and return a single JSON response.
   * Useful for debugging or non-streaming clients.
   */
  stream?: boolean;

  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
}

function randomId(prefix: string): string {
  // Edge runtimes typically have crypto.randomUUID(). Node >=18 does too.
  const uuid = (globalThis.crypto as any)?.randomUUID?.();
  if (uuid) {
    return `${prefix}_${uuid}`;
  }
  return `${prefix}_${Math.random().toString(16).slice(2)}${Date.now().toString(16)}`;
}

function toCoreMessages(input: any): Message[] {
  if (!Array.isArray(input)) {
    return [];
  }
  return input
    .map((m) => {
      const role = m?.role;
      const content = m?.content;
      if (typeof role !== 'string' || typeof content !== 'string') {
        return null;
      }
      // cascadeflow core MessageRole is a string union; validate to avoid runtime surprises.
      if (role !== 'system' && role !== 'user' && role !== 'assistant' && role !== 'tool') {
        return null;
      }
      return { role, content } as Message;
    })
    .filter(Boolean) as Message[];
}

function sseEncode(data: unknown): Uint8Array {
  const encoder = new TextEncoder();
  return encoder.encode(`data: ${JSON.stringify(data)}\n\n`);
}

function sseDone(): Uint8Array {
  const encoder = new TextEncoder();
  return encoder.encode('data: [DONE]\n\n');
}

function textEncode(text: string): Uint8Array {
  const encoder = new TextEncoder();
  return encoder.encode(text);
}

function baseSseHeaders(): Record<string, string> {
  return {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    // Required by Vercel AI SDK `useChat` default stream parser.
    'x-vercel-ai-ui-message-stream': 'v1',
  };
}

async function runTextStream(agent: CascadeAgent, input: string | Message[], options: VercelAIChatHandlerOptions, signal?: AbortSignal) {
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const event of agent.stream(input, {
          systemPrompt: options.systemPrompt,
          maxTokens: options.maxTokens,
          temperature: options.temperature,
        })) {
          if (signal?.aborted) {
            break;
          }
          if (event.type === StreamEventType.CHUNK) {
            controller.enqueue(textEncode(event.content));
          }
        }
      } catch (err: any) {
        controller.enqueue(textEncode(`\n[error] ${err?.message ?? String(err)}`));
      } finally {
        controller.close();
      }
    },
  });
}

async function runVercelAIDataStream(agent: CascadeAgent, messages: Message[], options: VercelAIChatHandlerOptions, signal?: AbortSignal) {
  const messageId = randomId('msg');
  const textId = randomId('txt');

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        controller.enqueue(sseEncode({ type: 'start', messageId }));
        controller.enqueue(
          sseEncode({
            type: 'message',
            message: {
              id: messageId,
              role: 'assistant',
              content: [{ type: 'text', text: '' }],
            },
          })
        );
        controller.enqueue(sseEncode({ type: 'text-start', id: textId }));

        let finishReason: string | undefined;
        let usage: any | undefined;

        for await (const event of agent.stream(messages, {
          systemPrompt: options.systemPrompt,
          maxTokens: options.maxTokens,
          temperature: options.temperature,
        })) {
          if (signal?.aborted) {
            break;
          }
          if (event.type === StreamEventType.CHUNK) {
            controller.enqueue(sseEncode({ type: 'text-delta', id: textId, delta: event.content }));
          } else if (event.type === StreamEventType.COMPLETE) {
            // StreamEventData.result is not strongly typed; best effort extraction.
            const result = event.data?.result ?? {};
            finishReason = result.finishReason ?? result.finish_reason;
            usage = result.usage ?? result.raw?.usage;
          } else if (event.type === StreamEventType.ERROR) {
            controller.enqueue(sseEncode({ type: 'error', errorText: event.data?.error ?? 'Unknown error' }));
          }
        }

        controller.enqueue(sseEncode({ type: 'text-end', id: textId }));
        controller.enqueue(
          sseEncode({
            type: 'finish',
            finishReason: finishReason ?? 'stop',
            ...(usage ? { usage } : {}),
          })
        );
        controller.enqueue(sseDone());
      } catch (err: any) {
        controller.enqueue(sseEncode({ type: 'error', errorText: err?.message ?? String(err) }));
        controller.enqueue(sseEncode({ type: 'finish', finishReason: 'error' }));
        controller.enqueue(sseDone());
      } finally {
        controller.close();
      }
    },
  });
}

export function createChatHandler(
  agent: CascadeAgent,
  options: VercelAIChatHandlerOptions = {}
): (request: Request) => Promise<Response> {
  return async (request: Request) => {
    const body = (await request.json().catch(() => ({}))) as any;
    const messages = toCoreMessages(body?.messages);

    if (options.stream === false) {
      const result = await agent.run(messages, {
        systemPrompt: options.systemPrompt,
        maxTokens: options.maxTokens,
        temperature: options.temperature,
      });
      return Response.json(result);
    }

    const protocol = options.protocol ?? 'data';
    if (protocol === 'text') {
      const stream = await runTextStream(agent, messages, options, request.signal);
      return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    const stream = await runVercelAIDataStream(agent, messages, options, request.signal);
    return new Response(stream, { headers: baseSseHeaders() });
  };
}

export function createCompletionHandler(
  agent: CascadeAgent,
  options: VercelAIChatHandlerOptions = {}
): (request: Request) => Promise<Response> {
  return async (request: Request) => {
    const body = (await request.json().catch(() => ({}))) as any;
    const prompt = typeof body?.prompt === 'string' ? body.prompt : '';

    if (options.stream === false) {
      const result = await agent.run(prompt, {
        systemPrompt: options.systemPrompt,
        maxTokens: options.maxTokens,
        temperature: options.temperature,
      });
      return Response.json(result);
    }

    const protocol = options.protocol ?? 'data';
    if (protocol === 'text') {
      const stream = await runTextStream(agent, prompt, options, request.signal);
      return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    // Completion endpoint maps to a single user message.
    const messages: Message[] = [{ role: 'user', content: prompt }];
    const stream = await runVercelAIDataStream(agent, messages, options, request.signal);
    return new Response(stream, { headers: baseSseHeaders() });
  };
}
