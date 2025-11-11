/**
 * Tools Module
 *
 * Universal tool configuration and execution for LLM function calling.
 *
 * @module tools
 */

// Tool Configuration
export {
  ToolConfig,
  createTool,
  tool,
  inferJsonType,
  buildParameterSchema,
} from './config';

export type {
  ToolFunction,
  ToolParameters,
  ToolConfigOptions,
} from './config';

// Tool Execution
export { ToolExecutor } from './executor';

// Tool Calls
export { ToolCall } from './call';
export type { ToolCallOptions } from './call';

// Tool Results
export { ToolResult } from './result';
export type { ToolResultOptions } from './result';

// Format Conversion
export {
  ToolCallFormat,
  toOpenAIFormat,
  toAnthropicFormat,
  toOllamaFormat,
  toProviderFormat,
  getProviderFormatType,
} from './formats';
