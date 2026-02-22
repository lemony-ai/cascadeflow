import type { CascadeAgent } from '../agent';
import { StreamEventType } from '../streaming';
import type { Message, Tool } from '../types';
import { ToolCall, ToolCallFormat, ToolConfig, ToolExecutor } from '../tools';

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

  /**
   * Optional tool executor for automatic server-side tool loops.
   *
   * When provided (with `tools`), the handler can execute tool calls and continue
   * the conversation up to `maxSteps`.
   */
  toolExecutor?: ToolExecutor;

  /**
   * Convenience map for server-side tool execution without manually constructing
   * a ToolExecutor. Keys must match `tools[].function.name`.
   */
  toolHandlers?: Record<string, (args: Record<string, any>) => unknown | Promise<unknown>>;

  /**
   * Maximum model turns when tool execution loop is enabled.
   * Default comes from the agent (`5` in current implementation).
   */
  maxSteps?: number;

  /**
   * Force direct execution (skip cascade) in the underlying agent.
   */
  forceDirect?: boolean;

  /**
   * Optional user tier for future tier-aware routing.
   */
  userTier?: string;

  /**
   * Emit cascade routing/decision events into stream parts for frontend debugging.
   * Enabled by default.
   */
  emitCascadeEvents?: boolean;

  /**
   * Optional request-level override policy. Useful for staging/test harnesses where
   * callers may need to toggle safe routing controls without redeploying.
   *
   * Overrides are read from `body.cascadeflow.overrides` (or `body.cascadeflow_overrides`).
   */
  requestOverrides?: {
    /** Enable request override parsing. Default: false */
    enabled?: boolean;
    /** Optional shared secret that must match the request header value. */
    secret?: string;
    /** Header name used for secret verification. Default: `x-cascadeflow-override-key` */
    headerName?: string;
    /** Allowlist of fields callers may override. Default: `forceDirect`, `maxSteps`, `userTier` */
    allowedFields?: Array<'forceDirect' | 'maxSteps' | 'userTier'>;
  };
}

type AgentRunLikeOptions = {
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
  tools?: Tool[];
  extra?: Record<string, any>;
  toolExecutor?: ToolExecutor;
  maxSteps?: number;
  forceDirect?: boolean;
  userTier?: string;
};

type RequestOverrideField = 'forceDirect' | 'maxSteps' | 'userTier';

const DEFAULT_REQUEST_OVERRIDE_HEADER = 'x-cascadeflow-override-key';
const DEFAULT_REQUEST_OVERRIDE_FIELDS: RequestOverrideField[] = [
  'forceDirect',
  'maxSteps',
  'userTier',
];

function resolveToolExecutor(options: VercelAIChatHandlerOptions): ToolExecutor | undefined {
  if (options.toolExecutor) {
    return options.toolExecutor;
  }

  if (!options.toolHandlers) {
    return undefined;
  }

  if (!options.tools || options.tools.length === 0) {
    throw new Error('`toolHandlers` requires `tools` to be configured.');
  }

  const configs = options.tools.map((tool) => {
    const name = tool?.function?.name;
    if (!name) {
      throw new Error('Each tool must define `function.name` when using `toolHandlers`.');
    }

    const handler = options.toolHandlers?.[name];
    if (typeof handler !== 'function') {
      throw new Error(`Missing tool handler for '${name}'. Add it to \`toolHandlers\`.`);
    }

    const description = tool?.function?.description ?? `Execute ${name}`;
    const parameters =
      tool?.function?.parameters && typeof tool.function.parameters === 'object'
        ? (tool.function.parameters as any)
        : { type: 'object', properties: {} };

    return new ToolConfig({
      name,
      description,
      parameters,
      function: handler,
    });
  });

  return new ToolExecutor(configs);
}

