/**
 * Tool Call Parsing
 *
 * Handles parsing tool calls from different provider formats.
 * Each provider returns tool calls in slightly different formats,
 * this class normalizes them to a universal format.
 *
 * @example
 * ```typescript
 * // Parse from OpenAI response
 * const call = ToolCall.fromOpenAI({
 *   id: 'call_123',
 *   type: 'function',
 *   function: {
 *     name: 'get_weather',
 *     arguments: '{"location": "Paris"}'
 *   }
 * });
 *
 * console.log(call.name); // 'get_weather'
 * console.log(call.arguments); // { location: 'Paris' }
 * ```
 */

import { ToolCallFormat } from './formats';

/**
 * Tool call options
 */
export interface ToolCallOptions {
  /** Unique call ID (for tracking) */
  id: string;

  /** Tool name */
  name: string;

  /** Tool arguments (parsed from JSON if needed) */
  arguments: Record<string, any>;

  /** Original format from provider */
  providerFormat: ToolCallFormat;
}

/**
 * Represents a tool call request from the model
 *
 * This is returned by the model when it wants to use a tool.
 *
 * @example
 * ```typescript
 * const call = new ToolCall({
 *   id: 'call_abc',
 *   name: 'calculator',
 *   arguments: { x: 5, y: 3, op: 'add' },
 *   providerFormat: ToolCallFormat.OPENAI
 * });
 * ```
 */
export class ToolCall {
  /** Unique call ID (for tracking) */
  readonly id: string;

  /** Tool name */
  readonly name: string;

  /** Tool arguments */
  readonly arguments: Record<string, any>;

  /** Original format from provider */
  readonly providerFormat: ToolCallFormat;

  constructor(options: ToolCallOptions) {
    this.id = options.id;
    this.name = options.name;
    this.arguments = options.arguments;
    this.providerFormat = options.providerFormat;
  }

  /**
   * Parse OpenAI tool call format
   *
   * @param toolCall - Raw tool call from OpenAI API
   * @returns Standardized ToolCall object
   *
   * @example
   * ```typescript
   * const call = ToolCall.fromOpenAI({
   *   id: 'call_123',
   *   type: 'function',
   *   function: {
   *     name: 'get_weather',
   *     arguments: '{"location": "Paris"}'
   *   }
   * });
   * ```
   */
  static fromOpenAI(toolCall: Record<string, any>): ToolCall {
    let parsedArgs: Record<string, any>;

    try {
      const argsStr = toolCall.function?.arguments || '{}';
      parsedArgs = typeof argsStr === 'string' ? JSON.parse(argsStr) : argsStr;
    } catch (e) {
      console.error(`Failed to parse OpenAI tool call arguments: ${e}`);
      parsedArgs = {};
    }

    return new ToolCall({
      id: toolCall.id || toolCall.function?.id || 'unknown',
      name: toolCall.function?.name || 'unknown',
      arguments: parsedArgs,
      providerFormat: ToolCallFormat.OPENAI,
    });
  }

  /**
   * Parse Anthropic tool use format
   *
   * @param toolUse - Raw tool use from Anthropic API
   * @returns Standardized ToolCall object
   *
   * @example
   * ```typescript
   * const call = ToolCall.fromAnthropic({
   *   type: 'tool_use',
   *   id: 'toolu_123',
   *   name: 'get_weather',
   *   input: {
   *     location: 'Paris'
   *   }
   * });
   * ```
   */
  static fromAnthropic(toolUse: Record<string, any>): ToolCall {
    return new ToolCall({
      id: toolUse.id || 'unknown',
      name: toolUse.name || 'unknown',
      arguments: toolUse.input || {},
      providerFormat: ToolCallFormat.ANTHROPIC,
    });
  }

  /**
   * Parse Ollama tool call format (same as OpenAI)
   *
   * @param toolCall - Raw tool call from Ollama API
   * @returns Standardized ToolCall object
   */
  static fromOllama(toolCall: Record<string, any>): ToolCall {
    return ToolCall.fromOpenAI(toolCall);
  }

  /**
   * Parse vLLM tool call format (same as OpenAI)
   *
   * @param toolCall - Raw tool call from vLLM API
   * @returns Standardized ToolCall object
   */
  static fromVLLM(toolCall: Record<string, any>): ToolCall {
    return ToolCall.fromOpenAI(toolCall);
  }

  /**
   * Parse tool call from any provider format
   *
   * @param provider - Provider name
   * @param toolCall - Raw tool call from provider response
   * @returns Standardized ToolCall object
   *
   * @example
   * ```typescript
   * const openaiCall = ToolCall.fromProvider('openai', rawOpenAICall);
   * const claudeCall = ToolCall.fromProvider('anthropic', rawClaudeCall);
   * ```
   */
  static fromProvider(provider: string, toolCall: Record<string, any>): ToolCall {
    const providerLower = provider.toLowerCase();

    if (['openai', 'groq', 'together', 'huggingface'].includes(providerLower)) {
      return ToolCall.fromOpenAI(toolCall);
    } else if (providerLower === 'anthropic') {
      return ToolCall.fromAnthropic(toolCall);
    } else if (providerLower === 'ollama') {
      return ToolCall.fromOllama(toolCall);
    } else if (providerLower === 'vllm') {
      return ToolCall.fromVLLM(toolCall);
    } else {
      // Try OpenAI format as default
      try {
        return ToolCall.fromOpenAI(toolCall);
      } catch (e) {
        console.error(`Failed to parse tool call from ${provider}: ${e}`);
        throw new Error(`Unsupported tool call format from provider '${provider}'`);
      }
    }
  }

  /**
   * Convert to JSON-serializable object
   */
  toJSON(): Record<string, any> {
    return {
      id: this.id,
      name: this.name,
      arguments: this.arguments,
      providerFormat: this.providerFormat,
    };
  }
}
