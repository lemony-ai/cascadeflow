import type { CascadeAgent } from '../agent';
import { StreamEventType } from '../streaming';
import type { Message, Tool } from '../types';

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

  /**
   * Tools to expose to the underlying cascadeflow agent.
   *
   * Note: tools should generally be server-defined (do not trust client input).
   */
  tools?: Tool[];

  /**
   * Provider-specific options forwarded to the underlying provider request.
   * Example: OpenAI `tool_choice`.
   *
   * Note: This is advanced and should be server-defined (do not trust client input).
   */
  extra?: Record<string, any>;
}

type DataStreamFormatter = <T extends string>(type: T, value: any) => string;

type UIMessageWriter = {
  write: (chunk: any) => void;
};

type UIMessageStreamFactory = (options: { execute: (args: { writer: UIMessageWriter }) => Promise<void> | void; onError?: (error: unknown) => string }) => ReadableStream<any>;
type UIMessageStreamResponseFactory = (options: { stream: ReadableStream<any>; status?: number; statusText?: string; headers?: any }) => Response;

async function tryGetUiStreamFactories(): Promise<{
  createUIMessageStream: UIMessageStreamFactory;
  createUIMessageStreamResponse: UIMessageStreamResponseFactory;
} | null> {
  try {
    const mod = await import('ai');
    const createUIMessageStream = (mod as any).createUIMessageStream;
    const createUIMessageStreamResponse = (mod as any).createUIMessageStreamResponse;
    if (typeof createUIMessageStream === 'function' && typeof createUIMessageStreamResponse === 'function') {
      return { createUIMessageStream, createUIMessageStreamResponse };
    }
    return null;
  } catch {
    return null;
  }
}

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

type NormalizedToolCall = {
  id: string;
  name: string;
  argsText: string;
};

function normalizeToolCalls(input: any): NormalizedToolCall[] {
  if (!Array.isArray(input)) {
    return [];
  }

  return input
    .map((tc, idx) => {
      const id = typeof tc?.id === 'string' && tc.id.length > 0 ? tc.id : `call_${idx}`;
      const name = typeof tc?.function?.name === 'string' ? tc.function.name : 'unknown';
      const args = tc?.function?.arguments;
      const argsText =
        typeof args === 'string'
          ? args
          : args && typeof args === 'object'
            ? JSON.stringify(args)
            : '';
      return { id, name, argsText };
    })
    .filter((tc) => tc.id.length > 0);
}

function tryParseJson(input: string): unknown | null {
  try {
    return JSON.parse(input);
  } catch {
    return null;
  }
}

type ToolCallStreamState = Map<string, { name: string; argsText: string; started: boolean }>;

function emitToolCallDeltasUi(writer: UIMessageWriter, state: ToolCallStreamState, toolCalls: NormalizedToolCall[]) {
  for (const tc of toolCalls) {
    const prev = state.get(tc.id) ?? { name: tc.name, argsText: '', started: false };
    const name = tc.name !== 'unknown' ? tc.name : prev.name;

    if (!prev.started) {
      writer.write({ type: 'tool-input-start', toolCallId: tc.id, toolName: name });
    }

    const prevArgs = prev.argsText;
    const nextArgs = tc.argsText;
    const delta =
      nextArgs.length >= prevArgs.length && nextArgs.startsWith(prevArgs)
        ? nextArgs.slice(prevArgs.length)
        : nextArgs;

    if (delta.length > 0) {
      writer.write({ type: 'tool-input-delta', toolCallId: tc.id, inputTextDelta: delta });
    }

    state.set(tc.id, { name, argsText: nextArgs, started: true });
  }
}

function emitToolCallsFinalUi(writer: UIMessageWriter, state: ToolCallStreamState, toolCalls: NormalizedToolCall[]) {
  for (const tc of toolCalls) {
    const prev = state.get(tc.id) ?? { name: tc.name, argsText: '', started: false };
    const name = tc.name !== 'unknown' ? tc.name : prev.name;
    const argsText = tc.argsText || prev.argsText;
    const parsed = typeof argsText === 'string' ? tryParseJson(argsText) : null;
    writer.write({
      type: 'tool-input-available',
      toolCallId: tc.id,
      toolName: name,
      input: parsed ?? argsText,
    });
    state.set(tc.id, { name, argsText, started: true });
  }
}

function emitToolCallDeltasData(
  controller: ReadableStreamDefaultController<Uint8Array>,
  formatDataStreamPart: DataStreamFormatter,
  state: ToolCallStreamState,
  toolCalls: NormalizedToolCall[]
) {
  for (const tc of toolCalls) {
    const prev = state.get(tc.id) ?? { name: tc.name, argsText: '', started: false };
    const name = tc.name !== 'unknown' ? tc.name : prev.name;

    if (!prev.started) {
      controller.enqueue(encodeUtf8(formatDataStreamPart('tool_call_streaming_start', { toolCallId: tc.id, toolName: name })));
    }

    const prevArgs = prev.argsText;
    const nextArgs = tc.argsText;
    const delta =
      nextArgs.length >= prevArgs.length && nextArgs.startsWith(prevArgs)
        ? nextArgs.slice(prevArgs.length)
        : nextArgs;

    if (delta.length > 0) {
      controller.enqueue(encodeUtf8(formatDataStreamPart('tool_call_delta', { toolCallId: tc.id, argsTextDelta: delta })));
    }

    state.set(tc.id, { name, argsText: nextArgs, started: true });
  }
}