function buildAgentRunOptions(
  options: VercelAIChatHandlerOptions,
  resolvedToolExecutor?: ToolExecutor
): AgentRunLikeOptions {
  return {
    systemPrompt: options.systemPrompt,
    maxTokens: options.maxTokens,
    temperature: options.temperature,
    tools: options.tools,
    extra: options.extra,
    toolExecutor: resolvedToolExecutor,
    maxSteps: options.maxSteps,
    forceDirect: options.forceDirect,
    userTier: options.userTier,
  };
}

function mergeAgentRunOptions(
  base: AgentRunLikeOptions,
  overrides: Partial<AgentRunLikeOptions>
): AgentRunLikeOptions {
  return {
    ...base,
    ...(overrides.forceDirect !== undefined ? { forceDirect: overrides.forceDirect } : {}),
    ...(overrides.maxSteps !== undefined ? { maxSteps: overrides.maxSteps } : {}),
    ...(overrides.userTier !== undefined ? { userTier: overrides.userTier } : {}),
  };
}

function buildAgentStreamOptions(runOptions: AgentRunLikeOptions) {
  return {
    systemPrompt: runOptions.systemPrompt,
    maxTokens: runOptions.maxTokens,
    temperature: runOptions.temperature,
    tools: runOptions.tools,
    extra: runOptions.extra,
    forceDirect: runOptions.forceDirect,
    userTier: runOptions.userTier,
  };
}

function resolveRequestOverrides(
  request: Request,
  body: any,
  options: VercelAIChatHandlerOptions
): Partial<AgentRunLikeOptions> {
  const policy = options.requestOverrides;
  if (!policy?.enabled) {
    return {};
  }

  const rawOverrides =
    body?.cascadeflow?.overrides && typeof body.cascadeflow.overrides === 'object'
      ? body.cascadeflow.overrides
      : body?.cascadeflow_overrides && typeof body.cascadeflow_overrides === 'object'
        ? body.cascadeflow_overrides
        : null;

  if (!rawOverrides) {
    return {};
  }

  if (policy.secret) {
    const headerName = policy.headerName || DEFAULT_REQUEST_OVERRIDE_HEADER;
    const provided = request.headers.get(headerName);
    if (!provided || provided !== policy.secret) {
      return {};
    }
  }

  const allowed = new Set<RequestOverrideField>(
    (policy.allowedFields && policy.allowedFields.length > 0
      ? policy.allowedFields
      : DEFAULT_REQUEST_OVERRIDE_FIELDS) as RequestOverrideField[]
  );

  const out: Partial<AgentRunLikeOptions> = {};
  if (allowed.has('forceDirect') && typeof rawOverrides.forceDirect === 'boolean') {
    out.forceDirect = rawOverrides.forceDirect;
  }
  if (allowed.has('maxSteps') && typeof rawOverrides.maxSteps === 'number' && Number.isFinite(rawOverrides.maxSteps)) {
    const bounded = Math.max(1, Math.min(20, Math.floor(rawOverrides.maxSteps)));
    out.maxSteps = bounded;
  }
  if (allowed.has('userTier') && typeof rawOverrides.userTier === 'string' && rawOverrides.userTier.trim().length > 0) {
    out.userTier = rawOverrides.userTier.trim();
  }

  return out;
}

