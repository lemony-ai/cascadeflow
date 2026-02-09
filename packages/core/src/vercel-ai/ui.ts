import type { CascadeAgent } from '../agent';
import { StreamEventType } from '../streaming';
import type { Message } from '../types';

export type VercelAIStreamProtocol = 'data' | 'text';

export interface VercelAIChatHandlerOptions {
  /**
   * Streaming protocol expected by the Vercel AI SDK hooks.
   * - `data` (default): Vercel AI SDK data stream protocol (default for `useChat`).
   * - `text`: plain text streaming (requires `useChat({ streamProtocol: 'text' })`).
   */
  protocol?: VercelAIStreamProtocol;

  /**
   * Disable streaming and return JSON.
   * Useful for debugging or non-streaming clients.
   */
  stream?: boolean;

  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
}

type DataStreamFormatter = <T extends string>(type: T, value: any) => string;

async function getFormatDataStreamPart(): Promise<DataStreamFormatter> {
  // `ai` is an optional peer for @cascadeflow/core.
  // For Vercel AI SDK integrations it will be installed, and using its formatter
  // keeps us aligned with the exact stream protocol.
  const mod = await import('ai');
  if (typeof (mod as any).formatDataStreamPart !== 'function') {
    throw new Error("Missing 'formatDataStreamPart' export from 'ai'.");
  }
  return (mod as any).formatDataStreamPart as DataStreamFormatter;
}

function encodeUtf8(text: string): Uint8Array {
  return new TextEncoder().encode(text);
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
      if (role !== 'system' && role !== 'user' && role !== 'assistant' && role !== 'tool') {
        return null;
      }
      return { role, content } as Message;
    })
    .filter(Boolean) as Message[];
}

function toTextPrompt(input: any): string {
  if (typeof input?.prompt === 'string') {
    return input.prompt;
  }
  return '';
}

async function runTextStream(
  agent: CascadeAgent,
  input: string | Message[],
  options: VercelAIChatHandlerOptions,
  signal?: AbortSignal
) {
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
            controller.enqueue(encodeUtf8(event.content));
          }
        }
      } catch (err: any) {
        controller.enqueue(encodeUtf8(`\n[error] ${err?.message ?? String(err)}`));
      } finally {
        controller.close();
      }
    },
  });
}

async function runDataStream(
  agent: CascadeAgent,
  messages: Message[],
  options: VercelAIChatHandlerOptions,
  signal?: AbortSignal
) {
  const formatDataStreamPart = await getFormatDataStreamPart();
  const messageId = `msg_${Date.now().toString(16)}_${Math.random().toString(16).slice(2)}`;

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        controller.enqueue(encodeUtf8(formatDataStreamPart('start_step', { messageId })));

        for await (const event of agent.stream(messages, {
          systemPrompt: options.systemPrompt,
          maxTokens: options.maxTokens,
          temperature: options.temperature,
        })) {
          if (signal?.aborted) {
            break;
          }

          if (event.type === StreamEventType.CHUNK) {
            controller.enqueue(encodeUtf8(formatDataStreamPart('text', event.content)));
          } else if (event.type === StreamEventType.ERROR) {
            controller.enqueue(
              encodeUtf8(formatDataStreamPart('error', event.data?.error ?? 'Unknown error'))
            );
          }
        }

        // cascadeflow does not currently expose token usage in stream results, so we omit it.
        controller.enqueue(
          encodeUtf8(formatDataStreamPart('finish_message', { finishReason: 'stop' }))
        );
        controller.enqueue(
          encodeUtf8(formatDataStreamPart('finish_step', { isContinued: false, finishReason: 'stop' }))
        );
      } catch (err: any) {
        controller.enqueue(encodeUtf8(formatDataStreamPart('error', err?.message ?? String(err))));
        controller.enqueue(
          encodeUtf8(formatDataStreamPart('finish_message', { finishReason: 'error' }))
        );
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

    const stream = await runDataStream(agent, messages, options, request.signal);
    return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  };
}

export function createCompletionHandler(
  agent: CascadeAgent,
  options: VercelAIChatHandlerOptions = {}
): (request: Request) => Promise<Response> {
  return async (request: Request) => {
    const body = (await request.json().catch(() => ({}))) as any;
    const prompt = toTextPrompt(body);

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
    const stream = await runDataStream(agent, messages, options, request.signal);
    return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  };
}