function emitToolCallsFinalData(
  controller: ReadableStreamDefaultController<Uint8Array>,
  formatDataStreamPart: DataStreamFormatter,
  state: ToolCallStreamState,
  toolCalls: NormalizedToolCall[]
) {
  for (const tc of toolCalls) {
    const prev = state.get(tc.id) ?? { name: tc.name, argsText: '', started: false };
    const name = tc.name !== 'unknown' ? tc.name : prev.name;
    const argsText = tc.argsText || prev.argsText;
    const parsed = typeof argsText === 'string' ? tryParseJson(argsText) : null;

    controller.enqueue(
      encodeUtf8(
        formatDataStreamPart('tool_call', {
          toolCallId: tc.id,
          toolName: name,
          args: parsed ?? argsText,
        })
      )
    );
    state.set(tc.id, { name, argsText, started: true });
  }
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
          tools: options.tools,
          extra: options.extra,
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
  // AI SDK v5+ prefers UI Message Streams (SSE + start/delta/end chunks).
  const uiFactories = await tryGetUiStreamFactories();
  if (uiFactories) {
    const { createUIMessageStream } = uiFactories;
    const textId = `txt_${Date.now().toString(16)}_${Math.random().toString(16).slice(2)}`;
    const toolState: ToolCallStreamState = new Map();
    return createUIMessageStream({
      onError: (err) => (err instanceof Error ? err.message : String(err)),
      async execute({ writer }) {
        writer.write({ type: 'text-start', id: textId });
        try {
          for await (const event of agent.stream(messages, {
            systemPrompt: options.systemPrompt,
            maxTokens: options.maxTokens,
            temperature: options.temperature,
            tools: options.tools,
            extra: options.extra,
          })) {
            if (signal?.aborted) {
              break;
            }
            if (event.type === StreamEventType.CHUNK) {
              const toolCalls = normalizeToolCalls((event as any)?.data?.tool_calls);
              if (toolCalls.length > 0) {
                emitToolCallDeltasUi(writer, toolState, toolCalls);
              }
              if (event.content) {
                writer.write({ type: 'text-delta', id: textId, delta: event.content });
              }
            } else if (event.type === StreamEventType.COMPLETE) {
              // Emit final tool-call inputs when the agent completes.
              const resultToolCalls = normalizeToolCalls((event as any)?.data?.result?.toolCalls);
              if (resultToolCalls.length > 0) {
                emitToolCallsFinalUi(writer, toolState, resultToolCalls);
              }
            }
          }
        } finally {
          writer.write({ type: 'text-end', id: textId });
        }
      },
    });
  }

  // AI SDK v4 fallback: "data" stream protocol (newline-delimited parts).
  const formatDataStreamPart = await getFormatDataStreamPart();
  const messageId = `msg_${Date.now().toString(16)}_${Math.random().toString(16).slice(2)}`;

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        controller.enqueue(encodeUtf8(formatDataStreamPart('start_step', { messageId })));

        const toolState: ToolCallStreamState = new Map();

        for await (const event of agent.stream(messages, {
          systemPrompt: options.systemPrompt,
          maxTokens: options.maxTokens,
          temperature: options.temperature,
          tools: options.tools,
          extra: options.extra,
        })) {
          if (signal?.aborted) {
            break;
          }

          if (event.type === StreamEventType.CHUNK) {
            const toolCalls = normalizeToolCalls((event as any)?.data?.tool_calls);
            if (toolCalls.length > 0) {
              emitToolCallDeltasData(controller, formatDataStreamPart, toolState, toolCalls);
            }
            if (event.content) {
              controller.enqueue(encodeUtf8(formatDataStreamPart('text', event.content)));
            }
          } else if (event.type === StreamEventType.COMPLETE) {
            const resultToolCalls = normalizeToolCalls((event as any)?.data?.result?.toolCalls);
            if (resultToolCalls.length > 0) {
              emitToolCallsFinalData(controller, formatDataStreamPart, toolState, resultToolCalls);
            }
          } else if (event.type === StreamEventType.ERROR) {
            controller.enqueue(
              encodeUtf8(formatDataStreamPart('error', event.data?.error ?? 'Unknown error'))
            );
          }
        }

        controller.enqueue(encodeUtf8(formatDataStreamPart('finish_message', { finishReason: 'stop' })));
        controller.enqueue(
          encodeUtf8(formatDataStreamPart('finish_step', { isContinued: false, finishReason: 'stop' }))
        );
      } catch (err: any) {
        controller.enqueue(encodeUtf8(formatDataStreamPart('error', err?.message ?? String(err))));
        controller.enqueue(encodeUtf8(formatDataStreamPart('finish_message', { finishReason: 'error' })));
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
        tools: options.tools,
        extra: options.extra,
      });
      return Response.json(result);
    }

    const protocol = options.protocol ?? 'data';
    if (protocol === 'text') {
      const stream = await runTextStream(agent, messages, options, request.signal);
      return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    // Prefer UI message stream response when available (AI SDK v5+).
    const uiFactories = await tryGetUiStreamFactories();
    const stream = await runDataStream(agent, messages, options, request.signal);
    if (uiFactories) {
      return uiFactories.createUIMessageStreamResponse({ stream });
    }
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
        tools: options.tools,
        extra: options.extra,
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
    const uiFactories = await tryGetUiStreamFactories();
    const stream = await runDataStream(agent, messages, options, request.signal);
    if (uiFactories) {
      return uiFactories.createUIMessageStreamResponse({ stream });
    }
    return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  };
}