function shouldUseBufferedToolLoop(options: VercelAIChatHandlerOptions, resolvedToolExecutor?: ToolExecutor): boolean {
  return Boolean(resolvedToolExecutor && options.tools && options.tools.length > 0);
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

type ToolExecutionOutcome = {
  call: NormalizedToolCall;
  success: boolean;
  output: unknown;
  error?: string;
};

type ToolLoopStepOutcome = {
  step: number;
  result: any;
  toolCalls: NormalizedToolCall[];
  toolExecution: ToolExecutionOutcome[];
  continued: boolean;
  maxStepsReached: boolean;
};

type ToolLoopExecutionResult = {
  result: any;
  steps: number;
  maxStepsReached: boolean;
  lastToolCalls: NormalizedToolCall[];
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

function parseNormalizedToolArgs(argsText: string): Record<string, any> {
  if (!argsText || argsText.trim().length === 0) {
    return {};
  }
  const parsed = tryParseJson(argsText);
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    return parsed as Record<string, any>;
  }
  return { value: parsed ?? argsText };
}

function toMessageToolCall(tc: NormalizedToolCall): NonNullable<Message['tool_calls']>[number] {
  return {
    id: tc.id,
    type: 'function',
    function: {
      name: tc.name,
      arguments: tc.argsText,
    },
  };
}

async function executeNormalizedToolCalls(
  executor: ToolExecutor,
  toolCalls: NormalizedToolCall[]
): Promise<ToolExecutionOutcome[]> {
  const parsedCalls = toolCalls.map((call) => {
    return new ToolCall({
      id: call.id,
      name: call.name,
      arguments: parseNormalizedToolArgs(call.argsText),
      providerFormat: ToolCallFormat.OPENAI,
    });
  });

  const results = await executor.executeParallel(parsedCalls);
  return results.map((result, idx) => {
    const call = toolCalls[idx];
    if (result.success) {
      return {
        call,
        success: true,
        output: result.result,
      };
    }
    const error = result.error || 'Tool execution failed';
    return {
      call,
      success: false,
      output: { error },
      error,
    };
  });
}

function appendToolLoopStepMessages(
  messages: Message[],
  result: any,
  toolCalls: NormalizedToolCall[],
  toolExecution: ToolExecutionOutcome[]
): void {
  const rawToolCalls = coerceToolCalls(result?.toolCalls);
  const fallbackToolCalls = toolCalls.map(toMessageToolCall);
  messages.push({
    role: 'assistant',
    content: typeof result?.content === 'string' ? result.content : '',
    ...(toolCalls.length > 0
      ? { tool_calls: rawToolCalls && rawToolCalls.length > 0 ? rawToolCalls : fallbackToolCalls }
      : {}),
  });

  for (const executed of toolExecution) {
    messages.push({
      role: 'tool',
      tool_call_id: executed.call.id,
      name: executed.call.name,
      content: toolOutputToContent(executed.output),
    });
  }
}

async function runBufferedToolLoop(
  agent: CascadeAgent,
  input: string | Message[],
  runOptions: AgentRunLikeOptions,
  executor: ToolExecutor,
  signal?: AbortSignal,
  onStep?: (outcome: ToolLoopStepOutcome) => Promise<void> | void
): Promise<ToolLoopExecutionResult> {
  const loopMessages: Message[] = Array.isArray(input)
    ? [...input]
    : [{ role: 'user', content: input }];
  const maxSteps = runOptions.maxSteps ?? 5;

  let lastResult: any = null;
  let lastToolCalls: NormalizedToolCall[] = [];

  for (let step = 1; step <= maxSteps; step++) {
    if (signal?.aborted) {
      break;
    }

    const stepResult = await agent.run(loopMessages, {
      ...runOptions,
      toolExecutor: undefined,
      maxSteps: undefined,
    } as any);
    lastResult = stepResult;

    const toolCalls = normalizeToolCalls((stepResult as any)?.toolCalls);
    lastToolCalls = toolCalls;
    const shouldContinue = toolCalls.length > 0 && step < maxSteps;
    let toolExecution: ToolExecutionOutcome[] = [];

    if (shouldContinue) {
      toolExecution = await executeNormalizedToolCalls(executor, toolCalls);
      appendToolLoopStepMessages(loopMessages, stepResult, toolCalls, toolExecution);
    }

    const outcome: ToolLoopStepOutcome = {
      step,
      result: stepResult,
      toolCalls,
      toolExecution,
      continued: shouldContinue,
      maxStepsReached: !shouldContinue && toolCalls.length > 0 && step >= maxSteps,
    };
    if (onStep) {
      await onStep(outcome);
    }

    if (!shouldContinue) {
      return {
        result: stepResult,
        steps: step,
        maxStepsReached: outcome.maxStepsReached,
        lastToolCalls: toolCalls,
      };
    }
  }

  return {
    result: lastResult,
    steps: maxSteps,
    maxStepsReached: lastToolCalls.length > 0,
    lastToolCalls,
  };
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

function shouldEmitCascadeEvents(options: VercelAIChatHandlerOptions): boolean {
  return options.emitCascadeEvents !== false;
}

function emitCascadePartUi(
  writer: UIMessageWriter,
  part: 'routing' | 'draft-decision' | 'switch' | 'summary',
  payload: Record<string, any>
) {
  writer.write({ type: `data-cascade-${part}`, data: payload });
}

function emitCascadePartData(
  controller: ReadableStreamDefaultController<Uint8Array>,
  formatDataStreamPart: DataStreamFormatter,
  part: 'routing' | 'draft-decision' | 'switch' | 'summary',
  payload: Record<string, any>
) {
  // AI SDK data stream protocol requires "data" parts to be arrays.
  controller.enqueue(
    encodeUtf8(
      formatDataStreamPart('data', [
        {
          type: `cascade-${part}`,
          data: payload,
        },
      ])
    )
  );
}

function emitCascadeStreamEventUi(writer: UIMessageWriter, event: any) {
  if (event.type === StreamEventType.ROUTING) {
    emitCascadePartUi(writer, 'routing', event.data || {});
  } else if (event.type === StreamEventType.DRAFT_DECISION) {
    emitCascadePartUi(writer, 'draft-decision', event.data || {});
  } else if (event.type === StreamEventType.SWITCH) {
    emitCascadePartUi(writer, 'switch', {
      ...(event.data || {}),
      message: event.content || '',
    });
  }
}

function emitCascadeStreamEventData(
  controller: ReadableStreamDefaultController<Uint8Array>,
  formatDataStreamPart: DataStreamFormatter,
  event: any
) {
  if (event.type === StreamEventType.ROUTING) {
    emitCascadePartData(controller, formatDataStreamPart, 'routing', event.data || {});
  } else if (event.type === StreamEventType.DRAFT_DECISION) {
    emitCascadePartData(controller, formatDataStreamPart, 'draft-decision', event.data || {});
  } else if (event.type === StreamEventType.SWITCH) {
    emitCascadePartData(controller, formatDataStreamPart, 'switch', {
      ...(event.data || {}),
      message: event.content || '',
    });
  }
}

function summarizeCascadeResult(result: any, steps: number, maxStepsReached: boolean): Record<string, any> {
  return {
    steps,
    max_steps_reached: maxStepsReached,
    routing_strategy: result?.routingStrategy,
    cascaded: result?.cascaded,
    draft_accepted: result?.draftAccepted,
    model_used: result?.modelUsed,
    has_tool_calls: result?.hasToolCalls,
    reason: result?.reason,
  };
}

function toJsonString(input: unknown): string {
  if (typeof input === 'string') {
    return input;
  }
  if (input === undefined) {
    return '';
  }
  try {
    return JSON.stringify(input);
  } catch {
    return String(input);
  }
}

function textFromMixedContent(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }
  if (!Array.isArray(content)) {
    return '';
  }
  const chunks: string[] = [];
  for (const part of content) {
    if (typeof part === 'string') {
      chunks.push(part);
      continue;
    }
    if (!part || typeof part !== 'object') {
      continue;
    }
    const type = (part as any).type;
    const text = (part as any).text;
    if ((type === 'text' || type === 'reasoning') && typeof text === 'string') {
      chunks.push(text);
    }
  }
  return chunks.join('');
}

function toolOutputToContent(output: unknown): string {
  if (output && typeof output === 'object') {
    const type = (output as any).type;
    if (type === 'text' && typeof (output as any).value === 'string') {
      return (output as any).value;
    }
    if (type === 'json') {
      return toJsonString((output as any).value);
    }
    if (type === 'execution-denied') {
      return typeof (output as any).reason === 'string' ? (output as any).reason : 'Tool execution denied';
    }
  }
  return toJsonString(output);
}

function coerceToolCalls(toolCalls: unknown): Message['tool_calls'] | undefined {
  if (!Array.isArray(toolCalls)) {
    return undefined;
  }
  const normalized = toolCalls
    .map((tc) => {
      const id = typeof (tc as any)?.id === 'string' ? (tc as any).id : '';
      const type = (tc as any)?.type === 'function' ? 'function' : null;
      const name = typeof (tc as any)?.function?.name === 'string' ? (tc as any).function.name : '';
      const args = (tc as any)?.function?.arguments;
      const argumentsText =
        typeof args === 'string' ? args : args && typeof args === 'object' ? JSON.stringify(args) : '';
      if (!id || !type || !name) {
        return null;
      }
      return {
        id,
        type,
        function: {
          name,
          arguments: argumentsText,
        },
      };
    })
    .filter(Boolean) as NonNullable<Message['tool_calls']>;
  return normalized.length > 0 ? normalized : undefined;
}

function coerceToolCallsFromParts(parts: unknown): Message['tool_calls'] | undefined {
  if (!Array.isArray(parts)) {
    return undefined;
  }

  const byId = new Map<string, NonNullable<Message['tool_calls']>[number]>();
  for (const part of parts) {
    if (!part || typeof part !== 'object') {
      continue;
    }

    const type = (part as any).type;
    const invocation =
      type === 'tool-invocation' && (part as any).toolInvocation && typeof (part as any).toolInvocation === 'object'
        ? (part as any).toolInvocation
        : null;

    let id = '';
    let name = '';
    let input: unknown;

    if (invocation) {
      id = typeof invocation.toolCallId === 'string' ? invocation.toolCallId : '';
      name = typeof invocation.toolName === 'string' ? invocation.toolName : '';
      input = invocation.args ?? invocation.input;
    } else if (typeof type === 'string' && type.startsWith('tool-')) {
      id = typeof (part as any).toolCallId === 'string' ? (part as any).toolCallId : '';
      if (type === 'dynamic-tool' || type === 'tool-call') {
        name = typeof (part as any).toolName === 'string' ? (part as any).toolName : '';
      } else if (type !== 'tool-result' && type !== 'tool-approval-request' && type !== 'tool-approval-response') {
        name = type.slice('tool-'.length);
      }
      input = (part as any).input;
    }

    if (!id || !name) {
      continue;
    }

    byId.set(id, {
      id,
      type: 'function',
      function: {
        name,
        arguments: toJsonString(input),
      },
    });
  }

  const toolCalls = Array.from(byId.values());
  return toolCalls.length > 0 ? toolCalls : undefined;
}

function toolMessagesFromParts(parts: unknown): Message[] {
  if (!Array.isArray(parts)) {
    return [];
  }

  const output: Message[] = [];
  const seen = new Set<string>();

  for (const part of parts) {
    if (!part || typeof part !== 'object') {
      continue;
    }

    const type = (part as any).type;
    const invocation =
      type === 'tool-invocation' && (part as any).toolInvocation && typeof (part as any).toolInvocation === 'object'
        ? (part as any).toolInvocation
        : null;

    const state =
      (invocation && typeof invocation.state === 'string' ? invocation.state : null) ??
      (typeof (part as any).state === 'string' ? (part as any).state : null);

    if (state !== 'output-available' && state !== 'output-error' && state !== 'output-denied') {
      continue;
    }

    const toolCallId =
      (invocation && typeof invocation.toolCallId === 'string' ? invocation.toolCallId : null) ??
      (typeof (part as any).toolCallId === 'string' ? (part as any).toolCallId : null);
    if (!toolCallId || seen.has(toolCallId)) {
      continue;
    }

    const toolName =
      (invocation && typeof invocation.toolName === 'string' ? invocation.toolName : null) ??
      (type === 'dynamic-tool' && typeof (part as any).toolName === 'string'
        ? (part as any).toolName
        : typeof type === 'string' &&
            type.startsWith('tool-') &&
            type !== 'tool-result' &&
            type !== 'tool-approval-request' &&
            type !== 'tool-approval-response' &&
            type !== 'tool-call'
          ? type.slice('tool-'.length)
          : null);

    let content = '';
    if (state === 'output-error') {
      content =
        (invocation && typeof invocation.errorText === 'string' ? invocation.errorText : null) ??
        (typeof (part as any).errorText === 'string' ? (part as any).errorText : 'Tool execution error');
    } else if (state === 'output-denied') {
      const approval = (invocation as any)?.approval ?? (part as any).approval;
      content =
        approval && typeof approval.reason === 'string' && approval.reason.length > 0
          ? approval.reason
          : 'Tool execution denied';
    } else {
      const outputValue = invocation ? invocation.result ?? invocation.output : (part as any).output;
      content = toolOutputToContent(outputValue);
    }

    output.push({
      role: 'tool',
      content,
      tool_call_id: toolCallId,
      ...(toolName ? { name: toolName } : {}),
    });
    seen.add(toolCallId);
  }

  return output;
}

function toCoreMessagesFromModelMessages(input: unknown): Message[] {
  if (!Array.isArray(input)) {
    return [];
  }

  const output: Message[] = [];
  for (const modelMessage of input) {
    if (!modelMessage || typeof modelMessage !== 'object') {
      continue;
    }

    const role = (modelMessage as any).role;
    if (role === 'system' || role === 'user') {
      output.push({
        role,
        content: textFromMixedContent((modelMessage as any).content),
      });
      continue;
    }

    if (role === 'assistant') {
      const content = textFromMixedContent((modelMessage as any).content);
      const toolCalls: NonNullable<Message['tool_calls']> = [];
      if (Array.isArray((modelMessage as any).content)) {
        for (const part of (modelMessage as any).content) {
          if (!part || typeof part !== 'object' || (part as any).type !== 'tool-call') {
            continue;
          }
          const id = typeof (part as any).toolCallId === 'string' ? (part as any).toolCallId : '';
          const name = typeof (part as any).toolName === 'string' ? (part as any).toolName : '';
          if (!id || !name) {
            continue;
          }
          toolCalls.push({
            id,
            type: 'function',
            function: {
              name,
              arguments: toJsonString((part as any).input),
            },
          });
        }
      }
      if (content.length > 0 || toolCalls.length > 0) {
        output.push({
          role: 'assistant',
          content,
          ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {}),
        });
      }
      continue;
    }

    if (role === 'tool' && Array.isArray((modelMessage as any).content)) {
      for (const part of (modelMessage as any).content) {
        if (!part || typeof part !== 'object' || (part as any).type !== 'tool-result') {
          continue;
        }
        const toolCallId =
          typeof (part as any).toolCallId === 'string' ? (part as any).toolCallId : undefined;
        const toolName = typeof (part as any).toolName === 'string' ? (part as any).toolName : undefined;
        output.push({
          role: 'tool',
          content: toolOutputToContent((part as any).output),
          ...(toolCallId ? { tool_call_id: toolCallId } : {}),
          ...(toolName ? { name: toolName } : {}),
        });
      }
    }
  }

  return output;
}

