/**
 * Streaming types and interfaces for cascadeflow
 *
 * Based on Python streaming implementation with TypeScript/JavaScript patterns
 */

/**
 * Types of streaming events
 */
export enum StreamEventType {
  /** Routing decision made */
  ROUTING = 'routing',

  /** Content chunk received */
  CHUNK = 'chunk',

  /** Draft quality decision */
  DRAFT_DECISION = 'draft_decision',

  /** Switching to verifier model */
  SWITCH = 'switch',

  /** Streaming complete */
  COMPLETE = 'complete',

  /** Error occurred */
  ERROR = 'error',
}

/**
 * Metadata for streaming events
 */
export interface StreamEventData {
  /** Model being used */
  model?: string;

  /** Current phase (draft/verifier/direct) */
  phase?: 'draft' | 'verifier' | 'direct';

  /** Provider name */
  provider?: string;

  /** Routing strategy */
  strategy?: string;

  /** Query complexity */
  complexity?: string;

  /** Draft accepted flag */
  accepted?: boolean;

  /** Quality score */
  score?: number;

  /** Confidence score */
  confidence?: number;

  /** Draft model name */
  draft_model?: string;

  /** Verifier model name */
  verifier_model?: string;

  /** Reason for decision/routing */
  reason?: string;

  /** Checks passed */
  checks_passed?: boolean;

  /** Quality threshold */
  quality_threshold?: number;

  /** Model switching from */
  from_model?: string;

  /** Model switching to */
  to_model?: string;

  /** Final result data */
  result?: any;

  /** Error information */
  error?: string;

  /** Error type */
  type?: string;

  /** Whether streaming is supported */
  streaming_supported?: boolean;

  /** Additional metadata */
  [key: string]: any;
}

/**
 * Individual streaming event
 */
export interface StreamEvent {
  /** Event type */
  type: StreamEventType;

  /** Content chunk (for CHUNK events) */
  content: string;

  /** Event metadata */
  data: StreamEventData;
}

/**
 * Provider-level stream chunk
 *
 * This is what providers yield when streaming
 */
export interface StreamChunk {
  /** Content delta */
  content: string;

  /** Whether this is the final chunk */
  done?: boolean;

  /** Token usage (if available mid-stream) */
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };

  /** Finish reason (if done) */
  finish_reason?: string;

  /** Tool calls (if any) */
  tool_calls?: any[];

  /** Log probability for this chunk (if available) */
  logprob?: number;

  /** Raw chunk from provider */
  raw?: any;
}

/**
 * Options for streaming
 */
export interface StreamOptions {
  /** Maximum tokens to generate */
  maxTokens?: number;

  /** Temperature (0-2) */
  temperature?: number;

  /** System prompt */
  systemPrompt?: string;

  /** Tools available */
  tools?: any[];

  /** Force direct execution (skip cascade) */
  forceDirect?: boolean;

  /** Enable quality validation */
  enableQualityCheck?: boolean;

  /** Quality threshold (0-1) */
  qualityThreshold?: number;
}

/**
 * Create a StreamEvent
 */
export function createStreamEvent(
  type: StreamEventType,
  content: string = '',
  data: StreamEventData = {}
): StreamEvent {
  return {
    type,
    content,
    data,
  };
}

/**
 * Helper to check if event is a chunk
 */
export function isChunkEvent(event: StreamEvent): boolean {
  return event.type === StreamEventType.CHUNK;
}

/**
 * Helper to check if event is complete
 */
export function isCompleteEvent(event: StreamEvent): boolean {
  return event.type === StreamEventType.COMPLETE;
}

/**
 * Helper to check if event is an error
 */
export function isErrorEvent(event: StreamEvent): boolean {
  return event.type === StreamEventType.ERROR;
}

/**
 * Collect all chunks from a stream into a single string
 */
export async function collectStream(
  stream: AsyncIterable<StreamEvent>
): Promise<string> {
  let content = '';

  for await (const event of stream) {
    if (isChunkEvent(event)) {
      content += event.content;
    }
  }

  return content;
}

/**
 * Collect final result from stream
 */
export async function collectResult(
  stream: AsyncIterable<StreamEvent>
): Promise<any> {
  let finalResult: any = null;

  for await (const event of stream) {
    if (isCompleteEvent(event)) {
      finalResult = event.data.result;
    }
  }

  return finalResult;
}
