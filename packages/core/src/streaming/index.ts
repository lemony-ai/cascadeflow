/**
 * Streaming Module Index
 *
 * Exports all streaming-related functionality:
 * - StreamManager for cascade streaming
 * - ToolStreamManager for tool-calling streaming
 * - Utilities for JSON parsing, validation, confidence estimation
 * - Event types and interfaces
 */

// Re-export from main streaming file
export {
  StreamEventType,
  createStreamEvent,
  isChunkEvent,
  isCompleteEvent,
  isErrorEvent,
  collectStream,
  collectResult,
} from '../streaming';
export type {
  StreamEvent,
  StreamEventData,
  StreamChunk,
  StreamOptions,
} from '../streaming';

// Stream Manager
export {
  StreamManager,
  createStreamManager,
} from './stream-manager';
export type {
  StreamManagerConfig,
  StreamOptions as StreamManagerOptions,
} from './stream-manager';

// Tool Stream Manager
export {
  ToolStreamManager,
  createToolStreamManager,
  ToolStreamEventType,
} from './tool-stream-manager';
export type {
  ToolStreamEvent,
  ToolStreamManagerConfig,
  ToolStreamOptions,
} from './tool-stream-manager';

// Utilities
export {
  ProgressiveJSONParser,
  ToolCallValidator,
  JSONParseState,
  estimateConfidenceFromLogprobs,
  estimateConfidenceFromContent,
  estimateTokens,
} from './utils';
export type {
  ParseResult,
} from './utils';