async function tryToCoreMessagesWithAi(input: unknown): Promise<Message[] | null> {
  if (!Array.isArray(input) || input.length === 0) {
    return [];
  }

  if (
    input.some(
      (m: any) =>
        m?.role === 'tool' ||
        typeof m?.tool_call_id === 'string' ||
        (Array.isArray(m?.tool_calls) && m.tool_calls.length > 0)
    )
  ) {
    return null;
  }

  try {
    const mod = await import('ai');
    const convertToModelMessages = (mod as any).convertToModelMessages;
    if (typeof convertToModelMessages !== 'function') {
      return null;
    }

    const uiMessages = input
      .map((m: any) => {
        if (!m || typeof m !== 'object') {
          return null;
        }
        const role = m.role;
        if (role !== 'system' && role !== 'user' && role !== 'assistant') {
          return null;
        }
        if (Array.isArray(m.parts)) {
          return { role, parts: m.parts };
        }
        return {
          role,
          parts: [{ type: 'text', text: textFromMixedContent(m.content) }],
        };
      })
      .filter(Boolean);

    if (uiMessages.length !== input.length) {
      return null;
    }

    const modelMessages = await convertToModelMessages(uiMessages as any);
    return toCoreMessagesFromModelMessages(modelMessages);
  } catch {
    return null;
  }
}

