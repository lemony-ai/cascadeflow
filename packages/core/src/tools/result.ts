/**
 * Tool Result Formatting
 *
 * Handles formatting tool execution results for different providers.
 * After tools execute, results must be sent back to the model in the
 * provider's expected format.
 *
 * @example
 * ```typescript
 * const result = new ToolResult({
 *   callId: 'call_123',
 *   name: 'get_weather',
 *   result: { temp: 22, condition: 'sunny' },
 *   executionTimeMs: 45.2
 * });
 *
 * const openaiMsg = result.toOpenAIMessage();
 * const anthropicMsg = result.toAnthropicMessage();
 * ```
 */

/**
 * Tool result options
 */
export interface ToolResultOptions {
  /** ID of the tool call */
  callId: string;

  /** Tool name */
  name: string;

  /** Tool output (null if error) */
  result: any;

  /** Error message if tool failed */
  error?: string;

  /** How long tool took (milliseconds) */
  executionTimeMs?: number;
}

/**
 * Result from executing a tool
 *
 * This is passed back to the model after tool execution.
 *
 * @example Basic usage
 * ```typescript
 * const result = new ToolResult({
 *   callId: 'call_abc',
 *   name: 'calculator',
 *   result: 42,
 *   executionTimeMs: 12.5
 * });
 *
 * console.log(result.success); // true
 * ```
 *
 * @example With error
 * ```typescript
 * const errorResult = new ToolResult({
 *   callId: 'call_abc',
 *   name: 'calculator',
 *   result: null,
 *   error: 'Division by zero'
 * });
 *
 * console.log(errorResult.success); // false
 * ```
 */
export class ToolResult {
  /** ID of the tool call */
  readonly callId: string;

  /** Tool name */
  readonly name: string;

  /** Tool output */
  readonly result: any;

  /** Error message if tool failed */
  readonly error?: string;

  /** How long tool took (milliseconds) */
  readonly executionTimeMs?: number;

  constructor(options: ToolResultOptions) {
    this.callId = options.callId;
    this.name = options.name;
    this.result = options.result;
    this.error = options.error;
    this.executionTimeMs = options.executionTimeMs;
  }

  /**
   * Whether tool execution succeeded
   */
  get success(): boolean {
    return this.error === undefined || this.error === null;
  }

  /**
   * Format as OpenAI tool result message
   *
   * Used by: OpenAI, Groq, Together, vLLM
   *
   * @returns OpenAI format message
   *
   * @example
   * ```typescript
   * const msg = result.toOpenAIMessage();
   * // Returns: {
   * //   tool_call_id: 'call_123',
   * //   role: 'tool',
   * //   name: 'get_weather',
   * //   content: "{'temp': 22, 'condition': 'sunny'}"
   * // }
   * ```
   */
  toOpenAIMessage(): Record<string, any> {
    const content = !this.error
      ? typeof this.result === 'string'
        ? this.result
        : JSON.stringify(this.result)
      : `Error: ${this.error}`;

    return {
      tool_call_id: this.callId,
      role: 'tool',
      name: this.name,
      content,
    };
  }

  /**
   * Format as Anthropic tool result message
   *
   * Key difference: Uses content blocks instead of role="tool"
   *
   * @returns Anthropic format message
   *
   * @example
   * ```typescript
   * const msg = result.toAnthropicMessage();
   * // Returns: {
   * //   role: 'user',
   * //   content: [{
   * //     type: 'tool_result',
   * //     tool_use_id: 'toolu_123',
   * //     content: "{'temp': 22}",
   * //     is_error: false
   * //   }]
   * // }
   * ```
   */
  toAnthropicMessage(): Record<string, any> {
    const content = !this.error
      ? typeof this.result === 'string'
        ? this.result
        : JSON.stringify(this.result)
      : `Error: ${this.error}`;

    return {
      role: 'user',
      content: [
        {
          type: 'tool_result',
          tool_use_id: this.callId,
          content,
          is_error: this.error !== undefined && this.error !== null,
        },
      ],
    };
  }

  /**
   * Format as Ollama tool result (same as OpenAI)
   *
   * @returns Ollama format message
   */
  toOllamaMessage(): Record<string, any> {
    return this.toOpenAIMessage();
  }

  /**
   * Format as vLLM tool result (same as OpenAI)
   *
   * @returns vLLM format message
   */
  toVLLMMessage(): Record<string, any> {
    return this.toOpenAIMessage();
  }

  /**
   * Format as provider-specific message
   *
   * @param provider - Provider name
   * @returns Tool result in provider's expected format
   *
   * @example
   * ```typescript
   * const openaiMsg = result.toProviderMessage('openai');
   * const claudeMsg = result.toProviderMessage('anthropic');
   * ```
   */
  toProviderMessage(provider: string): Record<string, any> {
    const providerLower = provider.toLowerCase();

    if (['openai', 'groq', 'together', 'huggingface'].includes(providerLower)) {
      return this.toOpenAIMessage();
    } else if (providerLower === 'anthropic') {
      return this.toAnthropicMessage();
    } else if (providerLower === 'ollama') {
      return this.toOllamaMessage();
    } else if (providerLower === 'vllm') {
      return this.toVLLMMessage();
    } else {
      // Default to OpenAI format
      console.warn(`Unknown provider '${provider}', using OpenAI format`);
      return this.toOpenAIMessage();
    }
  }

  /**
   * Convert to JSON-serializable object
   */
  toJSON(): Record<string, any> {
    return {
      callId: this.callId,
      name: this.name,
      result: this.result,
      error: this.error,
      executionTimeMs: this.executionTimeMs,
      success: this.success,
    };
  }
}
