/**
 * Anthropic Claude provider implementation with automatic environment detection
 *
 * Works in both Node.js (using Anthropic SDK) and browser (using fetch API).
 * Automatically detects the runtime environment and uses the appropriate method.
 *
 * Supports: Claude 4, Claude 3.7, Claude 3.5, Claude 3
 *
 * Note: Anthropic does not support logprobs natively
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

// Conditional import for Node.js environment
let Anthropic: any;
try {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof (globalThis as any).window === 'undefined') {
    Anthropic = require('@anthropic-ai/sdk').default;
  }
} catch {
  Anthropic = null;
}

/**
 * Anthropic pricing per 1M tokens (October 2025)
 * Source: https://docs.claude.com/en/docs/about-claude/pricing
 *
 * Format: Blended rate (50% input, 50% output)
 */
const ANTHROPIC_PRICING: Record<string, number> = {
  // Claude 4 Series
  'claude-opus-4.1': 45.0, // $15 in + $75 out = $45 blended
  'claude-opus-4': 45.0, // $15 in + $75 out = $45 blended
  'claude-sonnet-4.5': 9.0, // $3 in + $15 out = $9 blended
  'claude-sonnet-4': 9.0, // $3 in + $15 out = $9 blended

  // Claude 3.7 Series
  'claude-sonnet-3.7': 9.0, // $3 in + $15 out = $9 blended

  // Claude 3.5 Series
  'claude-3-5-sonnet': 9.0, // $3 in + $15 out = $9 blended
  'claude-sonnet-3-5': 9.0, // Alternative naming
  'claude-3-5-haiku': 3.0, // $1 in + $5 out = $3 blended
  'claude-haiku-3-5': 3.0, // Alternative naming

  // Claude 3 Series
  'claude-3-opus': 45.0, // $15 in + $75 out = $45 blended
  'claude-3-sonnet': 9.0, // $3 in + $15 out = $9 blended
  'claude-3-haiku': 0.75, // $0.25 in + $1.25 out = $0.75 blended
};

/**
 * Anthropic provider with automatic environment detection
 *
 * Automatically uses:
 * - Anthropic SDK in Node.js
 * - Fetch API in browser
 */
export class AnthropicProvider extends BaseProvider {
  readonly name = 'anthropic';
  private client: any = null;
  private useSDK: boolean;
  private baseUrl: string;

  constructor(config: ModelConfig) {
    super(config);

    // Detect environment and initialize accordingly
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    this.useSDK = typeof (globalThis as any).window === 'undefined' && Anthropic !== null;
    this.baseUrl = config.baseUrl || 'https://api.anthropic.com/v1';

    if (this.useSDK) {
      // Node.js: Use SDK
      this.client = new Anthropic({ apiKey: this.getApiKey() });
    }
    // Browser: Will use fetch in generate()
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    if (this.useSDK) {
      return this.generateWithSDK(request);
    } else {
      return this.generateWithFetch(request);
    }
  }

  /**
   * Stream a completion
   */
  async *stream(request: ProviderRequest): AsyncIterable<StreamChunk> {
    if (this.useSDK) {
      yield* this.streamWithSDK(request);
    } else {
      yield* this.streamWithFetch(request);
    }
  }

  /**
   * Stream using Anthropic SDK (Node.js)
   */
  private async *streamWithSDK(request: ProviderRequest): AsyncIterable<StreamChunk> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const anthropicMessages = this.convertToAnthropicMessages(messages);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const stream = await this.client.messages.stream({
        model: request.model || this.config.name,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        messages: anthropicMessages,
        system: request.systemPrompt,
        tools,
        ...request.extra,
      });