function toCoreMessagesLegacy(input: unknown): Message[] {
  if (!Array.isArray(input)) {
    return [];
  }

  const isMessageRole = (role: unknown): role is Message['role'] =>
    role === 'system' || role === 'user' || role === 'assistant' || role === 'tool';

  const output: Message[] = [];
  for (const m of input) {
    const role = (m as any)?.role;
    if (!isMessageRole(role)) {
      continue;
    }

    const content = textFromMixedContent((m as any)?.content) || textFromMixedContent((m as any)?.parts);
    const msg: Message = { role, content };

    if (typeof (m as any)?.name === 'string') {
      msg.name = (m as any).name;
    }
    if (typeof (m as any)?.tool_call_id === 'string') {
      msg.tool_call_id = (m as any).tool_call_id;
    }

    const toolCalls = coerceToolCalls((m as any)?.tool_calls) ?? coerceToolCallsFromParts((m as any)?.parts);
    if (toolCalls) {
      msg.tool_calls = toolCalls;
    }

    if (role !== 'assistant' || msg.content.length > 0 || (msg.tool_calls && msg.tool_calls.length > 0)) {
      output.push(msg);
    }

    if (role === 'assistant') {
      output.push(...toolMessagesFromParts((m as any)?.parts));
    }
  }

  return output;
}

