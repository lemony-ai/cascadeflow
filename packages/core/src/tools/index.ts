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