      for await (const event of stream) {
        if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
          yield {
            content: event.delta.text,
            done: false,
            raw: event,
          };
        } else if (event.type === 'message_stop') {
          yield {
            content: '',
            done: true,
            finish_reason: 'stop',
            raw: event,
          };
        }
      }
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Stream using fetch API (Browser) with SSE parsing
   */
  private async *streamWithFetch(request: ProviderRequest): AsyncIterable<StreamChunk> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const anthropicMessages = this.convertToAnthropicMessages(messages);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const body: any = {
        model: request.model || this.config.name,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        messages: anthropicMessages,
        stream: true,
        ...request.extra,
      };

      if (request.systemPrompt) {
        body.system = request.systemPrompt;
      }

      if (request.temperature !== undefined) {
        body.temperature = request.temperature;
      } else if (this.config.temperature !== undefined) {
        body.temperature = this.config.temperature;
      } else {
        body.temperature = 0.7;
      }

      if (tools) {
        body.tools = tools;
      }

      const response = await fetch(`${this.baseUrl}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.getApiKey(),
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`Anthropic API error: ${response.status} ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      // Parse SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || line.startsWith(':')) continue;

          if (line.startsWith('event: ') || line.startsWith('data: ')) {
            const isEvent = line.startsWith('event: ');
            const data = line.slice(isEvent ? 7 : 6);

            if (!isEvent) {
              try {
                const parsed = JSON.parse(data);

                // Handle content delta events
                if (parsed.type === 'content_block_delta' && parsed.delta?.type === 'text_delta') {
                  yield {
                    content: parsed.delta.text,
                    done: false,
                    raw: parsed,
                  };
                } else if (parsed.type === 'message_stop') {
                  yield {
                    content: '',
                    done: true,
                    finish_reason: 'stop',
                    raw: parsed,
                  };
                  return;
                }
              } catch (e) {
                // Skip invalid JSON
                continue;
              }
            }
          }
        }
      }
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Generate using Anthropic SDK (Node.js)
   */
  private async generateWithSDK(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const anthropicMessages = this.convertToAnthropicMessages(messages);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const completion = await this.client.messages.create({
        model: request.model || this.config.name,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        messages: anthropicMessages,
        system: request.systemPrompt,
        tools,
        ...request.extra,
      });

      // Extract text content
      const textContent = completion.content
        .filter((block: any) => block.type === 'text')
        .map((block: any) => block.text)
        .join('');

      // Extract tool calls
      const toolCalls = completion.content
        .filter((block: any) => block.type === 'tool_use')
        .map((block: any) => ({
          id: block.id,
          type: 'function' as const,
          function: {
            name: block.name,
            arguments: JSON.stringify(block.input),
          },
        }));

      return {
        content: textContent,
        model: completion.model,
        usage: {
          prompt_tokens: completion.usage.input_tokens,
          completion_tokens: completion.usage.output_tokens,
          total_tokens: completion.usage.input_tokens + completion.usage.output_tokens,
        },
        finish_reason: completion.stop_reason || undefined,
        tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
        raw: completion,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Generate using fetch API (Browser)
   */
  private async generateWithFetch(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const anthropicMessages = this.convertToAnthropicMessages(messages);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const body: any = {
        model: request.model || this.config.name,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        messages: anthropicMessages,
        ...request.extra,
      };

      if (request.systemPrompt) {
        body.system = request.systemPrompt;
      }

      if (request.temperature !== undefined) {
        body.temperature = request.temperature;
      } else if (this.config.temperature !== undefined) {
        body.temperature = this.config.temperature;
      } else {
        body.temperature = 0.7;
      }

      if (tools) {
        body.tools = tools;
      }

      const response = await fetch(`${this.baseUrl}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.getApiKey(),
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`Anthropic API error: ${response.status} ${response.statusText}`);
      }

      const completion: any = await response.json();

      // Extract text content
      const textContent = completion.content
        .filter((block: any) => block.type === 'text')
        .map((block: any) => block.text)
        .join('');

      // Extract tool calls
      const toolCalls = completion.content
        .filter((block: any) => block.type === 'tool_use')
        .map((block: any) => ({
          id: block.id,
          type: 'function' as const,
          function: {
            name: block.name,
            arguments: JSON.stringify(block.input),
          },
        }));

      return {
        content: textContent,
        model: completion.model,
        usage: {
          prompt_tokens: completion.usage.input_tokens,
          completion_tokens: completion.usage.output_tokens,
          total_tokens: completion.usage.input_tokens + completion.usage.output_tokens,
        },
        finish_reason: completion.stop_reason || undefined,
        tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
        raw: completion,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    const totalTokens = promptTokens + completionTokens;
    const modelLower = model.toLowerCase();

    // Find matching rate (try prefix match)
    for (const [modelPrefix, rate] of Object.entries(ANTHROPIC_PRICING)) {
      if (modelLower.includes(modelPrefix)) {
        return (totalTokens / 1_000_000) * rate;
      }
    }

    // Default to Sonnet pricing if unknown
    return (totalTokens / 1_000_000) * 9.0;
  }

  /**
   * Convert generic messages to Anthropic format
   */
  private convertToAnthropicMessages(messages: Message[]): any[] {
    const anthropicMessages: any[] = [];

    for (const msg of messages) {
      // Skip system messages (handled separately in systemPrompt)
      if (msg.role === 'system') {
        continue;
      }

      if (msg.role === 'user') {
        anthropicMessages.push({
          role: 'user',
          content: msg.content,
        });
      } else if (msg.role === 'assistant') {
        anthropicMessages.push({
          role: 'assistant',
          content: msg.content,
        });
      } else if (msg.role === 'tool') {
        // Anthropic format for tool results
        anthropicMessages.push({
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: msg.tool_call_id || '',
              content: msg.content,
            },
          ],
        });
      }
    }

    return anthropicMessages;
  }

  /**
   * Convert generic tools to Anthropic format
   */
  private convertTools(tools: Tool[]): any[] {
    return tools.map((tool) => ({
      name: tool.function.name,
      description: tool.function.description,
      input_schema: tool.function.parameters,
    }));
  }
}