async function toCoreMessages(input: unknown): Promise<Message[]> {
  const aiMessages = await tryToCoreMessagesWithAi(input);
  if (aiMessages) {
    return aiMessages;
  }
  return toCoreMessagesLegacy(input);
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
  runOptions: AgentRunLikeOptions,
  resolvedToolExecutor: ToolExecutor | undefined,
  signal?: AbortSignal
) {
  const bufferedToolLoop = shouldUseBufferedToolLoop(options, resolvedToolExecutor);

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        if (bufferedToolLoop) {
          const loop = await runBufferedToolLoop(
            agent,
            input,
            runOptions,
            resolvedToolExecutor as ToolExecutor,
            signal
          );
          if (!signal?.aborted && loop.result?.content) {
            controller.enqueue(encodeUtf8(loop.result.content));
          }
        } else {
          for await (const event of agent.stream(input, buildAgentStreamOptions(runOptions) as any)) {
            if (signal?.aborted) {
              break;
            }
            if (event.type === StreamEventType.CHUNK) {
              controller.enqueue(encodeUtf8(event.content));
            }
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
  runOptions: AgentRunLikeOptions,
  resolvedToolExecutor: ToolExecutor | undefined,
  signal?: AbortSignal
) {
  const bufferedToolLoop = shouldUseBufferedToolLoop(options, resolvedToolExecutor);
  const emitCascade = shouldEmitCascadeEvents(options);

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
          if (bufferedToolLoop) {
            const loop = await runBufferedToolLoop(
              agent,
              messages,
              runOptions,
              resolvedToolExecutor as ToolExecutor,
              signal,
              async (step) => {
                if (step.toolCalls.length > 0) {
                  emitToolCallsFinalUi(writer, toolState, step.toolCalls);
                }
              }
            );
            if (emitCascade && loop.result) {
              emitCascadePartUi(writer, 'summary', summarizeCascadeResult(loop.result, loop.steps, loop.maxStepsReached));
            }
            if (!signal?.aborted && loop.result?.content) {
              writer.write({ type: 'text-delta', id: textId, delta: loop.result.content });
            }
          } else {
            for await (const event of agent.stream(messages, buildAgentStreamOptions(runOptions) as any)) {
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
              if (emitCascade) {
                emitCascadeStreamEventUi(writer, event);
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
        if (bufferedToolLoop) {
          const loop = await runBufferedToolLoop(
            agent,
            messages,
            runOptions,
            resolvedToolExecutor as ToolExecutor,
            signal,
            async (step) => {
              if (step.toolCalls.length > 0) {
                emitToolCallsFinalData(controller, formatDataStreamPart, toolState, step.toolCalls);
              }
            }
          );
          if (emitCascade && loop.result) {
            emitCascadePartData(
              controller,
              formatDataStreamPart,
              'summary',
              summarizeCascadeResult(loop.result, loop.steps, loop.maxStepsReached)
            );
          }
          if (!signal?.aborted && loop.result?.content) {
            controller.enqueue(encodeUtf8(formatDataStreamPart('text', loop.result.content)));
          }
        } else {
          for await (const event of agent.stream(messages, buildAgentStreamOptions(runOptions) as any)) {
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
            if (emitCascade) {
              emitCascadeStreamEventData(controller, formatDataStreamPart, event);
            }
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
  const resolvedToolExecutor = resolveToolExecutor(options);
  const baseRunOptions = buildAgentRunOptions(options, resolvedToolExecutor);
  const bufferedToolLoop = shouldUseBufferedToolLoop(options, resolvedToolExecutor);

  return async (request: Request) => {
    const body = (await request.json().catch(() => ({}))) as any;
    const messages = await toCoreMessages(body?.messages);
    const requestOverrides = resolveRequestOverrides(request, body, options);
    const runOptions = mergeAgentRunOptions(baseRunOptions, requestOverrides);

    if (options.stream === false) {
      if (bufferedToolLoop) {
        const loop = await runBufferedToolLoop(
          agent,
          messages,
          runOptions,
          resolvedToolExecutor as ToolExecutor,
          request.signal
        );
        return Response.json(loop.result);
      }
      const result = await agent.run(messages, runOptions as any);
      return Response.json(result);
    }

    const protocol = options.protocol ?? 'data';
    if (protocol === 'text') {
      const stream = await runTextStream(
        agent,
        messages,
        options,
        runOptions,
        resolvedToolExecutor,
        request.signal
      );
      return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    // Prefer UI message stream response when available (AI SDK v5+).
    const uiFactories = await tryGetUiStreamFactories();
    const stream = await runDataStream(
      agent,
      messages,
      options,
      runOptions,
      resolvedToolExecutor,
      request.signal
    );
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
  const resolvedToolExecutor = resolveToolExecutor(options);
  const baseRunOptions = buildAgentRunOptions(options, resolvedToolExecutor);
  const bufferedToolLoop = shouldUseBufferedToolLoop(options, resolvedToolExecutor);

  return async (request: Request) => {
    const body = (await request.json().catch(() => ({}))) as any;
    const prompt = toTextPrompt(body);
    const requestOverrides = resolveRequestOverrides(request, body, options);
    const runOptions = mergeAgentRunOptions(baseRunOptions, requestOverrides);

    if (options.stream === false) {
      if (bufferedToolLoop) {
        const loop = await runBufferedToolLoop(
          agent,
          prompt,
          runOptions,
          resolvedToolExecutor as ToolExecutor,
          request.signal
        );
        return Response.json(loop.result);
      }
      const result = await agent.run(prompt, runOptions as any);
      return Response.json(result);
    }

    const protocol = options.protocol ?? 'data';
    if (protocol === 'text') {
      const stream = await runTextStream(
        agent,
        prompt,
        options,
        runOptions,
        resolvedToolExecutor,
        request.signal
      );
      return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    // Completion endpoint maps to a single user message.
    const messages: Message[] = [{ role: 'user', content: prompt }];
    const uiFactories = await tryGetUiStreamFactories();
    const stream = await runDataStream(
      agent,
      messages,
      options,
      runOptions,
      resolvedToolExecutor,
      request.signal
    );
    if (uiFactories) {
      return uiFactories.createUIMessageStreamResponse({ stream });
    }
    return new Response(stream, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  };
}
